//! Function-based date/time parsing and the Python compatibility boundary.
pub(crate) mod config;
pub(crate) mod fields;
pub(crate) mod formatted;
pub(crate) mod iso_factory;
pub(crate) mod objects;
mod resolve;
mod scan;
mod text;
pub(crate) mod zones;

use config::Configs;
use fields::{Fields, Lenient, ParseError, Policy, Strict};

use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyAny, PyInt, PyString, PyTuple};
use pyo3::{Borrowed, ffi};
use std::sync::Arc;
use text::TextView;

/// Native fields plus an optional, already registered regional boundary.
pub(crate) struct ParsedFields<P: Policy> {
    pub fields: Fields<P>,
    pub region: Option<Arc<zones::RegisteredZone>>,
    pub default_date: Option<[i32; 3]>,
}
impl<P: Policy> std::ops::Deref for ParsedFields<P> {
    type Target = Fields<P>;
    fn deref(&self) -> &Self::Target {
        &self.fields
    }
}

static DATETIME_KEYWORDS: PyOnceLock<Py<PyTuple>> = PyOnceLock::new();

/// A Python boundary truth value, stored as a native bool after extraction.
pub(crate) struct Truth(pub(crate) bool);
/// Read an ordinary option once; no arbitrary truth protocol is part of the API.
#[inline]
pub(crate) fn truth(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    crate::numeric::boolean(value)
}
impl<'a, 'py> FromPyObject<'a, 'py> for Truth {
    type Error = PyErr;
    fn extract(value: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        Ok(Self(truth(&value)?))
    }
}

#[cold]
#[inline(never)]
fn native_error(error: ParseError) -> PyErr {
    match error {
        ParseError::Value(message) => {
            Python::attach(|py| crate::error_context::domain(py, "ParseError", message))
        }
        ParseError::Overflow(message) => crate::error_context::overflow(message),
        ParseError::Assertion(message) => crate::error_context::runtime(message),
    }
}
#[cold]
#[inline(never)]
fn failed(py: Python<'_>, message: Bound<'_, PyAny>, cause: Option<PyErr>) -> PyErr {
    // The native parser has already chosen its own error category. A target
    // constructor/callback is external and must not become a parsing failure.
    if let Some(error) = cause {
        return error;
    }
    let detail = match message.extract::<String>() {
        Ok(detail) => detail,
        Err(error) => return error,
    };
    crate::error_context::domain(py, "ParseError", detail)
}

/// Complete error context at the actual public parser entry.
#[cold]
#[inline(never)]
pub(crate) fn entry_error(
    py: Python<'_>,
    entry: &str,
    parameter: &str,
    input: &Bound<'_, PyAny>,
    error: PyErr,
) -> PyErr {
    crate::error_context::argument(py, error, entry, parameter, input)
}

#[inline]
fn is_date_default(value: &Bound<'_, PyAny>) -> bool {
    // SAFETY: the imported datetime API checks live objects under the GIL.
    // Exact date/datetime values avoid a subtype walk; subclasses retain the
    // existing native-layout check and never read overridden Python properties.
    unsafe {
        ffi::PyDate_CheckExact(value.as_ptr()) != 0
            || ffi::PyDateTime_CheckExact(value.as_ptr()) != 0
            || ffi::PyDate_Check(value.as_ptr()) != 0
    }
}

