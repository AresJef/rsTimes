//! Integer calendar frequencies, independent of pandas versions and date objects.
const NS_DAY: i128 = 86_400_000_000_000;
const OVERFLOW: &str = "date_range calendar arithmetic overflow";

/// Shared endpoint vocabulary; callers retain their own error boundary.
pub(crate) fn inclusive(value: &str) -> Result<(bool, bool), &'static str> {
    match value {
        "both" => Ok((true, true)),
        "left" => Ok((true, false)),
        "right" => Ok((false, true)),
        "neither" => Ok((false, false)),
        _ => Err("inclusive must be 'both', 'left', 'right' or 'neither'"),
    }
}

#[derive(Clone)]
pub(crate) struct Business {
    pub mask: [bool; 7],
    pub holidays: Vec<i64>,
}
impl Business {
    pub fn weekday(day: i128) -> usize {
        ((day.rem_euclid(7) + 3) % 7) as usize
    }
    pub fn valid(&self, day: i64) -> bool {
        self.mask[Self::weekday(i128::from(day))] && self.holidays.binary_search(&day).is_err()
    }
    pub fn roll(&self, mut day: i64, direction: i64) -> Result<i64, &'static str> {
        while !self.valid(day) {
            day = day.checked_add(direction).ok_or(OVERFLOW)?;
        }
        Ok(day)
    }
    fn before(&self, day: i128) -> i128 {
        let full = day.div_euclid(7);
        let rest = day.rem_euclid(7) as usize;
        let count = self.mask.iter().filter(|v| **v).count() as i128;
        let weekdays = (0..rest).filter(|i| self.mask[(i + 3) % 7]).count() as i128;
        let holidays = if day > i128::from(i64::MAX) {
            self.holidays.len()
        } else if day <= i128::from(i64::MIN) {
            0
        } else {
            self.holidays.partition_point(|v| i128::from(*v) < day)
        };
        full * count + weekdays - holidays as i128
    }
    pub fn shift(&self, mut day: i64, mut count: i64) -> Result<i64, &'static str> {
        if !self.valid(day) {
            let direction = if count < 0 { -1 } else { 1 };
            day = self.roll(day, direction)?;
            if count != 0 {
                count = count.checked_sub(direction).ok_or(OVERFLOW)?;
            }
        }
        if count == 0 {
            return Ok(day);
        }
        let target = self.before(i128::from(day)) + i128::from(count);
        let span = i128::from(count).abs() * 7 + self.holidays.len() as i128 * 7 + 14;
        let mut low = i128::from(day) - span;
        let mut high = i128::from(day) + span;
        while low < high {
            let middle = low + (high - low) / 2;
            if self.before(middle + 1) > target {
                high = middle;
            } else {
                low = middle + 1;
            }
        }
        i64::try_from(low).map_err(|_| OVERFLOW)
    }
}

#[derive(Clone)]
pub(crate) enum Kind {
    Fixed(i128),
    Days,
    Week(Option<i64>),
    Business {
        custom: bool,
    },
    Boundary {
        stride: i64,
        anchor: i64,
        start: bool,
        business: bool,
    },
    CustomBusinessMonth {
        start: bool,
    },
    Semi {
        start: bool,
        day: i64,
    },
    WeekOfMonth {
        weekday: i64,
        week: i64,
        last: bool,
    },
}

#[derive(Clone)]
pub(crate) struct Frequency {
    pub kind: Kind,
    pub n: i64,
    pub normalize: bool,
    pub offset: i128,
    pub business: Business,
}

