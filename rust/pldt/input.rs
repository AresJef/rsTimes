//! One-time host input preparation and pure, fixed-resolution conversion.
use super::finish::Rows;
use super::zones::{Context, PolicyContext, prepare_host_zone};
use crate::epoch::{Options as ParseOptions, Unit, Zone};
use crate::parser::Truth;
use crate::precision::TickError as ScaleError;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use serde::Deserialize;

pub(super) fn resolution(unit: Unit) -> TimeUnit {
    match unit {
        Unit::Second | Unit::Millisecond => TimeUnit::Milliseconds,
        Unit::Microsecond => TimeUnit::Microseconds,
        Unit::Nanosecond => TimeUnit::Nanoseconds,
    }
}

pub(super) fn epoch_unit(unit: TimeUnit) -> Unit {
    match unit {
        TimeUnit::Milliseconds => Unit::Millisecond,
        TimeUnit::Microseconds => Unit::Microsecond,
        TimeUnit::Nanoseconds => Unit::Nanosecond,
    }
}

pub(super) fn selected(unit: Option<&str>) -> PyResult<Option<Unit>> {
    unit.map(|value| {
        let unit = Unit::parse(value)?;
        if unit == Unit::Second {
            return Err(crate::error_context::value_error(
                "Pldt: unit must be 'ms', 'us' or 'ns'; seconds are an input/output quantity, not a Polars Datetime storage unit",
            ));
        }
        Ok(unit)
    }).transpose()
}

/// The complete signed64 domain is valid here; null is represented separately.
fn scale(ns: i128, unit: Unit, round_ok: bool) -> Result<i64, ScaleError> {
    crate::precision::epoch_tick(ns, unit.nanos(), round_ok)
}

fn scale_error(error: ScaleError, row: usize) -> PyErr {
    let error = match error {
        ScaleError::Precision => crate::error_context::value_error(
            "source precision cannot fit the selected unit without loss; use a finer unit or explicitly request as_unit(round_ok=True)",
        ),
        ScaleError::Capacity => crate::error_context::overflow(
            "date exceeds the selected unit capacity; choose a coarser supported unit; seconds-only sources may require keeping their NumPy or Pddt representation",
        ),
    };
    Python::attach(|py| crate::error_context::location(py, error, "Pldt", &format!("data[{row}]")))
}

fn native_error(error: PolarsError) -> PyErr {
    super::eager_error(error)
}