/// Complete shared native fields before allocating any Python result.
#[inline]
pub(crate) fn complete<P: Policy>(f: &Fields<P>, default: Option<[i32; 3]>) -> PyResult<[i32; 7]> {
    let yy = if f.is_year_set() {
        f.year
    } else if let Some(v) = default {
        v[0]
    } else {
        return Err(native_error(ParseError::Value(
            "year is missing; provide a complete default date".into(),
        )));
    };
    let mm = if f.is_month_set() {
        f.month
    } else if let Some(v) = default {
        v[1]
    } else {
        return Err(native_error(ParseError::Value(
            "month is missing; provide a complete default date".into(),
        )));
    };
    let dd = if f.is_day_set() {
        f.day
    } else if let Some(v) = default {
        v[2]
    } else {
        return Err(native_error(ParseError::Value(
            "day is missing; provide a complete default date".into(),
        )));
    };
    let dd = if dd > 28 {
        let last = crate::calendar::days_in_month(i64::from(yy), i64::from(mm)) as i32;
        if f.strict() && f.is_day_set() && dd > last {
            return Err(native_error(ParseError::Value(format!(
                "day={dd} is invalid for {yy:04}-{mm:02}; expected 1 through {last}, inclusive"
            ))));
        }
        dd.min(last)
    } else {
        dd
    };
    let (mut yy, mut mm, mut dd) = (yy, mm, dd);
    if f.is_weekday_set() {
        // Native calendar indexing requires a real month. Match the reference
        // calendar helper's clamp before the Python constructor validates.
        let ordinal =
            crate::calendar::ordinal(i64::from(yy), i64::from(mm.clamp(1, 12)), i64::from(dd));
        let weekday = (ordinal - 1).rem_euclid(7) as i32;
        if weekday != f.weekday {
            if f.strict() && f.is_year_set() && f.is_month_set() && f.is_day_set() {
                return Err(native_error(ParseError::Value(format!(
                    "conflicting weekday: {yy:04}-{mm:02}-{dd:02} has weekday {weekday}, not {}",
                    f.weekday
                ))));
            }
            let adjustment = f.weekday.checked_sub(weekday).ok_or_else(|| {
                crate::error_context::overflow(
                    "weekday adjustment exceeds the supported integer range",
                )
            })?;
            let date = crate::calendar::from_ordinal(ordinal + i64::from(adjustment))
                .map_err(crate::error_context::overflow)?;
            yy = i32::try_from(date[0]).map_err(|_| {
                crate::error_context::overflow("weekday adjustment exceeds the native year range")
            })?;
            mm = date[1] as i32;
            dd = date[2] as i32;
        }
    }
    let h = if f.is_hour_set() { f.hour } else { 0 };
    let m = if f.is_minute_set() { f.minute } else { 0 };
    let s = if f.is_second_set() { f.second } else { 0 };
    let us = if f.is_microsecond_set() {
        f.microsecond
    } else {
        0
    };
    Ok([yy, mm, dd, h, m, s, us])
}

fn build<'py, P: Policy>(
    py: Python<'py>,
    f: &Fields<P>,
    default: Option<&Bound<'py, PyAny>>,
    default_date: Option<[i32; 3]>,
    dtclass: Option<&Bound<'py, PyAny>>,
    ignoretz: bool,
    region: Option<&zones::RegisteredZone>,
) -> PyResult<Py<PyAny>> {
    let values = complete(f, default_date)?;
    if let Some(region) = region.filter(|_| !ignoretz) {
        return build_region(py, region, values, default, dtclass, f.strict());
    }
    let [yy, mm, dd, h, m, s, us] = values;
    let tz = if ignoretz || !f.is_tzoffset_set() {
        None
    } else {
        let offset_us = f.timezone_microseconds();
        if !(-86_400_000_000..86_400_000_000).contains(&offset_us) || offset_us == -86_400_000_000 {
            return Err(invalid_offset(py, offset_us));
        }
        if offset_us == 0 {
            // SAFETY: datetime API owns the UTC singleton for this interpreter;
            // take an owned reference while the GIL and imported API are live.
            Some(unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_TimeZone_UTC()) })
        } else {
            // SAFETY: datetime API has been imported. Constructors consume the
            // normalized delta synchronously; owned references are checked.
            let offset = unsafe {
                Bound::from_owned_ptr_or_err(
                    py,
                    ffi::PyDelta_FromDSU(0, f.tzoffset, f.tzoffset_microsecond),
                )?
            };
            Some(unsafe {
                Bound::from_owned_ptr_or_err(py, ffi::PyTimeZone_FromOffset(offset.as_ptr()))?
            })
        }
    };
    construct(
        py,
        [yy, mm, dd, h, m, s, us],
        tz,
        zones::default_fold(default),
        dtclass,
    )
}

/// Describe the completed text offset, without rerunning any parsing or callbacks.
pub(crate) fn invalid_offset(py: Python<'_>, offset_us: i64) -> PyErr {
    let magnitude = offset_us.unsigned_abs();
    let sign = if offset_us < 0 { '-' } else { '+' };
    let hours = magnitude / 3_600_000_000;
    let minutes = magnitude / 60_000_000 % 60;
    let seconds = magnitude / 1_000_000 % 60;
    let fraction = magnitude % 1_000_000;
    let clock = if fraction == 0 {
        format!("{sign}{hours:02}:{minutes:02}:{seconds:02}")
    } else {
        format!("{sign}{hours:02}:{minutes:02}:{seconds:02}.{fraction:06}")
    };
    crate::error_context::domain(
        py,
        "ParseError",
        format!(
            "UTC offset {clock} is invalid; it must be strictly between -24:00:00 and +24:00:00"
        ),
    )
}

/// Keep regional preparation out of the ordinary date constructor's frame.
#[inline(never)]
fn build_region<'py>(
    py: Python<'py>,
    region: &zones::RegisteredZone,
    values: [i32; 7],
    default: Option<&Bound<'py, PyAny>>,
    dtclass: Option<&Bound<'py, PyAny>>,
    _strict: bool,
) -> PyResult<Py<PyAny>> {
    let zone = zones::object(py, region)?;
    construct(
        py,
        values,
        Some(zone.clone()),
        zones::default_fold(default),
        dtclass,
    )
}

