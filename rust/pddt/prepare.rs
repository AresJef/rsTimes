//! One-pass collection preparation, with no Python datetime text intermediate.
use super::common::{Rows, finish};
use crate::epoch::{self, Options, Unit, Zone};
use crate::parser::config::{Configs, FormatRules};
use crate::parser::fields::{Lenient, Nano, Policy, Precision, Strict};
use crate::parser::prepared::TextContext;
use polars::prelude::Series;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDate, PyDateTime, PyFloat, PyInt, PyList, PyString, PyTuple};
use pyo3_polars::PySeries;

#[pyfunction]
fn _pddt_register(py: Python<'_>, na: Py<PyAny>, nat: Py<PyAny>, resolver: Py<PyAny>) {
    crate::date_input::register_missing(py, na, nat);
    super::common::register_zone_resolver(py, resolver);
}

// This specialization retains the adopted pandas NaT numeric-sentinel contract.
pub(super) type Reader<'a, 'py> = crate::date_input::Reader<'a, 'py, true>;
pub(super) use crate::date_input::{missing, missing_text, nat, scalar_unit};

type Prepared<'py> = (Bound<'py, PyBytes>, &'static str, Py<PyAny>);

/// Callback-bearing defaults keep the adopted live Reader path. These exact
/// builtin values expose no custom field or conversion callback.
fn stable_default(value: Option<&Bound<'_, PyAny>>) -> bool {
    value.is_none_or(|value| {
        value.is_none()
            || value.is_exact_instance_of::<PyString>()
            || value.is_exact_instance_of::<PyInt>()
            || value.is_exact_instance_of::<PyFloat>()
            || value.is_exact_instance_of::<PyDateTime>()
            || value.is_exact_instance_of::<PyDate>()
    })
}

fn native_strings<'py, P: Policy>(
    py: Python<'py>,
    source: &Series,
    policy: &super::zones::Policies,
    requested: Option<Unit>,
    opts: Options<'_, '_>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<Prepared<'py>> {
    let values = source.str().map_err(|_| {
        crate::error_context::type_error("native date-text input must have Polars String dtype")
    })?;
    let mut rows = Rows::new(Unit::Second);
    rows.reserve(source.len())?;
    let mut prepared: Option<(TextContext, FormatRules)> = None;
    let mut scratch = crate::parser::native::Scratch::default();
    for (index, value) in values.iter().enumerate() {
        let Some(value) = value.filter(|value| !crate::date_input::missing_utf8(value)) else {
            rows.missing();
            continue;
        };
        if prepared.is_none() {
            let context = TextContext::eager(
                py,
                opts.cfg,
                opts.default,
                opts.yearfirst,
                opts.dayfirst,
                opts.isoformat,
                opts.strict,
            )
            .map_err(|error| match opts.default {
                Some(default) => {
                    crate::error_context::argument(py, error, entry, "default", default)
                }
                None => error,
            })?;
            // Keep original ZoneInfo identities in this GIL adapter only. The
            // shared native worker context continues to contain no Python data.
            let zones = FormatRules::prepare(opts.cfg)?;
            prepared = Some((context, zones));
        }
        let (context, zones) = prepared.as_mut().ok_or_else(|| {
            crate::error_context::runtime("native date-text preparation is unavailable")
        })?;
        let mut read = || -> PyResult<epoch::Parsed> {
            let parsed = crate::parser::native::parse::<P>(
                value,
                &mut scratch,
                &mut context.rules,
                context.options,
            )
            .map_err(crate::parser::native_error)?;
            let zone = if let Some(region) = parsed.region {
                let registered = zones
                    .region_key(&region.key, scratch.codepoints())
                    .ok_or_else(|| {
                        crate::error_context::value_error(
                            "the registered region is unavailable in this environment",
                        )
                    })?;
                Zone::Object(
                    crate::parser::zones::object(py, &registered)?
                        .clone()
                        .unbind(),
                )
            } else if parsed.fields.is_tzoffset_set() {
                let offset = parsed.fields.timezone_microseconds();
                if !(-86_400_000_000..86_400_000_000).contains(&offset) || offset == -86_400_000_000
                {
                    return Err(crate::parser::invalid_offset(py, offset));
                }
                Zone::Offset(offset)
            } else {
                Zone::Naive
            };
            Ok(epoch::Parsed {
                nanos: crate::civil::fields_nanos(
                    parsed.completed.map(i64::from),
                    i64::from(parsed.fields.fraction.tail()),
                )
                .map_err(crate::error_context::overflow)?,
                unit: if parsed.fields.fraction.has_nanos() {
                    Unit::Nanosecond
                } else {
                    Unit::Microsecond
                },
                zone,
            })
        };
        let parsed = read()
            .map_err(|error| crate::error_context::text_item(py, error, entry, index, value))?;
        rows.push(py, parsed, false)?;
    }
    finish(py, rows, requested, target, entry, policy)
}

