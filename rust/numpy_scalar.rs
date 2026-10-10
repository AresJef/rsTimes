//! The NumPy public datetime scalar layout is read only after a real type check.
use pyo3::exceptions::{PyOverflowError, PyTypeError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDateTime, PyDelta, PyType};

static TYPES: PyOnceLock<(Py<PyType>, Py<PyType>)> = PyOnceLock::new();
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

fn overflow() -> PyErr {
    PyOverflowError::new_err("integer overflow in NumPy scalar conversion")
}
fn mul(value: i64, factor: i64) -> PyResult<i64> {
    value.checked_mul(factor).ok_or_else(overflow)
}

pub fn microseconds(
    value: &Bound<'_, PyAny>,
    allow_datetime: bool,
) -> PyResult<Option<(i64, bool)>> {
    let py = value.py();
    let (date_type, duration_type) = TYPES.get_or_try_init(py, || -> PyResult<_> {
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
    })?;
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
    Ok(Some((converted, datetime)))
}

// NumPy scalars always produce a builtin naive datetime. Work on its validated
// parts directly, so the ordinary path allocates only the final result rather
// than an intermediate datetime followed by a second datetime.
pub fn apply_datetime_us<'py>(
    py: Python<'py>,
    delta: &crate::delta::Delta,
    value: i64,
    sign: i64,
) -> PyResult<Bound<'py, PyAny>> {
    let parts = datetime_parts(value)?;
    if !(1..=9999).contains(&parts[0]) {
        // Preserve the original Python constructor's exact range error before
        // applying any Delta replacement, including extreme NumPy dates.
        return datetime_from_us(py, value).map(Bound::into_any);
    }
    let result = if delta.__bool__() {
        crate::calendar::apply(&delta.snapshot(), parts, sign, true)
            .map_err(PyOverflowError::new_err)?
            .0
    } else {
        parts
    };
    let [year, month, day, hour, minute, second, microsecond] = result;
    let year = i32::try_from(year)
        .map_err(|_| PyOverflowError::new_err("integer overflow in Delta date arithmetic"))?;
    PyDateTime::new(
        py,
        year,
        month as u8,
        day as u8,
        hour as u8,
        minute as u8,
        second as u8,
        microsecond as u32,
        None,
    )
    .map(Bound::into_any)
}

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

pub fn datetime_from_us(py: Python<'_>, value: i64) -> PyResult<Bound<'_, PyDateTime>> {
    let [year, month, day, hour, minute, second, microsecond] = datetime_parts(value)?;
    PyDateTime::new(
        py,
        year as i32,
        month as u8,
        day as u8,
        hour as u8,
        minute as u8,
        second as u8,
        microsecond as u32,
        None,
    )
}
pub fn timedelta_from_us(py: Python<'_>, value: i64) -> PyResult<Bound<'_, PyDelta>> {
    let days = value.div_euclid(86_400_000_000);
    let rest = value.rem_euclid(86_400_000_000);
    PyDelta::new(
        py,
        days as i32,
        (rest / 1_000_000) as i32,
        (rest % 1_000_000) as i32,
        false,
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