/// Shared final allocation and custom-constructor error contract.
#[inline(always)]
fn construct<'py>(
    py: Python<'py>,
    [yy, mm, dd, h, m, s, us]: [i32; 7],
    tz: Option<Bound<'py, PyAny>>,
    output_fold: i32,
    dtclass: Option<&Bound<'py, PyAny>>,
) -> PyResult<Py<PyAny>> {
    if let Some(cls) = dtclass.filter(|c| {
        !c.is_none()
            && !std::ptr::eq(c.as_ptr(), unsafe {
                (*ffi::PyDateTimeAPI()).DateTimeType.cast()
            })
    }) {
        let zone = tz.clone().unwrap_or_else(|| py.None().into_bound(py));
        if let Some(value) = crate::pydt::try_from_fields(
            cls,
            [yy, mm, dd, h, m, s, us].map(i64::from),
            &zone,
            output_fold,
        )? {
            return Ok(value.unbind());
        }
        let integers = [yy, mm, dd, h, m, s, us].map(|value| PyInt::new(py, value));
        let mut arguments = [std::ptr::null_mut(); 9];
        for (slot, value) in arguments.iter_mut().zip(integers.iter()) {
            *slot = value.as_ptr();
        }
        arguments[7] = tz
            .as_ref()
            .map_or(unsafe { ffi::Py_None() }, |value| value.as_ptr());
        let fold = PyInt::new(py, output_fold);
        arguments[8] = fold.as_ptr();
        let keywords = DATETIME_KEYWORDS.get(py).ok_or_else(|| {
            crate::error_context::runtime("datetime keyword names not initialized")
        })?;
        // SAFETY: the callable, keyword tuple and every argument remain owned
        // throughout this synchronous call. There are zero positional arguments
        // and nine keyword values in the official insertion order.
        let result = unsafe {
            Bound::from_owned_ptr_or_err(
                py,
                ffi::PyObject_Vectorcall(
                    cls.as_ptr(),
                    arguments.as_ptr(),
                    0,
                    keywords.bind(py).as_ptr(),
                ),
            )
        }
        .map_err(crate::error_context::external)
        .and_then(|result| {
            // The reference accepts None, but checks other constructor results.
            // SAFETY: the imported datetime predicate checks a live object.
            if !result.is_none() && unsafe { ffi::PyDateTime_Check(result.as_ptr()) } == 0 {
                Err(crate::error_context::expected_type(
                    &result,
                    "",
                    "dtclass result",
                    "a datetime or None",
                ))
            } else {
                Ok(result.unbind())
            }
        });
        return result;
    }
    // SAFETY: all integer fields are passed to CPython's checked constructor;
    // tz is owned until it returns. The imported API yields a new reference.
    unsafe {
        let api = ffi::PyDateTimeAPI()
            .as_ref()
            .ok_or_else(|| crate::error_context::fetch(py))?;
        Bound::from_owned_ptr_or_err(
            py,
            (api.DateTime_FromDateAndTimeAndFold)(
                yy,
                mm,
                dd,
                h,
                m,
                s,
                us,
                tz.as_ref().map_or(ffi::Py_None(), |t| t.as_ptr()),
                output_fold,
                api.DateTimeType,
            ),
        )
        .map(Bound::unbind)
    }
}

