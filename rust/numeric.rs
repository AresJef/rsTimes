//! Shared, role-specific scalar preparation at Python API boundaries.

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyFloat, PyType};

struct NumpyFloat {
    kind: Py<PyType>,
    read: Py<PyAny>,
}

struct NumpyScalars {
    boolean: Py<PyType>,
    floats: [NumpyFloat; 3],
}

static NUMPY: PyOnceLock<NumpyScalars> = PyOnceLock::new();

/// Identify real boolean scalars before any integer/float protocol is invoked.
pub(crate) fn is_bool(value: &Bound<'_, PyAny>) -> bool {
    // SAFETY: the live reference is held while attached to its interpreter.
    if unsafe { ffi::PyBool_Check(value.as_ptr()) != 0 } {
        return true;
    }
    // Real int/float values cannot be NumPy boolean scalars.
    if unsafe { ffi::PyLong_Check(value.as_ptr()) != 0 || ffi::PyFloat_Check(value.as_ptr()) != 0 }
    {
        return false;
    }
    NUMPY
        .get(value.py())
        .is_some_and(|types| value.get_type().is(types.boolean.bind(value.py())))
}

/// Read only Python/NumPy boolean scalars, without arbitrary truth callbacks.
#[inline]
pub(crate) fn boolean(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    // SAFETY: value is live, and these checks do not invoke Python callbacks.
    unsafe {
        if ffi::Py_IsTrue(value.as_ptr()) != 0 {
            return Ok(true);
        }
        if ffi::Py_IsFalse(value.as_ptr()) != 0 {
            return Ok(false);
        }
    }
    if is_bool(value) {
        return value.is_truthy().map_err(crate::error_context::external);
    }
    Err(crate::error_context::type_error(
        "must be a Python bool or NumPy bool scalar; pass True or False",
    ))
}

/// Read an integer protocol once, rejecting boolean values before conversion.
#[inline]
pub(crate) fn index_i64(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    // Exact int excludes both boolean families and cannot invoke an index hook.
    // Keep its checked full-width conversion, without reclassifying it twice.
    if unsafe { ffi::PyLong_CheckExact(value.as_ptr()) != 0 } {
        return crate::delta::converted_integer(value);
    }
    if is_bool(value) {
        return Err(crate::error_context::type_error(
            "must be an integer; boolean values are not accepted",
        ));
    }
    // Reuse the checked converter, including its original callback exceptions.
    crate::delta::index_integer(value)
}

/// Read wide factory integers once; final date-buffer capacity is checked later.
pub(crate) fn index_i128(value: &Bound<'_, PyAny>) -> PyResult<i128> {
    if is_bool(value) {
        return Err(crate::error_context::type_error(
            "boolean values are not integers here",
        ));
    }
    if value.is_instance_of::<pyo3::types::PyInt>() {
        return value.extract::<i128>();
    }
    if unsafe { ffi::PyIndex_Check(value.as_ptr()) } == 0 {
        return Err(crate::error_context::type_error(
            "an integer index value is required",
        ));
    }
    // SAFETY: the live index protocol returns one owned integer or its original error.
    let number =
        unsafe { Bound::from_owned_ptr_or_err(value.py(), ffi::PyNumber_Index(value.as_ptr())) }
            .map_err(crate::error_context::external)?;
    number.extract::<i128>()
}

/// Recognize the explicitly supported floating types, without coercing others.
pub(crate) fn supported_float(value: &Bound<'_, PyAny>) -> bool {
    if value.is_instance_of::<PyFloat>() {
        return true;
    }
    NUMPY.get(value.py()).is_some_and(|types| {
        types
            .floats
            .iter()
            .any(|kind| numpy_float_instance(value, kind))
    })
}

/// Check real NumPy floating ancestry; names and conversion methods are not gates.
fn numpy_float_instance(value: &Bound<'_, PyAny>, kind: &NumpyFloat) -> bool {
    // SAFETY: the input and retained type belong to the attached interpreter.
    unsafe {
        ffi::PyType_IsSubtype(
            ffi::Py_TYPE(value.as_ptr()),
            kind.kind.bind(value.py()).as_type_ptr(),
        ) != 0
    }
}

/// Read an admitted NumPy scalar's stored value through its base descriptor.
pub(crate) fn float_value(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    let types = NUMPY
        .get(value.py())
        .ok_or_else(|| crate::error_context::runtime("NumPy scalar identities are not prepared"))?;
    let kind = types
        .floats
        .iter()
        .find(|kind| numpy_float_instance(value, kind))
        .ok_or_else(|| {
            crate::error_context::type_error(
                "must be a Python float or NumPy float16, float32 or float64",
            )
        })?;
    kind.read
        .bind(value.py())
        .call1((value,))
        .map_err(crate::error_context::external)?
        .extract::<f64>()
}

/// Expose strict preparation to thin Python wrappers; errors stay cold.
#[pyfunction]
fn _bool_option(value: &Bound<'_, PyAny>, entry: &str, parameter: &str) -> PyResult<bool> {
    boolean(value)
        .map_err(|error| crate::error_context::argument(value.py(), error, entry, parameter, value))
}

/// Share integer preparation with thin wrappers without a second conversion.
#[pyfunction]
fn _integer_arg(value: &Bound<'_, PyAny>, entry: &str, parameter: &str) -> PyResult<i64> {
    index_i64(value)
        .map_err(|error| crate::error_context::argument(value.py(), error, entry, parameter, value))
}

/// Prepare mandatory NumPy identities once, outside ordinary computation.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    let numpy = py.import("numpy").map_err(crate::error_context::external)?;
    let kind = |name: &str| -> PyResult<Py<PyType>> {
        Ok(numpy.getattr(name)?.cast_into::<PyType>()?.unbind())
    };
    let float_kind = |name: &str| -> PyResult<NumpyFloat> {
        let kind = kind(name)?;
        let read = kind.bind(py).getattr("__float__")?.unbind();
        Ok(NumpyFloat { kind, read })
    };
    let _ = NUMPY.set(
        py,
        NumpyScalars {
            boolean: kind("bool_")?,
            floats: [
                float_kind("float16")?,
                float_kind("float32")?,
                float_kind("float64")?,
            ],
        },
    );
    module.add_function(wrap_pyfunction!(_bool_option, module)?)?;
    module.add_function(wrap_pyfunction!(_integer_arg, module)?)?;
    Ok(())
}
