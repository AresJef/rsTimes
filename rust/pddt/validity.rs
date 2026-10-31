//! Source-role validity. NumPy/pandas use the MIN sentinel; Polars dates use
//! independent validity, including an allocation-free all-valid representation.
use pyo3::buffer::PyBuffer;
use pyo3::prelude::*;

#[derive(Clone, Copy)]
pub(super) struct TemporalValidity<'a> {
    mask: Option<&'a [u8]>,
}
impl<'a> TemporalValidity<'a> {
    /// None is the existing sentinel domain. Some(empty) is native all-valid;
    /// otherwise one nonzero byte means a missing source row.
    pub(super) fn new(mask: Option<&'a [u8]>, count: usize) -> PyResult<Self> {
        if mask.is_some_and(|mask| !mask.is_empty() && mask.len() != count) {
            return Err(crate::error_context::runtime(
                "temporal validity length does not match its values",
            ));
        }
        Ok(Self { mask })
    }
    #[inline]
    pub(super) fn missing(self, index: usize, tick: i64) -> bool {
        match self.mask {
            None => tick == i64::MIN,
            Some([]) => false,
            Some(mask) => mask[index] != 0,
        }
    }
}

/// The unchanged-coordinate fast path borrows the actual typed buffer only for
/// this check. PyBuffer owns its exporter and ReadOnlyCell permits Python aliases;
/// no borrowed Rust slice of immutable i64 is invented over mutable storage.
#[pyfunction]
fn _pddt_check_native_dates(data: &Bound<'_, PyAny>, mask: &[u8], entry: &str) -> PyResult<()> {
    let buffer = PyBuffer::<i64>::get(data)?;
    if buffer.dimensions() != 1 {
        return Err(crate::error_context::runtime(
            "native temporal buffer must be one-dimensional",
        ));
    }
    let values = buffer.as_slice(data.py()).ok_or_else(|| {
        crate::error_context::runtime("native temporal buffer must be contiguous and native-endian")
    })?;
    let validity = TemporalValidity::new(Some(mask), values.len())?;
    for (i, value) in values.iter().enumerate() {
        let tick = value.get();
        if tick == i64::MIN && !validity.missing(i, tick) {
            return Err(crate::error_context::location(
                data.py(),
                crate::error_context::overflow(
                    "valid source date collides with the target's reserved NaT value; explicitly convert the source if losing this value is intended",
                ),
                entry,
                &format!("result[{i}]"),
            ));
        }
    }
    Ok(())
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_check_native_dates, module)?)
}