/// Parse date/time text into the requested datetime class.
///
/// The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
///
/// Parameters
/// ----------
/// dtstr : str
///     Date/time text to parse. This argument must be a string.
/// default : date-like input | None, default None
///     An independently complete date used to fill missing year, month and day
///     only. Date/datetime subclasses, complete date text, numeric epoch seconds
///     and NumPy datetime64 are supported. A datetime also supplies its stored
///     fold; its clock and timezone are not defaults. Pandas NaT is rejected.
///     The fallback date does not impose the output datetime's year range.
/// yearfirst : bool | None, default None
///     Prefer a year in the first position of an ambiguous numeric date. None uses
///     Configs when this parser option is optional.
/// dayfirst : bool | None, default None
///     Prefer a day before a month in an ambiguous numeric date. None uses Configs
///     when this parser option is optional.
/// ignoretz : bool, default True
///     For text, True discards recognized timezone information without changing the
///     clock. False retains the timezone. Existing datetime objects retain their
///     own timezone.
/// isoformat : bool, default True
///     Try ISO date/time forms before the general grammar. This does not restrict
///     input to ISO text.
/// strict : bool, default False
///     True rejects explicit invalid fields, conflicting repeated fields and a
///     weekday inconsistent with a full written date. False clips invalid fields
///     without carrying and allows later conflicting fields to win. A two-digit
///     year requires False and a complete default date.
/// cfg : Configs | None, default None
///     Optional Configs vocabulary and ordering rules for text. None uses the
///     library defaults.
/// dtclass : Callable[..., datetime subclass | None], optional
///     Constructor for the completed datetime fields. None selects
///     datetime.datetime. Regional existence and repeated-time policy belong to
///     this constructor; Pydt rejects missing local times.
///
/// Returns
/// -------
/// datetime subclass | None
///     The requested datetime result. A custom constructor may return None when
///     permitted by its overload.
///
/// Raises
/// ------
/// TypeError
///     An argument has an unsupported type.
/// ParseError
///     Text cannot be interpreted under the requested rules.
/// ValueError
///     A numeric scalar is NaN or a date input is missing; output constructor errors retain their original type.
/// OverflowError
///     An integer conversion or result exceeds the supported range.
// Parameter order includes the approved strict position before cfg.
#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature=(dtstr,default=None,yearfirst=None,dayfirst=None,ignoretz=Truth(true),isoformat=Truth(true),strict=Truth(false),cfg=None,dtclass=None),
text_signature="(dtstr, default=None, yearfirst=None, dayfirst=None, ignoretz=True, isoformat=True, strict=False, cfg=None, dtclass=None)")]
fn parse_str<'py>(
    py: Python<'py>,
    dtstr: &Bound<'py, PyAny>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<Truth>,
    dayfirst: Option<Truth>,
    ignoretz: Truth,
    isoformat: Truth,
    strict: Truth,
    cfg: Option<&Bound<'py, PyAny>>,
    dtclass: Option<&Bound<'py, PyAny>>,
) -> PyResult<Py<PyAny>> {
    let yearfirst = yearfirst.map(|flag| flag.0);
    let dayfirst = dayfirst.map(|flag| flag.0);
    let input =
        exact_string(dtstr).map_err(|error| entry_error(py, "parse_str", "dtstr", dtstr, error))?;
    parse_string(
        py, input, default, yearfirst, dayfirst, ignoretz, isoformat, strict, cfg, dtclass,
    )
    .map_err(|error| entry_error(py, "parse_str", "dtstr", dtstr, error))
}

// Both public bindings finish their required validation before sharing this
// typed kernel. No Python conversion callback is repeated here.
#[inline]
#[allow(clippy::too_many_arguments)]
fn parse_string<'py>(
    py: Python<'py>,
    input: &Bound<'py, PyString>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    ignoretz: Truth,
    isoformat: Truth,
    strict: Truth,
    cfg: Option<&Bound<'py, PyAny>>,
    dtclass: Option<&Bound<'py, PyAny>>,
) -> PyResult<Py<PyAny>> {
    if strict.0 {
        parse_policy::<Strict>(
            py, input, default, yearfirst, dayfirst, ignoretz, isoformat, cfg, dtclass,
        )
    } else {
        parse_policy::<Lenient>(
            py, input, default, yearfirst, dayfirst, ignoretz, isoformat, cfg, dtclass,
        )
    }
}

