//! Native parser state and checked year/month/day labels.
//!
//! Parsing and rule queries own only Rust values. Python conversion is confined
//! to configuration and result boundaries.

use crate::calendar;

/// A token namespace queried at its original position in the scan.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Rule {
    Jump,
    Pertain,
    Utc,
    Tz,
    Month,
    Weekday,
    Hms,
    HmsContains,
    Ampm,
}

/// Failure produced without allocating a Python exception in the core.
#[derive(Debug)]
pub(crate) enum ParseError {
    Value(String),
    Overflow(String),
    Assertion(String),
    UnknownRegion(Vec<u32>),
    ConflictingRegions(String, String),
}

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Value(message) | Self::Overflow(message) | Self::Assertion(message) => {
                f.write_str(message)
            }
            Self::UnknownRegion(key) => {
                f.write_str("time zone '")?;
                for &code in key.iter().take(120) {
                    if let Some(value) = char::from_u32(code) {
                        write!(f, "{}", value.escape_debug())?;
                    } else {
                        write!(f, "\\u{code:04x}")?;
                    }
                }
                f.write_str("' is not registered; register it with cfg.add_tzone()")
            }
            Self::ConflictingRegions(key, previous) => {
                write!(f, "conflicting time zones: {key:?} and {previous:?}")
            }
        }
    }
}

/// Result shared by the native grammar and its configuration adapter.
pub(crate) type ParseResult<T> = Result<T, ParseError>;

/// Query configuration without exposing a Python container to the grammar.
///
/// Set-like queries return zero or one. Missing mapped values return -1,
/// except a missing timezone returns -100_000.
pub(crate) trait RuleLookup {
    fn query(&mut self, rule: Rule, token: &[u32]) -> ParseResult<i32>;
}

/// Fraction storage is absent from existing microsecond parser policies.
pub(crate) trait Precision: Default + std::fmt::Debug {
    const NANO: bool;
    fn tail(&self) -> i32 {
        0
    }
    fn has_nanos(&self) -> bool {
        false
    }
    fn set(&mut self, _tail: i32, _nanos: bool) {}
}
impl Precision for () {
    const NANO: bool = false;
}

/// Only epoch/batch parsing retains the final three digits and source precision.
#[derive(Debug, Default)]
pub(crate) struct NanoPrecision {
    tail: i32,
    nanos: bool,
}
impl Precision for NanoPrecision {
    const NANO: bool = true;
    fn tail(&self) -> i32 {
        self.tail
    }
    fn has_nanos(&self) -> bool {
        self.nanos
    }
    fn set(&mut self, tail: i32, nanos: bool) {
        self.tail = tail;
        self.nanos |= nanos;
    }
}

/// Preserve the same grammar and strict tracking with nanosecond precision.
#[derive(Debug, Default)]
pub(crate) struct Nano<P: Policy>(P);
impl<P: Policy> Policy for Nano<P> {
    const STRICT: bool = P::STRICT;
    type Fraction = NanoPrecision;
    fn tracking(&self) -> Option<&StrictTracking> {
        self.0.tracking()
    }
    fn tracking_mut(&mut self) -> Option<&mut StrictTracking> {
        self.0.tracking_mut()
    }
}

/// Parsing policies select native state without a runtime trait object.
pub(crate) trait Policy: Default + std::fmt::Debug {
    type Fraction: Precision;
    const ISO_ONLY: bool = false;
    /// Whether explicit fields and conflicts require validation.
    const STRICT: bool;
    /// Strict state is absent from the ordinary policy's type and storage.
    fn tracking(&self) -> Option<&StrictTracking> {
        None
    }
    /// Borrow strict state without a heap allocation or a dynamic dispatcher.
    fn tracking_mut(&mut self) -> Option<&mut StrictTracking> {
        None
    }
}

/// The ordinary path owns no conflict history and requires no destructor.
#[derive(Debug, Default)]
pub(crate) struct Lenient;
impl Policy for Lenient {
    type Fraction = ();
    const STRICT: bool = false;
}

