//! The exact nanosecond Delta value; independent of Python and date containers.
//!
//! A calendar-month group and a fixed-day/clock group are canonicalized
//! separately. Absolute field presence is intrinsic, including explicit zero.

/// Nanoseconds in one civil day.
pub(crate) const NS_PER_DAY: i128 = 86_400_000_000_000;

/// An absolute field in canonical, serialized order.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(usize)]
pub(crate) enum AbsoluteField {
    Year,
    Month,
    Day,
    Weekday,
    Hour,
    Minute,
    Second,
    Microsecond,
    Nanosecond,
}

impl AbsoluteField {
    /// All fields, in the version-two state order.
    pub(crate) const ALL: [Self; 9] = [
        Self::Year,
        Self::Month,
        Self::Day,
        Self::Weekday,
        Self::Hour,
        Self::Minute,
        Self::Second,
        Self::Microsecond,
        Self::Nanosecond,
    ];

    const fn bounds(self) -> (i64, i64) {
        match self {
            Self::Year => (1, 9999),
            Self::Month => (1, 12),
            Self::Day => (1, 31),
            Self::Weekday => (0, 6),
            Self::Hour => (0, 23),
            Self::Minute | Self::Second => (0, 59),
            Self::Microsecond => (0, 999_999),
            Self::Nanosecond => (0, 999),
        }
    }
}

/// Native errors; public adapters supply their own exception and context.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum ValueError {
    Overflow,
    NotANumber,
    AbsoluteRange(AbsoluteField),
    NonCanonical,
}

/// Compact absolute values with a separate unset encoding for every field.
///
/// Each lane stores value+1, or zero when absent. No lane is inferred from
/// another field, so microsecond=1 does not imply nanosecond=0 in the value.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub(crate) struct AbsoluteFields(u128);

const WIDTHS: [u32; 9] = [14, 4, 6, 3, 5, 6, 6, 20, 10];
const SHIFTS: [u32; 9] = [0, 14, 18, 24, 27, 32, 38, 44, 64];

impl AbsoluteFields {
    /// No absolute replacements.
    pub(crate) const EMPTY: Self = Self(0);

    /// Return a field, preserving absent versus explicit zero.
    #[inline]
    pub(crate) fn get(self, field: AbsoluteField) -> Option<i64> {
        let index = field as usize;
        let lane = if field == AbsoluteField::Nanosecond {
            (self.0 >> 64) as u64 & 1023
        } else {
            // Every other lane is wholly in the low native word.
            (self.0 as u64 >> SHIFTS[index]) & ((1_u64 << WIDTHS[index]) - 1)
        };
        (lane != 0).then_some(lane as i64 - 1)
    }

    /// Set a validated absolute field; convenience clamping belongs at input.
    #[inline]
    pub(crate) fn set(
        &mut self,
        field: AbsoluteField,
        value: Option<i64>,
    ) -> Result<(), ValueError> {
        let index = field as usize;
        let encoded = if let Some(value) = value {
            let (minimum, maximum) = field.bounds();
            if !(minimum..=maximum).contains(&value) {
                return Err(ValueError::AbsoluteRange(field));
            }
            (value + 1) as u128
        } else {
            0
        };
        let mask = ((1_u128 << WIDTHS[index]) - 1) << SHIFTS[index];
        self.0 = (self.0 & !mask) | (encoded << SHIFTS[index]);
        Ok(())
    }

    /// Insert a bounded constructor selection into an unset lane.
    /// Binding rejects duplicate roles before conversion; aliases are combined
    /// before this call. Existing-value replacements continue to use `set`.
    #[inline]
    pub(crate) fn insert(&mut self, field: AbsoluteField, value: i64) -> Result<(), ValueError> {
        debug_assert!(self.get(field).is_none());
        let (minimum, maximum) = field.bounds();
        if !(minimum..=maximum).contains(&value) {
            return Err(ValueError::AbsoluteRange(field));
        }
        if field == AbsoluteField::Nanosecond {
            self.0 |= ((value + 1) as u128) << 64;
        } else {
            let low = self.0 as u64 | ((value + 1) as u64) << SHIFTS[field as usize];
            self.0 = (self.0 & !(u64::MAX as u128)) | u128::from(low);
        }
        Ok(())
    }

