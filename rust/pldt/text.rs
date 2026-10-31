//! Native String parsing and format adapters share grammar and final assembly.
use super::finish::{Failure, Kind, Rows, fields_nanos};
use super::zones::{Context, Policies, PolicyContext};
use crate::epoch::Unit;
use crate::parser::config::{Configs, NativeRegion, NativeRules};
use crate::parser::fields::{Lenient, Nano, Policy, Precision, Strict};
use crate::parser::formatted::{self, Format, FormatError, FormattedZone};
use crate::parser::native;
use crate::parser::prepared::{TextContext, TextData};
use crate::temporal_zone::{Zone, ZoneData};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyString};
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;

#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "lowercase")]
enum Resolution {
    Ms,
    Us,
    Ns,
}
impl Resolution {
    fn epoch(self) -> Unit {
        match self {
            Self::Ms => Unit::Millisecond,
            Self::Us => Unit::Microsecond,
            Self::Ns => Unit::Nanosecond,
        }
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    unit: Option<Resolution>,
    prepared: TextData,
    #[serde(default)]
    target: Option<ZoneData>,
    #[serde(default = "Policies::strict")]
    policy: Policies,
    #[serde(default)]
    mask_scalar: bool,
    #[serde(default, deserialize_with = "crate::serde_values::byte_vector")]
    format: Vec<u8>,
}

fn output_field(fields: &[Field], options: Options) -> PolarsResult<Field> {
    polars_ensure!(options.version==1,InvalidOperation:"unsupported rstimes text preparation version");
    polars_ensure!(!fields.is_empty()&&fields.len()<=2,InvalidOperation:"Pldt.parse requires one String source and at most one ambiguous mask");
    if let Some(mask) = fields.get(1) {
        polars_ensure!(mask.dtype()==&DataType::Boolean,InvalidOperation:"Pldt.parse ambiguous Expr must return booleans");
    }
    let formatted = !options.format.is_empty();
    let (unit, source_zone) = match fields[0].dtype() {
        DataType::String => {
            let unit=options.unit.map(Resolution::epoch).ok_or_else(||polars_err!(InvalidOperation:"Pldt.parse: String Expr requires an explicit unit (ms/us/ns)"))?;
            (unit, None)
        }
        DataType::Null => (
            options.unit.map(Resolution::epoch).unwrap_or(if formatted {
                Unit::Microsecond
            } else {
                Unit::Millisecond
            }),
            None,
        ),
        DataType::Datetime(unit, zone) if !formatted => (
            options
                .unit
                .map(Resolution::epoch)
                .unwrap_or(super::input::epoch_unit(*unit)),
            zone.clone(),
        ),
        DataType::Date if !formatted => (
            options
                .unit
                .map(Resolution::epoch)
                .unwrap_or(Unit::Millisecond),
            None,
        ),
        dtype
            if !formatted
                && (dtype.is_integer()
                    || matches!(dtype, DataType::Float32 | DataType::Float64)) =>
        {
            (
                options
                    .unit
                    .map(Resolution::epoch)
                    .unwrap_or(Unit::Nanosecond),
                None,
            )
        }
        _ => {
            polars_bail!(InvalidOperation:"Pldt.parse: unsupported source dtype; formatted parsing requires String input")
        }
    };
    let zone = if let Some(target) = options.target {
        TimeZone::opt_try_new(Some(target.key))?
    } else {
        source_zone
    };
    Ok(Field::new(
        fields[0].name().clone(),
        DataType::Datetime(super::input::resolution(unit), zone),
    ))
}

/// Only the approved exact missing markers. Bad text is never coerced to null.
pub(super) fn missing(value: &str) -> bool {
    crate::date_input::missing_utf8(value)
}

fn region(rows: &mut Rows, value: &NativeRegion) -> Result<usize, Failure> {
    if !value.available {
        return Err(Failure::new(
            Kind::Value,
            "the registered region is unavailable; restore timezone data and prepare the expression again",
        ));
    }
    if let Some(offset) = value.fixed_offset_us {
        rows.offset(offset)
    } else {
        rows.region(&value.key)
    }
}

struct Run<'a> {
    prepared: crate::parser::native::Options,
    rules: NativeRules,
    strict: bool,
    format: Option<&'a Format>,
    requested: Option<Unit>,
    target: Option<&'a Zone>,
    policy: Policies,
    expression: bool,
}

