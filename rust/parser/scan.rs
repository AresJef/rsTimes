//! Function-based scanner over native Unicode tokens.
use super::fields::{Fields, ParseError, ParseResult, Policy, Precision, Rule, RuleLookup};
use super::text::{CharacterRead, Tokens, ascii_letter, digit, space};

#[inline]
fn date_sep(ch: u32) -> bool {
    (45..=47).contains(&ch)
}
#[inline]
fn one(t: &[u32], ch: u32) -> bool {
    t == [ch]
}
#[inline]
fn dsep(t: &[u32]) -> bool {
    t.len() == 1 && date_sep(t[0])
}
#[inline]
fn ctl(t: &[u32]) -> bool {
    t.len() == 1 && space(t[0])
}
#[inline]
fn week_sep(ch: u32) -> bool {
    ch == 87 || ch == 119
}
/// Convert an ordinal already bounded by ordinal_day or week_date.
#[inline]
fn doy_date(year: i32, doy: i32) -> (i32, i32, i32) {
    const STARTS: [i32; 12] = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    let leap = crate::calendar::leap(i64::from(year));
    debug_assert!((1..=365 + i32::from(leap)).contains(&doy));
    let rest = doy - 1;
    // The calendar's ordinal conversion uses this estimate and one correction.
    let mut month = (rest + 50) >> 5;
    let mut start = STARTS[(month - 1) as usize] + i32::from(month > 2 && leap);
    if start > rest {
        month -= 1;
        start = STARTS[(month - 1) as usize] + i32::from(month > 2 && leap);
    }
    (year, month, rest - start + 1)
}
fn week_date(year: i32, week: i32, weekday: i32) -> (i32, i32, i32) {
    let jan1 = crate::calendar::ordinal(year as i64, 1, 1);
    let jan4 = jan1 + 3;
    let monday = jan4 - (jan4 - 1).rem_euclid(7);
    let target = monday + (week as i64 - 1) * 7 + (weekday as i64 - 1);
    let mut doy = (target - jan1 + 1) as i32;
    if doy < 1 {
        let y = year - 1;
        doy += 365 + i32::from(crate::calendar::leap(y as i64));
        doy_date(y, doy)
    } else if doy > 365 + i32::from(crate::calendar::leap(year as i64)) {
        doy_date(
            year + 1,
            doy - 365 - i32::from(crate::calendar::leap(year as i64)),
        )
    } else {
        doy_date(year, doy)
    }
}
/// Validate raw ISO fields before converting them to a calendar date.
fn iso_week_number<P: Policy>(f: &Fields<P>, year: i32, week: i32) -> ParseResult<i32> {
    let weekday = (crate::calendar::ordinal(i64::from(year), 1, 1) - 1).rem_euclid(7);
    let maximum =
        52 + i32::from(weekday == 3 || (weekday == 2 && crate::calendar::leap(i64::from(year))));
    f.bounded("ISO week", i64::from(week), 1, maximum)
}

fn ordinal_day<P: Policy>(f: &Fields<P>, year: i32, day: i32) -> ParseResult<i32> {
    f.bounded(
        "day-of-year",
        i64::from(day),
        1,
        365 + i32::from(crate::calendar::leap(i64::from(year))),
    )
}

