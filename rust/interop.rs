//! Boundary between checked Rust calendar work and Python date objects.
//!
//! Builtin date/datetime paths preserve timezone, fold and no-change identity.
//! Custom constructors run only after the native field snapshot is complete.
//! Dateutil type caches are interpreter-aware, and conversion errors propagate.

use pyo3::exceptions::{PyException, PyOverflowError, PyValueError};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{
    PyDate, PyDateAccess, PyDateTime, PyDelta, PyDict, PyString, PyTimeAccess, PyTuple,
    PyTzInfoAccess,
};

static DATE_KEYS: PyOnceLock<[Py<PyString>; 10]> = PyOnceLock::new();

/// Share fixed keyword names while preserving constructor and attribute callback order.
fn date_keys(py: Python<'_>) -> &[Py<PyString>; 10] {
    DATE_KEYS.get_or_init(py, || {
        let names = [
            "__class__",
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
            "microsecond",
            "tzinfo",
            "fold",
        ];
        std::array::from_fn(|index| PyString::intern(py, names[index]).unbind())
    })
}

/// Apply Delta to a Python date/datetime while preserving its result type.
///
/// # Arguments
/// sign selects addition (1) or subtraction (-1). other may be a builtin or a
/// subclass; non-date inputs return None so arithmetic dispatch can continue.
///
/// # Returns
/// Some(result), preserving datetime tzinfo and fold. An empty or unchanged
/// operation may return the original object.
///
/// # Errors
/// Propagates overflow and builtin constructor range errors. A failing custom
/// date/datetime constructor is wrapped in ValueError with its original cause.
#[inline]
pub fn apply_date<'py>(
    delta: &crate::delta::Delta,
    other: &Bound<'py, PyAny>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let dt = other.cast::<PyDateTime>().ok();
    let date = if dt.is_none() {
        other.cast::<PyDate>().ok()
    } else {
        None
    };
    if dt.is_none() && date.is_none() {
        return Ok(None);
    }
    if let Some(date) = date {
        return apply_date_only(delta, other, date, sign);
    }
    let Some(dt) = dt else {
        return Ok(None);
    };
    apply_datetime(delta, other, dt, sign)
}

/// Compute a builtin starting value's exact wall-clock span without a date object.
///
/// # Preconditions
/// The caller accepts only the exact immutable Delta type. Subclass operands
/// return None so their addition, construction and subtraction callbacks remain
/// on the ordinary Python path. Calendar work uses the same checked kernel.
/// # Errors
/// Propagates calendar overflow. Out-of-range final years return None so the
/// ordinary constructor supplies its original exception and message.
pub(crate) fn builtin_span<'py>(
    delta: &crate::delta::Delta,
    start: &Bound<'py, PyAny>,
) -> PyResult<Option<Bound<'py, PyDelta>>> {
    let (input, datetime) = if start.is_exact_instance_of::<PyDateTime>() {
        let dt = start.cast::<PyDateTime>()?;
        (
            [
                i64::from(dt.get_year()),
                i64::from(dt.get_month()),
                i64::from(dt.get_day()),
                i64::from(dt.get_hour()),
                i64::from(dt.get_minute()),
                i64::from(dt.get_second()),
                i64::from(dt.get_microsecond()),
            ],
            true,
        )
    } else if start.is_exact_instance_of::<PyDate>() {
        let date = start.cast::<PyDate>()?;
        (
            [
                i64::from(date.get_year()),
                i64::from(date.get_month()),
                i64::from(date.get_day()),
                0,
                0,
                0,
                0,
            ],
            false,
        )
    } else {
        return Ok(None);
    };
    let (result, _) =
        crate::calendar::apply(&delta.calendar_snapshot(datetime), input, 1, datetime)
            .map_err(PyOverflowError::new_err)?;
    if !(1..=9999).contains(&result[0]) {
        return Ok(None);
    }
    let days = if result[..3] == input[..3] {
        0
    } else {
        crate::calendar::ordinal(result[0], result[1], result[2])
            - crate::calendar::ordinal(input[0], input[1], input[2])
    };
    // The ordinary result retains the starting tzinfo object. Python subtracts
    // equal-tzinfo datetimes by wall time, without offset or fold adjustments.
    // Valid builtin years bound days to ±3652058; canonical clock differences
    // bound seconds to ±86399 and microseconds to ±999999, so narrowing is exact.
    let seconds =
        (result[3] - input[3]) * 3600 + (result[4] - input[4]) * 60 + result[5] - input[5];
    PyDelta::new(
        start.py(),
        days as i32,
        seconds as i32,
        (result[6] - input[6]) as i32,
        true,
    )
    .map(Some)
}

