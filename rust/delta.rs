//! Exact nanosecond Delta values with checked Python protocol boundaries.
//! Storage and arithmetic have one native model; target adapters decide capacity
//! and final date/datetime/column precision. No legacy packed-us representation.

use pyo3::exceptions::PyOverflowError;
use pyo3::prelude::*;
use pyo3::types::{
    PyBool, PyDate, PyDateAccess, PyDateTime, PyDelta, PyDict, PyInt, PyList, PyString, PyTuple,
    PyType,
};
use std::borrow::Cow;
use std::cell::OnceCell;
use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};

mod fixed;
mod prepare;
mod runtime;
pub(crate) mod value;
pub(crate) use prepare::{
    FixedFractions, RelativeFields, normalize_relative_fields, relative_input,
};
pub(crate) use runtime::PreparedAddition;

static NATIVE_TUPLE_HASH: AtomicBool = AtomicBool::new(false);
/// Own one display string only on the registered ordinary-GIL base path.
/// Other runtimes never access this cell. PyO3 retains responsibility for the
/// owned string's destruction, including deferred decref outside an attachment.
struct RepresentationCache(OnceCell<Py<PyString>>);
// SAFETY: get/set are private unsafe entry points. Their callers prove the
// registered non-free-threaded GIL path before every access, retain the instance,
// and never keep a cell borrow across a Python call or a discarded value's Drop.
unsafe impl Sync for RepresentationCache {}

impl RepresentationCache {
    const fn new() -> Self {
        Self(OnceCell::new())
    }

    /// Clone a saved string without exposing a cell borrow.
    /// # Safety
    /// The caller holds the conventional GIL and a live registered base instance.
    #[inline(always)]
    unsafe fn get<'py>(&self, py: Python<'py>) -> Option<Bound<'py, PyString>> {
        self.0.get().map(|text| text.bind(py).clone())
    }

    /// Save the first completed display; drop a reentrant loser's value normally.
    /// # Safety
    /// The same GIL qualification must be checked after formatting callbacks.
    #[inline(always)]
    unsafe fn set(&self, _py: Python<'_>, text: Py<PyString>) {
        let _ = self.0.set(text);
    }
}

/// Enable allocation-free integer tuple hashing only for the verified interpreter.
///
/// Other interpreter versions and pointer widths retain Python's tuple hash.
pub(crate) fn configure_hash(py: Python<'_>) {
    prepare::configure_names(py);
    let version = py.version_info();
    NATIVE_TUPLE_HASH.store(
        cfg!(target_pointer_width = "64") && version.major == 3 && version.minor == 13,
        Ordering::Relaxed,
    );
}

