//! Boundary between checked Rust calendar work and Python date objects.
//!
//! Builtin date/datetime paths preserve timezone, fold and no-change identity.
//! Custom constructors run only after the native field snapshot is complete.
//! Dateutil type caches are interpreter-aware, and conversion errors propagate.

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{
    PyDate, PyDateAccess, PyDateTime, PyDelta, PyDeltaAccess, PyDict, PyFloat, PyString,
    PyTimeAccess, PyTuple, PyTzInfoAccess,
};

static DATE_KEYS: PyOnceLock<[Py<PyString>; 9]> = PyOnceLock::new();
static RELATIVE_KEYS: PyOnceLock<[Py<PyString>; 16]> = PyOnceLock::new();
static PANDAS_TIMESTAMP: PyOnceLock<Py<PyType>> = PyOnceLock::new();
static PANDAS_TIMEDELTA: PyOnceLock<Py<PyType>> = PyOnceLock::new();

/// Retained public base property, optionally using its public C getter directly.
struct BaseProperty {
    descriptor: Py<PyAny>,
    native: Option<(ffi::getter, usize)>,
}
impl BaseProperty {
    /// Retain a public base descriptor and its validated native getter, if available.
    fn prepare(class: &Bound<'_, PyType>, name: &str) -> PyResult<Self> {
        let descriptor = class
            .getattr(name)
            .map_err(crate::error_context::external)?;
        let native = if unsafe {
            ffi::Py_TYPE(descriptor.as_ptr()) == std::ptr::addr_of_mut!(ffi::PyGetSetDescr_Type)
        } {
            // SAFETY: exact public descriptor layout; prove its declared owner
            // accepts the captured base type before retaining its getter.
            let definition = unsafe { &*descriptor.as_ptr().cast::<ffi::PyGetSetDescrObject>() };
            if !definition.d_common.d_type.is_null()
                && !definition.d_getset.is_null()
                && unsafe {
                    ffi::PyType_IsSubtype(class.as_type_ptr(), definition.d_common.d_type) != 0
                }
            {
                let getset = unsafe { &*definition.d_getset };
                getset.get.map(|getter| (getter, getset.closure as usize))
            } else {
                None
            }
        } else {
            None
        };
        Ok(Self {
            descriptor: descriptor.unbind(),
            native,
        })
    }

    /// The caller has proved real inheritance from this property's base type.
    fn read<'py>(&self, value: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some((getter, closure)) = self.native {
            // SAFETY: actual ancestry is proved by every caller; the retained
            // descriptor owns the getter and closure for the complete call.
            return unsafe {
                Bound::from_owned_ptr_or_err(value.py(), getter(value.as_ptr(), closure as *mut _))
            }
            .map_err(crate::error_context::external);
        }
        self.descriptor
            .bind(value.py())
            .call_method1("__get__", (value, value.get_type()))
            .map_err(crate::error_context::external)
    }
}
struct TimestampProperties {
    ticks: BaseProperty,
    year: BaseProperty,
    nanos: BaseProperty,
    add: Py<PyAny>,
    subtract: Py<PyAny>,
    reflected_subtract: Py<PyAny>,
    replace_needs_tail: bool,
}
static TIMESTAMP_PROPERTIES: PyOnceLock<TimestampProperties> = PyOnceLock::new();
static DURATION_PROPERTY: PyOnceLock<BaseProperty> = PyOnceLock::new();

/// Publish the type objects captured by the shared optional-dependency entry.
///
/// # Errors
/// Rejects an invalid private registration without publishing that type.
#[pyfunction]
pub(crate) fn _configure_optional(
    py: Python<'_>,
    timestamp: &Bound<'_, PyAny>,
    duration: &Bound<'_, PyAny>,
    nat: &Bound<'_, PyAny>,
    series: &Bound<'_, PyAny>,
    timestamp_replace_needs_tail: bool,
) -> PyResult<()> {
    let candidates = [timestamp, duration, nat].map(|value| {
        if value.is_none() {
            Ok(None)
        } else {
            value
                .cast::<PyType>()
                .map(|kind| Some(kind.clone().unbind()))
                .map_err(PyErr::from)
        }
    });
    let [timestamp, duration, nat] = candidates;
    let types = [timestamp?, duration?, nat?];
    if let Some(kind) = &types[0] {
        let class = kind.bind(py);
        let properties = TimestampProperties {
            ticks: BaseProperty::prepare(class, "asm8")?,
            year: BaseProperty::prepare(class, "year")?,
            nanos: BaseProperty::prepare(class, "nanosecond")?,
            add: class
                .getattr("__add__")
                .map_err(crate::error_context::external)?
                .unbind(),
            subtract: class
                .getattr("__sub__")
                .map_err(crate::error_context::external)?
                .unbind(),
            reflected_subtract: class
                .getattr("__rsub__")
                .map_err(crate::error_context::external)?
                .unbind(),
            replace_needs_tail: timestamp_replace_needs_tail,
        };
        let _ = TIMESTAMP_PROPERTIES.set(py, properties);
    }
    if let Some(kind) = &types[1] {
        let property = BaseProperty::prepare(kind.bind(py), "asm8")?;
        let _ = DURATION_PROPERTY.set(py, property);
    }
    crate::epoch::prepare_polars_type(series)?;
    for (cache, kind) in [&PANDAS_TIMESTAMP, &PANDAS_TIMEDELTA, &PANDAS_NAT]
        .into_iter()
        .zip(types)
    {
        if let Some(kind) = kind {
            let _ = cache.set(py, kind);
        }
    }
    Ok(())
}

