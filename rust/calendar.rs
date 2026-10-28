//! Checked Gregorian calculations required by Delta.
//!
//! Ordinal 1 is 0001-01-01. Absolute replacements precede relative increments;
//! weekday adjustment runs last. Internal years may exceed Python's date range,
//! while integer widths and final Python constructor bounds are checked separately.

const OVERFLOW: &str = "integer overflow in Delta date arithmetic";
const MONTH_STARTS: [i64; 12] = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

/// Return whether year is a leap year in the proleptic Gregorian calendar.
///
/// The same divisibility rules apply to temporary years outside Python's range.
pub fn leap(year: i64) -> bool {
    year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
}

/// Return the Gregorian month length for a year and a month in 1..=12.
///
/// # Preconditions
/// Callers validate month before entering this internal helper; other values
/// fall through to 31 and are not an alternate input validation interface.
pub fn days_in_month(year: i64, month: i64) -> i64 {
    match month {
        2 => {
            if leap(year) {
                29
            } else {
                28
            }
        }
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}

/// Convert year, month and day to a day number where 0001-01-01 is 1.
///
/// Day is clamped to 1..=days_in_month(year, month), preserving Delta's
/// month-end behavior before relative days are added.
///
/// # Preconditions
/// Month must be in 1..=12 and year must fit the checked calendar path's i32
/// range. These invariants keep indexing and year arithmetic within bounds.
pub fn ordinal(year: i64, month: i64, day: i64) -> i64 {
    let previous = year - 1;
    previous * 365 + previous.div_euclid(4) - previous.div_euclid(100)
        + previous.div_euclid(400)
        + MONTH_STARTS[(month - 1) as usize]
        + i64::from(month > 2 && leap(year))
        + if day > 28 {
            day.min(days_in_month(year, month))
        } else {
            day.max(1)
        }
}

/// Compute an ordinal for wide temporary years using checked arithmetic.
/// # Preconditions
/// Month is1..12; day uses the same clamping as the bounded fast path.
/// # Errors
/// Rejects unrepresentable calendar intermediates before adding relative days.
pub(crate) fn checked_ordinal(year: i64, month: i64, day: i64) -> Result<i64, &'static str> {
    let previous = year.checked_sub(1).ok_or(OVERFLOW)?;
    let before = previous
        .checked_mul(365)
        .ok_or(OVERFLOW)?
        .checked_add(previous.div_euclid(4))
        .ok_or(OVERFLOW)?
        .checked_sub(previous.div_euclid(100))
        .ok_or(OVERFLOW)?
        .checked_add(previous.div_euclid(400))
        .ok_or(OVERFLOW)?;
    before
        .checked_add(MONTH_STARTS[(month - 1) as usize])
        .ok_or(OVERFLOW)?
        .checked_add(i64::from(month > 2 && leap(year)))
        .ok_or(OVERFLOW)?
        .checked_add(day.max(1).min(days_in_month(year, month)))
        .ok_or(OVERFLOW)
}

/// Decode a Gregorian day number into [year, month, day].
///
/// # Errors
/// Returns the calendar overflow error if subtracting one from value overflows.
/// The returned year may be outside Python's 1..=9999 range; Python constructors
/// validate that final range.
pub fn from_ordinal(value: i64) -> Result<[i64; 3], &'static str> {
    let n = value.checked_sub(1).ok_or(OVERFLOW)?;
    let cycles = n.div_euclid(146_097);
    let mut rest = n.rem_euclid(146_097);
    let centuries = rest / 36_524;
    rest %= 36_524;
    let fours = rest / 1_461;
    rest %= 1_461;
    let years = rest / 365;
    rest %= 365;
    let year = cycles * 400 + centuries * 100 + fours * 4 + years + 1;
    if centuries == 4 || years == 4 {
        return Ok([year - 1, 12, 31]);
    }
    // Same estimate and one correction as the frozen ordinal conversion.
    let mut month = (rest + 50) >> 5;
    let before =
        |month: i64| MONTH_STARTS[(month - 1) as usize] + i64::from(month > 2 && leap(year));
    let mut month_start = before(month);
    if month_start > rest {
        month -= 1;
        month_start = before(month);
    }
    Ok([year, month, rest - month_start + 1])
}