/// An immutable calendar increment with relative amounts and optional field settings.
///
/// Parameters
/// ----------
/// years : int or SupportsIndex, default 0
///     Signed calendar years to add. Negative values reverse that direction; zero
///     is a real zero increment.
/// quarters : int or SupportsIndex, default 0
///     Signed calendar quarters to add. Negative values reverse that direction;
///     zero is a real zero increment.
/// months : int or SupportsIndex, default 0
///     Signed calendar months to add. Negative values reverse that direction; zero
///     is a real zero increment.
/// weeks : int, float or numpy.float16/float32/float64, default 0
///     Signed weeks to add. Negative values reverse that direction; zero is a real
///     zero increment. Fixed-duration floats are combined and rounded once to
///     nanoseconds.
/// days : int, float or numpy.float16/float32/float64, default 0
///     Signed days to add. Negative values reverse that direction; zero is a real
///     zero increment. Fixed-duration floats are combined and rounded once to
///     nanoseconds.
/// hours : int, float or numpy.float16/float32/float64, default 0
///     Signed hours to add. Negative values reverse that direction; zero is a real
///     zero increment. Fixed-duration floats are combined and rounded once to
///     nanoseconds.
/// minutes : int, float or numpy.float16/float32/float64, default 0
///     Signed minutes to add. Negative values reverse that direction; zero is a
///     real zero increment. Fixed-duration floats are combined and rounded once to
///     nanoseconds.
/// seconds : int, float or numpy.float16/float32/float64, default 0
///     Signed seconds to add. Negative values reverse that direction; zero is a
///     real zero increment. Fixed-duration floats are combined and rounded once to
///     nanoseconds.
/// milliseconds : int, float or numpy.float16/float32/float64, default 0
///     Signed milliseconds to add. Negative values reverse that direction; zero is
///     a real zero increment. Fixed-duration floats are combined and rounded once
///     to nanoseconds.
/// microseconds : int, float or numpy.float16/float32/float64, default 0
///     Signed microseconds to add. Negative values reverse that direction; zero is
///     a real zero increment. Fixed-duration floats are combined and rounded once
///     to nanoseconds.
/// nanoseconds : int, float or numpy.float16/float32/float64, keyword-only, default 0
///     Relative nanoseconds, combined exactly with all fixed-duration fields.
/// year : int | None, default None
///     Absolute year replacement. None leaves it unset; explicit integers must be
///     positive. Values above 9999 are limited to that maximum.
/// month : int | None, default None
///     Absolute month replacement. None leaves it unset; explicit integers must be
///     positive. Values above 12 are limited to that maximum.
/// day : int | None, default None
///     Absolute day replacement. None leaves it unset; explicit integers must be
///     positive. Values above 31 are limited to that maximum.
/// weekday : int | None, default None
///     Absolute weekday replacement in 0 (Monday) through 6 (Sunday). None leaves
///     it unset; zero is an actual setting. Floats and out-of-range numbers are
///     rejected.
/// hour : int | None, default None
///     Absolute hour replacement in 0 through 23. None leaves it unset; zero is an
///     actual setting. Floats and out-of-range numbers are rejected.
/// minute : int | None, default None
///     Absolute minute replacement in 0 through 59. None leaves it unset; zero is
///     an actual setting. Floats and out-of-range numbers are rejected.
/// second : int | None, default None
///     Absolute second replacement in 0 through 59. None leaves it unset; zero is
///     an actual setting. Floats and out-of-range numbers are rejected.
/// millisecond : int | None, default None
///     Absolute millisecond replacement in 0 through 999. None leaves it unset;
///     zero is an actual setting. Floats and out-of-range numbers are rejected.
/// microsecond : int | None, default None
///     Absolute microsecond replacement in 0 through 999999. None leaves it unset;
///     zero is an actual setting. Floats and out-of-range numbers are rejected. If
///     millisecond is also set, only the final three microsecond digits are used.
/// nanosecond : int | None, keyword-only, default None
///     Absolute tail after the six microsecond digits, in0..999. None leaves
///     this field unset; zero explicitly clears the source tail. Setting only
///     microsecond also clears the source tail when applied to a date.
///
/// Returns
/// -------
/// Delta
///     A completed instance of this class.
///
/// Notes
/// -----
/// Relative amounts add or subtract time; singular fields replace date or clock fields. None leaves an absolute field unset, while an explicit clock zero sets that field to zero. Positive year/month/day selections keep their upper limiting and month-end behavior. Other absolute fields require their stated ranges. Integer-like values such as NumPy integers are accepted for absolute fields; floats are rejected.
///
/// Fixed-duration fractions are combined and rounded once to nanoseconds, with halfway cases rounded to an even nanosecond. Relative years, quarters and months require the integer index protocol; floats are rejected. Public numeric fields reject boolean values. Fixed-duration inputs accept the listed real floating types and integer index values, not arbitrary numeric conversions. Calendar month moves need not be reversible: January 31 plus one month and then minus one month may finish on January 29.
///
/// Applying to datetime or Pydt rounds the complete target to microseconds
/// once, with ties to even. A date selects the containing calendar day.
/// Timestamp and column adapters retain nanoseconds; existing Pddt and Pldt
/// values keep their fixed unit and reject an inexact or overflowing result.
///
/// Values compare and hash by their fields with other Delta values. Fields cannot be changed in place; calling __init__ again leaves the existing value unchanged.
///
/// Examples
/// --------
/// >>> Delta(hour=None).hour is None
/// True
/// >>> Delta(hour=0).hour
/// 0
/// >>> from datetime import date
/// >>> date(2024, 1, 31) + Delta(months=1)
/// datetime.date(2024, 2, 29)
///
#[pyclass(frozen, subclass, immutable_type, module = "rstimes.delta")]
pub struct Delta {
    value: value::DeltaValue,
    hash_code: AtomicIsize,
    representation: RepresentationCache,
}
/// Read an integer without accepting truncating float or text conversions.
///
/// Native integers keep the direct extraction path. Other values may implement
/// Python's integer index protocol; its callback completes before native work.
#[inline]
pub(crate) fn index_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    if value.is_instance_of::<PyInt>() {
        return converted_integer(value);
    }
    // No callback exists in this case; this is our unsupported-input error.
    if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) == 0 } {
        return Err(crate::error_context::type_error("an integer is required"));
    }
    index_protocol_integer(value)
}

/// Run an already-proven index protocol once and preserve its original failure.
#[inline]
fn index_protocol_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    // SAFETY: the live input is borrowed under the GIL. PyNumber_Index returns
    // a new owned integer or an exception; Bound takes that ownership exactly once.
    let integer = unsafe {
        Bound::from_owned_ptr_or_err(value.py(), pyo3::ffi::PyNumber_Index(value.as_ptr()))
    }
    .map_err(crate::error_context::external)?;
    converted_integer(&integer)
}