    /// Whether any replacement, including a zero clock field, is present.
    #[inline]
    pub(crate) fn is_empty(self) -> bool {
        self.0 == 0
    }

    /// Whether any absolute clock lane is present, including explicit zero.
    #[inline]
    pub(crate) fn replaces_clock(self) -> bool {
        self.0 >> SHIFTS[AbsoluteField::Hour as usize] != 0
    }

    /// Merge each absolute field independently. Right wins for addition;
    /// left wins for subtraction. Neither operation changes absolute signs.
    fn merge(self, other: Self, subtract: bool) -> Self {
        let (preferred, fallback) = if subtract {
            (self, other)
        } else {
            (other, self)
        };
        if preferred.is_empty() {
            return fallback;
        }
        if fallback.is_empty() {
            return preferred;
        }
        let mut bits = 0;
        for index in 0..9 {
            let mask = ((1_u128 << WIDTHS[index]) - 1) << SHIFTS[index];
            let selected = preferred.0 & mask;
            bits |= if selected != 0 {
                selected
            } else {
                fallback.0 & mask
            };
        }
        Self(bits)
    }
}

/// One immutable canonical Delta value, used by every container adapter.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct DeltaValue {
    pub(crate) years: i64,
    months: u8,
    pub(crate) days: i64,
    clock_ns: u64,
    absolute: AbsoluteFields,
}

impl DeltaValue {
    /// Empty Delta; no relative quantity and no absolute setting.
    pub(crate) const ZERO: Self = Self::from_canonical(0, 0, 0, 0, AbsoluteFields::EMPTY);

    /// Store already validated canonical groups. Normalization and public
    /// range checks happen before this private representation boundary.
    #[inline]
    pub(crate) const fn from_canonical(
        years: i64,
        months: u8,
        days: i64,
        clock_ns: u64,
        absolute: AbsoluteFields,
    ) -> Self {
        debug_assert!(months < 12);
        debug_assert!(clock_ns < NS_PER_DAY as u64);
        debug_assert!(absolute.0 >> 74 == 0);
        Self {
            years,
            months,
            days,
            clock_ns,
            absolute,
        }
    }

    /// The only canonical relative clock, in nanoseconds within its day.
    #[inline]
    pub(crate) const fn clock_ns(&self) -> u64 {
        self.clock_ns
    }

    /// Calendar-month remainder, independent of fixed days and clock.
    #[inline]
    pub(crate) const fn months(&self) -> u8 {
        self.months
    }

    /// Return the independently present absolute fields without re-encoding.
    #[inline]
    pub(crate) const fn absolute(&self) -> AbsoluteFields {
        self.absolute
    }

    #[inline]
    pub(crate) fn set_months(&mut self, months: u8) {
        debug_assert!(months < 12);
        self.months = months;
    }

    #[inline]
    pub(crate) fn set_clock_ns(&mut self, clock_ns: u64) {
        debug_assert!(clock_ns < NS_PER_DAY as u64);
        self.clock_ns = clock_ns;
    }

    #[inline]
    pub(crate) const fn with_absolute(mut self, absolute: AbsoluteFields) -> Self {
        debug_assert!(absolute.0 >> 74 == 0);
        self.absolute = absolute;
        self
    }

    /// Update one validated lane, keeping representation changes local.
    #[inline]
    pub(crate) fn set_absolute_field(
        &mut self,
        field: AbsoluteField,
        value: Option<i64>,
    ) -> Result<(), ValueError> {
        self.absolute.set(field, value)
    }

