//! Prepared field roles and native local-calendar column transforms.
use super::finish::{Failure, Kind, Rows};
use super::zones::{Context, Policies, PolicyContext};
use crate::batch_shape::Column;
use crate::temporal_zone::{Candidates, Zone, ZoneData};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyBytes, PyString};
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;

#[derive(Clone, Copy)]
struct Role {
    optional: bool,
    names: u8,
    low: Option<i64>,
    high: Option<i64>,
}
impl Role {
    fn value(self, value: Option<i64>) -> Result<Option<i64>, Failure> {
        if value.is_none() && !self.optional {
            return Err(Failure::new(
                Kind::Type,
                "relative increments require integers; use 0 rather than None/null",
            ));
        }
        if value.is_some_and(|v| {
            self.low.is_some_and(|low| v < low) || self.high.is_some_and(|high| v > high)
        }) {
            return Err(Failure::new(
                Kind::Value,
                format!(
                    "field must be in the inclusive range {} through {}",
                    self.low.unwrap_or(i64::MIN),
                    self.high.unwrap_or(i64::MAX)
                ),
            ));
        }
        Ok(value)
    }
    fn name(self, text: &str) -> Result<i64, Failure> {
        let value = crate::pydt::lookup_default_name(text, self.names == 2);
        if value < 0 {
            Err(Failure::new(
                Kind::Value,
                format!(
                    "unknown {} name {text:?}",
                    if self.names == 2 { "weekday" } else { "month" }
                ),
            ))
        } else {
            Ok(i64::from(value))
        }
    }
}
fn roles(kind: &str) -> Result<Vec<Role>, Failure> {
    let required = Role {
        optional: false,
        names: 0,
        low: None,
        high: None,
    };
    let optional = Role {
        optional: true,
        ..required
    };
    let bounded = |low, high| Role {
        low: Some(low),
        high: Some(high),
        ..optional
    };
    Ok(match kind {
        "replace" | "adjust" => vec![
            optional,
            bounded(1, 12),
            bounded(1, 31),
            bounded(0, 23),
            bounded(0, 59),
            bounded(0, 59),
            bounded(0, 999_999),
            bounded(0, 999),
        ],
        "add" | "sub" => vec![required; 11],
        "year" => vec![
            required,
            Role {
                names: 1,
                ..bounded(1, 12)
            },
            bounded(1, 31),
        ],
        "quarter" => vec![required, bounded(1, 3), bounded(1, 31)],
        "month" => vec![required, bounded(1, 31)],
        "weekday" => vec![
            required,
            Role {
                names: 2,
                ..bounded(0, 6)
            },
        ],
        "day" => vec![required],
        _ => return Err(Failure::new(Kind::Runtime, "unknown calendar transform")),
    })
}
fn values(source: &Series, scalar: bool, role: Role) -> Result<Column<Option<i64>>, Failure> {
    let mut output = Vec::with_capacity(source.len());
    match source.dtype() {
        DataType::Null if role.optional => output.resize(source.len(), None),
        dtype if dtype.is_integer() => {
            let cast = source
                .strict_cast(&DataType::Int64)
                .map_err(|_| Failure::new(Kind::Capacity, "integer field exceeds signed64"))?;
            for (row, value) in cast
                .i64()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .iter()
                .enumerate()
            {
                output.push(role.value(value).map_err(|e| e.at(row))?);
            }
        }
        DataType::String if role.names != 0 => {
            for (row, value) in source
                .str()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .iter()
                .enumerate()
            {
                let value = value
                    .map(|value| role.name(value))
                    .transpose()
                    .map_err(|e| e.at(row))?;
                output.push(role.value(value).map_err(|e| e.at(row))?);
            }
        }
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "requires integer fields, not Boolean/float/date/duration values; only optional selectors accept saved names",
            ));
        }
    }
    if scalar {
        if output.len() != 1 {
            return Err(Failure::new(
                Kind::Value,
                "a logical scalar field must contain exactly one value",
            ));
        }
        Ok(Column::Scalar(output[0]))
    } else {
        Ok(Column::Values(output))
    }
}