/// Apply Delta to a checked datetime while retaining timezone, fold and identity.
///
/// # Errors
/// Propagates checked calendar/constructor errors and custom constructor failures.
#[inline(always)]
pub(crate) fn apply_datetime<'py>(
    delta: &crate::delta::Delta,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    if !delta.__bool__() || delta.preserves_datetime_clock(dt) {
        return Ok(Some(other.clone()));
    }
    apply_datetime_fields(&delta.calendar_snapshot(true), false, other, dt, sign)
}

/// Apply an already captured Delta value through the same checked date kernel.
///
/// # Preconditions
/// fields is the immutable canonical snapshot; empty is its derived truth flag.
/// # Errors
/// Preserves all original arithmetic, subtype and constructor errors.
#[inline(always)]
pub(crate) fn apply_datetime_fields<'py>(
    fields: &[i64; 15],
    empty: bool,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    // The public vector call preserves the same keyword order and callbacks,
    // while avoiding a temporary keyword dictionary for datetime subclasses.
    apply_datetime_fields_impl::<true>(fields, empty, other, dt, sign)
}

/// Apply prepared datetime fields using public keyword vectorcall for subtypes.
/// # Errors
/// Preserves date, custom constructor and allocation failures.
pub(crate) fn apply_datetime_fields_vector<'py>(
    fields: &[i64; 15],
    empty: bool,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    apply_datetime_fields_impl::<true>(fields, empty, other, dt, sign)
}

/// Run the same checked calendar work with a fixed constructor calling convention.
/// # Errors
/// Preserves normalization, boundaries and custom constructor exception handling.
#[inline(always)]
fn apply_datetime_fields_impl<'py, const VECTOR: bool>(
    fields: &[i64; 15],
    empty: bool,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = other.py();
    if empty {
        return Ok(Some(other.clone()));
    }
    let parts = [
        i64::from(dt.get_year()),
        i64::from(dt.get_month()),
        i64::from(dt.get_day()),
        i64::from(dt.get_hour()),
        i64::from(dt.get_minute()),
        i64::from(dt.get_second()),
        i64::from(dt.get_microsecond()),
    ];
    // Finish calendar work before any Python constructor callback.
    let (result, unchanged) =
        crate::calendar::apply(fields, parts, sign, true).map_err(PyOverflowError::new_err)?;
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let [year, month, day, hour, minute, second, microsecond] = result;
    let year = i32::try_from(year)
        .map_err(|_| PyOverflowError::new_err("integer overflow in Delta date arithmetic"))?;
    if other.is_exact_instance_of::<PyDateTime>() {
        // The checked datetime receiver initialized this SDK capsule. Its tzinfo
        // is borrowed from the live input; the public constructor retains it in
        // the new object. Avoid a temporary owned Python reference on this path.
        if let Some(api) = unsafe { ffi::PyDateTimeAPI().as_ref() } {
            // SAFETY: dt is a live checked datetime under the GIL; calendar parts
            // are normalized, year was checked, and the SDK validates date bounds.
            // It returns a new reference or NULL with a Python exception set.
            let result = unsafe {
                (api.DateTime_FromDateAndTimeAndFold)(
                    year,
                    month as i32,
                    day as i32,
                    hour as i32,
                    minute as i32,
                    second as i32,
                    microsecond as i32,
                    ffi::PyDateTime_DATE_GET_TZINFO(dt.as_ptr()),
                    i32::from(dt.get_fold()),
                    api.DateTimeType,
                )
            };
            return unsafe { Bound::from_owned_ptr_or_err(py, result) }.map(Some);
        }
        let tz = dt.get_tzinfo();
        return PyDateTime::new_with_fold(
            py,
            year,
            month as u8,
            day as u8,
            hour as u8,
            minute as u8,
            second as u8,
            microsecond as u32,
            tz.as_ref(),
            dt.get_fold(),
        )
        .map(|value| Some(value.into_any()));
    }
    construct_subclass::<VECTOR>(
        other,
        Some(dt),
        [
            i64::from(year),
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
        ],
    )
}

