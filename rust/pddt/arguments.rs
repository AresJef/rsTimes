//! Once-read integer components shared by column factories and operations.
use pyo3::prelude::*;
use pyo3::types::PyString;

pub(super) use crate::batch_shape::Column;

#[pyclass(frozen, name = "_PddtIntegers")]
pub(super) struct Integers(pub Column<Option<i64>>);

pub(super) fn date_missing(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    crate::date_input::date_missing(value)
}

fn integer(value: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    if date_missing(value)? {
        Ok(None)
    } else {
        crate::numeric::index_i64(value).map(Some)
    }
}

#[pyfunction]
#[pyo3(signature=(data,column,entry,parameter,buffer=None,kind=None,mask=None))]
fn _pddt_integers(
    data: &Bound<'_, PyAny>,
    column: bool,
    entry: &str,
    parameter: &str,
    buffer: Option<&[u8]>,
    kind: Option<&str>,
    mask: Option<&[u8]>,
) -> PyResult<Integers> {
    let py = data.py();
    if let Some(bytes) = buffer {
        if bytes.len() % 8 != 0 || mask.is_some_and(|m| m.len() != bytes.len() / 8) {
            return Err(crate::error_context::runtime(
                "invalid integer column metadata",
            ));
        }
        let kind = kind.unwrap_or("");
        if !matches!(kind, "i" | "u" | "f") {
            return Err(crate::error_context::runtime("invalid integer storage"));
        }
        let mut values = Vec::with_capacity(bytes.len() / 8);
        for (i, bytes) in bytes.chunks_exact(8).enumerate() {
            if mask.is_some_and(|m| m[i] != 0) {
                values.push(None);
                continue;
            }
            let raw: [u8; 8] = bytes
                .try_into()
                .map_err(|_| crate::error_context::runtime("invalid integer bytes"))?;
            let result = match kind {
                "i" => Some(i64::from_ne_bytes(raw)),
                "u" => Some(i64::try_from(u64::from_ne_bytes(raw)).map_err(|_| {
                    crate::error_context::location(
                        py,
                        crate::error_context::overflow("integer component exceeds signed64"),
                        entry,
                        &format!("{parameter}[{i}]"),
                    )
                })?),
                _ if f64::from_ne_bytes(raw).is_nan() => None,
                _ => {
                    return Err(crate::error_context::location(
                        py,
                        crate::error_context::type_error(
                            "requires integer index values, not floats",
                        ),
                        entry,
                        &format!("{parameter}[{i}]"),
                    ));
                }
            };
            values.push(result);
        }
        return Ok(Integers(Column::Values(values)));
    }
    let scalar = !column
        && (date_missing(data)?
            || unsafe { pyo3::ffi::PyIndex_Check(data.as_ptr()) != 0 }
            || crate::numeric::supported_float(data)
            || data.is_instance_of::<PyString>()
            || data.is_instance_of::<pyo3::types::PyBytes>()
            || data.is_instance_of::<pyo3::types::PyByteArray>());
    if scalar {
        return integer(data)
            .map(|v| Integers(Column::Scalar(v)))
            .map_err(|e| crate::error_context::argument(py, e, entry, parameter, data));
    }
    let iterator = data.try_iter().map_err(crate::error_context::external)?;
    let mut values = Vec::new();
    for (i, item) in iterator.enumerate() {
        let item = item
            .map_err(crate::error_context::external)
            .map_err(|e| crate::error_context::item(py, e, entry, parameter, i, None, true))?;
        values.push(integer(&item).map_err(|e| {
            crate::error_context::item(py, e, entry, parameter, i, Some(&item), false)
        })?);
    }
    Ok(Integers(Column::Values(values)))
}

pub(super) fn length(
    lengths: impl IntoIterator<Item = Option<usize>>,
    size: Option<usize>,
) -> PyResult<usize> {
    crate::batch_shape::length(lengths, size).map_err(crate::error_context::value_error)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_component, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_integers, module)?)
}