/// Strict parsing keeps its bookkeeping inline; dates allocate only on repeats.
#[derive(Debug, Default)]
pub(crate) struct Strict(StrictTracking);
impl Policy for Strict {
    type Fraction = ();
    const STRICT: bool = true;
    fn tracking(&self) -> Option<&StrictTracking> {
        Some(&self.0)
    }
    fn tracking_mut(&mut self) -> Option<&mut StrictTracking> {
        Some(&mut self.0)
    }
}

/// Restrict a shared grammar policy to a fully recognized ISO prefix.
#[derive(Debug, Default)]
pub(crate) struct Iso<P: Policy>(P);
impl<P: Policy> Policy for Iso<P> {
    const STRICT: bool = P::STRICT;
    const ISO_ONLY: bool = true;
    type Fraction = P::Fraction;
    fn tracking(&self) -> Option<&StrictTracking> {
        self.0.tracking()
    }
    fn tracking_mut(&mut self) -> Option<&mut StrictTracking> {
        self.0.tracking_mut()
    }
}

/// Collected fields and the three ordered calendar values.
///
/// -1 means absent for calendar/clock fields. Timezone uses the reference's
/// separate sentinel so ordinary negative offsets remain representable.
#[derive(Debug)]
pub(crate) struct Fields<P: Policy> {
    policy: P,
    pub fraction: P::Fraction,
    hour_input: i32,
    pub ymd: [i32; 3],
    pub idx: i32,
    pub yidx: i32,
    pub midx: i32,
    pub didx: i32,
    pub resolved: bool,
    pub year: i32,
    pub month: i32,
    pub month_override: i32,
    pub day: i32,
    pub hour: i32,
    pub minute: i32,
    pub second: i32,
    pub microsecond: i32,
    pub weekday: i32,
    pub doy: i32,
    pub ampm: i32,
    pub tzoffset: i32,
    pub tzoffset_microsecond: i32,
    pub tzoffset_finalized: bool,
    pub century_specified: bool,
}

/// Strict conflict bookkeeping. Calendar snapshots own no recursive state.
#[derive(Debug)]
pub(crate) struct StrictTracking {
    clock_seen: u8,
    pending_hour: i32,
    pending_timezone: i64,
    dates: Vec<CalendarSnapshot>,
}

impl Default for StrictTracking {
    fn default() -> Self {
        Self {
            clock_seen: 0,
            pending_hour: -1,
            pending_timezone: i64::MIN,
            dates: Vec::new(),
        }
    }
}

/// An earlier explicit date, retained only to check strict duplicate fields.
#[derive(Debug)]
pub(crate) struct CalendarSnapshot {
    ymd: [i32; 3],
    idx: i32,
    yidx: i32,
    midx: i32,
    didx: i32,
    doy: i32,
    century_specified: bool,
    month_override: i32,
}

impl CalendarSnapshot {
    /// Recreate fields for the same policy before resolving the earlier date.
    pub fn into_fields<P: Policy>(self) -> Fields<P> {
        Fields {
            ymd: self.ymd,
            idx: self.idx,
            yidx: self.yidx,
            midx: self.midx,
            didx: self.didx,
            doy: self.doy,
            century_specified: self.century_specified,
            month_override: self.month_override,
            ..Fields::new()
        }
    }
}

impl<P: Policy> Default for Fields<P> {
    #[inline]
    fn default() -> Self {
        Self {
            policy: P::default(),
            fraction: P::Fraction::default(),
            hour_input: -1,
            ymd: [-1; 3],
            idx: -1,
            yidx: -1,
            midx: -1,
            didx: -1,
            resolved: false,
            year: -1,
            month: -1,
            month_override: -1,
            day: -1,
            hour: -1,
            minute: -1,
            second: -1,
            microsecond: -1,
            weekday: -1,
            doy: -1,
            ampm: -1,
            tzoffset: -100_000,
            tzoffset_microsecond: 0,
            tzoffset_finalized: false,
            century_specified: false,
        }
    }
}

impl<P: Policy> Fields<P> {
    #[inline]
    pub fn new() -> Self {
        Self::default()
    }

    #[inline]
    pub fn strict(&self) -> bool {
        P::STRICT
    }