/// Pure typed Polars preparation, shared by eager construction and Expr.
pub(super) struct NativeOptions<'a> {
    pub(super) requested: Option<Unit>,
    pub(super) target: Option<&'a crate::temporal_zone::Zone>,
    pub(super) policy: &'a super::zones::Policies,
    pub(super) copy: bool,
    pub(super) round_ok: bool,
}
pub(super) fn column(
    source: &Series,
    options: NativeOptions<'_>,
) -> Result<Series, super::finish::Failure> {
    use super::finish::{Failure, Kind};
    options.policy.check_len(source.len())?;
    let (original, source_zone) = match source.dtype() {
        DataType::Datetime(unit, zone) => (epoch_unit(*unit), zone.clone()),
        DataType::Date | DataType::Null => (Unit::Millisecond, None),
        dtype if dtype.is_integer() || matches!(dtype, DataType::Float32 | DataType::Float64) => {
            (Unit::Nanosecond, None)
        }
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "unsupported native date dtype; expected Date/Datetime or supported numeric ticks",
            ));
        }
    };
    let chosen = options.requested.unwrap_or(original);
    let output_zone = match options.target {
        Some(zone) => TimeZone::opt_try_new(Some(zone.key()))
            .map_err(|error| Failure::new(Kind::Value, error.to_string()))?,
        None => source_zone.clone(),
    };
    if source.dtype() == &DataType::Null {
        return Ok(Series::full_null(
            source.name().clone(),
            source.len(),
            &DataType::Datetime(resolution(chosen), output_zone),
        ));
    }
    if let Ok(dates) = source.datetime() {
        if options.target.is_none_or(|_| source_zone.is_some())
            && chosen == original
            && !options.copy
        {
            return Ok(dates
                .physical()
                .clone()
                .into_datetime(resolution(chosen), output_zone)
                .into_series());
        }
    }
    let mut rows = Rows::new(chosen);
    match source.dtype() {
        DataType::Datetime(_, _) => {
            for value in source
                .datetime()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .physical()
                .iter()
            {
                if let Some(value) = value {
                    rows.push(
                        i128::from(value) * original.nanos(),
                        0,
                        source_zone.is_some(),
                        original,
                    )
                } else {
                    rows.missing()
                }
            }
        }
        DataType::Date => {
            for value in source
                .date()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .physical()
                .iter()
            {
                if let Some(value) = value {
                    rows.push(i128::from(value) * 86_400_000_000_000, 0, false, original)
                } else {
                    rows.missing()
                }
            }
        }
        dtype if dtype.is_integer() => {
            let values = source
                .strict_cast(&DataType::Int64)
                .map_err(|_| Failure::new(Kind::Capacity, "numeric date tick exceeds signed64"))?;
            // Raw numbers are already ticks in the explicitly chosen/default unit.
            if !options.copy {
                return Ok(values
                    .i64()
                    .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                    .clone()
                    .into_datetime(resolution(chosen), output_zone)
                    .into_series());
            }
            for value in values
                .i64()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
            {
                if let Some(value) = value {
                    rows.push(i128::from(value) * chosen.nanos(), 0, true, chosen)
                } else {
                    rows.missing()
                }
            }
        }
        DataType::Float32 | DataType::Float64 => {
            let values = source
                .cast(&DataType::Float64)
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?;
            for (row, value) in values
                .f64()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                let Some(value) = value.filter(|value| !value.is_nan()) else {
                    rows.missing();
                    continue;
                };
                if !value.is_finite() || value < i64::MIN as f64 || value >= 9223372036854775808.0 {
                    return Err(
                        Failure::new(Kind::Capacity, "numeric date tick exceeds signed64").at(row),
                    );
                }
                if value.fract() != 0.0 {
                    return Err(Failure::new(Kind::Value,"numeric construction requires an integer tick; use fromseconds for fractional seconds").at(row));
                }
                rows.push(i128::from(value as i64) * chosen.nanos(), 0, true, chosen)
            }
        }
        _ => {
            return Err(Failure::new(
                Kind::Runtime,
                "validated native date dtype was lost",
            ));
        }
    }
    let result = rows.finish(
        source.name().clone(),
        Some(chosen),
        options.target,
        options.policy,
        options.round_ok,
    )?;
    if options.target.is_none() && source_zone.is_some() {
        let dates = result
            .datetime()
            .map_err(|error| Failure::new(Kind::Runtime, error.to_string()))?;
        Ok(dates
            .physical()
            .clone()
            .into_datetime(resolution(chosen), source_zone)
            .into_series())
    } else {
        Ok(result)
    }
}

