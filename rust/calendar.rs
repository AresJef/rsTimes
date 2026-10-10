//! Gregorian calculations needed by Delta; ordinal 1 is 0001-01-01.

const OVERFLOW: &str = "integer overflow in Delta date arithmetic";
const MONTH_STARTS: [i64; 12] = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

pub fn leap(year: i64) -> bool {
    year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
}

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

fn add(left: i64, right: i64) -> Result<i64, &'static str> {
    left.checked_add(right).ok_or(OVERFLOW)
}

fn signed(value: i64, sign: i64) -> Result<i64, &'static str> {
    value.checked_mul(sign).ok_or(OVERFLOW)
}

fn year_add(left: i64, right: i64) -> Result<i64, &'static str> {
    let value = add(left, right)?;
    i32::try_from(value).map(i64::from).map_err(|_| OVERFLOW)
}

/// Replace absolute fields, add relative fields, then adjust weekday.
/// Temporary years may be outside Python's range; constructors check the result.
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
    // Relative years have i32 width; relative months are -11..=11. Their
    // multiplication/addition cannot overflow i64. Keep the original i32
    // year limit check, and checked arithmetic for the unbounded i64 days.
    let mut year = year_add(replace(7, input[0], true), fields[0] * SIGN)?;
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
            if !(0..base).contains(&time[child]) {
                time[parent] += time[child].div_euclid(base);
                time[child] = time[child].rem_euclid(base);
            }
        }
        if !(0..24).contains(&time[0]) {
            relative_days = add(relative_days, i64::from(time[0].div_euclid(24)))?;
            time[0] = time[0].rem_euclid(24);
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
    // day first, as ordinal() does, and retain the original checked year width.
    // The 27-day bound is below every month's length, including February.
    if relative_days != 0 && (-27..=27).contains(&relative_days) && fields[10] < 0 {
        day = day.min(days_in_month(year, month)) + relative_days;
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
    } else if relative_days != 0 || fields[10] >= 0 {
        let old = ordinal(year, month, day);
        let mut new = add(old, relative_days)?;
        if fields[10] >= 0 {
            let weekday = add(new, 6)?.rem_euclid(7);
            new = add(new, fields[10] - weekday)?;
        }
        if new != old {
            [year, month, day] = from_ordinal(new)?;
            i32::try_from(year).map_err(|_| OVERFLOW)?;
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
        assert!(apply(&fields, [i64::from(i32::MAX), 12, 31, 0, 0, 0, 0], 1, false).is_err());
        fields[2] = -1;
        assert!(apply(&fields, [i64::from(i32::MIN), 1, 1, 0, 0, 0, 0], 1, false).is_err());
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
