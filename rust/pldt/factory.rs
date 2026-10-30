//! Native current-time and numerical factories; one final date column only.
use super::finish::{Failure, Kind, Rows};
use super::input::{resolution, selected};
use super::zones::{Context, Policies, PolicyContext, prepare_host_zone};
use crate::epoch::Unit;
use crate::numeric_epoch::Quantity;
use crate::temporal_zone::{Zone, ZoneData};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;
use std::time::SystemTime;

#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Operation {
    Seconds,
    Micros,
    Timestamp,
    LocalTimestamp,
    UtcTimestamp,
}
impl Operation {
    fn quantity(self) -> Quantity {
        if matches!(self, Self::Micros) {
            Quantity::Microseconds
        } else {
            Quantity::Seconds
        }
    }
    fn entry(self) -> &'static str {
        match self {
            Self::Seconds => "Pldt.fromseconds",
            Self::Micros => "Pldt.frommicroseconds",
            Self::Timestamp => "Pldt.fromtimestamp",
            Self::LocalTimestamp => "Pldt.fromtimestamp",
            Self::UtcTimestamp => "Pldt.utcfromtimestamp",
        }
    }
    fn instant(self) -> bool {
        matches!(
            self,
            Self::Timestamp | Self::LocalTimestamp | Self::UtcTimestamp
        )
    }
}
fn operation(value: &str) -> PyResult<Operation> {
    match value {
        "seconds" => Ok(Operation::Seconds),
        "micros" => Ok(Operation::Micros),
        "timestamp" => Ok(Operation::Timestamp),
        "local_timestamp" => Ok(Operation::LocalTimestamp),
        "utc_timestamp" => Ok(Operation::UtcTimestamp),
        _ => Err(crate::error_context::runtime("unknown numerical factory")),
    }
}
fn output_unit(value: Option<&str>) -> Result<Option<Unit>, Failure> {
    value
        .map(|value| match value {
            "ms" => Ok(Unit::Millisecond),
            "us" => Ok(Unit::Microsecond),
            "ns" => Ok(Unit::Nanosecond),
            _ => Err(Failure::new(Kind::Value, "unit must be ms/us/ns")),
        })
        .transpose()
}

fn current<F: FnOnce() -> Result<i128, &'static str>>(
    count: usize,
    unit: Unit,
    name: PlSmallStr,
    zone: Option<&Zone>,
    naive: bool,
    clock: F,
) -> Result<Series, Failure> {
    count
        .checked_mul(8)
        .filter(|size| *size <= isize::MAX as usize)
        .ok_or_else(|| Failure::new(Kind::Capacity, "size exceeds the native date column range"))?;
    let output_zone = if naive {
        None
    } else {
        TimeZone::opt_try_new(zone.map(Zone::key))
            .map_err(|error| Failure::new(Kind::Value, error.to_string()))?
    };
    let mut values = Vec::new();
    values
        .try_reserve_exact(count)
        .map_err(|_| Failure::new(Kind::Memory, "cannot allocate the requested date column"))?;
    if count != 0 {
        let mut ns = clock().map_err(|message| Failure::new(Kind::Capacity, message))?;
        if naive {
            ns = zone
                .ok_or_else(|| Failure::new(Kind::Runtime, "local clock requires a prepared zone"))?
                .wall(ns)?
        }
        let value = crate::precision::epoch_tick(ns, unit.nanos(), true)
            .map_err(|_| Failure::new(Kind::Capacity, "current clock exceeds the selected unit"))?;
        values.resize(count, value);
    }
    Ok(Int64Chunked::from_vec(name, values)
        .into_datetime(resolution(unit), output_zone)
        .into_series())
}
#[pyfunction]
#[pyo3(signature=(target,count,unit,name,zone,naive))]
fn _pldt_now<'py>(
    target: &Bound<'py, PyAny>,
    count: usize,
    unit: &str,
    name: &str,
    zone: Option<PyRef<'_, Context>>,
    naive: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let unit =
        selected(Some(unit))?.ok_or_else(|| crate::error_context::runtime("clock unit missing"))?;
    let value = current(
        count,
        unit,
        name.into(),
        zone.as_ref().map(|zone| &zone.value),
        naive,
        || crate::clock::system_nanos(SystemTime::now()),
    )
    .map_err(|error| error.python(py, "Pldt.now"))?;
    super::export(py, &value, target)
}