/// Exact builtin sequences have no iterator callback. The caller verifies every
/// element before preparing rules; callback-bearing defaults stay on Reader.
#[expect(
    clippy::too_many_arguments,
    reason = "Callback-free collection adapter keeps parser and output roles explicit"
)]
fn plain_strings<'py, P: Policy>(
    py: Python<'py>,
    values: impl Iterator<Item = Bound<'py, PyAny>>,
    mut rows: Rows,
    opts: Options<'_, '_>,
    requested: Option<Unit>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
    policy: &super::zones::Policies,
) -> PyResult<Prepared<'py>> {
    let mut prepared = None;
    let mut scratch = crate::parser::native::Scratch::default();
    for (index, item) in values.enumerate() {
        let mut read = || -> PyResult<Option<epoch::Parsed>> {
            if item.is_none() {
                return Ok(None);
            }
            let text = item.cast::<PyString>()?;
            if missing_text(text)? {
                return Ok(None);
            }
            if prepared.is_none() {
                let default = crate::parser::prepare_default(
                    py,
                    opts.default,
                    opts.yearfirst,
                    opts.dayfirst,
                    opts.isoformat,
                    opts.cfg,
                    opts.strict,
                )
                .map_err(|error| match opts.default {
                    Some(default) => {
                        crate::error_context::argument(py, error, entry, "default", default)
                    }
                    None => error,
                })?;
                prepared = Some((
                    crate::parser::native::Options {
                        default,
                        yearfirst: opts.yearfirst,
                        dayfirst: opts.dayfirst,
                        isoformat: opts.isoformat,
                    },
                    FormatRules::prepare(opts.cfg)?,
                ));
            }
            let (options, rules) = prepared.as_ref().ok_or_else(|| {
                crate::error_context::runtime("date-text preparation is unavailable")
            })?;
            let parsed = crate::parser::read_collection_fields::<P>(
                py,
                text,
                *options,
                rules,
                &mut scratch,
            )?;
            crate::date_input::finish_text(py, parsed, false).map(Some)
        };
        let parsed = read().map_err(|error| {
            crate::error_context::item(py, error, entry, "data", index, Some(&item), false)
        })?;
        if let Some(parsed) = parsed {
            rows.push(py, parsed, false)?;
        } else {
            rows.missing();
        }
    }
    finish(py, rows, requested, target, entry, policy)
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared native String collection boundary"
)]
#[pyo3(signature=(data,policy,unit=None,default=None,yearfirst=None,dayfirst=None,isoformat=true,strict=false,cfg=None,target=None,entry="Pddt"))]
fn _pddt_strings<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    policy: PyRef<'_, super::zones::Policies>,
    unit: Option<&str>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    strict: bool,
    cfg: Option<&Bound<'py, PyAny>>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<Option<Prepared<'py>>> {
    let requested = unit.map(Unit::parse).transpose()?;
    if let Some(cfg) = cfg.filter(|value| !value.is_none()) {
        cfg.cast::<Configs>().map_err(|_| {
            crate::error_context::expected_type(cfg, entry, "cfg", "a Configs instance or None")
        })?;
    }
    if !stable_default(default) {
        return Ok(None);
    }
    if !epoch::is_polars_series(data) {
        return Err(crate::error_context::expected_type(
            data,
            entry,
            "data",
            "a Polars Series",
        ));
    }
    let source = data
        .extract::<PySeries>()
        .map_err(crate::error_context::external)?
        .0;
    let opts = Options {
        default,
        yearfirst,
        dayfirst,
        ignoretz: false,
        isoformat,
        strict,
        iso_only: false,
        cfg,
        input_unit: requested.unwrap_or(Unit::Nanosecond),
    };
    if strict {
        native_strings::<Nano<Strict>>(py, &source, &policy, requested, opts, target, entry)
    } else {
        native_strings::<Nano<Lenient>>(py, &source, &policy, requested, opts, target, entry)
    }
    .map(Some)
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One prepared collection boundary"
)]
#[pyo3(signature=(data,policy,unit=None,base_unit=None,default=None,yearfirst=None,dayfirst=None,isoformat=true,strict=false,cfg=None,target=None,entry="Pddt"))]
fn _pddt_prepare<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    policy: PyRef<'_, super::zones::Policies>,
    unit: Option<&str>,
    base_unit: Option<&str>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    strict: bool,
    cfg: Option<&Bound<'py, PyAny>>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let requested = unit.map(Unit::parse).transpose()?;
    if let Some(cfg) = cfg.filter(|c| !c.is_none()) {
        cfg.cast::<crate::parser::config::Configs>().map_err(|_| {
            crate::error_context::expected_type(cfg, entry, "cfg", "a Configs instance or None")
        })?;
    }
    let mut rows = Rows::new(
        base_unit
            .map(Unit::parse)
            .transpose()?
            .unwrap_or(Unit::Second),
    );
    let numeric = requested.unwrap_or(Unit::Nanosecond);
    let opts = Options {
        default,
        yearfirst,
        dayfirst,
        ignoretz: false,
        isoformat,
        strict,
        iso_only: false,
        cfg,
        input_unit: numeric,
    };
    // Only these native builtin iterators and exact scalar values can prove
    // that no user callback changes configuration between text rows.
    if stable_default(default) {
        let simple =
            |item: Bound<'_, PyAny>| item.is_none() || item.is_exact_instance_of::<PyString>();
        if data.is_exact_instance_of::<PyList>() {
            let values = data.cast::<PyList>()?;
            if values.iter().all(simple) {
                rows.reserve(values.len())?;
                return if strict {
                    plain_strings::<Nano<Strict>>(
                        py,
                        values.iter(),
                        rows,
                        opts,
                        requested,
                        target,
                        entry,
                        &policy,
                    )
                } else {
                    plain_strings::<Nano<Lenient>>(
                        py,
                        values.iter(),
                        rows,
                        opts,
                        requested,
                        target,
                        entry,
                        &policy,
                    )
                };
            }
        } else if data.is_exact_instance_of::<PyTuple>() {
            let values = data.cast::<PyTuple>()?;
            if values.iter().all(simple) {
                rows.reserve(values.len())?;
                return if strict {
                    plain_strings::<Nano<Strict>>(
                        py,
                        values.iter(),
                        rows,
                        opts,
                        requested,
                        target,
                        entry,
                        &policy,
                    )
                } else {
                    plain_strings::<Nano<Lenient>>(
                        py,
                        values.iter(),
                        rows,
                        opts,
                        requested,
                        target,
                        entry,
                        &policy,
                    )
                };
            }
        }
    }
    let mut reader = Reader::new(opts, rows.unit);
    let iterator = data
        .try_iter()
        .map_err(crate::error_context::external)
        .map_err(|e| crate::error_context::argument(py, e, entry, "data", data))?;
    for (i, item) in iterator.enumerate() {
        let item = item
            .map_err(crate::error_context::external)
            .map_err(|e| crate::error_context::item(py, e, entry, "data", i, None, true))?;
        let row = reader
            .read(&item, entry)
            .map_err(|e| crate::error_context::item(py, e, entry, "data", i, Some(&item), false))?;
        rows.unit = reader.unit;
        if let Some((parsed, instant)) = row {
            rows.push(py, parsed, instant)?;
        } else {
            rows.missing();
        }
    }
    finish(py, rows, requested, target, entry, &policy)
}