/// Prove actual pandas ancestry from the once-published shared type reference.
fn pandas_scalar(value: &Bound<'_, PyAny>, cache: &PyOnceLock<Py<PyType>>) -> PyResult<bool> {
    let py = value.py();
    let Some(class) = cache.get(py) else {
        return Ok(false);
    };
    // Both operands are real types, so use C ancestry rather than allocating a
    // temporary type reference or consulting a Python __subclasscheck__ hook.
    // SAFETY: value and the retained cached class are live under the GIL.
    let base = class.bind(py).as_type_ptr();
    Ok(unsafe {
        let actual = ffi::Py_TYPE(value.as_ptr());
        actual == base || ffi::PyType_IsSubtype(actual, base) != 0
    })
}

/// Years used by pandas' missing/wide date carriers; all other base years are real.
#[inline(always)]
pub(crate) fn needs_true_year(year: i32) -> bool {
    matches!(year, 1 | 1970 | 1972)
}

static PANDAS_NAT: PyOnceLock<Py<PyType>> = PyOnceLock::new();

/// Reject actual pandas missing dates before reading their datetime base storage.
/// Ordinary values require no pandas import or Python callbacks.
pub(crate) fn reject_nat(value: &Bound<'_, PyAny>, entry: &str, parameter: &str) -> PyResult<()> {
    if is_nat(value)? {
        let error = crate::error_context::value_error(
            "pandas NaT is a missing date; provide a valid date instead",
        );
        return Err(crate::error_context::argument(
            value.py(),
            error,
            entry,
            parameter,
            value,
        ));
    }
    Ok(())
}

/// Test genuine NaT ancestry without importing pandas for ordinary dates.
pub(crate) fn is_nat(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    // pandas NaT's datetime carrier is year 1. Ordinary calendar years need
    // no optional-module lookup. The actual type check below remains the proof.
    // SAFETY: the real date predicate precedes its stored-field read.
    if unsafe {
        ffi::PyDate_Check(value.as_ptr()) != 0 && ffi::PyDateTime_GET_YEAR(value.as_ptr()) != 1
    } {
        return Ok(false);
    }
    let py = value.py();
    let actual = value.get_type();
    let Some(kind) = PANDAS_NAT.get(py) else {
        return Ok(false);
    };
    Ok(actual.is(kind.bind(py)) || actual.is_subclass(kind.bind(py))?)
}

/// Actual Timestamp wall fields and sub-microsecond remainder from public ticks.
/// # Errors
/// Rejects NaT and propagates real unit, calendar and timezone conversion errors.
pub(crate) fn timestamp_parts(value: &Bound<'_, PyAny>) -> PyResult<Option<([i64; 7], i64)>> {
    // pandas 2/3 creates out-of-range Timestamp carriers with year 1970
    // or 1972 (timestamps.pyx:create_timestamp_from_ts). Every other stored
    // year is already real. This semantic guard preserves the native ordinary
    // path without depending on any private pandas field offset.
    // SAFETY: the native datetime predicate proves the stored year layout.
    if unsafe { ffi::PyDateTime_Check(value.as_ptr()) == 0 } {
        return Ok(None);
    }
    let year = unsafe { ffi::PyDateTime_GET_YEAR(value.as_ptr()) };
    if !matches!(year, 1970 | 1972) {
        if year == 1 {
            reject_nat(value, "date conversion", "value")?;
        }
        return Ok(None);
    }
    if value.is_exact_instance_of::<PyDateTime>() || crate::pydt::is_exact(value) {
        return Ok(None);
    }
    if !pandas_scalar(value, &PANDAS_TIMESTAMP)? {
        return Ok(None);
    }
    let fields = timestamp_local_fields(value)?;
    let access = timestamp_properties(value.py())?;
    Ok(Some((fields, access.nanos.read(value)?.extract()?)))
}

/// Return the already committed Timestamp descriptors; never prepare them on a hot call.
fn timestamp_properties(py: Python<'_>) -> PyResult<&TimestampProperties> {
    TIMESTAMP_PROPERTIES.get(py).ok_or_else(|| {
        crate::error_context::runtime("pandas Timestamp properties are not initialized")
    })
}

/// Read actual local fields from a proven Timestamp, without any offset callback.
/// Only pandas' out-of-range year carrier needs the retained year descriptor.
pub(crate) fn timestamp_local_fields(value: &Bound<'_, PyAny>) -> PyResult<[i64; 7]> {
    let dt = value.cast::<PyDateTime>()?;
    let year = if matches!(dt.get_year(), 1970 | 1972) {
        timestamp_properties(value.py())?
            .year
            .read(value)?
            .extract::<i64>()?
    } else {
        i64::from(dt.get_year())
    };
    Ok([
        year,
        i64::from(dt.get_month()),
        i64::from(dt.get_day()),
        i64::from(dt.get_hour()),
        i64::from(dt.get_minute()),
        i64::from(dt.get_second()),
        i64::from(dt.get_microsecond()),
    ])
}

