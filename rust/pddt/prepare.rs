//! One-pass collection preparation, with no Python datetime text intermediate.
use super::common::{NS_DAY, Rows, finish};
use crate::epoch::{self, Options, Parsed, Unit, Zone};
use crate::parser::fields::{Lenient, Nano, Policy, Precision, Strict};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBytes, PyFloat, PyInt, PyString};

static MISSING: PyOnceLock<(Py<PyAny>, Py<PyAny>)> = PyOnceLock::new();

#[pyfunction]
fn _pddt_register(py: Python<'_>, na: Py<PyAny>, nat: Py<PyAny>, resolver: Py<PyAny>) {
    let _ = MISSING.set(py, (na, nat));
    super::common::register_zone_resolver(py, resolver);
}

/// Decode completed local fields; region localization belongs to Pddt, not Parser.
pub(super) fn text_fields<P: Policy>(
    py: Python<'_>,
    text: &Bound<'_, PyString>,
    default: Option<[i32; 3]>,
    opts: &Options<'_, '_>,
) -> PyResult<Parsed> {
    let parsed = crate::parser::read_fields_prepared::<P>(
        py,
        text,
        default,
        opts.yearfirst,
        opts.dayfirst,
        opts.ignoretz,
        opts.isoformat,
        opts.cfg,
    )?;
    let [y, m, d, h, minute, s, us] = crate::parser::complete(&parsed.fields, default)?;
    let day = crate::calendar::checked_ordinal(i64::from(y), i64::from(m), i64::from(d))
        .map_err(crate::error_context::overflow)?
        - 719_163;
    let nanos = i128::from(day) * NS_DAY
        + ((i128::from(h) * 60 + i128::from(minute)) * 60 + i128::from(s)) * 1_000_000_000
        + i128::from(us) * 1000
        + i128::from(parsed.fields.fraction.tail());
    let zone = if opts.ignoretz {
        Zone::Naive
    } else if let Some(region) = parsed.region {
        let object = region.object.as_ref().ok_or_else(|| {
            crate::error_context::value_error(
                "the registered region is unavailable in this environment",
            )
        })?;
        Zone::Object(object.clone_ref(py))
    } else if parsed.fields.is_tzoffset_set() {
        let offset = parsed.fields.timezone_microseconds();
        if !(-86_400_000_000..86_400_000_000).contains(&offset) || offset == -86_400_000_000 {
            return Err(crate::parser::invalid_offset(py, offset));
        }
        Zone::Offset(offset)
    } else {
        Zone::Naive
    };
    Ok(Parsed {
        nanos,
        unit: if parsed.fields.fraction.has_nanos() {
            Unit::Nanosecond
        } else {
            Unit::Microsecond
        },
        zone,
    })
}

/// Check only the tiny ASCII missing literals without UTF8-encoding date text.
pub(super) fn missing_text(text: &Bound<'_, PyString>) -> PyResult<bool> {
    // SAFETY: the checked live PyString proves Unicode layout and keeps its owner.
    let length = unsafe { ffi::PyUnicode_GET_LENGTH(text.as_ptr()) };
    if length == 0 {
        return Ok(true);
    }
    if length != 3 {
        return Ok(false);
    }
    for token in [c"NaT", c"NAT", c"nat", c"NaN", c"NAN", c"nan"] {
        // The public Unicode comparison reads code points, including surrogates.
        let result =
            unsafe { ffi::PyUnicode_CompareWithASCIIString(text.as_ptr(), token.as_ptr()) };
        if result == -1 && PyErr::occurred(text.py()) {
            return Err(PyErr::fetch(text.py()));
        }
        if result == 0 {
            return Ok(true);
        }
    }
    Ok(false)
}

pub(super) fn missing(value: &Bound<'_, PyAny>) -> bool {
    value.is_none()
        || MISSING.get(value.py()).is_some_and(|(na, nat)| {
            value.is(na.bind(value.py())) || value.is(nat.bind(value.py()))
        })
}