    pub fn take_prior_dates(&mut self) -> Option<Vec<CalendarSnapshot>> {
        self.policy
            .tracking_mut()
            .filter(|state| !state.dates.is_empty())
            .map(|state| std::mem::take(&mut state.dates))
    }

    /// Check or clip an identified field, without losing its source value.
    #[inline(always)]
    pub fn bounded(&self, name: &str, value: i64, min: i32, max: i32) -> ParseResult<i32> {
        if (min > 0 && value < i64::from(min))
            || (self.strict() && !(i64::from(min)..=i64::from(max)).contains(&value))
        {
            return Err(Self::invalid_field(name, value, min, max));
        }
        Ok(value.clamp(i64::from(min), i64::from(max)) as i32)
    }

    /// Preserve a nonnegative written year until the chosen output checks its range.
    pub fn year_value(&self, value: i64) -> ParseResult<i32> {
        if value < 0 {
            return Err(Self::invalid_field("year", value, 0, i32::MAX));
        }
        i32::try_from(value)
            .map_err(|_| ParseError::Overflow("parsed year exceeds native integer range".into()))
    }

    /// Return the full signed offset, including its fractional second.
    #[inline]
    pub fn timezone_microseconds(&self) -> i64 {
        i64::from(self.tzoffset) * 1_000_000 + i64::from(self.tzoffset_microsecond)
    }

    /// Initialize the first ISO clock, validating its fields once.
    ///
    /// The prefix reader owns fresh Fields, so no prior clock or pending hour
    /// needs reconciliation. Keep the same explicit-field mask for later tokens.
    #[inline]
    pub fn initial_strict_clock(
        &mut self,
        hour: i32,
        minute: i32,
        second: i32,
        has_second: bool,
    ) -> ParseResult<()> {
        self.hour = self.bounded("hour", i64::from(hour), 0, 23)?;
        self.minute = self.bounded("minute", i64::from(minute), 0, 59)?;
        self.second = if has_second {
            self.bounded("second", i64::from(second), 0, 59)?
        } else {
            0
        };
        self.hour_input = self.hour;
        if let Some(state) = self.policy.tracking_mut() {
            state.clock_seen |= 3 | if has_second { 4 } else { 0 };
        }
        Ok(())
    }

    /// Set a clock field; an invalid explicit value is never silently ignored.
    #[inline(always)]
    pub fn set_clock(&mut self, flag: i32, value: i32) -> ParseResult<()> {
        if !self.strict() {
            match flag {
                0 => {
                    self.hour = value.clamp(0, 23);
                    self.ampm = -1;
                }
                1 => self.minute = value.clamp(0, 59),
                2 => self.second = value.clamp(0, 59),
                _ => self.microsecond = value.clamp(0, 999_999),
            }
            return Ok(());
        }
        let (name, max) = match flag {
            0 => ("hour", 23),
            1 => ("minute", 59),
            2 => ("second", 59),
            _ => ("microsecond", 999_999),
        };
        let value = self.bounded(name, i64::from(value), 0, max)?;
        let bit = 1 << flag;
        let previous = match flag {
            0 => self.hour,
            1 => self.minute,
            2 => self.second,
            _ => self.microsecond,
        };
        if flag == 0 {
            self.finish_hour()?;
            if self.clock_was_seen(flag) {
                if let Some(state) = self.policy.tracking_mut() {
                    state.pending_hour = previous;
                }
            }
            self.hour_input = value;
            self.ampm = -1;
        } else if self.clock_was_seen(flag) && previous != value {
            return Err(Self::conflict(name, previous, value));
        }
        if let Some(state) = self.policy.tracking_mut() {
            state.clock_seen |= bit;
        }
        match flag {
            0 => self.hour = value,
            1 => self.minute = value,
            2 => self.second = value,
            _ => self.microsecond = value,
        }
        Ok(())
    }

    #[cold]
    #[inline(never)]
    fn invalid_field(name: &str, value: i64, min: i32, max: i32) -> ParseError {
        ParseError::Value(format!(
            "{name}={value} is outside the allowed range {min} through {max}, inclusive"
        ))
    }

