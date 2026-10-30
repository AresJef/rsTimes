//! Registered ZoneInfo objects; Python is used only at configuration/build boundaries.
use super::text::TextView;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PySet, PyString};
use std::collections::HashMap;
use std::sync::Arc;

/// Construct one checked builtin datetime; user constructors are called later.
fn datetime<'py>(
    py: Python<'py>,
    values: [i32; 7],
    zone: &Bound<'py, PyAny>,
    fold: i32,
) -> PyResult<Bound<'py, PyAny>> {
    // SAFETY: the parser imports datetime's API. All fields go through its
    // checked constructor, and the zone is held alive for the entire call.
    unsafe {
        let api = ffi::PyDateTimeAPI()
            .as_ref()
            .ok_or_else(|| crate::error_context::runtime("datetime API is unavailable"))?;
        Bound::from_owned_ptr_or_err(
            py,
            (api.DateTime_FromDateAndTimeAndFold)(
                values[0],
                values[1],
                values[2],
                values[3],
                values[4],
                values[5],
                values[6],
                zone.as_ptr(),
                fold,
                api.DateTimeType,
            ),
        )
    }
}

/// Read fold only from the stored layout of a datetime default.
pub(crate) fn default_fold(default: Option<&Bound<'_, PyAny>>) -> i32 {
    // SAFETY: the predicate qualifies datetime storage, including true subclasses.
    default
        .filter(|value| unsafe { ffi::PyDateTime_Check(value.as_ptr()) != 0 })
        .map_or(0, |value| unsafe {
            i32::from(ffi::PyDateTime_DATE_GET_FOLD(value.as_ptr()))
        })
}

/// Borrow a previously registered ZoneInfo without validating a wall time.
pub(crate) fn object<'a, 'py>(
    py: Python<'py>,
    zone: &'a RegisteredZone,
) -> PyResult<&'a Bound<'py, PyAny>> {
    match zone.object.as_ref() {
        Some(object) => Ok(object.bind(py)),
        None => Err(crate::error_context::domain(
            py,
            "ParseError",
            format!(
                "time zone {} is unavailable on this machine; install timezone data and restore or register the configuration again",
                crate::error_context::text_preview(py, &zone.key)?,
            ),
        )),
    }
}

/// Build the requested wall fields; existence policy belongs to the output type.
pub(crate) fn resolve<'py>(
    py: Python<'py>,
    zone: &RegisteredZone,
    values: [i32; 7],
    default: Option<&Bound<'py, PyAny>>,
    _strict: bool,
) -> PyResult<Bound<'py, PyAny>> {
    datetime(py, values, object(py, zone)?, default_fold(default))
}

pub(crate) struct RegisteredZone {
    pub(crate) key: String,
    pub(crate) object: Option<Py<PyAny>>,
    pub(crate) fixed_offset_us: Option<i64>,
}

pub(super) type ZoneMap = HashMap<Vec<u32>, Arc<RegisteredZone>>;

/// Validate serialized keys even when the receiving machine lacks zoneinfo.
fn key_text(value: &Bound<'_, PyAny>) -> PyResult<String> {
    let key = value
        .cast_exact::<PyString>()?
        .extract::<String>()
        .map_err(|error| {
            if error.is_instance_of::<pyo3::exceptions::PyUnicodeEncodeError>(value.py()) {
                let error = crate::error_context::caused_domain(
                    value.py(),
                    "ConfigError",
                    "time zone key must contain valid Unicode characters".to_owned(),
                    error,
                );
                crate::error_context::argument(value.py(), error, "", "key", value)
            } else {
                error
            }
        })?;
    if key.starts_with('/')
        || key.contains('\0')
        || key.split('/').any(|part| matches!(part, "" | "." | ".."))
    {
        return Err(crate::error_context::domain(
            value.py(),
            "ConfigError",
            "a time zone key must be a normalized relative name, such as 'Asia/Shanghai'"
                .to_owned(),
        ));
    }
    Ok(key)
}

fn unavailable(py: Python<'_>, error: &PyErr) -> PyResult<bool> {
    if crate::error_context::critical(py, error)? {
        return Ok(false);
    }
    let class = py
        .import("zoneinfo")?
        .getattr("ZoneInfoNotFoundError")
        .map_err(crate::error_context::external)?;
    Ok(error.is_instance(py, &class))
}

/// Keep missing keys only during restore, so configuration intent survives.
pub(super) fn load(value: &Bound<'_, PyAny>, restoring: bool) -> PyResult<Arc<RegisteredZone>> {
    load_key(value.py(), key_text(value)?, restoring)
}

/// Load a previously validated owned key, outside any caller-owned iterator.
fn load_key(py: Python<'_>, key: String, restoring: bool) -> PyResult<Arc<RegisteredZone>> {
    let object = py
        .import("zoneinfo")
        .and_then(|m| {
            m.getattr("ZoneInfo")
                .map_err(crate::error_context::external)
        })
        .and_then(|cls| cls.call1((&key,)).map_err(crate::error_context::external));
    let object = match object {
        Ok(object) => Some(object.unbind()),
        Err(error) if unavailable(py, &error)? => {
            if restoring {
                None
            } else {
                return Err(crate::error_context::caused_domain(
                    py,
                    "ConfigError",
                    format!(
                        "time zone {} is invalid or timezone data is unavailable; provide an installed IANA name",
                        crate::error_context::text_preview(py, &key)?,
                    ),
                    error,
                ));
            }
        }
        Err(error) => return Err(error),
    };
    let fixed_offset_us = match object.as_ref() {
        Some(zone) => crate::pydt::fixed_zoneinfo_offset(zone.bind(py))?,
        None => None,
    };
    Ok(Arc::new(RegisteredZone {
        key,
        object,
        fixed_offset_us,
    }))
}

pub(super) fn from_set(value: Option<&Bound<'_, PyAny>>, restoring: bool) -> PyResult<ZoneMap> {
    let mut result = ZoneMap::new();
    if let Some(value) = value.filter(|v| !v.is_none()) {
        let values = value.cast::<PySet>()?;
        // Validate all names before ZoneInfo can re-enter Python and mutate
        // the original set. The completed map is committed by the caller once.
        let keys = values
            .iter()
            .map(|key| key_text(&key))
            .collect::<PyResult<Vec<_>>>()?;
        for key in keys {
            let zone = load_key(value.py(), key, restoring)?;
            result.insert(zone.key.chars().map(u32::from).collect(), zone);
        }
    }
    Ok(result)
}

pub(super) fn names<'py>(py: Python<'py>, zones: &ZoneMap) -> PyResult<Bound<'py, PySet>> {
    PySet::new(py, zones.values().map(|zone| zone.key.as_str()))
}

pub(super) fn token(value: &Bound<'_, PyAny>) -> PyResult<Vec<u32>> {
    let key = value
        .cast_exact::<PyString>()
        .map_err(|_| crate::error_context::type_error("A time zone name must be a string."))?;
    let view = TextView::new(key)?;
    Ok(view.range(0, view.len()))
}