/// Extract an already-qualified integer using the frozen width and error text.
///
/// The caller established PyInt membership or completed the numeric conversion.
/// # Errors
/// Propagates conversion errors and rejects inputs outside signed 64-bit range.
#[inline(always)]
pub(crate) fn converted_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    // SAFETY: the caller qualified this live value as an integer under the GIL.
    // The public API checks signed 64-bit range without reading private payloads.
    let number = unsafe { pyo3::ffi::PyLong_AsLongLong(value.as_ptr()) };
    if number == -1 && unsafe { !pyo3::ffi::PyErr_Occurred().is_null() } {
        let error = crate::error_context::fetch(value.py());
        if error.is_instance_of::<PyOverflowError>(value.py()) {
            return Err(crate::error_context::overflow(
                "Python int too large to convert to C long",
            ));
        }
        return Err(error);
    }
    Ok(number as i64)
}

fn append_integer(text: &mut String, value: i64) {
    let mut digits = [0_u8; 20];
    let mut cursor = digits.len();
    let mut number = value.unsigned_abs();
    loop {
        cursor -= 1;
        digits[cursor] = b'0' + (number % 10) as u8;
        number /= 10;
        if number == 0 {
            break;
        }
    }
    if value < 0 {
        text.push('-');
    }
    text.extend(digits[cursor..].iter().map(|digit| char::from(*digit)));
}

/// Format the fixed native class name and integer fields without a temporary heap string.
///
/// All labels are ASCII and fields are validated integers. The 512-byte stack
/// buffer exceeds the maximum 17-field native representation; checked slices
/// retain a bounded error path if the internal labels ever grow.
///
/// # Errors
/// Raises RuntimeError for an inconsistent internal buffer; allocation errors
/// from the public Python Unicode constructor propagate unchanged.
fn exact_representation<'py>(
    py: Python<'py>,
    fields: &[i64; 17],
    names: &[&str; 17],
) -> PyResult<Bound<'py, PyString>> {
    let mut bytes = [0_u8; 512];
    let mut length = 0;
    let mut append = |text: &[u8]| -> PyResult<()> {
        let end = length + text.len();
        bytes
            .get_mut(length..end)
            .ok_or_else(|| crate::error_context::runtime("Delta representation buffer exceeded"))?
            .copy_from_slice(text);
        length = end;
        Ok(())
    };
    append(b"<'Delta' (")?;
    let mut separated = false;
    for (index, (&name, &value)) in names.iter().zip(fields).enumerate() {
        if (index < 8 && value == 0) || (index >= 8 && value == -1) {
            continue;
        }
        if separated {
            append(b", ")?;
        }
        separated = true;
        append(name.as_bytes())?;
        append(b"=")?;
        if index == 11 {
            append([b"MO", b"TU", b"WE", b"TH", b"FR", b"SA", b"SU"][value as usize])?;
        } else {
            if value < 0 {
                append(b"-")?;
            }
            let mut digits = [0_u8; 20];
            let mut cursor = digits.len();
            let mut number = value.unsigned_abs();
            loop {
                cursor -= 1;
                digits[cursor] = b'0' + (number % 10) as u8;
                number /= 10;
                if number == 0 {
                    break;
                }
            }
            append(&digits[cursor..])?;
        }
    }
    append(b")>")?;
    // SAFETY: Only fixed ASCII labels, punctuation and integer digits were
    // appended. The checked buffer remains live through this public API call,
    // which copies its one-byte code points into an owned Unicode object.
    // Subclass names keep the separate Unicode-aware path below.
    let value = unsafe {
        pyo3::ffi::PyUnicode_FromKindAndData(
            pyo3::ffi::PyUnicode_1BYTE_KIND as std::ffi::c_int,
            bytes.as_ptr().cast(),
            length as pyo3::ffi::Py_ssize_t,
        )
    };
    let value = unsafe { Bound::from_owned_ptr_or_err(py, value) }?;
    // The public constructor guarantees a Unicode result after a non-null return.
    Ok(unsafe { value.cast_into_unchecked::<PyString>() })
}