/// Read a proven Timestamp's original numpy unit/ticks through its base property.
pub(crate) fn timestamp_ticks(value: &Bound<'_, PyAny>) -> PyResult<crate::epoch::Parsed> {
    let access = timestamp_properties(value.py())?;
    let scalar = access.ticks.read(value)?;
    let mut parsed = crate::epoch::read_numpy(&scalar)?
        .ok_or_else(|| crate::error_context::value_error("invalid pandas Timestamp ticks"))?;
    // pandas2 replace can retain coarse asm8 storage while setting a real
    // sub-microsecond field. Read that base field before any shared arithmetic
    // or parsing exit; ns asm8 already contains it and must not count it twice.
    // The prepared pandas3 fast path needs no additional descriptor read.
    if access.replace_needs_tail && parsed.unit < crate::epoch::Unit::Nanosecond {
        let tail = access.nanos.read(value)?.extract::<i64>()?;
        if tail != 0 {
            parsed.nanos = parsed
                .nanos
                .checked_add(i128::from(tail))
                .ok_or_else(|| crate::error_context::overflow("Timestamp nanosecond overflow"))?;
            parsed.unit = crate::epoch::Unit::Nanosecond;
        }
    }
    Ok(parsed)
}

/// Read datetime-operation fields and its stored timezone protocol.
///
/// Public epoch parsing deliberately supports a datetime child's own
/// `utcoffset` method. Standard datetime comparison/subtraction instead ask
/// the retained tzinfo, while same-zone operations need no offset callback.
pub(crate) fn datetime_operation_ticks(
    value: &Bound<'_, PyDateTime>,
    wall_clock: bool,
) -> PyResult<(i128, bool)> {
    let timestamp = is_timestamp(value.as_any())?;
    let (fields, tail) = if timestamp {
        (
            timestamp_local_fields(value.as_any())?,
            timestamp_ticks(value.as_any())?.nanos.rem_euclid(1000),
        )
    } else {
        (
            [
                i64::from(value.get_year()),
                i64::from(value.get_month()),
                i64::from(value.get_day()),
                i64::from(value.get_hour()),
                i64::from(value.get_minute()),
                i64::from(value.get_second()),
                i64::from(value.get_microsecond()),
            ],
            0,
        )
    };
    let [year, month, day, hour, minute, second, microsecond] = fields;
    let days = crate::calendar::ordinal(year, month, day) - 719_163;
    let local = i128::from(days) * 86_400_000_000_000
        + ((i128::from(hour) * 60 + i128::from(minute)) * 60 + i128::from(second)) * 1_000_000_000
        + i128::from(microsecond) * 1000
        + tail;
    if wall_clock {
        return Ok((local, false));
    }
    match crate::epoch::offset_us(&crate::pydt::utc_offset(value)?)? {
        Some(offset) => Ok((local - i128::from(offset) * 1000, true)),
        None => Ok((local, false)),
    }
}

/// Qualify a live arithmetic definition without trusting metaclass lookup.
fn standard_timestamp_method(value: &Bound<'_, PyAny>, name: &str) -> PyResult<bool> {
    let access = timestamp_properties(value.py())?;
    let expected = match name {
        "__add__" => &access.add,
        "__sub__" => &access.subtract,
        "__rsub__" => &access.reflected_subtract,
        _ => return Ok(false),
    };
    let expected = expected.bind(value.py());
    // Both public native descriptor forms occur in supported pandas builds.
    // An unrelated borrowed descriptor or Python replacement is not standard.
    let standard = unsafe {
        let descriptor_type = ffi::Py_TYPE(expected.as_ptr());
        if descriptor_type != std::ptr::addr_of_mut!(ffi::PyWrapperDescr_Type)
            && descriptor_type != std::ptr::addr_of_mut!(ffi::PyMethodDescr_Type)
        {
            false
        } else {
            // SAFETY: both proven descriptor types start with PyDescrObject.
            let owner = (*expected.as_ptr().cast::<ffi::PyDescrObject>()).d_type;
            !owner.is_null()
                && timestamp_type(value.py())
                    .is_some_and(|kind| ffi::PyType_IsSubtype(kind, owner) != 0)
        }
    };
    if !standard {
        return Ok(false);
    }
    Ok(crate::protocol::method_definition(&value.get_type(), name)?
        .is_some_and(|definition| definition.is(expected)))
}

/// Preserve Timestamp addition, then compute its standard difference in wide ticks.
/// Custom arithmetic uses its own ordinary subtraction and is never repeated.
pub(crate) fn timestamp_span<'py>(
    delta: &Bound<'py, crate::delta::Delta>,
    start: &Bound<'py, PyAny>,
) -> PyResult<Option<Bound<'py, PyDelta>>> {
    if !is_timestamp(start)? || !standard_timestamp_method(start, "__add__")? {
        return Ok(None);
    }
    let target = start.add(delta).map_err(crate::error_context::external)?;
    let timestamp_target = is_timestamp(&target)?;
    // Python gives a strict right-hand subclass's reflected operation priority.
    // Once addition ran, any fallback must subtract this target, never add again.
    let reflected_priority = timestamp_target
        && unsafe {
            ffi::Py_TYPE(start.as_ptr()) != ffi::Py_TYPE(target.as_ptr())
                && ffi::PyType_IsSubtype(
                    ffi::Py_TYPE(start.as_ptr()),
                    ffi::Py_TYPE(target.as_ptr()),
                ) != 0
        };
    if !timestamp_target
        || !standard_timestamp_method(&target, "__sub__")?
        || (reflected_priority && !standard_timestamp_method(start, "__rsub__")?)
    {
        let difference = target
            .sub(start)
            .map_err(crate::error_context::external)?
            .cast_into::<PyDelta>()
            .map_err(|_| {
                crate::error_context::type_error("start arithmetic did not produce a timedelta")
            })?;
        return standard_span(&difference).map(Some);
    }
    // Timestamp's own standard subtraction uses stored elapsed ticks, unlike
    // datetime's same-zone wall clock or public epoch callback protocols.
    let end = timestamp_ticks(&target)?;
    let begin = timestamp_ticks(start)?;
    if target.cast::<PyDateTime>()?.get_tzinfo().is_some()
        != start.cast::<PyDateTime>()?.get_tzinfo().is_some()
    {
        return Err(crate::error_context::type_error(
            "cannot subtract offset-naive and offset-aware dates",
        ));
    }
    let span = end
        .nanos
        .checked_sub(begin.nanos)
        .ok_or_else(|| crate::error_context::overflow("date difference overflow"))?;
    span_from_nanoseconds(start.py(), span).map(Some)
}