fn split(value: i128) -> Result<(i64, i128), &'static str> {
    Ok((
        i64::try_from(value.div_euclid(NS_DAY)).map_err(|_| OVERFLOW)?,
        value.rem_euclid(NS_DAY),
    ))
}
fn fields(day: i64) -> Result<[i64; 3], &'static str> {
    crate::calendar::from_ordinal(day.checked_add(719_163).ok_or(OVERFLOW)?)
}
fn month_day(month: i64, day: i64) -> Result<i64, &'static str> {
    crate::calendar::checked_ordinal(month.div_euclid(12), month.rem_euclid(12) + 1, day)?
        .checked_sub(719_163)
        .ok_or(OVERFLOW)
}
fn month_index(year: i64, month: i64) -> Result<i64, &'static str> {
    year.checked_mul(12)
        .and_then(|v| v.checked_add(month - 1))
        .ok_or(OVERFLOW)
}

impl Frequency {
    fn point(&self, month: i64) -> Result<i64, &'static str> {
        let year = month.div_euclid(12);
        let m = month.rem_euclid(12) + 1;
        let length = crate::calendar::days_in_month(year, m);
        match self.kind {
            Kind::Boundary {
                start, business, ..
            } => {
                let day = month_day(month, if start { 1 } else { length })?;
                if business {
                    self.business.roll(day, if start { 1 } else { -1 })
                } else {
                    Ok(day)
                }
            }
            Kind::WeekOfMonth {
                weekday,
                week,
                last,
            } => {
                if last {
                    let end = month_day(month, length)?;
                    end.checked_sub(
                        (Business::weekday(i128::from(end)) as i64 - weekday).rem_euclid(7),
                    )
                    .ok_or(OVERFLOW)
                } else {
                    let first = month_day(month, 1)?;
                    first
                        .checked_add(
                            (weekday - Business::weekday(i128::from(first)) as i64).rem_euclid(7)
                                + week * 7,
                        )
                        .ok_or(OVERFLOW)
                }
            }
            _ => Err("frequency does not have a monthly anchor"),
        }
    }
    fn month_stride(&self) -> i64 {
        if let Kind::Boundary { stride, .. } = self.kind {
            stride
        } else {
            1
        }
    }
    fn eligible_month(&self, month: i64, direction: i64) -> Result<i64, &'static str> {
        if let Kind::Boundary { stride, anchor, .. } = self.kind {
            let rest = (month - (anchor - 1)).rem_euclid(stride);
            month
                .checked_add(if rest == 0 {
                    0
                } else if direction > 0 {
                    stride - rest
                } else {
                    -rest
                })
                .ok_or(OVERFLOW)
        } else {
            Ok(month)
        }
    }
    /// Roll by the generation direction, independent of the multiplier magnitude.
    pub fn roll(&self, value: i128, direction: i64) -> Result<i128, &'static str> {
        let (day, clock) = split(value)?;
        if let Kind::CustomBusinessMonth { .. } = self.kind {
            // Backward rolling normalizes before the membership check and
            // step. Forward rolling keeps the supplied clock for the step.
            let (value, clock) = if self.normalize && direction < 0 {
                (i128::from(day) * NS_DAY, 0)
            } else {
                (value, clock)
            };
            if (!self.normalize || clock == 0) && self.apply(self.apply(value, 1)?, -1)? == value {
                return Ok(value);
            }
            return self.apply_calendar(value, direction);
        }
        let had_clock = clock != 0;
        // Forward workday rolling applies the offset to the original clock
        // before normalizing to midnight.
        let clock =
            if self.normalize && !(direction > 0 && matches!(self.kind, Kind::Business { .. })) {
                0
            } else {
                clock
            };
        let mut rolled = match self.kind {
            Kind::Fixed(_) | Kind::Days | Kind::Week(None) => day,
            Kind::Week(Some(weekday)) => {
                let wd = Business::weekday(i128::from(day)) as i64;
                day.checked_add(if direction > 0 {
                    (weekday - wd).rem_euclid(7)
                } else {
                    -(wd - weekday).rem_euclid(7)
                })
                .ok_or(OVERFLOW)?
            }
            Kind::Business { .. } => self.business.roll(day, direction)?,
            Kind::Semi { start, day: middle } => {
                let [y, m, d] = fields(day)?;
                let mut month = month_index(y, m)?;
                let last = crate::calendar::days_in_month(y, m);
                let candidates = if start { [1, middle] } else { [middle, last] };
                let target = if direction > 0 {
                    if d <= candidates[0] {
                        candidates[0]
                    } else if d <= candidates[1] {
                        candidates[1]
                    } else {
                        month = month.checked_add(1).ok_or(OVERFLOW)?;
                        if start { 1 } else { middle }
                    }
                } else if d >= candidates[1] {
                    candidates[1]
                } else if d >= candidates[0] {
                    candidates[0]
                } else {
                    month = month.checked_sub(1).ok_or(OVERFLOW)?;
                    if start {
                        middle
                    } else {
                        crate::calendar::days_in_month(
                            month.div_euclid(12),
                            month.rem_euclid(12) + 1,
                        )
                    }
                };
                month_day(month, target)?
            }
            _ => {
                let [y, m, _] = fields(day)?;
                let mut month = self.eligible_month(month_index(y, m)?, direction)?;
                let mut candidate = self.point(month)?;
                if (direction > 0 && candidate < day) || (direction < 0 && candidate > day) {
                    month = month
                        .checked_add(direction * self.month_stride())
                        .ok_or(OVERFLOW)?;
                    candidate = self.point(month)?;
                }
                candidate
            }
        };
        if self.normalize && had_clock && direction > 0 && rolled == day {
            rolled = self.advance_day(day, 1)?;
        }
        let result = i128::from(rolled)
            .checked_mul(NS_DAY)
            .and_then(|v| v.checked_add(clock))
            .ok_or(OVERFLOW)?;
        let result = if rolled != day {
            self.add_offset(result, clock)?
        } else {
            result
        };
        Ok(if self.normalize {
            result.div_euclid(NS_DAY) * NS_DAY
        } else {
            result
        })
    }
    fn advance_day(&self, day: i64, n: i64) -> Result<i64, &'static str> {
        let target = match self.kind {
            Kind::Days => day.checked_add(n).ok_or(OVERFLOW)?,
            Kind::Week(_) => day
                .checked_add(n.checked_mul(7).ok_or(OVERFLOW)?)
                .ok_or(OVERFLOW)?,
            Kind::Business { .. } => self.business.shift(day, n)?,
            Kind::CustomBusinessMonth { start } => self.advance_custom_month(day, n, start)?,
            Kind::Semi { start, day: middle } => {
                let [y, m, d] = fields(day)?;
                let month = month_index(y, m)?;
                let slot = if start {
                    i64::from(d >= middle)
                } else {
                    i64::from(d > middle)
                };
                let position = month
                    .checked_mul(2)
                    .and_then(|v| v.checked_add(slot))
                    .and_then(|v| v.checked_add(n))
                    .ok_or(OVERFLOW)?;
                let target = position.div_euclid(2);
                let slot = position.rem_euclid(2);
                let day = if start {
                    if slot == 0 { 1 } else { middle }
                } else if slot == 0 {
                    middle
                } else {
                    crate::calendar::days_in_month(target.div_euclid(12), target.rem_euclid(12) + 1)
                };
                month_day(target, day)?
            }
            _ => {
                let [y, m, _] = fields(day)?;
                let month = month_index(y, m)?
                    .checked_add(n.checked_mul(self.month_stride()).ok_or(OVERFLOW)?)
                    .ok_or(OVERFLOW)?;
                self.point(month)?
            }
        };
        Ok(target)
    }
    fn advance_custom_month(&self, day: i64, n: i64, start: bool) -> Result<i64, &'static str> {
        let [year, month, date] = fields(day)?;
        let current = month_index(year, month)?;
        let length = crate::calendar::days_in_month(year, month);
        let first = day.checked_sub(date - 1).ok_or(OVERFLOW)?;
        let edge = if start {
            first
        } else {
            day.checked_add(length - date).ok_or(OVERFLOW)?
        };
        let direction = if start { 1 } else { -1 };
        let anchor = self.business.roll(edge, direction)?;
        let anchor_date = match anchor.checked_sub(first) {
            Some(index) if (0..length).contains(&index) => index + 1,
            // A sparse work calendar can put the anchor in another month.
            // The frequency compares day-of-month even in that case.
            _ => fields(anchor)?[2],
        };
        let shift = if n > 0 && date < anchor_date {
            n - 1
        } else if n <= 0 && date > anchor_date {
            n + 1
        } else {
            n
        };
        if shift == 0 {
            return Ok(anchor);
        }
        let target = current.checked_add(shift).ok_or(OVERFLOW)?;
        let date = if start {
            1
        } else {
            crate::calendar::days_in_month(target.div_euclid(12), target.rem_euclid(12) + 1)
        };
        self.business.roll(month_day(target, date)?, direction)
    }
    /// Advance one whole frequency, keeping the full native clock and ns tail.
    pub fn apply(&self, value: i128, multiplier: i64) -> Result<i128, &'static str> {
        let n = self.n.checked_mul(multiplier).ok_or(OVERFLOW)?;
        if let Kind::Fixed(step) = self.kind {
            return step
                .checked_mul(i128::from(multiplier))
                .and_then(|v| value.checked_add(v))
                .ok_or(OVERFLOW);
        }
        if matches!(self.kind, Kind::Days) && !self.normalize && self.offset == 0 {
            // Moving a whole local day keeps the clock. Check the same
            // source and result day bounds as split and advance_day.
            const FIRST: i128 = (i64::MIN as i128) * NS_DAY;
            const LIMIT: i128 = (i64::MAX as i128 + 1) * NS_DAY;
            if !(FIRST..LIMIT).contains(&value) {
                return Err(OVERFLOW);
            }
            // A sum of two signed-64-bit day coordinates fits i128.
            let shifted = value + i128::from(n) * NS_DAY;
            return (FIRST..LIMIT)
                .contains(&shifted)
                .then_some(shifted)
                .ok_or(OVERFLOW);
        }
        self.apply_calendar(value, n)
    }
    fn apply_calendar(&self, value: i128, n: i64) -> Result<i128, &'static str> {
        let (day, clock) = split(value)?;
        let target = self.advance_day(day, n)?;
        let result = i128::from(target) * NS_DAY + clock;
        let shifted = self.add_offset(result, clock)?;
        Ok(if self.normalize {
            shifted.div_euclid(NS_DAY) * NS_DAY
        } else {
            shifted
        })
    }

    #[inline]
    fn add_offset(&self, value: i128, clock: i128) -> Result<i128, &'static str> {
        let offset = self.offset;
        if offset == 0 {
            return Ok(value);
        }
        let submicro = offset.rem_euclid(1_000);
        if submicro != 0 && matches!(self.kind, Kind::Business { custom: true }) {
            // CustomBusinessDay applies its offset to a microsecond wall clock.
            let effective = offset.checked_sub(submicro).ok_or(OVERFLOW)?;
            return value.checked_add(effective).ok_or(OVERFLOW);
        }
        let shifted = value.checked_add(offset).ok_or(OVERFLOW)?;
        if submicro != 0
            && !self.normalize
            && matches!(
                self.kind,
                Kind::Business { custom: false } | Kind::CustomBusinessMonth { .. }
            )
        {
            // The pinned timestamp offset restores the source tail if the
            // applied offset changed it. A whole microsecond never changes it.
            return shifted.checked_add(clock % 1_000).ok_or(OVERFLOW);
        }
        Ok(shifted)
    }
}