fn iso_date<P: Policy>(
    input: &impl CharacterRead,
    f: &mut Fields<P>,
) -> ParseResult<Option<usize>> {
    let n = input.len();
    if n < 7 {
        return Ok(None);
    }
    let y = input.number(0, 4, 0, 9999);
    if y < 0 {
        return Ok(None);
    }
    let (mut year, month, day, pos);
    let c4 = input.get(4);
    if digit(c4) {
        // Read the complete numeric run once. Its end both selects the compact
        // shape and proves that a longer field will never be partly committed.
        let end = (5..n).find(|&index| !digit(input.get(index))).unwrap_or(n);
        let suffix = input.get(end);
        if end < n
            && !matches!(suffix, 84 | 116)
            && (date_sep(suffix) || (!P::ISO_ONLY && (ascii_letter(suffix) || suffix > 127)))
        {
            return Ok(None);
        }
        if end + 1 == n && matches!(suffix, 72 | 77 | 83 | 104 | 109 | 115) {
            return Ok(None);
        }
        let y = f.year_value(i64::from(y))?;
        if end >= 15 {
            uint(&input.range(0, end))?;
            return Err(ParseError::Value(
                "Unsupported compact calendar length; use a supported date/time form.".into(),
            ));
        }
        if end == 8 {
            let m = input.number(4, 2, 0, 99);
            let d = input.number(6, 2, 0, 99);
            if m < 0 || d < 0 {
                return Ok(None);
            }
            (year, month, day, pos) = (y, m, d, end);
        } else if end == 7 {
            let doy = input.number(4, 3, 0, 999);
            if doy == 0 {
                return Err(ParseError::Value("ordinal day must be at least 1".into()));
            }
            if doy < 0 {
                return Ok(None);
            }
            let doy = ordinal_day(f, y, doy)?;
            (year, month, day) = doy_date(y, doy);
            pos = end;
        } else {
            return Ok(None);
        }
    } else {
        let y = f.year_value(i64::from(y))?;
        if date_sep(c4) {
            // The normal two-digit month already has its delimiter in position 7.
            // Only other shapes need the complete-field fallback scan.
            if !date_sep(input.get(7)) {
                let end = (5..n).find(|&index| !digit(input.get(index))).unwrap_or(n);
                if end != 7 && end < n && date_sep(input.get(end)) {
                    return Ok(None);
                }
            }
            if P::ISO_ONLY && c4 != 45 {
                return Err(ParseError::Value("ISO dates use a hyphen separator".into()));
            }
            if n < 8 {
                let month = input.number(5, 2, 1, 12);
                if !P::ISO_ONLY && c4 != 46 && y > 99 && month > 0 {
                    // Preserve the general scanner's two calendar slots so default
                    // completion, strict checks and error representations agree.
                    f.ymd = [y, month, -1];
                    f.idx = 1;
                    f.yidx = 0;
                    f.century_specified = true;
                    return Ok(Some(n));
                }
                return Ok(None);
            }
            let c7 = input.get(7);
            if date_sep(c7) {
                if P::ISO_ONLY && c7 != 45 {
                    return Err(ParseError::Value("ISO dates use a hyphen separator".into()));
                }
                let m = input.number(5, 2, 0, 99);
                let d = input.number(8, 2, 0, 99);
                if m < 0 || d < 0 {
                    return Ok(None);
                }
                (year, month, day, pos) = (y, m, d, 10);
            } else if week_sep(input.get(5)) {
                let w = input.number(6, 2, 0, 99);
                if w == 0 {
                    return Err(ParseError::Value("ISO week must be at least 1".into()));
                }
                if w < 0 {
                    return Ok(None);
                }
                let (wd, p) = if n > 9 && date_sep(input.get(8)) {
                    let wd = input.number(9, 1, 0, 9);
                    if wd == 0 {
                        return Err(ParseError::Value("ISO weekday must be at least 1".into()));
                    }
                    if wd < 0 {
                        return Ok(None);
                    }
                    (wd, 10)
                } else {
                    (1, 8)
                };
                let w = iso_week_number(f, y, w)?;
                let wd = f.bounded("ISO weekday", i64::from(wd), 1, 7)?;
                (year, month, day) = week_date(y, w, wd);
                pos = p;
            } else if digit(c7) {
                let doy = input.number(5, 3, 0, 999);
                if doy == 0 {
                    return Err(ParseError::Value("ordinal day must be at least 1".into()));
                }
                if doy < 0 {
                    return Ok(None);
                }
                let doy = ordinal_day(f, y, doy)?;
                (year, month, day) = doy_date(y, doy);
                pos = 8;
            } else {
                return Ok(None);
            }
        } else if week_sep(c4) {
            let w = input.number(5, 2, 0, 99);
            if w == 0 {
                return Err(ParseError::Value("ISO week must be at least 1".into()));
            }
            if w < 0 {
                return Ok(None);
            }
            let (wd, p) = if n > 8 && date_sep(input.get(7)) {
                let wd = input.number(8, 1, 0, 9);
                if wd == 0 {
                    return Err(ParseError::Value("ISO weekday must be at least 1".into()));
                }
                if wd < 0 { (1, 7) } else { (wd, 9) }
            } else if n > 7 {
                let wd = input.number(7, 1, 0, 9);
                if wd == 0 {
                    return Err(ParseError::Value("ISO weekday must be at least 1".into()));
                }
                if wd < 0 { (1, 7) } else { (wd, 8) }
            } else {
                (1, 7)
            };
            let w = iso_week_number(f, y, w)?;
            let wd = f.bounded("ISO weekday", i64::from(wd), 1, 7)?;
            (year, month, day) = week_date(y, w, wd);
            pos = p;
        } else {
            return Ok(None);
        }
        // Delimited/week readers still have an independent final field edge.
        if digit(input.get(pos)) {
            return Ok(None);
        }
    }
    if year != y {
        year = f.year_value(i64::from(year))?;
    }
    let month = f.bounded("month", i64::from(month), 1, 12)?;
    let day = f.bounded("day", i64::from(day), 1, 31)?;
    // This is the first scan of fresh fields; ISO readers above validated the
    // month/day and fixed all three roles. Preserve those roles for any suffix.
    f.century_specified = true;
    f.ymd = [year, month, day];
    f.idx = 2;
    f.yidx = 0;
    f.midx = 1;
    f.didx = 2;
    // The ISO reader has already assigned and checked all calendar roles.
    // A calendar suffix invalidates this completed state through record_ymd.
    f.year = year;
    f.month = month;
    f.day = day;
    f.resolved = true;
    Ok(Some(pos))
}
/// Returns the continuation position and whether only post-time handlers apply.
fn iso_time<P: Policy>(
    input: &impl CharacterRead,
    start: usize,
    f: &mut Fields<P>,
    ignore: bool,
) -> ParseResult<(usize, bool)> {
    let n = input.len();
    if start == n {
        return Ok((n, true));
    }
    if start < 7
        || n - start < if P::ISO_ONLY { 3 } else { 6 }
        || !matches!(input.get(start), 32 | 84 | 116)
    {
        return Ok((start, false));
    }
    let h = input.number(start + 1, 2, 0, 99);
    if h < 0 {
        return Ok((start, false));
    }
    // A colon immediately after two proven hour digits fixes their role.
    // Unit suffixes and longer numbers still take the complete-token check.
    let clock_separator = input.get(start + 3);
    if clock_separator != 58 {
        let end = (start + 1..n)
            .find(|&index| !digit(input.get(index)))
            .unwrap_or(n);
        let mut after_number = end;
        if matches!(input.get(after_number), 44 | 46) {
            after_number += 1;
            while digit(input.get(after_number)) {
                after_number += 1;
            }
        }
        if !P::ISO_ONLY
            && ((ascii_letter(input.get(after_number))
                && !matches!(input.get(after_number), 90 | 122))
                || input.get(after_number) > 127)
        {
            return Ok((start, false));
        }
        if input.get(end) == 58 && end != start + 3 {
            return Ok((start, false));
        }
    }
    let (m, s, mut p) = if P::ISO_ONLY
        && (n == start + 3 || matches!(clock_separator, 32 | 43 | 45 | 44 | 46 | 90 | 122))
    {
        (0, 0, start + 3)
    } else if clock_separator == 58 {
        let minute = input.number(start + 4, 2, 0, 99);
        if input.get(start + 6) == 58 {
            (minute, input.number(start + 7, 2, 0, 99), start + 9)
        } else {
            // Fractional minutes retain the general grammar's conversion.
            // A following numeric offset is a separate field, never seconds.
            if !P::ISO_ONLY && matches!(input.get(start + 6), 44 | 46) {
                return Ok((start, false));
            }
            (minute, 0, start + 6)
        }
    } else if P::ISO_ONLY && n >= start + 5 && (n == start + 5 || !digit(input.get(start + 5))) {
        (input.number(start + 3, 2, 0, 99), 0, start + 5)
    } else {
        (
            input.number(start + 3, 2, 0, 99),
            input.number(start + 5, 2, 0, 99),
            start + 7,
        )
    };
    if m < 0 || s < 0 {
        return Ok((start, false));
    }
    let clock_suffix = input.get(p);
    if digit(clock_suffix) {
        return Ok((start, false));
    }
    let second_explicit = p >= start + 7;
    if f.strict() {
        f.initial_strict_clock(h, m, s, clock_separator != 58 || second_explicit)?;
    } else {
        // Fresh ISO fields have no earlier clock to compare. Clamp the values
        // directly and defer AM/PM bookkeeping until a suffix actually uses it.
        f.hour = h.min(23);
        f.minute = m.min(59);
        f.second = s.min(59);
    }
    if n - p > 1 && matches!(clock_suffix, 44 | 46) {
        p += 1;
        let digits = if P::Fraction::NANO { 9 } else { 6 };
        let (us, count, end) = input.fractional_digits(p, digits);
        p = end;
        let microsecond = if count == 0 {
            -1
        } else {
            us * 10_i32.pow(digits - count)
        };
        if microsecond != -1 {
            if P::Fraction::NANO {
                f.initial_fraction(microsecond / 1000, microsecond % 1000, count > 6);
            } else {
                f.initial_fraction(microsecond, 0, false);
            }
        }
    }
    if f.microsecond < 0 && second_explicit {
        f.initial_fraction(0, 0, false);
    }
    while p < n && input.get(p) == 32 {
        p += 1;
    }
    if p == n {
        return Ok((p, true));
    }
    if !ignore {
        if matches!(input.get(p), 90 | 122) {
            if n - p == 1 {
                f.tzoffset = 0;
                f.tzoffset_finalized = true;
                return Ok((n, true));
            }
            if input.get(p + 1) == 32 {
                f.tzoffset = 0;
                f.tzoffset_finalized = true;
                p += 2;
            }
        } else if n - p > 4 && matches!(input.get(p), 43 | 45) {
            let sign = if input.get(p) == 43 { 1 } else { -1 };
            let raw_hour = input.number(p + 1, 2, 0, 99);
            let colon = input.get(p + 3) == 58;
            let minute_start = p + if colon { 4 } else { 3 };
            let raw_minute = input.number(minute_start, 2, 0, 99);
            // A compact hour/minute followed by a colon has explicit seconds.
            // Leave the whole offset to the token reader before committing it.
            if !colon && input.get(minute_start + 2) == 58 {
                return Ok((p, true));
            }
            if colon && minute_start + 2 < n {
                let suffix = input.get(minute_start + 2);
                // A third minute digit or nonstandard seconds field belongs
                // to the complete-token reader. Exact HH:MM needs no reread.
                if digit(suffix)
                    || (suffix == 58
                        && (digit(input.get(minute_start + 5))
                            || !digit(input.get(minute_start + 4))))
                {
                    return Ok((p, true));
                }
            }
            if raw_hour >= 0 && raw_minute >= 0 {
                let hour = f.bounded("timezone hour", i64::from(raw_hour), 0, 23)?;
                let minute = f.bounded("timezone minute", i64::from(raw_minute), 0, 59)?;
                p = minute_start + 2;
                let mut second = 0;
                let mut microsecond = 0;
                if (colon && input.get(p) == 58) || (!colon && digit(input.get(p))) {
                    let second_start = p + usize::from(colon);
                    let raw_second = input.number(second_start, 2, 0, 99);
                    if raw_second >= 0 {
                        second = f.bounded("timezone second", i64::from(raw_second), 0, 59)?;
                        p = second_start + 2;
                        if matches!(input.get(p), 44 | 46) {
                            let (digits, count, end) = input.fractional_digits(p + 1, 6);
                            if count > 0 {
                                microsecond = digits * 10_i32.pow(6 - count);
                                p = end;
                            }
                        }
                    }
                }
                f.numeric_timezone_parts(
                    sign * (hour * 3600 + minute * 60 + second),
                    sign * microsecond,
                )?;
            }
        }
    }
    Ok((p, true))
}

