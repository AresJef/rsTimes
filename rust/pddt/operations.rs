//! Native field/relative transforms over one immutable date-buffer snapshot.
use super::arguments::Integers;
use super::common::{Rows, finish, pack};
use super::zones::{Candidates, Policies};
use crate::epoch::{Parsed, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

fn transform_error(error: crate::date_transform::Error) -> PyErr {
    match error {
        crate::date_transform::Error::Value(message) => crate::error_context::value_error(message),
        crate::date_transform::Error::Capacity(message) => crate::error_context::overflow(message),
    }
}
pub(super) fn fields(ns: i128) -> PyResult<[i64; 8]> {
    crate::date_transform::fields(ns).map_err(transform_error)
}
pub(super) fn nanos(fields: [i64; 8]) -> PyResult<i128> {
    crate::date_transform::nanos(fields).map_err(transform_error)
}

/// Prefer the actual source offset, constrained to a valid target calendar day.
/// Regional candidate probing is deliberately absent from naive/fixed loops.
pub(super) fn automatic(
    wall: i128,
    source: i128,
    source_wall: i128,
    zone: &Bound<'_, PyAny>,
) -> PyResult<i128> {
    let select = |c: Candidates| match c {
        Candidates::One(v) => Some(v),
        Candidates::Repeated(a, b) => Some(crate::calendar::calendar_repeat(
            wall,
            source_wall - source,
            a,
            b,
        )),
        Candidates::Gap { .. } => None,
    };
    let candidate = super::zones::candidates(wall, zone)?;
    let Candidates::Gap { before, after } = candidate else {
        return select(candidate)
            .ok_or_else(|| crate::error_context::runtime("missing automatic candidate"));
    };
    let gap = i128::from(after - before) * 1000;
    let forward = crate::calendar::calendar_gap_forward(
        wall,
        source_wall,
        source_wall - source,
        i128::from(before) * 1000,
        i128::from(after) * 1000,
    );
    for shifted in crate::calendar::calendar_gap_targets(wall, gap, forward)
        .into_iter()
        .flatten()
    {
        let candidate = super::zones::candidates(shifted, zone)?;
        let value = match candidate {
            Candidates::One(v) => Some(v),
            Candidates::Repeated(a, b) => Some(crate::calendar::calendar_repeat(
                shifted,
                source_wall - source,
                a,
                b,
            )),
            Candidates::Gap { .. } => None,
        };
        if let Some(value) = value {
            return Ok(value);
        }
    }
    Err(crate::error_context::value_error(
        "the selected calendar day has no valid local result; choose another date",
    ))
}

fn transformed(wall: i128, kind: &str, args: &[PyRef<'_, Integers>], row: usize) -> PyResult<i128> {
    crate::date_transform::transform(wall, kind, |index| args[index].0.get(row))
        .map_err(transform_error)
}

type Output<'py> = (Bound<'py, PyBytes>, &'static str, Py<PyAny>, bool);

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One native array transform with prepared columns and explicit replacement zone"
)]
#[pyo3(signature=(data,unit,zone,kind,components,entry,policy=None,target=None,replace_zone=false))]
fn _pddt_transform<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    kind: &str,
    components: Vec<Py<Integers>>,
    entry: &str,
    policy: Option<PyRef<'_, Policies>>,
    target: Option<&Bound<'py, PyAny>>,
    replace_zone: bool,
) -> PyResult<Output<'py>> {
    if data.len() % 8 != 0 {
        return Err(crate::error_context::runtime("invalid date buffer"));
    }
    let unit = Unit::parse(unit)?;
    let source = zone.filter(|v| !v.is_none());
    let output = if replace_zone {
        target.filter(|v| !v.is_none())
    } else {
        source
    };
    let count = data.len() / 8;
    let expected = match kind {
        "replace" | "adjust" => 8,
        "add" | "sub" => 11,
        "year" | "quarter" => 3,
        "month" | "weekday" => 2,
        "day" => 1,
        _ => 0,
    };
    if expected == 0 || components.len() != expected {
        return Err(crate::error_context::runtime(
            "invalid prepared transform components",
        ));
    }
    let args: Vec<_> = components.iter().map(|v| v.borrow(py)).collect();
    if args.iter().any(|a| a.0.len().is_some_and(|n| n != count)) {
        return Err(crate::error_context::value_error(
            "every target column must match source length",
        ));
    }
    let source_zone = source.map_or(Zone::Naive, |v| Zone::Object(v.clone().unbind()));
    let output_zone = output.map_or(Zone::Naive, |v| Zone::Object(v.clone().unbind()));
    let source_fixed = super::common::fixed_offset(py, &source_zone)?;
    let output_fixed = super::common::fixed_offset(py, &output_zone)?;
    let same = super::common::same_zone(py, &source_zone, &output_zone)?;
    let mut changed_any = !same;
    let mut rows = Rows::new(unit);
    if policy.is_some() {
        rows.reserve(count)?;
    }
    let mut values = Vec::new();
    if policy.is_none() {
        values.try_reserve_exact(count).map_err(|_| {
            pyo3::exceptions::PyMemoryError::new_err("cannot allocate date results")
        })?;
    }
    for (i, bytes) in data.chunks_exact(8).enumerate() {
        let raw: [u8; 8] = bytes
            .try_into()
            .map_err(|_| crate::error_context::runtime("invalid date tick"))?;
        let tick = i64::from_ne_bytes(raw);
        if tick == i64::MIN {
            if policy.is_some() {
                rows.missing();
            } else {
                values.push(None);
            }
            continue;
        }
        let instant = i128::from(tick) * unit.nanos();
        let wall = if let Some(offset) = source_fixed {
            instant + i128::from(offset) * 1000
        } else {
            super::zones::utc_wall(
                instant,
                source.ok_or_else(|| crate::error_context::runtime("missing source region"))?,
                None,
            )?
        };
        let changed = transformed(wall, kind, &args, i)
            .map_err(|e| crate::error_context::location(py, e, entry, &format!("result[{i}]")))?;
        if policy.is_some() {
            let unchanged = changed == wall && same;
            changed_any |= !unchanged;
            rows.push(
                py,
                Parsed {
                    nanos: if unchanged { instant } else { changed },
                    unit,
                    zone: Zone::Naive,
                },
                unchanged,
            )?;
        } else {
            let value = if changed == wall && same {
                instant
            } else if let Some(offset) = output_fixed {
                changed - i128::from(offset) * 1000
            } else {
                automatic(
                    changed,
                    instant,
                    wall,
                    output.ok_or_else(|| crate::error_context::runtime("missing result region"))?,
                )
                .map_err(|e| {
                    crate::error_context::location(py, e, entry, &format!("result[{i}]"))
                })?
            };
            changed_any |= value != instant;
            values.push(Some(value));
        }
    }
    let (packed, zone) = if let Some(policy) = &policy {
        let (packed, _, zone) = finish(py, rows, Some(unit), output, entry, policy)?;
        (packed, zone)
    } else {
        (
            pack(py, &values, unit, true, entry)?,
            output.map_or_else(|| py.None(), |v| v.clone().unbind()),
        )
    };
    Ok((packed, unit.name(), zone, changed_any))
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_transform, module)?)
}