pub(super) fn query_values(
    source: &Series,
    scalar: bool,
    names: u8,
) -> Result<Column<Option<i64>>, Failure> {
    values(
        source,
        scalar,
        Role {
            optional: false,
            names,
            low: None,
            high: None,
        },
    )
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    kind: String,
    entry: String,
    scalars: Vec<bool>,
    target: Option<ZoneData>,
    replace_zone: bool,
    policy: Option<Policies>,
    mask_scalar: bool,
}
fn schema(source: &Field, options: &Options) -> PolarsResult<Field> {
    let (unit, zone) = match source.dtype() {
        DataType::Datetime(unit, zone) => (*unit, zone.clone()),
        DataType::Date if !matches!(options.kind.as_str(), "replace" | "adjust") => {
            (TimeUnit::Milliseconds, None)
        }
        _ => {
            polars_bail!(InvalidOperation:"{} requires Datetime input; use parse/fromdate first for field replacement",options.entry)
        }
    };
    let output = if options.replace_zone {
        TimeZone::opt_try_new(options.target.as_ref().map(|value| value.key.as_str()))?
    } else {
        zone
    };
    Ok(Field::new(
        source.name().clone(),
        DataType::Datetime(unit, output),
    ))
}

fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    let roles = roles(&kwargs.kind).map_err(|e| e.polars(&kwargs.entry))?;
    polars_ensure!(kwargs.version==1&&kwargs.scalars.len()==roles.len()&&(fields.len()==roles.len()+1||fields.len()==roles.len()+2),InvalidOperation:"invalid native transform preparation");
    for (field, role) in fields[1..=roles.len()].iter().zip(roles) {
        polars_ensure!(field.dtype().is_integer()||(role.optional&&field.dtype()==&DataType::Null)||(role.names!=0&&field.dtype()==&DataType::String),InvalidOperation:"{}: invalid field dtype for {}",kwargs.entry,field.name());
    }
    if let Some(field) = fields.get(kwargs.scalars.len() + 1) {
        polars_ensure!(field.dtype()==&DataType::Boolean,InvalidOperation:"ambiguous Expr requires Boolean dtype")
    }
    schema(&fields[0], &kwargs)
}
pub(super) fn automatic(
    wall: i128,
    instant: i128,
    source_wall: i128,
    zone: &Zone,
) -> Result<i128, Failure> {
    let source_offset = source_wall - instant;
    let select = |wall, a, b| crate::calendar::calendar_repeat(wall, source_offset, a, b);
    let candidate = zone.candidates(wall)?;
    let Candidates::Gap { before, after } = candidate else {
        return Ok(match candidate {
            Candidates::One(value) => value,
            Candidates::Repeated(a, b) => select(wall, a, b),
            Candidates::Gap { .. } => unreachable!(),
        });
    };
    let before = i128::from(before) * 1_000_000_000;
    let after = i128::from(after) * 1_000_000_000;
    let forward =
        crate::calendar::calendar_gap_forward(wall, source_wall, source_offset, before, after);
    for shifted in crate::calendar::calendar_gap_targets(wall, after - before, forward)
        .into_iter()
        .flatten()
    {
        match zone.candidates(shifted)? {
            Candidates::One(value) => return Ok(value),
            Candidates::Repeated(a, b) => return Ok(select(shifted, a, b)),
            Candidates::Gap { .. } => {}
        }
    }
    Err(Failure::new(
        Kind::Value,
        "the selected calendar day has no valid local result; choose another date",
    ))
}
fn transform(
    source: &Series,
    components: &[Series],
    options: &Options,
    target: Option<&Zone>,
    policy: Option<&Policies>,
) -> Result<Series, Failure> {
    let (unit, source_name) = match source.dtype() {
        DataType::Datetime(resolution, zone) => {
            (super::input::epoch_unit(*resolution), zone.as_ref())
        }
        DataType::Date if !matches!(options.kind.as_str(), "replace" | "adjust") => {
            (crate::epoch::Unit::Millisecond, None)
        }
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "requires a Datetime source; use parse/fromdate first for field replacement",
            ));
        }
    };
    let roles = roles(&options.kind)?;
    if components.len() != roles.len() || options.scalars.len() != roles.len() {
        return Err(Failure::new(Kind::Runtime, "invalid field preparation"));
    }
    let values = components
        .iter()
        .zip(&options.scalars)
        .zip(roles)
        .map(|((source, scalar), role)| values(source, *scalar, role))
        .collect::<Result<Vec<_>, _>>()?;
    if values
        .iter()
        .any(|value| value.len().is_some_and(|len| len != source.len()))
    {
        return Err(Failure::new(
            Kind::Value,
            "every field collection must equal the source length; length-one collections are not scalar",
        ));
    }
    let source_zone = source_name
        .map(|key| Zone::named(key.as_str()))
        .transpose()
        .map_err(|message| Failure::new(Kind::Value, message))?;
    let output = if options.replace_zone {
        target
    } else {
        source_zone.as_ref()
    };
    if let Some(policy) = policy {
        policy.check_len(source.len())?;
    }
    let same = source_name.map(|v| v.as_str()) == output.map(Zone::key);
    let mut rows = Rows::new(unit);
    rows.reserve(source.len())?;
    let mut push = |row: usize, value: Option<i128>| -> Result<(), Failure> {
        let Some(instant) = value else {
            rows.missing();
            return Ok(());
        };
        let wall = source_zone
            .as_ref()
            .map_or(Ok(instant), |zone| zone.wall(instant))
            .map_err(|e| Failure::from(e).at(row))?;
        let changed =
            crate::date_transform::transform(wall, &options.kind, |index| values[index].get(row))
                .map_err(|error| match error {
                    crate::date_transform::Error::Value(message) => {
                        Failure::new(Kind::Value, message)
                    }
                    crate::date_transform::Error::Capacity(message) => {
                        Failure::new(Kind::Capacity, message)
                    }
                })
                .map_err(|e| e.at(row))?;
        let unchanged = changed == wall && same;
        let known = unchanged || policy.is_none();
        let value = if unchanged {
            instant
        } else if policy.is_some() {
            changed
        } else {
            match output {
                None => changed,
                Some(zone) => {
                    if let Some(offset) = zone.fixed_seconds() {
                        changed - i128::from(offset) * 1_000_000_000
                    } else {
                        automatic(changed, instant, wall, zone).map_err(|e| e.at(row))?
                    }
                }
            }
        };
        rows.push(value, 0, known, unit);
        Ok(())
    };
    match source.dtype() {
        DataType::Date => {
            for (row, value) in source
                .date()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                push(
                    row,
                    value.map(|value| i128::from(value) * 86_400_000_000_000),
                )?
            }
        }
        DataType::Datetime(_, _) => {
            for (row, value) in source
                .datetime()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                push(row, value.map(|value| i128::from(value) * unit.nanos()))?
            }
        }
        _ => {
            return Err(Failure::new(
                Kind::Runtime,
                "validated calendar source dtype was lost",
            ));
        }
    }
    rows.finish(
        source.name().clone(),
        Some(unit),
        output,
        policy.unwrap_or(&Policies::strict()),
        false,
    )
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_transform(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    let arity = kwargs.scalars.len();
    polars_ensure!(kwargs.version==1&&(inputs.len()==arity+1||inputs.len()==arity+2),InvalidOperation:"invalid transform inputs");
    let target = kwargs
        .target
        .clone()
        .map(Zone::from_data)
        .transpose()
        .map_err(|message| polars_err!(ComputeError:"{}: {}",kwargs.entry,message))?;
    let policy = if let Some(mask) = inputs.get(arity + 1) {
        Some(
            kwargs
                .policy
                .as_ref()
                .ok_or_else(|| polars_err!(InvalidOperation:"unexpected ambiguous mask"))?
                .with_expression_mask(mask, kwargs.mask_scalar)
                .map_err(|e| polars_err!(ComputeError:"{}: {}",kwargs.entry,e))?,
        )
    } else {
        kwargs.policy.clone()
    };
    transform(
        &inputs[0],
        &inputs[1..=arity],
        &kwargs,
        target.as_ref(),
        policy.as_ref(),
    )
    .map_err(|e| e.polars(&kwargs.entry))
}
#[pyfunction]
#[pyo3(signature=(source,components,scalars,target,kind,entry,tz,replace_zone,policy))]
#[expect(
    clippy::too_many_arguments,
    reason = "One prepared native transform with independent source, roles, target and explicit policy"
)]
fn _pldt_transform<'py>(
    source: PySeries,
    components: Vec<PySeries>,
    scalars: Vec<bool>,
    target: &Bound<'py, PyAny>,
    kind: String,
    entry: String,
    tz: Option<PyRef<'_, Context>>,
    replace_zone: bool,
    policy: Option<PyRef<'_, PolicyContext>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let zone = tz.map(|v| v.value.clone());
    let policy = policy.map(|v| v.value.clone());
    let options = Options {
        version: 1,
        kind,
        entry,
        scalars,
        target: None,
        replace_zone,
        policy: None,
        mask_scalar: false,
    };
    let components: Vec<_> = components.into_iter().map(|v| v.0).collect();
    let result = py
        .detach(|| {
            transform(
                &source.0,
                &components,
                &options,
                zone.as_ref(),
                policy.as_ref(),
            )
        })
        .map_err(|e| e.python(py, &options.entry))?;
    super::export(py, &result, target)
}