fn kind(t: &[u32]) -> i32 {
    if t.is_empty() {
        return 0;
    }
    let mut dot = false;
    let mut has_digit = false;
    for &ch in t {
        if digit(ch) {
            has_digit = true;
        } else if ch == 46 && !dot {
            dot = true;
        } else {
            return 0;
        }
    }
    if !has_digit {
        0
    } else if dot {
        2
    } else {
        1
    }
}
fn uint(t: &[u32]) -> ParseResult<i64> {
    let mut v = 0_i64;
    for &ch in t {
        if !digit(ch) {
            return Ok(-1);
        }
        v = v
            .checked_mul(10)
            .and_then(|v| v.checked_add((ch - 48) as i64))
            .ok_or_else(|| ParseError::Overflow("integer overflow parsing numeric token".into()))?;
    }
    Ok(v)
}
/// Recognize a short calendar token and read its value in the same pass.
fn small_calendar_number(t: &[u32]) -> Option<i64> {
    if t.is_empty() || t.len() > 4 {
        return None;
    }
    let mut value = 0;
    for &ch in t {
        if !digit(ch) {
            return None;
        }
        // At most four decimal digits fit without the general overflow path.
        value = value * 10 + i64::from(ch - 48);
    }
    Some(value)
}

fn fixed(t: &[u32], start: usize, count: usize, min: i32, max: i32) -> i32 {
    let Some(s) = t.get(start..start + count) else {
        return -1;
    };
    let mut v = 0;
    for &ch in s {
        if !digit(ch) {
            return -1;
        }
        v = v * 10 + (ch - 48) as i32;
    }
    if v >= min && v <= max { v } else { -1 }
}

/// Read a two-digit part of an already classified decimal token.
/// The caller proves the token is ASCII digits and the requested pair exists.
#[inline(always)]
fn clock_pair(t: &[u32], start: usize) -> i32 {
    debug_assert!(start + 2 <= t.len());
    debug_assert!(digit(t[start]) && digit(t[start + 1]));
    ((t[start] - 48) * 10 + t[start + 1] - 48) as i32
}

fn fraction<P: Policy>(t: &[u32]) -> (i32, i32, bool) {
    if t.is_empty() {
        return (-1, 0, false);
    }
    let digits = if P::Fraction::NANO { 9 } else { 6 };
    let (mut value, mut count) = (0, 0);
    for &ch in t {
        if !digit(ch) || count == digits {
            break;
        }
        value = value * 10 + (ch - 48) as i32;
        count += 1;
    }
    value *= 10_i32.pow(digits - count);
    if P::Fraction::NANO {
        (value / 1000, value % 1000, count > 6)
    } else {
        (value, 0, false)
    }
}
fn hms<P: Policy>(f: &mut Fields<P>, flag: i32, t: &[u32]) -> ParseResult<bool> {
    hms_known(f, flag, t, kind(t))
}

