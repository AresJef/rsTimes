//! Read NumPy's checked public datetime scalar prefix and convert its units.
//!
//! Only actual datetime64/timedelta64 scalar types reach the layout cast. This
//! module preserves the frozen multiplier, NaT and unsupported-unit behavior;
//! it does not add an array interface or promise arbitrary NumPy ABI compatibility.

use pyo3::exceptions::{PyOverflowError, PyTypeError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDateTime, PyType};

static TYPES: PyOnceLock<(Py<PyType>, Py<PyType>)> = PyOnceLock::new();

/// Interpreter-owned exact scalar identities, captured once for a native batch.
pub(crate) struct ExactTypes {
    date: *mut pyo3::ffi::PyTypeObject,
    duration: *mut pyo3::ffi::PyTypeObject,
}

impl ExactTypes {
    /// Reuse initialized identities without importing or touching Python values.
    pub(crate) fn cached(py: Python<'_>) -> Option<Self> {
        TYPES.get(py).map(|(date, duration)| Self {
            date: date.bind(py).as_type_ptr(),
            duration: duration.bind(py).as_type_ptr(),
        })
    }

    /// Test exact native identity; subclass methods must retain Python dispatch.
    pub(crate) fn matches(&self, value: &Bound<'_, PyAny>) -> bool {
        // SAFETY: All identities are live under the attached interpreter.
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        actual == self.date || actual == self.duration
    }

    /// Initialize only for a plausible NumPy first item; identity remains the gate.
    /// # Errors
    /// Propagates the same NumPy import/type errors as ordinary scalar conversion.
    pub(crate) fn for_first(value: &Bound<'_, PyAny>) -> PyResult<Option<Self>> {
        let py = value.py();
        // SAFETY: A live ready Python type owns a null-terminated tp_name. This
        // name is only an import hint; exact cached identity guards payload reads.
        let name =
            unsafe { std::ffi::CStr::from_ptr((*pyo3::ffi::Py_TYPE(value.as_ptr())).tp_name) };
        if !matches!(name.to_bytes(), b"numpy.datetime64" | b"numpy.timedelta64") {
            return Ok(None);
        }
        let (date, duration) = scalar_types(py)?;
        let types = Self {
            date: date.bind(py).as_type_ptr(),
            duration: duration.bind(py).as_type_ptr(),
        };
        // SAFETY: All pointers remain live under the attached interpreter.
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        Ok((actual == types.date || actual == types.duration).then_some(types))
    }

    /// Decode a proven exact scalar without repeated Python type/cache operations.
    /// # Errors
    /// Retains all unit conversion, overflow and unsupported-unit errors.
    #[inline]
    pub(crate) fn microseconds(&self, value: &Bound<'_, PyAny>) -> PyResult<Option<(i64, bool)>> {
        // SAFETY: The live actual type is compared to interpreter-owned identities
        // before reading the verified public scalar prefix. Subclasses fall back.
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        if actual != self.date && actual != self.duration {
            return Ok(None);
        }
        convert_scalar(value, actual == self.date).map(Some)
    }
}

/// Cache the real NumPy scalar types without changing dependency versions.
/// # Errors
/// Preserves module and attribute errors from the existing scalar entrance.
fn scalar_types(py: Python<'_>) -> PyResult<&(Py<PyType>, Py<PyType>)> {
    TYPES.get_or_try_init(py, || -> PyResult<_> {
        let module = py.import("numpy")?;
        Ok((
            module
                .getattr("datetime64")?
                .cast_into::<PyType>()?
                .unbind(),
            module
                .getattr("timedelta64")?
                .cast_into::<PyType>()?
                .unbind(),
        ))
    })
}
#[repr(C)]
struct Metadata {
    unit: std::ffi::c_int,
    multiplier: std::ffi::c_int,
}
#[repr(C)]
struct Scalar {
    object: pyo3::ffi::PyObject,
    value: i64,
    metadata: Metadata,
}

/// Create the common OverflowError for checked NumPy scalar conversion.
fn overflow() -> PyErr {
    PyOverflowError::new_err("integer overflow in NumPy scalar conversion")
}
/// Multiply NumPy ticks by a unit factor using checked i64 arithmetic.
///
/// # Errors
/// Raises OverflowError when the product cannot be represented.
fn mul(value: i64, factor: i64) -> PyResult<i64> {
    value.checked_mul(factor).ok_or_else(overflow)
}