/// Read the true pandas duration without narrowing its total to signed64 micros.
pub(crate) fn duration_nanoseconds(value: &Bound<'_, PyAny>) -> PyResult<Option<i128>> {
    if !pandas_scalar(value, &PANDAS_TIMEDELTA)? {
        return Ok(None);
    }
    let property = DURATION_PROPERTY.get(value.py()).ok_or_else(|| {
        crate::error_context::runtime("pandas Timedelta property is not initialized")
    })?;
    let scalar = property.read(value)?;
    crate::numpy_scalar::duration_nanoseconds(&scalar)
}

/// Retain the prepared actual pandas duration base for reflected protocol checks.
pub(crate) fn timedelta_type(py: Python<'_>) -> Option<Bound<'_, PyType>> {
    PANDAS_TIMEDELTA.get(py).map(|class| class.bind(py).clone())
}

/// Prove actual Timestamp ancestry, including children whose names differ.
pub(crate) fn is_timestamp(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    pandas_scalar(value, &PANDAS_TIMESTAMP)
}

/// Borrow the cached base type, retained by the interpreter-aware type cache.
pub(crate) fn timestamp_type(py: Python<'_>) -> Option<*mut ffi::PyTypeObject> {
    PANDAS_TIMESTAMP
        .get(py)
        .map(|class| class.bind(py).as_type_ptr())
}

/// Borrow the already registered scalar class for a necessary dynamic carrier.
pub(crate) fn timestamp_class(py: Python<'_>) -> PyResult<&Bound<'_, PyType>> {
    PANDAS_TIMESTAMP
        .get(py)
        .map(|class| class.bind(py))
        .ok_or_else(|| crate::error_context::runtime("pandas Timestamp is not registered"))
}

/// Read the nanosecond remainder only from a proven pandas Timestamp.
pub(crate) fn timestamp_nanoseconds(value: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    if pandas_scalar(value, &PANDAS_TIMESTAMP)? {
        return timestamp_properties(value.py())?
            .nanos
            .read(value)?
            .extract()
            .map(Some);
    }
    Ok(None)
}

/// Return a standard timedelta, rounding a pandas remainder once to even microseconds.
///
/// # Errors
/// Propagates pandas attribute errors and rejects a rounded span outside timedelta.
pub(crate) fn standard_span<'py>(value: &Bound<'py, PyDelta>) -> PyResult<Bound<'py, PyDelta>> {
    if value.is_exact_instance_of::<PyDelta>() {
        return Ok(value.clone());
    }
    let py = value.py();
    let total = if let Some(nanos) = duration_nanoseconds(value.as_any())? {
        nanos
    } else {
        (i128::from(value.get_days()) * 86_400_000_000
            + i128::from(value.get_seconds()) * 1_000_000
            + i128::from(value.get_microseconds()))
            * 1000
    };
    span_from_nanoseconds(py, total)
}

/// Round once to even microseconds, then construct a bounded standard timedelta.
pub(crate) fn span_from_nanoseconds<'py>(
    py: Python<'py>,
    total: i128,
) -> PyResult<Bound<'py, PyDelta>> {
    let quotient = total.div_euclid(1_000);
    let remainder = total.rem_euclid(1_000);
    let rounded = quotient + i128::from(remainder > 500 || (remainder == 500 && quotient % 2 != 0));
    let days = rounded.div_euclid(86_400_000_000);
    if !(-999_999_999..=999_999_999).contains(&days) {
        return Err(crate::error_context::overflow(
            "duration is outside timedelta's supported range",
        ));
    }
    let clock = rounded.rem_euclid(86_400_000_000);
    PyDelta::new(
        py,
        days as i32,
        (clock / 1_000_000) as i32,
        (clock % 1_000_000) as i32,
        false,
    )
}