    #[cold]
    #[inline(never)]
    pub fn conflict(name: &str, previous: i32, value: i32) -> ParseError {
        ParseError::Value(format!(
            "Conflicting {name} values '{previous}' and '{value}'."
        ))
    }

    pub fn clock_was_seen(&self, flag: i32) -> bool {
        self.policy
            .tracking()
            .is_some_and(|state| state.clock_seen & (1 << flag) != 0)
    }

    /// An explicit second owns its entire fraction, including an absent zero.
    #[inline(always)]
    pub fn set_second(&mut self, second: i32, us: i32, tail: i32, nanos: bool) -> ParseResult<()> {
        if !self.strict() {
            self.second = second.clamp(0, 59);
            self.microsecond = us;
            self.fraction.set(tail, nanos);
            return Ok(());
        }
        self.set_clock(2, second)?;
        self.set_fraction(us, tail, nanos)
    }

    /// The ISO prefix is the first clock reader. Its fraction is already
    /// restricted to six decimal places, so it needs no repeated-field check.
    #[inline(always)]
    pub fn initial_fraction(&mut self, value: i32, tail: i32, nanos: bool) {
        self.microsecond = value;
        self.fraction.set(tail, nanos);
        if self.strict() {
            if let Some(state) = self.policy.tracking_mut() {
                state.clock_seen |= 8;
            }
        }
    }

    /// Apply one fractional second, including nanosecond conflict checks.
    pub fn set_fraction(&mut self, value: i32, tail: i32, nanos: bool) -> ParseResult<()> {
        if P::Fraction::NANO
            && self.strict()
            && self.clock_was_seen(3)
            && self.fraction.tail() != tail
        {
            return Err(Self::conflict("nanosecond", self.fraction.tail(), tail));
        }
        self.set_clock(3, value)?;
        self.fraction.set(tail, nanos);
        Ok(())
    }

    /// Compare hours after a following AM/PM suffix has been applied.
    pub fn finish_hour(&mut self) -> ParseResult<()> {
        if let Some(state) = self
            .policy
            .tracking_mut()
            .filter(|state| state.pending_hour != -1)
        {
            let previous = std::mem::replace(&mut state.pending_hour, -1);
            if previous != self.hour {
                return Err(Self::conflict("hour", previous, self.hour));
            }
        }
        Ok(())
    }

    /// Start a timezone field; a following offset may still complete its value.
    pub fn begin_timezone(&mut self, value: i32) -> ParseResult<()> {
        self.finish_timezone()?;
        if self.strict() && self.tzoffset != -100_000 {
            let previous = self.timezone_microseconds();
            if let Some(state) = self.policy.tracking_mut() {
                state.pending_timezone = previous;
            }
        }
        self.tzoffset = value;
        self.tzoffset_microsecond = 0;
        self.tzoffset_finalized = false;
        Ok(())
    }

    pub fn numeric_timezone_parts(&mut self, offset: i32, microsecond: i32) -> ParseResult<()> {
        if self.tzoffset_finalized {
            self.begin_timezone(offset)?;
        } else if self.tzoffset != -100_000 {
            self.tzoffset = self
                .tzoffset
                .checked_add(offset)
                .ok_or_else(|| ParseError::Overflow("UTC offset overflow".into()))?;
        } else {
            self.tzoffset = offset;
        }
        self.tzoffset_microsecond = microsecond;
        self.tzoffset_finalized = true;
        Ok(())
    }

    pub fn finish_timezone(&mut self) -> ParseResult<()> {
        let current = self.timezone_microseconds();
        if let Some(state) = self
            .policy
            .tracking_mut()
            .filter(|state| state.pending_timezone != i64::MIN)
        {
            let previous = std::mem::replace(&mut state.pending_timezone, i64::MIN);
            if previous != current {
                return Err(ParseError::Value(format!(
                    "Conflicting timezone offsets '{previous}' and '{current}' microseconds."
                )));
            }
        }
        Ok(())
    }