/// Convert text or a supported scalar date/time value into the requested datetime class.
///
/// The parser recognizes fields and forwards timezone and fold to the output constructor. It does not repair or reject missing regional times itself. A default datetime supplies fold; otherwise fold=0. Explicit invalid fields follow strict, and the chosen output type decides its representable date range.
///
/// Parameters
/// ----------
/// dtobj : str | datetime.datetime | datetime.date | int | float | np.datetime64
///     One supported date/time input: text, a Python date/datetime, numeric epoch
///     seconds, or a NumPy datetime64 scalar. NaT and unsupported containers are
///     rejected.
/// default : date-like input | None, default None
///     An independently complete date used to fill missing year, month and day
///     only. Date/datetime subclasses, complete date text, numeric epoch seconds
///     and NumPy datetime64 are supported. A datetime also supplies its stored
///     fold; its clock and timezone are not defaults. Pandas NaT is rejected.
///     The fallback date does not impose the output datetime's year range.
/// yearfirst : bool | None, default None
///     Prefer a year in the first position of an ambiguous numeric date. None uses
///     Configs when this parser option is optional.
/// dayfirst : bool | None, default None
///     Prefer a day before a month in an ambiguous numeric date. None uses Configs
///     when this parser option is optional.
/// ignoretz : bool, default True
///     For text, True discards recognized timezone information without changing the
///     clock. False retains the timezone. Existing datetime objects retain their
///     own timezone.
/// isoformat : bool, default True
///     Try ISO date/time forms before the general grammar. This does not restrict
///     input to ISO text.
/// strict : bool, default False
///     True rejects explicit invalid fields, conflicting repeated fields and a
///     weekday inconsistent with a full written date. False clips invalid fields
///     without carrying and allows later conflicting fields to win. A two-digit
///     year requires False and a complete default date.
/// cfg : Configs | None, default None
///     Optional Configs vocabulary and ordering rules for text. None uses the
///     library defaults.
/// dtclass : Callable[..., datetime subclass | None], optional
///     Constructor for the completed datetime fields. None selects
///     datetime.datetime. Regional existence and repeated-time policy belong to
///     this constructor; Pydt rejects missing local times.
///
/// Returns
/// -------
/// datetime subclass | None
///     The requested datetime result. A custom constructor may return None when
///     permitted by its overload.
///
/// Raises
/// ------
/// TypeError
///     An argument has an unsupported type.
/// ParseError
///     Text cannot be interpreted under the requested rules.
/// ValueError
///     A numeric scalar is NaN or a date input is missing; output constructor errors retain their original type.
/// OverflowError
///     An integer conversion or result exceeds the supported range.
#[allow(clippy::too_many_arguments)]
#[pyfunction]
#[pyo3(signature=(dtobj,default=None,yearfirst=None,dayfirst=None,ignoretz=Truth(true),isoformat=Truth(true),strict=Truth(false),cfg=None,dtclass=None),
text_signature="(dtobj, default=None, yearfirst=None, dayfirst=None, ignoretz=True, isoformat=True, strict=False, cfg=None, dtclass=None)")]
fn parse<'py>(
    py: Python<'py>,
    dtobj: &Bound<'py, PyAny>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<Truth>,
    dayfirst: Option<Truth>,
    ignoretz: Truth,
    isoformat: Truth,
    strict: Truth,
    cfg: Option<&Bound<'py, PyAny>>,
    dtclass: Option<&Bound<'py, PyAny>>,
) -> PyResult<Py<PyAny>> {
    let yearfirst = yearfirst.map(|flag| flag.0);
    let dayfirst = dayfirst.map(|flag| flag.0);
    // Unlike parse_str, the object entrance checks cfg before dispatching.
    if let Some(value) = cfg.filter(|c| !c.is_none()) {
        value.cast::<Configs>().map_err(|_| {
            crate::error_context::expected_type(value, "parse", "cfg", "a Configs instance or None")
        })?;
    }
    if let Ok(input) = dtobj.cast_exact::<PyString>() {
        return parse_string(
            py, input, default, yearfirst, dayfirst, ignoretz, isoformat, strict, cfg, dtclass,
        )
        .map_err(|error| entry_error(py, "parse", "dtobj", dtobj, error));
    }
    if dtobj.is_instance_of::<PyString>() {
        let converted = dtobj
            .str()
            .map_err(crate::error_context::external)
            .map_err(|error| entry_error(py, "parse", "dtobj", dtobj, error))?;
        let input = exact_string(converted.as_any())
            .map_err(|error| entry_error(py, "parse", "dtobj", dtobj, error))?;
        return parse_string(
            py, input, default, yearfirst, dayfirst, ignoretz, isoformat, strict, cfg, dtclass,
        )
        .map_err(|error| entry_error(py, "parse", "dtobj", dtobj, error));
    }
    objects::convert(py, dtobj, dtclass)
        .map_err(|error| entry_error(py, "parse", "dtobj", dtobj, error))
}

fn exact_string<'a, 'py>(dtstr: &'a Bound<'py, PyAny>) -> PyResult<&'a Bound<'py, PyString>> {
    dtstr.cast_exact::<PyString>().map_err(|_| {
        crate::error_context::expected_type(dtstr, "parse_str", "dtstr", "an exact str")
    })
}

// Each policy has concrete native storage. The ordinary path contains neither
// duplicate-field bookkeeping nor a history container to release.
#[allow(clippy::too_many_arguments)]
fn parse_policy<'py, P: Policy>(
    py: Python<'py>,
    input: &Bound<'py, PyString>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    ignoretz: Truth,
    isoformat: Truth,
    cfg: Option<&Bound<'py, PyAny>>,
    dtclass: Option<&Bound<'py, PyAny>>,
) -> PyResult<Py<PyAny>> {
    let fields = read_fields::<P>(
        py,
        input,
        default,
        yearfirst,
        dayfirst,
        ignoretz.0,
        isoformat.0,
        cfg,
    )?;
    build(
        py,
        &fields.fields,
        default,
        fields.default_date,
        dtclass,
        ignoretz.0,
        fields.region.as_deref(),
    )
}