/// Share fixed keyword names while preserving constructor and attribute callback order.
fn date_keys(py: Python<'_>) -> &[Py<PyString>; 9] {
    DATE_KEYS.get_or_init(py, || {
        let names = [
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
/// date/datetime constructor retains its original exception and receives context.
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
    let (result, _) = crate::calendar::apply(&delta.native_value(), input, 1, datetime)
        .map_err(crate::error_context::overflow)?;
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
    if dt.get_year() == 1 {
        reject_nat(other, "Delta date arithmetic", "other")?;
    }
    if !delta.__bool__() {
        return Ok(Some(other.clone()));
    }
    if delta.preserves_datetime_clock(dt)
        && ((delta
            .native_value()
            .absolute
            .get(crate::delta::value::AbsoluteField::Microsecond)
            .is_none()
            && delta
                .native_value()
                .absolute
                .get(crate::delta::value::AbsoluteField::Nanosecond)
                .is_none())
            || timestamp_nanoseconds(other)?.unwrap_or(0) == 0)
    {
        return Ok(Some(other.clone()));
    }
    apply_datetime_fields(&delta.native_value(), false, other, dt, sign)
}

/// Apply an already captured Delta value through the same checked date kernel.
///
/// # Preconditions
/// fields is the immutable canonical snapshot; empty is its derived truth flag.
/// # Errors
/// Preserves all original arithmetic, subtype and constructor errors.
#[inline(always)]
pub(crate) fn apply_datetime_fields<'py>(
    fields: &crate::delta::value::DeltaValue,
    empty: bool,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    // The public vector call preserves the same keyword order and callbacks,
    // while avoiding a temporary keyword dictionary for datetime subclasses.
    if other.is_exact_instance_of::<PyDateTime>() {
        apply_datetime_fields_impl::<true, true>(fields, empty, other, dt, sign)
    } else {
        apply_datetime_fields_impl::<true, false>(fields, empty, other, dt, sign)
    }
}

/// Apply a batch item whose exact builtin datetime type was already proved.
/// # Preconditions
/// other and dt refer to the same exact builtin datetime, checked by the batch.
/// # Errors
/// Preserves the shared calendar, bounds and builtin allocation errors.
#[inline(always)]
pub(crate) fn apply_builtin_datetime_fields<'py>(
    fields: &crate::delta::value::DeltaValue,
    empty: bool,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    apply_datetime_fields_impl::<true, true>(fields, empty, other, dt, sign)
}

/// Apply prepared datetime fields using public keyword vectorcall for subtypes.
/// # Errors
/// Preserves date, custom constructor and allocation failures.
pub(crate) fn apply_datetime_fields_vector<'py>(
    fields: &crate::delta::value::DeltaValue,
    empty: bool,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    apply_datetime_fields_impl::<true, false>(fields, empty, other, dt, sign)
}

/// Run the same checked calendar work with a fixed constructor calling convention.
/// # Errors
/// Preserves normalization, boundaries and custom constructor exception handling.
#[inline(always)]
fn apply_datetime_fields_impl<'py, const VECTOR: bool, const BUILTIN: bool>(
    fields: &crate::delta::value::DeltaValue,
    empty: bool,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = other.py();
    if !BUILTIN && dt.get_year() == 1 {
        reject_nat(other, "Delta date arithmetic", "other")?;
    }
    if empty {
        return Ok(Some(other.clone()));
    }
    // A real Timestamp retains its complete ns coordinate until its own public
    // replacement method. Other datetime subclasses use the us target below.
    if !BUILTIN && is_timestamp(other)? {
        return apply_timestamp(fields, other, dt, sign).map(Some);
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
    let (result, unchanged) = crate::calendar::apply(fields, parts, sign, true)
        .map_err(crate::error_context::overflow)?;
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let [year, month, day, hour, minute, second, microsecond] = result;
    if BUILTIN || other.is_exact_instance_of::<PyDateTime>() {
        let year = i32::try_from(year).map_err(|_| {
            crate::error_context::overflow("integer overflow in Delta date arithmetic")
        })?;
        // The checked datetime receiver initialized this SDK capsule. Its tzinfo
        // is borrowed from the live input; the public constructor retains it in
        // the new object. Avoid a temporary owned Python reference on this path.
        // The checked datetime type/cast has already initialized this capsule.
        // Use its one public constructor; keep an explicit error for an invalid
        // interpreter state instead of carrying a second constructor frame.
        let api = unsafe { ffi::PyDateTimeAPI().as_ref() }
            .ok_or_else(|| crate::error_context::runtime("datetime API is not initialized"))?;
        // SAFETY: dt is checked and live under the GIL. The initialized public
        // SDK validates calendar bounds, retains tzinfo and returns a new ref.
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
    finish_datetime_subclass::<VECTOR>(other, dt, result, unchanged)
}

/// Apply complete local Timestamp fields without an intermediate us projection.
/// # Errors
/// Preserves actual storage, checked calendar and the real replace callback.
#[inline(never)]
fn apply_timestamp<'py>(
    fields: &crate::delta::value::DeltaValue,
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    sign: i64,
) -> PyResult<Bound<'py, PyAny>> {
    let parts = timestamp_local_fields(other)?;
    let access = timestamp_properties(other.py())?;
    let tail = access.nanos.read(other)?.extract::<i64>()?;
    let input = crate::civil::CivilNs {
        year: i128::from(parts[0]),
        month: parts[1] as u8,
        day: parts[2] as u8,
        clock_ns: (((parts[3] * 60 + parts[4]) * 60 + parts[5]) * 1_000_000_000
            + parts[6] * 1000
            + tail) as u64,
    };
    let result =
        crate::civil::apply(fields, input, sign).map_err(crate::error_context::overflow)?;
    if result == input {
        return Ok(other.clone());
    }
    let clock = result.clock_ns;
    let new_tail = (clock % 1000) as i64;
    replace_timestamp(
        other,
        [
            i64::try_from(result.year).map_err(|_| {
                crate::error_context::overflow("Timestamp year exceeds signed64 capacity")
            })?,
            i64::from(result.month),
            i64::from(result.day),
            (clock / 3_600_000_000_000) as i64,
            (clock / 60_000_000_000 % 60) as i64,
            (clock / 1_000_000_000 % 60) as i64,
            (clock / 1000 % 1_000_000) as i64,
        ],
        (new_tail != tail || (tail != 0 && access.replace_needs_tail)).then_some(new_tail),
        dt.get_fold(),
    )
}

