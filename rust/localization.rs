//! Independent Gregorian names and native system timezone discovery.
//! CLDR is compiled data; neither service imports date classes from this library.

use std::borrow::Cow;

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDateAccess, PyDateTime, PyString, PyType, PyTzInfo};
#[path = "localization_data.rs"]
mod data;
static PYTZ_TYPES: PyOnceLock<Vec<Py<PyType>>> = PyOnceLock::new();
static ENGLISH: PyOnceLock<[Py<PyString>; 19]> = PyOnceLock::new();
// Only compiled CLDR groups can occupy a slot; arbitrary locale text is never retained.
static GROUP_NAMES: [PyOnceLock<[Py<PyString>; 19]>; data::GROUPS.len()] =
    [const { PyOnceLock::new() }; data::GROUPS.len()];

/// Adapt only genuine, already loaded pytz types; absence is not cached.
#[pyfunction]
fn _resolve_optional_timezone<'py>(
    value: &Bound<'py, PyTzInfo>,
    named: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    if !loaded_pytz(value)? {
        return Ok(value.clone().into_any());
    }
    let name = value
        .getattr("zone")
        .map_err(crate::error_context::external)?;
    let name = name.cast::<pyo3::types::PyString>().map_err(|_| crate::error_context::value_error(
        "pytz input must have a valid ZoneInfo name; pass a standard timezone for a fixed offset"))?;
    if name.len()? == 0 {
        return Err(crate::error_context::value_error(
            "pytz input must have a nonempty ZoneInfo name",
        ));
    }
    named.call1((name,)).map_err(crate::error_context::external)
}

/// Recognize actual loaded pytz types without forcing that optional import.
pub(crate) fn loaded_pytz(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    let py = value.py();
    let cached = if let Some(types) = PYTZ_TYPES.get(py) {
        Some(types)
    } else {
        // SAFETY: the attached interpreter owns its live module dictionary.
        // A miss remains retryable without importing sys on every custom zone.
        let modules = unsafe { Borrowed::from_ptr(py, ffi::PyImport_GetModuleDict()) };
        let modules = modules.cast::<pyo3::types::PyDict>()?;
        let Some(module) = modules.get_item("pytz")? else {
            return Ok(false);
        };
        let Some(tzinfo) = modules.get_item("pytz.tzinfo")? else {
            return Ok(false);
        };
        let types = vec![
            module
                .getattr("utc")
                .map_err(crate::error_context::external)?
                .get_type()
                .unbind(),
            module
                .getattr("_FixedOffset")
                .map_err(crate::error_context::external)?
                .cast_into::<PyType>()?
                .unbind(),
            tzinfo
                .getattr("BaseTzInfo")
                .map_err(crate::error_context::external)?
                .cast_into::<PyType>()?
                .unbind(),
        ];
        let _ = PYTZ_TYPES.set(py, types);
        PYTZ_TYPES.get(py)
    };
    let genuine = cached.is_some_and(|types| {
        types.iter().any(|kind| {
            // SAFETY: all candidate references and the actual receiver are retained.
            unsafe {
                ffi::PyType_IsSubtype(value.get_type().as_type_ptr(), kind.bind(py).as_type_ptr())
                    != 0
            }
        })
    });
    Ok(genuine)
}

/// Resolve a process system IANA name only when the Python local service asks.
#[pyfunction]
fn _local_timezone_name() -> PyResult<String> {
    iana_time_zone::get_timezone().map_err(|error| crate::error_context::value_error(format!(
        "local timezone could not be identified: {error}; set TZ to an installed IANA timezone name")))
}

/// Read a true stored month or weekday and return its compiled wide name.
#[pyfunction(signature=(value, locale, weekday))]
fn _localized_name<'py>(
    value: &Bound<'py, PyDateTime>,
    locale: Option<&Bound<'py, PyAny>>,
    weekday: bool,
) -> PyResult<Bound<'py, PyString>> {
    let py = value.py();
    let position = if weekday {
        12 + (crate::calendar::ordinal(
            i64::from(value.get_year()),
            i64::from(value.get_month()),
            i64::from(value.get_day()),
        ) - 1)
            .rem_euclid(7) as usize
    } else {
        usize::from(value.get_month()) - 1
    };
    let group = name_group(py, locale)?;
    calendar_name(py, group, position)
}

/// Resolve one CLDR group before an array loop, preserving scalar locale rules.
pub(crate) fn name_group(py: Python<'_>, locale: Option<&Bound<'_, PyAny>>) -> PyResult<usize> {
    let group = if let Some(locale) = locale.filter(|locale| !locale.is_none()) {
        let text = locale
            .cast::<PyString>()
            .map_err(|_| {
                crate::error_context::type_error(
                    "locale must be a string identifier or None, for example 'en_US'",
                )
            })?
            .to_str()?;
        if matches!(text, "en_US" | "en") {
            data::ENGLISH
        } else {
            let code = text.split(['.', '@']).next().unwrap_or("");
            let code = if code
                .bytes()
                .any(|byte| byte == b'_' || byte.is_ascii_uppercase())
            {
                let mut canonical = String::with_capacity(code.len());
                canonical.extend(code.chars().map(|value| {
                    if value == '_' {
                        '-'
                    } else {
                        value.to_ascii_lowercase()
                    }
                }));
                Cow::Owned(canonical)
            } else {
                Cow::Borrowed(code)
            };
            match data::LOCALES.binary_search_by_key(&code.as_ref(), |entry| entry.0) {
                Ok(index) => data::LOCALES[index].1,
                Err(_) => {
                    return Err(crate::error_context::value_error(format!(
                        "unknown locale {}; use a supported CLDR identifier such as 'en_US' or 'zh_CN'",
                        crate::error_context::text_preview(py, text)?,
                    )));
                }
            }
        }
    } else {
        data::ENGLISH
    };
    Ok(group)
}

/// Return one compiled wide month or weekday name without parsing locale again.
pub(crate) fn calendar_name(
    py: Python<'_>,
    group: usize,
    position: usize,
) -> PyResult<Bound<'_, PyString>> {
    if group == data::ENGLISH {
        let names = ENGLISH.get_or_init(py, || {
            std::array::from_fn(|index| PyString::new(py, data::GROUPS[group][index]).unbind())
        });
        return Ok(names[position].bind(py).clone());
    }
    let names = GROUP_NAMES[group].get_or_init(py, || {
        std::array::from_fn(|index| PyString::new(py, data::GROUPS[group][index]).unbind())
    });
    Ok(names[position].bind(py).clone())
}

/// Immutable compiled names for Python-free native column workers.
pub(crate) fn native_name(group: usize, position: usize) -> Option<&'static str> {
    data::GROUPS
        .get(group)
        .and_then(|names| names.get(position))
        .copied()
}

/// Register the small independent services; registration does not probe local time.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_local_timezone_name, module)?)?;
    module.add_function(wrap_pyfunction!(_localized_name, module)?)?;
    module.add_function(wrap_pyfunction!(_resolve_optional_timezone, module)?)?;
    Ok(())
}
