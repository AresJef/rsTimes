//! Native numeric formatting and a prepared, explicit eager system adapter.
use super::finish::{Failure, Kind};
use crate::strftime_output::Context;
use crate::strftime_plan::Plan;
use crate::temporal_zone::Zone;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::PyDateTime;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Kwargs {
    #[serde(deserialize_with = "crate::serde_values::byte_vector")]
    prepared: Vec<u8>,
}
fn prepared(bytes: &[u8]) -> Result<Plan, Failure> {
    let plan: Plan =
        serde_json::from_slice(bytes).map_err(|e| Failure::new(Kind::Value, e.to_string()))?;
    plan.validate().map_err(|e| Failure::new(Kind::Value, e))?;
    if !plan.native() {
        return Err(Failure::new(
            Kind::Value,
            "system-locale/platform formats require eager data; use the eager strftime method or native .dt.strftime",
        ));
    }
    Ok(plan)
}
fn meta(source: &Field) -> Result<Field, Failure> {
    if !matches!(source.dtype(), DataType::Date | DataType::Datetime(..)) {
        return Err(Failure::new(
            Kind::Type,
            "strftime requires a Date or Datetime source",
        ));
    }
    Ok(Field::new(source.name().clone(), DataType::String))
}
fn execute(source: &Series, plan: &Plan) -> Result<Series, Failure> {
    meta(&Field::new(source.name().clone(), source.dtype().clone()))?;
    let (digits, key) = match source.dtype() {
        DataType::Datetime(unit, key) => (
            if *unit == TimeUnit::Nanoseconds { 9 } else { 6 },
            key.as_ref(),
        ),
        _ => (6, None),
    };
    let needs_zone = plan.needs_wall() || plan.needs_offset() || plan.needs_name();
    let zone = if needs_zone {
        key.map(|key| Zone::named(key.as_str()))
            .transpose()
            .map_err(|e| Failure::new(Kind::Value, e))?
    } else {
        None
    };
    let mut output = StringChunkedBuilder::new(source.name().clone(), source.len());
    super::input::visit_nanos(source, |row, value| {
        let result = (|| {
            let Some(instant) = value else {
                output.append_null();
                return Ok(());
            };
            let wall = if plan.needs_wall() {
                zone.as_ref()
                    .map_or(Ok(instant), |zone| zone.wall(instant))?
            } else {
                instant
            };
            let offset = if plan.needs_offset() {
                zone.as_ref()
                    .map(|zone| zone.offset_seconds(instant))
                    .transpose()?
            } else {
                None
            };
            let name = if plan.needs_name() {
                zone.as_ref()
                    .map(|zone| zone.abbreviation(instant))
                    .transpose()?
            } else {
                None
            };
            output.append_value(plan.render(wall, digits, offset, name.as_deref())?);
            Ok(())
        })();
        result.map_err(|e: Failure| e.at(row))
    })?;
    Ok(output.finish().into_series())
}
fn output(fields: &[Field], kwargs: Kwargs) -> PolarsResult<Field> {
    polars_ensure!(fields.len()==1,InvalidOperation:"strftime requires one temporal source");
    prepared(&kwargs.prepared).map_err(|e| e.polars("Pldt.strftime"))?;
    meta(&fields[0]).map_err(|e| e.polars("Pldt.strftime"))
}
#[polars_expr(output_type_func_with_kwargs=output)]
fn pldt_strftime(inputs: &[Series], kwargs: Kwargs) -> PolarsResult<Series> {
    polars_ensure!(inputs.len()==1,InvalidOperation:"strftime requires one temporal source");
    let plan = prepared(&kwargs.prepared).map_err(|e| e.polars("Pldt.strftime"))?;
    execute(&inputs[0], &plan).map_err(|e| e.polars("Pldt.strftime"))
}
#[pyfunction]
fn _pldt_strftime<'py>(
    source: PySeries,
    context: PyRef<'_, Context>,
    zone: &Bound<'py, PyAny>,
    target: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let plan = &context.plan;
    let result = if plan.native() {
        py.detach(|| execute(&source.0, plan))
            .map_err(|e| e.python(py, "Pldt.strftime"))?
    } else {
        host(py, &source.0, plan, zone)?
    };
    super::export(py, &result, target)
}
fn host(py: Python<'_>, source: &Series, plan: &Plan, zone: &Bound<'_, PyAny>) -> PyResult<Series> {
    meta(&Field::new(source.name().clone(), source.dtype().clone()))
        .map_err(|e| e.python(py, "Pldt.strftime"))?;
    let (quantum, digits, key) = match source.dtype() {
        DataType::Datetime(unit, key) => (
            super::input::epoch_unit(*unit).nanos(),
            if *unit == TimeUnit::Nanoseconds { 9 } else { 6 },
            key.as_ref(),
        ),
        _ => (86_400_000_000_000, 6, None),
    };
    let native = key
        .map(|key| Zone::named(key.as_str()))
        .transpose()
        .map_err(crate::error_context::value_error)?;
    let fixed = native.as_ref().map_or(Some(0), Zone::fixed_seconds);
    let mut out = StringChunkedBuilder::new(source.name().clone(), source.len());
    if source.dtype() == &DataType::Date {
        host_values(
            py,
            source
                .date()
                .map_err(super::eager_error)?
                .physical()
                .iter()
                .map(|v| v.map(|v| i128::from(v) * quantum)),
            plan,
            zone,
            fixed,
            digits,
            &mut out,
        )?;
    } else {
        host_values(
            py,
            source
                .datetime()
                .map_err(super::eager_error)?
                .physical()
                .iter()
                .map(|v| v.map(|v| i128::from(v) * quantum)),
            plan,
            zone,
            fixed,
            digits,
            &mut out,
        )?;
    }
    Ok(out.finish().into_series())
}
fn host_values<'py>(
    py: Python<'py>,
    values: impl Iterator<Item = Option<i128>>,
    plan: &Plan,
    zone: &Bound<'py, PyAny>,
    fixed: Option<i32>,
    digits: u8,
    out: &mut StringChunkedBuilder,
) -> PyResult<()> {
    for (row, value) in values.enumerate() {
        let result = (|| -> PyResult<()> {
            let Some(instant) = value else {
                out.append_null();
                return Ok(());
            };
            let carrier = if let Some(offset) = fixed {
                let wall = instant + i128::from(offset) * 1_000_000_000;
                let fields =
                    crate::parser::objects::wide_microsecond_fields(wall.div_euclid(1000))?;
                if !(1..=9999).contains(&fields[0]) {
                    return Err(crate::error_context::overflow(
                        "system strftime requires a Python date carrier in years 1 through 9999; use native numeric directives for wide years",
                    ));
                }
                if zone.is_none() {
                    PyDateTime::new(
                        py,
                        fields[0] as i32,
                        fields[1] as u8,
                        fields[2] as u8,
                        fields[3] as u8,
                        fields[4] as u8,
                        fields[5] as u8,
                        fields[6] as u32,
                        None,
                    )?
                } else {
                    crate::pydt::wall_carrier(py, fields, zone)?
                }
            } else {
                crate::host_zone::utc_local(instant, zone)?.0
            };
            let format = plan.system_format(instant.rem_euclid(1_000_000_000) as u32, digits);
            let value = crate::strftime_output::standard(py)?
                .bind(py)
                .call1((&carrier, format))
                .map_err(crate::error_context::external)?;
            out.append_value(value.extract::<String>()?);
            Ok(())
        })();
        result.map_err(|e| {
            crate::error_context::location(py, e, "Pldt.strftime", &format!("data[{row}]"))
        })?;
    }
    Ok(())
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_strftime, module)?)
}
