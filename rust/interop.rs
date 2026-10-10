//! Python object construction stays at this boundary; calculations stay in Rust.
use pyo3::exceptions::{PyException, PyOverflowError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDate, PyDateAccess, PyDateTime, PyDict, PyTimeAccess, PyTzInfoAccess};

pub fn apply_date<'py>(
    fields: &[i64; 15],
    other: &Bound<'py, PyAny>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = other.py();
    let (parts, datetime) = if let Ok(value) = other.cast::<PyDateTime>() {
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
            true,
        )
    } else if let Ok(value) = other.cast::<PyDate>() {
        (
            [
                i64::from(value.get_year()),
                i64::from(value.get_month()),
                i64::from(value.get_day()),
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
    let (result, unchanged) =
        crate::calendar::apply(fields, parts, sign, datetime).map_err(PyOverflowError::new_err)?;
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let [year, month, day, hour, minute, second, microsecond] = result;
    let year = i32::try_from(year)
        .map_err(|_| PyOverflowError::new_err("integer overflow in Delta date arithmetic"))?;
    if datetime && other.is_exact_instance_of::<PyDateTime>() {
        let dt = other.cast::<PyDateTime>()?;
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
    if !datetime && other.is_exact_instance_of::<PyDate>() {
        return PyDate::new(py, year, month as u8, day as u8).map(|value| Some(value.into_any()));
    }
    let class = other.getattr("__class__")?;
    let kwargs = PyDict::new(py);
    for (key, value) in [("year", i64::from(year)), ("month", month), ("day", day)] {
        kwargs.set_item(key, value)?;
    }
    if datetime {
        let dt = other.cast::<PyDateTime>()?;
        for (key, value) in [
            ("hour", hour),
            ("minute", minute),
            ("second", second),
            ("microsecond", microsecond),
        ] {
            kwargs.set_item(key, value)?;
        }
        kwargs.set_item("tzinfo", dt.get_tzinfo())?;
        kwargs.set_item("fold", i32::from(dt.get_fold()))?;
    }
    match class.call((), Some(&kwargs)) {
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