fn parse_error(error: crate::parser::fields::ParseError) -> Failure {
    use crate::parser::fields::ParseError;
    let kind = match &error {
        ParseError::Overflow(_) => Kind::Capacity,
        ParseError::Assertion(_) => Kind::Runtime,
        _ => Kind::Parse,
    };
    Failure::new(kind, error.to_string())
}
fn format_error(error: FormatError) -> Failure {
    match error {
        FormatError::Mismatch => Failure::new(
            Kind::Parse,
            "text does not match the supplied strptime format",
        ),
        FormatError::Value(message) => Failure::new(Kind::Value, message),
        FormatError::Overflow(message) => Failure::new(Kind::Capacity, message),
        FormatError::Runtime(message) => Failure::new(Kind::Runtime, message),
    }
}
fn parse_rows<P: Policy>(source: &Series, mut run: Run<'_>) -> Result<Series, Failure> {
    let values = source
        .str()
        .map_err(|_| Failure::new(Kind::Type, "parse requires a native String source"))?;
    let mut rows = Rows::new(if run.format.is_some() {
        Unit::Microsecond
    } else {
        Unit::Second
    });
    let mut scratch = native::Scratch::default();
    for (row, value) in values.iter().enumerate() {
        let Some(value) = value.filter(|value| !missing(value)) else {
            rows.missing();
            continue;
        };
        let mut read = || -> Result<(i128, usize, Unit), Failure> {
            if let Some(format) = run.format {
                let points = scratch.codepoints();
                points.clear();
                points.extend(value.chars().map(u32::from));
                let parsed =
                    formatted::read_native(format, &run.rules, points).map_err(format_error)?;
                let zone = match parsed.zone {
                    FormattedZone::Naive => 0,
                    FormattedZone::Offset(offset) => rows.offset(offset)?,
                    FormattedZone::Region(value) => region(&mut rows, &value)?,
                };
                Ok((
                    fields_nanos(parsed.fields, parsed.tail)?,
                    zone,
                    if parsed.tail == 0 {
                        Unit::Microsecond
                    } else {
                        Unit::Nanosecond
                    },
                ))
            } else {
                let parsed = native::parse::<P>(value, &mut scratch, &mut run.rules, run.prepared)
                    .map_err(parse_error)?;
                let zone = if let Some(value) = parsed.region {
                    region(&mut rows, &value)?
                } else if parsed.fields.is_tzoffset_set() {
                    rows.offset(parsed.fields.timezone_microseconds())?
                } else {
                    0
                };
                let unit = if parsed.fields.fraction.has_nanos() {
                    Unit::Nanosecond
                } else {
                    Unit::Microsecond
                };
                Ok((
                    fields_nanos(
                        parsed.completed.map(i64::from),
                        i64::from(parsed.fields.fraction.tail()),
                    )?,
                    zone,
                    unit,
                ))
            }
        };
        let (nanos, zone, unit) = read().map_err(|mut failure| {
            let preview: String = value.chars().take(120).collect();
            failure.message = format!("row {row}, input {preview:?}: {}", failure.message);
            failure.at(row)
        })?;
        if run.expression && run.target.is_none() && zone != 0 {
            return Err(Failure::new(Kind::Value,"timezone-aware text requires an explicit output tz; pass tz='UTC' or another supported common target").at(row));
        }
        rows.push(nanos, zone, false, unit);
    }
    rows.finish(
        source.name().clone(),
        run.requested,
        run.target,
        &run.policy,
        run.format.is_some(),
    )
}
fn execute(source: &Series, run: Run<'_>) -> Result<Series, Failure> {
    run.policy.check_len(source.len())?;
    if run.format.is_none() && source.dtype() != &DataType::String {
        return super::input::column(
            source,
            super::input::NativeOptions {
                requested: run.requested,
                target: run.target,
                policy: &run.policy,
                copy: false,
                round_ok: false,
            },
        );
    }
    if run.expression && run.requested.is_none() {
        return Err(Failure::new(
            Kind::Value,
            "String Expr requires an explicit unit (ms/us/ns)",
        ));
    }
    if source.dtype() == &DataType::Null {
        let unit = run.requested.unwrap_or(Unit::Microsecond);
        let zone = TimeZone::opt_try_new(run.target.map(Zone::key))
            .map_err(|error| Failure::new(Kind::Value, error.to_string()))?;
        return Ok(Series::full_null(
            source.name().clone(),
            source.len(),
            &DataType::Datetime(super::input::resolution(unit), zone),
        ));
    }
    if run.strict {
        parse_rows::<Nano<Strict>>(source, run)
    } else {
        parse_rows::<Nano<Lenient>>(source, run)
    }
}