/// Reuse a numeric token classification already established by the lexer.
fn hms_known<P: Policy>(f: &mut Fields<P>, flag: i32, t: &[u32], k: i32) -> ParseResult<bool> {
    if !(0..=2).contains(&flag) {
        return Ok(false);
    }
    if k == 0 {
        return Ok(false);
    }
    let split = if k == 1 {
        None
    } else {
        t.iter().position(|&c| c == 46)
    };
    let value = if k == 1 && t.len() == 2 {
        // Classification already checked both ASCII digits. Short clock fields
        // fit i32; keep general checked accumulation for longer/decimal tokens.
        clock_pair(t, 0)
    } else if k == 1 && t.len() == 1 {
        (t[0] - 48) as i32
    } else {
        let integer = uint(&t[..split.unwrap_or(t.len())])?;
        i32::try_from(integer)
            .map_err(|_| ParseError::Overflow("integer overflow parsing clock field".into()))?
    };
    if flag == 2 {
        let (us, tail, nanos) = split.map_or((0, 0, false), |p| fraction::<P>(&t[p + 1..]));
        f.set_second(value, us, tail, nanos)?;
        return Ok(true);
    }
    if !f.strict() && value <= if flag == 0 { 23 } else { 59 } {
        // ASCII digits and the checked fallback already establish nonnegativity.
        // Keep the common valid clock as a single check and direct assignment;
        // exceptional ranges and strict tracking use the shared policy below.
        match flag {
            0 => {
                f.hour = value;
                f.ampm = -1;
            }
            1 => f.minute = value,
            _ => f.second = value,
        }
    } else {
        f.set_clock(flag, value)?;
    }
    if let Some(p) = split {
        let mut numerator = 0_u128;
        let mut denominator = 1_u128;
        for &ch in &t[p + 1..] {
            numerator = numerator
                .checked_mul(10)
                .and_then(|v| v.checked_add(u128::from(ch - 48)))
                .ok_or_else(|| {
                    ParseError::Overflow("decimal clock precision exceeds native arithmetic".into())
                })?;
            denominator = denominator.checked_mul(10).ok_or_else(|| {
                ParseError::Overflow("decimal clock precision exceeds native arithmetic".into())
            })?;
        }
        let factor = if flag == 0 {
            3_600_000_000_000
        } else {
            60_000_000_000
        };
        let nanos = numerator
            .checked_mul(factor)
            .ok_or_else(|| ParseError::Overflow("decimal clock arithmetic overflow".into()))?
            / denominator;
        if flag == 0 {
            f.set_clock(1, (nanos / 60_000_000_000) as i32)?;
        }
        f.set_clock(2, (nanos / 1_000_000_000 % 60) as i32)?;
        let fraction = nanos % 1_000_000_000;
        f.set_fraction(
            (fraction / 1000) as i32,
            if P::Fraction::NANO {
                (fraction % 1000) as i32
            } else {
                0
            },
            P::Fraction::NANO && fraction % 1000 != 0,
        )?;
    }
    Ok(true)
}
fn set_ymd<P: Policy>(
    f: &mut Fields<P>,
    q: &mut impl RuleLookup,
    flag: i32,
    t: &[u32],
) -> ParseResult<bool> {
    match kind(t) {
        1 => f.set_ymd_str(flag, t),
        2 => Ok(false),
        _ => {
            if t.is_empty() {
                return Ok(false);
            }
            let m = q.query(Rule::Month, t)?;
            if m != -1 && q.query(Rule::Jump, t)? == 0 {
                f.set_ymd_int(2, m as i64)
            } else {
                Ok(false)
            }
        }
    }
}
fn tok(ts: &Tokens, i: usize, off: isize) -> &[u32] {
    i.checked_add_signed(off)
        .and_then(|j| ts.get(j))
        .unwrap_or(&[])
}
fn query(q: &mut impl RuleLookup, r: Rule, t: &[u32], missing: i32) -> ParseResult<i32> {
    if t.is_empty() {
        Ok(missing)
    } else {
        q.query(r, t)
    }
}

/// Commit a complete named date before its numbers acquire clock/ordinal roles.
fn complete_named_calendar<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    q: &mut impl RuleLookup,
    leading_month: Option<i32>,
) -> ParseResult<bool> {
    if leading_month.is_none() && matches!(tok(ts, *i, 0).len(), 6 | 7 | 8 | 10 | 12 | 14) {
        // A compact calendar/clock remains its own field, not a long year
        // belonging to the named date that follows it.
        return Ok(false);
    }
    if leading_month.is_some() && matches!(f.ymd_slots_filled(), 1 | 2) {
        // An earlier day/year may be waiting for this month and a year.
        // Do not steal its following clock to create another calendar.
        return Ok(false);
    }
    if !(ctl(tok(ts, *i, 1)) || dsep(tok(ts, *i, 1))) {
        return Ok(false);
    }
    let separator = tok(ts, *i, 3);
    let end = if ctl(separator) || dsep(separator) {
        4
    } else if one(separator, 44) && query(q, Rule::Jump, separator, 0)? != 0 {
        if ctl(tok(ts, *i, 4)) { 5 } else { 4 }
    } else {
        return Ok(false);
    };
    let parts = [tok(ts, *i, 0), tok(ts, *i, 2), tok(ts, *i, end)];
    if parts[2].is_empty() {
        return Ok(false);
    }
    let (month, month_index, number_indices) = if let Some(month) = leading_month {
        if kind(parts[1]) != 1 || kind(parts[2]) != 1 {
            return Ok(false);
        }
        (month, 0, [1, 2])
    } else {
        let middle = kind(parts[1]);
        let last = kind(parts[2]);
        let month_index = if middle == 0 && last == 1 {
            1
        } else if middle == 1 && last == 0 {
            2
        } else {
            return Ok(false);
        };
        let month = query(q, Rule::Month, parts[month_index], -1)?;
        if month == -1 {
            return Ok(false);
        }
        (
            month,
            month_index,
            if month_index == 1 { [0, 2] } else { [0, 1] },
        )
    };
    let [a, b] = number_indices.map(|index| parts[index]);
    // A written long year fixes the other number as a day, including zeroes
    // and out-of-range days. Ambiguous short years retain normal resolution.
    let year_slot = if (a.len() >= 4 && b.len() < 4) || (a.len() > 2 && b.len() <= 2) {
        0
    } else if (b.len() >= 4 && a.len() < 4) || (b.len() > 2 && a.len() <= 2) {
        1
    } else if a.len() > 2 && b.len() > 2 {
        match (uint(a)? > 31, uint(b)? > 31) {
            (true, false) => 0,
            (false, true) => 1,
            _ => return Ok(false),
        }
    } else {
        return Ok(false);
    };
    if month_index == 2 && number_indices[year_slot] == 0 && parts[1].len() == 3 && !dsep(separator)
    {
        // "2024-014 Feb" is an ordinal followed by a separate month selection.
        return Ok(false);
    }
    let numbers = [a, b];
    let day_offset = [0, 2, end][number_indices[1 - year_slot]];
    if one(tok(ts, *i, day_offset + 1), 58) {
        return Ok(false);
    }
    let year = f.year_value(uint(numbers[year_slot])?)?;
    let day = f.bounded("day", uint(numbers[1 - year_slot])?, 1, 31)?;
    f.replace_calendar([year, month, day], 0);
    f.midx = 1;
    f.didx = 2;
    *i += end as usize;
    Ok(true)
}

