//! Checked resolution changes over owned, initialized int64 date buffers.

use pyo3::buffer::PyBuffer;
use pyo3::exceptions::PyBufferError;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBytes, PyType};

use crate::epoch::Unit;

static ARRAY_TYPE: PyOnceLock<Py<PyType>> = PyOnceLock::new();

/// Captured at the old snapshot point, before any later Python argument runs.
/// Geometry cannot change and the exact bytes owner is genuinely immutable.
#[pyclass(frozen, skip_from_py_object, name = "_PddtTicks")]
struct TickSpan {
    owner: Py<PyBytes>,
    start: usize,
    end: usize,
}

/// Both forms own immutable bytes through the kernel's last read. A span never
/// constructs an immutable Rust slice over a writable ndarray or PyBuffer.
pub(super) struct InputBytes<'py> {
    owner: Bound<'py, PyBytes>,
    start: usize,
    end: usize,
}
impl<'a, 'py> FromPyObject<'a, 'py> for InputBytes<'py> {
    type Error = PyErr;
    fn extract(value: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        if let Ok(bytes) = value.cast::<PyBytes>() {
            return Ok(Self {
                owner: bytes.to_owned(),
                start: 0,
                end: bytes.as_bytes().len(),
            });
        }
        let span = value.cast::<TickSpan>()?.borrow();
        Ok(Self {
            owner: span.owner.bind(value.py()).clone(),
            start: span.start,
            end: span.end,
        })
    }
}
impl InputBytes<'_> {
    #[inline]
    pub(super) fn as_slice(&self) -> PyResult<&[u8]> {
        self.owner
            .as_bytes()
            .get(self.start..self.end)
            .ok_or_else(|| {
                crate::error_context::runtime("captured date bytes exceed their immutable owner")
            })
    }
}

/// Borrow only a proved native, contiguous span of an exact bytes root.
/// Every other source performs its actual old tobytes call here, at the same
/// evaluation point; read-only flags alone never establish immutability.
#[pyfunction]
fn _pddt_data<'py>(data: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let py = data.py();
    let snapshot = || {
        data.call_method0(pyo3::intern!(py, "tobytes"))
            .map_err(crate::error_context::external)?
            .cast_into::<PyBytes>()
            .map(Bound::into_any)
            .map_err(Into::into)
    };
    let kind = ARRAY_TYPE
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("NumPy date buffer type is unavailable"))?
        .bind(py);
    if !data.get_type().is(kind) {
        return snapshot();
    }
    let buffer = match PyBuffer::<i64>::get(data) {
        Ok(buffer) => buffer,
        Err(error) if error.is_instance_of::<PyBufferError>(py) => return snapshot(),
        Err(error) => return Err(error),
    };
    if buffer.dimensions() != 1
        || !buffer.readonly()
        || buffer.len_bytes() == 0
        || buffer.as_slice(py).is_none()
    {
        return snapshot();
    }
    let mut owner = data.clone();
    while owner.get_type().is(kind) {
        owner = owner.getattr(pyo3::intern!(py, "base"))?;
    }
    if !owner.is_exact_instance_of::<PyBytes>() {
        return snapshot();
    }
    let owner = owner.cast_into::<PyBytes>()?;
    let Some(start) = (buffer.buf_ptr() as usize).checked_sub(owner.as_bytes().as_ptr() as usize)
    else {
        return snapshot();
    };
    let Some(end) = start
        .checked_add(buffer.len_bytes())
        .filter(|end| *end <= owner.as_bytes().len())
    else {
        return snapshot();
    };
    if start == 0 && end == owner.as_bytes().len() {
        return Ok(owner.into_any());
    }
    Py::new(
        py,
        TickSpan {
            owner: owner.unbind(),
            start,
            end,
        },
    )
    .map(|span| span.into_bound(py).into_any())
}

/// Change an immutable tick snapshot without Python scalars in the loop.
#[pyfunction]
#[pyo3(signature=(data, source_unit, target_unit, round_ok, entry, multiplier=1))]
fn _pddt_rescale<'py>(
    py: Python<'py>,
    data: InputBytes<'py>,
    source_unit: &str,
    target_unit: &str,
    round_ok: bool,
    entry: &str,
    multiplier: i64,
) -> PyResult<Bound<'py, PyBytes>> {
    let data = data.as_slice()?;
    let source = Unit::parse(source_unit)?.nanos();
    let target = Unit::parse(target_unit)?.nanos();
    if !data.len().is_multiple_of(8) || multiplier < 1 {
        return Err(crate::error_context::value_error(
            "invalid date buffer or dtype multiplier",
        ));
    }
    let scale = source
        .checked_mul(i128::from(multiplier))
        .ok_or_else(|| crate::error_context::overflow("date unit multiplier is too large"))?;
    PyBytes::new_with(py, data.len(), |output| {
        for (index, (input, output)) in data
            .as_chunks::<8>()
            .0
            .iter()
            .zip(output.as_chunks_mut::<8>().0.iter_mut())
            .enumerate()
        {
            let mut raw = [0; 8];
            raw.copy_from_slice(input);
            let tick = i64::from_ne_bytes(raw);
            let converted = if tick == i64::MIN {
                tick
            } else {
                let nanos = i128::from(tick).checked_mul(scale).ok_or_else(|| {
                    crate::error_context::overflow("date unit conversion overflow")
                })?;
                match crate::precision::epoch_tick(nanos, target, round_ok) {
                    Err(crate::precision::TickError::Precision) => {
                        return Err(crate::error_context::location(
                            py,
                            crate::error_context::value_error(
                                "cannot preserve the date at this unit; choose a finer unit or explicitly allow rounding",
                            ),
                            entry,
                            &format!("data[{index}]"),
                        ));
                    }
                    Err(crate::precision::TickError::Capacity) | Ok(i64::MIN) => {
                        return Err(crate::error_context::location(
                            py,
                            crate::error_context::overflow(
                                "date is outside the requested unit range; choose a coarser unit",
                            ),
                            entry,
                            &format!("data[{index}]"),
                        ));
                    }
                    Ok(value) => value,
                }
            };
            output.copy_from_slice(&converted.to_ne_bytes());
        }
        Ok(())
    })
}

/// Register the small buffer boundary without changing scalar parser semantics.
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    let kind = py
        .import("numpy")?
        .getattr("ndarray")?
        .cast_into::<PyType>()?
        .unbind();
    let _ = ARRAY_TYPE.set(py, kind);
    module.add_class::<TickSpan>()?;
    module.add_function(wrap_pyfunction!(_pddt_data, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_rescale, module)?)
}