use crate::epoch::Unit;
use pyo3::prelude::*;
#[pyclass(frozen, name = "_RangeFrequency")]
pub(crate) struct Plan {
    pub(crate) frequency: Frequency,
    pub(crate) precision: Unit,
}
#[pymethods]
impl Plan {
    #[getter]
    fn rounding_step(&self) -> Option<i128> {
        match self.frequency.kind {
            Kind::Fixed(value) => Some(value),
            Kind::Days => Some(i128::from(self.frequency.n) * 86_400_000_000_000),
            _ => None,
        }
    }
    #[getter]
    pub(crate) fn tick(&self) -> Option<i128> {
        if let Kind::Fixed(value) = self.frequency.kind {
            Some(value)
        } else {
            None
        }
    }
}

impl Plan {
    pub(crate) fn required_unit(&self) -> Unit {
        let fraction = match self.frequency.kind {
            Kind::Fixed(value) => value,
            _ => self.frequency.offset,
        };
        self.precision.max(crate::precision::quantum_unit(fraction))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn whole_local_days_preserve_clock_and_calendar_capacity() {
        let frequency = Frequency {
            kind: Kind::Days,
            n: 1,
            normalize: false,
            offset: 0,
            business: Business {
                mask: [true; 7],
                holidays: Vec::new(),
            },
        };
        let first = i128::from(i64::MIN) * NS_DAY;
        let last = i128::from(i64::MAX) * NS_DAY + NS_DAY - 1;
        assert_eq!(frequency.apply(-1, 1), Ok(NS_DAY - 1));
        assert_eq!(frequency.apply(NS_DAY - 1, -1), Ok(-1));
        assert_eq!(frequency.apply(last - NS_DAY, 1), Ok(last));
        assert_eq!(frequency.apply(last, 1), Err(OVERFLOW));
        assert_eq!(frequency.apply(first, -1), Err(OVERFLOW));
        assert_eq!(frequency.apply(first - 1, 1), Err(OVERFLOW));
        assert_eq!(frequency.apply(last + 1, -1), Err(OVERFLOW));
    }

    #[test]
    fn sparse_business_month_anchors_match_independent_day_coordinates() {
        // January 2024 has no working day in this Monday-only calendar.
        // Each row records the date returned for Jan 1..31 in pandas 3.0.6
        // before adding -1 µs, for successive multipliers -2 through 2.
        let anchors = [
            19_667, 19_688, 19_695, 19_716, 19_758, 19_779, 19_786, 19_807,
        ];
        let begin = [
            b"AAAAACCCCCCCCCCCCCCCCCCCCCCCCCC",
            b"CCCCCEEEEEEEEEEEEEEEEEEEEEEEEEE",
            b"EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE",
            b"EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE",
            b"EEEEGGGGGGGGGGGGGGGGGGGGGGGGGGG",
        ];
        let end = [
            b"BBBBBBBBBBBBBBBBBBBBBBBBBDDDDDD",
            b"DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
            b"DDDDDDDDDDDDDDDDDDDDDDDDDFFFFFF",
            b"DDDDDDDDDDDDDDDDDDDDDDDDFFFFFFF",
            b"FFFFFFFFFFFFFFFFFFFFFFFFHHHHHHH",
        ];
        for (start, table) in [(true, begin), (false, end)] {
            let frequency = Frequency {
                kind: Kind::CustomBusinessMonth { start },
                n: 1,
                normalize: false,
                offset: -1_000,
                business: Business {
                    mask: [true, false, false, false, false, false, false],
                    holidays: (0..5).map(|week| 19_723 + 7 * week).collect(),
                },
            };
            for (multiplier, choices) in (-2_i64..=2).zip(table) {
                for (i, &choice) in choices.iter().enumerate() {
                    let source = (19_723 + i as i128) * NS_DAY;
                    let expected = anchors[usize::from(choice - b'A')] * NS_DAY - 1_000;
                    assert_eq!(
                        frequency.apply(source, multiplier),
                        Ok(expected),
                        "start={start}, Jan {}, multiplier={multiplier}",
                        i + 1,
                    );
                }
            }
        }
    }
}
