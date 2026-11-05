//! Strict ISO text shares the scalar grammar and native final assembly.
use super::finish::{Failure, Kind, Rows};
use super::zones::{Context, Policies, PolicyContext};
use crate::epoch::Unit;
use crate::parser::iso_factory;
use crate::temporal_zone::{Zone, ZoneData};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::PyString;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    unit: Option<String>,
    target: Option<ZoneData>,
    policy: Policies,
    mask_scalar: bool,
}
fn selected(value: Option<&str>) -> Result<Option<Unit>, Failure> {
    value
        .map(|value| match value {
            "ms" => Ok(Unit::Millisecond),
            "us" => Ok(Unit::Microsecond),
            "ns" => Ok(Unit::Nanosecond),
            _ => Err(Failure::new(Kind::Value, "unit must be ms/us/ns")),
        })
        .transpose()
}
fn read(
    rows: &mut Rows,
    text: &str,
    expression: bool,
    target: Option<&Zone>,
) -> Result<(), Failure> {
    if super::text::missing(text) {
        rows.missing();
        return Ok(());
    }
    let parsed = iso_factory::read_native(text).map_err(|error| {
        Failure::new(
            if matches!(error, iso_factory::Error::Overflow(_)) {
                Kind::Capacity
            } else {
                Kind::Value
            },
            error.to_string(),
        )
    })?;
    if expression && target.is_none() && parsed.offset.is_some() {
        return Err(Failure::new(
            Kind::Value,
            "ISO text Expr containing a source timezone requires an explicit tz",
        ));
    }
    let zone = parsed
        .offset
        .map(|offset| rows.offset(offset))
        .transpose()?
        .unwrap_or(0);
    rows.push(parsed.nanos, zone, false, parsed.unit);
    Ok(())
}
fn column(
    source: &Series,
    unit: Option<Unit>,
    target: Option<&Zone>,
    policy: &Policies,
    expression: bool,
) -> Result<Series, Failure> {
    let mut rows = Rows::new(Unit::Second);
    match source.dtype() {
        DataType::Null => {
            for _ in 0..source.len() {
                rows.missing();
            }
        }
        DataType::String => {
            for (row, value) in source
                .str()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                if let Some(value) = value {
                    read(&mut rows, value, expression, target).map_err(|error| error.at(row))?;
                } else {
                    rows.missing();
                }
            }
        }
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "fromisoformat requires ISO String or Null input; it does not convert dates or numbers to text",
            ));
        }
    }
    rows.finish(source.name().clone(), unit, target, policy, false)
}
fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    polars_ensure!(kwargs.version==1&&!fields.is_empty()&&fields.len()<=2,InvalidOperation:"Pldt.fromisoformat: invalid prepared input");
    polars_ensure!(matches!(fields[0].dtype(),DataType::String|DataType::Null),InvalidOperation:"Pldt.fromisoformat requires String or Null dtype");
    if let Some(mask) = fields.get(1) {
        polars_ensure!(mask.dtype()==&DataType::Boolean,InvalidOperation:"ambiguous Expr requires Boolean");
    }
    let unit=selected(kwargs.unit.as_deref()).map_err(|error|error.polars("Pldt.fromisoformat"))?.or_else(||(fields[0].dtype()==&DataType::Null).then_some(Unit::Millisecond)).ok_or_else(||polars_err!(ComputeError:"Pldt.fromisoformat: String Expr requires an explicit unit"))?;
    Ok(Field::new(
        fields[0].name().clone(),
        DataType::Datetime(
            super::input::resolution(unit),
            TimeZone::opt_try_new(kwargs.target.map(|zone| zone.key))?,
        ),
    ))
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_iso(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    polars_ensure!(kwargs.version==1&&!inputs.is_empty()&&inputs.len()<=2,InvalidOperation:"Pldt.fromisoformat: invalid native inputs");
    let target = kwargs
        .target
        .map(Zone::from_data)
        .transpose()
        .map_err(|message| polars_err!(ComputeError:"Pldt.fromisoformat: {}",message))?;
    let policy = if let Some(mask) = inputs.get(1) {
        kwargs
            .policy
            .with_expression_mask(mask, kwargs.mask_scalar)
            .map_err(|error| polars_err!(ComputeError:"Pldt.fromisoformat: {}",error))?
    } else {
        kwargs.policy
    };
    let unit =
        selected(kwargs.unit.as_deref()).map_err(|error| error.polars("Pldt.fromisoformat"))?;
    column(&inputs[0], unit, target.as_ref(), &policy, true)
        .map_err(|error| error.polars("Pldt.fromisoformat"))
}
#[pyfunction]
fn _pldt_iso_column<'py>(
    source: PySeries,
    target: &Bound<'py, PyAny>,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let result = column(
        &source.0,
        super::input::selected(unit)?,
        tz.as_ref().map(|zone| &zone.value),
        &policy.value,
        false,
    )
    .map_err(|error| error.python(py, "Pldt.fromisoformat"))?;
    super::export(py, &result, target)
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Once-read ISO scalar/column role and final output schema"
)]
#[pyo3(signature=(data,target,unit,tz,policy,size,name,column))]
fn _pldt_iso_objects<'py>(
    data: &Bound<'py, PyAny>,
    target: &Bound<'py, PyAny>,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    size: Option<usize>,
    name: &str,
    column: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let py = data.py();
    let entry = "Pldt.fromisoformat";
    let mut rows = Rows::new(Unit::Second);
    let zone = tz.as_ref().map(|zone| &zone.value);
    let mut read_object = |value: &Bound<'py, PyAny>| -> PyResult<()> {
        if !value.is_instance_of::<PyString>() && crate::date_input::date_missing(value)? {
            rows.missing();
            return Ok(());
        }
        let text = value.cast::<PyString>().map_err(|_| {
            crate::error_context::type_error(
                "fromisoformat requires ISO text values, not dates or numbers",
            )
        })?;
        let converted;
        let text = if value.is_exact_instance_of::<PyString>() {
            text
        } else {
            converted = value.str().map_err(crate::error_context::external)?;
            &converted
        };
        read(&mut rows, text.to_str()?, false, zone).map_err(|error| error.python(py, entry))
    };
    if !column && crate::numeric_epoch::scalar(data)? {
        let count = size
            .ok_or_else(|| crate::error_context::value_error("a scalar ISO input requires size"))?;
        read_object(data)
            .map_err(|error| crate::error_context::argument(py, error, entry, "dtstr", data))?;
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
                    crate::error_context::item(py, error, entry, "dtstr", row, None, true)
                })?;
            read_object(&value).map_err(|error| {
                crate::error_context::item(py, error, entry, "dtstr", row, Some(&value), false)
            })?;
        }
    }
    let result = rows
        .finish(
            name.into(),
            super::input::selected(unit)?,
            zone,
            &policy.value,
            false,
        )
        .map_err(|error| error.python(py, entry))?;
    super::export(py, &result, target)
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_iso_column, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_iso_objects, module)?)
}