/// Keep foreign precision and constructor callbacks outside builtin loop frames.
#[inline(never)]
fn finish_datetime_subclass<'py, const VECTOR: bool>(
    other: &Bound<'py, PyAny>,
    dt: &Bound<'py, PyDateTime>,
    result: [i64; 7],
    unchanged: bool,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let prepared = crate::pydt::delta_calendar_fields(dt, result)?;
    construct_subclass::<VECTOR>(
        other,
        Some(dt),
        prepared.map_or(result, |value| value.0),
        prepared.map(|value| value.1),
    )
}

/// Carry extra precision through pandas' public replacement method.
/// Keep its keyword allocation outside ordinary datetime and Pydt loop frames.
#[inline(never)]
fn replace_timestamp<'py>(
    value: &Bound<'py, PyAny>,
    parts: [i64; 7],
    nanos: Option<i64>,
    fold: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let kwargs = PyDict::new(value.py());
    let input_microsecond = i64::from(value.cast::<PyDateTime>()?.get_microsecond());
    for (name, part) in [
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
        "microsecond",
    ]
    .into_iter()
    .zip(parts)
    {
        // Explicit microsecond=0 can force a coarse wide Timestamp into an
        // unrepresentable finer resolution. Omit an unchanged fractional field.
        if name != "microsecond" || part != input_microsecond {
            kwargs.set_item(name, part)?;
        }
    }
    if let Some(nanos) = nanos {
        kwargs.set_item("nanosecond", nanos)?;
    }
    kwargs.set_item("fold", i64::from(fold))?;
    value
        .call_method("replace", (), Some(&kwargs))
        .map_err(crate::error_context::external)
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
    apply_date_only_fields(&delta.native_value(), false, other, date, sign)
}

/// Apply an already captured Delta value through the same checked date kernel.
///
/// # Preconditions
/// fields is the immutable canonical snapshot; empty is its derived truth flag.
/// # Errors
/// Preserves all original arithmetic, subtype and constructor errors.
#[inline]
pub(crate) fn apply_date_only_fields<'py>(
    fields: &crate::delta::value::DeltaValue,
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
    let (result, unchanged) = crate::calendar::apply(fields, parts, sign, false)
        .map_err(crate::error_context::overflow)?;
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let year = i32::try_from(result[0])
        .map_err(|_| crate::error_context::overflow("integer overflow in Delta date arithmetic"))?;
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
    construct_subclass::<false>(other, None, result, None)
}