pub(super) fn nat(py: Python<'_>) -> PyResult<Bound<'_, PyAny>> {
    MISSING
        .get(py)
        .map(|(_, nat)| nat.bind(py).clone())
        .ok_or_else(|| crate::error_context::runtime("Pddt missing values are not registered"))
}

pub(super) fn scalar_unit(code: i32) -> PyResult<Unit> {
    match code {
        0..=2 | 4..=7 | 14 => Ok(Unit::Second),
        8 => Ok(Unit::Millisecond),
        9 => Ok(Unit::Microsecond),
        10 => Ok(Unit::Nanosecond),
        _ => Err(crate::error_context::value_error(
            "unsupported NumPy date unit; use years through nanoseconds",
        )),
    }
}

/// One-pass scalar decoding reused by columns, range endpoints and date targets.
pub(super) struct Reader<'a, 'py> {
    opts: Options<'a, 'py>,
    pub unit: Unit,
    prepared_default: Option<Option<[i32; 3]>>,
}
impl<'a, 'py> Reader<'a, 'py> {
    pub fn new(opts: Options<'a, 'py>, unit: Unit) -> Self {
        Self {
            opts,
            unit,
            prepared_default: None,
        }
    }
    pub fn read(
        &mut self,
        item: &Bound<'_, PyAny>,
        entry: &str,
    ) -> PyResult<Option<(Parsed, bool)>> {
        let result = self.read_value(item, entry)?;
        if let Some((parsed, _)) = &result {
            self.unit = self.unit.max(parsed.unit);
        }
        Ok(result)
    }
    fn read_value(
        &mut self,
        item: &Bound<'_, PyAny>,
        entry: &str,
    ) -> PyResult<Option<(Parsed, bool)>> {
        let py = item.py();
        let opts = &self.opts;
        let (default, yearfirst, dayfirst, isoformat, cfg, strict, numeric) = (
            opts.default,
            opts.yearfirst,
            opts.dayfirst,
            opts.isoformat,
            opts.cfg,
            opts.strict,
            opts.input_unit,
        );

        if missing(item) {
            return Ok(None);
        }
        if crate::numeric::is_bool(item) {
            return Err(crate::error_context::type_error(
                "boolean values are not date inputs",
            ));
        }
        if let Ok(text) = item.cast::<PyString>() {
            let converted;
            let text = if item.is_exact_instance_of::<PyString>() {
                text
            } else {
                converted = item.str().map_err(crate::error_context::external)?;
                &converted
            };
            if missing_text(text)? {
                return Ok(None);
            }
            let fallback = if let Some(value) = self.prepared_default {
                value
            } else {
                let value = crate::parser::prepare_default(
                    py, default, yearfirst, dayfirst, isoformat, cfg, strict,
                )
                .map_err(|e| match default {
                    Some(v) => crate::error_context::argument(py, e, entry, "default", v),
                    None => e,
                })?;
                self.prepared_default = Some(value);
                value
            };
            let value = if strict {
                text_fields::<Nano<Strict>>(py, text, fallback, opts)?
            } else {
                text_fields::<Nano<Lenient>>(py, text, fallback, opts)?
            };
            return Ok(Some((value, false)));
        }
        if let Some((ticks, code, multiplier)) = crate::numpy_scalar::datetime_ticks(item)? {
            self.unit = self.unit.max(scalar_unit(code)?);
            if ticks == i64::MIN {
                return Ok(None);
            }
            return epoch::numpy_ticks(ticks, code, multiplier).map(|p| Some((p, false)));
        }
        if item.is_instance_of::<PyInt>() || unsafe { ffi::PyIndex_Check(item.as_ptr()) != 0 } {
            let ticks = crate::numeric::index_i64(item)?;
            self.unit = self.unit.max(numeric);
            if ticks == i64::MIN {
                return Ok(None);
            }
            return Ok(Some((
                Parsed {
                    nanos: i128::from(ticks) * numeric.nanos(),
                    unit: numeric,
                    zone: Zone::Naive,
                },
                true,
            )));
        }
        if crate::numeric::supported_float(item) {
            let value = if item.is_instance_of::<PyFloat>() {
                item.extract::<f64>()?
            } else {
                crate::numeric::float_value(item)?
            };
            if value.is_nan() {
                return Ok(None);
            }
            if !value.is_finite() || value < i64::MIN as f64 || value >= 9223372036854775808.0 {
                return Err(crate::error_context::overflow(
                    "numeric date tick exceeds signed64",
                ));
            }
            if value.fract() != 0.0 {
                return Err(crate::error_context::value_error(
                    "numeric construction requires an integer tick; use fromseconds for fractional seconds",
                ));
            }
            self.unit = self.unit.max(numeric);
            if value == i64::MIN as f64 {
                return Ok(None);
            }
            return Ok(Some((
                Parsed {
                    nanos: i128::from(value as i64) * numeric.nanos(),
                    unit: numeric,
                    zone: Zone::Naive,
                },
                true,
            )));
        }
        // Actual datetime/date subclasses keep the existing live-field and
        // offset protocol. Other iterable objects are not scalar dates.
        if unsafe { ffi::PyDate_Check(item.as_ptr()) != 0 } {
            let parsed = epoch::read(item, opts)?;
            let instant = !matches!(parsed.zone, Zone::Naive);
            return Ok(Some((parsed, instant)));
        }
        Err(crate::error_context::type_error(
            "expected date/time text, date, datetime, NumPy datetime64 or a supported numeric tick",
        ))
    }
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
    if data.len() % 8 != 0 || multiplier < 1 {
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
    for (index, bytes) in data.chunks_exact(8).enumerate() {
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
