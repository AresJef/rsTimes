//! Native Polars column execution, shared by eager calls and expression plugins.
//!
//! The SDK owns the Series/Arrow FFI boundary. Worker calculations below contain
//! no Python objects, imports, callbacks, or implicit GIL acquisition.

mod arithmetic;
mod calendar;
mod combine;
mod dates;
mod factory;
mod finish;
mod input;
mod iso;
mod operations;
mod range;
mod text;
mod timezone;
mod zones;

use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::export::polars_ffi::version_0::export_series;
use serde::Deserialize;
use std::mem::ManuallyDrop;

const EPOCH_ORDINAL: i64 = 719_163;

#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Operation {
    NextMonth,
    IsMonth,
    AddDays,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    operation: Operation,
    argument: i64,
    scalar: bool,
}

fn validate_options(options: &Options) -> PolarsResult<()> {
    polars_ensure!(options.version == 1, InvalidOperation: "unsupported rstimes plugin kwargs version");
    if matches!(options.operation, Operation::IsMonth) {
        polars_ensure!((1..=12).contains(&options.argument), InvalidOperation: "Pldt.is_month: month must be in 1..=12");
    }
    Ok(())
}

fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    validate_options(&kwargs)?;
    let source = fields
        .first()
        .ok_or_else(|| polars_err!(InvalidOperation: "Pldt requires a date source"))?;
    polars_ensure!(matches!(source.dtype(), DataType::Datetime(_, _) | DataType::Date), InvalidOperation: "Pldt requires Date/Datetime input");
    if matches!(kwargs.operation, Operation::IsMonth) {
        Ok(Field::new(source.name().clone(), DataType::Boolean))
    } else if source.dtype() == &DataType::Date {
        Ok(Field::new(
            source.name().clone(),
            DataType::Datetime(TimeUnit::Milliseconds, None),
        ))
    } else {
        Ok(source.clone())
    }
}

fn day_ticks(unit: TimeUnit) -> i64 {
    match unit {
        TimeUnit::Milliseconds => 86_400_000,
        TimeUnit::Microseconds => 86_400_000_000,
        TimeUnit::Nanoseconds => 86_400_000_000_000,
    }
}

fn shift_month(value: i64, per_day: i64) -> PolarsResult<i64> {
    let day = value.div_euclid(per_day);
    let ordinal = day
        .checked_add(EPOCH_ORDINAL)
        .ok_or_else(|| polars_err!(OutOfBounds: "Pldt.to_next_month: date overflow"))?;
    let [year, month, date] = crate::calendar::from_ordinal(ordinal)
        .map_err(|message| polars_err!(OutOfBounds: "Pldt.to_next_month: {}", message))?;
    let (year, month) = if month == 12 {
        (year + 1, 1)
    } else {
        (year, month + 1)
    };
    let target = crate::calendar::checked_ordinal(year, month, date)
        .map_err(|message| polars_err!(OutOfBounds: "Pldt.to_next_month: {}", message))?;
    let ticks = i128::from(target - EPOCH_ORDINAL) * i128::from(per_day)
        + i128::from(value.rem_euclid(per_day));
    i64::try_from(ticks).map_err(|_| polars_err!(OutOfBounds: "Pldt.to_next_month: result exceeds current unit; use as_unit explicitly"))
}

