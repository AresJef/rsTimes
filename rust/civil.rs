//! Exact civil calendar application shared by scalar and column adapters.
//!
//! This layer knows neither Python capacity nor missing-value encodings. Source
//! and final-container validation stay at their respective boundaries.

use crate::delta::value::{AbsoluteField as Field, DeltaValue, NS_PER_DAY};

const OVERFLOW: &str = "integer overflow in Delta date arithmetic";

/// Wide calendar fields with a canonical nanosecond clock within one civil day.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct CivilNs {
    pub(crate) year: i128,
    pub(crate) month: u8,
    pub(crate) day: u8,
    pub(crate) clock_ns: u64,
}

/// Month length on a wide Gregorian year. Month is already validated1..=12.
fn month_length(year: i128, month: u8) -> u8 {
    match month {
        2 => {
            let leap = if let Ok(year) = i64::try_from(year) {
                crate::calendar::leap(year)
            } else {
                year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
            };
            if leap { 29 } else { 28 }
        }
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}

/// Wide ordinal with an ordinary signed64 fast path, sharing the400-year cycle.
pub(crate) fn ordinal(year: i128, month: u8, day: u8) -> Result<i128, &'static str> {
    if let Ok(year) = i64::try_from(year)
        && let Ok(value) = crate::calendar::checked_ordinal(year, i64::from(month), i64::from(day))
    {
        return Ok(i128::from(value));
    }
    let previous = year.checked_sub(1).ok_or(OVERFLOW)?;
    let cycles = previous.div_euclid(400);
    let within = (previous.rem_euclid(400) + 1) as i64;
    let rest = crate::calendar::checked_ordinal(within, i64::from(month), i64::from(day))?;
    cycles
        .checked_mul(146_097)
        .and_then(|number| number.checked_add(i128::from(rest)))
        .ok_or(OVERFLOW)
}

/// Decode a wide ordinal using the existing bounded Gregorian decoder.
pub(crate) fn from_ordinal(ordinal: i128) -> Result<(i128, u8, u8), &'static str> {
    if let Ok(value) = i64::try_from(ordinal)
        && let Ok([year, month, day]) = crate::calendar::from_ordinal(value)
    {
        return Ok((i128::from(year), month as u8, day as u8));
    }
    let before = ordinal.checked_sub(1).ok_or(OVERFLOW)?;
    let cycles = before.div_euclid(146_097);
    let within = (before.rem_euclid(146_097) + 1) as i64;
    let [year, month, day] = crate::calendar::from_ordinal(within)?;
    let year = cycles
        .checked_mul(400)
        .and_then(|value| value.checked_add(i128::from(year)))
        .ok_or(OVERFLOW)?;
    Ok((year, month as u8, day as u8))
}

/// Apply one canonical Delta, preserving ns until a separate final projection.
pub(crate) fn apply(
    value: &DeltaValue,
    input: CivilNs,
    sign: i64,
) -> Result<CivilNs, &'static str> {
    if !matches!(sign, -1 | 1) {
        return Err(OVERFLOW);
    }
    let absolute = value.absolute;
    if absolute.is_empty()
        && value.years == 0
        && value.months == 0
        && value.clock_ns == 0
        && (-27..=27).contains(&value.days)
        && let Ok(year) = i64::try_from(input.year)
        && let Ok([year, month, day]) = crate::calendar::shift_small_days(
            year,
            i64::from(input.month),
            i64::from(input.day),
            sign * value.days,
        )
    {
        // Exact integral-day motion needs no clock decode or ns rounding.
        // Wide/carry cases still use the full checked civil calculation below.
        return Ok(CivilNs {
            year: i128::from(year),
            month: month as u8,
            day: day as u8,
            clock_ns: input.clock_ns,
        });
    }
    let mut year = i128::from(absolute.get(Field::Year).unwrap_or(0));
    if absolute.get(Field::Year).is_none() {
        year = input.year;
    }
    year = year
        .checked_add(i128::from(sign) * i128::from(value.years))
        .ok_or(OVERFLOW)?;
    let mut month = absolute.get(Field::Month).unwrap_or(i64::from(input.month))
        + sign * i64::from(value.months);
    if month > 12 {
        month -= 12;
        year = year.checked_add(1).ok_or(OVERFLOW)?;
    } else if month < 1 {
        month += 12;
        year = year.checked_sub(1).ok_or(OVERFLOW)?;
    }
    let month = month as u8;
    let day = (absolute.get(Field::Day).unwrap_or(i64::from(input.day)) as u8)
        .min(month_length(year, month));

    // Both canonical clocks are below a day. The signed combination and one
    // carry fit i64; the large day group remains wide until the target exit.
    let original = input.clock_ns;
    let hour = absolute
        .get(Field::Hour)
        .unwrap_or((original / 3_600_000_000_000) as i64);
    let minute = absolute
        .get(Field::Minute)
        .unwrap_or((original / 60_000_000_000 % 60) as i64);
    let second = absolute
        .get(Field::Second)
        .unwrap_or((original / 1_000_000_000 % 60) as i64);
    let fraction = if let Some(microsecond) = absolute.get(Field::Microsecond) {
        microsecond * 1000 + absolute.get(Field::Nanosecond).unwrap_or(0)
    } else {
        (original / 1000 % 1_000_000) as i64 * 1000
            + absolute
                .get(Field::Nanosecond)
                .unwrap_or((original % 1000) as i64)
    };
    let clock = hour * 3_600_000_000_000
        + minute * 60_000_000_000
        + second * 1_000_000_000
        + fraction
        + sign * value.clock_ns as i64;
    let days =
        i128::from(sign) * i128::from(value.days) + i128::from(clock.div_euclid(NS_PER_DAY as i64));
    let clock_ns = clock.rem_euclid(NS_PER_DAY as i64) as u64;
    let small = if days != 0 && (-27..=27).contains(&days) && absolute.get(Field::Weekday).is_none()
    {
        i64::try_from(year).ok().and_then(|year| {
            crate::calendar::shift_small_days(year, i64::from(month), i64::from(day), days as i64)
                .ok()
                .map(|[year, month, day]| (i128::from(year), month as u8, day as u8))
        })
    } else {
        None
    };
    let (year, month, day) = if days == 0 && absolute.get(Field::Weekday).is_none() {
        (year, month, day)
    } else if let Some(date) = small {
        date
    } else {
        let number = ordinal(year, month, day)?
            .checked_add(days)
            .ok_or(OVERFLOW)?;
        let number = if let Some(weekday) = absolute.get(Field::Weekday) {
            let actual = number.checked_sub(1).ok_or(OVERFLOW)?.rem_euclid(7);
            number
                .checked_add(i128::from(weekday) - actual)
                .ok_or(OVERFLOW)?
        } else {
            number
        };
        from_ordinal(number)?
    };
    Ok(CivilNs {
        year,
        month,
        day,
        clock_ns,
    })
}