#[pymethods]
impl Delta {
    /// Keep NumPy scalar operands intact until reflected Delta dispatch.
    #[classattr]
    fn __array_priority__() -> f64 {
        1000.0
    }
    /// Create a Delta from supported relativedelta fields.
    ///
    /// Parameters
    /// ----------
    /// rd : dateutil.relativedelta
    ///     Relative amounts and absolute settings to convert.
    ///
    /// Returns
    /// -------
    /// Delta
    ///     A new Delta, including when called through a Delta subclass.
    ///
    /// Raises
    /// ------
    /// ImportError
    ///     Optional python-dateutil is missing; install rsTimes[dateutil] and restart Python.
    /// TypeError
    ///     rd is not a relativedelta instance.
    /// ValueError
    ///     weekday is set or leapdays is nonzero; Delta cannot preserve those rules.
    /// OverflowError
    ///     A converted value or calculation is outside the supported integer range.
    ///
    /// Notes
    /// -----
    /// Fields follow the source relativedelta meaning: date zero means unset,
    /// clock zero is an explicit replacement, and relative years/months are applied
    /// before limiting a destination day. Unrepresentable rules are rejected.
    /// Raw fields are read directly; custom normalized() methods are not called.
    /// Fixed-duration fractions use the same exact nanosecond preparation as Delta().
    /// The returned value follows Delta's own date, fold and arithmetic rules;
    /// it is not a transparent replacement for every source operation.
    /// Errors from actual field access or numeric conversion reach the caller.
    ///
    /// Examples
    /// --------
    /// >>> from dateutil.relativedelta import relativedelta
    /// >>> Delta.from_relativedelta(relativedelta(months=1)).months
    /// 1
    #[classmethod]
    pub(crate) fn from_relativedelta(
        _class: &Bound<'_, PyType>,
        rd: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        crate::interop::relativedelta_fields(rd)
            .and_then(Self::from_fields)
            .map_err(|error| {
                crate::error_context::argument(rd.py(), error, "Delta.from_relativedelta", "rd", rd)
            })
    }
    /// Convert this Delta to a standard-library time span.
    ///
    /// Parameters
    /// ----------
    /// start : date or datetime, optional
    ///     Starting value for calendar years, months or absolute replacements.
    ///     With a start, the result is (start + self) - start.
    ///
    /// Returns
    /// -------
    /// datetime.timedelta
    ///     The fixed span, or the difference at the supplied starting value.
    ///
    /// Raises
    /// ------
    /// ValueError
    ///     No start was supplied for years, months or an absolute replacement.
    /// TypeError
    ///     start is not a date or datetime.
    /// OverflowError
    ///     The fixed span is outside timedelta's supported range.
    ///
    /// Notes
    /// -----
    /// A date start gives a whole-day difference. For datetimes in the same
    /// time zone, Python's wall-clock subtraction rules apply across clock changes.
    /// Standard pandas Timestamp anchors instead use elapsed instants, preserving
    /// nanoseconds and long spans until the final standard timedelta is created.
    /// Custom arithmetic methods retain control over their own results.
    /// Months are never approximated as a fixed number of days. Errors from
    /// applying the Delta to the starting value propagate.
    /// A nanosecond difference is rounded once to the nearest microsecond,
    /// with ties going to the even microsecond. Other timedelta subclasses
    /// are returned as a standard datetime.timedelta with the same span.
    ///
    /// Examples
    /// --------
    /// >>> Delta(hours=25).to_timedelta()
    /// datetime.timedelta(days=1, seconds=3600)
    /// >>> Delta(months=1).to_timedelta(date(2024, 1, 31))
    /// datetime.timedelta(days=29)
    #[pyo3(signature = (start=None))]
    pub(crate) fn to_timedelta<'py>(
        slf: &Bound<'py, Self>,
        start: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyDelta>> {
        let py = slf.py();
        (|| {
            if let Some(start) = start {
                crate::interop::reject_nat(start, "Delta.to_timedelta", "start")?;
                if !start.is_instance_of::<PyDate>() {
                    return Err(crate::error_context::type_error(
                        "start must be a date or datetime",
                    ));
                }
                if slf.is_exact_instance_of::<Self>()
                    && let Some(span) = crate::interop::builtin_span(slf.get(), start)?
                {
                    return Ok(span);
                }
                if let Some(span) = crate::interop::timestamp_span(slf, start)? {
                    return Ok(span);
                }
                let target = start.add(slf).map_err(crate::error_context::external)?;
                let difference = target.sub(start).map_err(crate::error_context::external)?;
                let difference = difference.cast_into::<PyDelta>().map_err(|_| {
                    crate::error_context::type_error("start arithmetic did not produce a timedelta")
                })?;
                return crate::interop::standard_span(&difference);
            }
            slf.get().fixed_timedelta(py)
        })()
        .map_err(|error| {
            let none = py.None();
            crate::error_context::argument(
                py,
                error,
                "Delta.to_timedelta",
                "start",
                start.unwrap_or(none.bind(py)),
            )
        })
    }
    /// Add this Delta to each value and return the results in order.
    /// NumPy inputs retain ordinary value + Delta return types and exceptions.
    ///
    /// Parameters
    /// ----------
    /// values : iterable
    ///     Values supporting value + self, including dates, datetimes, Delta,
    ///     timedelta, supported third-party scalars, or a mixture of these.
    ///
    /// Returns
    /// -------
    /// list
    ///     One result per input, with the same values and types as
    ///     [value + self for value in values]. An empty input returns [].
    ///
    /// Raises
    /// ------
    /// TypeError
    ///     values is not iterable or an item does not support addition.
    /// Exception
    ///     Errors from iteration or addition propagate. No partial list is
    ///     returned; a consumed iterator is not rewound.
    ///
    /// Examples
    /// --------
    /// >>> Delta(days=1).apply_many([date(2024, 1, 1), date(2024, 1, 2)])
    /// [datetime.date(2024, 1, 2), datetime.date(2024, 1, 3)]
    fn apply_many<'py>(
        slf: &Bound<'py, Self>,
        values: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyList>> {
        crate::bulk::apply(slf, values)
    }