#[pyfunction]
#[pyo3(signature=(source,role,entry,parameter))]
fn _pldt_component_column(
    py: Python<'_>,
    source: PySeries,
    role: (bool, u8, Option<i64>, Option<i64>),
    entry: &str,
    parameter: &str,
) -> PyResult<PySeries> {
    let (optional, names, low, high) = role;
    let role = Role {
        optional,
        names,
        low,
        high,
    };
    let Column::Values(values) = values(&source.0, false, role)
        .map_err(|e| crate::error_context::location(py, e.python(py, entry), entry, parameter))?
    else {
        return Err(crate::error_context::runtime(
            "expected a prepared field collection",
        ));
    };
    Ok(PySeries(Series::new(source.0.name().clone(), values)))
}
#[pyfunction]
#[pyo3(signature=(data,column,role,entry,parameter))]
fn _pldt_component_objects(
    data: &Bound<'_, PyAny>,
    column: bool,
    role: (bool, u8, Option<i64>, Option<i64>),
    entry: &str,
    parameter: &str,
) -> PyResult<(PySeries, bool)> {
    let py = data.py();
    let (optional, names, low, high) = role;
    let role = Role {
        optional,
        names,
        low,
        high,
    };
    let convert = |value: &Bound<'_, PyAny>| -> PyResult<Option<i64>> {
        let result = if optional && value.is_none() {
            None
        } else if names != 0 && value.is_instance_of::<PyString>() {
            Some(
                role.name(value.cast::<PyString>()?.to_str()?)
                    .map_err(|e| e.python(py, entry))?,
            )
        } else {
            Some(crate::numeric::index_i64(value)?)
        };
        role.value(result).map_err(|e| e.python(py, entry))
    };
    let scalar = !column
        && (data.is_none()
            || unsafe { pyo3::ffi::PyIndex_Check(data.as_ptr()) != 0 }
            || crate::numeric::supported_float(data)
            || data.is_instance_of::<PyString>()
            || data.is_instance_of::<PyBytes>()
            || data.is_instance_of::<PyByteArray>());
    let values = if scalar {
        vec![
            convert(data)
                .map_err(|e| crate::error_context::argument(py, e, entry, parameter, data))?,
        ]
    } else {
        let mut values = Vec::new();
        for (row, value) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let value = value.map_err(crate::error_context::external).map_err(|e| {
                crate::error_context::item(py, e, entry, parameter, row, None, true)
            })?;
            values.push(convert(&value).map_err(|e| {
                crate::error_context::item(py, e, entry, parameter, row, Some(&value), false)
            })?);
        }
        values
    };
    Ok((PySeries(Series::new(parameter.into(), values)), scalar))
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_transform, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_component_column, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_component_objects, module)?)
}