#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_parse(inputs: &[Series], mut kwargs: Options) -> PolarsResult<Series> {
    polars_ensure!(kwargs.version==1 && !inputs.is_empty()&&inputs.len()<=2,InvalidOperation:"Pldt.parse: invalid prepared inputs/version");
    let entry = if kwargs.format.is_empty() {
        "Pldt.parse"
    } else {
        "Pldt.strptime"
    };
    let rules = match kwargs.prepared.rules.take() {
        Some(data) => NativeRules::from_data(data)
            .map_err(|error| polars_err!(ComputeError:"{}: {}",entry,error))?,
        None => NativeRules::library(),
    };
    let format = if kwargs.format.is_empty() {
        None
    } else {
        Some(serde_json::from_slice::<Format>(&kwargs.format).map_err(
            |error| polars_err!(ComputeError:"{}: invalid prepared format: {}",entry,error),
        )?)
    };
    let target = kwargs
        .target
        .map(Zone::from_data)
        .transpose()
        .map_err(|message| polars_err!(ComputeError:"{}: {}",entry,message))?;
    let policy = match inputs.get(1) {
        Some(mask) => kwargs
            .policy
            .with_expression_mask(mask, kwargs.mask_scalar)
            .map_err(|error| polars_err!(ComputeError:"{}: {}",entry,error))?,
        None => kwargs.policy,
    };
    execute(
        &inputs[0],
        Run {
            prepared: kwargs.prepared.options,
            rules,
            strict: kwargs.prepared.strict,
            format: format.as_ref(),
            requested: kwargs.unit.map(Resolution::epoch),
            target: target.as_ref(),
            policy,
            expression: true,
        },
    )
    .map_err(|error| error.polars(entry))
}

/// A compiled structure and immutable recognition data; no Python callbacks.
#[pyclass(frozen, skip_from_py_object, name = "_PldtFormatContext")]
struct FormatContext {
    format: Format,
    rules: NativeRules,
    custom: bool,
}
#[pymethods]
impl FormatContext {
    #[getter]
    fn has_fraction(&self) -> bool {
        self.format.has_fraction()
    }
    #[getter]
    fn has_timezone(&self) -> bool {
        self.format.has_timezone()
    }
    fn plugin_kwargs<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let data = PyDict::new(py);
        data.set_item(
            "prepared",
            TextData {
                options: native::Options {
                    default: None,
                    yearfirst: None,
                    dayfirst: None,
                    isoformat: false,
                },
                strict: false,
                rules: self.custom.then(|| self.rules.data()),
            },
        )?;
        let bytes = serde_json::to_vec(&self.format).map_err(|error| {
            crate::error_context::runtime(format!("cannot encode a compiled format: {error}"))
        })?;
        data.set_item("format", PyBytes::new(py, &bytes))?;
        Ok(data)
    }
}
#[pyfunction]
#[pyo3(signature=(format,cfg=None))]
fn _pldt_prepare_format(
    format: PyRef<'_, Format>,
    cfg: Option<&Bound<'_, PyAny>>,
) -> PyResult<FormatContext> {
    let rules = match cfg.filter(|v| !v.is_none()) {
        Some(value) => value
            .cast::<Configs>()
            .map_err(|_| {
                crate::error_context::expected_type(
                    value,
                    "Pldt.strptime",
                    "cfg",
                    "a Configs instance or None",
                )
            })?
            .borrow()
            .native_snapshot(),
        None => NativeRules::library(),
    };
    Ok(FormatContext {
        format: format.clone(),
        rules,
        custom: cfg.is_some_and(|v| !v.is_none()),
    })
}

#[pyfunction]
fn _pldt_text_needed(source: PySeries) -> PyResult<bool> {
    let values = source.0.str().map_err(super::eager_error)?;
    Ok(values
        .iter()
        .any(|value| value.is_some_and(|value| !missing(value))))
}