/// Resolve the convenient high day-of-year selection on the shared calendar.
/// The public caller rejects days below one before entering this function.
pub(crate) fn year_day_ordinal(year: i64, day: i64) -> Result<i64, &'static str> {
    checked_ordinal(year, 1, 1)?
        .checked_add(day.min(365 + i64::from(leap(year))) - 1)
        .ok_or(OVERFLOW)
}

/// Resolve an ISO week/day using the actual last week and convenient high limits.
/// The public caller validates positive week/day; wide years remain supported.
pub(crate) fn iso_ordinal(year: i64, week: i64, weekday: i64) -> Result<i64, &'static str> {
    let jan1 = checked_ordinal(year, 1, 1)?;
    let wd = jan1.checked_sub(1).ok_or(OVERFLOW)?.rem_euclid(7);
    let last = if wd == 3 || (wd == 2 && leap(year)) {
        53
    } else {
        52
    };
    let jan4 = jan1.checked_add(3).ok_or(OVERFLOW)?;
    let monday = jan4
        .checked_sub(jan4.checked_sub(1).ok_or(OVERFLOW)?.rem_euclid(7))
        .ok_or(OVERFLOW)?;
    monday
        .checked_add((week.min(last) - 1) * 7 + weekday.min(7) - 1)
        .ok_or(OVERFLOW)
}

/// Add calendar values with checked i64 arithmetic.
///
/// # Errors
/// Returns the calendar overflow error when the sum is not representable.
fn add(left: i64, right: i64) -> Result<i64, &'static str> {
    left.checked_add(right).ok_or(OVERFLOW)
}

/// Apply an operation sign to a relative calendar value.
///
/// # Errors
/// Rejects multiplication overflow, including negation of i64::MIN.
fn signed(value: i64, sign: i64) -> Result<i64, &'static str> {
    value.checked_mul(sign).ok_or(OVERFLOW)
}

/// Add temporary calendar years using checked signed64 arithmetic.
///
/// # Errors
/// Rejects real signed64 addition overflow.
fn year_add(left: i64, right: i64) -> Result<i64, &'static str> {
    add(left, right)
}

/// Shift a normalized date by at most 27 days without an ordinal round trip.
///
/// Month must be 1..=12 and offset must be -27..=27. Wide intermediate
/// years retain Delta's checked year-carry behavior; callers enforce date bounds.
/// # Errors
/// Returns an error if crossing a year would overflow signed 64-bit storage.
#[inline(always)]
pub(crate) fn shift_small_days(
    mut year: i64,
    mut month: i64,
    mut day: i64,
    offset: i64,
) -> Result<[i64; 3], &'static str> {
    day = day.min(days_in_month(year, month)) + offset;
    if day < 1 {
        if month == 1 {
            year = year_add(year, -1)?;
            month = 12;
        } else {
            month -= 1;
        }
        day += days_in_month(year, month);
    } else {
        let length = days_in_month(year, month);
        if day > length {
            day -= length;
            if month == 12 {
                year = year_add(year, 1)?;
                month = 1;
            } else {
                month += 1;
            }
        }
    }
    Ok([year, month, day])
}

/// Select the destination month once, clamp its legal day intent, then move days.
/// Input/selection months and days have already passed their public ranges.
/// Output capacity belongs to the scalar or array caller, not this calendar.
pub(crate) fn move_date(
    date: [i64; 3],
    months: i128,
    days: i128,
    month: Option<i64>,
    day: Option<i64>,
) -> Result<[i64; 3], &'static str> {
    let total = i128::from(date[0]) * 12 + i128::from(month.unwrap_or(date[1])) - 1 + months;
    let year = i64::try_from(total.div_euclid(12)).map_err(|_| OVERFLOW)?;
    let month = (total.rem_euclid(12) + 1) as i64;
    let day = day.unwrap_or(date[2]).min(days_in_month(year, month));
    if days == 0 {
        return Ok([year, month, day]);
    }
    if (-27..=27).contains(&days) {
        return shift_small_days(year, month, day, days as i64);
    }
    let ordinal = i128::from(checked_ordinal(year, month, day)?) + days;
    from_ordinal(i64::try_from(ordinal).map_err(|_| OVERFLOW)?)
}

