//! Dedicated ISO factory grammar; ordinary text parsing retains its own policy.
//! No Python date carrier is needed to retain zero/wide years or nanoseconds.
use super::text::{CharacterRead, digit};
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

#[inline]
fn digits(input: &impl CharacterRead, position: &mut usize, count: usize) -> Result<i64, Error> {
    if count <= 4 {
        let value = input.number(*position, count, 0, 9_999);
        if value < 0 {
            return Err(invalid());
        }
        *position += count;
        return Ok(i64::from(value));
    }
    wide_digits(input, position, count)
}

fn wide_digits(
    input: &impl CharacterRead,
    position: &mut usize,
    count: usize,
) -> Result<i64, Error> {
    let end = position.checked_add(count).ok_or_else(invalid)?;
    if end > input.len() {
        return Err(invalid());
    }
    let mut value = 0_i64;
    for index in *position..end {
        let ch = input.get(index);
        if !digit(ch) {
            return Err(invalid());
        }
        value = value
            .checked_mul(10)
            .and_then(|v| v.checked_add(i64::from(ch - 48)))
            .ok_or(Error::Overflow("ISO year exceeds native integer range"))?;
    }
    *position = end;
    Ok(value)
}

/// Read every fractional digit, retaining only the target's meaningful prefix.
#[inline]
fn fraction(
    input: &impl CharacterRead,
    position: &mut usize,
    precision: u32,
) -> Result<(i64, usize), Error> {
    let start = *position;
    let (value, used, end) = input.fractional_digits(start, precision);
    if used == 0 {
        return Err(invalid());
    }
    *position = end;
    Ok((i64::from(value) * 10_i64.pow(precision - used), end - start))
}

#[inline]
fn clock(
    input: &impl CharacterRead,
    position: &mut usize,
    precision: u32,
) -> Result<(i64, i64, usize), Error> {
    let hour = digits(input, position, 2)?;
    let mut minute = 0;
    let mut second = 0;
    let mut compact_seconds = false;
    if input.get(*position) == 58 {
        *position += 1;
        minute = digits(input, position, 2)?;
        if input.get(*position) == 58 {
            *position += 1;
            second = digits(input, position, 2)?;
        }
    } else if digit(input.get(*position)) {
        minute = digits(input, position, 2)?;
        if digit(input.get(*position)) {
            second = digits(input, position, 2)?;
            compact_seconds = true;
        }
    }
    if hour > 23 || minute > 59 || second > 59 {
        return Err(invalid());
    }
    let seconds = (hour * 60 + minute) * 60 + second;
    let next = input.get(*position);
    let (part, count) = if matches!(next, 46 | 44) {
        *position += 1;
        fraction(input, position, precision)?
    } else if compact_seconds && digit(next) && digit(input.get(*position + 1)) {
        // The common compact form accepts a fractional tail after HHMMSS.
        fraction(input, position, precision)?
    } else {
        (0, 0)
    };
    Ok((seconds, part, count))
}

/// Decode one complete ISO factory value into local native fields and timezone.
pub(crate) fn read_native(input: &impl CharacterRead) -> Result<NativeParsed, Error> {
    let run = (0..input.len())
        .take_while(|&index| digit(input.get(index)))
        .count();
    if run < 4 {
        return Err(invalid());
    }
    if run == 4 || input.get(run) != 45 {
        return read_width(input, 4);
    }
    // A dash can also follow a compact date or its clock after a digit
    // separator. The clock may include an arbitrarily long fraction.
    if !matches!(run, 7 | 8 | 10..) {
        return read_width(input, run);
    }
    match read_width(input, run) {
        Err(Error::Invalid) => read_width(input, 4),
        Err(error @ Error::Overflow(_)) => wide_overflow(input, run, error),
        result => result,
    }
}

#[cold]
fn wide_overflow(
    input: &impl CharacterRead,
    width: usize,
    error: Error,
) -> Result<NativeParsed, Error> {
    let Ok(short) = read_width(input, 4) else {
        return Err(error);
    };
    // A Gregorian 400-year cycle preserves valid calendar fields and week
    // dates. Validate the wide suffix without narrowing the oversized year.
    let equivalent_year = (0..width).fold(0_i64, |year, i| {
        (year * 10 + i64::from(input.get(i) - 48)) % 400
    });
    match read_date(input, width, equivalent_year) {
        Err(Error::Invalid) => Ok(short),
        _ => Err(error),
    }
}

fn read_width(input: &impl CharacterRead, width: usize) -> Result<NativeParsed, Error> {
    let mut position = 0;
    let year = digits(input, &mut position, width)?;
    read_date(input, position, year)
}

