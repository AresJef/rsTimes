//! Native calendar bounds, shared by boundary transforms and direct predicates.
use super::common::{NS_DAY, pack};
use super::zones::Candidates;
use crate::epoch::{Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

#[derive(Clone, Copy)]
pub(super) enum Period {
    Year,
    Quarter,
    Month,
    Week,
    Day,
    Tick(i128),
    NamedMonth(i64),
    NamedWeekday(i64),
}
impl Period {
    pub fn parse(text: &str, clock: bool) -> PyResult<Self> {
        let value = match text {
            "Y" => Self::Year,
            "Q" => Self::Quarter,
            "M" => Self::Month,
            "W" => Self::Week,
            "D" => Self::Day,
            "h" => Self::Tick(3_600_000_000_000),
            "m" | "min" => Self::Tick(60_000_000_000),
            "s" => Self::Tick(1_000_000_000),
            "ms" => Self::Tick(1_000_000),
            "us" => Self::Tick(1000),
            "ns" => Self::Tick(1),
            _ => {
                let (month, weekday) = crate::pydt::boundary_names(text);
                if month > 0 {
                    Self::NamedMonth(i64::from(month))
                } else if clock && weekday >= 0 {
                    Self::NamedWeekday(i64::from(weekday))
                } else {
                    return Err(crate::error_context::value_error(
                        "unknown or empty period or stored name; use Y, Q, M, W and supported clock units or stored names",
                    ));
                }
            }
        };
        if !clock && matches!(value, Self::Day | Self::Tick(_) | Self::NamedWeekday(_)) {
            return Err(crate::error_context::value_error(
                "first/last require Y, Q, M, W or a stored month name",
            ));
        }
        Ok(value)
    }
    pub fn clock(self) -> bool {
        matches!(self, Self::Tick(_))
    }
    pub fn bounds(self, wall: i128) -> PyResult<(i128, i128)> {
        if let Self::Tick(step) = self {
            let lower = wall.div_euclid(step) * step;
            return Ok((
                lower,
                lower
                    .checked_add(step)
                    .ok_or_else(|| crate::error_context::overflow("period boundary overflow"))?,
            ));
        }
        let day = wall.div_euclid(NS_DAY);
        if matches!(self, Self::Day) {
            return Ok((day * NS_DAY, (day + 1) * NS_DAY));
        }
        if matches!(self, Self::Week | Self::NamedWeekday(_)) {
            let weekday = (day + 3).rem_euclid(7);
            let lower = day - weekday;
            return Ok(match self {
                Self::NamedWeekday(value) => (
                    (lower + i128::from(value)) * NS_DAY,
                    (lower + i128::from(value) + 1) * NS_DAY,
                ),
                _ => (lower * NS_DAY, (lower + 7) * NS_DAY),
            });
        }
        let f = super::operations::fields(wall)?;
        let (month, width) = match self {
            Self::Year => (1, 12),
            Self::Quarter => ((f[1] - 1) / 3 * 3 + 1, 3),
            Self::Month => (f[1], 1),
            Self::NamedMonth(month) => (month, 1),
            _ => return Err(crate::error_context::runtime("invalid calendar period")),
        };
        let first = crate::calendar::checked_ordinal(f[0], month, 1)
            .map_err(crate::error_context::overflow)?;
        let next = crate::calendar::move_date([f[0], month, 1], width, 0, None, None)
            .map_err(crate::error_context::overflow)?;
        let last = crate::calendar::checked_ordinal(next[0], next[1], next[2])
            .map_err(crate::error_context::overflow)?;
        Ok((
            (i128::from(first) - 719_163) * NS_DAY,
            (i128::from(last) - 719_163) * NS_DAY,
        ))
    }
}

fn align(value: i128, unit: Unit, end: bool) -> PyResult<i128> {
    let q = value.div_euclid(unit.nanos());
    (q + i128::from(!end && value.rem_euclid(unit.nanos()) != 0))
        .checked_mul(unit.nanos())
        .ok_or_else(|| crate::error_context::overflow("period output overflow"))
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
    if data.len() % 8 != 0 {
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
    for (i, bytes) in data.chunks_exact(8).enumerate() {
        let raw: [u8; 8] = bytes
            .try_into()
            .map_err(|_| crate::error_context::runtime("invalid date tick"))?;
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
    if data.len() % 8 != 0 {
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
    for (i, bytes) in data.chunks_exact(8).enumerate() {
        let raw: [u8; 8] = bytes
            .try_into()
            .map_err(|_| crate::error_context::runtime("invalid date tick"))?;
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
    (mode != 1 || value >= source) && (mode != 2 || value <= source)
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
        if let Some(value) = select(super::zones::candidates(wall, zone)?) {
            if best.is_none_or(|previous: i128| {
                (value - source).abs() < (previous - source).abs()
                    || ((value - source).abs() == (previous - source).abs() && value > previous)
            }) {
                best = Some(value);
            }
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
    if data.len() % 8 != 0 || step <= 0 || mode > 2 {
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
    for (i, bytes) in data.chunks_exact(8).enumerate() {
        let raw: [u8; 8] = bytes
            .try_into()
            .map_err(|_| crate::error_context::runtime("invalid date tick"))?;
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
        let q = wall.div_euclid(step);
        let r = wall.rem_euclid(step);
        if r == 0 {
            values.push(Some(source));
            continue;
        }
        let up = match mode {
            0 => r > step - r || (r == step - r && q.rem_euclid(2) != 0),
            1 => true,
            _ => false,
        };
        let target = (q + i128::from(up))
            .checked_mul(step)
            .ok_or_else(|| crate::error_context::overflow("rounded date overflow"))?;
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
struct Snap {
    period: Period,
    months: i64,
    step: i128,
    width_months: i64,
    width: i128,
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
    fn prepare(period: Period, wall: i128) -> PyResult<(Self, i128)> {
        let (months, step, width_months, width) = match period {
            Period::Year => (12, 0, 12, 0),
            Period::Quarter => (3, 0, 3, 0),
            Period::Month => (1, 0, 1, 0),
            Period::NamedMonth(_) => (12, 0, 1, 0),
            Period::Week => (0, 7 * NS_DAY, 0, 7 * NS_DAY),
            Period::NamedWeekday(_) => (0, 7 * NS_DAY, 0, NS_DAY),
            Period::Day => (0, NS_DAY, 0, NS_DAY),
            Period::Tick(step) => (0, step, 0, step),
        };
        let spec = Self {
            period,
            months,
            step,
            width_months,
            width,
        };
        let mut lower = period.bounds(wall)?.0;
        if lower > wall {
            lower = spec.shift(lower, -1)?;
        }
        Ok((spec, lower))
    }
    fn shift(self, start: i128, direction: i64) -> PyResult<i128> {
        if self.months != 0 {
            self.month_boundary(start, self.months * direction)
        } else {
            start
                .checked_add(self.step * i128::from(direction))
                .ok_or_else(|| crate::error_context::overflow("Snap period overflow"))
        }
    }
    fn month_boundary(self, start: i128, months: i64) -> PyResult<i128> {
        let f = super::operations::fields(start)?;
        let date = crate::calendar::move_date([f[0], f[1], 1], i128::from(months), 0, None, None)
            .map_err(crate::error_context::overflow)?;
        super::operations::nanos([date[0], date[1], date[2], 0, 0, 0, 0, 0])
    }
    fn end(self, start: i128) -> PyResult<i128> {
        if self.width_months != 0 {
            self.month_boundary(start, self.width_months)
        } else {
            start
                .checked_add(self.width)
                .ok_or_else(|| crate::error_context::overflow("Snap period overflow"))
        }
    }
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
    if data.len() % 8 != 0 {
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
    for (i, bytes) in data.chunks_exact(8).enumerate() {
        let raw: [u8; 8] = bytes
            .try_into()
            .map_err(|_| crate::error_context::runtime("invalid date tick"))?;
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
                if !expanded && spec.months == 0 && spec.step < NS_DAY {
                    if let Candidates::Repeated(a, b) = super::zones::candidates(start, zone)? {
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
