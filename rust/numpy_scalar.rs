//! Read NumPy's checked public datetime scalar prefix and convert its units.
//!
//! Only actual datetime64/timedelta64 scalar types reach the layout cast. This
//! module applies dtype multipliers before precision conversion and retains unsupported-unit errors;
//! NaT is explicitly rejected. No array interface or arbitrary NumPy ABI promise is added.

use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDate, PyDateTime, PyType};

static TYPES: PyOnceLock<(Py<PyType>, Py<PyType>)> = PyOnceLock::new();

/// Interpreter-owned exact scalar identities, captured once for a native batch.
pub(crate) struct ExactTypes {
    date: *mut pyo3::ffi::PyTypeObject,
    duration: *mut pyo3::ffi::PyTypeObject,
}

impl ExactTypes {
    /// Read a proven exact temporal scalar into the Delta ns model. The caller
    /// decides direction and date-only output without using item conversion.
    pub(crate) fn delta_scalar(
        &self,
        value: &Bound<'_, PyAny>,
        allow_date: bool,
    ) -> PyResult<Option<DeltaScalar>> {
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        if actual == self.date {
            if allow_date {
                decode_delta_scalar(value, true).map(Some)
            } else {
                Ok(None)
            }
        } else if actual == self.duration {
            decode_delta_scalar(value, false).map(Some)
        } else {
            Ok(None)
        }
    }

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

    /// Prepare trusted identities once, without relying on a value's type name.
    /// # Errors
    /// Propagates the same NumPy import/type errors as ordinary scalar conversion.
    pub(crate) fn for_value(value: &Bound<'_, PyAny>) -> PyResult<Option<Self>> {
        let py = value.py();
        let (date, duration) = scalar_types(py)?;
        let types = Self {
            date: date.bind(py).as_type_ptr(),
            duration: duration.bind(py).as_type_ptr(),
        };
        // SAFETY: All pointers remain live under the attached interpreter.
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        Ok((actual == types.date || actual == types.duration).then_some(types))
    }
}

/// Cache the real NumPy scalar types without changing dependency versions.
/// # Errors
/// Preserves module and attribute errors from the existing scalar entrance.
fn scalar_types(py: Python<'_>) -> PyResult<&(Py<PyType>, Py<PyType>)> {
    if let Some(types) = TYPES.get(py) {
        return Ok(types);
    }
    // Import and attribute access may reenter rstimes. Never perform them while
    // owning an initialization lock: a nested call may publish the same cache.
    let module = match py.import("numpy._core._multiarray_umath") {
        Ok(module) => module,
        Err(error) if error.is_instance_of::<pyo3::exceptions::PyModuleNotFoundError>(py) => {
            let missing = error
                .value(py)
                .getattr("name")
                .map_err(crate::error_context::external)?;
            let name = missing.extract::<String>()?;
            if name != "numpy._core" && name != "numpy._core._multiarray_umath" {
                return Err(error);
            }
            py.import("numpy.core._multiarray_umath")?
        }
        Err(error) => return Err(error),
    };
    let capsule = module
        .getattr("_ARRAY_API")
        .map_err(crate::error_context::external)?;
    // SAFETY: NumPy's public multiarray API is a nameless exact capsule. Its
    // documented entries 215/216 are the actual scalar PyTypeObjects, including
    // in the supported NumPy 1.x/2.x tables. Mutable Python aliases are not used.
    let candidate = unsafe {
        if pyo3::ffi::PyCapsule_CheckExact(capsule.as_ptr()) == 0 {
            return Err(crate::error_context::type_error(
                "NumPy _ARRAY_API must be a capsule",
            ));
        }
        let api = pyo3::ffi::PyCapsule_GetPointer(capsule.as_ptr(), std::ptr::null());
        if api.is_null() {
            return Err(crate::error_context::fetch(py));
        }
        let table = api.cast::<*mut pyo3::ffi::PyObject>();
        let date = Bound::from_borrowed_ptr_or_err(py, *table.add(215))?.cast_into::<PyType>()?;
        let duration =
            Bound::from_borrowed_ptr_or_err(py, *table.add(216))?.cast_into::<PyType>()?;
        (date.unbind(), duration.unbind())
    };
    // Publication itself invokes no user code. If a nested prepare won, retain
    // its complete value and drop only our redundant owned type references.
    let _ = TYPES.set(py, candidate);
    TYPES
        .get(py)
        .ok_or_else(|| crate::error_context::type_error("NumPy scalar types were not prepared"))
}