/// Read known native dtype and metadata once, without Python scalar dates.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One native dtype/unit/timezone preparation boundary"
)]
#[pyo3(signature=(source,target,unit=None,copy=Truth(false),round_ok=Truth(false),numpy_date=None,numpy_zone=None,tz=None,policy=None))]
fn _pldt_native<'py>(
    source: PySeries,
    target: &Bound<'py, PyAny>,
    unit: Option<&str>,
    copy: Truth,
    round_ok: Truth,
    numpy_date: Option<(i32, i32)>,
    numpy_zone: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: Option<PyRef<'_, PolicyContext>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let source = source.0;
    let requested = selected(unit)?;
    let strict;
    let policy = if let Some(value) = policy.as_ref() {
        &value.value
    } else {
        strict = super::zones::Policies::strict();
        &strict
    };
    policy
        .check_len(source.len())
        .map_err(super::zones::error)?;
    // Localize before narrowing the output unit: a valid final offset result
    // must not be rejected by an unnecessarily narrow naive intermediate.
    if let (Some(target_zone), Some((code, multiplier))) = (tz.as_ref(), numpy_date)
        && numpy_zone.is_none()
    {
        let chosen =
            requested.unwrap_or(crate::date_input::scalar_unit(code)?.max(Unit::Millisecond));
        if multiplier < 1 {
            return Err(crate::error_context::value_error(
                "invalid NumPy date multiplier",
            ));
        }
        let mut rows = Rows::new(chosen);
        for value in source.i64().map_err(native_error)?.iter() {
            if let Some(value) = value.filter(|value| *value != i64::MIN) {
                let parsed = crate::epoch::native_datetime_ticks(value, code, multiplier)?;
                rows.push(parsed.nanos, 0, false, parsed.unit)
            } else {
                rows.missing()
            }
        }
        let result = rows
            .finish(
                source.name().clone(),
                Some(chosen),
                Some(&target_zone.value),
                policy,
                round_ok.0,
            )
            .map_err(|error| error.python(py, "Pldt"))?;
        return super::export(py, &result, target);
    }
    let result = if let Some((code, multiplier)) = numpy_date {
        let chosen =
            requested.unwrap_or(crate::date_input::scalar_unit(code)?.max(Unit::Millisecond));
        if multiplier < 1 {
            return Err(crate::error_context::value_error(
                "invalid NumPy date multiplier",
            ));
        }
        let values = source.i64().map_err(native_error)?;
        let mut output =
            PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
        for (row, value) in values.iter().enumerate() {
            let result = match value.filter(|value| *value != i64::MIN) {
                None => None,
                Some(value) => Some(
                    scale(
                        crate::epoch::native_datetime_ticks(value, code, multiplier)?.nanos,
                        chosen,
                        false,
                    )
                    .map_err(|error| scale_error(error, row))?,
                ),
            };
            output.append_option(result);
        }
        output
            .finish()
            .into_datetime(
                resolution(chosen),
                TimeZone::opt_try_new(numpy_zone).map_err(native_error)?,
            )
            .into_series()
    } else {
        return super::export(
            py,
            &column(
                &source,
                NativeOptions {
                    requested,
                    target: tz.as_ref().map(|zone| &zone.value),
                    policy,
                    copy: copy.0,
                    round_ok: round_ok.0,
                },
            )
            .map_err(|error| error.python(py, "Pldt"))?,
            target,
        );
    };
    let result = if let Some(zone) = tz {
        let dates = result.datetime().map_err(native_error)?;
        dates
            .physical()
            .clone()
            .into_datetime(
                dates.time_unit(),
                TimeZone::opt_try_new(Some(zone.value.key())).map_err(native_error)?,
            )
            .into_series()
    } else {
        result
    };
    super::export(py, &result, target)
}

/// Once-prepared object protocol path. Native String columns use W13's worker.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One host input preparation boundary"
)]
#[pyo3(signature=(data,target,unit=None,base_unit=None,name="",default=None,yearfirst=None,dayfirst=None,isoformat=Truth(true),strict=Truth(false),cfg=None,tz=None,policy=None))]
fn _pldt_objects<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    target: &Bound<'py, PyAny>,
    unit: Option<&str>,
    base_unit: Option<&str>,
    name: &str,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<Truth>,
    dayfirst: Option<Truth>,
    isoformat: Truth,
    strict: Truth,
    cfg: Option<&Bound<'py, PyAny>>,
    tz: Option<PyRef<'_, Context>>,
    policy: Option<PyRef<'_, PolicyContext>>,
) -> PyResult<Bound<'py, PyAny>> {
    let requested = selected(unit)?;
    let cfg = cfg.filter(|value| !value.is_none());
    if let Some(value) = cfg {
        value
            .cast::<crate::parser::config::Configs>()
            .map_err(|_| {
                crate::error_context::expected_type(
                    value,
                    "Pldt",
                    "cfg",
                    "a Configs instance or None",
                )
            })?;
    }
    let options = ParseOptions {
        default,
        yearfirst: yearfirst.map(|v| v.0),
        dayfirst: dayfirst.map(|v| v.0),
        ignoretz: false,
        isoformat: isoformat.0,
        strict: strict.0,
        iso_only: false,
        cfg,
        input_unit: requested.unwrap_or(Unit::Nanosecond),
    };
    let mut reader = crate::date_input::Reader::<false>::new(
        options,
        base_unit
            .map(Unit::parse)
            .transpose()?
            .unwrap_or(Unit::Second),
    );
    let mut rows = Rows::new(Unit::Second);
    for (row, item) in data
        .try_iter()
        .map_err(crate::error_context::external)?
        .enumerate()
    {
        let item = item.map_err(crate::error_context::external)?;
        let parsed = reader.read(&item, "Pldt").map_err(|e| {
            crate::error_context::item(py, e, "Pldt", "data", row, Some(&item), false)
        })?;
        match parsed {
            None => rows.missing(),
            Some((parsed, instant)) => {
                let source = (|| -> PyResult<usize> {
                    Ok(if instant && tz.is_some() {
                        0
                    } else {
                        match parsed.zone {
                            Zone::Naive => 0,
                            Zone::Offset(offset) => rows
                                .offset(offset)
                                .map_err(|error| error.at(row).python(py, "Pldt"))?,
                            Zone::Object(value) => rows
                                .zone(prepare_host_zone(value.bind(py))?)
                                .map_err(|error| error.at(row).python(py, "Pldt"))?,
                        }
                    })
                })()
                .map_err(|error| {
                    crate::error_context::item(py, error, "Pldt", "data", row, Some(&item), false)
                })?;
                rows.push(parsed.nanos, source, instant, parsed.unit);
            }
        }
    }
    rows.include_unit(reader.unit);
    let fallback;
    let policy = if let Some(value) = policy.as_ref() {
        &value.value
    } else {
        fallback = super::zones::Policies::strict();
        &fallback
    };
    let result = rows
        .finish(
            name.into(),
            requested,
            tz.as_ref().map(|value| &value.value),
            policy,
            false,
        )
        .map_err(|error| error.python(py, "Pldt"))?;
    super::export(py, &result, target)
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ConvertOptions {
    version: u8,
    unit: String,
    round_ok: bool,
}

