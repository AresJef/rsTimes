//! Failure-only ownership and context at the Rust/Python boundary.
//!
//! Native scanners/calendars keep their Result types. At a Python adapter, an
//! error created by this library is marked at its creation site. A callback
//! failure is explicitly external instead, even when it raises ParseError.
//! This does not infer origin from an exception class or message. Successful
//! calls create no error state, preview, Python container or extra reference.
use pyo3::PyErrArguments;
use pyo3::exceptions::{
    PyException, PyMemoryError, PyOverflowError, PyRuntimeError, PyTypeError, PyValueError,
};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;

static HELPERS: PyOnceLock<[Py<PyAny>; 7]> = PyOnceLock::new();

/// Prepare callback-capable helper lookups before publishing the shared cache.
fn helper<'py>(py: Python<'py>, index: usize) -> PyResult<&'py Bound<'py, PyAny>> {
    let helpers = crate::python_cache::get_or_prepare(&HELPERS, py, || {
        let module = py.import("rstimes.errors")?;
        Ok::<_, PyErr>([
            module.getattr("_own_error")?.unbind(),
            module.getattr("_external_error")?.unbind(),
            module.getattr("_argument_error")?.unbind(),
            module.getattr("_location_error")?.unbind(),
            module.getattr("_binary_error")?.unbind(),
            module.getattr("_preview")?.unbind(),
            module.getattr("_critical")?.unbind(),
        ])
    })?;
    Ok(helpers[index].bind(py))
}

/// Tag a library failure at the known origin, not by its Python category.
#[cold]
#[inline(never)]
pub(crate) fn own(error: PyErr) -> PyErr {
    Python::attach(
        |py| match helper(py, 0).and_then(|f| f.call1((error.value(py),))) {
            Ok(_) => error,
            Err(secondary) => secondary,
        },
    )
}

/// Keep an exception crossing an actual user/third-party callback boundary.
#[cold]
#[inline(never)]
pub(crate) fn external(error: PyErr) -> PyErr {
    Python::attach(|py| {
        if fast_critical(py, &error) {
            return error;
        }
        match helper(py, 1).and_then(|f| f.call1((error.value(py),))) {
            Ok(_) => error,
            Err(secondary) => secondary,
        }
    })
}

/// No helper calls or explanatory arguments are needed for exits or memory failure.
fn fast_critical(py: Python<'_>, error: &PyErr) -> bool {
    !error.is_instance_of::<PyException>(py) || error.is_instance_of::<PyMemoryError>(py)
}

/// Used only where an optional capability may legitimately decline ordinary failure.
pub(crate) fn critical(py: Python<'_>, error: &PyErr) -> PyResult<bool> {
    if fast_critical(py, error) {
        return Ok(true);
    }
    helper(py, 6)?.call1((error.value(py),))?.extract()
}

/// Add only the outer call's known context; never reconstruct a callback error.
#[cold]
#[inline(never)]
pub(crate) fn argument(
    py: Python<'_>,
    error: PyErr,
    entry: &str,
    parameter: &str,
    value: &Bound<'_, PyAny>,
) -> PyErr {
    if fast_critical(py, &error) {
        return error;
    }
    match helper(py, 2).and_then(|f| f.call1((error.value(py), entry, parameter, value))) {
        Ok(value) => PyErr::from_value(value),
        Err(secondary) => secondary,
    }
}

/// Create one owned TypeError at a known unsupported-type check.
#[cold]
#[inline(never)]
pub(crate) fn type_error<A: PyErrArguments + Send + Sync + 'static>(args: A) -> PyErr {
    own(PyTypeError::new_err(args))
}
/// Create one owned ValueError at a known invalid-value check.
#[cold]
#[inline(never)]
pub(crate) fn value_error<A: PyErrArguments + Send + Sync + 'static>(args: A) -> PyErr {
    own(PyValueError::new_err(args))
}
/// Create one owned OverflowError for a genuine representability failure.
#[cold]
#[inline(never)]
pub(crate) fn overflow<A: PyErrArguments + Send + Sync + 'static>(args: A) -> PyErr {
    own(PyOverflowError::new_err(args))
}
/// Report an internal invariant without presenting it as bad user input.
#[cold]
#[inline(never)]
pub(crate) fn runtime<A: PyErrArguments + Send + Sync + 'static>(args: A) -> PyErr {
    own(PyRuntimeError::new_err(args))
}

/// Create one domain exception for a native failure at its Python adapter.
#[cold]
#[inline(never)]
pub(crate) fn domain(py: Python<'_>, name: &str, message: String) -> PyErr {
    create_domain(py, name, message, None)
}

/// Only an explicitly controlled translation receives a new cause relationship.
#[cold]
#[inline(never)]
pub(crate) fn caused_domain(py: Python<'_>, name: &str, message: String, cause: PyErr) -> PyErr {
    create_domain(py, name, message, Some(cause))
}