/// Finish a public parse while retaining an explicit native no-match result internally.
#[inline(always)]
#[allow(clippy::too_many_arguments)]
pub(crate) fn read_fields<'py, P: Policy>(
    py: Python<'py>,
    input: &Bound<'py, PyString>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    ignoretz: bool,
    isoformat: bool,
    cfg: Option<&Bound<'py, PyAny>>,
) -> PyResult<ParsedFields<P>> {
    read_fields_candidate::<P>(
        py, input, default, yearfirst, dayfirst, ignoretz, isoformat, cfg,
    )?
    .ok_or_else(|| {
        crate::error_context::domain(
            py,
            "ParseError",
            "no date/time fields could be read; provide a recognizable date or time".to_owned(),
        )
    })
}

/// String subtraction may negotiate only a genuine native no-match.
/// Conversion hooks and real field, timezone or overflow failures still propagate.
pub(crate) fn arithmetic_date<'py>(operand: &Bound<'py, PyAny>) -> PyResult<Option<Py<PyAny>>> {
    let py = operand.py();
    let converted;
    let text = if operand.is_exact_instance_of::<PyString>() {
        operand.cast::<PyString>()?
    } else {
        converted = operand.str().map_err(crate::error_context::external)?;
        &converted
    };
    let Some(parsed) =
        read_fields_candidate::<Lenient>(py, text, None, None, None, false, true, None)?
    else {
        return Ok(None);
    };
    if !(parsed.is_year_set() && parsed.is_month_set() && parsed.is_day_set()) {
        return Ok(None);
    }
    build(
        py,
        &parsed.fields,
        None,
        None,
        None,
        false,
        parsed.region.as_deref(),
    )
    .map(Some)
}

/// Shared native scanner/resolver used by datetime and epoch result builders.
#[inline(always)]
#[allow(clippy::too_many_arguments)]
fn read_fields_candidate<'py, P: Policy>(
    py: Python<'py>,
    input: &Bound<'py, PyString>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    ignoretz: bool,
    isoformat: bool,
    cfg: Option<&Bound<'py, PyAny>>,
) -> PyResult<Option<ParsedFields<P>>> {
    let default_date = prepare_default(py, default, yearfirst, dayfirst, isoformat, cfg, P::STRICT)
        .map_err(|error| match default {
            Some(value) => entry_error(py, "", "default", value, error),
            None => error,
        })?;
    scan_prepared::<P>(
        py,
        input,
        default_date,
        yearfirst,
        dayfirst,
        ignoretz,
        isoformat,
        cfg,
    )
}

/// Read a batch text element after its independent default was prepared once.
#[allow(clippy::too_many_arguments)]
pub(crate) fn read_fields_prepared<'py, P: Policy>(
    py: Python<'py>,
    input: &Bound<'py, PyString>,
    default_date: Option<[i32; 3]>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    ignoretz: bool,
    isoformat: bool,
    cfg: Option<&Bound<'py, PyAny>>,
) -> PyResult<ParsedFields<P>> {
    scan_prepared::<P>(
        py,
        input,
        default_date,
        yearfirst,
        dayfirst,
        ignoretz,
        isoformat,
        cfg,
    )?
    .ok_or_else(|| {
        crate::error_context::domain(
            py,
            "ParseError",
            "no date/time fields could be read; provide a recognizable date or time".to_owned(),
        )
    })
}