    /// Normalize sufficiently wide totals, then check final signed64 groups.
    #[inline]
    pub(crate) fn from_totals(
        calendar_months: i128,
        fixed_ns: i128,
        absolute: AbsoluteFields,
    ) -> Result<Self, ValueError> {
        // Common totals fit signed64 even though preparation is deliberately
        // wide. Choose the cheaper division width without reducing precision;
        // wide sources/cancellations retain the same final checked fallback.
        let (years, months) = if let Ok(total) = i64::try_from(calendar_months) {
            if (0..12).contains(&total) {
                (0, total as u8)
            } else {
                (total.div_euclid(12), total.rem_euclid(12) as u8)
            }
        } else {
            (
                i64::try_from(calendar_months.div_euclid(12)).map_err(|_| ValueError::Overflow)?,
                calendar_months.rem_euclid(12) as u8,
            )
        };
        let (days, clock_ns) = if let Ok(total) = i64::try_from(fixed_ns) {
            if (0..NS_PER_DAY as i64).contains(&total) {
                (0, total as u64)
            } else {
                (
                    total.div_euclid(NS_PER_DAY as i64),
                    total.rem_euclid(NS_PER_DAY as i64) as u64,
                )
            }
        } else {
            (
                i64::try_from(fixed_ns.div_euclid(NS_PER_DAY)).map_err(|_| ValueError::Overflow)?,
                fixed_ns.rem_euclid(NS_PER_DAY) as u64,
            )
        };
        Ok(Self::from_canonical(
            years, months, days, clock_ns, absolute,
        ))
    }

    /// Combine already canonical groups using at most one carry per group.
    /// Inputs arise only from adding, subtracting or negating canonical values:
    /// months are in -11..=22 and clock is strictly between -day and 2*day.
    /// Keep years/days wide until the carry, so boundary cancellation is valid.
    #[inline]
    fn from_near_canonical(
        years: i128,
        months: i64,
        days: i128,
        clock_ns: i64,
        absolute: AbsoluteFields,
    ) -> Result<Self, ValueError> {
        debug_assert!((-11..=22).contains(&months));
        debug_assert!((-(NS_PER_DAY as i64)..2 * NS_PER_DAY as i64).contains(&clock_ns));
        let year_carry = if months < 0 {
            -1
        } else {
            i128::from(months >= 12)
        };
        let day_carry = if clock_ns < 0 {
            -1
        } else {
            i128::from(clock_ns >= NS_PER_DAY as i64)
        };
        let years = years.checked_add(year_carry).ok_or(ValueError::Overflow)?;
        let days = days.checked_add(day_carry).ok_or(ValueError::Overflow)?;
        Ok(Self::from_canonical(
            i64::try_from(years).map_err(|_| ValueError::Overflow)?,
            (months - year_carry as i64 * 12) as u8,
            i64::try_from(days).map_err(|_| ValueError::Overflow)?,
            (clock_ns - day_carry as i64 * NS_PER_DAY as i64) as u64,
            absolute,
        ))
    }

    /// Full calendar quantity for independent canonical-value test checks.
    #[cfg(test)]
    #[inline]
    pub(crate) fn calendar_months(self) -> i128 {
        i128::from(self.years) * 12 + i128::from(self.months())
    }

    /// Full fixed quantity for canonical-value test checks, safe in i128.
    #[cfg(test)]
    #[inline]
    pub(crate) fn fixed_ns(self) -> i128 {
        i128::from(self.days) * NS_PER_DAY + i128::from(self.clock_ns())
    }

    /// Combine a wide fixed source after its own safe day/clock split. Calendar
    /// months and independent absolute fields still belong to this Delta.
    #[inline]
    pub(crate) fn with_fixed_parts(
        self,
        days: i128,
        clock_ns: u64,
        subtract: bool,
        reverse: bool,
    ) -> Result<Self, ValueError> {
        debug_assert!(clock_ns < NS_PER_DAY as u64);
        if !subtract {
            // Fixed addition leaves the already canonical calendar group alone.
            // The two clocks fit below two days; retain wide source days until
            // their one possible carry and the final signed64 capacity check.
            let clock = self.clock_ns() + clock_ns;
            let carry = u64::from(clock >= NS_PER_DAY as u64);
            let days = days
                .checked_add(i128::from(self.days))
                .and_then(|days| days.checked_add(i128::from(carry)))
                .ok_or(ValueError::Overflow)?;
            return Ok(Self::from_canonical(
                self.years,
                self.months(),
                i64::try_from(days).map_err(|_| ValueError::Overflow)?,
                clock - carry * NS_PER_DAY as u64,
                self.absolute(),
            ));
        }
        let (left_days, left_clock, right_days, right_clock) = if reverse {
            (
                days,
                clock_ns as i64,
                i128::from(self.days),
                self.clock_ns() as i64,
            )
        } else {
            (
                i128::from(self.days),
                self.clock_ns() as i64,
                days,
                clock_ns as i64,
            )
        };
        let direction = if subtract { -1 } else { 1 };
        let clock = left_clock + direction as i64 * right_clock;
        let right_days = right_days
            .checked_mul(direction)
            .ok_or(ValueError::Overflow)?;
        let days = left_days
            .checked_add(right_days)
            .ok_or(ValueError::Overflow)?;
        let calendar_sign = if reverse && subtract { -1 } else { 1 };
        Self::from_near_canonical(
            i128::from(self.years) * calendar_sign,
            i64::from(self.months()) * calendar_sign as i64,
            days,
            clock,
            self.absolute(),
        )
    }

