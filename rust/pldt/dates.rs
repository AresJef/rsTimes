//! Dedicated date sources preserve local fields independently of final capacity.
use super::finish::{Failure, Kind, Rows};
use super::zones::{Context, Policies, PolicyContext, prepare_host_zone};
use crate::date_input::{self, DateSource};
use crate::epoch::{Unit, Zone as ParsedZone};
use crate::temporal_zone::{Zone, ZoneData};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;
const NS_DAY: i128 = 86_400_000_000_000;
#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "lowercase")]
enum Operation {
    Date,
    Datetime,
}
impl Operation {
    fn entry(self) -> &'static str {
        match self {
            Self::Date => "Pldt.fromdate",
            Self::Datetime => "Pldt.fromdatetime",
        }
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    operation: Operation,
    unit: Option<String>,
    target: Option<ZoneData>,
    policy: Policies,
    mask_scalar: bool,
}
fn unit(value: Option<&str>) -> Result<Option<Unit>, Failure> {
    value
        .map(|value| match value {
            "ms" => Ok(Unit::Millisecond),
            "us" => Ok(Unit::Microsecond),
            "ns" => Ok(Unit::Nanosecond),
            _ => Err(Failure::new(Kind::Value, "unit must be ms/us/ns")),
        })
        .transpose()
}
fn meta(
    source: &DataType,
    operation: Operation,
    requested: Option<Unit>,
    target: Option<&str>,
) -> Result<(Unit, Option<TimeZone>), Failure> {
    let (source_unit, zone) = match source {
        DataType::Datetime(value, zone) => (super::input::epoch_unit(*value), zone.clone()),
        DataType::Date if matches!(operation, Operation::Date) => (Unit::Millisecond, None),
        DataType::Null => (Unit::Millisecond, None),
        _ => {
            return Err(Failure::new(
                Kind::Type,
                match operation {
                    Operation::Date => "fromdate requires Date/Datetime input",
                    Operation::Datetime => {
                        "fromdatetime requires Datetime input, not Date/text/numbers"
                    }
                },
            ));
        }
    };
    let output = if let Some(target) = target {
        TimeZone::opt_try_new(Some(target))
            .map_err(|error| Failure::new(Kind::Value, error.to_string()))?
    } else if matches!(operation, Operation::Date) {
        None
    } else {
        zone
    };
    Ok((requested.unwrap_or(source_unit), output))
}
fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    polars_ensure!(kwargs.version==1&&!fields.is_empty()&&fields.len()<=2,InvalidOperation:"invalid named date preparation");
    if let Some(mask) = fields.get(1) {
        polars_ensure!(mask.dtype()==&DataType::Boolean,InvalidOperation:"ambiguous Expr requires Boolean")
    }
    let requested =
        unit(kwargs.unit.as_deref()).map_err(|error| error.polars(kwargs.operation.entry()))?;
    let (unit, zone) = meta(
        fields[0].dtype(),
        kwargs.operation,
        requested,
        kwargs.target.as_ref().map(|zone| zone.key.as_str()),
    )
    .map_err(|error| error.polars(kwargs.operation.entry()))?;
    Ok(Field::new(
        fields[0].name().clone(),
        DataType::Datetime(super::input::resolution(unit), zone),
    ))
}
fn column(
    source: &Series,
    operation: Operation,
    requested: Option<Unit>,
    target: Option<&Zone>,
    policy: &Policies,
) -> Result<Series, Failure> {
    let (chosen, output_zone) = meta(source.dtype(), operation, requested, target.map(Zone::key))?;
    policy.check_len(source.len())?;
    if matches!(operation, Operation::Datetime) && target.is_none() {
        return super::input::column(
            source,
            super::input::NativeOptions {
                requested: Some(chosen),
                target: None,
                policy,
                copy: false,
                round_ok: false,
            },
        );
    }
    if source.dtype() == &DataType::Null {
        return Ok(Series::full_null(
            source.name().clone(),
            source.len(),
            &DataType::Datetime(super::input::resolution(chosen), output_zone),
        ));
    }
    let original = match source.dtype() {
        DataType::Datetime(value, _) => super::input::epoch_unit(*value),
        _ => Unit::Millisecond,
    };
    let source_zone = if source.null_count() == source.len() {
        None
    } else {
        match source.dtype() {
            DataType::Datetime(_, Some(zone)) => Some(
                Zone::named(zone.as_str()).map_err(|message| Failure::new(Kind::Value, message))?,
            ),
            _ => None,
        }
    };
    let mut rows = Rows::new(original);
    let mut push = |row, value: Option<i128>| -> Result<(), Failure> {
        if let Some(mut wall) = value {
            if let Some(zone) = &source_zone {
                wall = zone
                    .wall(wall)
                    .map_err(|error| Failure::from(error).at(row))?
            }
            if matches!(operation, Operation::Date) {
                wall = wall.div_euclid(NS_DAY) * NS_DAY
            }
            rows.push(wall, 0, false, original);
        } else {
            rows.missing()
        }
        Ok(())
    };
    match source.dtype() {
        DataType::Date => {
            for (row, value) in source
                .date()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                push(row, value.map(|value| i128::from(value) * NS_DAY))?
            }
        }
        DataType::Datetime(_, _) => {
            for (row, value) in source
                .datetime()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                push(row, value.map(|value| i128::from(value) * original.nanos()))?
            }
        }
        _ => return Err(Failure::new(Kind::Runtime, "validated date dtype was lost")),
    }
    rows.finish(source.name().clone(), Some(chosen), target, policy, false)
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_dates(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    polars_ensure!(kwargs.version==1&&!inputs.is_empty()&&inputs.len()<=2,InvalidOperation:"invalid named date inputs");
    let entry = kwargs.operation.entry();
    let requested = unit(kwargs.unit.as_deref()).map_err(|error| error.polars(entry))?;
    let target = kwargs
        .target
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
    column(
        &inputs[0],
        kwargs.operation,
        requested,
        target.as_ref(),
        &policy,
    )
    .map_err(|error| error.polars(entry))
}
#[pyfunction]
#[pyo3(signature=(source,target,kind,unit,tz,policy))]
fn _pldt_date_column<'py>(
    source: PySeries,
    target: &Bound<'py, PyAny>,
    kind: &str,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let operation = if kind == "date" {
        Operation::Date
    } else {
        Operation::Datetime
    };
    let requested = super::input::selected(unit)?;
    let result = column(
        &source.0,
        operation,
        requested,
        tz.as_ref().map(|zone| &zone.value),
        &policy.value,
    )
    .map_err(|error| error.python(py, operation.entry()))?;
    super::export(py, &result, target)
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Real source role/scalar shape and final date target"
)]
#[pyo3(signature=(data,target,kind,unit,tz,policy,size=None,name="",column=false))]
fn _pldt_date_objects<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    target: &Bound<'py, PyAny>,
    kind: &str,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    size: Option<usize>,
    name: &str,
    column: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let requested = super::input::selected(unit)?;
    let (role, entry) = match kind {
        "date" => (DateSource::Date, "Pldt.fromdate"),
        "datetime" => (DateSource::Datetime, "Pldt.fromdatetime"),
        "numpy" => (DateSource::Numpy, "Pldt.fromdatetime64"),
        _ => return Err(crate::error_context::runtime("unknown date source role")),
    };
    let mut rows = Rows::new(Unit::Second);
    let mut read = |value: &Bound<'py, PyAny>| -> PyResult<()> {
        if matches!(role, DateSource::Numpy) {
            if let Some((ticks, code, multiplier)) = crate::numpy_scalar::datetime_ticks(value)? {
                let unit = date_input::scalar_unit(code)?.max(Unit::Millisecond);
                rows.include_unit(unit);
                if ticks == i64::MIN {
                    rows.missing();
                    return Ok(());
                }
                let parsed = crate::epoch::native_datetime_ticks(ticks, code, multiplier)?;
                rows.push(parsed.nanos, 0, false, unit);
                return Ok(());
            }
        }
        let Some((parsed, instant)) = date_input::named_date(value, role, tz.is_some())? else {
            rows.missing();
            return Ok(());
        };
        let zone = match parsed.zone {
            ParsedZone::Naive => 0,
            ParsedZone::Offset(value) => rows
                .offset(value)
                .map_err(|error| error.python(py, entry))?,
            ParsedZone::Object(value) => rows
                .zone(prepare_host_zone(value.bind(py))?)
                .map_err(|error| error.python(py, entry))?,
        };
        rows.push(parsed.nanos, zone, instant, parsed.unit);
        Ok(())
    };
    if !column && crate::numeric_epoch::scalar(data)? {
        let count = size.ok_or_else(|| {
            crate::error_context::value_error("a scalar date factory input requires size")
        })?;
        read(data)
            .map_err(|error| crate::error_context::argument(py, error, entry, "data", data))?;
        rows.repeat(count)
            .map_err(|error| error.python(py, entry))?;
    } else {
        if size.is_some() {
            return Err(crate::error_context::value_error(
                "omit size for a collection",
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
                    crate::error_context::item(py, error, entry, "data", row, None, true)
                })?;
            read(&value).map_err(|error| {
                crate::error_context::item(py, error, entry, "data", row, Some(&value), false)
            })?;
        }
    }
    let result = rows
        .finish(
            name.into(),
            requested,
            tz.as_ref().map(|zone| &zone.value),
            &policy.value,
            false,
        )
        .map_err(|error| error.python(py, entry))?;
    super::export(py, &result, target)
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_date_column, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_date_buffer, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_date_objects, module)?)
}

