//! Dedicated ISO factory grammar; ordinary text parsing retains its own policy.
//! No Python date carrier is needed to retain zero/wide years or nanoseconds.
use crate::epoch::{Parsed, Unit, Zone};
use pyo3::prelude::*;

#[derive(Debug)]
pub(crate) enum Error {
    Invalid,
    Overflow(&'static str),
}
impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Invalid => f.write_str(
                "expected a complete ISO date/time with valid calendar and clock fields",
            ),
            Self::Overflow(message) => f.write_str(message),
        }
    }
}
pub(crate) struct NativeParsed {
    pub(crate) nanos: i128,
    pub(crate) unit: Unit,
    pub(crate) offset: Option<i64>,
}
fn invalid() -> Error {
    Error::Invalid
}

fn digits(input: &[u8], position: &mut usize, count: usize) -> Result<i64, Error> {
    let end = position.checked_add(count).ok_or_else(invalid)?;
    let bytes = input.get(*position..end).ok_or_else(invalid)?;
    let mut value = 0_i64;
    for &digit in bytes {
        if !digit.is_ascii_digit() {
            return Err(invalid());
        }
        value = value
            .checked_mul(10)
            .and_then(|v| v.checked_add(i64::from(digit - b'0')))
            .ok_or(Error::Overflow("ISO year exceeds native integer range"))?;
    }
    *position = end;
    Ok(value)
}

/// Read every fractional digit, retaining only the target's meaningful prefix.
fn fraction(input: &[u8], position: &mut usize, precision: usize) -> Result<(i64, usize), Error> {
    *position += 1;
    let start = *position;
    let mut value = 0;
    while input.get(*position).is_some_and(u8::is_ascii_digit) {
        if *position - start < precision {
            value = value * 10 + i64::from(input[*position] - b'0');
        }
        *position += 1;
    }
    let count = *position - start;
    if count == 0 {
        return Err(invalid());
    }
    value *= 10_i64.pow((precision - count.min(precision)) as u32);
    Ok((value, count))
}

fn clock(input: &[u8], position: &mut usize) -> Result<(i64, i64, i64), Error> {
    let hour = digits(input, position, 2)?;
    let mut minute = 0;
    let mut second = 0;
    if input.get(*position) == Some(&b':') {
        *position += 1;
        minute = digits(input, position, 2)?;
        if input.get(*position) == Some(&b':') {
            *position += 1;
            second = digits(input, position, 2)?;
        }
    } else if input.get(*position).is_some_and(u8::is_ascii_digit) {
        minute = digits(input, position, 2)?;
        if input.get(*position).is_some_and(u8::is_ascii_digit) {
            second = digits(input, position, 2)?;
        }
    }
    if hour > 23 || minute > 59 || second > 59 {
        return Err(invalid());
    }
    Ok((hour, minute, second))
}