    /// Add/subtract values with final, rather than narrow intermediate, bounds.
    pub(crate) fn combine(self, other: Self, subtract: bool) -> Result<Self, ValueError> {
        let sign = if subtract { -1 } else { 1 };
        Self::from_near_canonical(
            i128::from(self.years) + i128::from(sign) * i128::from(other.years),
            i64::from(self.months()) + sign * i64::from(other.months()),
            i128::from(self.days) + i128::from(sign) * i128::from(other.days),
            self.clock_ns() as i64 + sign * other.clock_ns() as i64,
            self.absolute().merge(other.absolute(), subtract),
        )
    }

    /// Negate relative groups while preserving absolute settings.
    pub(crate) fn negated(self) -> Result<Self, ValueError> {
        Self::from_near_canonical(
            -i128::from(self.years),
            -i64::from(self.months()),
            -i128::from(self.days),
            -(self.clock_ns() as i64),
            self.absolute(),
        )
    }

    /// Absolute magnitude by calendar and fixed groups, preserving replacements.
    pub(crate) fn magnitude(self) -> Result<Self, ValueError> {
        if self.years >= 0 && self.days >= 0 {
            return Ok(self);
        }
        let calendar_sign = if self.years < 0 { -1 } else { 1 };
        let fixed_sign = if self.days < 0 { -1 } else { 1 };
        Self::from_near_canonical(
            i128::from(self.years) * i128::from(calendar_sign),
            i64::from(self.months()) * calendar_sign,
            i128::from(self.days) * i128::from(fixed_sign),
            self.clock_ns() as i64 * fixed_sign,
            self.absolute(),
        )
    }

    /// True for a nonzero relative value or any explicit absolute replacement.
    #[inline]
    pub(crate) fn is_nonzero(self) -> bool {
        self.years != 0
            || self.months != 0
            || self.days != 0
            || self.clock_ns != 0
            || !self.absolute.is_empty()
    }

    /// Expand only at the explicit version-two state/representation boundary.
    #[inline]
    pub(crate) fn core17(&self) -> [i64; 17] {
        let clock = self.clock_ns();
        let absolute = self.absolute();
        let mut fields = [
            self.years,
            i64::from(self.months()),
            self.days,
            (clock / 3_600_000_000_000) as i64,
            (clock / 60_000_000_000 % 60) as i64,
            (clock / 1_000_000_000 % 60) as i64,
            (clock / 1000 % 1_000_000) as i64,
            (clock % 1000) as i64,
            -1,
            -1,
            -1,
            -1,
            -1,
            -1,
            -1,
            -1,
            -1,
        ];
        for (index, field) in AbsoluteField::ALL.into_iter().enumerate() {
            fields[index + 8] = absolute.get(field).unwrap_or(-1);
        }
        fields
    }