/// Project an exact clock to microseconds once, with ties to the full even tick.
/// A day contains an even number of microseconds, so clock parity is sufficient.
pub(crate) fn project_microseconds(mut value: CivilNs) -> Result<[i64; 7], &'static str> {
    let clock = value.clock_ns;
    let quotient = clock / 1000;
    let remainder = clock % 1000;
    let mut micros =
        quotient + u64::from(remainder > 500 || (remainder == 500 && quotient % 2 != 0));
    if micros == 86_400_000_000 {
        (value.year, value.month, value.day) = from_ordinal(
            ordinal(value.year, value.month, value.day)?
                .checked_add(1)
                .ok_or(OVERFLOW)?,
        )?;
        micros = 0;
    }
    Ok([
        i64::try_from(value.year).map_err(|_| OVERFLOW)?,
        i64::from(value.month),
        i64::from(value.day),
        (micros / 3_600_000_000) as i64,
        (micros / 60_000_000 % 60) as i64,
        (micros / 1_000_000 % 60) as i64,
        (micros % 1_000_000) as i64,
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::delta::value::AbsoluteFields;

    #[test]
    fn final_coordinate_controls_half_even_projection() {
        let delta = DeltaValue::from_totals(0, 500, AbsoluteFields::EMPTY).unwrap();
        let input = CivilNs {
            year: 2024,
            month: 1,
            day: 1,
            clock_ns: 1000,
        };
        assert_eq!(
            project_microseconds(apply(&delta, input, 1).unwrap()).unwrap()[6],
            2
        );
        let input = CivilNs {
            clock_ns: 0,
            ..input
        };
        assert_eq!(
            project_microseconds(apply(&delta, input, 1).unwrap()).unwrap()[6],
            0
        );
    }

    #[test]
    fn negative_ns_selects_previous_date_but_may_round_back_as_datetime() {
        let delta = DeltaValue::from_totals(0, -1, AbsoluteFields::EMPTY).unwrap();
        let input = CivilNs {
            year: 2024,
            month: 1,
            day: 1,
            clock_ns: 0,
        };
        let result = apply(&delta, input, 1).unwrap();
        assert_eq!((result.year, result.month, result.day), (2023, 12, 31));
        assert_eq!(result.clock_ns, 86_399_999_999_999);
        assert_eq!(
            project_microseconds(result).unwrap(),
            [2024, 1, 1, 0, 0, 0, 0]
        );
    }

    #[test]
    fn relative_months_finish_before_month_end_fitting() {
        let mut absolute = AbsoluteFields::EMPTY;
        absolute.set(Field::Month, Some(2)).unwrap();
        absolute.set(Field::Day, Some(31)).unwrap();
        let delta = DeltaValue::from_totals(1, 0, absolute).unwrap();
        let input = CivilNs {
            year: 2024,
            month: 1,
            day: 1,
            clock_ns: 123_456_789,
        };
        assert_eq!(
            apply(&delta, input, 1).unwrap(),
            CivilNs {
                year: 2024,
                month: 3,
                day: 31,
                ..input
            }
        );
    }

    #[test]
    fn explicit_microsecond_clears_only_unspecified_source_tail() {
        let input = CivilNs {
            year: 2024,
            month: 1,
            day: 1,
            clock_ns: 123_456_789,
        };
        let mut delta = DeltaValue::ZERO;
        delta.absolute.set(Field::Microsecond, Some(1)).unwrap();
        assert_eq!(apply(&delta, input, 1).unwrap().clock_ns, 1000);
        delta.absolute.set(Field::Nanosecond, Some(2)).unwrap();
        assert_eq!(apply(&delta, input, 1).unwrap().clock_ns, 1002);
    }
}