// Keep the pure-date calendar form visible to the optimizer without forcing
// the complete datetime/subclass routine into every arithmetic caller.
/// Apply the date-only calendar form without building datetime state.
///
/// # Errors
/// Propagates arithmetic overflow and constructor errors as in apply_date.
#[inline(always)]
pub(crate) fn apply_date_only<'py>(
    delta: &crate::delta::Delta,
    other: &Bound<'py, PyAny>,
    date: &Bound<'py, PyDate>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    if !delta.__bool__() {
        return Ok(Some(other.clone()));
    }
    apply_date_only_fields(&delta.calendar_snapshot(false), false, other, date, sign)
}

/// Apply an already captured Delta value through the same checked date kernel.
///
/// # Preconditions
/// fields is the immutable canonical snapshot; empty is its derived truth flag.
/// # Errors
/// Preserves all original arithmetic, subtype and constructor errors.
#[inline]
pub(crate) fn apply_date_only_fields<'py>(
    fields: &[i64; 15],
    empty: bool,
    other: &Bound<'py, PyAny>,
    date: &Bound<'py, PyDate>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    if empty {
        return Ok(Some(other.clone()));
    }
    let parts = [
        i64::from(date.get_year()),
        i64::from(date.get_month()),
        i64::from(date.get_day()),
        0,
        0,
        0,
        0,
    ];
    let (result, unchanged) =
        crate::calendar::apply(fields, parts, sign, false).map_err(PyOverflowError::new_err)?;
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let year = i32::try_from(result[0])
        .map_err(|_| PyOverflowError::new_err("integer overflow in Delta date arithmetic"))?;
    if other.is_exact_instance_of::<PyDate>() {
        if let Some(api) = unsafe { ffi::PyDateTimeAPI().as_ref() } {
            // SAFETY: the GIL is held and the SDK owns its ready date type. The
            // checked calendar result supplies normalized month/day values; the
            // public constructor checks Python's final bounds and owns its result.
            let result = unsafe {
                (api.Date_FromDate)(year, result[1] as i32, result[2] as i32, api.DateType)
            };
            return unsafe { Bound::from_owned_ptr_or_err(other.py(), result) }.map(Some);
        }
        return PyDate::new(other.py(), year, result[1] as u8, result[2] as u8)
            .map(|value| Some(value.into_any()));
    }
    construct_subclass::<false>(other, None, result)
}

