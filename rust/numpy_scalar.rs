//! Read NumPy's checked public datetime scalar prefix and convert its units.
//!
//! Only actual datetime64/timedelta64 scalar types reach the layout cast. This
//! module applies dtype multipliers before precision conversion and retains unsupported-unit errors;
//! NaT is explicitly rejected. No array interface or arbitrary NumPy ABI promise is added.

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

    /// Decode a proven exact scalar without repeated Python type/cache operations.
    /// # Errors
    /// Retains all unit conversion, overflow and unsupported-unit errors.
    #[inline]
    pub(crate) fn microseconds(&self, value: &Bound<'_, PyAny>) -> PyResult<Option<(i64, bool)>> {
        self.microseconds_for_operation(value, true)
    }

    /// Decode only units whose ordinary addition produces the same native type.
    /// Date-only and integer-valued item() conversions retain Python dispatch.
    pub(crate) fn addition_microseconds(
        &self,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<Option<(i64, bool)>> {
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        if actual != self.date && actual != self.duration {
            return Ok(None);
        }
        // SAFETY: exact scalar identity establishes the public prefix.
        let unit = unsafe { (*value.as_ptr().cast::<Scalar>()).metadata.unit };
        let equivalent = if actual == self.date {
            (5..=9).contains(&unit)
        } else {
            unit == 2 || (4..=9).contains(&unit)
        };
        if equivalent {
            self.microseconds(value)
        } else {
            Ok(None)
        }
    }

    /// Check one exact scalar identity and the operation's date restriction once.
    /// # Errors
    /// Retains NaT, unit and overflow errors; disallowed dates return None before decoding.
    #[inline(always)]
    pub(crate) fn microseconds_for_operation(
        &self,
        value: &Bound<'_, PyAny>,
        allow_datetime: bool,
    ) -> PyResult<Option<(i64, bool)>> {
        // SAFETY: The live actual type is compared to interpreter-owned identities
        // before reading the verified public scalar prefix. Subclasses fall back.
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        if actual != self.date && actual != self.duration {
            return Ok(None);
        }
        let datetime = actual == self.date;
        if datetime && !allow_datetime {
            return Ok(None);
        }
        // SAFETY: Exact identity above proves the live scalar prefix. Ordinary
        // microsecond values need no unit arithmetic or general calendar decoder.
        // NaT and every other unit retain the complete converter and its errors.
        let scalar = unsafe { &*value.as_ptr().cast::<Scalar>() };
        if scalar.metadata.unit == 9 && scalar.metadata.multiplier == 1 && scalar.value != i64::MIN
        {
            return Ok(Some((scalar.value, datetime)));
        }
        convert_scalar(value, datetime).map(Some)
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

/// Preserve NumPy's ordinary reflected conversion, while rejecting NaT first.
///
/// # Errors
/// Rejects a proven missing scalar with ValueError; item conversion errors propagate.
pub(crate) fn reflected_item<'py>(
    value: &Bound<'py, PyAny>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = value.py();
    let types = match ExactTypes::cached(py) {
        Some(types) => Some(types),
        None => ExactTypes::for_value(value)?,
    };
    let Some(types) = types else {
        return Ok(None);
    };
    if !types.matches(value) {
        return Ok(None);
    }
    // SAFETY: ExactTypes proved the actual live scalar layout under the GIL.
    // NaT is identified before item() can erase it into an unrelated None.
    if unsafe { (*value.as_ptr().cast::<Scalar>()).value } == i64::MIN {
        return Err(crate::error_context::value_error(
            "NumPy NaT has no valid date or duration",
        ));
    }
    value
        .call_method0(pyo3::intern!(py, "item"))
        .map_err(crate::error_context::external)
        .map(Some)
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
            .map_err(crate::error_context::overflow)?
            .0
    } else {
        parts
    };
    let [year, month, day, hour, minute, second, microsecond] = result;
    let year = i32::try_from(year)
        .map_err(|_| crate::error_context::overflow("integer overflow in Delta date arithmetic"))?;
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
        crate::calendar::from_ordinal(days + 719_163).map_err(crate::error_context::overflow)?;
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
