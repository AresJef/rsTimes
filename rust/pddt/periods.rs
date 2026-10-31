//! Native calendar bounds, shared by boundary transforms and direct predicates.
use super::common::{NS_DAY, pack};
use super::zones::Candidates;
use crate::epoch::{Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

pub(super) use crate::period::Period;
use crate::period::Snap;
impl From<crate::period::Error> for PyErr {
    fn from(error: crate::period::Error) -> Self {
        match error {
            crate::period::Error::Value(message) => crate::error_context::value_error(message),
            crate::period::Error::Capacity(message) => crate::error_context::overflow(message),
            crate::period::Error::Internal(message) => crate::error_context::runtime(message),
        }
    }
}
fn align(value: i128, unit: Unit, end: bool) -> PyResult<i128> {
    crate::period::align(value, unit.nanos(), end).map_err(PyErr::from)
}

/// Actual candidates at a local bound, clipped to this period and output lattice.
pub(super) fn edge_candidates(
    lower: i128,
    upper: i128,
    end: bool,
    zone: &Bound<'_, PyAny>,
    unit: Unit,
) -> PyResult<[Option<i128>; 2]> {
    let wall = if end { upper - 1 } else { lower };
    let mut candidate = super::zones::candidates(wall, zone)?;
    if let Candidates::Gap { before, after } = candidate {
        let wall_us = i64::try_from(wall.div_euclid(1000))
            .map_err(|_| crate::error_context::overflow("regional boundary overflow"))?;
        let (last, first) = crate::pydt::gap_edges(wall_us, after - before, zone)?;
        let shifted = if end {
            (i128::from(last) + 1) * 1000 - 1
        } else {
            i128::from(first) * 1000
        };
        if shifted < lower || shifted >= upper {
            return Ok([None, None]);
        }
        candidate = super::zones::candidates(shifted, zone)?;
    }
    let values = match candidate {
        Candidates::One(value) => [Some(value), None],
        Candidates::Repeated(a, b) => [Some(a), Some(b)],
        Candidates::Gap { .. } => {
            return Err(crate::error_context::value_error(
                "timezone cannot confirm a valid period boundary",
            ));
        }
    };
    let mut result = [None, None];
    for (i, value) in values.into_iter().enumerate() {
        if let Some(value) = value {
            let selected = align(value, unit, end)?;
            let local = super::zones::utc_wall(selected, zone, None)?;
            if (lower..upper).contains(&local) {
                result[i] = Some(selected);
            }
        }
    }
    Ok(result)
}

fn edge(
    bounds: (i128, i128),
    end: bool,
    clock: bool,
    original: (i128, i128),
    zone: Option<&Bound<'_, PyAny>>,
    fixed: Option<i64>,
    unit: Unit,
) -> PyResult<Option<i128>> {
    let (lower, upper) = bounds;
    let (source, source_wall) = original;
    let wall = if end { upper - 1 } else { lower };
    if let Some(offset) = fixed {
        let value = align(wall - i128::from(offset) * 1000, unit, end)?;
        return Ok(
            ((lower..upper).contains(&(value + i128::from(offset) * 1000))).then_some(value),
        );
    }
    let zone = zone.ok_or_else(|| crate::error_context::runtime("missing period region"))?;
    let choices = edge_candidates(lower, upper, end, zone, unit)?;
    if clock {
        let offset = source_wall - source;
        for value in choices.into_iter().flatten() {
            let local = super::zones::utc_wall(value, zone, None)?;
            if local - value == offset {
                return Ok(Some(value));
            }
        }
    }
    Ok(if end {
        choices.into_iter().flatten().max()
    } else {
        choices.into_iter().flatten().min()
    })
}

type Output<'py> = (Bound<'py, PyBytes>, bool);

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One period dispatch outside a native row loop"
)]
fn _pddt_period<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    token: &str,
    mode: u8,
    query: bool,
    entry: &str,
) -> PyResult<Output<'py>> {
    if !data.len().is_multiple_of(8) {
        return Err(crate::error_context::runtime("invalid date source buffer"));
    }
    let period = Period::parse(token, mode >= 2)?;
    let unit = Unit::parse(unit)?;
    let zone = zone.filter(|v| !v.is_none());
    let fixed = super::common::fixed_offset(
        py,
        &zone.map_or(Zone::Naive, |z| Zone::Object(z.clone().unbind())),
    )?;
    let mut values = Vec::new();
    let mut flags = Vec::new();
    if query {
        flags.reserve(data.len() / 8);
    } else {
        values.reserve(data.len() / 8);
    }
    let mut changed = false;
    for (i, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        let raw: [u8; 8] = *bytes;
        let tick = i64::from_ne_bytes(raw);
        if tick == i64::MIN {
            if query {
                flags.push(0)
            } else {
                values.push(None)
            };
            continue;
        }
        let instant = i128::from(tick) * unit.nanos();
        let wall = if let Some(offset) = fixed {
            instant + i128::from(offset) * 1000
        } else {
            super::zones::utc_wall(
                instant,
                zone.ok_or_else(|| crate::error_context::runtime("missing period region"))?,
                None,
            )?
        };
        let (lower, upper) = period.bounds(wall)?;
        let end = mode % 2 == 1;
        let target = if mode < 2 {
            let day = (if end { upper - 1 } else { lower }).div_euclid(NS_DAY);
            if query {
                flags.push(u8::from(day == wall.div_euclid(NS_DAY)));
                continue;
            }
            let result = day * NS_DAY + wall.rem_euclid(NS_DAY);
            Some(if result == wall {
                instant
            } else if let Some(offset) = fixed {
                result - i128::from(offset) * 1000
            } else {
                super::operations::automatic(
                    result,
                    instant,
                    wall,
                    zone.ok_or_else(|| crate::error_context::runtime("missing period region"))?,
                )?
            })
        } else {
            if query {
                let edge_day = (if end { upper - 1 } else { lower }).div_euclid(NS_DAY);
                if !(lower..upper).contains(&wall) {
                    flags.push(0);
                    continue;
                }
                if wall.div_euclid(NS_DAY) != edge_day
                    && (fixed.is_some() || (wall.div_euclid(NS_DAY) - edge_day).abs() > 2)
                {
                    flags.push(0);
                    continue;
                }
            }
            edge(
                (lower, upper),
                end,
                period.clock(),
                (instant, wall),
                zone,
                fixed,
                unit,
            )
            .map_err(|e| crate::error_context::location(py, e, entry, &format!("result[{i}]")))?
        };
        if query {
            flags.push(u8::from(target == Some(instant)));
        } else {
            let value = target.ok_or_else(|| {
                crate::error_context::location(
                    py,
                    crate::error_context::value_error(
                        "the requested period has no existing representable local time",
                    ),
                    entry,
                    &format!("result[{i}]"),
                )
            })?;
            changed |= value != instant;
            values.push(Some(value));
        }
    }
    if query {
        Ok((PyBytes::new(py, &flags), false))
    } else {
        Ok((pack(py, &values, unit, true, entry)?, changed))
    }
}

