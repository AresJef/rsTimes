//! Current frequency strings decode directly into the shared native calendar.
use crate::epoch::Unit;
use crate::range_calendar::{Business, Frequency, Kind, Plan};
use pyo3::prelude::*;
use pyo3::types::{PyDelta, PyDeltaAccess, PyString};
#[derive(Debug)]
pub(crate) enum Error {
    Value(&'static str),
    Capacity(&'static str),
}
impl From<Error> for PyErr {
    fn from(error: Error) -> Self {
        match error {
            Error::Value(message) => crate::error_context::value_error(message),
            Error::Capacity(message) => crate::error_context::overflow(message),
        }
    }
}
fn base(kind: Kind, n: i64, precision: Unit) -> Result<Plan, Error> {
    if n == 0 || matches!(kind, Kind::Fixed(0)) {
        return Err(Error::Value("frequency must not be zero"));
    }
    Ok(Plan {
        frequency: Frequency {
            kind,
            n,
            normalize: false,
            offset: 0,
            business: Business {
                mask: [true, true, true, true, true, false, false],
                holidays: Vec::new(),
            },
        },
        precision,
    })
}
fn fixed(value: i128, precision: Unit) -> Result<Plan, Error> {
    base(
        Kind::Fixed(value),
        if value < 0 { -1 } else { 1 },
        precision,
    )
}

fn number(text: &str) -> Result<i64, Error> {
    match text {
        "" | "+" => Ok(1),
        "-" => Ok(-1),
        _ => text
            .parse()
            .map_err(|_| Error::Capacity("frequency multiplier exceeds signed64")),
    }
}
fn month(text: &str) -> Result<i64, Error> {
    [
        "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
    ]
    .iter()
    .position(|value| *value == text)
    .map(|value| value as i64 + 1)
    .ok_or(Error::Value(
        "frequency month anchor must be JAN through DEC",
    ))
}
fn weekday(text: &str) -> Result<i64, Error> {
    ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        .iter()
        .position(|value| *value == text)
        .map(|value| value as i64)
        .ok_or(Error::Value("weekly frequency requires MON through SUN"))
}
fn decimal(text: &str) -> Result<(i128, i128), Error> {
    let mut value = 0_i128;
    let mut denominator = 1_i128;
    let mut fractional = false;
    let mut digits = 0;
    for byte in text.bytes() {
        if byte == b'.' && !fractional {
            fractional = true;
            continue;
        }
        if !byte.is_ascii_digit() {
            return Err(Error::Value("invalid decimal frequency"));
        }
        digits += 1;
        value = value
            .checked_mul(10)
            .and_then(|value| value.checked_add(i128::from(byte - b'0')))
            .ok_or(Error::Capacity(
                "frequency coefficient exceeds native precision",
            ))?;
        if fractional {
            denominator = denominator
                .checked_mul(10)
                .ok_or(Error::Capacity("frequency decimal precision is too large"))?;
        }
    }
    if digits == 0 {
        return Err(Error::Value("frequency needs a numeric coefficient"));
    }
    Ok((value, denominator))
}
fn scale(unit: &str) -> Option<(i128, Unit)> {
    match unit {
        "D" => Some((86_400_000_000_000, Unit::Second)),
        "h" => Some((3_600_000_000_000, Unit::Second)),
        "min" => Some((60_000_000_000, Unit::Second)),
        "s" => Some((1_000_000_000, Unit::Second)),
        "ms" => Some((1_000_000, Unit::Millisecond)),
        "us" => Some((1000, Unit::Microsecond)),
        "ns" => Some((1, Unit::Nanosecond)),
        _ => None,
    }
}
/// None means only a recognized, explicitly mature-only frequency family.
pub(crate) fn parse(text: &str) -> Result<Option<Plan>, Error> {
    let text = text.trim();
    if text.is_empty() {
        return Err(Error::Value("frequency must not be empty"));
    }
    let (sign, unsigned) = if let Some(rest) = text.strip_prefix('-') {
        (-1_i128, rest)
    } else {
        (1, text.strip_prefix('+').unwrap_or(text))
    };
    let bytes = unsigned.as_bytes();
    let mut position = 0;
    let mut parts = Vec::new();
    let mut fixed_valid = true;
    while position < bytes.len() {
        while bytes.get(position).is_some_and(u8::is_ascii_whitespace) {
            position += 1;
        }
        let start = position;
        while bytes
            .get(position)
            .is_some_and(|value| value.is_ascii_digit() || *value == b'.')
        {
            position += 1;
        }
        if position == start {
            fixed_valid = false;
            break;
        }
        let coefficient = &unsigned[start..position];
        while bytes.get(position).is_some_and(u8::is_ascii_whitespace) {
            position += 1;
        }
        let unit = ["min", "ms", "us", "ns", "D", "h", "s"]
            .into_iter()
            .find(|unit| unsigned[position..].starts_with(unit));
        let Some(unit) = unit else {
            fixed_valid = false;
            break;
        };
        position += unit.len();
        parts.push((coefficient, unit));
    }
    if fixed_valid && position == bytes.len() && !parts.is_empty() {
        if parts.len() == 1 && parts[0].1 == "D" {
            let (value, denominator) = decimal(parts[0].0)?;
            if value % denominator == 0 {
                return base(
                    Kind::Days,
                    i64::try_from(sign * (value / denominator))
                        .map_err(|_| Error::Capacity("day multiplier exceeds signed64"))?,
                    Unit::Second,
                )
                .map(Some);
            }
        }
        let mut total = 0_i128;
        let mut precision = Unit::Second;
        for (coefficient, unit) in parts {
            let (value, denominator) = decimal(coefficient)?;
            let (scale, unit) = scale(unit).ok_or(Error::Value("unknown fixed frequency"))?;
            let value = value
                .checked_mul(scale)
                .ok_or(Error::Capacity("frequency exceeds native precision"))?;
            if value % denominator != 0 {
                return Err(Error::Value("frequency is finer than one nanosecond"));
            }
            total = total
                .checked_add(value / denominator)
                .ok_or(Error::Capacity("frequency exceeds native precision"))?;
            precision = precision.max(unit);
        }
        return fixed(sign * total, precision).map(Some);
    }
    let mut split = 0;
    let bytes = text.as_bytes();
    if matches!(bytes.first(), Some(b'+' | b'-')) {
        split += 1;
    }
    while bytes.get(split).is_some_and(u8::is_ascii_digit) {
        split += 1;
    }
    let n = number(&text[..split])?;
    let rest = text[split..].trim_start();
    let (code, anchor) = rest
        .split_once('-')
        .map_or((rest, None), |(code, anchor)| (code, Some(anchor)));
    if matches!(code, "bh" | "cbh" | "RE" | "REQ") {
        if n == 0 {
            return Err(Error::Value("frequency must not be zero"));
        }
        return Ok(None);
    }
    let kind = match code {
        "h" | "min" | "s" | "ms" | "us" | "ns" if anchor.is_none() => {
            let (scale, unit) = scale(code).ok_or(Error::Value("unknown fixed frequency"))?;
            return fixed(i128::from(n) * scale, unit).map(Some);
        }
        "D" if anchor.is_none() => Kind::Days,
        "W" => Kind::Week(Some(weekday(anchor.unwrap_or("SUN"))?)),
        "B" | "C" if anchor.is_none() => Kind::Business,
        "MS" | "ME" | "BMS" | "BME" | "CBMS" | "CBME" if anchor.is_none() => Kind::Boundary {
            stride: 1,
            anchor: 1,
            start: code.ends_with('S'),
            business: code.starts_with('B') || code.starts_with("CB"),
        },
        "QS" | "QE" | "BQS" | "BQE" | "YS" | "YE" | "BYS" | "BYE" => {
            let start = code.ends_with('S');
            let stride = if code.contains('Q') { 3 } else { 12 };
            Kind::Boundary {
                stride,
                anchor: anchor
                    .map(month)
                    .transpose()?
                    .unwrap_or(if start { 1 } else { 12 }),
                start,
                business: code.starts_with('B'),
            }
        }
        "SMS" | "SME" => {
            let day = if let Some(anchor) = anchor {
                if anchor.is_empty() || !anchor.bytes().all(|value| value.is_ascii_digit()) {
                    return Err(Error::Value(
                        "semi-month frequency needs a numeric day anchor",
                    ));
                }
                anchor
                    .parse::<i64>()
                    .map_err(|_| Error::Capacity("semi-month anchor exceeds signed64"))?
            } else {
                15
            };
            if !(1..=27).contains(&day) {
                return Err(Error::Value("semi-month anchor must be in 1..27"));
            }
            Kind::Semi {
                start: code == "SMS",
                day,
            }
        }
        "WOM" => {
            let anchor = anchor.ok_or(Error::Value("WOM needs 1MON through 4SUN"))?;
            if anchor.len() != 4 || !matches!(anchor.as_bytes()[0], b'1'..=b'4') {
                return Err(Error::Value("WOM needs 1MON through 4SUN"));
            }
            Kind::WeekOfMonth {
                weekday: weekday(&anchor[1..])?,
                week: i64::from(anchor.as_bytes()[0] - b'1'),
                last: false,
            }
        }
        "LWOM" => Kind::WeekOfMonth {
            weekday: weekday(anchor.ok_or(Error::Value("LWOM needs MON through SUN"))?)?,
            week: 0,
            last: true,
        },
        _ => {
            return Err(Error::Value(
                "unsupported frequency; use current names such as '15min', 'ME' or 'QS-JAN', or a pandas DateOffset for a custom rule",
            ));
        }
    };
    base(kind, n, Unit::Second).map(Some)
}
#[pyfunction]
fn _pldt_frequency(value: &Bound<'_, PyAny>) -> PyResult<Option<Plan>> {
    if let Ok(text) = value.cast::<PyString>() {
        let converted;
        let text = if value.is_exact_instance_of::<PyString>() {
            text
        } else {
            converted = value.str().map_err(crate::error_context::external)?;
            &converted
        };
        return parse(text.to_str()?).map_err(PyErr::from);
    }
    if let Some(value) = crate::interop::duration_nanoseconds(value)? {
        return fixed(value, crate::precision::quantum_unit(value))
            .map(Some)
            .map_err(PyErr::from);
    }
    if let Ok(value) = value.cast::<PyDelta>() {
        let ns = (i128::from(value.get_days()) * 86400 + i128::from(value.get_seconds()))
            * 1_000_000_000
            + i128::from(value.get_microseconds()) * 1000;
        return fixed(ns, crate::precision::quantum_unit(ns))
            .map(Some)
            .map_err(PyErr::from);
    }
    Err(crate::error_context::type_error(
        "freq must be a current frequency string, timedelta or supported pandas DateOffset",
    ))
}
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_frequency, module)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_frequency_complete_consumption_decimal_and_role() {
        std::thread::spawn(|| {
            for text in [
                "1h2", "1h-30min", "M", "H", "m", "T", "0ns", "0D", "WOM-5MON", "QS-XYZ",
            ] {
                assert!(parse(text).is_err(), "{text}");
            }
            let plan = parse("0.5us")
                .unwrap_or_else(|error| panic!("{error:?}"))
                .expect("native plan");
            assert!(matches!(plan.frequency.kind, Kind::Fixed(500)));
            assert_eq!(plan.precision, Unit::Microsecond);
            let plan = parse("1.0D")
                .unwrap_or_else(|error| panic!("{error:?}"))
                .expect("native day");
            assert!(matches!(plan.frequency.kind, Kind::Days));
            let plan = parse("1.5D")
                .unwrap_or_else(|error| panic!("{error:?}"))
                .expect("native duration");
            assert!(matches!(
                plan.frequency.kind,
                Kind::Fixed(129_600_000_000_000)
            ));
            assert!(
                parse("bh")
                    .unwrap_or_else(|error| panic!("{error:?}"))
                    .is_none()
            );
            assert!(
                parse("RE-L-DEC-SAT")
                    .unwrap_or_else(|error| panic!("{error:?}"))
                    .is_none()
            );
        })
        .join()
        .expect("unattached frequency worker must not panic");
    }
}
