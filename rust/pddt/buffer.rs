//! Checked resolution changes over owned, initialized int64 date buffers.

use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::epoch::Unit;

/// Change an immutable tick snapshot without Python scalars in the loop.
#[pyfunction]
#[pyo3(signature=(data, source_unit, target_unit, round_ok, entry, multiplier=1))]
fn _pddt_rescale<'py>(
    py: Python<'py>,
    data: &[u8],
    source_unit: &str,
    target_unit: &str,
    round_ok: bool,
    entry: &str,
    multiplier: i64,
) -> PyResult<Bound<'py, PyBytes>> {
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
    module.add_function(wrap_pyfunction!(_pddt_rescale, module)?)
}