#[pyfunction]
fn _pddt_fsp<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    precision: i64,
    entry: &str,
) -> PyResult<Output<'py>> {
    if precision < 0 {
        return Err(crate::error_context::value_error(
            "precision must be nonnegative",
        ));
    }
    if !data.len().is_multiple_of(8) {
        return Err(crate::error_context::runtime("invalid date source buffer"));
    }
    if precision >= 9 {
        return Ok((PyBytes::new(py, data), false));
    }
    let unit = Unit::parse(unit)?;
    let factor = 10_i128.pow((9 - precision) as u32);
    let zone = zone.filter(|v| !v.is_none());
    let fixed = super::common::fixed_offset(
        py,
        &zone.map_or(Zone::Naive, |z| Zone::Object(z.clone().unbind())),
    )?;
    let mut values = Vec::with_capacity(data.len() / 8);
    let mut changed = false;
    for (i, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        let raw: [u8; 8] = *bytes;
        let tick = i64::from_ne_bytes(raw);
        if tick == i64::MIN {
            values.push(None);
            continue;
        }
        let source = i128::from(tick) * unit.nanos();
        let wall = if let Some(offset) = fixed {
            source + i128::from(offset) * 1000
        } else {
            super::zones::utc_wall(
                source,
                zone.ok_or_else(|| crate::error_context::runtime("missing fractional region"))?,
                None,
            )?
        };
        let selected = wall.div_euclid(factor) * factor;
        let value = if selected == wall {
            source
        } else if let Some(offset) = fixed {
            selected - i128::from(offset) * 1000
        } else {
            super::operations::automatic(
                selected,
                source,
                wall,
                zone.ok_or_else(|| crate::error_context::runtime("missing fractional region"))?,
            )
            .map_err(|e| crate::error_context::location(py, e, entry, &format!("result[{i}]")))?
        };
        changed |= value != source;
        values.push(Some(value));
    }
    Ok((pack(py, &values, unit, true, entry)?, changed))
}