#[pyfunction]
#[pyo3(signature=(source,target,prepared,format,unit,tz,policy))]
fn _pldt_text<'py>(
    source: PySeries,
    target: &Bound<'py, PyAny>,
    prepared: Option<PyRef<'_, TextContext>>,
    format: Option<PyRef<'_, FormatContext>>,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let requested = super::input::selected(unit)?;
    let (options, rules, strict) = if let Some(context) = prepared.as_ref() {
        (context.options, context.rules.clone(), context.strict)
    } else if let Some(context) = format.as_ref() {
        (
            native::Options {
                default: None,
                yearfirst: None,
                dayfirst: None,
                isoformat: false,
            },
            context.rules.clone(),
            false,
        )
    } else {
        return Err(crate::error_context::runtime("text preparation is missing"));
    };
    let zone = tz.map(|context| context.value.clone());
    let policy = policy.value.clone();
    let format = format.map(|context| context.format.clone());
    let entry = if format.is_some() {
        "Pldt.strptime"
    } else {
        "Pldt.parse"
    };
    let result = py
        .detach(move || {
            execute(
                &source.0,
                Run {
                    prepared: options,
                    rules,
                    strict,
                    format: format.as_ref(),
                    requested,
                    target: zone.as_ref(),
                    policy,
                    expression: false,
                },
            )
        })
        .map_err(|error| error.python(py, entry))?;
    super::export(py, &result, target)
}

/// Mixed Python text keeps real str-subclass/iterator protocols at one boundary.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One formatted object input and final assembly boundary"
)]
#[pyo3(signature=(data,target,format,unit,tz,policy,cfg=None,size=None,name=""))]
fn _pldt_format_objects<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    target: &Bound<'py, PyAny>,
    format: PyRef<'_, Format>,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    cfg: Option<&Bound<'py, PyAny>>,
    size: Option<usize>,
    name: &str,
) -> PyResult<Bound<'py, PyAny>> {
    let requested = super::input::selected(unit)?;
    let context = formatted::Context::prepare(&format, cfg)?;
    let mut rows = Rows::new(Unit::Microsecond);
    let mut read = |value: &Bound<'py, PyAny>| -> PyResult<()> {
        if !value.is_instance_of::<PyString>() && crate::date_input::date_missing(value)? {
            rows.missing();
            return Ok(());
        }
        let text = value.cast::<PyString>().map_err(|_| {
            crate::error_context::type_error(
                "strptime requires text values, not dates or numeric input",
            )
        })?;
        let converted;
        let text = if value.is_exact_instance_of::<PyString>() {
            text
        } else {
            converted = value.str().map_err(crate::error_context::external)?;
            &converted
        };
        if crate::date_input::missing_text(text)? {
            rows.missing();
            return Ok(());
        }
        let parsed = formatted::read(&context, text)?.into_epoch()?;
        let source = match parsed.zone {
            crate::epoch::Zone::Naive => 0,
            crate::epoch::Zone::Offset(offset) => rows
                .offset(offset)
                .map_err(|error| error.python(py, "Pldt.strptime"))?,
            crate::epoch::Zone::Object(value) => rows
                .zone(super::zones::prepare_host_zone(value.bind(py))?)
                .map_err(|error| error.python(py, "Pldt.strptime"))?,
        };
        rows.push(parsed.nanos, source, false, parsed.unit);
        Ok(())
    };
    if let Some(size) = size {
        read(data).map_err(|error| {
            crate::error_context::argument(py, error, "Pldt.strptime", "dtstr", data)
        })?;
        rows.repeat(size)
            .map_err(|error| error.python(py, "Pldt.strptime"))?;
    } else {
        for (row, value) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let value = value.map_err(crate::error_context::external)?;
            read(&value).map_err(|error| {
                crate::error_context::item(
                    py,
                    error,
                    "Pldt.strptime",
                    "dtstr",
                    row,
                    Some(&value),
                    false,
                )
            })?;
        }
    }
    let result = rows
        .finish(
            name.into(),
            requested,
            tz.as_ref().map(|value| &value.value),
            &policy.value,
            true,
        )
        .map_err(|error| error.python(py, "Pldt.strptime"))?;
    super::export(py, &result, target)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<FormatContext>()?;
    module.add_function(wrap_pyfunction!(_pldt_prepare_format, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_text_needed, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_text, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_format_objects, module)?)
}