struct Values {
    nanos: Vec<Option<i128>>,
}
fn numeric_failure(error: crate::numeric_epoch::Error) -> Failure {
    match error {
        crate::numeric_epoch::Error::Type(message) => Failure::new(Kind::Type, message),
        crate::numeric_epoch::Error::Capacity(message) => Failure::new(Kind::Capacity, message),
    }
}
fn native_values(source: &Series, operation: Operation) -> Result<Values, Failure> {
    let mut output = Vec::with_capacity(source.len());
    match source.dtype() {
        DataType::Null => output.resize(source.len(), None),
        DataType::String => {
            for (row, value) in source
                .str()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                if value.is_some_and(|value| !super::text::missing(value)) {
                    return Err(Failure::new(
                        Kind::Type,
                        "numeric factories do not parse text numbers",
                    )
                    .at(row));
                }
                output.push(None)
            }
        }
        dtype if dtype.is_integer() => {
            let values = source
                .strict_cast(&DataType::Int128)
                .map_err(|_| Failure::new(Kind::Capacity, "numeric quantity exceeds signed128"))?;
            let scale = if matches!(operation, Operation::Micros) {
                1000
            } else {
                1_000_000_000
            };
            for (row, value) in values
                .i128()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                output.push(
                    value
                        .map(|value| {
                            value.checked_mul(scale).ok_or_else(|| {
                                Failure::new(
                                    Kind::Capacity,
                                    "numeric quantity exceeds native nanoseconds",
                                )
                                .at(row)
                            })
                        })
                        .transpose()?,
                );
            }
        }
        dtype if dtype.is_numeric() => {
            let values = source
                .cast(&DataType::Float64)
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?;
            for (row, value) in values
                .f64()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                output.push(
                    value
                        .map(|value| {
                            crate::numeric_epoch::float_number(value, operation.quantity())
                                .map_err(|error| numeric_failure(error).at(row))
                        })
                        .transpose()?
                        .flatten(),
                );
            }
        }
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "numeric factories require numeric values, not dates, durations or booleans",
            ));
        }
    }
    Ok(Values { nanos: output })
}
fn finish(
    values: Values,
    name: PlSmallStr,
    operation: Operation,
    requested: Option<Unit>,
    target: Option<&Zone>,
    local: Option<&Zone>,
    policy: &Policies,
) -> Result<Series, Failure> {
    policy.check_len(values.nanos.len())?;
    let mut rows = Rows::new(Unit::Microsecond);
    for (row, value) in values.nanos.into_iter().enumerate() {
        let Some(mut ns) = value else {
            rows.missing();
            continue;
        };
        if matches!(operation, Operation::LocalTimestamp) {
            ns = local
                .ok_or_else(|| {
                    Failure::new(
                        Kind::Runtime,
                        "local timestamp requires prepared local rules",
                    )
                })?
                .wall(ns)
                .map_err(|error| Failure::from(error).at(row))?
        }
        let unit = if ns.rem_euclid(1000) == 0 {
            Unit::Microsecond
        } else {
            Unit::Nanosecond
        };
        rows.push(ns, 0, operation.instant(), unit);
    }
    rows.finish(name, requested, target, policy, false)
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    operation: Operation,
    unit: Option<String>,
    target: Option<ZoneData>,
    local: Option<ZoneData>,
    policy: Policies,
    mask_scalar: bool,
}
fn output_field(fields: &[Field], options: Options) -> PolarsResult<Field> {
    polars_ensure!(options.version==1&&!fields.is_empty()&&fields.len()<=2,InvalidOperation:"invalid numeric factory preparation");
    let dtype = fields[0].dtype();
    polars_ensure!(dtype.is_numeric()||matches!(dtype,DataType::Null|DataType::String),InvalidOperation:"numeric factories require numbers, not dates/durations/booleans");
    if let Some(mask) = fields.get(1) {
        polars_ensure!(mask.dtype()==&DataType::Boolean,InvalidOperation:"ambiguous Expr requires Boolean")
    }
    let unit = output_unit(options.unit.as_deref())
        .map_err(|error| error.polars(options.operation.entry()))?;
    let default_allowed = matches!(options.operation, Operation::Micros)
        || dtype.is_integer()
        || matches!(dtype, DataType::Null | DataType::String);
    polars_ensure!(unit.is_some()||default_allowed,InvalidOperation:"floating seconds Expr requires explicit unit (ms/us/ns)");
    let zone = TimeZone::opt_try_new(options.target.map(|zone| zone.key))?;
    Ok(Field::new(
        fields[0].name().clone(),
        DataType::Datetime(resolution(unit.unwrap_or(Unit::Microsecond)), zone),
    ))
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_numbers(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    polars_ensure!(kwargs.version==1&&!inputs.is_empty()&&inputs.len()<=2,InvalidOperation:"invalid numeric factory inputs");
    let entry = kwargs.operation.entry();
    let unit = output_unit(kwargs.unit.as_deref())
        .map_err(|error| error.polars(entry))?
        .or(Some(Unit::Microsecond));
    let target = kwargs
        .target
        .map(Zone::from_data)
        .transpose()
        .map_err(|message| polars_err!(ComputeError:"{}: {}",entry,message))?;
    let local = kwargs
        .local
        .map(Zone::from_data)
        .transpose()
        .map_err(|message| polars_err!(ComputeError:"{}: {}",entry,message))?;
    let policy = if let Some(mask) = inputs.get(1) {
        kwargs
            .policy
            .with_expression_mask(mask, kwargs.mask_scalar)
            .map_err(|error| polars_err!(ComputeError:"{}: {}",entry,error))?
    } else {
        kwargs.policy
    };
    let values =
        native_values(&inputs[0], kwargs.operation).map_err(|error| error.polars(entry))?;
    finish(
        values,
        inputs[0].name().clone(),
        kwargs.operation,
        unit,
        target.as_ref(),
        local.as_ref(),
        &policy,
    )
    .map_err(|error| error.polars(entry))
}

fn actual_number(value: &Bound<'_, PyAny>, quantity: Quantity) -> PyResult<Option<i128>> {
    if crate::date_input::missing(value) {
        return Ok(None);
    }
    if let Some((ticks, code, _)) = crate::numpy_scalar::datetime_ticks(value)? {
        crate::date_input::scalar_unit(code)?;
        if ticks == i64::MIN {
            return Ok(None);
        }
        return Err(crate::error_context::type_error(
            "datetime64 is a date, not a numeric epoch quantity; use fromdatetime64",
        ));
    }
    // SAFETY: only the real date ancestry of this live bound value is inspected.
    if unsafe { pyo3::ffi::PyDate_Check(value.as_ptr()) != 0 }
        || crate::numpy_scalar::duration_ticks(value)?.is_some()
    {
        return Err(crate::error_context::type_error(
            "date/datetime/timedelta values are not numeric epoch quantities",
        ));
    }
    crate::numeric_epoch::read(value, quantity)
}
fn local_zone<'py>(
    py: Python<'py>,
    needed: bool,
    local: Option<&Bound<'py, PyAny>>,
) -> PyResult<Option<Zone>> {
    if !needed {
        return Ok(None);
    }
    let resolver =
        local.ok_or_else(|| crate::error_context::runtime("local timestamp resolver missing"))?;
    let value = resolver.call0()?;
    prepare_host_zone(&value).map(Some).map_err(|error| {
        crate::error_context::location(py, error, "Pldt.fromtimestamp", "local timezone")
    })
}
#[pyfunction]
#[pyo3(signature=(source,target,kind,unit,tz,policy,local=None))]
fn _pldt_number_column<'py>(
    source: PySeries,
    target: &Bound<'py, PyAny>,
    kind: &str,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    local: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let operation = operation(kind)?;
    let requested = selected(unit)?;
    let source = source.0;
    let values =
        native_values(&source, operation).map_err(|error| error.python(py, operation.entry()))?;
    let local = local_zone(
        py,
        matches!(operation, Operation::LocalTimestamp) && values.nanos.iter().any(Option::is_some),
        local,
    )?;
    let result = finish(
        values,
        source.name().clone(),
        operation,
        requested,
        tz.as_ref().map(|zone| &zone.value),
        local.as_ref(),
        &policy.value,
    )
    .map_err(|error| error.python(py, operation.entry()))?;
    super::export(py, &result, target)
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One actual numeric scalar/collection protocol boundary"
)]
#[pyo3(signature=(data,target,kind,unit,tz,policy,size=None,name="",local=None,column=false))]
fn _pldt_number_objects<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    target: &Bound<'py, PyAny>,
    kind: &str,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    size: Option<usize>,
    name: &str,
    local: Option<&Bound<'py, PyAny>>,
    column: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let operation = operation(kind)?;
    let requested = selected(unit)?;
    let mut values = Vec::new();
    let mut prepared_local = None;
    if !column && crate::numeric_epoch::scalar(data)? {
        let count = size.ok_or_else(|| {
            crate::error_context::value_error("a scalar numeric factory input requires size")
        })?;
        let value = actual_number(data, operation.quantity()).map_err(|error| {
            crate::error_context::argument(py, error, operation.entry(), "data", data)
        })?;
        prepared_local = local_zone(
            py,
            matches!(operation, Operation::LocalTimestamp) && count != 0 && value.is_some(),
            local,
        )?;
        count
            .checked_mul(32)
            .filter(|size| *size <= isize::MAX as usize)
            .ok_or_else(|| {
                crate::error_context::overflow("size exceeds the native date allocation range")
            })?;
        values.try_reserve_exact(count).map_err(|_| {
            pyo3::exceptions::PyMemoryError::new_err("cannot reserve numeric factory dates")
        })?;
        values.resize(count, value);
    } else {
        if size.is_some() {
            return Err(crate::error_context::value_error(
                "omit size for a collection input",
            ));
        }
        for (row, value) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let value = value
                .map_err(crate::error_context::external)
                .map_err(|error| {
                    crate::error_context::item(
                        py,
                        error,
                        operation.entry(),
                        "data",
                        row,
                        None,
                        true,
                    )
                })?;
            let nanos = actual_number(&value, operation.quantity()).map_err(|error| {
                crate::error_context::item(
                    py,
                    error,
                    operation.entry(),
                    "data",
                    row,
                    Some(&value),
                    false,
                )
            })?;
            if matches!(operation, Operation::LocalTimestamp)
                && nanos.is_some()
                && prepared_local.is_none()
            {
                prepared_local = local_zone(py, true, local)?;
            }
            values.push(nanos);
        }
    }
    let result = finish(
        Values { nanos: values },
        name.into(),
        operation,
        requested,
        tz.as_ref().map(|zone| &zone.value),
        prepared_local.as_ref(),
        &policy.value,
    )
    .map_err(|error| error.python(py, operation.entry()))?;
    super::export(py, &result, target)
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_now, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_number_column, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_number_objects, module)?)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn current_clock_once_or_never_and_native_tail() {
        let calls = std::cell::Cell::new(0);
        let zone = Zone::named("UTC").unwrap();
        let value = current(
            3,
            Unit::Nanosecond,
            "stamp".into(),
            Some(&zone),
            false,
            || {
                calls.set(calls.get() + 1);
                Ok(1_123_456_789)
            },
        )
        .unwrap_or_else(|_| panic!("valid clock"));
        assert_eq!(calls.get(), 1);
        assert_eq!(
            value.datetime().unwrap().physical().get(2),
            Some(1_123_456_789)
        );
        let value = current(0, Unit::Nanosecond, "stamp".into(), None, true, || {
            panic!("must not read empty clock")
        })
        .unwrap_or_else(|_| panic!("empty clock"));
        assert_eq!(value.len(), 0);
        let local = Zone::named("Etc/GMT-8").unwrap();
        let value = current(
            2,
            Unit::Millisecond,
            "stamp".into(),
            Some(&local),
            true,
            || Ok(1_123_456_789),
        )
        .unwrap_or_else(|_| panic!("local clock"));
        assert_eq!(
            value.datetime().unwrap().physical().get(0),
            Some(28_801_123)
        );
        assert_eq!(
            value.dtype(),
            &DataType::Datetime(TimeUnit::Milliseconds, None)
        );
    }
}