fn direction(value: i128, source: i128, mode: u8) -> bool {
    crate::period::direction(value, source, mode)
}
fn rounded(
    wall: i128,
    source: i128,
    step: i128,
    mode: u8,
    zone: &Bound<'_, PyAny>,
) -> PyResult<i128> {
    let select = |candidate: Candidates| -> Option<i128> {
        let choices = match candidate {
            Candidates::One(v) => [Some(v), None],
            Candidates::Repeated(a, b) => [Some(a), Some(b)],
            Candidates::Gap { .. } => [None, None],
        };
        choices
            .into_iter()
            .flatten()
            .filter(|v| direction(*v, source, mode))
            .min_by_key(|v| ((*v - source).abs(), *v))
    };
    let candidate = super::zones::candidates(wall, zone)?;
    let Candidates::Gap { before, after } = candidate else {
        return select(candidate).ok_or_else(|| {
            crate::error_context::value_error(
                "no rounded local occurrence preserves the requested direction",
            )
        });
    };
    let (last, first) = crate::pydt::gap_edges(
        i64::try_from(wall.div_euclid(1000))
            .map_err(|_| crate::error_context::overflow("regional rounding overflow"))?,
        after - before,
        zone,
    )?;
    let last = (i128::from(last) + 1) * 1000 - 1;
    let first = i128::from(first) * 1000;
    let lower = last.div_euclid(step) * step;
    let upper = (first.div_euclid(step) + i128::from(first.rem_euclid(step) != 0)) * step;
    let mut best = None;
    for wall in [lower, upper] {
        if let Some(value) = select(super::zones::candidates(wall, zone)?)
            && best.is_none_or(|previous: i128| {
                (value - source).abs() < (previous - source).abs()
                    || ((value - source).abs() == (previous - source).abs() && value > previous)
            })
        {
            best = Some(value);
        }
    }
    best.ok_or_else(|| {
        crate::error_context::value_error(
            "no valid rounded boundary preserves the requested direction",
        )
    })
}

#[pyfunction]
fn _pddt_round<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    step: i128,
    mode: u8,
    entry: &str,
) -> PyResult<Output<'py>> {
    if !data.len().is_multiple_of(8) || step <= 0 || mode > 2 {
        return Err(crate::error_context::value_error(
            "invalid rounding grid or mode",
        ));
    }
    let unit = Unit::parse(unit)?;
    let zone = zone.filter(|v| !v.is_none());
    let fixed = super::common::fixed_offset(
        py,
        &zone.map_or(Zone::Naive, |z| Zone::Object(z.clone().unbind())),
    )?;
    let mut values = Vec::with_capacity(data.len() / 8);
    let mut changed = false;
    for (i, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        let raw: [u8; 8] = *bytes;
        let ticks = i64::from_ne_bytes(raw);
        if ticks == i64::MIN {
            values.push(None);
            continue;
        }
        let source = i128::from(ticks) * unit.nanos();
        let wall = if let Some(offset) = fixed {
            source + i128::from(offset) * 1000
        } else {
            super::zones::utc_wall(
                source,
                zone.ok_or_else(|| crate::error_context::runtime("missing rounding region"))?,
                None,
            )?
        };
        let target = crate::period::rounded(wall, step, mode)?;
        if target == wall {
            values.push(Some(source));
            continue;
        }
        let value = if let Some(offset) = fixed {
            target - i128::from(offset) * 1000
        } else {
            rounded(
                target,
                source,
                step,
                mode,
                zone.ok_or_else(|| crate::error_context::runtime("missing rounding region"))?,
            )
            .map_err(|e| crate::error_context::location(py, e, entry, &format!("result[{i}]")))?
        };
        changed |= source != value;
        values.push(Some(value));
    }
    Ok((pack(py, &values, unit, true, entry)?, changed))
}

#[derive(Clone, Copy)]
struct SnapChoice {
    start: i128,
    later: bool,
    values: [Option<i128>; 2],
}

/// Keep only two resolved boundaries within this operation's exact immutable zone.
struct SnapCache {
    enabled: bool,
    choices: [Option<SnapChoice>; 2],
    next: usize,
}
impl SnapCache {
    fn get(
        &mut self,
        spec: Snap,
        start: i128,
        later: bool,
        zone: &Bound<'_, PyAny>,
        unit: Unit,
    ) -> PyResult<[Option<i128>; 2]> {
        if self.enabled {
            for previous in self.choices.iter().flatten() {
                if previous.start == start && previous.later == later {
                    return Ok(previous.values);
                }
            }
        }
        let values = spec.candidates(start, later, zone, unit)?;
        if self.enabled {
            self.choices[self.next] = Some(SnapChoice {
                start,
                later,
                values,
            });
            self.next ^= 1;
        }
        Ok(values)
    }
}