    pub fn apply_ampm(&mut self, value: i32) -> ParseResult<()> {
        if self.strict() && self.ampm != -1 && self.ampm != value {
            return Err(Self::conflict("AM/PM", self.ampm, value));
        }
        let hour = if self.ampm == -1 {
            self.hour_input = self.hour;
            self.hour
        } else {
            self.hour_input
        };
        let hour = if self.strict() {
            self.bounded("12-hour clock hour", i64::from(hour), 1, 12)?
        } else {
            hour.clamp(1, 12)
        };
        self.ampm = value;
        self.hour = if (1..=11).contains(&hour) && value == 1 {
            hour + 12
        } else if hour == 12 && value == 0 {
            0
        } else {
            hour
        };
        Ok(())
    }

    /// Only repeated complete calendars need storage; the normal path allocates none.
    pub fn replace_calendar(&mut self, values: [i32; 3], year_index: i32) {
        if self.strict() && self.ymd_slots_filled() != 0 {
            let previous = CalendarSnapshot {
                ymd: self.ymd,
                idx: self.idx,
                yidx: self.yidx,
                midx: self.midx,
                didx: self.didx,
                doy: self.doy,
                century_specified: self.century_specified,
                month_override: self.month_override,
            };
            if let Some(state) = self.policy.tracking_mut() {
                state.dates.push(previous);
            }
        }
        self.ymd = values;
        self.idx = 2;
        self.yidx = year_index;
        self.midx = -1;
        self.didx = -1;
        self.year = -1;
        self.month = -1;
        self.month_override = -1;
        self.day = -1;
        self.doy = -1;
        self.resolved = false;
        self.century_specified = true;
    }

    #[inline(always)]
    pub fn set_ymd_int(&mut self, mut flag: i32, mut value: i64) -> ParseResult<bool> {
        if self.idx >= 2 && flag == 0 {
            return Ok(false);
        }
        match flag {
            0 => {
                if value > 31 {
                    if value > 99 && !self.is_year_set() {
                        self.century_specified = true;
                    }
                    flag = 1;
                } else if value == 0 {
                    flag = 1;
                }
            }
            1 => {
                if value > 99 && !self.is_year_set() {
                    self.century_specified = true;
                }
            }
            2 => value = i64::from(self.bounded("month", value, 1, 12)?),
            3 => value = i64::from(self.bounded("day", value, 1, 31)?),
            _ => return Err(Self::invalid_flag(flag)),
        }
        if flag == 1 && (self.century_specified || !(0..100).contains(&value)) {
            value = i64::from(self.year_value(value)?);
        }
        self.record_ymd(flag, value as i32)
    }

    pub fn set_ymd_str(&mut self, mut flag: i32, token: &[u32]) -> ParseResult<bool> {
        if self.idx >= 2 && flag == 0 {
            return Ok(false);
        }
        if token.is_empty() || token.iter().any(|&c| !(48..=57).contains(&c)) {
            return Err(ParseError::Value(
                "year/month/day text must contain decimal digits".into(),
            ));
        }
        let mut value = 0u64;
        for &c in token {
            value = value
                .checked_mul(10)
                .and_then(|v| v.checked_add(u64::from(c - 48)))
                .ok_or_else(|| {
                    ParseError::Overflow("integer overflow while reading Y/M/D".into())
                })?;
        }
        let mut value = i64::try_from(value)
            .map_err(|_| ParseError::Overflow("integer overflow while reading year".into()))?;
        if flag == 0 && token.len() == 3 && self.yidx >= 0 && self.midx < 0 && self.didx < 0 {
            self.doy = i32::try_from(value)
                .map_err(|_| ParseError::Overflow("day-of-year overflow".into()))?;
            return Ok(true);
        }
        match flag {
            0 => {
                if token.len() > 2 {
                    if !self.is_year_set() {
                        self.century_specified = true;
                    }
                    flag = 1;
                } else if value > 31 || value == 0 {
                    flag = 1;
                }
            }
            1 => {
                if token.len() > 2 && !self.is_year_set() {
                    self.century_specified = true;
                }
            }
            2 => value = i64::from(self.bounded("month", value, 1, 12)?),
            3 => value = i64::from(self.bounded("day", value, 1, 31)?),
            _ => return Err(Self::invalid_flag(flag)),
        }
        if flag == 1 && (self.century_specified || !(0..100).contains(&value)) {
            value = i64::from(self.year_value(value)?);
        }
        self.record_ymd(flag, value as i32)
    }