/// Read a checked NumPy datetime64/timedelta64 scalar as microseconds.
///
/// # Arguments
/// allow_datetime controls whether datetime64 participates in this dispatch.
///
/// # Returns
/// Some((microseconds, is_datetime)) for a supported scalar; None for other types
/// or a datetime scalar rejected by allow_datetime. Negative nanoseconds use
/// floor division. Frozen unit-multiplier and NaT behavior are retained rather
/// than replaced with NumPy array semantics.
///
/// # Errors
/// Raises OverflowError on unrepresentable conversions and TypeError for the
/// frozen unsupported-unit path. NumPy import/type-check errors propagate.
///
/// # Layout contract
/// The actual scalar type is checked before reading the public C scalar prefix.
/// The prefix is validated against the NumPy headers in the accepted environment.
pub fn microseconds(
    value: &Bound<'_, PyAny>,
    allow_datetime: bool,
) -> PyResult<Option<(i64, bool)>> {
    let py = value.py();
    if let Some(types) = ExactTypes::cached(py) {
        // SAFETY: The attached interpreter owns the initialized scalar types.
        // Exact identity permits the same checked decoder without two subclass
        // checks. Missing caches and subclasses retain the original path below.
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        if actual == types.date {
            if !allow_datetime {
                return Ok(None);
            }
            return convert_scalar(value, true).map(Some);
        }
        if actual == types.duration {
            return convert_scalar(value, false).map(Some);
        }
    }
    let (date_type, duration_type) = scalar_types(py)?;
    let actual = value.get_type();
    let datetime = if actual.is_subclass(date_type.bind(py))? {
        true
    } else if actual.is_subclass(duration_type.bind(py))? {
        false
    } else {
        return Ok(None);
    };
    if datetime && !allow_datetime {
        return Ok(None);
    }
    convert_scalar(value, datetime).map(Some)
}

/// Read the verified scalar prefix after actual type identity/inheritance checks.
/// # Preconditions
/// The caller proved the actual object has the NumPy scalar layout.
/// # Errors
/// Preserves checked conversion and frozen unsupported-unit exceptions.
#[inline]
fn convert_scalar(value: &Bound<'_, PyAny>, datetime: bool) -> PyResult<(i64, bool)> {
    // NumPy arrayscalars.h defines the same PyObject + i64 + metadata prefix
    // for both scalar types. Actual PyType inheritance is checked above, so a
    // forged __class__ cannot reach this cast. `value` keeps the object alive.
    // Only read, and only while CPython is attached. ABI offsets were checked
    // against the installed public C headers (numpy-layout-c.json).
    let scalar = unsafe { &*value.as_ptr().cast::<Scalar>() };
    let (ticks, unit) = (scalar.value, scalar.metadata.unit);
    let converted = match unit {
        10 => ticks.div_euclid(1_000),
        9 => ticks,
        8 => mul(ticks, 1_000)?,
        7 => mul(ticks, 1_000_000)?,
        6 => mul(ticks, 60_000_000)?,
        5 => mul(ticks, 3_600_000_000)?,
        4 => mul(ticks, 86_400_000_000)?,
        2 => mul(mul(ticks, 86_400_000_000)?, 7)?,
        0 | 1 if !datetime => mul(
            ticks,
            if unit == 0 {
                31_556_952_000_000
            } else {
                2_629_746_000_000
            },
        )?,
        0 | 1 => {
            let years = if unit == 0 {
                ticks
            } else {
                ticks.div_euclid(12)
            };
            let month = if unit == 0 {
                1
            } else {
                ticks.rem_euclid(12) + 1
            };
            let year = years.checked_add(1970).ok_or_else(overflow)?;
            // Preserve the source's original-width intermediate overflow policy.
            mul(years, 365)?;
            let previous = year.checked_sub(1).ok_or_else(overflow)?;
            let before_year = mul(previous, 365)?
                .checked_add(previous.div_euclid(4))
                .ok_or_else(overflow)?
                .checked_sub(previous.div_euclid(100))
                .ok_or_else(overflow)?
                .checked_add(previous.div_euclid(400))
                .ok_or_else(overflow)?;
            let month_days =
                [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][(month - 1) as usize];
            let ordinal = before_year
                .checked_add(month_days)
                .and_then(|value| {
                    value.checked_add(i64::from(month > 2 && crate::calendar::leap(year)))
                })
                .and_then(|value| value.checked_add(1))
                .ok_or_else(overflow)?;
            let days = ordinal.checked_sub(719_163).ok_or_else(overflow)?;
            mul(days, 86_400_000_000)?
        }
        _ => {
            // The frozen helper assigns type(value) to a Cython str before
            // formatting its error. Preserve this observable TypeError.
            return Err(PyTypeError::new_err("Expected str, got type"));
        }
    };
    // Deliberately ignore metadata.multiplier, as the frozen Delta does.
    Ok((converted, datetime))
}

