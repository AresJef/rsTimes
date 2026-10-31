//! Versioned core payloads and real native deep buffers, separate from business state.
use crate::parser::Truth;
use polars::prelude::*;
use polars::series::IsSorted;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3_polars::PySeries;
type Core<'py> = (
    Bound<'py, PyBytes>,
    Bound<'py, PyBytes>,
    &'static str,
    Option<String>,
    String,
    u8,
);
fn order(value: IsSorted) -> u8 {
    match value {
        IsSorted::Not => 0,
        IsSorted::Ascending => 1,
        IsSorted::Descending => 2,
    }
}
#[pyfunction]
fn _pldt_core(py: Python<'_>, source: PySeries, sorted: u8) -> PyResult<Core<'_>> {
    let DataType::Datetime(unit, zone) = source.0.dtype() else {
        return Err(crate::error_context::type_error(
            "Pldt state requires a Datetime source",
        ));
    };
    let dates = source.0.datetime().map_err(super::eager_error)?;
    let length = source.0.len();
    let size = length
        .checked_mul(8)
        .filter(|v| *v <= isize::MAX as usize)
        .ok_or_else(|| crate::error_context::overflow("date state exceeds native byte capacity"))?;
    let mut mask = if source.0.null_count() == 0 {
        Vec::new()
    } else {
        vec![0u8; length.div_ceil(8)]
    };
    let data = PyBytes::new_with(py, size, |bytes| {
        for (row, (value, out)) in dates
            .physical()
            .iter()
            .zip(bytes.as_chunks_mut::<8>().0.iter_mut())
            .enumerate()
        {
            out.copy_from_slice(&value.unwrap_or(0).to_le_bytes());
            if !mask.is_empty() && value.is_some() {
                mask[row / 8] |= 1 << (row % 8);
            }
        }
        Ok(())
    })?;
    let unit = match unit {
        TimeUnit::Milliseconds => "ms",
        TimeUnit::Microseconds => "us",
        TimeUnit::Nanoseconds => "ns",
    };
    Ok((
        data,
        PyBytes::new(py, &mask),
        unit,
        zone.as_ref().map(ToString::to_string),
        source.0.name().as_str().to_owned(),
        sorted,
    ))
}
/// Packing/restoration already visits all values. Check any retained sorted
/// promise in that same pass; never preserve a forged/stale assertion blindly.
fn build(
    values: impl Iterator<Item = Option<i64>>,
    len: usize,
    name: PlSmallStr,
    unit: TimeUnit,
    zone: Option<TimeZone>,
    sorted: u8,
) -> Series {
    let mut output = PrimitiveChunkedBuilder::<Int64Type>::new(name, len);
    let (mut previous, mut asc, mut desc, mut leading, mut trailing, mut internal) =
        (None, true, true, false, false, false);
    for value in values {
        output.append_option(value);
        if let Some(value) = value {
            if let Some(previous) = previous {
                asc &= value >= previous;
                desc &= value <= previous;
            }
            if trailing {
                internal = true;
            }
            previous = Some(value);
        } else if previous.is_some() {
            trailing = true;
        } else {
            leading = true;
        }
    }
    let mut result = output.finish().into_datetime(unit, zone).into_series();
    let legal_nulls = !(internal || leading && trailing);
    result.set_sorted_flag(match sorted {
        1 if asc && legal_nulls => IsSorted::Ascending,
        2 if desc && legal_nulls => IsSorted::Descending,
        _ => IsSorted::Not,
    });
    result
}
#[pyfunction]
fn _pldt_restore_core<'py>(
    data: &[u8],
    validity: &[u8],
    unit: &str,
    zone: Option<&str>,
    name: &str,
    sorted: u8,
    target: &Bound<'py, PyAny>,
) -> PyResult<(Bound<'py, PyAny>, u8)> {
    let py = target.py();
    if !data.len().is_multiple_of(8) {
        return Err(crate::error_context::value_error(
            "state.values length must be a multiple of eight bytes",
        ));
    }
    let count = data.len() / 8;
    if !validity.is_empty() && (validity.len() != count.div_ceil(8) || count == 0) {
        return Err(crate::error_context::value_error(
            "state.validity length must match the date row count",
        ));
    }
    if !count.is_multiple_of(8)
        && !validity.is_empty()
        && validity[validity.len() - 1] & !((1u8 << (count % 8)) - 1) != 0
    {
        return Err(crate::error_context::value_error(
            "unused state.validity bits must be zero",
        ));
    }
    if sorted > 2 {
        return Err(crate::error_context::value_error(
            "state.sorted must be zero, one or two",
        ));
    }
    let unit = super::input::selected(Some(unit))?
        .ok_or_else(|| crate::error_context::value_error("state.unit must be ms/us/ns"))?;
    if let Some(zone) = zone {
        crate::temporal_zone::Zone::named(zone).map_err(crate::error_context::value_error)?;
    }
    let timezone = TimeZone::opt_try_new(zone).map_err(super::eager_error)?;
    let values = data
        .as_chunks::<8>()
        .0
        .iter()
        .enumerate()
        .map(|(row, raw)| {
            if !validity.is_empty() && validity[row / 8] & (1 << (row % 8)) == 0 {
                None
            } else {
                let mut bytes = [0; 8];
                bytes.copy_from_slice(raw);
                Some(i64::from_le_bytes(bytes))
            }
        });
    let result = build(
        values,
        count,
        name.into(),
        super::input::resolution(unit),
        timezone,
        sorted,
    );
    let sorted = order(result.is_sorted_flag());
    Ok((super::export(py, &result, target)?, sorted))
}
#[pyfunction]
fn _pldt_copy_core<'py>(
    source: PySeries,
    deep: Truth,
    sorted: u8,
    target: &Bound<'py, PyAny>,
) -> PyResult<(Bound<'py, PyAny>, u8)> {
    let py = target.py();
    let result = if deep.0 {
        let DataType::Datetime(unit, zone) = source.0.dtype() else {
            return Err(crate::error_context::type_error(
                "Pldt copy requires a Datetime source",
            ));
        };
        let values = source.0.datetime().map_err(super::eager_error)?.physical();
        build(
            values.iter(),
            source.0.len(),
            source.0.name().clone(),
            *unit,
            zone.clone(),
            sorted,
        )
    } else {
        source.0.clone()
    };
    let sorted = if deep.0 {
        order(result.is_sorted_flag())
    } else {
        sorted
    };
    Ok((super::export(py, &result, target)?, sorted))
}
/// Official SDK handle export avoids an unrelated business clone/new callback.
#[pyfunction]
fn _pldt_snapshot<'py>(
    source: PySeries,
    target: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    super::export(target.py(), &source.0, target)
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_snapshot, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_core, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_restore_core, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_copy_core, module)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pure_rebuild_retains_valid_minimum_and_does_not_forge_sorting() {
        std::thread::spawn(|| {
            let result = build(
                [Some(i64::MIN), None, Some(i64::MAX)].into_iter(),
                3,
                "events".into(),
                TimeUnit::Nanoseconds,
                None,
                1,
            );
            assert_eq!(
                result
                    .datetime()
                    .unwrap()
                    .physical()
                    .iter()
                    .collect::<Vec<_>>(),
                vec![Some(i64::MIN), None, Some(i64::MAX)]
            );
            assert_eq!(result.is_sorted_flag(), IsSorted::Not);
            let result = build(
                [Some(i64::MIN), Some(0), Some(i64::MAX)].into_iter(),
                3,
                "events".into(),
                TimeUnit::Nanoseconds,
                None,
                1,
            );
            assert_eq!(result.is_sorted_flag(), IsSorted::Ascending);
        })
        .join()
        .unwrap();
    }
}