// Ordinary builtins do not need a keyword dictionary or Python callback.
// Keep this less common constructor/error path out of their call frame.
/// Construct the input's runtime date class with computed keyword arguments.
///
/// # Errors
/// A constructor is an external callback: retain its original exception.
/// Public arithmetic/batch boundaries supply their own context, once.
#[cold]
#[inline(never)]
fn construct_subclass<'py, const VECTOR: bool>(
    other: &Bound<'py, PyAny>,
    dt: Option<&Bound<'py, PyDateTime>>,
    result: [i64; 7],
    fold: Option<i32>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = other.py();
    let [year, month, day, hour, minute, second, microsecond] = result;
    let keys = date_keys(py);
    let class = other.get_type();
    let called = if VECTOR {
        static KEYWORDS: PyOnceLock<Py<PyTuple>> = PyOnceLock::new();
        let names = KEYWORDS.get_or_try_init(py, || -> PyResult<_> {
            Ok(PyTuple::new(py, keys.iter().map(|key| key.bind(py)))?.unbind())
        })?;
        let Some(dt) = dt else {
            return Err(crate::error_context::runtime(
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
            fold.unwrap_or_else(|| i32::from(dt.get_fold()))
                .into_pyobject(py)?
                .into_any(),
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
            kwargs.set_item(keys[index].bind(py), value)?;
        }
        if let Some(dt) = dt {
            for (index, value) in [hour, minute, second, microsecond].into_iter().enumerate() {
                kwargs.set_item(keys[index + 3].bind(py), value)?;
            }
            kwargs.set_item(keys[7].bind(py), dt.get_tzinfo())?;
            kwargs.set_item(
                keys[8].bind(py),
                fold.unwrap_or_else(|| i32::from(dt.get_fold())),
            )?;
        }
        class
            .call((), Some(&kwargs))
            .map_err(crate::error_context::external)
    };
    called.map(Some).map_err(crate::error_context::external)
}

use pyo3::sync::PyOnceLock;
use pyo3::types::PyType;

static RELATIVEDELTA: PyOnceLock<Py<PyType>> = PyOnceLock::new();
static DATEUTIL_AVAILABLE: PyOnceLock<bool> = PyOnceLock::new();

/// Cache only genuine top-level absence; installed-provider failures propagate.
fn dateutil_available(py: Python<'_>) -> PyResult<bool> {
    Ok(*crate::python_cache::get_or_prepare(
        &DATEUTIL_AVAILABLE,
        py,
        || match py.import("dateutil") {
            Ok(_) => Ok(true),
            Err(error) => {
                if error.is_instance_of::<pyo3::exceptions::PyModuleNotFoundError>(py)
                    && error.value(py).getattr("name")?.eq("dateutil")?
                {
                    Ok(false)
                } else {
                    Err(error)
                }
            }
        },
    )?)
}

/// Supply the Configs boundary with its real optional source class.
///
/// This does not prepare relativedelta's type early: its existing first-use
/// lookup and finite reentrant preparation remain observable protocols.
/// # Errors
/// Propagates errors from an installed but unusable dateutil provider.
pub(crate) fn parserinfo_type(py: Python<'_>) -> PyResult<Option<Py<PyType>>> {
    if !dateutil_available(py)? {
        return Ok(None);
    }
    Ok(Some(
        py.import("dateutil.parser._parser")?
            .getattr("parserinfo")?
            .cast_into::<PyType>()?
            .unbind(),
    ))
}

/// Check actual relativedelta ancestry, or return false when dateutil is absent.
///
/// # Errors
/// Propagates errors from an installed but unusable dateutil provider.
pub fn is_relativedelta(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    let py = value.py();
    let class = if let Some(class) = RELATIVEDELTA.get(py) {
        class
    } else {
        if !dateutil_available(py)? {
            return Ok(false);
        }
        crate::python_cache::get_or_prepare(&RELATIVEDELTA, py, || -> PyResult<_> {
            Ok(py
                .import("dateutil.relativedelta")?
                .getattr("relativedelta")
                .map_err(crate::error_context::external)?
                .cast_into::<PyType>()?
                .unbind())
        })?
    };
    // SAFETY: both actual types remain live; no __class__ or metaclass hook runs.
    Ok(unsafe {
        ffi::PyType_IsSubtype(ffi::Py_TYPE(value.as_ptr()), class.bind(py).as_type_ptr()) != 0
    })
}

/// Return the already initialized dateutil type without imports or callbacks.
pub(crate) fn exact_relative_type(py: Python<'_>) -> Option<*mut ffi::PyTypeObject> {
    RELATIVEDELTA
        .get(py)
        .map(|class| class.bind(py).as_type_ptr())
}

/// Read raw source fields only when the live object is the exact cached dateutil type.
///
/// The cache must already be initialized; a missing cache or any subclass/fake
/// class returns None so the original membership/callback path remains active.
/// # Errors
/// Preserves actual field, numeric conversion and normalization failures.
#[inline]
pub(crate) fn exact_relative_fields(
    value: &Bound<'_, PyAny>,
) -> PyResult<Option<crate::delta::RelativeFields>> {
    let py = value.py();
    if let Some(class) = exact_relative_type(py) {
        // SAFETY: Both type identities are live and owned while attached.
        // Only an actual exact type can qualify; no foreign payload is cast.
        if unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) } == class {
            return read_relative_fields(value).map(Some);
        }
    }
    Ok(None)
}