fn read_date(
    input: &impl CharacterRead,
    mut position: usize,
    year: i64,
) -> Result<NativeParsed, Error> {
    let dashed = input.get(position) == 45;
    if dashed {
        position += 1;
    }
    if matches!(input.get(position), 87 | 119) {
        position += 1;
        let week = digits(input, &mut position, 2)?;
        return read_week(input, position, year, week, dashed);
    }
    let remaining = (position..input.len())
        .take_while(|&index| digit(input.get(index)))
        .count();
    if remaining == 3 || (dashed && remaining > 3) {
        return read_year_day(input, position, year);
    }
    match read_calendar(input, position, year, dashed) {
        Err(Error::Invalid) if !dashed && remaining > 3 => read_year_day(input, position, year),
        value => value,
    }
}

fn read_week(
    input: &impl CharacterRead,
    position: usize,
    year: i64,
    week: i64,
    dashed: bool,
) -> Result<NativeParsed, Error> {
    let (first, last) = crate::calendar::iso_year_start(year).map_err(Error::Overflow)?;
    if !(1..=last).contains(&week) {
        return Err(invalid());
    }
    let weekday_end = match input.get(position) {
        45 => position + 2,
        ch if digit(ch) => position + 1,
        _ => position,
    };
    // Select the same separator as Pydt for shared ISO week spellings. A
    // digit used as separator changes the parity of a compact week suffix.
    let common_end = if dashed {
        if input.get(position) == 45 && !digit(input.get(position + 2)) {
            weekday_end
        } else {
            position
        }
    } else if digit(input.get(position)) {
        let count = (position..input.len())
            .take_while(|&index| digit(input.get(index)))
            .count();
        position + usize::from(count == 1 || count % 2 == 0)
    } else {
        position
    };
    let finish = |end| {
        let day = if end == position {
            1
        } else {
            match input.get(end - 1) {
                ch @ 49..=55 => i64::from(ch - 48),
                _ => return Err(invalid()),
            }
        };
        let ordinal = crate::calendar::iso_ordinal_from_year_start(first, week, day)
            .map_err(Error::Overflow)?;
        read_tail(input, end, ordinal)
    };
    match finish(common_end) {
        // Preserve column extensions such as a dashed weekday on basic weeks
        // when the shared spelling does not provide a complete interpretation.
        Err(Error::Invalid) if weekday_end != common_end => finish(weekday_end),
        value => value,
    }
}

fn read_year_day(
    input: &impl CharacterRead,
    mut position: usize,
    year: i64,
) -> Result<NativeParsed, Error> {
    let day = digits(input, &mut position, 3)?;
    if !(1..=365 + i64::from(crate::calendar::leap(year))).contains(&day) {
        return Err(invalid());
    }
    let ordinal = crate::calendar::year_day_ordinal(year, day).map_err(Error::Overflow)?;
    read_tail(input, position, ordinal)
}

fn read_calendar(
    input: &impl CharacterRead,
    mut position: usize,
    year: i64,
    dashed: bool,
) -> Result<NativeParsed, Error> {
    let month = digits(input, &mut position, 2)?;
    if dashed {
        if input.get(position) != 45 {
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
    let ordinal = crate::calendar::checked_ordinal(year, month, day).map_err(Error::Overflow)?;
    read_tail(input, position, ordinal)
}

fn read_tail(
    input: &impl CharacterRead,
    mut position: usize,
    ordinal: i64,
) -> Result<NativeParsed, Error> {
    let mut nanos = (i128::from(ordinal) - 719_163) * 86_400_000_000_000;
    let mut unit = Unit::Microsecond;
    let mut offset = None;
    if position < input.len() {
        // Exactly one separator code point; the view retains its input owner.
        position += 1;
        let (seconds, part, count) = clock(input, &mut position, 9)?;
        nanos += i128::from(seconds * 1_000_000_000 + part);
        if count > 6 {
            unit = Unit::Nanosecond;
        }
        match input.get(position) {
            90 | 122 => {
                position += 1;
                offset = Some(0);
            }
            43 | 45 => {
                let negative = input.get(position) == 45;
                position += 1;
                let (seconds, part, _) = clock(input, &mut position, 6)?;
                let value = seconds * 1_000_000 + part;
                offset = Some(if negative { -value } else { value });
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
pub(crate) fn read(input: &impl CharacterRead) -> PyResult<Parsed> {
    let parsed = read_native(input).map_err(|error| match error {
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

    fn read_native(text: &str) -> Result<NativeParsed, Error> {
        let mut scratch = Vec::new();
        super::read_native(&crate::parser::text::Utf8View::new(text, &mut scratch))
    }
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