/// Shared scan/resolution body; no result object or default conversion is made here.
#[inline(always)]
#[allow(clippy::too_many_arguments)]
fn scan_prepared<'py, P: Policy>(
    py: Python<'py>,
    input: &Bound<'py, PyString>,
    default_date: Option<[i32; 3]>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    ignoretz: bool,
    isoformat: bool,
    cfg: Option<&Bound<'py, PyAny>>,
) -> PyResult<Option<ParsedFields<P>>> {
    let configuration = match cfg.filter(|c| !c.is_none()) {
        Some(value) => Some(value.cast::<Configs>().map_err(|_| {
            crate::error_context::expected_type(value, "", "cfg", "a Configs instance or None")
        })?),
        None => None,
    };
    let mut view = TextView::new(input)?;
    let mut fields = Fields::<P>::new();
    let mut region = None;
    let result = match scan::prefix(&view, &mut fields, ignoretz, isoformat) {
        Err(error) => Err(native_error(error)),
        Ok((start, _)) if start == view.len() => Ok(()),
        Ok(_) if P::ISO_ONLY => Err(native_error(ParseError::Value(
            "expected a complete ISO date/time string".to_owned(),
        ))),
        Ok((start, _)) => {
            let configured = configuration.is_some_and(|cfg| cfg.borrow().has_zones());
            let mut tokens = if configured {
                None
            } else {
                Some(text::tokenize(&view, start))
            };
            if configured || tokens.as_ref().is_some_and(|t| t.region_candidate) {
                region = zones::suffix(py, &mut view, configuration, ignoretz, fields.strict())
                    .map_err(|error| {
                        failed(
                            py,
                            PyString::new(py, "Cannot resolve registered time zone.").into_any(),
                            Some(error),
                        )
                    })?;
                tokens = Some(text::tokenize(&view, start));
            }
            let tokens =
                tokens.ok_or_else(|| crate::error_context::runtime("missing parser token view"))?;
            if let Some(configuration) = configuration {
                let native_config = configuration.borrow();
                let mut lookup = native_config.native_view();
                scan::process_tokens(
                    &tokens,
                    &mut fields,
                    &mut lookup,
                    ignoretz || region.is_some(),
                    default_date.map(|date| date[0]),
                )
                .map_err(native_error)
            } else {
                let mut lookup = config::DefaultView;
                scan::process_tokens(
                    &tokens,
                    &mut fields,
                    &mut lookup,
                    ignoretz || region.is_some(),
                    default_date.map(|date| date[0]),
                )
                .map_err(native_error)
            }
        }
    };
    result?;
    // Defaults are immutable Rust rules, so the ordinary path needs no Python
    // Configs borrow. Read explicit settings at their original expression:
    // Resolve explicit flags before reading the effective ordering preferences.
    // Configs is sealed and these two flags are native booleans. Take their
    // shared snapshot once after scanning, without repeating a Python borrow.
    let (configured_year, configured_day) = if yearfirst.is_none() || dayfirst.is_none() {
        configuration.map_or((true, false), |c| c.borrow().flags())
    } else {
        (true, false)
    };
    let year = yearfirst.unwrap_or(configured_year);
    let day = dayfirst.unwrap_or(configured_day);
    let reference_year = if fields.idx >= 0 && !fields.century_specified && !fields.strict() {
        default_date.map(|date| date[0])
    } else {
        None
    };
    let resolved = if fields.resolved {
        true
    } else {
        resolve::resolve(&mut fields, year, day, reference_year).map_err(|error| {
            failed(
                py,
                PyString::new(py, "Cannot resolve calendar fields.").into_any(),
                Some(native_error(error)),
            )
        })?
    };
    if !resolved {
        return Ok(None);
    }
    Ok(Some(ParsedFields {
        fields,
        region,
        default_date,
    }))
}

/// Prepare a standalone fallback once, retaining native calendar fields only.
/// Only the caller's original datetime may supply fold at the zone boundary.
#[inline]
#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_default(
    py: Python<'_>,
    default: Option<&Bound<'_, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    cfg: Option<&Bound<'_, PyAny>>,
    strict: bool,
) -> PyResult<Option<[i32; 3]>> {
    let Some(value) = default.filter(|value| !value.is_none()) else {
        return Ok(None);
    };
    let native_date = is_date_default(value);
    if native_date {
        // SAFETY: the native date predicate proves the stored field layout.
        let year = unsafe { ffi::PyDateTime_GET_YEAR(value.as_ptr()) };
        if !crate::interop::needs_true_year(year) {
            return Ok(Some(unsafe {
                [
                    year,
                    ffi::PyDateTime_GET_MONTH(value.as_ptr()),
                    ffi::PyDateTime_GET_DAY(value.as_ptr()),
                ]
            }));
        }
    }
    prepare_other_default(
        py,
        value,
        native_date,
        yearfirst,
        dayfirst,
        isoformat,
        cfg,
        strict,
    )
}

