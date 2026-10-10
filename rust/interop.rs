//! Python object construction stays at this boundary; calculations stay in Rust.
use pyo3::exceptions::{PyException, PyOverflowError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDate, PyDateAccess, PyDateTime, PyDict, PyTimeAccess, PyTzInfoAccess};

#[inline]
pub fn apply_date<'py>(
    delta: &crate::delta::Delta,
    other: &Bound<'py, PyAny>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = other.py();
    let dt = other.cast::<PyDateTime>().ok();
    let date = if dt.is_none() {
        other.cast::<PyDate>().ok()
    } else {
        None
    };
    if dt.is_none() && date.is_none() {
        return Ok(None);
    }
    if !delta.__bool__() {
        return Ok(Some(other.clone()));
    }
    if let Some(date) = date {
        return apply_date_only(delta, other, date, sign);
    }
    let Some(dt) = dt else {
        return Ok(None);
    };
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
    let fields = delta.calendar_snapshot(true);
    let (result, unchanged) =
        crate::calendar::apply(&fields, parts, sign, true).map_err(PyOverflowError::new_err)?;
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let [year, month, day, hour, minute, second, microsecond] = result;
    let year = i32::try_from(year)
        .map_err(|_| PyOverflowError::new_err("integer overflow in Delta date arithmetic"))?;
    if other.is_exact_instance_of::<PyDateTime>() {
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
    construct_subclass(
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
#[inline(always)]
fn apply_date_only<'py>(
    delta: &crate::delta::Delta,
    other: &Bound<'py, PyAny>,
    date: &Bound<'py, PyDate>,
    sign: i64,
) -> PyResult<Option<Bound<'py, PyAny>>> {
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
        crate::calendar::apply(&delta.calendar_snapshot(false), parts, sign, false)
            .map_err(PyOverflowError::new_err)?;
    if unchanged {
        return Ok(Some(other.clone()));
    }
    let year = i32::try_from(result[0])
        .map_err(|_| PyOverflowError::new_err("integer overflow in Delta date arithmetic"))?;
    if other.is_exact_instance_of::<PyDate>() {
        return PyDate::new(other.py(), year, result[1] as u8, result[2] as u8)
            .map(|value| Some(value.into_any()));
    }
    construct_subclass(other, None, result)
}

// Ordinary builtins do not need a keyword dictionary or Python callback.
// Keep this less common constructor/error path out of their call frame.
#[cold]
#[inline(never)]
fn construct_subclass<'py>(
    other: &Bound<'py, PyAny>,
    dt: Option<&Bound<'py, PyDateTime>>,
    result: [i64; 7],
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = other.py();
    let datetime = dt.is_some();
    let [year, month, day, hour, minute, second, microsecond] = result;
    let class = other.getattr("__class__")?;
    let kwargs = PyDict::new(py);
    for (key, value) in [("year", year), ("month", month), ("day", day)] {
        kwargs.set_item(key, value)?;
    }
    if let Some(dt) = dt {
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

use pyo3::sync::PyOnceLock;
use pyo3::types::PyType;
static RELATIVEDELTA: PyOnceLock<Py<PyType>> = PyOnceLock::new();

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
    let mut fields = [0; 15];
    for (index, name) in names.into_iter().enumerate() {
        let mut item = normalized.getattr(name)?;
        if index >= 7 && item.is_none() {
            fields[index] = -1;
            continue;
        }
        if index == 10 {
            item = item.getattr(pyo3::intern!(py, "weekday"))?;
        }
        fields[index] = crate::delta::input_integer(&item, !(2..7).contains(&index))?;
    }
    Ok(fields)
}
