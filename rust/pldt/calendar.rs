//! Scalar/positional integer calendar factories with a single native exit.
use super::finish::{Failure, Kind, Rows};
use super::zones::{Context, Policies, PolicyContext};
use crate::batch_shape::{Column, length};
use crate::epoch::Unit;
use crate::temporal_zone::{Zone, ZoneData};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;
const NS_DAY: i128 = 86_400_000_000_000;
#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "lowercase")]
enum Operation {
    Ordinal,
    Iso,
    Doy,
}
impl Operation {
    fn entry(self) -> &'static str {
        match self {
            Self::Ordinal => "Pldt.fromordinal",
            Self::Iso => "Pldt.fromisocalendar",
            Self::Doy => "Pldt.fromdayofyear",
        }
    }
    fn arity(self) -> usize {
        match self {
            Self::Ordinal => 1,
            Self::Iso => 3,
            Self::Doy => 2,
        }
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    operation: Operation,
    unit: String,
    target: Option<ZoneData>,
    policy: Policies,
    scalars: Vec<bool>,
    mask_scalar: bool,
}
fn selected(unit: &str) -> Result<Unit, Failure> {
    match unit {
        "ms" => Ok(Unit::Millisecond),
        "us" => Ok(Unit::Microsecond),
        "ns" => Ok(Unit::Nanosecond),
        _ => Err(Failure::new(Kind::Value, "unit must be ms/us/ns")),
    }
}
fn integer_dtype(dtype: &DataType) -> bool {
    dtype.is_integer()
        || matches!(
            dtype,
            DataType::Null | DataType::Float32 | DataType::Float64 | DataType::String
        )
}
fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    let arity = kwargs.operation.arity();
    polars_ensure!(kwargs.version==1&&kwargs.scalars.len()==arity&&(fields.len()==arity||fields.len()==arity+1),InvalidOperation:"invalid calendar factory preparation");
    for field in fields.iter().take(arity) {
        polars_ensure!(integer_dtype(field.dtype()),InvalidOperation:"{}: components require integer dtype",kwargs.operation.entry());
    }
    if let Some(mask) = fields.get(arity) {
        polars_ensure!(mask.dtype()==&DataType::Boolean,InvalidOperation:"ambiguous Expr requires Boolean");
    }
    let unit = selected(&kwargs.unit).map_err(|error| error.polars(kwargs.operation.entry()))?;
    let zone = TimeZone::opt_try_new(kwargs.target.map(|zone| zone.key))?;
    Ok(Field::new(
        fields[0].name().clone(),
        DataType::Datetime(super::input::resolution(unit), zone),
    ))
}
fn values(source: &Series, scalar: bool) -> Result<Column<Option<i64>>, Failure> {
    let values = match source.dtype() {
        DataType::Null => vec![None; source.len()],
        dtype if dtype.is_integer() => source
            .strict_cast(&DataType::Int64)
            .map_err(|_| Failure::new(Kind::Capacity, "integer component exceeds signed64"))?
            .i64()
            .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
            .iter()
            .collect(),
        DataType::Float32 | DataType::Float64 => {
            let cast = source
                .strict_cast(&DataType::Float64)
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?;
            let mut out = Vec::with_capacity(source.len());
            for (row, value) in cast
                .f64()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                if value.is_some_and(|value| !value.is_nan()) {
                    return Err(Failure::new(
                        Kind::Type,
                        "calendar components require integer index values, not floats",
                    )
                    .at(row));
                }
                out.push(None);
            }
            out
        }
        DataType::String => {
            let mut out = Vec::with_capacity(source.len());
            for (row, value) in source
                .str()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                if value.is_some_and(|value| !super::text::missing(value)) {
                    return Err(Failure::new(
                        Kind::Type,
                        "calendar components do not parse text numbers",
                    )
                    .at(row));
                }
                out.push(None);
            }
            out
        }
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "calendar components require integers, not Boolean/date/duration values",
            ));
        }
    };
    if scalar {
        if values.len() != 1 {
            return Err(Failure::new(
                Kind::Runtime,
                "a logical scalar component must contain one value",
            ));
        }
        Ok(Column::Scalar(values[0]))
    } else {
        Ok(Column::Values(values))
    }
}
fn calculate(
    sources: &[Series],
    scalars: &[bool],
    size: Option<usize>,
    operation: Operation,
    unit: Unit,
    target: Option<&Zone>,
    policy: &Policies,
) -> Result<Series, Failure> {
    if sources.len() != operation.arity() || scalars.len() != sources.len() {
        return Err(Failure::new(
            Kind::Runtime,
            "invalid calendar component arity",
        ));
    }
    let values = sources
        .iter()
        .zip(scalars)
        .map(|(source, scalar)| values(source, *scalar))
        .collect::<Result<Vec<_>, _>>()?;
    let size = length(values.iter().map(Column::len), size)
        .map_err(|message| Failure::new(Kind::Value, message))?;
    // Validate every supplied low component even when another value is missing,
    // a column is empty, or all-scalar output explicitly requests zero rows.
    for (index, value) in values.iter().enumerate().skip(1) {
        let slice = match value {
            Column::Scalar(value) => std::slice::from_ref(value),
            Column::Values(values) => values.as_slice(),
        };
        if slice.iter().flatten().any(|value| *value < 1) {
            return Err(Failure::new(
                Kind::Value,
                format!(
                    "{} must be at least 1",
                    if matches!(operation, Operation::Doy) {
                        "doy"
                    } else if index == 1 {
                        "ISO week"
                    } else {
                        "ISO weekday"
                    }
                ),
            ));
        }
    }
    policy.check_len(size)?;
    let mut rows = Rows::new(Unit::Microsecond);
    if scalars.iter().all(|value| *value) {
        push(&mut rows, &values, 0, operation)?;
        rows.repeat(size)?;
    } else {
        for row in 0..size {
            push(&mut rows, &values, row, operation)?;
        }
    }
    rows.finish(sources[0].name().clone(), Some(unit), target, policy, false)
}
fn push(
    rows: &mut Rows,
    values: &[Column<Option<i64>>],
    row: usize,
    operation: Operation,
) -> Result<(), Failure> {
    let a = values[0].get(row);
    let b = values.get(1).map(|value| value.get(row));
    let c = values.get(2).map(|value| value.get(row));
    if a.is_none()
        || b.is_some_and(|value| value.is_none())
        || c.is_some_and(|value| value.is_none())
    {
        rows.missing();
        return Ok(());
    }
    let a =
        a.ok_or_else(|| Failure::new(Kind::Runtime, "validated calendar component was lost"))?;
    let ordinal = match operation {
        Operation::Ordinal => Ok(a),
        Operation::Doy => crate::calendar::year_day_ordinal(a, b.flatten().unwrap_or(1)),
        Operation::Iso => {
            crate::calendar::iso_ordinal(a, b.flatten().unwrap_or(1), c.flatten().unwrap_or(1))
        }
    }
    .map_err(|message| Failure::new(Kind::Capacity, message).at(row))?;
    rows.push(
        (i128::from(ordinal) - 719_163) * NS_DAY,
        0,
        false,
        Unit::Microsecond,
    );
    Ok(())
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_calendar(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    let arity = kwargs.operation.arity();
    let entry = kwargs.operation.entry();
    polars_ensure!(kwargs.version==1&&(inputs.len()==arity||inputs.len()==arity+1),InvalidOperation:"invalid calendar factory inputs");
    let target = kwargs
        .target
        .map(Zone::from_data)
        .transpose()
        .map_err(|message| polars_err!(ComputeError:"{}: {}",entry,message))?;
    let policy = if let Some(mask) = inputs.get(arity) {
        kwargs
            .policy
            .with_expression_mask(mask, kwargs.mask_scalar)
            .map_err(|error| polars_err!(ComputeError:"{}: {}",entry,error))?
    } else {
        kwargs.policy
    };
    // Scalar Exprs evaluate as one logical row and can be broadcast by Polars.
    let size = kwargs.scalars.iter().all(|value| *value).then_some(1);
    calculate(
        &inputs[..arity],
        &kwargs.scalars,
        size,
        kwargs.operation,
        selected(&kwargs.unit).map_err(|error| error.polars(entry))?,
        target.as_ref(),
        &policy,
    )
    .map_err(|error| error.polars(entry))
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared integer components and final date schema"
)]
#[pyo3(signature=(sources,scalars,target,kind,unit,tz,policy,size=None))]
fn _pldt_calendar<'py>(
    sources: Vec<PySeries>,
    scalars: Vec<bool>,
    target: &Bound<'py, PyAny>,
    kind: &str,
    unit: &str,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    size: Option<usize>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let operation = match kind {
        "ordinal" => Operation::Ordinal,
        "doy" => Operation::Doy,
        "iso" => Operation::Iso,
        _ => return Err(crate::error_context::runtime("unknown calendar operation")),
    };
    let inputs = sources
        .into_iter()
        .map(|source| source.0)
        .collect::<Vec<_>>();
    let result = calculate(
        &inputs,
        &scalars,
        size,
        operation,
        selected(unit).map_err(|error| error.python(py, operation.entry()))?,
        tz.as_ref().map(|zone| &zone.value),
        &policy.value,
    )
    .map_err(|error| error.python(py, operation.entry()))?;
    super::export(py, &result, target)
}
#[pyfunction]
#[pyo3(signature=(data,column,entry,parameter))]
fn _pldt_integer_objects(
    data: &Bound<'_, PyAny>,
    column: bool,
    entry: &str,
    parameter: &str,
) -> PyResult<(PySeries, bool)> {
    let py = data.py();
    let integer = |value: &Bound<'_, PyAny>| -> PyResult<Option<i64>> {
        if crate::date_input::date_missing(value)? {
            Ok(None)
        } else {
            crate::numeric::index_i64(value).map(Some)
        }
    };
    let scalar = !column && crate::numeric_epoch::scalar(data)?;
    let mut values = Vec::new();
    if scalar {
        values.push(
            integer(data).map_err(|error| {
                crate::error_context::argument(py, error, entry, parameter, data)
            })?,
        );
    } else {
        for (row, item) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let item = item
                .map_err(crate::error_context::external)
                .map_err(|error| {
                    crate::error_context::item(py, error, entry, parameter, row, None, true)
                })?;
            values.push(integer(&item).map_err(|error| {
                crate::error_context::item(py, error, entry, parameter, row, Some(&item), false)
            })?);
        }
    }
    Ok((
        PySeries(
            Int64Chunked::from_iter_options(parameter.into(), values.into_iter()).into_series(),
        ),
        scalar,
    ))
}
#[pyfunction]
fn _pldt_integer_column(py: Python<'_>, source: PySeries) -> PyResult<PySeries> {
    let values =
        values(&source.0, false).map_err(|error| error.python(py, "Pldt calendar component"))?;
    let Column::Values(values) = values else {
        return Err(crate::error_context::runtime("expected integer column"));
    };
    Ok(PySeries(
        Int64Chunked::from_iter_options(source.0.name().clone(), values.into_iter()).into_series(),
    ))
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_calendar, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_integer_column, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_integer_objects, module)?)
}