fn convert_field(fields: &[Field], options: ConvertOptions) -> PolarsResult<Field> {
    polars_ensure!(options.version==1,InvalidOperation:"unsupported rstimes kwargs version");
    let unit = match options.unit.as_str() {
        "ms" => TimeUnit::Milliseconds,
        "us" => TimeUnit::Microseconds,
        "ns" => TimeUnit::Nanoseconds,
        _ => polars_bail!(InvalidOperation:"Pldt.as_unit: unit must be ms/us/ns"),
    };
    let source = fields
        .first()
        .ok_or_else(|| polars_err!(InvalidOperation:"Pldt.as_unit requires one source"))?;
    let zone = match source.dtype() {
        DataType::Datetime(_, zone) => zone.clone(),
        DataType::Date => None,
        _ => polars_bail!(InvalidOperation:"Pldt.as_unit requires Date/Datetime"),
    };
    Ok(Field::new(
        source.name().clone(),
        DataType::Datetime(unit, zone),
    ))
}

#[polars_expr(output_type_func_with_kwargs=convert_field)]
fn pldt_as_unit(inputs: &[Series], kwargs: ConvertOptions) -> PolarsResult<Series> {
    polars_ensure!(inputs.len()==1,InvalidOperation:"Pldt.as_unit requires one source");
    let field = convert_field(
        &[Field::new(
            inputs[0].name().clone(),
            inputs[0].dtype().clone(),
        )],
        ConvertOptions {
            version: kwargs.version,
            unit: kwargs.unit.clone(),
            round_ok: kwargs.round_ok,
        },
    )?;
    let DataType::Datetime(target, zone) = field.dtype() else {
        polars_bail!(InvalidOperation:"invalid date output")
    };
    let target = epoch_unit(*target);
    let source = &inputs[0];
    if matches!(source.dtype(),DataType::Datetime(unit,_) if *unit==resolution(target)) {
        return Ok(source.clone());
    }
    let mut output = PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
    let mut append = |row, value: Option<i128>| -> PolarsResult<()> {
        output.append_option(value.map(|value|scale(value,target,kwargs.round_ok).map_err(|error|match error{
            ScaleError::Precision=>polars_err!(ComputeError:"Pldt.as_unit: batch item {} cannot preserve precision; choose round_ok=True explicitly",row),
            ScaleError::Capacity=>polars_err!(ComputeError:"Pldt.as_unit: batch item {} exceeds target capacity",row),
        })).transpose()?);
        Ok(())
    };
    match source.dtype() {
        DataType::Datetime(unit, _) => {
            for (row, value) in source.datetime()?.physical().iter().enumerate() {
                append(
                    row,
                    value.map(|v| i128::from(v) * epoch_unit(*unit).nanos()),
                )?;
            }
        }
        DataType::Date => {
            for (row, value) in source.date()?.physical().iter().enumerate() {
                append(row, value.map(|v| i128::from(v) * 86_400_000_000_000))?;
            }
        }
        _ => polars_bail!(InvalidOperation:"Pldt.as_unit requires Date/Datetime"),
    }
    Ok(output
        .finish()
        .into_datetime(resolution(target), zone.clone())
        .into_series())
}

#[pyfunction]
fn _pldt_register_missing(py: Python<'_>, na: Py<PyAny>, nat: Py<PyAny>) {
    crate::date_input::register_missing(py, na, nat);
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_native, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_objects, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_register_missing, module)?)
}