impl Snap {
    fn candidates(
        self,
        mut start: i128,
        later: bool,
        zone: &Bound<'_, PyAny>,
        unit: Unit,
    ) -> PyResult<[Option<i128>; 2]> {
        for _ in 0..4 {
            let choices = edge_candidates(start, self.end(start)?, false, zone, unit)?;
            if choices.iter().any(Option::is_some) {
                return Ok(choices);
            }
            if self.months != 0 {
                start = self.shift(start, if later { 1 } else { -1 })?;
                continue;
            }
            let Candidates::Gap { before, after } = super::zones::candidates(start, zone)? else {
                return Err(crate::error_context::value_error(
                    "no representable adjacent Snap period at this unit",
                ));
            };
            let (last, first) = crate::pydt::gap_edges(
                i64::try_from(start.div_euclid(1000))
                    .map_err(|_| crate::error_context::overflow("regional Snap overflow"))?,
                after - before,
                zone,
            )?;
            let edge = if later {
                i128::from(first) * 1000
            } else {
                (i128::from(last) + 1) * 1000 - 1
            };
            let next = start + (edge - start).div_euclid(self.step) * self.step;
            start = if next == start {
                self.shift(start, if later { 1 } else { -1 })?
            } else {
                next
            };
        }
        Err(crate::error_context::value_error(
            "timezone cannot confirm adjacent existing Snap periods",
        ))
    }
}

#[pyfunction]
fn _pddt_snap<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    token: &str,
    entry: &str,
) -> PyResult<Output<'py>> {
    if !data.len().is_multiple_of(8) {
        return Err(crate::error_context::runtime("invalid date source buffer"));
    }
    // Validate even empty/all-missing data; the actual alignment uses each row.
    let period = Period::parse(token, true)?;
    let unit = Unit::parse(unit)?;
    if matches!(period, Period::Tick(1))
        || matches!(period, Period::Tick(1000)) && unit != Unit::Nanosecond
    {
        return Ok((PyBytes::new(py, data), false));
    }
    let zone = zone.filter(|v| !v.is_none());
    let fixed = super::common::fixed_offset(
        py,
        &zone.map_or(Zone::Naive, |z| Zone::Object(z.clone().unbind())),
    )?;
    let mut cache = SnapCache {
        enabled: fixed.is_none() && zone.is_some_and(crate::pydt::is_exact_zoneinfo),
        choices: [None; 2],
        next: 0,
    };
    let mut values = Vec::with_capacity(data.len() / 8);
    let mut changed = false;
    for (i, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        let raw: [u8; 8] = *bytes;
        let ticks = i64::from_ne_bytes(raw);
        if ticks == i64::MIN {
            values.push(None);
            continue;
        }
        let source = i128::from(ticks) * unit.nanos();
        let wall = if let Some(offset) = fixed {
            source + i128::from(offset) * 1000
        } else {
            super::zones::utc_wall(
                source,
                zone.ok_or_else(|| crate::error_context::runtime("missing Snap region"))?,
                None,
            )?
        };
        let (spec, lower) = Snap::prepare(period, wall)?;
        let upper = spec.shift(lower, 1)?;
        let value = (|| -> PyResult<i128> {
            if let Some(offset) = fixed {
                let offset = i128::from(offset) * 1000;
                let first = align(lower - offset, unit, false)?;
                if first == source {
                    return Ok(source);
                }
                let second = align(upper - offset, unit, false)?;
                return Ok(if (source - first).abs() < (second - source).abs() {
                    first
                } else {
                    second
                });
            }
            let zone = zone.ok_or_else(|| crate::error_context::runtime("missing Snap region"))?;
            let mut starts = vec![lower, upper];
            let mut best = None;
            let mut expanded = false;
            let mut next = 0;
            while next < starts.len() {
                let start = starts[next];
                next += 1;
                let choices = cache.get(spec, start, start >= wall, zone, unit)?;
                for value in choices.into_iter().flatten() {
                    if value == source {
                        return Ok(source);
                    }
                    if best.is_none_or(|previous: i128| {
                        (value - source).abs() < (previous - source).abs()
                            || ((value - source).abs() == (previous - source).abs()
                                && value > previous)
                    }) {
                        best = Some(value);
                    }
                }
                if !expanded
                    && spec.months == 0
                    && spec.step < NS_DAY
                    && let Candidates::Repeated(a, b) = super::zones::candidates(start, zone)?
                {
                    expanded = true;
                    for offset in [start - a, start - b] {
                        let projected = source + offset;
                        let aligned = spec.period.bounds(projected)?.0;
                        for candidate in
                            [spec.shift(aligned, -1)?, aligned, spec.shift(aligned, 1)?]
                        {
                            if !starts.contains(&candidate) {
                                starts.push(candidate);
                            }
                        }
                    }
                }
            }
            best.ok_or_else(|| crate::error_context::value_error("no valid adjacent Snap start"))
        })()
        .map_err(|e| crate::error_context::location(py, e, entry, &format!("result[{i}]")))?;
        changed |= value != source;
        values.push(Some(value));
    }
    Ok((pack(py, &values, unit, true, entry)?, changed))
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_period, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_snap, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_round, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_fsp, module)?)
}