/// Decode a homogeneous owned date snapshot without creating scalar objects.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared buffer metadata boundary"
)]
#[pyo3(signature=(data,policy,source,multiplier=1,unit=None,source_zone=None,target=None,entry="Pddt",mask=None))]
fn _pddt_dates<'py>(
    py: Python<'py>,
    data: &[u8],
    policy: PyRef<'_, super::zones::Policies>,
    source: &str,
    multiplier: i32,
    unit: Option<&str>,
    source_zone: Option<&Bound<'py, PyAny>>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
    mask: Option<&[u8]>,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let code = match source {
        "Y" => 0,
        "M" => 1,
        "W" => 2,
        "D" => 4,
        "h" => 5,
        "m" => 6,
        "s" => 7,
        "ms" => 8,
        "us" => 9,
        "ns" => 10,
        _ => {
            return Err(crate::error_context::value_error(
                "unsupported NumPy date unit; use years through nanoseconds",
            ));
        }
    };
    if !data.len().is_multiple_of(8) || multiplier < 1 {
        return Err(crate::error_context::value_error(
            "invalid date buffer metadata",
        ));
    }
    let validity = super::validity::TemporalValidity::new(mask, data.len() / 8)?;
    let requested = unit.map(Unit::parse).transpose()?;
    let mut rows = Rows::new(scalar_unit(code)?);
    let source_zone = source_zone.filter(|z| !z.is_none());
    // A homogeneous native-unit snapshot has one known source role. Decode
    // its ticks directly; mixed zones and calendar units keep full preparation.
    let native_scale = (multiplier == 1 && source_zone.is_none() && (7..=10).contains(&code))
        .then_some(rows.unit.nanos());
    let mut raw = [0; 8];
    for (index, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        raw.copy_from_slice(bytes);
        let ticks = i64::from_ne_bytes(raw);
        if validity.missing(index, ticks) {
            rows.missing();
            continue;
        }
        if let Some(scale) = native_scale {
            rows.values.push(Some(i128::from(ticks) * scale));
            rows.sources.push(super::common::Source {
                zone: 0,
                instant: false,
            });
            continue;
        }
        let mut parsed =
            epoch::native_datetime_ticks(ticks, code, multiplier).map_err(|error| {
                crate::error_context::location(py, error, entry, &format!("data[{index}]"))
            })?;
        if let Some(zone) = source_zone {
            parsed.zone = Zone::Object(zone.clone().unbind());
        }
        rows.push(py, parsed, source_zone.is_some())?;
    }
    // Typed all-NaT/empty aware sources retain their declared timezone too.
    finish(py, rows, requested, target.or(source_zone), entry, &policy)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_result_type, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_register, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_prepare, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_strings, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_dates, module)?)
}

/// New date results require real ancestry, never a displayed class or ABC hook.
#[pyfunction]
fn _pddt_result_type(
    value: &Bound<'_, PyAny>,
    class: &Bound<'_, pyo3::types::PyType>,
    base: &Bound<'_, pyo3::types::PyType>,
) -> bool {
    // SAFETY: the live value and both validated Python type objects are held
    // under the GIL. The C predicate reads actual inheritance without callbacks.
    unsafe {
        let actual = pyo3::ffi::Py_TYPE(value.as_ptr());
        pyo3::ffi::PyType_IsSubtype(actual, class.as_type_ptr()) != 0
            && pyo3::ffi::PyType_IsSubtype(actual, base.as_type_ptr()) != 0
    }
}
