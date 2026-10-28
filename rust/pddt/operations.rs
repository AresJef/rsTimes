//! Native field/relative transforms over one immutable date-buffer snapshot.
use super::arguments::Integers;
use super::common::{NS_DAY, Rows, finish, pack};
use super::zones::{Candidates, Policies};
use crate::epoch::{Parsed, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

pub(super) fn fields(ns: i128) -> PyResult<[i64; 8]> {
    let ordinal = i64::try_from(ns.div_euclid(NS_DAY) + 719_163)
        .map_err(|_| crate::error_context::overflow("calendar day exceeds native range"))?;
    let date = crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)?;
    let clock = ns.rem_euclid(NS_DAY);
    Ok([
        date[0],
        date[1],
        date[2],
        (clock / 3_600_000_000_000) as i64,
        (clock / 60_000_000_000 % 60) as i64,
        (clock / 1_000_000_000 % 60) as i64,
        (clock / 1000 % 1_000_000) as i64,
        (clock % 1000) as i64,
    ])
}
pub(super) fn nanos(f: [i64; 8]) -> PyResult<i128> {
    let day = crate::calendar::checked_ordinal(f[0], f[1], f[2])
        .map_err(crate::error_context::overflow)?;
    Ok((i128::from(day) - 719_163) * NS_DAY
        + ((i128::from(f[3]) * 60 + i128::from(f[4])) * 60 + i128::from(f[5])) * 1_000_000_000
        + i128::from(f[6]) * 1000
        + i128::from(f[7]))
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
        Candidates::Repeated(a, b) => Some(if wall - b == source_wall - source {
            b
        } else {
            a
        }),
        Candidates::Gap { .. } => None,
    };
    let candidate = super::zones::candidates(wall, zone)?;
    let Candidates::Gap { before, after } = candidate else {
        return select(candidate)
            .ok_or_else(|| crate::error_context::runtime("missing automatic candidate"));
    };
    let gap = i128::from(after - before) * 1000;
    let forward = if source_wall - source == i128::from(before) * 1000 {
        true
    } else if source_wall - source == i128::from(after) * 1000 {
        false
    } else {
        wall >= source_wall
    };
    for shifted in crate::calendar::calendar_gap_targets(wall, gap, forward)
        .into_iter()
        .flatten()
    {
        let candidate = super::zones::candidates(shifted, zone)?;
        let value = match candidate {
            Candidates::One(v) => Some(v),
            Candidates::Repeated(a, b) => Some(if shifted - b == source_wall - source {
                b
            } else {
                a
            }),
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
    let mut f = fields(wall)?;
    let get = |i: usize| args[i].0.get(row);
    if matches!(kind, "replace" | "adjust") {
        for (i, field) in f.iter_mut().enumerate() {
            if let Some(value) = get(i) {
                *field = value;
            }
        }
        if get(6).is_some() && get(7).is_none() {
            f[7] = 0;
        }
        let last = crate::calendar::days_in_month(f[0], f[1]);
        if f[2] > last {
            if kind == "replace" {
                return Err(crate::error_context::value_error(format!(
                    "day {} is invalid for year {} and month {}",
                    f[2], f[0], f[1]
                )));
            }
            f[2] = last;
        }
        return nanos(f);
    }
    let required = |i| {
        get(i).ok_or_else(|| crate::error_context::runtime("required component was not prepared"))
    };
    let (months, days, clock, month, day) = if matches!(kind, "add" | "sub") {
        let sign = if kind == "sub" { -1 } else { 1 };
        let months = (i128::from(required(0)?) * 12
            + i128::from(required(1)?) * 3
            + i128::from(required(2)?))
            * sign;
        let days = (i128::from(required(3)?) * 7 + i128::from(required(4)?)) * sign;
        let clock = ((((i128::from(required(5)?) * 60 + i128::from(required(6)?)) * 60
            + i128::from(required(7)?))
            * 1000
            + i128::from(required(8)?))
            * 1000
            + i128::from(required(9)?))
            * 1000
            + i128::from(required(10)?);
        (months, days, clock * sign, None, None)
    } else {
        let offset = i128::from(required(0)?);
        match kind {
            "year" => (offset * 12, 0, 0, get(1), get(2)),
            "quarter" => (
                offset * 3,
                0,
                0,
                get(1).map(|v| (f[1] - 1) / 3 * 3 + v),
                get(2),
            ),
            "month" => (offset, 0, 0, None, get(1)),
            "weekday" => {
                let ordinal = crate::calendar::checked_ordinal(f[0], f[1], f[2])
                    .map_err(crate::error_context::overflow)?;
                (
                    0,
                    offset * 7 + get(1).map_or(0, |v| i128::from(v - (ordinal - 1).rem_euclid(7))),
                    0,
                    None,
                    None,
                )
            }
            "day" => (0, offset, 0, None, None),
            _ => return Err(crate::error_context::runtime("unknown calendar transform")),
        }
    };
    let date = crate::calendar::move_date([f[0], f[1], f[2]], months, days, month, day)
        .map_err(crate::error_context::overflow)?;
    f[..3].copy_from_slice(&date);
    nanos(f)?
        .checked_add(clock)
        .ok_or_else(|| crate::error_context::overflow("calendar clock increment overflow"))
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