/// Gap alternatives remain in the explicitly selected local calendar day.
pub(crate) fn calendar_gap_targets(wall: i128, gap: i128, forward: bool) -> [Option<i128>; 2] {
    const DAY: i128 = 86_400_000_000_000;
    let day = wall.div_euclid(DAY);
    let preferred = if forward { gap } else { -gap };
    [wall.checked_add(preferred), wall.checked_sub(preferred)]
        .map(|value| value.filter(|v| v.div_euclid(DAY) == day))
}

/// Apply absolute replacements, relative increments, then weekday adjustment.
///
/// # Arguments
/// - fields: The 15 normalized Delta fields in snapshot order.
/// - input: [year, month, day, hour, minute, second, microsecond].
/// - sign: 1 for addition or -1 for subtraction.
/// - datetime: Whether clock fields belong to the input datetime or affect a date
///   only through their contribution to whole days.
///
/// # Returns
/// The resulting seven date/time parts and whether those parts are unchanged.
/// Temporary years may exceed Python's range; the caller's constructor checks it.
///
/// # Errors
/// Rejects an invalid sign, checked arithmetic overflow, or a year outside the
/// reference's intermediate i32 width.
#[inline(always)]
pub fn apply(
    fields: &[i64; 15],
    input: [i64; 7],
    sign: i64,
    datetime: bool,
) -> Result<([i64; 7], bool), &'static str> {
    match (sign, datetime) {
        (1, true) => apply_inner::<1, true>(fields, input),
        (1, false) => apply_inner::<1, false>(fields, input),
        (-1, true) => apply_inner::<-1, true>(fields, input),
        (-1, false) => apply_inner::<-1, false>(fields, input),
        _ => Err(OVERFLOW),
    }
}