// NumPy scalars always produce a builtin naive datetime. Work on its validated
// parts directly, so the ordinary path allocates only the final result rather
// than an intermediate datetime followed by a second datetime.
/// Apply Delta to Unix microseconds and allocate only the final naive datetime.
///
/// # Errors
/// Propagates conversion/calendar overflow and Python datetime range errors.
/// The source date's range is checked before absolute Delta replacements.
pub fn apply_datetime_us<'py>(
    py: Python<'py>,
    delta: &crate::delta::Delta,
    value: i64,
    sign: i64,
) -> PyResult<Bound<'py, PyAny>> {
    apply_datetime_fields_us(py, &delta.snapshot(), !delta.__bool__(), value, sign)
}

/// Apply a captured immutable field set to a verified NumPy instant.
/// # Errors
/// Preserves original input date checks, calendar overflow and allocation errors.
pub(crate) fn apply_datetime_fields_us<'py>(
    py: Python<'py>,
    fields: &[i64; 15],
    empty: bool,
    value: i64,
    sign: i64,
) -> PyResult<Bound<'py, PyAny>> {
    let parts = datetime_parts(value)?;
    if !(1..=9999).contains(&parts[0]) {
        // Preserve the original Python constructor's exact range error before
        // applying any Delta replacement, including extreme NumPy dates.
        return datetime_from_us(py, value).map(Bound::into_any);
    }
    let result = if !empty {
        crate::calendar::apply(fields, parts, sign, true)
            .map_err(PyOverflowError::new_err)?
            .0
    } else {
        parts
    };
    let [year, month, day, hour, minute, second, microsecond] = result;
    let year = i32::try_from(year)
        .map_err(|_| PyOverflowError::new_err("integer overflow in Delta date arithmetic"))?;
    native_datetime(
        py,
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
    .map(Bound::into_any)
}

/// Split Unix microseconds into Gregorian date and normalized clock parts.
///
/// # Errors
/// Converts ordinal decoding failures to OverflowError; final Python year bounds
/// are left to the constructor.
fn datetime_parts(value: i64) -> PyResult<[i64; 7]> {
    let days = value.div_euclid(86_400_000_000);
    let time = value.rem_euclid(86_400_000_000);
    let [year, month, day] =
        crate::calendar::from_ordinal(days + 719_163).map_err(PyOverflowError::new_err)?;
    Ok([
        year,
        month,
        day,
        time / 3_600_000_000,
        time / 60_000_000 % 60,
        time / 1_000_000 % 60,
        time % 1_000_000,
    ])
}

/// Construct a builtin naive datetime from signed Unix microseconds.
///
/// # Errors
/// Propagates ordinal overflow or Python's invalid-year/date constructor errors.
pub fn datetime_from_us(py: Python<'_>, value: i64) -> PyResult<Bound<'_, PyDateTime>> {
    let [year, month, day, hour, minute, second, microsecond] = datetime_parts(value)?;
    native_datetime(py, [year, month, day, hour, minute, second, microsecond])
}

/// Construct the same builtin datetime through the initialized public C API.
/// # Errors
/// Retains Python's date bounds and allocation errors, with SDK initialization
/// as the fallback when the datetime capsule has not yet been populated.
#[inline(always)]
fn native_datetime<'py>(py: Python<'py>, parts: [i64; 7]) -> PyResult<Bound<'py, PyDateTime>> {
    let [year, month, day, hour, minute, second, microsecond] = parts;
    let year = year as i32;
    let (month, day, hour, minute, second) = (
        month as u8,
        day as u8,
        hour as u8,
        minute as u8,
        second as u8,
    );
    let microsecond = microsecond as u32;
    if let Some(api) = unsafe { pyo3::ffi::PyDateTimeAPI().as_ref() } {
        // SAFETY: The SDK owns the initialized capsule and its ready type.
        // The public constructor validates the same builtin bounds and returns
        // an owned reference or NULL with an exception. This is the same naive,
        // fold-zero value; no user constructor or timezone callback is skipped.
        let pointer = unsafe {
            (api.DateTime_FromDateAndTimeAndFold)(
                year,
                i32::from(month),
                i32::from(day),
                i32::from(hour),
                i32::from(minute),
                i32::from(second),
                microsecond as i32,
                pyo3::ffi::Py_None(),
                0,
                api.DateTimeType,
            )
        };
        return unsafe { Bound::from_owned_ptr_or_err(py, pointer) }
            .map(|value| unsafe { value.cast_into_unchecked::<PyDateTime>() });
    }
    PyDateTime::new(
        py,
        year,
        month,
        day,
        hour,
        minute,
        second,
        microsecond,
        None,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn scalar_layout_matches_public_numpy_headers() {
        assert_eq!(std::mem::size_of::<Scalar>(), 32);
        assert_eq!(std::mem::offset_of!(Scalar, value), 16);
        assert_eq!(std::mem::offset_of!(Scalar, metadata), 24);
        assert_eq!(std::mem::size_of::<Metadata>(), 8);
    }
}