/// Existing-column parameters accept only None as an optional unchanged field.
/// Date missing markers remain a separate factory/data role.
fn component_value(value: &Bound<'_, PyAny>, optional: bool, names: u8) -> PyResult<Option<i64>> {
    if value.is_none() && optional {
        return Ok(None);
    }
    if names != 0 && value.is_instance_of::<PyString>() {
        let text = value.cast::<PyString>()?.to_str()?;
        return crate::pydt::lookup_selector(value.py(), text, names == 2)
            .map(|v| Some(i64::from(v)));
    }
    crate::numeric::index_i64(value).map(Some)
}
fn component_range(
    value: Option<i64>,
    low: Option<i64>,
    high: Option<i64>,
) -> PyResult<Option<i64>> {
    if value.is_some_and(|n| low.is_some_and(|l| n < l) || high.is_some_and(|h| n > h)) {
        return Err(crate::error_context::value_error(format!(
            "must be in the inclusive range {} through {}{}",
            low.unwrap_or(i64::MIN),
            high.unwrap_or(i64::MAX),
            if value.is_none() {
                ""
            } else {
                "; use None only when the field may be retained"
            }
        )));
    }
    Ok(value)
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One-time native parameter preparation with role and optional typed buffer"
)]
#[pyo3(signature=(data,column,length,entry,parameter,optional=false,names=0,low=None,high=None,buffer=None,kind=None,mask=None))]
fn _pddt_component(
    data: &Bound<'_, PyAny>,
    column: bool,
    length: usize,
    entry: &str,
    parameter: &str,
    optional: bool,
    names: u8,
    low: Option<i64>,
    high: Option<i64>,
    buffer: Option<&[u8]>,
    kind: Option<&str>,
    mask: Option<&[u8]>,
) -> PyResult<Integers> {
    let py = data.py();
    let convert =
        |v: &Bound<'_, PyAny>| component_range(component_value(v, optional, names)?, low, high);
    if let Some(bytes) = buffer {
        if bytes.len() % 8 != 0 || mask.is_some_and(|m| m.len() != bytes.len() / 8) {
            return Err(crate::error_context::runtime(
                "invalid component buffer metadata",
            ));
        }
        if bytes.len() / 8 != length {
            return Err(crate::error_context::location(
                py,
                crate::error_context::value_error(format!(
                    "collection length {} must equal source length {length}; a one-element collection is not a scalar",
                    bytes.len() / 8
                )),
                entry,
                parameter,
            ));
        }
        if !matches!(kind, Some("i" | "u")) {
            return Err(crate::error_context::argument(
                py,
                crate::error_context::type_error(
                    "requires integer fields, not a floating or non-integer dtype",
                ),
                entry,
                parameter,
                data,
            ));
        }
        let mut out = Vec::with_capacity(length);
        for (i, bytes) in bytes.chunks_exact(8).enumerate() {
            if mask.is_some_and(|m| m[i] != 0) {
                return Err(crate::error_context::location(
                    py,
                    crate::error_context::type_error(
                        "missing target parameter is not an integer; only explicit None may retain an optional field",
                    ),
                    entry,
                    &format!("{parameter}[{i}]"),
                ));
            }
            let raw: [u8; 8] = bytes
                .try_into()
                .map_err(|_| crate::error_context::runtime("invalid component bytes"))?;
            let value = if kind == Some("i") {
                i64::from_ne_bytes(raw)
            } else {
                i64::try_from(u64::from_ne_bytes(raw)).map_err(|_| {
                    crate::error_context::location(
                        py,
                        crate::error_context::overflow("integer component exceeds signed64"),
                        entry,
                        &format!("{parameter}[{i}]"),
                    )
                })?
            };
            out.push(component_range(Some(value), low, high).map_err(|e| {
                crate::error_context::location(py, e, entry, &format!("{parameter}[{i}]"))
            })?);
        }
        return Ok(Integers(Column::Values(out)));
    }
    let scalar = !column
        && (data.is_none()
            || crate::numeric::is_bool(data)
            || unsafe { pyo3::ffi::PyIndex_Check(data.as_ptr()) != 0 }
            || crate::numeric::supported_float(data)
            || data.is_instance_of::<PyString>()
            || data.is_instance_of::<pyo3::types::PyBytes>()
            || data.is_instance_of::<pyo3::types::PyByteArray>()
            || super::prepare::missing(data));
    if scalar {
        return convert(data)
            .map(|n| Integers(Column::Scalar(n)))
            .map_err(|e| crate::error_context::argument(py, e, entry, parameter, data));
    }
    let iterator = data.try_iter().map_err(crate::error_context::external)?;
    let mut values = Vec::with_capacity(length);
    for (i, value) in iterator.enumerate() {
        let value = value
            .map_err(crate::error_context::external)
            .map_err(|e| crate::error_context::item(py, e, entry, parameter, i, None, true))?;
        if i == length {
            return Err(crate::error_context::location(
                py,
                crate::error_context::value_error(format!(
                    "collection has more than {length} elements; targets must match source length"
                )),
                entry,
                parameter,
            ));
        }
        values.push(convert(&value).map_err(|e| {
            crate::error_context::item(py, e, entry, parameter, i, Some(&value), false)
        })?);
    }
    if values.len() != length {
        return Err(crate::error_context::location(
            py,
            crate::error_context::value_error(format!(
                "collection length {} must equal source length {length}",
                values.len()
            )),
            entry,
            parameter,
        ));
    }
    Ok(Integers(Column::Values(values)))
}