/// Convert nontrivial defaults outside the ordinary date/default scan frame.
///
/// # Errors
/// Preserves missing-value, capacity, configuration and real conversion errors.
#[inline(never)]
#[allow(clippy::too_many_arguments)]
fn prepare_other_default(
    py: Python<'_>,
    value: &Bound<'_, PyAny>,
    native_date: bool,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    cfg: Option<&Bound<'_, PyAny>>,
    strict: bool,
) -> PyResult<Option<[i32; 3]>> {
    if native_date {
        // SAFETY: is_date_default already proved the native date layout.
        if crate::interop::needs_true_year(unsafe { ffi::PyDateTime_GET_YEAR(value.as_ptr()) }) {
            crate::interop::reject_nat(value, "parse", "default")?;
            if let Some((fields, _)) = crate::interop::timestamp_parts(value)? {
                return fields[..3]
                    .iter()
                    .map(|n| {
                        i32::try_from(*n).map_err(|_| {
                            crate::error_context::overflow(
                                "default year exceeds the parser integer range",
                            )
                        })
                    })
                    .collect::<PyResult<Vec<_>>>()
                    .map(|n| Some([n[0], n[1], n[2]]));
            }
        }
        // SAFETY: the checked native date layout owns these fields.
        return Ok(Some(unsafe {
            [
                ffi::PyDateTime_GET_YEAR(value.as_ptr()),
                ffi::PyDateTime_GET_MONTH(value.as_ptr()),
                ffi::PyDateTime_GET_DAY(value.as_ptr()),
            ]
        }));
    }
    if crate::numeric::is_bool(value) {
        return Err(crate::error_context::type_error(
            "default must be a complete date, not a boolean value",
        ));
    }
    if value.is_instance_of::<pyo3::types::PyFloat>() {
        // Numeric defaults keep the established microsecond date role; data
        // epochs may now preserve finer precision without changing this role.
        let fields = objects::wide_microsecond_fields(objects::seconds_to_wide_us(
            value.extract::<f64>()?,
        )?)?;
        let year = i32::try_from(fields[0]).map_err(|_| {
            crate::error_context::overflow("default year exceeds the parser integer range")
        })?;
        return Ok(Some([year, fields[1] as i32, fields[2] as i32]));
    }
    if value.is_instance_of::<PyString>()
        || unsafe {
            ffi::PyLong_Check(value.as_ptr()) != 0 || ffi::PyFloat_Check(value.as_ptr()) != 0
        }
    {
        let options = crate::epoch::Options {
            default: None,
            yearfirst,
            dayfirst,
            ignoretz: true,
            isoformat,
            strict,
            iso_only: false,
            cfg,
            input_unit: crate::epoch::Unit::Second,
        };
        let parsed = crate::epoch::read(value, &options)?;
        let ordinal = parsed.nanos.div_euclid(86_400_000_000_000) + 719_163;
        return crate::calendar::from_ordinal(i64::try_from(ordinal).map_err(|_| {
            crate::error_context::overflow("default day exceeds the calendar range")
        })?)
        .and_then(|date| {
            let [year, month, day] = date;
            let year =
                i32::try_from(year).map_err(|_| "default year exceeds the parser integer range")?;
            Ok(Some([year, month as i32, day as i32]))
        })
        .map_err(crate::error_context::overflow);
    }
    if let Some(parsed) = crate::epoch::read_numpy(value)? {
        let fields = objects::wide_microsecond_fields(parsed.nanos.div_euclid(1000))?;
        let year = i32::try_from(fields[0]).map_err(|_| {
            crate::error_context::overflow("default year exceeds the parser integer range")
        })?;
        return Ok(Some([year, fields[1] as i32, fields[2] as i32]));
    }
    let _ = py;
    Err(crate::error_context::type_error(
        "default must independently provide a complete date: use date, datetime, a complete date string, epoch seconds or numpy.datetime64",
    ))
}

/// Register the public parser functions and initialize immutable defaults.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    // SAFETY: import initializes the per-interpreter datetime C API while the
    // GIL is held. All subsequent date reads and constructors require it.
    unsafe {
        ffi::PyDateTime_IMPORT();
    }
    let keywords = PyTuple::new(
        py,
        [
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
            "microsecond",
            "tzinfo",
            "fold",
        ],
    )?;
    let _ = DATETIME_KEYWORDS.set(py, keywords.unbind());
    config::configure(module)?;
    formatted::configure(module)?;
    let configuration_type = py.get_type::<Configs>();
    // SAFETY: registration has completed while the GIL is held. The sealed
    // configuration type has a stable layout and its descriptors stay fixed.
    unsafe {
        (*configuration_type.as_type_ptr()).tp_flags |= ffi::Py_TPFLAGS_IMMUTABLETYPE;
    }

    module.add_function(wrap_pyfunction!(parse_str, module)?)?;
    module
        .getattr("parse_str")
        .map_err(crate::error_context::external)?
        .setattr("__module__", "rstimes.parser")?;
    module.add_function(wrap_pyfunction!(parse, module)?)?;
    module
        .getattr("parse")
        .map_err(crate::error_context::external)?
        .setattr("__module__", "rstimes.parser")?;
    Ok(())
}

#[cfg(test)]
mod internal_rules_tests {
    use super::{config, fields::Rule};

    #[test]
    fn library_module_can_read_defaults_without_python_objects() {
        for (rule, text, value) in [
            (Rule::Jump, "at", 1),
            (Rule::Pertain, "of", 1),
            (Rule::Utc, "UTC", 1),
            (Rule::Tz, "unregistered", -100_000),
            (Rule::Month, "October", 10),
            (Rule::Weekday, "Monday", 0),
            (Rule::Hms, "h", 0),
            (Rule::HmsContains, "h", 1),
            (Rule::Ampm, "pm", 1),
            (Rule::Month, "février", 2),
            (Rule::Month, "unknown", -1),
        ] {
            let token: Vec<u32> = text.chars().map(u32::from).collect();
            assert_eq!(config::default_lookup(rule, &token), value);
        }
    }
}