/// Own the fixed attribute names once for a batch, without reading foreign data.
pub(crate) fn relative_keys(py: Python<'_>) -> [Py<PyString>; 16] {
    [
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

/// Read raw source attributes with the batch's owned fixed names.
/// # Errors
/// Preserves field, numeric conversion and unsupported-rule failures.
pub(crate) fn relative_fields_named(
    value: &Bound<'_, PyAny>,
    keys: &[Py<PyString>; 16],
) -> PyResult<crate::delta::RelativeFields> {
    let py = value.py();
    check_relative_rules(value, keys[10].bind(py), keys[15].bind(py))?;
    let names = std::array::from_fn(|index| keys[index].bind(py));
    read_raw_relative_fields(value, names, keys[15].bind(py))
}

/// Import actual source fields; unsupported weekday and leapdays rules are rejected.
/// No normalized() method is called, including for true source subclasses.
/// # Errors
/// Rejects a foreign type and propagates real field/numeric conversion failures.
pub(crate) fn relativedelta_fields(
    value: &Bound<'_, PyAny>,
) -> PyResult<crate::delta::RelativeFields> {
    if !is_relativedelta(value)? {
        if !dateutil_available(value.py())? {
            let error = pyo3::exceptions::PyImportError::new_err(
                "dateutil integration requires python-dateutil; install rstimes[dateutil]",
            );
            // ImportError otherwise displays its cached msg instead of the
            // args completed by our existing public-entry error boundary.
            error.value(value.py()).setattr("msg", value.py().None())?;
            return Err(crate::error_context::own(error));
        }
        return Err(crate::error_context::type_error(
            "rd must be a dateutil.relativedelta instance",
        ));
    }
    read_relative_fields(value)
}

/// Read ordered attributes after actual relativedelta ancestry was established.
///
/// # Errors
/// Propagates attribute, numeric conversion and checked normalization errors.
#[inline]
pub(crate) fn read_relative_fields(
    value: &Bound<'_, PyAny>,
) -> PyResult<crate::delta::RelativeFields> {
    let py = value.py();
    // Cache names only. Every actual source field and live rule is still read
    // in the same order; no user value or callback result is cached.
    let keys = crate::python_cache::get_or_prepare(&RELATIVE_KEYS, py, || {
        Ok::<_, PyErr>(relative_keys(py))
    })?;
    relative_fields_named(value, keys)
}

/// Reject unsupported rules before reading source numeric fields.
fn check_relative_rules(
    value: &Bound<'_, PyAny>,
    weekday: &Bound<'_, PyString>,
    leapdays: &Bound<'_, PyString>,
) -> PyResult<()> {
    if !value
        .getattr(weekday)
        .map_err(crate::error_context::external)?
        .is_none()
    {
        return Err(crate::error_context::value_error(
            "weekday rules cannot be represented by Delta",
        ));
    }
    if value
        .getattr(leapdays)
        .map_err(crate::error_context::external)?
        .is_truthy()
        .map_err(crate::error_context::external)?
    {
        return Err(crate::error_context::value_error(
            "nonzero leapdays cannot be represented by Delta",
        ));
    }
    Ok(())
}

/// Read a source snapshot, adapting absolute meaning before normalization.
/// # Errors
/// Preserves attribute access, checked conversion and unsupported-rule failures.
#[inline(always)]
fn read_raw_relative_fields(
    source: &Bound<'_, PyAny>,
    names: [&Bound<'_, PyString>; 15],
    leapdays: &Bound<'_, PyString>,
) -> PyResult<crate::delta::RelativeFields> {
    let mut fields = [0; 15];
    let mut fraction = crate::delta::FixedFractions::default();
    let mut absolute_present = 0_u16;
    for (index, name) in names.into_iter().enumerate() {
        let item = source
            .getattr(name)
            .map_err(crate::error_context::external)?;
        if index >= 7 && item.is_none() {
            fields[index] = -1;
            continue;
        }
        if index == 10 {
            return Err(crate::error_context::value_error(
                "weekday rules cannot be represented by Delta",
            ));
        }
        if index >= 7 {
            absolute_present |= 1 << index;
        }
        fields[index] = if index < 7 {
            crate::delta::relative_input(&item, [0, 2, 4, 5, 6, 7, 9][index], &mut fraction)?
        } else if index <= 9 && !item.is_truthy().map_err(crate::error_context::external)? {
            // dateutil explicitly uses a false date field as an absent selection.
            0
        } else if index == 9 && item.is_exact_instance_of::<PyFloat>() {
            let day = item.extract::<f64>()?;
            if day.is_finite() && day >= 31.0 {
                31
            } else {
                crate::delta::index_integer(&item)?
            }
        } else {
            crate::delta::index_integer(&item)?
        };
    }
    // Later absolute clock conversions may have changed the source rules.
    // This deliberate live check is separate from the once-read number fields.
    check_relative_rules(source, names[10], leapdays)?;
    crate::delta::normalize_relative_fields(
        interpret_relative_absolute(fields, absolute_present)?,
        fraction,
    )
}

/// Resolve dateutil's absolute-and-relative date rules before compact storage.
///
/// This is a source adapter, not the public Delta constructor: dateutil treats
/// absolute date zero as absent and applies relative years/months before its
/// destination-month day clamp. Reject values that cannot retain that meaning.
fn interpret_relative_absolute(mut fields: [i64; 15], present: u16) -> PyResult<[i64; 15]> {
    let overflow = || crate::error_context::overflow("calendar combination overflow");
    let invalid = |name: &str, number: i64| {
        crate::error_context::value_error(format!(
            "{name}={number} cannot be represented with the same date meaning"
        ))
    };
    let year_set = present & (1 << 7) != 0 && fields[7] != 0;
    let folded_year = year_set && !(1..=9999).contains(&fields[7]);
    if folded_year {
        fields[7] = fields[7].checked_add(fields[0]).ok_or_else(overflow)?;
        fields[0] = 0;
    } else if !year_set {
        fields[7] = -1;
    }
    if present & (1 << 8) != 0 && fields[8] != 0 {
        if (folded_year && !(1..=9999).contains(&fields[7])) || !(1..=12).contains(&fields[8]) {
            let mut month = fields[8];
            if fields[1] != 0 {
                month = month.checked_add(fields[1]).ok_or_else(overflow)?;
                let carry = if month > 12 {
                    month -= 12;
                    1
                } else if month < 1 {
                    month += 12;
                    -1
                } else {
                    0
                };
                let target = if folded_year {
                    &mut fields[7]
                } else {
                    &mut fields[0]
                };
                *target = target.checked_add(carry).ok_or_else(overflow)?;
            }
            if !(1..=12).contains(&month) {
                return Err(invalid("month", month));
            }
            fields[8] = month;
            fields[1] = 0;
        }
    } else {
        fields[8] = -1;
    }
    if folded_year && !(1..=9999).contains(&fields[7]) {
        // Without an absolute month, some starting months can still carry the
        // temporary year back into range. Encode that same operation using a
        // legal absolute year plus an exact relative year; do not clamp its
        // result or change Delta's own constructor/calendar behavior.
        if fields[8] == -1
            && ((fields[7] == 0 && fields[1] > 0) || (fields[7] == 10000 && fields[1] < 0))
        {
            let anchor = fields[7].clamp(1, 9999);
            fields[0] = fields[7] - anchor;
            fields[7] = anchor;
        } else {
            return Err(invalid("year", fields[7]));
        }
    }
    if present & (1 << 9) != 0 && fields[9] != 0 {
        if fields[9] < 1 {
            return Err(invalid("day", fields[9]));
        }
        fields[9] = fields[9].min(31);
    } else {
        fields[9] = -1;
    }
    for (index, maximum) in [(11, 23), (12, 59), (13, 59), (14, 999_999)] {
        if present & (1 << index) != 0 && !(0..=maximum).contains(&fields[index]) {
            let name = ["hour", "minute", "second", "microsecond"][index - 11];
            return Err(invalid(name, fields[index]));
        }
    }
    Ok(fields)
}