/// Recognize a complete ISO week/ordinal group before compact-number guesses.
#[inline]
fn explicit_iso_calendar<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    reference_year: Option<i32>,
) -> ParseResult<bool> {
    let separator = tok(ts, *i, 1);
    let separated = dsep(separator) || ctl(separator);
    let marker_offset = if separated { 2 } else { 1 };
    let marker = tok(ts, *i, marker_offset);
    let week = marker.len() == 1 && week_sep(marker[0]);
    let ordinal = separated && marker.len() == 3 && kind(marker) == 1 && !dsep(tok(ts, *i, 3));
    if !week && !ordinal {
        return Ok(false);
    }
    if week {
        let number = tok(ts, *i, marker_offset + 1);
        // W is also a legal configured word. A missing week-number shape is
        // not an ISO year and must not trigger year completion or mutation.
        if !(2..=3).contains(&number.len()) || kind(number) != 1 {
            return Ok(false);
        }
    }
    resolve_iso_calendar(ts, i, f, reference_year, marker_offset, week)
}

/// Convert a proven week/ordinal shape without enlarging normal numeric scans.
#[inline(never)]
fn resolve_iso_calendar<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    reference_year: Option<i32>,
    marker_offset: isize,
    week: bool,
) -> ParseResult<bool> {
    let year_token = tok(ts, *i, 0);
    let marker = tok(ts, *i, marker_offset);
    let raw_year = f.year_value(uint(year_token)?)?;
    let year =
        super::resolve::complete_year(raw_year, year_token.len() > 2, f.strict(), reference_year)?;
    let (year, month, day, advance) = if week {
        let token = tok(ts, *i, marker_offset + 1);
        let number = iso_week_number(f, year, fixed(token, 0, 2, 0, 99))?;
        let mut weekday = if token.len() == 3 {
            fixed(token, 2, 1, 0, 9)
        } else {
            1
        };
        let mut advance = marker_offset + 1;
        if dsep(tok(ts, *i, advance + 1)) && kind(tok(ts, *i, advance + 2)) == 1 {
            weekday = f.bounded("ISO weekday", uint(tok(ts, *i, advance + 2))?, 1, 7)?;
            advance += 2;
        }
        let weekday = f.bounded("ISO weekday", i64::from(weekday), 1, 7)?;
        let (year, month, day) = week_date(year, number, weekday);
        (year, month, day, advance)
    } else {
        let raw = i32::try_from(uint(marker)?)
            .map_err(|_| ParseError::Overflow("day-of-year overflow".into()))?;
        let day = ordinal_day(f, year, raw)?;
        let (year, month, day) = doy_date(year, day);
        (year, month, day, 2)
    };
    f.replace_calendar([year, month, day], 0);
    f.midx = 1;
    f.didx = 2;
    *i += advance as usize;
    Ok(true)
}

/// Read a proven integer hour followed by a colon using shared clock rules.
#[inline]
fn colon_clock<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    hour: &[u32],
) -> ParseResult<bool> {
    if !hms_known(f, 0, hour, 1)? {
        return Ok(false);
    }
    if !hms(f, 1, tok(ts, *i, 2))? {
        *i += 1;
    } else if !one(tok(ts, *i, 3), 58) || !hms(f, 2, tok(ts, *i, 4))? {
        *i += 2;
    } else {
        *i += 4;
    }
    Ok(true)
}

