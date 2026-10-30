//! Scalar temporal input roles shared by native column adapters.
//!
//! The Reader prepares default lazily once and preserves actual source precision.
//! Its const sentinel policy applies only to bare numeric ticks: NumPy dates keep
//! their own NaT semantics while Polars numeric input uses all signed64 values.
use crate::epoch::{self, Options, Parsed, Unit, Zone};
use crate::parser::fields::{Lenient, Nano, Policy, Precision, Strict};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyFloat, PyInt, PyString};

const NS_DAY: i128 = 86_400_000_000_000;
static MISSING: PyOnceLock<(Py<PyAny>, Py<PyAny>)> = PyOnceLock::new();

/// Cache actual optional pandas missing singletons once; no pandas import here.
pub(crate) fn register_missing(py: Python<'_>, na: Py<PyAny>, nat: Py<PyAny>) {
    let _ = MISSING.set(py, (na, nat));
}

/// Decode completed local fields; region localization belongs to Pddt, not Parser.
pub(crate) fn text_fields<P: Policy>(
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
pub(crate) fn missing_text(text: &Bound<'_, PyString>) -> PyResult<bool> {
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

pub(crate) fn missing(value: &Bound<'_, PyAny>) -> bool {
    value.is_none()
        || MISSING.get(value.py()).is_some_and(|(na, nat)| {
            value.is(na.bind(value.py())) || value.is(nat.bind(value.py()))
        })
}

/// Missing date values at typed factory/field boundaries; no truth coercion.
pub(crate) fn date_missing(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    if missing(value) {
        return Ok(true);
    }
    if let Ok(text) = value.cast::<PyString>() {
        return missing_text(text);
    }
    if crate::numeric::supported_float(value) {
        let number = if value.is_instance_of::<PyFloat>() {
            value.extract::<f64>()?
        } else {
            crate::numeric::float_value(value)?
        };
        return Ok(number.is_nan());
    }
    if let Some((ticks, code, _)) = crate::numpy_scalar::datetime_ticks(value)? {
        scalar_unit(code)?;
        return Ok(ticks == i64::MIN);
    }
    Ok(false)
}

/// Named source roles share ordinary field reading, not public constructors.
#[derive(Clone, Copy)]
pub(crate) enum DateSource {
    Date,
    Datetime,
    Numpy,
}

/// Read real source fields with the already adopted local/instant distinction.
pub(crate) fn named_date(
    value: &Bound<'_, PyAny>,
    kind: DateSource,
    replace: bool,
) -> PyResult<Option<(Parsed, bool)>> {
    if date_missing(value)? {
        return Ok(None);
    }
    if matches!(kind, DateSource::Numpy) {
        let (ticks, code, multiplier) =
            crate::numpy_scalar::datetime_ticks(value)?.ok_or_else(|| {
                crate::error_context::type_error(
                    "requires a NumPy datetime64 value; use fromdatetime for Python datetime",
                )
            })?;
        return epoch::numpy_ticks(ticks, code, multiplier).map(|value| Some((value, false)));
    }
    // SAFETY: only real ancestry of a live bound object is checked here.
    let valid = unsafe {
        if matches!(kind, DateSource::Date) {
            ffi::PyDate_Check(value.as_ptr())
        } else {
            ffi::PyDateTime_Check(value.as_ptr())
        }
    };
    if valid == 0 {
        return Err(crate::error_context::type_error(
            if matches!(kind, DateSource::Date) {
                "requires date or datetime values; use parse for text and fromdatetime64 for NumPy dates"
            } else {
                "requires datetime values, not plain date, text or numeric data"
            },
        ));
    }
    let opts = Options {
        default: None,
        yearfirst: None,
        dayfirst: None,
        ignoretz: replace || matches!(kind, DateSource::Date),
        isoformat: true,
        strict: false,
        iso_only: false,
        cfg: None,
        input_unit: Unit::Second,
    };
    let mut parsed = epoch::read(value, &opts)?;
    if matches!(kind, DateSource::Date) {
        parsed.nanos = parsed.nanos.div_euclid(NS_DAY) * NS_DAY;
        parsed.zone = Zone::Naive;
    }
    let instant =
        matches!(kind, DateSource::Datetime) && !replace && !matches!(parsed.zone, Zone::Naive);
    Ok(Some((parsed, instant)))
}

pub(crate) fn nat(py: Python<'_>) -> PyResult<Bound<'_, PyAny>> {
    MISSING
        .get(py)
        .map(|(_, nat)| nat.bind(py).clone())
        .ok_or_else(|| crate::error_context::runtime("Pddt missing values are not registered"))
}

pub(crate) fn scalar_unit(code: i32) -> PyResult<Unit> {
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
pub(crate) struct Reader<'a, 'py, const SENTINEL: bool> {
    opts: Options<'a, 'py>,
    pub unit: Unit,
    prepared_default: Option<Option<[i32; 3]>>,
}
impl<'a, 'py, const SENTINEL: bool> Reader<'a, 'py, SENTINEL> {
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
            if SENTINEL && ticks == i64::MIN {
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
            if SENTINEL && value == i64::MIN as f64 {
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

/// Fixed timezone preparation shared by host-side source readers.
pub(crate) fn fixed_offset(py: Python<'_>, zone: &Zone) -> PyResult<Option<i64>> {
    match zone {
        Zone::Naive => Ok(Some(0)),
        Zone::Offset(us) => Ok(Some(*us)),
        Zone::Object(value) => {
            let zone = value.bind(py);
            // SAFETY: datetime's initialized capsule owns its standard UTC object.
            let fixed = unsafe {
                ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
            };
            if fixed {
                return crate::epoch::offset_us(
                    &zone
                        .call_method1("utcoffset", (py.None(),))
                        .map_err(crate::error_context::external)?,
                );
            }
            crate::pydt::fixed_zoneinfo_offset(zone)
        }
    }
}