// Four fixed operation forms allow Rust to remove unused date/time branches
// and multiplication by +1; negative-day overflow remains checked.
/// Evaluate one fixed sign/date form without repeating dispatch decisions.
///
/// # Preconditions
/// SIGN is 1 or -1, input is a valid builtin date/datetime's parts, and fields
/// satisfy Delta's normalized ranges. The caller selects the matching form.
///
/// # Errors
/// Returns the calendar overflow error for unrepresentable days or years.
#[inline(always)]
fn apply_inner<const SIGN: i64, const DATETIME: bool>(
    fields: &[i64; 15],
    input: [i64; 7],
) -> Result<([i64; 7], bool), &'static str> {
    let replace = |index: usize, original: i64, positive: bool| {
        let value = fields[index];
        if value > 0 || (!positive && value == 0) {
            value
        } else {
            original
        }
    };
    // Caller supplies normalized Delta fields and a built-in date's parts.
    // Years and days can occupy the whole signed64 range. Checked sign and
    // addition happen before calendars or constructor callbacks. Months remain
    // canonical0..11 and cross at most one year.
    let mut year = year_add(replace(7, input[0], true), signed(fields[0], SIGN)?)?;
    let mut month = replace(8, input[1], true) + fields[1] * SIGN;
    // Absolute month is1..12 and normalized relative month is0..11.
    // Either sign can therefore cross at most one year; division is unnecessary.
    if month > 12 {
        year = year_add(year, 1)?;
        month -= 12;
    } else if month < 1 {
        year = year_add(year, -1)?;
        month += 12;
    }
    let mut day = replace(9, input[2], true);
    let mut relative_days = signed(fields[2], SIGN)?;
    let mut time = [0_i32; 4];
    for (offset, value) in time.iter_mut().enumerate() {
        // Normalized relative time and valid builtin date/time parts are bounded.
        // Microseconds sum is within -999999..=1999998; all time sums and
        // subsequent carries fit i32. This matches the original clock widths.
        *value = replace(
            11 + offset,
            if DATETIME { input[3 + offset] } else { 0 },
            false,
        ) as i32
            + fields[3 + offset] as i32 * SIGN as i32;
    }
    if DATETIME {
        for (child, parent, base) in [(3, 2, 1_000_000), (2, 1, 60), (1, 0, 60)] {
            // Valid input and canonical Delta components need at most one
            // carry or borrow, including the preceding smaller-unit carry.
            // Preserve negative floor normalization without integer division.
            if time[child] >= base {
                time[child] -= base;
                time[parent] += 1;
            } else if time[child] < 0 {
                time[child] += base;
                time[parent] -= 1;
            }
        }
        if time[0] >= 24 {
            relative_days = add(relative_days, 1)?;
            time[0] -= 24;
        } else if time[0] < 0 {
            relative_days = add(relative_days, -1)?;
            time[0] += 24;
        }
    } else {
        let mut us = i64::from(time[3]);
        for (index, factor) in [(2, 1_000_000), (1, 60_000_000), (0, 3_600_000_000)] {
            us += i64::from(time[index]) * factor;
        }
        if us != 0 {
            relative_days = add(relative_days, us.div_euclid(86_400_000_000))?;
        }
        time = [0; 4];
    }
    // A small day shift needs at most one month boundary. Clamp the source
    // day first, as ordinal() does, and use checked signed64 year carries.
    // The 27-day bound is below every month's length, including February.
    if relative_days != 0 && (-27..=27).contains(&relative_days) && fields[10] < 0 {
        [year, month, day] = shift_small_days(year, month, day, relative_days)?;
    } else if relative_days != 0 || fields[10] >= 0 {
        let old = if i32::try_from(year).is_ok() {
            ordinal(year, month, day)
        } else {
            checked_ordinal(year, month, day)?
        };
        let mut new = add(old, relative_days)?;
        if fields[10] >= 0 {
            let weekday = add(new, 6)?.rem_euclid(7);
            new = add(new, fields[10] - weekday)?;
        }
        if new != old {
            [year, month, day] = from_ordinal(new)?;
        }
    }
    let mut result = [
        year,
        month,
        day,
        i64::from(time[0]),
        i64::from(time[1]),
        i64::from(time[2]),
        i64::from(time[3]),
    ];
    let unchanged = result == input;
    if day > 28 {
        day = day.min(days_in_month(year, month));
    }
    result[2] = day;
    Ok((result, unchanged))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn gregorian_centuries_and_known_ordinals() {
        assert!(!leap(1900));
        assert!(leap(2000));
        for (ymd, expected) in [
            ([1, 1, 1], 1),
            ([1970, 1, 1], 719_163),
            ([2000, 2, 29], 730_179),
            ([9999, 12, 31], 3_652_059),
            ([0, 12, 31], 0),
            ([-1, 12, 31], -366),
        ] {
            assert_eq!(ordinal(ymd[0], ymd[1], ymd[2]), expected);
            assert_eq!(from_ordinal(expected).unwrap(), ymd);
        }
    }
    #[test]
    fn ordinal_clamps_month_end_before_adding_days() {
        assert_eq!(ordinal(2023, 2, 31), ordinal(2023, 2, 28));
        assert_eq!(
            from_ordinal(ordinal(2023, 2, 31) + 1).unwrap(),
            [2023, 3, 1]
        );
    }
    #[test]
    fn ordinal_extreme_is_rejected() {
        assert!(from_ordinal(i64::MIN).is_err());
    }

    #[test]
    fn small_day_shifts_match_gregorian_ordinals_and_keep_year_limits() {
        let mut fields = [0; 15];
        fields[7..].fill(-1);
        for year in [-1, 0, 1, 1900, 2000, 2024, 9999] {
            for month in 1..=12 {
                for day in [1, 28, days_in_month(year, month)] {
                    for shift in -27..=27 {
                        if shift == 0 {
                            continue;
                        }
                        fields[2] = shift;
                        let (actual, _) =
                            apply(&fields, [year, month, day, 0, 0, 0, 0], 1, false).unwrap();
                        let expected = from_ordinal(ordinal(year, month, day) + shift).unwrap();
                        assert_eq!(&actual[..3], &expected);
                    }
                }
            }
        }
        fields[2] = 1;
        assert!(apply(&fields, [i64::MAX, 12, 31, 0, 0, 0, 0], 1, false).is_err());
        fields[2] = -1;
        assert!(apply(&fields, [i64::MIN, 1, 1, 0, 0, 0, 0], 1, false).is_err());
        // Absolute day31 first clamps to February's last valid day.
        fields[2] = 1;
        fields[9] = 31;
        assert_eq!(
            apply(&fields, [2023, 2, 10, 0, 0, 0, 0], 1, false)
                .unwrap()
                .0,
            [2023, 3, 1, 0, 0, 0, 0]
        );
    }
}