fn execute(inputs: &[Series], options: &Options) -> PolarsResult<Series> {
    validate_options(options)?;
    let source = inputs
        .first()
        .ok_or_else(|| polars_err!(InvalidOperation: "Pldt requires a date source"))?;
    let promoted;
    let source = if source.dtype() == &DataType::Date {
        promoted = source.cast(&DataType::Datetime(TimeUnit::Milliseconds, None))?;
        &promoted
    } else {
        source
    };
    let dates = source.datetime()?;
    let unit = dates.time_unit();
    let zone = dates.time_zone();
    // Region policy resolution is added by W12. Never interpret aware ticks as
    // local wall-clock fields while the native timezone service is incomplete.
    polars_ensure!(zone.is_none(), InvalidOperation: "regional Pldt execution requires the timezone kernel");
    let per_day = day_ticks(unit);
    let values = dates.physical();
    match options.operation {
        Operation::IsMonth => {
            let mut result = BooleanChunkedBuilder::new(source.name().clone(), source.len());
            for value in values.iter() {
                let matches = match value {
                    Some(value) => {
                        let ordinal = value.div_euclid(per_day) + EPOCH_ORDINAL;
                        crate::calendar::from_ordinal(ordinal).map_err(
                            |message| polars_err!(ComputeError: "Pldt.is_month: {}", message),
                        )?[1]
                            == options.argument
                    }
                    None => false,
                };
                result.append_value(matches);
            }
            Ok(result.finish().into_series())
        }
        Operation::NextMonth => {
            let mut result =
                PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
            for value in values.iter() {
                result.append_option(value.map(|value| shift_month(value, per_day)).transpose()?);
            }
            Ok(result
                .finish()
                .into_datetime(unit, zone.clone())
                .into_series())
        }
        Operation::AddDays => {
            let operand = inputs
                .get(1)
                .ok_or_else(|| polars_err!(InvalidOperation: "Pldt.add: days is required"))?;
            polars_ensure!(operand.dtype().is_integer(), InvalidOperation: "Pldt.add: days must contain integers, not booleans or floats");
            polars_ensure!(if options.scalar { operand.len() == 1 } else { operand.len() == source.len() }, ShapeMismatch: "Pldt.add: days column must match the date source length; length one columns are not scalars");
            polars_ensure!(operand.null_count() == 0, InvalidOperation: "Pldt.add: days cannot contain null");
            let operand = operand.strict_cast(&DataType::Int64)?;
            let amounts = operand.i64()?;
            let mut result =
                PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
            let scalar = if options.scalar { amounts.get(0) } else { None };
            for (index, value) in values.iter().enumerate() {
                let amount = scalar
                    .or_else(|| amounts.get(index))
                    .ok_or_else(|| polars_err!(InvalidOperation: "Pldt.add: missing days"))?;
                let shifted = value.map(|value| {
                    let ticks = i128::from(value) + i128::from(amount) * i128::from(per_day);
                    i64::try_from(ticks).map_err(|_| polars_err!(OutOfBounds: "Pldt.add: result exceeds current unit; use as_unit explicitly"))
                }).transpose()?;
                result.append_option(shifted);
            }
            Ok(result
                .finish()
                .into_datetime(unit, zone.clone())
                .into_series())
        }
    }
}

#[polars_expr(output_type_func_with_kwargs = output_field)]
fn pldt_execute(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    execute(inputs, &kwargs)
}

/// Execute an eager column operation through the same Python-free kernel.
///
/// The official SDK imports the source, retaining Arrow owners. Its versioned
/// export protocol constructs the final target directly, without a temporary
/// Python parent Series. Only this entry/exit adapter holds the GIL.
#[pyfunction]
#[pyo3(signature = (source, target, operation, argument, operand, scalar))]
fn _pldt_execute<'py>(
    py: Python<'py>,
    source: PySeries,
    target: &Bound<'py, PyAny>,
    operation: &str,
    argument: i64,
    operand: Option<PySeries>,
    scalar: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let operation = match operation {
        "next_month" => Operation::NextMonth,
        "is_month" => Operation::IsMonth,
        "add_days" => Operation::AddDays,
        _ => {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "unknown rstimes column operation",
            ));
        }
    };
    let options = Options {
        version: 1,
        operation,
        argument,
        scalar,
    };
    let mut inputs = vec![source.0];
    if let Some(operand) = operand {
        inputs.push(operand.0);
    }
    let result = py
        .detach(|| execute(&inputs, &options))
        .map_err(eager_error)?;
    // This is the same SDK-owned SeriesExport transfer as PySeries::into_pyobject.
    // Polars' _import consumes it and assumes responsibility for release callbacks.
    export(py, &result, target)
}

/// Transfer ownership through the SDK's versioned SeriesExport protocol.
pub(super) fn export<'py>(
    _py: Python<'py>,
    result: &Series,
    target: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let export = ManuallyDrop::new(export_series(result));
    target.call_method1("_import", ((&raw const export).addr(),))
}

/// Adapt known native failure categories only at the eager Python boundary.
/// Plugin execution retains the engine's native error protocol instead.
pub(super) fn eager_error(error: PolarsError) -> PyErr {
    match error {
        PolarsError::SchemaMismatch(message) => {
            crate::error_context::type_error(message.to_string())
        }
        PolarsError::OutOfBounds(message) => crate::error_context::overflow(message.to_string()),
        PolarsError::ShapeMismatch(message)
        | PolarsError::InvalidOperation(message)
        | PolarsError::ComputeError(message) => {
            crate::error_context::value_error(message.to_string())
        }
        PolarsError::Python { error } => crate::error_context::external(error.0),
        PolarsError::Context { .. } | PolarsError::ExprContext { .. } => {
            eager_error(error.context_trace())
        }
        other => pyo3_polars::error::PyPolarsErr::from(other).into(),
    }
}

/// Register the eager adapter without importing or requiring Python Polars.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_execute, module)?)?;
    input::configure(module)?;
    text::configure(module)?;
    factory::configure(module)?;
    dates::configure(module)?;
    iso::configure(module)?;
    operations::configure(module)?;
    range::configure(module)?;
    calendar::configure(module)?;
    arithmetic::configure(module)?;
    combine::configure(module)?;
    zones::configure(module)?;
    timezone::configure(module)
}
