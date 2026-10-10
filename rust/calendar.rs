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
        + day.clamp(1, days_in_month(year, month))
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
    let mut month = 1;
    while rest >= days_in_month(year, month) {
        rest -= days_in_month(year, month);
        month += 1;
    }
    Ok([year, month, rest + 1])
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
pub fn apply(
    fields: &[i64; 15],
    input: [i64; 7],
    sign: i64,
    datetime: bool,
) -> Result<([i64; 7], bool), &'static str> {
    let replace = |index: usize, original: i64, positive: bool| {
        let value = fields[index];
        if value > 0 || (!positive && value == 0) {
            value
        } else {
            original
        }
    };
    let mut year = year_add(replace(7, input[0], true), signed(fields[0], sign)?)?;
    let month = add(replace(8, input[1], true), signed(fields[1], sign)?)?;
    year = year_add(year, (month - 1).div_euclid(12))?;
    let mut month = (month - 1).rem_euclid(12) + 1;
    let mut day = replace(9, input[2], true);
    let mut relative_days = signed(fields[2], sign)?;
    let mut time = [0; 4];
    for (offset, value) in time.iter_mut().enumerate() {
        *value = add(
            replace(
                11 + offset,
                if datetime { input[3 + offset] } else { 0 },
                false,
            ),
            signed(fields[3 + offset], sign)?,
        )?;
    }
    if datetime {
        for (child, parent, base) in [(3, 2, 1_000_000), (2, 1, 60), (1, 0, 60)] {
            time[parent] = add(time[parent], time[child].div_euclid(base))?;
            time[child] = time[child].rem_euclid(base);
        }
        relative_days = add(relative_days, time[0].div_euclid(24))?;
        time[0] = time[0].rem_euclid(24);
    } else {
        let mut us = time[3];
        for (index, factor) in [(2, 1_000_000), (1, 60_000_000), (0, 3_600_000_000)] {
            us = add(us, time[index].checked_mul(factor).ok_or(OVERFLOW)?)?;
        }
        relative_days = add(relative_days, us.div_euclid(86_400_000_000))?;
        time = [0; 4];
    }
    if relative_days != 0 || fields[10] >= 0 {
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
    let unchanged = [year, month, day, time[0], time[1], time[2], time[3]] == input;
    day = day.min(days_in_month(year, month));
    Ok((
        [year, month, day, time[0], time[1], time[2], time[3]],
        unchanged,
    ))
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
}