    fn invalid_flag(flag: i32) -> ParseError {
        ParseError::Assertion(format!(
            "invalid internal calendar field selector {flag}; expected 0 through 3, inclusive"
        ))
    }

    #[inline(always)]
    pub fn record_ymd(&mut self, flag: i32, value: i32) -> ParseResult<bool> {
        self.resolved = false;
        let index = match flag {
            1 => self.yidx,
            2 => self.midx,
            3 => self.didx,
            _ => -1,
        };
        if index >= 0 {
            if flag == 1 && self.could_be_doy(i64::from(value)) {
                self.doy = value;
                return Ok(true);
            }
            let old = self.ymd[index as usize];
            if self.strict() && old != value {
                return Err(Self::conflict(
                    match flag {
                        1 => "year",
                        2 => "month",
                        _ => "day",
                    },
                    old,
                    value,
                ));
            }
            self.ymd[index as usize] = value;
            return Ok(true);
        }
        if self.idx >= 2 {
            return Ok(false);
        }
        let next = self.idx + 1;
        match flag {
            0 => {}
            1 => self.yidx = next,
            2 => self.midx = next,
            3 => self.didx = next,
            _ => return Err(Self::invalid_flag(flag)),
        }
        self.idx = next;
        self.ymd[next as usize] = value;
        Ok(true)
    }

    pub fn ymd_slots_filled(&self) -> i32 {
        self.idx + 1
    }

    pub fn ymd_roles_resolved(&self) -> i32 {
        i32::from(self.yidx != -1) + i32::from(self.midx != -1) + i32::from(self.didx != -1)
    }

    pub fn could_be_day(&self, value: i64) -> bool {
        if self.didx != -1 || value < 1 {
            return false;
        }
        if self.midx == -1 {
            return value <= 31;
        }
        let month = i64::from(self.ymd[self.midx as usize]);
        let year = if self.yidx == -1 {
            2000
        } else {
            self.ymd[self.yidx as usize]
        };
        value <= calendar::days_in_month(i64::from(year), month)
    }

    pub fn could_be_doy(&self, value: i64) -> bool {
        self.doy == -1
            && value >= 1
            && self.midx == -1
            && self.didx == -1
            && self.yidx != -1
            && value <= 365 + i64::from(calendar::leap(i64::from(self.ymd[self.yidx as usize])))
    }

    pub fn is_year_set(&self) -> bool {
        self.yidx != -1 || self.year != -1
    }
    pub fn is_month_set(&self) -> bool {
        self.midx != -1 || self.month != -1
    }
    pub fn is_day_set(&self) -> bool {
        self.didx != -1 || self.day != -1
    }
    pub fn is_hour_set(&self) -> bool {
        self.hour != -1
    }
    pub fn is_minute_set(&self) -> bool {
        self.minute != -1
    }
    pub fn is_second_set(&self) -> bool {
        self.second != -1
    }
    pub fn is_microsecond_set(&self) -> bool {
        self.microsecond != -1
    }
    pub fn is_weekday_set(&self) -> bool {
        self.weekday != -1
    }
    pub fn is_tzoffset_set(&self) -> bool {
        self.tzoffset != -100_000
    }

    pub fn valid(&self) -> bool {
        self.is_year_set()
            || self.is_month_set()
            || self.is_day_set()
            || self.is_hour_set()
            || self.is_minute_set()
            || self.is_second_set()
            || self.is_microsecond_set()
            || self.is_weekday_set()
            || self.is_tzoffset_set()
    }
}

#[cfg(test)]
mod policy_tests {
    use super::{Fields, Lenient, Strict};

    #[test]
    fn ordinary_fields_require_no_cleanup() {
        assert!(!std::mem::needs_drop::<Fields<Lenient>>());
        assert!(std::mem::needs_drop::<Fields<Strict>>());
    }
}