fn numeric<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    q: &mut impl RuleLookup,
    reference_year: Option<i32>,
    k: i32,
) -> ParseResult<bool> {
    let t = tok(ts, *i, 0);
    if k == 0 {
        return Ok(false);
    }
    let n = t.len();
    // A following colon fixes the full token as an hour before any compact
    // calendar/clock guess; leading zeroes do not change that role.
    if k == 1 && one(tok(ts, *i, 1), 58) {
        return colon_clock(ts, i, f, t);
    }
    // An explicit clock unit fixes the role before compact-date heuristics.
    if n >= 6 {
        let unit_offset = if ctl(tok(ts, *i, 1)) { 2 } else { 1 };
        let clock_unit = query(q, Rule::Hms, tok(ts, *i, unit_offset), -1)?;
        if clock_unit != -1 {
            hms_known(f, clock_unit, t, k)?;
            *i += unit_offset as usize;
            return Ok(true);
        }
    }
    // Every integer followed by ':' already returned above. Do not reread
    // that token after the unit lookup on the remaining numeric path.
    if k == 1 && explicit_iso_calendar(ts, i, f, reference_year)? {
        return Ok(true);
    }
    if k == 1 && dsep(tok(ts, *i, 1)) && dsep(tok(ts, *i, 3)) && (n > 2 || tok(ts, *i, 4).len() > 2)
    {
        let second = tok(ts, *i, 2);
        let third = tok(ts, *i, 4);
        let short = second.len() <= 4 && third.len() <= 4;
        let values = if short {
            small_calendar_number(second).and_then(|b| small_calendar_number(third).map(|c| (b, c)))
        } else {
            None
        };
        let integers = if short {
            values.is_some()
        } else {
            kind(second) == 1 && kind(third) == 1
        };
        if integers {
            let a = uint(t)?;
            // Long tokens retain the original a, b, c conversion/error order.
            let (b, c) = match values {
                Some(values) => values,
                None => (uint(second)?, uint(third)?),
            };
            let year_index = if n > 2 { 0 } else { 2 };
            let mut values = [a, b, c];
            values[year_index] = i64::from(f.year_value(values[year_index])?);
            let mut calendar = [0; 3];
            for (slot, value) in calendar.iter_mut().zip(values) {
                *slot = i32::try_from(value).map_err(|_| {
                    ParseError::Overflow("integer overflow parsing calendar field".into())
                })?;
            }
            f.replace_calendar(calendar, year_index as i32);
            *i += 4;
            return Ok(true);
        }
    }
    // Proven colon/ISO/numeric calendars already returned. Resolve a complete
    // named calendar before the remaining compact-clock and year guesses.
    if k == 1 && complete_named_calendar(ts, i, f, q, None)? {
        return Ok(true);
    }
    if k == 1 {
        if matches!(n, 2 | 4)
            && (n == 4 || f.hour < 0)
            && (f.ymd_slots_filled() == 3 || (f.is_year_set() && f.doy > 0))
            && (tok(ts, *i, 1).is_empty()
                || (!one(tok(ts, *i, 1), 58) && q.query(Rule::HmsContains, tok(ts, *i, 1))? == 0))
        {
            f.set_clock(0, fixed(t, 0, 2, 0, 99))?;
            if n == 4 {
                f.set_clock(1, fixed(t, 2, 2, 0, 99))?;
            }
            return Ok(true);
        }
        if n == 7 && f.ymd_slots_filled() == 0 {
            let year = f.year_value(i64::from(fixed(t, 0, 4, 0, 9999)))?;
            let day = ordinal_day(f, year, fixed(t, 4, 3, 0, 999))?;
            let (year, month, day) = doy_date(year, day);
            f.century_specified = true;
            f.set_ymd_int(1, i64::from(year))?;
            f.set_ymd_int(2, i64::from(month))?;
            f.set_ymd_int(3, i64::from(day))?;
            return Ok(true);
        }
        if n == 6 {
            if f.ymd_slots_filled() == 0 {
                for p in [0, 2, 4] {
                    f.set_ymd_int(0, fixed(t, p, 2, 0, 99) as i64)?;
                }
            } else {
                // kind == 1 has already checked every digit. Keep field range
                // and repeated-field rules in the existing policy setters.
                f.set_clock(0, clock_pair(t, 0))?;
                f.set_clock(1, clock_pair(t, 2))?;
                f.set_second(clock_pair(t, 4), 0, 0, false)?;
            }
            return Ok(true);
        }
        if matches!(n, 8 | 10 | 12 | 14) {
            let year = f.year_value(i64::from(fixed(t, 0, 4, 0, 9999)))?;
            f.replace_calendar([year, fixed(t, 4, 2, 0, 99), fixed(t, 6, 2, 0, 99)], 0);
            f.midx = 1;
            f.didx = 2;
            if n > 8 {
                f.set_clock(0, fixed(t, 8, 2, 0, 99))?;
            }
            if n > 10 {
                f.set_clock(1, fixed(t, 10, 2, 0, 99))?;
            }
            if n > 12 {
                f.set_second(fixed(t, 12, 2, 0, 99), 0, 0, false)?;
            }
            return Ok(true);
        }
        if one(tok(ts, *i, 1), 58) {
            return colon_clock(ts, i, f, t);
        }
        if dsep(tok(ts, *i, 1)) && set_ymd(f, q, 0, t)? {
            if !set_ymd(f, q, 0, tok(ts, *i, 2))? {
                *i += 1;
                return Ok(true);
            }
            if !dsep(tok(ts, *i, 3)) || !set_ymd(f, q, 0, tok(ts, *i, 4))? {
                *i += 2;
            } else {
                *i += 4;
            }
            return Ok(true);
        }
    } else if n > 6 && t[6] == 46 {
        f.set_clock(0, fixed(t, 0, 2, 0, 99))?;
        f.set_clock(1, fixed(t, 2, 2, 0, 99))?;
        let (us, tail, nanos) = if n > 7 {
            fraction::<P>(&t[7..])
        } else {
            (0, 0, false)
        };
        f.set_second(fixed(t, 4, 2, 0, 99), us, tail, nanos)?;
        return Ok(true);
    }
    // A four-digit year completing an existing month/day remains a year,
    // even when the next skip word also happens to be an AM/PM alias.
    if k == 1
        && n == 4
        && !f.is_year_set()
        && f.ymd_slots_filled() == 2
        && !one(tok(ts, *i, 1), 58)
        && query(q, Rule::Hms, tok(ts, *i, 1), -1)? == -1
    {
        f.century_specified = true;
        f.set_ymd_int(1, uint(t)?)?;
        return Ok(true);
    }
    let flag = query(q, Rule::Hms, tok(ts, *i, 1), -1)?;
    if flag != -1 && hms_known(f, flag, t, k)? {
        *i += 1;
        return Ok(true);
    }
    let flag = query(q, Rule::Ampm, tok(ts, *i, 1), -1)?;
    if flag != -1 && hms_known(f, 0, t, k)? {
        f.apply_ampm(flag)?;
        *i += 1;
        return Ok(true);
    }
    let flag = query(q, Rule::Hms, tok(ts, *i, -1), -1)?;
    if matches!(flag, 0 | 1) && hms_known(f, flag + 1, t, k)? {
        return Ok(true);
    }
    if tok(ts, *i, 1).is_empty() || query(q, Rule::Jump, tok(ts, *i, 1), 0)? != 0 {
        let flag = q.query(Rule::Ampm, tok(ts, *i, 2))?;
        if flag != -1 {
            if hms_known(f, 0, t, k)? {
                f.apply_ampm(flag)?;
                *i += 2;
                return Ok(true);
            }
        } else if set_ymd(f, q, 0, t)? {
            *i += 1;
            return Ok(true);
        }
    }
    if k == 1 {
        if n <= 3 {
            let v = uint(t)?;
            if f.could_be_day(v) || f.could_be_doy(v) {
                f.set_ymd_int(0, v)?;
                return Ok(true);
            }
        }
        if n == 4 && !f.is_year_set() {
            f.century_specified = true;
            f.set_ymd_int(1, uint(t)?)?;
        }
    }
    Ok(true)
}
fn month<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    q: &mut impl RuleLookup,
) -> ParseResult<bool> {
    let m = q.query(Rule::Month, tok(ts, *i, 0))?;
    if m == -1 {
        return Ok(false);
    }
    let next_day = tok(ts, *i, 2);
    let next_year = tok(ts, *i, 4);
    let separator = |token: &[u32]| ctl(token) || dsep(token);
    // A complete named date needs no numeric-role guessing. Only skip a comma
    // whose configured role is actually Jump; other punctuation meanings stay
    // at their original token position. Invalid/partial fields retain fallback.
    if f.ymd_slots_filled() == 0
        && separator(tok(ts, *i, 1))
        && next_day.len() <= 2
        && one(tok(ts, *i, 3), 44)
        && q.query(Rule::Jump, tok(ts, *i, 3))? != 0
    {
        let year_offset = if ctl(next_year) { 5 } else { 4 };
        let year_token = tok(ts, *i, year_offset);
        if year_token.len() == 4
            && let Some(day) = small_calendar_number(next_day)
            && (1..=31).contains(&day)
            && let Some(year) = small_calendar_number(year_token)
            && year > 0
        {
            f.replace_calendar([year as i32, m, day as i32], 0);
            f.midx = 1;
            f.didx = 2;
            *i += year_offset as usize;
            return Ok(true);
        }
    }
    // A year already written before this month completes the date here.
    // Do not steal a following HHMM/HHMMSS as a replacement year.
    if f.ymd_slots_filled() == 1
        && f.is_year_set()
        && !f.is_month_set()
        && !f.is_day_set()
        && separator(tok(ts, *i, 1))
        && next_day.len() <= 2
        && kind(next_day) == 1
    {
        f.set_ymd_int(2, i64::from(m))?;
        f.set_ymd_int(3, uint(next_day)?)?;
        *i += 2;
        return Ok(true);
    }
    if complete_named_calendar(ts, i, f, q, Some(m))? {
        return Ok(true);
    }
    if separator(tok(ts, *i, 1))
        && separator(tok(ts, *i, 3))
        && next_day.len() <= 2
        && next_year.len() >= 3
        && kind(next_day) == 1
        && kind(next_year) == 1
    {
        let year = f.year_value(uint(next_year)?)?;
        let day = f.bounded("day", uint(next_day)?, 1, 31)?;
        f.replace_calendar([year, m, day], 0);
        f.midx = 1;
        f.didx = 2;
        *i += 4;
        return Ok(true);
    }
    let previous_day = tok(ts, *i, -2);
    if *i >= 2
        && previous_day.len() <= 2
        && next_day.len() >= 3
        && separator(tok(ts, *i, -1))
        && separator(tok(ts, *i, 1))
        && kind(previous_day) == 1
        && kind(next_day) == 1
    {
        let year = f.year_value(uint(next_day)?)?;
        let day = f.bounded("day", uint(previous_day)?, 1, 31)?;
        f.replace_calendar([year, m, day], 0);
        f.midx = 1;
        f.didx = 2;
        *i += 2;
        return Ok(true);
    }
    if f.ymd_slots_filled() == 3 {
        // A standalone repeated month needs an adjacent recognized field.
        // Do not turn a translated month word in trailing prose ("man on Mars")
        // into a replacement for the already complete date.
        let mut previous = *i;
        while previous > 0 {
            previous -= 1;
            let token = tok(ts, previous, 0);
            if separator(token) || q.query(Rule::Jump, token)? != 0 {
                continue;
            }
            let recognized = matches!(kind(token), 1 | 2)
                || q.query(Rule::Month, token)? != -1
                || q.query(Rule::Weekday, token)? != -1
                || q.query(Rule::Hms, token)? != -1
                || q.query(Rule::Ampm, token)? != -1
                || q.query(Rule::Utc, token)? != 0
                || q.query(Rule::Tz, token)? != -100_000;
            if !recognized {
                return Ok(false);
            }
            break;
        }
        if f.resolved {
            let previous = f.month;
            if f.strict() && previous != m {
                return Err(Fields::<P>::conflict("month", previous, m));
            }
            if f.midx >= 0 {
                f.ymd[f.midx as usize] = m;
            }
            f.month = m;
        } else {
            // Resolve ambiguous numeric month/day order at its original stage;
            // only then compare or replace this explicit month selection.
            if f.strict() && f.month_override != -1 && f.month_override != m {
                return Err(Fields::<P>::conflict("month", f.month_override, m));
            }
            f.month_override = m;
        }
        return Ok(true);
    }
    if f.is_month_set() {
        return Ok(false);
    }
    if !f.set_ymd_int(2, m as i64)? {
        return Ok(true);
    }
    if tok(ts, *i, 2).is_empty() {
        return Ok(true);
    }
    if dsep(tok(ts, *i, 1)) {
        if !set_ymd(f, q, 0, tok(ts, *i, 2))? {
            return Ok(true);
        }
        if !dsep(tok(ts, *i, 3)) || !set_ymd(f, q, 0, tok(ts, *i, 4))? {
            *i += 2;
        } else {
            *i += 4;
        }
        return Ok(true);
    }
    if one(tok(ts, *i, 1), 44) && ctl(tok(ts, *i, 2)) && set_ymd(f, q, 1, tok(ts, *i, 3))? {
        *i += 3;
        return Ok(true);
    }
    if ctl(tok(ts, *i, 1))
        && ctl(tok(ts, *i, 3))
        && query(q, Rule::Pertain, tok(ts, *i, 2), 0)? != 0
        && set_ymd(f, q, 1, tok(ts, *i, 4))?
    {
        *i += 4;
    }
    Ok(true)
}
fn iso_week<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    reference_year: Option<i32>,
) -> ParseResult<bool> {
    let t = tok(ts, *i, 0);
    if !f.is_year_set() || f.is_month_set() || f.is_day_set() || t.len() != 1 || !week_sep(t[0]) {
        return Ok(false);
    }
    let next = tok(ts, *i, 1);
    if !(2..=3).contains(&next.len()) {
        return Ok(false);
    }
    if next == [48, 48] {
        return Err(ParseError::Value("ISO week must be at least 1".into()));
    }
    let w = fixed(next, 0, 2, 1, 99);
    if w == -1 {
        // Preserve the grammar's treatment of an unrecognized week number;
        // its digits must not become another calendar year or day-of-year.
        *i += 1;
        if next != [48, 48] && dsep(tok(ts, *i, 1)) && kind(tok(ts, *i, 2)) == 1 {
            *i += 2;
        }
        return Ok(true);
    }
    let mut wd = if next.len() == 3 {
        fixed(next, 2, 1, 0, 9)
    } else {
        1
    };
    if wd == 0 {
        return Err(ParseError::Value("ISO weekday must be at least 1".into()));
    }
    let third = tok(ts, *i, 3);
    if third.len() == 1 && dsep(tok(ts, *i, 2)) {
        if third == [48] {
            return Err(ParseError::Value("ISO weekday must be at least 1".into()));
        }
        let v = fixed(third, 0, 1, 1, 9);
        if v > 0 {
            wd = v;
            *i += 2;
        }
    }
    let year = if f.yidx >= 0 {
        f.ymd[f.yidx as usize]
    } else {
        f.year
    };
    let year =
        super::resolve::complete_year(year, f.century_specified, f.strict(), reference_year)?;
    let w = iso_week_number(f, year, w)?;
    let wd = f.bounded("ISO weekday", i64::from(wd), 1, 7)?;
    let (calendar_year, m, d) = week_date(year, w, wd);
    if f.yidx >= 0 {
        f.ymd[f.yidx as usize] = calendar_year;
    }
    f.year = calendar_year;
    f.century_specified = true;
    f.set_ymd_int(2, m as i64)?;
    f.set_ymd_int(3, d as i64)?;
    *i += 1;
    Ok(true)
}
fn weekday<P: Policy>(t: &[u32], f: &mut Fields<P>, q: &mut impl RuleLookup) -> ParseResult<bool> {
    let w = q.query(Rule::Weekday, t)?;
    if w == -1 {
        return Ok(false);
    }
    if f.strict() && f.weekday != -1 && f.weekday != w {
        return Err(Fields::<P>::conflict("weekday", f.weekday, w));
    }
    f.weekday = w;
    Ok(true)
}
fn ampm<P: Policy>(
    ts: &Tokens,
    index: usize,
    f: &mut Fields<P>,
    q: &mut impl RuleLookup,
) -> ParseResult<bool> {
    let t = tok(ts, index, 0);
    if f.ampm != -1 {
        let offset = if ctl(tok(ts, index, -1)) { -2 } else { -1 };
        if query(q, Rule::Ampm, tok(ts, index, offset), -1)? == -1 {
            return Ok(false);
        }
    }
    if f.hour < 0 {
        return Ok(false);
    }
    let a = q.query(Rule::Ampm, t)?;
    if a == -1 {
        return Ok(false);
    }
    f.apply_ampm(a)?;
    Ok(true)
}
fn tzoffset<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    ignore: bool,
    override_sign: Option<i32>,
) -> ParseResult<bool> {
    let sign = match override_sign {
        Some(sign) => sign,
        None if one(tok(ts, *i, 0), 43) => 1,
        None if one(tok(ts, *i, 0), 45) => -1,
        _ => return Ok(false),
    };
    let next = tok(ts, *i, 1);
    let next_kind = kind(next);
    if next_kind == 0 {
        return Ok(false);
    }
    let split = next.iter().position(|&ch| ch == 46);
    let whole = &next[..split.unwrap_or(next.len())];
    // A decimal compact offset gives its fraction to the seconds field.
    // Do not reinterpret an arbitrary fractional hour or minute as this form.
    if next_kind == 2 && whole.len() != 6 {
        return Ok(false);
    }
    let mut seconds = 0;
    let mut microsecond = 0;
    let (h, m, mut advance) = if whole.len() == 6 {
        seconds = fixed(whole, 4, 2, 0, 99);
        if let Some(split) = split {
            (microsecond, _, _) = fraction::<super::fields::Lenient>(&next[split + 1..]);
        }
        (fixed(whole, 0, 2, 0, 99), fixed(whole, 2, 2, 0, 99), 1)
    } else if next.len() == 4 {
        (fixed(next, 0, 2, 0, 99), fixed(next, 2, 2, 0, 99), 1)
    } else if (1..=2).contains(&next.len()) {
        let h = uint(next)? as i32;
        let third = tok(ts, *i, 3);
        if one(tok(ts, *i, 2), 58) && !third.is_empty() && kind(third) == 1 {
            (
                h,
                i32::try_from(uint(third)?)
                    .map_err(|_| ParseError::Overflow("timezone minute overflow".into()))?,
                3,
            )
        } else {
            (h, 0, 1)
        }
    } else {
        return Ok(false);
    };
    if one(tok(ts, *i, advance + 1), 58) {
        let token = tok(ts, *i, advance + 2);
        if kind(token) != 0 {
            let split = token.iter().position(|&ch| ch == 46);
            let whole = &token[..split.unwrap_or(token.len())];
            seconds = i32::try_from(uint(whole)?)
                .map_err(|_| ParseError::Overflow("timezone second overflow".into()))?;
            if let Some(split) = split {
                (microsecond, _, _) = fraction::<super::fields::Lenient>(&token[split + 1..]);
            }
            advance += 2;
        }
    }
    *i += advance as usize;
    if !ignore {
        let hour = f.bounded("timezone hour", i64::from(h), 0, 23)?;
        let minute = f.bounded("timezone minute", i64::from(m), 0, 59)?;
        let second = f.bounded("timezone second", i64::from(seconds), 0, 59)?;
        f.numeric_timezone_parts(
            sign * (hour * 3600 + minute * 60 + second),
            sign * microsecond,
        )?;
    }
    Ok(true)
}
fn tzname<P: Policy>(
    ts: &Tokens,
    i: &mut usize,
    f: &mut Fields<P>,
    q: &mut impl RuleLookup,
    ignore: bool,
) -> ParseResult<bool> {
    if ignore || (f.tzoffset != -100_000 && one(tok(ts, *i, -1), 40)) {
        return Ok(false);
    }
    let t = tok(ts, *i, 0);
    let utc = q.query(Rule::Utc, t)? != 0;
    if utc {
        f.begin_timezone(0)?;
    } else {
        if !t.iter().all(|&c| ascii_letter(c)) {
            return Ok(false);
        }
        let off = q.query(Rule::Tz, t)?;
        if off == -100000 {
            return Ok(false);
        }
        f.begin_timezone(off)?;
    }
    if utc {
        let t2 = tok(ts, *i, 2);
        let end = t2.iter().position(|&ch| ch == 46).unwrap_or(t2.len());
        if (matches!(t2.len(), 1 | 2 | 4 | 6) && kind(t2) == 1) || (end == 6 && kind(t2) == 2) {
            let sign = if one(tok(ts, *i, 1), 43) {
                Some(-1)
            } else if one(tok(ts, *i, 1), 45) {
                Some(1)
            } else {
                None
            };
            if sign.is_some() {
                *i += 1;
                return tzoffset(ts, i, f, ignore, sign);
            }
        }
    }
    f.tzoffset_finalized = false;
    Ok(true)
}
/// Read the configuration-independent prefix before selecting a rule adapter.
pub(super) fn prefix<P: Policy>(
    input: &impl CharacterRead,
    fields: &mut Fields<P>,
    ignoretz: bool,
    isoformat: bool,
) -> ParseResult<(usize, bool)> {
    if isoformat {
        match iso_date(input, fields)? {
            Some(p) => iso_time(input, p, fields, ignoretz),
            None => Ok((0, false)),
        }
    } else {
        Ok((0, false))
    }
}

pub(super) fn process_tokens<P: Policy>(
    tokens: &Tokens,
    fields: &mut Fields<P>,
    lookup: &mut impl RuleLookup,
    ignoretz: bool,
    reference_year: Option<i32>,
) -> ParseResult<()> {
    let mut i = 0;
    while i < tokens.len() {
        if !ctl(tok(tokens, i, 0)) {
            let current = tok(tokens, i, 0);
            // One numeric reader selects explicit calendar and clock roles
            // with or without an ISO prefix.
            let numeric_kind = kind(current);
            let handled = numeric(tokens, &mut i, fields, lookup, reference_year, numeric_kind)?
                || month(tokens, &mut i, fields, lookup)?
                || iso_week(tokens, &mut i, fields, reference_year)?
                || weekday(tok(tokens, i, 0), fields, lookup)?
                || ampm(tokens, i, fields, lookup)?
                || tzname(tokens, &mut i, fields, lookup, ignoretz)?;
            if !handled {
                tzoffset(tokens, &mut i, fields, ignoretz, None)?;
            }
        }
        i += 1;
    }
    fields.finish_hour()?;
    fields.finish_timezone()?;
    Ok(())
}