    /// Restore a strictly canonical state; never normalize malformed state.
    pub(crate) fn from_core17(fields: [i64; 17]) -> Result<Self, ValueError> {
        let limits = [(1, 11), (3, 23), (4, 59), (5, 59), (6, 999_999), (7, 999)];
        if limits
            .iter()
            .any(|&(index, maximum)| !(0..=maximum).contains(&fields[index]))
        {
            return Err(ValueError::NonCanonical);
        }
        let mut absolute = AbsoluteFields::EMPTY;
        for (index, field) in AbsoluteField::ALL.into_iter().enumerate() {
            let value = fields[index + 8];
            absolute.set(field, if value == -1 { None } else { Some(value) })?;
        }
        Ok(Self::from_canonical(
            fields[0],
            fields[1] as u8,
            fields[2],
            (fields[3] * 3_600_000_000_000
                + fields[4] * 60_000_000_000
                + fields[5] * 1_000_000_000
                + fields[6] * 1000
                + fields[7]) as u64,
            absolute,
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn total_width_specialization_matches_wide_euclidean_coordinates() {
        let months = [
            i128::from(i64::MIN) - 1,
            i128::from(i64::MIN),
            -1,
            0,
            1,
            i128::from(i64::MAX),
            i128::from(i64::MAX) + 1,
            11,
            12,
            13,
            i128::from(i64::MAX) * 12 + 11,
            i128::from(i64::MAX) * 12 + 12,
        ];
        let fixed = [
            i128::from(i64::MIN) - 1,
            i128::from(i64::MIN),
            -NS_PER_DAY - 1,
            -1,
            0,
            1,
            NS_PER_DAY - 1,
            NS_PER_DAY,
            NS_PER_DAY + 1,
            i128::from(i64::MAX),
            i128::from(i64::MAX) + 1,
            i128::from(i64::MAX) * NS_PER_DAY + NS_PER_DAY - 1,
            i128::from(i64::MAX) * NS_PER_DAY + NS_PER_DAY,
        ];
        for calendar in months {
            for ns in fixed {
                let year = i64::try_from(calendar.div_euclid(12));
                let day = i64::try_from(ns.div_euclid(NS_PER_DAY));
                let actual = DeltaValue::from_totals(calendar, ns, AbsoluteFields::EMPTY);
                match (year, day) {
                    (Ok(years), Ok(days)) => assert_eq!(
                        actual.unwrap(),
                        DeltaValue::from_canonical(
                            years,
                            calendar.rem_euclid(12) as u8,
                            days,
                            ns.rem_euclid(NS_PER_DAY) as u64,
                            AbsoluteFields::EMPTY,
                        )
                    ),
                    _ => assert_eq!(actual, Err(ValueError::Overflow)),
                }
            }
        }
    }

    #[test]
    fn negative_one_ns_borrows_a_day() {
        let value = DeltaValue::from_totals(0, -1, AbsoluteFields::EMPTY).unwrap();
        assert_eq!(value.days, -1);
        assert_eq!(value.clock_ns(), 86_399_999_999_999);
        assert_eq!(&value.core17()[3..8], &[23, 59, 59, 999_999, 999]);
        assert_eq!(value.fixed_ns(), -1);
    }

    #[test]
    fn exact_units_cancel_and_compare() {
        let one_us = DeltaValue::from_totals(0, 1000, AbsoluteFields::EMPTY).unwrap();
        let minus = DeltaValue::from_totals(0, -1000, AbsoluteFields::EMPTY).unwrap();
        assert_eq!(one_us.combine(minus, false).unwrap(), DeltaValue::ZERO);
        assert_ne!(
            DeltaValue::from_totals(0, 1, AbsoluteFields::EMPTY).unwrap(),
            DeltaValue::ZERO
        );
    }

    #[test]
    fn independent_absolute_fields_merge_without_clearing_ns() {
        let mut first = DeltaValue::ZERO;
        first
            .set_absolute_field(AbsoluteField::Nanosecond, Some(2))
            .unwrap();
        let mut second = DeltaValue::ZERO;
        second
            .set_absolute_field(AbsoluteField::Microsecond, Some(1))
            .unwrap();
        for result in [
            first.combine(second, false).unwrap(),
            second.combine(first, false).unwrap(),
        ] {
            assert_eq!(result.absolute().get(AbsoluteField::Microsecond), Some(1));
            assert_eq!(result.absolute().get(AbsoluteField::Nanosecond), Some(2));
        }
        assert_eq!(second.absolute().get(AbsoluteField::Nanosecond), None);
    }

    #[test]
    fn explicit_absolute_zero_is_not_unset() {
        let mut value = DeltaValue::ZERO;
        value
            .set_absolute_field(AbsoluteField::Nanosecond, Some(0))
            .unwrap();
        assert!(value.is_nonzero());
        assert_ne!(value, DeltaValue::ZERO);
        assert_eq!(DeltaValue::from_core17(value.core17()).unwrap(), value);
    }

    #[test]
    fn minimum_days_can_be_negated_after_clock_carry() {
        let value = DeltaValue::from_canonical(0, 0, i64::MIN, 1, AbsoluteFields::EMPTY);
        let opposite = value.negated().unwrap();
        assert_eq!(opposite.days, i64::MAX);
        assert_eq!(opposite.clock_ns(), 86_399_999_999_999);
        assert!(
            DeltaValue::from_canonical(0, 0, i64::MIN, 0, AbsoluteFields::EMPTY)
                .negated()
                .is_err()
        );
        assert_eq!(value.magnitude().unwrap(), opposite);
    }

    #[test]
    fn canonical_carries_match_full_wide_totals_at_signed_boundaries() {
        let groups = [i64::MIN, i64::MIN + 1, -1, 0, 1, i64::MAX - 1, i64::MAX];
        let clocks = [0, 1, NS_PER_DAY as u64 / 2, NS_PER_DAY as u64 - 1];
        for (index, &years) in groups.iter().enumerate() {
            for &months in &[0, 1, 11] {
                for &days in &groups {
                    for &clock_ns in &clocks {
                        let a = DeltaValue::from_canonical(
                            years,
                            months,
                            days,
                            clock_ns,
                            AbsoluteFields::EMPTY,
                        );
                        for &other_years in &groups {
                            let b = DeltaValue::from_canonical(
                                other_years,
                                11 - months,
                                groups[(index + 3) % groups.len()],
                                clocks[(index + 1) % clocks.len()],
                                AbsoluteFields::EMPTY,
                            );
                            for subtract in [false, true] {
                                let sign = if subtract { -1 } else { 1 };
                                let expected = DeltaValue::from_totals(
                                    a.calendar_months() + sign * b.calendar_months(),
                                    a.fixed_ns() + sign * b.fixed_ns(),
                                    AbsoluteFields::EMPTY,
                                );
                                assert_eq!(
                                    a.combine(b, subtract),
                                    expected,
                                    "a={a:?} b={b:?} subtract={subtract}"
                                );
                            }
                        }
                        assert_eq!(
                            a.negated(),
                            DeltaValue::from_totals(
                                -a.calendar_months(),
                                -a.fixed_ns(),
                                a.absolute()
                            )
                        );
                        assert_eq!(
                            a.magnitude(),
                            DeltaValue::from_totals(
                                a.calendar_months().abs(),
                                a.fixed_ns().abs(),
                                a.absolute()
                            )
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn absolute_clock_presence_preserves_explicit_zero_and_calendar_only() {
        assert!(!AbsoluteFields::EMPTY.replaces_clock());
        for field in AbsoluteField::ALL {
            let mut absolute = AbsoluteFields::EMPTY;
            absolute.set(field, Some(field.bounds().0)).unwrap();
            assert_eq!(
                absolute.replaces_clock(),
                field as usize >= AbsoluteField::Hour as usize,
                "{field:?}"
            );
        }
    }

    #[test]
    fn all_abs_lanes_are_independent_at_their_limits() {
        let mut absolute = AbsoluteFields::EMPTY;
        for field in AbsoluteField::ALL {
            absolute.set(field, Some(field.bounds().1)).unwrap();
        }
        for field in AbsoluteField::ALL {
            assert_eq!(absolute.get(field), Some(field.bounds().1));
        }
        let value = DeltaValue::ZERO.with_absolute(absolute);
        assert_eq!(DeltaValue::from_core17(value.core17()).unwrap(), value);
        assert!(absolute.set(AbsoluteField::Nanosecond, Some(1000)).is_err());
        assert!(absolute.set(AbsoluteField::Nanosecond, Some(-1)).is_err());
    }

    #[test]
    fn subtraction_keeps_left_absolute() {
        let mut left = DeltaValue::ZERO;
        left.set_absolute_field(AbsoluteField::Nanosecond, Some(0))
            .unwrap();
        let mut right = DeltaValue::ZERO;
        right
            .set_absolute_field(AbsoluteField::Nanosecond, Some(999))
            .unwrap();
        assert_eq!(
            left.combine(right, true)
                .unwrap()
                .absolute()
                .get(AbsoluteField::Nanosecond),
            Some(0)
        );
    }

    #[test]
    fn malformed_state_does_not_get_normalized() {
        let mut fields = DeltaValue::ZERO.core17();
        fields[7] = 1000;
        assert_eq!(
            DeltaValue::from_core17(fields),
            Err(ValueError::NonCanonical)
        );
    }
}