/// Construct a single domain failure, retaining a deliberately translated cause.
#[cold]
#[inline(never)]
fn create_domain(py: Python<'_>, name: &str, message: String, cause: Option<PyErr>) -> PyErr {
    match py
        .import("rstimes.errors")
        .and_then(|m| m.getattr(name))
        .and_then(|c| c.call1((message,)))
        .map_err(external)
    {
        Ok(value) => {
            let error = PyErr::from_value(value);
            if let Err(secondary) = helper(py, 0).and_then(|f| f.call1((error.value(py),))) {
                return secondary;
            }
            if let Some(cause) = cause {
                error.set_cause(py, Some(cause));
            }
            error
        }
        Err(secondary) => secondary,
    }
}

/// A C API error came from the called Python operation, not our constructors.
#[cold]
#[inline(never)]
pub(crate) fn fetch(py: Python<'_>) -> PyErr {
    external(PyErr::fetch(py))
}

/// The input slot may have been removed by a callback; only its index is known.
#[cold]
#[inline(never)]
pub(crate) fn location(py: Python<'_>, error: PyErr, entry: &str, parameter: &str) -> PyErr {
    if fast_critical(py, &error) {
        return error;
    }
    match helper(py, 3).and_then(|f| f.call1((error.value(py), entry, parameter))) {
        Ok(value) => PyErr::from_value(value),
        Err(secondary) => secondary,
    }
}

/// Both numeric-slot operands are retained by CPython throughout the callback.
#[cold]
#[inline(never)]
pub(crate) fn binary(
    py: Python<'_>,
    error: PyErr,
    entry: &str,
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
) -> PyErr {
    if fast_critical(py, &error) {
        return error;
    }
    match helper(py, 4).and_then(|f| f.call1((error.value(py), entry, left, right))) {
        Ok(value) => PyErr::from_value(value),
        Err(secondary) => secondary,
    }
}

/// Format only a failing builtin value; custom display methods are never called.
pub(crate) fn preview(value: &Bound<'_, PyAny>) -> PyResult<String> {
    helper(value.py(), 5)?.call1((value,))?.extract()
}

/// Bound a native string before creating the Python fragment used for escaping.
pub(crate) fn text_preview(py: Python<'_>, value: &str) -> PyResult<String> {
    let length = value.chars().count();
    let fragment: String = value.chars().take(96).collect();
    helper(py, 5)?.call1((fragment, length))?.extract()
}

/// Complete a native UTF8 row error without copying its whole text into Python.
#[cold]
#[inline(never)]
pub(crate) fn text_item(
    py: Python<'_>,
    error: PyErr,
    entry: &str,
    index: usize,
    value: &str,
) -> PyErr {
    match critical(py, &error) {
        Ok(true) => return error,
        Err(secondary) => return secondary,
        Ok(false) => {}
    }
    let parameter = format!("data[{index}]");
    match text_preview(py, value).and_then(|preview| {
        helper(py, 2)?.call1((error.value(py), entry, parameter, py.None(), true, preview))
    }) {
        Ok(value) => PyErr::from_value(value),
        Err(secondary) => secondary,
    }
}

/// Known parameter binding failures need no fallible type-name fallback.
#[cold]
#[inline(never)]
pub(crate) fn expected_type(
    value: &Bound<'_, PyAny>,
    entry: &str,
    parameter: &str,
    allowed: &str,
) -> PyErr {
    argument(
        value.py(),
        type_error(format!("must be {allowed}")),
        entry,
        parameter,
        value,
    )
}

/// Build an element position only after ruling out a critical exception.
pub(crate) fn item(
    py: Python<'_>,
    error: PyErr,
    entry: &str,
    group: &str,
    index: usize,
    value: Option<&Bound<'_, PyAny>>,
    reading: bool,
) -> PyErr {
    match critical(py, &error) {
        Ok(true) => return error,
        Err(secondary) => return secondary,
        Ok(false) => {}
    }
    let parameter = if reading {
        format!("reading {group}[{index}]")
    } else {
        format!("{group}[{index}]")
    };
    match value {
        Some(value) => argument(py, error, entry, &parameter, value),
        None => location(py, error, entry, &parameter),
    }
}

/// A metadata setter's name is known, but displaying its object is unnecessary.
pub(crate) fn attribute(
    py: Python<'_>,
    error: PyErr,
    entry: &str,
    name: &Bound<'_, PyAny>,
) -> PyErr {
    match critical(py, &error) {
        Ok(true) => return error,
        Err(secondary) => return secondary,
        Ok(false) => {}
    }
    match preview(name) {
        Ok(name) => location(py, error, entry, &format!("state.slots[{name}]")),
        Err(secondary) => secondary,
    }
}