/// Prove genuine datetime64 ancestry without consulting names or Python aliases.
pub(crate) fn is_datetime(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    let (date, _) = scalar_types(value.py())?;
    // SAFETY: the value and retained real type are live on this interpreter.
    Ok(unsafe {
        pyo3::ffi::PyType_IsSubtype(
            pyo3::ffi::Py_TYPE(value.as_ptr()),
            date.bind(value.py()).as_type_ptr(),
        ) != 0
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

/// A source's exact native fields, independent of its final Python container.
pub(crate) enum DeltaScalar {
    Date {
        civil: crate::civil::CivilNs,
        coarse: bool,
    },
    Duration {
        days: i128,
        clock_ns: u64,
        calendar_unit: bool,
    },
}

/// Qualify genuine temporal inheritance before decoding its public scalar data.
pub(crate) fn delta_scalar(
    value: &Bound<'_, PyAny>,
    allow_date: bool,
) -> PyResult<Option<DeltaScalar>> {
    let (date, duration) = scalar_types(value.py())?;
    let actual = value.get_type();
    if actual.is_subclass(date.bind(value.py()))? {
        if allow_date {
            decode_delta_scalar(value, true).map(Some)
        } else {
            Ok(None)
        }
    } else if actual.is_subclass(duration.bind(value.py()))? {
        decode_delta_scalar(value, false).map(Some)
    } else {
        Ok(None)
    }
}

/// Decode after real ancestry was proved, avoiding tick*multiplier*ns overflow.
fn decode_delta_scalar(value: &Bound<'_, PyAny>, datetime: bool) -> PyResult<DeltaScalar> {
    // SAFETY: both callers prove real datetime64/timedelta64 scalar ancestry.
    // The input remains owned and the GIL held through these immutable reads.
    let scalar = unsafe { &*value.as_ptr().cast::<Scalar>() };
    if scalar.value == i64::MIN {
        return Err(crate::error_context::value_error(
            "NumPy NaT has no valid date or duration",
        ));
    }
    let unit = scalar.metadata.unit;
    let ticks = scaled_ticks(scalar.value, scalar.metadata.multiplier)?;
    if !matches!(unit, 0 | 1 | 2 | 4..=10) {
        return Err(unsupported_unit(unit, datetime));
    }
    if datetime && unit <= 1 {
        let (year, month) = if unit == 0 {
            (1970 + ticks, 1)
        } else {
            (
                1970 + ticks.div_euclid(12),
                (ticks.rem_euclid(12) + 1) as u8,
            )
        };
        return Ok(DeltaScalar::Date {
            civil: crate::civil::CivilNs {
                year,
                month,
                day: 1,
                clock_ns: 0,
            },
            coarse: true,
        });
    }
    let (days, clock_ns) = match unit {
        // The largest ticks product is below2^95; seconds below2^120.
        // Splitting seconds before scaling the remainder keeps ns below a day.
        0 | 1 => {
            let seconds = ticks * if unit == 0 { 31_556_952 } else { 2_629_746 };
            (
                seconds.div_euclid(86_400),
                (seconds.rem_euclid(86_400) * 1_000_000_000) as u64,
            )
        }
        2 => (ticks * 7, 0),
        4 => (ticks, 0),
        5..=10 => {
            let per_day = [
                24i128,
                1440,
                86_400,
                86_400_000,
                86_400_000_000,
                86_400_000_000_000,
            ][(unit - 5) as usize];
            let scale = [
                3_600_000_000_000i128,
                60_000_000_000,
                1_000_000_000,
                1_000_000,
                1000,
                1,
            ][(unit - 5) as usize];
            if let Ok(ticks) = i64::try_from(ticks) {
                let per_day = per_day as i64;
                (
                    i128::from(ticks.div_euclid(per_day)),
                    ticks.rem_euclid(per_day) as u64 * scale as u64,
                )
            } else {
                (
                    ticks.div_euclid(per_day),
                    (ticks.rem_euclid(per_day) * scale) as u64,
                )
            }
        }
        _ => unreachable!("supported NumPy unit"),
    };
    if datetime {
        let (year, month, day) =
            crate::civil::from_ordinal(days + 719_163).map_err(crate::error_context::overflow)?;
        Ok(DeltaScalar::Date {
            civil: crate::civil::CivilNs {
                year,
                month,
                day,
                clock_ns,
            },
            coarse: unit <= 4,
        })
    } else {
        Ok(DeltaScalar::Duration {
            days,
            clock_ns,
            calendar_unit: unit <= 1,
        })
    }
}

/// Apply exact NumPy wall fields and construct only its required final object.
pub(crate) fn apply_delta_date<'py>(
    py: Python<'py>,
    fields: &crate::delta::value::DeltaValue,
    input: crate::civil::CivilNs,
    sign: i64,
    date_only: bool,
) -> PyResult<Bound<'py, PyAny>> {
    if !(1..=9999).contains(&input.year) {
        return Err(crate::error_context::value_error(format!(
            "NumPy date arithmetic source year must be from1 through9999; got{}",
            input.year
        )));
    }
    let result =
        crate::civil::apply(fields, input, sign).map_err(crate::error_context::overflow)?;
    if date_only {
        let year = i32::try_from(result.year).map_err(|_| overflow())?;
        return PyDate::new(py, year, result.month, result.day).map(Bound::into_any);
    }
    let parts =
        crate::civil::project_microseconds(result).map_err(crate::error_context::overflow)?;
    i32::try_from(parts[0]).map_err(|_| overflow())?;
    native_datetime(py, parts).map(Bound::into_any)
}

/// Read a real datetime64 scalar without reducing its precision.
/// The public scalar prefix is unchanged across the supported NumPy 1/2 ABIs.
pub(crate) fn datetime_ticks(value: &Bound<'_, PyAny>) -> PyResult<Option<(i64, i32, i32)>> {
    let (date, _) = scalar_types(value.py())?;
    if !value.get_type().is_subclass(date.bind(value.py()))? {
        return Ok(None);
    }
    // SAFETY: actual datetime64 ancestry authorizes the public scalar prefix;
    // the bound value keeps its storage alive and the GIL remains held.
    let scalar = unsafe { &*value.as_ptr().cast::<Scalar>() };
    if scalar.metadata.multiplier <= 0 {
        return Err(crate::error_context::value_error(
            "invalid NumPy datetime unit multiplier",
        ));
    }
    Ok(Some((
        scalar.value,
        scalar.metadata.unit,
        scalar.metadata.multiplier,
    )))
}

/// Read actual duration scalar storage without narrowing or importing display fields.
pub(crate) fn duration_ticks(value: &Bound<'_, PyAny>) -> PyResult<Option<(i64, i32, i32)>> {
    let (_, duration) = scalar_types(value.py())?;
    if !value.get_type().is_subclass(duration.bind(value.py()))? {
        return Ok(None);
    }
    // SAFETY: actual initialized NumPy duration ancestry proves its scalar prefix;
    // the attached GIL and retained input keep the immutable storage alive.
    let scalar = unsafe { &*value.as_ptr().cast::<Scalar>() };
    if scalar.metadata.multiplier < 1 {
        return Err(crate::error_context::value_error(
            "invalid NumPy duration unit multiplier",
        ));
    }
    Ok(Some((
        scalar.value,
        scalar.metadata.unit,
        scalar.metadata.multiplier,
    )))
}

/// Decode a genuine timedelta64 exported by pandas without an i64 microsecond limit.
pub(crate) fn duration_nanoseconds(value: &Bound<'_, PyAny>) -> PyResult<Option<i128>> {
    let (_, duration) = scalar_types(value.py())?;
    if !value.get_type().is_subclass(duration.bind(value.py()))? {
        return Ok(None);
    }
    // SAFETY: actual timedelta64 ancestry proves the public NumPy scalar prefix.
    let scalar = unsafe { &*value.as_ptr().cast::<Scalar>() };
    if scalar.value == i64::MIN {
        return Err(crate::error_context::value_error(
            "NumPy NaT has no valid duration",
        ));
    }
    let ticks = scaled_ticks(scalar.value, scalar.metadata.multiplier)?;
    let scale: i128 = match scalar.metadata.unit {
        2 => 604_800_000_000_000,
        4 => 86_400_000_000_000,
        5 => 3_600_000_000_000,
        6 => 60_000_000_000,
        7 => 1_000_000_000,
        8 => 1_000_000,
        9 => 1000,
        10 => 1,
        _ => {
            return Err(crate::error_context::value_error(
                "pandas duration requires a fixed unit from weeks through nanoseconds",
            ));
        }
    };
    ticks.checked_mul(scale).map(Some).ok_or_else(overflow)
}

/// Create the common OverflowError for checked NumPy scalar conversion.
fn overflow() -> PyErr {
    crate::error_context::overflow("integer overflow in NumPy scalar conversion")
}

/// Unsupported temporal dtypes are type failures, with their actual unit named.
fn unsupported_unit(unit: i32, datetime: bool) -> PyErr {
    let name = match unit {
        11 => "ps",
        12 => "fs",
        13 => "as",
        14 => "generic",
        _ => "unknown",
    };
    crate::error_context::type_error(format!(
        "unsupported NumPy {} unit '{name}' (code {unit}); supported units are Y, M, W, D, h, m, s, ms, us and ns",
        if datetime {
            "datetime64"
        } else {
            "timedelta64"
        },
    ))
}
/// Read a checked NumPy datetime64/timedelta64 scalar as microseconds.
///
/// # Arguments
/// allow_datetime controls whether datetime64 participates in this dispatch.
///
/// # Returns
/// Some((microseconds, is_datetime)) for a supported scalar; None for other types
/// or a datetime scalar rejected by allow_datetime. Negative nanoseconds use
/// floor division. Dtype multipliers are applied before precision conversion; NaT is
/// rejected rather than converted into a date or duration.
///
/// # Errors
/// Raises ValueError for NaT, OverflowError on unrepresentable conversions and TypeError for the
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

/// Decode only datetime scalars, rejecting other objects before inspecting payloads.
///
/// # Errors
/// Preserves NumPy import errors, NaT rejection and checked conversion overflow.
pub(crate) fn datetime_microseconds(value: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    let (date, _) = scalar_types(value.py())?;
    let actual = value.get_type();
    if !actual.is(date.bind(value.py())) && !actual.is_subclass(date.bind(value.py()))? {
        return Ok(None);
    }
    convert_scalar(value, true).map(|(micros, _)| Some(micros))
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
    if scalar.value == i64::MIN {
        return Err(crate::error_context::value_error(
            "NumPy NaT has no valid date or duration",
        ));
    }
    let unit = scalar.metadata.unit;
    if scalar.metadata.multiplier == 1 {
        return convert_narrow(scalar.value, unit, datetime);
    }
    let ticks = scaled_ticks(scalar.value, scalar.metadata.multiplier)?;
    if let Ok(narrow) = i64::try_from(ticks) {
        return convert_narrow(narrow, unit, datetime);
    }
    // Only sub-microsecond division can bring a wider product back into i64.
    // Every supported calendar/coarser unit instead increases its magnitude.
    match unit {
        10 => Ok((
            i64::try_from(ticks.div_euclid(1_000)).map_err(|_| overflow())?,
            datetime,
        )),
        0 | 1 | 2 | 4..=9 => Err(overflow()),
        _ => Err(unsupported_unit(unit, datetime)),
    }
}

/// Convert representable ticks with ordinary checked integer arithmetic.
/// # Errors
/// Rejects unsupported units and results outside the final microsecond range.
#[inline]
fn convert_narrow(ticks: i64, unit: i32, datetime: bool) -> PyResult<(i64, bool)> {
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
            // A failure here necessarily exceeds the final microsecond range.
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
            return Err(unsupported_unit(unit, datetime));
        }
    };
    Ok((converted, datetime))
}

/// Checked scaling for coarser units; no valid final result can hide an overflow.
#[inline]
fn mul(value: i64, factor: i64) -> PyResult<i64> {
    value.checked_mul(factor).ok_or_else(overflow)
}

/// Apply NumPy's positive dtype multiplier before precision conversion.
/// The input widths prove the product fits i128, even when it exceeds i64.
#[inline]
pub(crate) fn scaled_ticks(ticks: i64, multiplier: i32) -> PyResult<i128> {
    if multiplier <= 0 {
        return Err(crate::error_context::value_error(
            "invalid NumPy unit multiplier",
        ));
    }
    Ok(i128::from(ticks) * i128::from(multiplier))
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