    /// Create a fully initialized Delta value.
    ///
    /// The arguments are the same as Delta(...). Calling this method directly
    /// also returns a complete value; there is no empty initialization stage.
    #[new]
    #[pyo3(signature = (*args, **kwargs), text_signature = "(years=0, quarters=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0, year=None, month=None, day=None, weekday=None, hour=None, minute=None, second=None, millisecond=None, microsecond=None, *, nanoseconds=0, nanosecond=None)")]
    fn new(args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        Self::construct(args, kwargs)
    }

    /// Leave the value unchanged after construction.
    ///
    /// Notes
    /// -----
    /// Values are set by __new__. Calling __init__ again does not change any
    /// field or the object's hash. Construct a new Delta to use different values.
    #[pyo3(signature = (*args, **kwargs))]
    pub(crate) fn __init__(&self, args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) {
        let _ = (args, kwargs);
    }

    /// Return whether a relative field is nonzero or an absolute field is set.
    ///
    /// Explicit absolute zero is set and therefore makes a Delta truthy.
    pub(crate) fn __bool__(&self) -> bool {
        self.value.is_nonzero()
    }

    /// Compare the values of two Delta objects.
    ///
    /// Returns
    /// -------
    /// bool or NotImplemented
    ///     Whether all relative and absolute fields match. Other object types
    ///     return NotImplemented and follow Python's reflected comparison rules.
    ///
    /// Notes
    /// -----
    /// Delta subclasses that inherit equality, inequality and hashing use the same value rules.
    /// Equal Delta values have equal hashes and can share dictionary keys.
    pub(crate) fn __eq__<'py>(
        slf: &Bound<'py, Self>,
        other: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let py = other.py();
        if !crate::protocol::same_value_semantics(slf, other)? {
            return Ok(py.NotImplemented().into_bound(py));
        }
        let Ok(rhs) = other.cast::<Self>() else {
            return Ok(py.NotImplemented().into_bound(py));
        };
        Ok(PyBool::new(py, slf.get().native_eq(rhs.get()))
            .to_owned()
            .into_any())
    }

    /// Compare two Delta values for inequality.
    ///
    /// Returns
    /// -------
    /// bool or NotImplemented
    ///     The opposite of equality. A subclass overriding __eq__ inherits its
    ///     opposite here unless it defines __ne__ itself. Direct calls preserve
    ///     NotImplemented and equality callback exceptions.
    pub(crate) fn __ne__<'py>(
        slf: &Bound<'py, Self>,
        other: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let py = other.py();
        // Ordinary inherited values need only their existing semantic check.
        // Delegate to Python equality only when that native path does not apply.
        if crate::protocol::same_value_semantics(slf, other)?
            && let Ok(rhs) = other.cast::<Self>()
        {
            return Ok(PyBool::new(py, !slf.get().native_eq(rhs.get()))
                .to_owned()
                .into_any());
        }
        if let Some(result) = crate::protocol::inherited_inequality(slf, other)? {
            return Ok(result);
        }
        Ok(py.NotImplemented().into_bound(py))
    }

    /// Return a separate object with the same Delta value and type.
    ///
    /// Returns
    /// -------
    /// Delta
    ///     A shallow copy. Additional dictionary and slot attribute values remain shared.
    fn __copy__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::copy_object(slf, None).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__copy__",
                "arguments",
                slf.as_any(),
            )
        })
    }
    /// Return a distinct deep copy, preserving subtype and tracking cycles.
    ///
    /// Parameters
    /// ----------
    /// memo : dict
    ///     Python deepcopy's object-identity table, reused for recursion.
    ///
    /// Raises
    /// ------
    /// Exception
    ///     Allocation, subclass and recursive deepcopy errors propagate.
    fn __deepcopy__<'py>(
        slf: &Bound<'py, Self>,
        memo: &Bound<'py, PyDict>,
    ) -> PyResult<Bound<'py, PyAny>> {
        crate::state::copy_object(slf, Some(memo)).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__deepcopy__",
                "memo",
                memo.as_any(),
            )
        })
    }

    /// Return the saved fields and additional attributes used by this package.
    ///
    /// Returns
    /// -------
    /// tuple
    ///     ("rstimes.delta",2,core17,metadata), with no derived caches.
    ///
    /// Notes
    /// -----
    /// Use pickle or copy for ordinary saving and copying. Subclass dictionary
    /// and slot attributes are included. The17 fields include relative ns and
    /// independently present absolute ns. Version1 and old byte formats are
    /// rejected by the new implementation; they are not automatically migrated.
    fn __getstate__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::capture(slf).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__getstate__",
                "arguments",
                slf.as_any(),
            )
        })
    }
    /// Restore saved extra attributes while keeping this Delta value.
    ///
    /// Parameters
    /// ----------
    /// state : tuple, dict or None
    ///     State returned by this package, or the extra attributes used by pickle.
    ///
    /// Returns
    /// -------
    /// None
    ///
    /// Raises
    /// ------
    /// TypeError
    ///     The state has unsupported containers or value types.
    /// ValueError
    ///     The state is invalid or tries to change the Delta's fields.
    /// OverflowError
    ///     A saved integer is too large.
    ///
    /// Notes
    /// -----
    /// The object's value and hash cannot be replaced. Only load pickle data from
    /// trusted sources. Errors from subclass attribute handling are passed through.
    fn __setstate__(slf: &Bound<'_, Self>, state: &Bound<'_, PyAny>) -> PyResult<()> {
        crate::state::restore(slf, state).map_err(|error| {
            crate::error_context::argument(slf.py(), error, "Delta.__setstate__", "state", state)
        })
    }
    /// Return the recipe used by pickle to save this Delta.
    ///
    /// Parameters
    /// ----------
    /// protocol : int
    ///     The protocol selected by pickle.
    ///
    /// Returns
    /// -------
    /// tuple
    ///     A reconstruction recipe that preserves the value and additional attributes.
    ///
    /// Notes
    /// -----
    /// Only load pickle data from trusted sources.
    fn __reduce_ex__<'py>(slf: &Bound<'py, Self>, _protocol: i32) -> PyResult<Bound<'py, PyAny>> {
        crate::state::reduce_ex(slf).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__reduce_ex__",
                "arguments",
                slf.as_any(),
            )
        })
    }
    /// Return the reconstruction recipe used by pickle.
    ///
    /// Returns
    /// -------
    /// tuple
    ///     The same recipe as __reduce_ex__.
    ///
    /// Notes
    /// -----
    /// Only load pickle data from trusted sources.
    fn __reduce__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::reduce(slf).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__reduce__",
                "arguments",
                slf.as_any(),
            )
        })
    }

    /// Return a stable hash based on the Delta value.
    ///
    /// Returns
    /// -------
    /// int
    ///     Equal Delta values have equal hashes.
    ///
    /// Notes
    /// -----
    /// Additional subclass attributes do not change the Delta value or its hash.
    #[inline]
    pub(crate) fn __hash__(&self, py: Python<'_>) -> PyResult<isize> {
        let cached = self.hash_code.load(Ordering::Relaxed);
        if cached != -1 {
            return Ok(cached);
        }
        self.compute_hash(py)
    }

    /// Return the runtime class name and set fields in the frozen display order.
    ///
    /// Zero relative fields and unset absolute fields are omitted; weekdays use MO
    /// through SU. __str__ resolves to the same representation.
    pub(crate) fn __repr__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyString>> {
        let py = slf.py();
        // SAFETY: slf owns a live instance. A registered cache type proves the
        // conventional GIL path; SDK exact-type fallback never grants cell access.
        let cached_exact = unsafe { crate::protocol::is_cached_exact_delta(slf.as_ptr()) };
        let exact = cached_exact || slf.is_exact_instance_of::<Self>();
        if cached_exact && let Some(text) = unsafe { slf.get().representation.get(py) } {
            return Ok(text);
        }
        let fields = slf.get().snapshot();
        let names = [
            "years",
            "months",
            "days",
            "hours",
            "minutes",
            "seconds",
            "microseconds",
            "nanoseconds",
            "year",
            "month",
            "day",
            "weekday",
            "hour",
            "minute",
            "second",
            "microsecond",
            "nanosecond",
        ];
        if exact {
            // Only the immutable base caches its own display. Subclasses keep
            // their observable name lookups. A Python string has no back-edge
            // to this value; PyO3 drops the owned reference before storage reuse.
            // Compute before claiming the one-time cell. This avoids detaching
            // for uncontended first formatting and permits safe reentrant lookup.
            // A reentrant winner has the same immutable fields; set() then drops
            // the unused owned string without replacing the saved one.
            let text = exact_representation(py, &fields, &names)?.unbind();
            // Formatting can reenter or destroy the cache owner. Recheck its
            // GIL qualification before touching the cell; otherwise return the
            // complete string through the standard SDK ownership path.
            if !unsafe { crate::protocol::is_cached_exact_delta(slf.as_ptr()) } {
                return Ok(text.into_bound(py));
            }
            // SAFETY: the refreshed qualification and live slf prove the GIL
            // contract. Neither cell operation retains a borrow across callbacks.
            unsafe { slf.get().representation.set(py, text) };
            return unsafe { slf.get().representation.get(py) }.ok_or_else(|| {
                crate::error_context::runtime("Delta representation was not initialized")
            });
        }
        // Subclasses retain observable class/name lookup and Unicode conversion.
        let class_name = slf
            .as_any()
            .getattr(pyo3::intern!(py, "__class__"))
            .map_err(crate::error_context::external)?
            .getattr(pyo3::intern!(py, "__name__"))
            .map_err(crate::error_context::external)?;
        let class = class_name.extract::<Cow<'_, str>>()?;
        let mut text = String::with_capacity(256);
        text.push_str("<'");
        text.push_str(&class);
        text.push_str("' (");
        let mut separated = false;
        for (index, (&name, &value)) in names.iter().zip(&fields).enumerate() {
            if (index < 8 && value == 0) || (index >= 8 && value == -1) {
                continue;
            }
            if separated {
                text.push_str(", ");
            }
            separated = true;
            if index == 11 {
                text.push_str("weekday=");
                text.push_str(["MO", "TU", "WE", "TH", "FR", "SA", "SU"][value as usize]);
            } else {
                text.push_str(name);
                text.push('=');
                append_integer(&mut text, value);
            }
        }
        text.push_str(")>");
        Ok(PyString::new(py, &text))
    }

    /// Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Increment or date operand; NumPy arrays are unsupported.
    ///
    /// Returns
    /// -------
    /// Delta | date | datetime | NotImplemented
    ///     A base Delta for increment operands,
    ///         the input date subtype for Python dates, or a naive builtin datetime for
    ///         NumPy datetime64. Unsupported operands return NotImplemented.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     Numeric conversion or calendar arithmetic overflows.
    /// ValueError
    ///     Invalid dates or NumPy NaT. Custom constructor errors propagate unchanged.
    /// Exception
    ///     Third-party conversion and other Python callback errors propagate.
    ///
    /// Notes
    /// -----
    /// Date operations apply absolute fields, relative increments, then weekday;
    /// datetime timezone and fold are preserved. Pandas Timestamp nanoseconds are
    /// retained unless an absolute microsecond or millisecond setting replaces
    /// the fractional second. Arrays are not supported.
    pub(crate) fn __add__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        // Delta operands cannot also have datetime's incompatible native layout.
        // Resolve the native increment pair before entering the date adapter.
        if let Ok(rhs) = other.cast::<Self>() {
            return Bound::new(other.py(), self.combine(&rhs.borrow(), false)?)
                .map(Bound::into_any);
        }
        if let Some(result) = crate::interop::apply_date(self, other, 1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, false, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::read_relative_fields(other)?,
                    false,
                    false,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some(value) = crate::numpy_scalar::delta_scalar(other, true)? {
            return self.apply_numpy(other.py(), value, false, false, false);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Apply reflected addition using the same date and duration rules as __add__.
    ///
    /// NumPy may convert a left-hand scalar before reflected dispatch. An
    /// expression such as value + delta can pass a different type from a direct
    /// delta.__radd__(value) call.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Left-hand date, duration or relativedelta operand.
    ///
    /// A direct reflected call with another Delta returns NotImplemented. Conversion,
    /// calendar and custom-constructor errors follow __add__.
    pub(crate) fn __radd__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(result) = crate::interop::apply_date(self, other, 1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, false, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::read_relative_fields(other)?,
                    false,
                    true,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some(value) = crate::numpy_scalar::delta_scalar(other, true)? {
            return self.apply_numpy(other.py(), value, false, true, false);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Left-hand date, duration or relativedelta operand.
    ///
    /// relativedelta is also supported; direct reflected Delta calls return
    /// NotImplemented. Return types and calendar errors follow reflected dispatch,
    /// with OverflowError for unrepresentable negation or subtraction.
    pub(crate) fn __rsub__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(result) = crate::interop::apply_date(self, other, -1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, true, true)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::read_relative_fields(other)?,
                    true,
                    true,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some(value) = crate::numpy_scalar::delta_scalar(other, true)? {
            return self.apply_numpy(other.py(), value, true, true, false);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Increment to subtract; dates are unsupported here.
    ///
    /// Returns
    /// -------
    /// Delta | NotImplemented
    ///     A base Delta or NotImplemented for unsupported types,
    ///         including dates and NumPy datetime64 in this direction.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     Numeric conversion, subtraction or normalization overflows.
    /// Exception
    ///     Third-party conversion and Python callback errors propagate.
    pub(crate) fn __sub__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Ok(date) = other.cast::<PyDateTime>()
            && date.get_year() == 1
        {
            crate::interop::reject_nat(other, "Delta.__sub__", "other")?;
        }
        if let Ok(rhs) = other.cast::<Self>() {
            return Bound::new(other.py(), self.combine(&rhs.borrow(), true)?).map(Bound::into_any);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, true, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::read_relative_fields(other)?,
                    true,
                    false,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some(value) = crate::numpy_scalar::delta_scalar(other, false)? {
            return self.apply_numpy(other.py(), value, true, false, false);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Negate relative components and retain absolute replacements in a new Delta.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     A relative component cannot be negated or normalized.
    #[inline(always)]
    pub(crate) fn __neg__(&self) -> PyResult<Self> {
        self.value
            .negated()
            .map(Self::from_value)
            .map_err(prepare::python_error)
    }

    /// Return a new Delta with the frozen grouped-sign absolute-value behavior.
    ///
    /// Year/month and day/time groups use their leading normalized component's sign;
    /// absolute replacement fields are retained.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     Required negation or normalization cannot be represented.
    #[inline(always)]
    pub(crate) fn __abs__(&self) -> PyResult<Self> {
        self.value
            .magnitude()
            .map(Self::from_value)
            .map_err(prepare::python_error)
    }

    /// int: Normalized relative years; months are carried into this value.
    #[getter]
    fn years(&self) -> i64 {
        self.relative(0)
    }
    /// int: Relative months after grouping years, in 0..11.
    #[getter]
    fn months(&self) -> i64 {
        self.relative(1)
    }
    /// int: Relative days, including normalized weeks and clock carries.
    #[getter]
    fn days(&self) -> i64 {
        self.relative(2)
    }
    /// int: Normalized relative hours, in 0..23.
    #[getter]
    fn hours(&self) -> i64 {
        self.relative(3)
    }
    /// int: Normalized relative minutes, in 0..59.
    #[getter]
    fn minutes(&self) -> i64 {
        self.relative(4)
    }
    /// int: Normalized relative seconds, in 0..59.
    #[getter]
    fn seconds(&self) -> i64 {
        self.relative(5)
    }
    /// int: Normalized relative microseconds, in 0..999999.
    #[getter]
    fn microseconds(&self) -> i64 {
        self.relative(6)
    }
    /// int | None: Absolute year replacement, or None when unset.
    #[getter]
    fn year(&self) -> Option<i64> {
        self.absolute(8)
    }
    /// int | None: Absolute month replacement (1..12), or None when unset.
    #[getter]
    fn month(&self) -> Option<i64> {
        self.absolute(9)
    }
    /// int | None: Absolute day replacement (1..31), or None when unset.
    #[getter]
    fn day(&self) -> Option<i64> {
        self.absolute(10)
    }
    /// int | None: Absolute weekday replacement (Monday=0 to Sunday=6), or None.
    #[getter]
    fn weekday(&self) -> Option<i64> {
        self.absolute(11)
    }
    /// int | None: Absolute hour replacement (0..23), or None when unset.
    #[getter]
    fn hour(&self) -> Option<i64> {
        self.absolute(12)
    }
    /// int | None: Absolute minute replacement (0..59), or None when unset.
    #[getter]
    fn minute(&self) -> Option<i64> {
        self.absolute(13)
    }
    /// int | None: Absolute second replacement (0..59), or None when unset.
    #[getter]
    fn second(&self) -> Option<i64> {
        self.absolute(14)
    }
    /// int | None: Absolute microsecond replacement (0..999999), or None.
    #[getter]
    fn microsecond(&self) -> Option<i64> {
        self.absolute(15)
    }
    /// int: Normalized relative nanosecond tail, in0..999.
    #[getter]
    fn nanoseconds(&self) -> i64 {
        self.relative(7)
    }
    /// int | None: Absolute nanosecond tail, or None when unset.
    #[getter]
    fn nanosecond(&self) -> Option<i64> {
        self.absolute(16)
    }
}