// Ordinary builtins do not need a keyword dictionary or Python callback.
// Keep this less common constructor/error path out of their call frame.
/// Construct the input's runtime date class with computed keyword arguments.
///
/// # Errors
/// Wraps custom constructor Exception failures in ValueError with a cause;
/// BaseException subclasses and earlier attribute failures propagate unchanged.
#[cold]
#[inline(never)]
fn construct_subclass<'py, const VECTOR: bool>(
    other: &Bound<'py, PyAny>,
    dt: Option<&Bound<'py, PyDateTime>>,
    result: [i64; 7],
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = other.py();
    let datetime = dt.is_some();
    let [year, month, day, hour, minute, second, microsecond] = result;
    let keys = date_keys(py);
    let class = other.getattr(keys[0].bind(py))?;
    let called = if VECTOR {
        static KEYWORDS: PyOnceLock<Py<PyTuple>> = PyOnceLock::new();
        let names = KEYWORDS.get_or_try_init(py, || -> PyResult<_> {
            Ok(PyTuple::new(py, keys[1..].iter().map(|key| key.bind(py)))?.unbind())
        })?;
        let Some(dt) = dt else {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Datetime vector constructor has no datetime",
            ));
        };
        let args = [
            year.into_pyobject(py)?.into_any(),
            month.into_pyobject(py)?.into_any(),
            day.into_pyobject(py)?.into_any(),
            hour.into_pyobject(py)?.into_any(),
            minute.into_pyobject(py)?.into_any(),
            second.into_pyobject(py)?.into_any(),
            microsecond.into_pyobject(py)?.into_any(),
            dt.get_tzinfo()
                .map_or_else(|| py.None().into_bound(py), Bound::into_any),
            i32::from(dt.get_fold()).into_pyobject(py)?.into_any(),
        ];
        let pointers = args.each_ref().map(Bound::as_ptr);
        // SAFETY: All keyword values, names and the live callable are owned for
        // this public call. There are zero positional values and nine named
        // datetime values; the API never steals their references.
        unsafe {
            Bound::from_owned_ptr_or_err(
                py,
                ffi::PyObject_Vectorcall(
                    class.as_ptr(),
                    pointers.as_ptr(),
                    0,
                    names.bind(py).as_ptr(),
                ),
            )
        }
    } else {
        let kwargs = PyDict::new(py);
        for (index, value) in [year, month, day].into_iter().enumerate() {
            kwargs.set_item(keys[index + 1].bind(py), value)?;
        }
        if let Some(dt) = dt {
            for (index, value) in [hour, minute, second, microsecond].into_iter().enumerate() {
                kwargs.set_item(keys[index + 4].bind(py), value)?;
            }
            kwargs.set_item(keys[8].bind(py), dt.get_tzinfo())?;
            kwargs.set_item(keys[9].bind(py), i32::from(dt.get_fold()))?;
        }
        class.call((), Some(&kwargs))
    };
    match called {
        Ok(value) => Ok(Some(value)),
        Err(error) if error.is_instance_of::<PyException>(py) => {
            let kind = if datetime { "datetime" } else { "date" };
            let argument = if datetime { "dtclass" } else { "dclass" };
            let wrapped = PyValueError::new_err(format!(
                "Cannot create {kind} using custom '{argument}' {}, {}",
                class.str()?.to_str()?,
                error.value(py).str()?.to_str()?
            ));
            wrapped.set_cause(py, Some(error));
            Err(wrapped)
        }
        Err(error) => Err(error),
    }
}

use pyo3::sync::PyOnceLock;
use pyo3::types::PyType;
static RELATIVEDELTA: PyOnceLock<Py<PyType>> = PyOnceLock::new();

/// Check dateutil.relativedelta membership using an interpreter-aware type cache.
///
/// # Errors
/// Propagates import, attribute access and Python instance-check errors.
pub fn is_relativedelta(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    let py = value.py();
    let class = RELATIVEDELTA.get_or_try_init(py, || -> PyResult<_> {
        Ok(py
            .import("dateutil.relativedelta")?
            .getattr("relativedelta")?
            .cast_into::<PyType>()?
            .unbind())
    })?;
    value.is_instance(class.bind(py))
}

/// Return the already initialized dateutil type without imports or callbacks.
pub(crate) fn exact_relative_type(py: Python<'_>) -> Option<*mut ffi::PyTypeObject> {
    RELATIVEDELTA
        .get(py)
        .map(|class| class.bind(py).as_type_ptr())
}

/// Read normalized fields only when the live object is the exact cached dateutil type.
///
/// The cache must already be initialized; a missing cache or any subclass/fake
/// class returns None so the original membership/callback path remains active.
/// # Errors
/// Preserves normalized(), attribute and checked conversion failures.
#[inline]
pub(crate) fn exact_relative_fields(value: &Bound<'_, PyAny>) -> PyResult<Option<[i64; 15]>> {
    let py = value.py();
    if let Some(class) = RELATIVEDELTA.get(py) {
        // SAFETY: Both type identities are live and owned while attached.
        // Only an actual exact type can qualify; no foreign payload is cast.
        if unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) } == class.bind(py).as_type_ptr() {
            return read_relative_fields(value).map(Some);
        }
    }
    Ok(None)
}