/// Decode one complete ISO factory value into local native fields and timezone.
pub(crate) fn read_native(text: &str) -> Result<NativeParsed, Error> {
    let input = text.as_bytes();
    let run = input.iter().take_while(|v| v.is_ascii_digit()).count();
    let width = if run >= 4 && input.get(run) == Some(&b'-') {
        run
    } else {
        4
    };
    if run < 4 {
        return Err(invalid());
    }
    let mut position = 0;
    let year = digits(input, &mut position, width)?;
    let dashed = input.get(position) == Some(&b'-');
    if dashed {
        position += 1;
    }
    let ordinal = if matches!(input.get(position), Some(b'W' | b'w')) {
        position += 1;
        let week = digits(input, &mut position, 2)?;
        let weekday = if input.get(position) == Some(&b'-') {
            position += 1;
            digits(input, &mut position, 1)?
        } else if input.get(position).is_some_and(u8::is_ascii_digit) {
            digits(input, &mut position, 1)?
        } else {
            1
        };
        let jan1 = crate::calendar::checked_ordinal(year, 1, 1).map_err(Error::Overflow)?;
        let wd = (jan1 - 1).rem_euclid(7);
        let last = 52 + i64::from(wd == 3 || (wd == 2 && crate::calendar::leap(year)));
        if !(1..=last).contains(&week) || !(1..=7).contains(&weekday) {
            return Err(invalid());
        }
        crate::calendar::iso_ordinal(year, week, weekday).map_err(Error::Overflow)?
    } else {
        let remaining = input[position..]
            .iter()
            .take_while(|v| v.is_ascii_digit())
            .count();
        if (dashed && input.get(position + 2) != Some(&b'-') && remaining == 3)
            || (!dashed && remaining == 3)
        {
            let day = digits(input, &mut position, 3)?;
            if !(1..=365 + i64::from(crate::calendar::leap(year))).contains(&day) {
                return Err(invalid());
            }
            crate::calendar::year_day_ordinal(year, day).map_err(Error::Overflow)?
        } else {
            let month = digits(input, &mut position, 2)?;
            if dashed {
                if input.get(position) != Some(&b'-') {
                    return Err(invalid());
                }
                position += 1;
            }
            let day = digits(input, &mut position, 2)?;
            if !(1..=12).contains(&month)
                || !(1..=crate::calendar::days_in_month(year, month)).contains(&day)
            {
                return Err(invalid());
            }
            crate::calendar::checked_ordinal(year, month, day).map_err(Error::Overflow)?
        }
    };
    let mut nanos = (i128::from(ordinal) - 719_163) * 86_400_000_000_000;
    let mut unit = Unit::Microsecond;
    let mut offset = None;
    if position < input.len() {
        let separator = text[position..].chars().next().ok_or_else(invalid)?;
        position += separator.len_utf8();
        let (h, m, s) = clock(input, &mut position)?;
        nanos += ((i128::from(h) * 60 + i128::from(m)) * 60 + i128::from(s)) * 1_000_000_000;
        if matches!(input.get(position), Some(b'.' | b',')) {
            let (part, count) = fraction(input, &mut position, 9)?;
            nanos += i128::from(part);
            if count > 6 {
                unit = Unit::Nanosecond;
            }
        }
        match input.get(position) {
            Some(b'Z' | b'z') => {
                position += 1;
                offset = Some(0);
            }
            Some(b'+' | b'-') => {
                let negative = input[position] == b'-';
                position += 1;
                let (h, m, s) = clock(input, &mut position)?;
                let mut value = ((h * 60 + m) * 60 + s) * 1_000_000;
                if matches!(input.get(position), Some(b'.' | b',')) {
                    value += fraction(input, &mut position, 6)?.0;
                }
                if negative {
                    value = -value;
                }
                offset = Some(value);
            }
            _ => {}
        }
    }
    if position != input.len() {
        return Err(invalid());
    }
    Ok(NativeParsed {
        nanos,
        unit,
        offset,
    })
}

/// Existing scalar adapter preserves its original error and timezone contracts.
pub(crate) fn read(text: &str) -> PyResult<Parsed> {
    let parsed = read_native(text).map_err(|error| match error {
        Error::Invalid => crate::error_context::value_error(error.to_string()),
        Error::Overflow(message) => crate::error_context::overflow(message),
    })?;
    Ok(Parsed {
        nanos: parsed.nanos,
        unit: parsed.unit,
        zone: parsed.offset.map_or(Zone::Naive, Zone::Offset),
    })
}

#[cfg(test)]
mod native_tests {
    use super::*;
    #[test]
    fn strict_iso_and_source_width_run_without_python_on_a_worker() {
        std::thread::spawn(|| {
            let p = read_native("2024-01-02T00:00:00.000000001+00:00")
                .unwrap_or_else(|error| panic!("{error}"));
            assert_eq!(p.nanos, 1_704_153_600_000_000_001);
            assert_eq!(p.offset, Some(0));
            assert_eq!(p.unit, Unit::Nanosecond);
            let p = read_native("0000-01-01").unwrap_or_else(|error| panic!("{error}"));
            assert_eq!(p.nanos, -62_167_219_200_000_000_000);
            let p = read_native("2024-01-02🕓12:30").unwrap_or_else(|error| panic!("{error}"));
            assert_eq!(p.nanos / 1_000_000_000, 1_704_198_600);
            let p = read_native("2024-01-02T00:00:00.123456789999")
                .unwrap_or_else(|error| panic!("{error}"));
            assert_eq!(p.nanos.rem_euclid(1_000_000_000), 123_456_789);
            for text in [
                "2024-02-30",
                "2021-W53-7",
                "2023-366",
                "Jan 2 2024",
                "2024-01-02 tail",
            ] {
                assert!(read_native(text).is_err(), "{text}");
            }
        })
        .join()
        .expect("native ISO worker must not panic");
    }
}
