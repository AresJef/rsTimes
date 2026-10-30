//! One native timezone operation over a complete logical column or group.
use super::zones::{Context, Policies, PolicyContext};
use crate::epoch::Unit;
use crate::temporal_zone::{Zone, ZoneData, ZoneError};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;

#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Operation {
    Localize,
    Convert,
    Switch,
    Astimezone,
}
impl Operation {
    fn entry(self) -> &'static str {
        match self {
            Self::Localize => "Pldt.tz_localize",
            Self::Convert => "Pldt.tz_convert",
            Self::Switch => "Pldt.tz_switch",
            Self::Astimezone => "Pldt.astimezone",
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    operation: Operation,
    target: Option<ZoneData>,
    base: Option<ZoneData>,
    policy: Policies,
    naive: bool,
    mask_scalar: bool,
}

struct Failure {
    kind: ZoneError,
    row: Option<usize>,
}
impl From<ZoneError> for Failure {
    fn from(kind: ZoneError) -> Self {
        Self { kind, row: None }
    }
}
impl Failure {
    fn python(self, py: Python<'_>, entry: &str) -> PyErr {
        let error = super::zones::error(self.kind);
        crate::error_context::location(
            py,
            error,
            entry,
            &self
                .row
                .map_or_else(|| "arguments".to_owned(), |row| format!("data[{row}]")),
        )
    }
    fn polars(self, entry: &str) -> PolarsError {
        let location = self
            .row
            .map_or_else(String::new, |row| format!("batch item {row}: "));
        polars_err!(ComputeError:"{}: {}{}",entry,location,self.kind)
    }
}

fn meta(source: &DataType, options: &Options) -> Result<(TimeUnit, Option<TimeZone>), ZoneError> {
    if options.version != 1 {
        return Err(ZoneError::Value(
            "unsupported rstimes timezone kwargs version",
        ));
    }
    let (unit, source_zone) = match source {
        DataType::Datetime(unit, zone) => (*unit, zone.as_ref()),
        DataType::Date => (TimeUnit::Milliseconds, None),
        _ => return Err(ZoneError::Type("source must be a Date/Datetime column")),
    };
    let key = match options.operation {
        Operation::Localize => {
            if source_zone.is_some() && options.target.is_some() {
                return Err(ZoneError::Type(
                    "source already has a timezone; use tz_convert to preserve its instants",
                ));
            }
            options.target.as_ref().map(|zone| zone.key.as_str())
        }
        Operation::Convert => {
            if source_zone.is_none() {
                return Err(ZoneError::Type(
                    "source is naive; attach its timezone using tz_localize first",
                ));
            }
            options.target.as_ref().map(|zone| zone.key.as_str())
        }
        Operation::Switch => {
            if options.target.is_some() && source_zone.is_none() && options.base.is_none() {
                return Err(ZoneError::Value(
                    "naive dates need base_tz; use tz_switch('UTC', base_tz='Asia/Shanghai')",
                ));
            }
            if options.naive {
                None
            } else {
                options.target.as_ref().map(|zone| zone.key.as_str())
            }
        }
        Operation::Astimezone => {
            if options.target.is_none() || (source_zone.is_none() && options.base.is_none()) {
                return Err(ZoneError::Value("local timezone preparation is missing"));
            }
            options.target.as_ref().map(|zone| zone.key.as_str())
        }
    };
    let zone = TimeZone::opt_try_new(key)
        .map_err(|_| ZoneError::Value("target timezone cannot be encoded in Polars"))?;
    Ok((unit, zone))
}

fn output_field(fields: &[Field], options: Options) -> PolarsResult<Field> {
    let source = fields.first().ok_or_else(
        || polars_err!(InvalidOperation:"Pldt timezone operation requires one source"),
    )?;
    let (unit, zone) = meta(source.dtype(), &options)
        .map_err(|error| Failure::from(error).polars(options.operation.entry()))?;
    Ok(Field::new(
        source.name().clone(),
        DataType::Datetime(unit, zone),
    ))
}

fn epoch_unit(unit: TimeUnit) -> Unit {
    match unit {
        TimeUnit::Milliseconds => Unit::Millisecond,
        TimeUnit::Microseconds => Unit::Microsecond,
        TimeUnit::Nanoseconds => Unit::Nanosecond,
    }
}

fn execute(inputs: &[Series], mut options: Options) -> Result<Series, Failure> {
    let source = inputs
        .first()
        .ok_or(ZoneError::Value("timezone operation requires one source"))?;
    let (time_unit, output_zone) = meta(source.dtype(), &options)?;
    let unit = epoch_unit(time_unit);
    if let Some(mask) = inputs.get(1) {
        options.policy = options
            .policy
            .with_expression_mask(mask, options.mask_scalar)?;
    }
    options.policy.check_len(source.len())?;
    let promoted;
    let source = if source.dtype() == &DataType::Date {
        promoted = source
            .cast(&DataType::Datetime(time_unit, None))
            .map_err(|_| ZoneError::Value("cannot promote native Date midnight"))?;
        &promoted
    } else {
        source
    };
    let values = source
        .datetime()
        .map_err(|_| ZoneError::Type("source must contain native dates"))?;
    let source_key = values.time_zone().as_ref().map(|zone| zone.as_str());
    // Aware conversions are metadata-only; the actual source is already an instant.
    let convert_only = matches!(
        options.operation,
        Operation::Convert | Operation::Astimezone
    ) && source_key.is_some()
        || matches!(options.operation, Operation::Switch)
            && options.target.is_some()
            && source_key.is_some()
            && !options.naive;
    if convert_only {
        return Ok(values
            .physical()
            .clone()
            .into_datetime(time_unit, output_zone)
            .into_series());
    }
    let strip = options.target.is_none();
    let source_zone = if strip {
        source_key.map(Zone::named).transpose().map_err(|_| {
            ZoneError::Value("source timezone is unavailable in the native database")
        })?
    } else {
        None
    };
    let target = options
        .target
        .as_ref()
        .map(|data| Zone::from_data(data.clone()))
        .transpose()
        .map_err(|_| ZoneError::Value("target timezone data is invalid or unavailable"))?;
    let interpretation = match options.operation {
        Operation::Localize => target.clone(),
        Operation::Astimezone | Operation::Switch if source_key.is_none() && !strip => options
            .base
            .as_ref()
            .map(|data| Zone::from_data(data.clone()))
            .transpose()
            .map_err(|_| ZoneError::Value("base timezone data is invalid or unavailable"))?,
        _ => None,
    };
    // Simple zones are just one checked integer shift. A zero shift only
    // changes metadata; it neither scans rows nor allocates inference state.
    let initial_delta = if strip {
        source_zone.as_ref().map_or(Some(0), |zone| {
            zone.fixed_seconds()
                .map(|value| i128::from(value) * 1_000_000_000)
        })
    } else {
        interpretation.as_ref().map_or(Some(0), |zone| {
            zone.fixed_seconds()
                .map(|value| -i128::from(value) * 1_000_000_000)
        })
    };
    let fixed_delta = if matches!(options.operation, Operation::Switch) && options.naive && !strip {
        initial_delta.and_then(|value| {
            target
                .as_ref()
                .and_then(|zone| zone.fixed_seconds())
                .map(|offset| value + i128::from(offset) * 1_000_000_000)
        })
    } else {
        initial_delta
    };
    if let Some(delta) = fixed_delta {
        let delta = delta / unit.nanos();
        if delta == 0 {
            return Ok(values
                .physical()
                .clone()
                .into_datetime(time_unit, output_zone)
                .into_series());
        }
        let mut output =
            PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
        for (row, value) in values.physical().iter().enumerate() {
            output.append_option(
                value
                    .map(|value| {
                        i64::try_from(i128::from(value) + delta).map_err(|_| Failure {
                            kind: ZoneError::Capacity(
                                "timezone result exceeds the current unit; use as_unit explicitly",
                            ),
                            row: Some(row),
                        })
                    })
                    .transpose()?,
            );
        }
        return Ok(output
            .finish()
            .into_datetime(time_unit, output_zone)
            .into_series());
    }
    let mut result = Vec::with_capacity(source.len());
    let mut pending = if options.policy.infer()
        && interpretation
            .as_ref()
            .is_some_and(|zone| zone.fixed_seconds().is_none())
    {
        vec![None; source.len()]
    } else {
        Vec::new()
    };
    for (row, value) in values.physical().iter().enumerate() {
        let converted = (|| -> Result<Option<i128>, ZoneError> {
            let Some(value) = value else {
                return Ok(None);
            };
            let value = i128::from(value) * unit.nanos();
            if strip {
                return source_zone
                    .as_ref()
                    .map_or(Ok(Some(value)), |zone| zone.wall(value).map(Some));
            }
            match interpretation.as_ref() {
                Some(zone) => options
                    .policy
                    .localize(value, zone, unit, row, 0, &mut pending),
                None => Ok(Some(value)),
            }
        })()
        .map_err(|kind| Failure {
            kind,
            row: Some(row),
        })?;
        result.push(converted);
    }
    options.policy.complete(&mut result, &pending)?;
    let mut output = PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
    for (row, value) in result.into_iter().enumerate() {
        let value=value.map(|value|{
            let value=if matches!(options.operation,Operation::Switch) && options.naive && !strip {target.as_ref().ok_or(ZoneError::Value("target timezone is missing"))?.wall(value)?}else{value};
            crate::precision::epoch_tick(value,unit.nanos(),false).map_err(|error|match error {
                crate::precision::TickError::Precision=>ZoneError::Value("timezone result cannot preserve precision at the current unit; use as_unit explicitly"),
                crate::precision::TickError::Capacity=>ZoneError::Capacity("timezone result exceeds the current unit; use as_unit explicitly"),
            })
        }).transpose().map_err(|kind|Failure{kind,row:Some(row)})?;
        output.append_option(value);
    }
    Ok(output
        .finish()
        .into_datetime(time_unit, output_zone)
        .into_series())
}

#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_timezone(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    let entry = kwargs.operation.entry();
    execute(inputs, kwargs).map_err(|failure| failure.polars(entry))
}

#[pyfunction]
#[pyo3(signature=(source,target_type,operation,target,base,policy,naive))]
fn _pldt_timezone<'py>(
    source: PySeries,
    target_type: &Bound<'py, PyAny>,
    operation: &str,
    target: Option<PyRef<'_, Context>>,
    base: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    naive: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target_type.py();
    let operation = match operation {
        "localize" => Operation::Localize,
        "convert" => Operation::Convert,
        "switch" => Operation::Switch,
        "astimezone" => Operation::Astimezone,
        _ => {
            return Err(crate::error_context::value_error(
                "unknown timezone operation",
            ));
        }
    };
    let options = Options {
        version: 1,
        operation,
        target: target.map(|c| c.value.snapshot()),
        base: base.map(|c| c.value.snapshot()),
        policy: policy.value.clone(),
        naive,
        mask_scalar: false,
    };
    let result = py
        .detach(|| execute(&[source.0], options))
        .map_err(|failure| failure.python(py, operation.entry()))?;
    super::export(py, &result, target_type)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_timezone, module)?)
}