/// Own the fixed attribute names once for a batch, without reading foreign data.
pub(crate) fn relative_keys(py: Python<'_>) -> [Py<PyString>; 17] {
    [
        "normalized",
        "years",
        "months",
        "days",
        "hours",
        "minutes",
        "seconds",
        "microseconds",
        "year",
        "month",
        "day",
        "weekday",
        "hour",
        "minute",
        "second",
        "microsecond",
        "leapdays",
    ]
    .map(|name| PyString::intern(py, name).unbind())
}

/// Read current normalized attributes using the batch's owned fixed names.
/// # Errors
/// Preserves all normalized(), attribute, conversion and unsupported-rule failures.
pub(crate) fn relative_fields_named(
    value: &Bound<'_, PyAny>,
    keys: &[Py<PyString>; 17],
) -> PyResult<[i64; 15]> {
    let py = value.py();
    let normalized = value.call_method0(keys[0].bind(py))?;
    let names = std::array::from_fn(|index| keys[index + 1].bind(py));
    read_normalized_fields(&normalized, names, keys[16].bind(py))
}

/// Read normalized dateutil fields into Delta's 15-field internal order.
///
/// Absent absolute fields become -1. A weekday object's weekday value is used;
/// its occurrence count is not a separate Delta field.
///
/// # Errors
/// Raises rstimes.errors.InvalidRelativeDelta for an unsupported input type.
/// Propagates normalized(), attribute access and checked integer conversion errors.
pub fn relativedelta_fields(value: &Bound<'_, PyAny>) -> PyResult<[i64; 15]> {
    let py = value.py();
    if !is_relativedelta(value)? {
        let error = py
            .import("rstimes.errors")?
            .getattr("InvalidRelativeDelta")?;
        let message = format!(
            "<'Delta'> Invalid 'from_relativedelta(rd)' input.\nExpects an instance of 'dateutil.relativedelta', instead got {}.",
            value.get_type().str()?.to_str()?
        );
        return Err(PyErr::from_value(error.call1((message,))?));
    }
    read_relative_fields(value)
}

/// Read the same ordered attributes after actual or Python membership is established.
///
/// # Errors
/// Propagates normalized(), attribute and integer conversion errors unchanged.
#[inline]
fn read_relative_fields(value: &Bound<'_, PyAny>) -> PyResult<[i64; 15]> {
    let py = value.py();
    let normalized = value.call_method0(pyo3::intern!(py, "normalized"))?;
    // Each literal has its own interpreter-aware cache. A dynamic loop value
    // cannot share one intern! call site without caching the wrong name.
    let names = [
        pyo3::intern!(py, "years"),
        pyo3::intern!(py, "months"),
        pyo3::intern!(py, "days"),
        pyo3::intern!(py, "hours"),
        pyo3::intern!(py, "minutes"),
        pyo3::intern!(py, "seconds"),
        pyo3::intern!(py, "microseconds"),
        pyo3::intern!(py, "year"),
        pyo3::intern!(py, "month"),
        pyo3::intern!(py, "day"),
        pyo3::intern!(py, "weekday"),
        pyo3::intern!(py, "hour"),
        pyo3::intern!(py, "minute"),
        pyo3::intern!(py, "second"),
        pyo3::intern!(py, "microsecond"),
    ];
    read_normalized_fields(&normalized, names, pyo3::intern!(py, "leapdays"))
}

/// Read the ordered attributes of an owned normalized result with fixed names.
/// # Errors
/// Preserves attribute access, checked conversion and unsupported-rule failures.
#[inline(always)]
fn read_normalized_fields(
    normalized: &Bound<'_, PyAny>,
    names: [&Bound<'_, PyString>; 15],
    leapdays: &Bound<'_, PyString>,
) -> PyResult<[i64; 15]> {
    let mut fields = [0; 15];
    for (index, name) in names.into_iter().enumerate() {
        let item = normalized.getattr(name)?;
        if index >= 7 && item.is_none() {
            fields[index] = -1;
            continue;
        }
        if index == 10 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "relativedelta weekday rules cannot be represented by Delta",
            ));
        }
        fields[index] = crate::delta::input_integer(&item)?;
    }
    if normalized.getattr(leapdays)?.is_truthy()? {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "relativedelta leapdays rules cannot be represented by Delta",
        ));
    }
    Ok(fields)
}
