//! Shared numeric epoch protocols; each public boundary chooses its date roles.
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyBytes, PyFloat, PyString};

/// Input quantity, independent of a date column's final storage unit.
#[derive(Clone, Copy)]
pub(crate) enum Quantity {
    Seconds,
    Microseconds,
}

/// Native errors that can cross a worker without a Python exception.
pub(crate) enum Error {
    Type(&'static str),
    Capacity(&'static str),
}

/// Convert ordinary floating seconds or reject a finite float integer quantity.
pub(crate) fn float_number(value: f64, quantity: Quantity) -> Result<Option<i128>, Error> {
    if value.is_nan() {
        return Ok(None);
    }
    if matches!(quantity, Quantity::Microseconds) {
        return Err(Error::Type(
            "microseconds require integer index values, not floats",
        ));
    }
    crate::precision::float_epoch_nanos(value, 1_000_000_000)
        .map(Some)
        .map_err(|_| Error::Capacity("numeric epoch is too large"))
}
/// Build an exception only at a host adapter.
pub(crate) fn error(value: Error) -> PyErr {
    match value {
        Error::Type(message) => crate::error_context::type_error(message),
        Error::Capacity(message) => crate::error_context::overflow(message),
    }
}

/// The already adopted numeric-factory missing protocol, without float coercion.
pub(crate) fn missing(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    if crate::date_input::missing(value) {
        return Ok(true);
    }
    if let Ok(text) = value.cast::<PyString>() {
        return crate::date_input::missing_text(text);
    }
    if let Some((ticks, code, _)) = crate::numpy_scalar::datetime_ticks(value)? {
        crate::date_input::scalar_unit(code)?;
        return Ok(ticks == i64::MIN);
    }
    Ok(false)
}
/// Real protocol slots classify a scalar without executing its conversion.
pub(crate) fn scalar(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    if missing(value)?
        || value.is_instance_of::<PyString>()
        || value.is_instance_of::<PyBytes>()
        || value.is_instance_of::<PyByteArray>()
    {
        return Ok(true);
    }
    // SAFETY: the bound value and its actual heap type remain live; only native
    // protocol slot metadata is inspected, without calling a conversion.
    Ok(unsafe {
        pyo3::ffi::PyDate_Check(value.as_ptr()) != 0
            || pyo3::ffi::PyIndex_Check(value.as_ptr()) != 0
            || !pyo3::ffi::PyType_GetSlot(
                pyo3::ffi::Py_TYPE(value.as_ptr()),
                pyo3::ffi::Py_nb_float,
            )
            .is_null()
    })
}
/// Read the existing index/number-float protocol once; do not parse text numbers.
pub(crate) fn read(value: &Bound<'_, PyAny>, quantity: Quantity) -> PyResult<Option<i128>> {
    if missing(value)? {
        return Ok(None);
    }
    if crate::numeric::is_bool(value) {
        return Err(crate::error_context::type_error(
            "boolean values are not numeric dates",
        ));
    }
    if matches!(quantity, Quantity::Microseconds) {
        if crate::numeric::supported_float(value) {
            let number = if value.is_instance_of::<PyFloat>() {
                value.extract::<f64>()?
            } else {
                crate::numeric::float_value(value)?
            };
            if number.is_nan() {
                return Ok(None);
            }
        }
        return crate::numeric::index_i128(value)?
            .checked_mul(1000)
            .map(Some)
            .ok_or_else(|| crate::error_context::overflow("microseconds exceed native range"));
    }
    // SAFETY: the live bound object is inspected without executing its index.
    if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) != 0 } {
        return crate::numeric::index_i128(value)?
            .checked_mul(1_000_000_000)
            .map(Some)
            .ok_or_else(|| crate::error_context::overflow("seconds exceed native range"));
    }
    if value.is_instance_of::<PyString>()
        || value.is_instance_of::<PyBytes>()
        || value.is_instance_of::<PyByteArray>()
    {
        return Err(crate::error_context::type_error(
            "seconds must be numeric, not text or byte strings",
        ));
    }
    let number = unsafe {
        Bound::from_owned_ptr_or_err(value.py(), pyo3::ffi::PyNumber_Float(value.as_ptr()))
    }
    .map_err(crate::error_context::external)?
    .extract::<f64>()?;
    float_number(number, quantity).map_err(error)
}
