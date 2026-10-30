//! Integer calendar frequencies, independent of pandas versions and date objects.
const NS_DAY: i128 = 86_400_000_000_000;
const OVERFLOW: &str = "date_range calendar arithmetic overflow";

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
    Business,
    Boundary {
        stride: i64,
        anchor: i64,
        start: bool,
        business: bool,
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
        let had_clock = clock != 0;
        let clock = if self.normalize { 0 } else { clock };
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
            Kind::Business => self.business.roll(day, direction)?,
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
            result.checked_add(self.offset).ok_or(OVERFLOW)?
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
            Kind::Business => self.business.shift(day, n)?,
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
    /// Advance one whole frequency, keeping the full native clock and ns tail.
    pub fn apply(&self, value: i128, multiplier: i64) -> Result<i128, &'static str> {
        let n = self.n.checked_mul(multiplier).ok_or(OVERFLOW)?;
        if let Kind::Fixed(step) = self.kind {
            return step
                .checked_mul(i128::from(multiplier))
                .and_then(|v| value.checked_add(v))
                .ok_or(OVERFLOW);
        }
        let (day, clock) = split(value)?;
        let target = self.advance_day(day, n)?;
        let result = i128::from(target) * NS_DAY + clock;
        let shifted = result.checked_add(self.offset).ok_or(OVERFLOW)?;
        Ok(if self.normalize {
            shifted.div_euclid(NS_DAY) * NS_DAY
        } else {
            shifted
        })
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