/// A pandas datetime buffer is an instant/sentinel source, not a Polars dtype.
/// Transform local fields in i128 before choosing the final output capacity.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Native source unit/zone and one final date role"
)]
#[pyo3(signature=(source,target,kind,code,source_zone,offset_us,unit,tz,policy))]
fn _pldt_date_buffer<'py>(
    source: PySeries,
    target: &Bound<'py, PyAny>,
    kind: &str,
    code: i32,
    source_zone: Option<PyRef<'_, Context>>,
    offset_us: Option<i64>,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let date = kind == "date";
    let entry = if date {
        "Pldt.fromdate"
    } else {
        "Pldt.fromdatetime"
    };
    let original = date_input::scalar_unit(code)?;
    let mut rows = Rows::new(original);
    let retain = !date && tz.is_none();
    let source_index = if retain {
        if let Some(zone) = source_zone.as_ref() {
            rows.zone(zone.value.clone())
                .map_err(|error| error.python(py, entry))?
        } else if let Some(offset) = offset_us {
            rows.offset(offset)
                .map_err(|error| error.python(py, entry))?
        } else {
            0
        }
    } else {
        0
    };
    rows.inherit_zone(source_index);
    for (row, value) in source
        .0
        .i64()
        .map_err(|error| crate::error_context::type_error(error.to_string()))?
        .iter()
        .enumerate()
    {
        let Some(value) = value.filter(|value| *value != i64::MIN) else {
            rows.missing();
            continue;
        };
        let mut ns = i128::from(value) * original.nanos();
        if !retain {
            ns = if let Some(zone) = source_zone.as_ref() {
                zone.value
                    .wall(ns)
                    .map_err(|error| Failure::from(error).at(row).python(py, entry))?
            } else {
                ns + i128::from(offset_us.unwrap_or(0)) * 1000
            };
            if date {
                ns = ns.div_euclid(NS_DAY) * NS_DAY;
            }
        }
        rows.push(
            ns,
            source_index,
            retain && (source_zone.is_some() || offset_us.is_some()),
            original,
        );
    }
    let result = rows
        .finish(
            source.0.name().clone(),
            super::input::selected(unit)?,
            tz.as_ref().map(|zone| &zone.value),
            &policy.value,
            false,
        )
        .map_err(|error| error.python(py, entry))?;
    super::export(py, &result, target)
}
