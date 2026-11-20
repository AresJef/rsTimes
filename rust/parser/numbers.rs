//! Independent numeric text grammars, without date fields or Python callbacks.
use super::text::{CharacterRead, TextView};
use pyo3::Borrowed;
use pyo3::exceptions::PyMemoryError;
use pyo3::prelude::*;
use pyo3::types::{PyInt, PyString};

/// Prepare an option once and add its exact public context only on failure.
struct Flag<const FLOAT: bool, const GROUP: bool>(bool);
impl<'a, 'py, const FLOAT: bool, const GROUP: bool> FromPyObject<'a, 'py> for Flag<FLOAT, GROUP> {
    type Error = PyErr;
    fn extract(value: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        crate::numeric::boolean(&value).map(Self).map_err(|error| {
            crate::error_context::argument(
                value.py(),
                error,
                if FLOAT {
                    "parse_to_float"
                } else {
                    "parse_to_integer"
                },
                if GROUP { "allow_grouping" } else { "strict" },
                &value,
            )
        })
    }
}

#[derive(Debug)]
enum Failure {
    Value(usize, &'static str),
    Overflow(usize),
    Memory,
}
type Result<T> = std::result::Result<T, Failure>;

struct Bytes<'a>(&'a [u8]);
impl CharacterRead for Bytes<'_> {
    fn len(&self) -> usize {
        self.0.len()
    }
    #[inline]
    fn get(&self, index: usize) -> u32 {
        self.0.get(index).map_or(0, |&value| u32::from(value))
    }
    fn truncate(&mut self, end: usize) {
        self.0 = &self.0[..end.min(self.0.len())];
    }
    fn byte_slice(&self) -> Option<&[u8]> {
        Some(self.0)
    }
}

#[inline]
fn digit(ch: u32) -> bool {
    (48..=57).contains(&ch)
}
#[inline]
fn separator(ch: u32) -> bool {
    ch == 46 || ch == 44
}

fn start(input: &impl CharacterRead, strict: bool, floating: bool) -> Result<usize> {
    if strict {
        return if input.len() == 0 {
            Err(Failure::Value(0, "no ASCII number was found"))
        } else {
            Ok(0)
        };
    }
    loose_start(input, floating)
}

// Keep the optional prefix scan out of the compact strict-token entry path.
#[inline(never)]
fn loose_start(input: &impl CharacterRead, floating: bool) -> Result<usize> {
    // A valid numeric fragment must contain a digit. Find it once, then include
    // only its immediately adjacent decimal mark/sign. Prefix characters need
    // neither sign classification nor repeated lookahead.
    let first = if let Some(bytes) = input.byte_slice() {
        bytes.iter().position(u8::is_ascii_digit)
    } else {
        (0..input.len()).find(|&pos| digit(input.get(pos)))
    };
    let mut pos = first.ok_or(Failure::Value(input.len(), "no ASCII number was found"))?;
    if floating && pos > 0 && separator(input.get(pos - 1)) {
        pos -= 1;
    }
    if pos > 0 && matches!(input.get(pos - 1), 43 | 45) {
        pos -= 1;
    }
    Ok(pos)
}

fn body(input: &impl CharacterRead, start: usize) -> (usize, bool) {
    let ch = input.get(start);
    (start + usize::from(ch == 43 || ch == 45), ch == 45)
}

/// Validate the entire integer part, including in loose extraction mode.
fn groups(input: &impl CharacterRead, start: usize, end: usize, sep: u32) -> Result<()> {
    let (mut width, mut first) = (0_usize, true);
    for pos in start..end {
        let ch = input.get(pos);
        if digit(ch) {
            width += 1;
        } else if ch == sep {
            if width == 0 || first && width > 3 || !first && width != 3 {
                return Err(Failure::Value(pos, "invalid three-digit grouping"));
            }
            first = false;
            width = 0;
        } else {
            return Err(Failure::Value(pos, "inconsistent grouping separators"));
        }
    }
    if width == 0 || first && width > 3 || !first && width != 3 {
        return Err(Failure::Value(end, "invalid three-digit grouping"));
    }
    Ok(())
}

fn exponent_end(input: &impl CharacterRead, pos: usize) -> Option<usize> {
    if input.get(pos) != 101 && input.get(pos) != 69 {
        return None;
    }
    let mut end = pos + 1;
    if input.get(end) == 43 || input.get(end) == 45 {
        end += 1;
    }
    let digits = end;
    while end < input.len() && digit(input.get(end)) {
        end += 1;
    }
    (end > digits).then_some(end)
}

fn integer(input: &impl CharacterRead, strict: bool, grouping: bool) -> Result<i128> {
    let start = start(input, strict, false)?;
    let (body, negative) = body(input, start);
    let first = input.get(body);
    if !digit(first) {
        return Err(Failure::Value(body, "an ASCII integer is required"));
    }
    let mut end = input.len();
    if grouping {
        end = body;
        let mut sep = None;
        while end < input.len() {
            let ch = input.get(end);
            if separator(ch) {
                if sep.is_some_and(|prior| prior != ch) {
                    return Err(Failure::Value(end, "inconsistent integer grouping"));
                }
                sep = Some(ch);
            } else if !digit(ch) {
                break;
            }
            end += 1;
        }
        if let Some(sep) = sep {
            groups(input, body, end, sep)?;
        }
        if exponent_end(input, end).is_some() {
            return Err(Failure::Value(end, "an integer cannot contain an exponent"));
        }
    }
    // Keep small values in a native word. On overflow promote at this digit,
    // retaining all prior work; never rescan or return a shorter numeric prefix.
    // The first digit was already checked. Consume it once and skip leading
    // zeros, which cannot affect capacity; their positions remain in the view.
    let (mut small, mut pos) = (u64::from(first - 48), body + 1);
    if small == 0 {
        while pos < end && input.get(pos) == 48 {
            pos += 1;
        }
    }
    // Four-digit decoding benefits native byte storage. Wide Unicode retains
    // its scalar route rather than probing and rereading partial chunks.
    if !grouping && input.byte_slice().is_some() {
        while end - pos >= 4 {
            let chunk = input.number(pos, 4, 0, 9999);
            if chunk < 0 {
                break;
            }
            let Some(next) = small
                .checked_mul(10_000)
                .and_then(|value| value.checked_add(chunk as u64))
            else {
                break;
            };
            small = next;
            pos += 4;
        }
    }
    let mut needs_wide = false;
    while pos < end {
        let ch = input.get(pos);
        if grouping && separator(ch) {
            pos += 1;
            continue;
        }
        if !digit(ch) {
            break;
        }
        let Some(next) = small
            .checked_mul(10)
            .and_then(|value| value.checked_add(u64::from(ch - 48)))
        else {
            needs_wide = true;
            break;
        };
        small = next;
        pos += 1;
    }
    let mut value = u128::from(small);
    if needs_wide {
        let limit = (i128::MAX as u128) + u128::from(negative);
        if !grouping && input.byte_slice().is_some() {
            while end - pos >= 4 {
                let chunk = input.number(pos, 4, 0, 9999);
                if chunk < 0 {
                    break;
                }
                let Some(next) = value
                    .checked_mul(10_000)
                    .and_then(|value| value.checked_add(chunk as u128))
                    .filter(|&value| value <= limit)
                else {
                    // The scalar remainder reports the first overflowing digit,
                    // rather than the end of a four-digit chunk.
                    break;
                };
                value = next;
                pos += 4;
            }
        }
        while pos < end {
            let ch = input.get(pos);
            if grouping && separator(ch) {
                pos += 1;
                continue;
            }
            if !digit(ch) {
                break;
            }
            value = value
                .checked_mul(10)
                .and_then(|value| value.checked_add(u128::from(ch - 48)))
                .filter(|&value| value <= limit)
                .ok_or(Failure::Overflow(pos))?;
            pos += 1;
        }
    }
    if strict && pos != input.len() {
        return Err(Failure::Value(
            pos,
            "unexpected character after the integer",
        ));
    }
    Ok(if negative {
        if value == 1_u128 << 127 {
            i128::MIN
        } else {
            -(value as i128)
        }
    } else {
        value as i128
    })
}

struct FloatSpan {
    start: usize,
    end: usize,
    decimal: Option<usize>,
    // The only group marks are ASCII dot/comma. A byte option leaves the
    // validated-short flag in existing padding instead of growing the span.
    group: Option<u8>,
    short: bool,
}

fn float_span(input: &impl CharacterRead, strict: bool, grouping: bool) -> Result<FloatSpan> {
    let start = start(input, strict, true)?;
    let (body, _) = body(input, start);
    let mut end = body;
    let (mut dots, mut commas) = (0_usize, 0_usize);
    let mut last = None;
    while end < input.len() {
        let ch = input.get(end);
        if !digit(ch) && separator(ch) {
            if !grouping && last.is_some() {
                break;
            }
            dots += usize::from(ch == 46);
            commas += usize::from(ch == 44);
            last = Some(end);
        } else if !digit(ch) {
            break;
        }
        end += 1;
    }
    // The scanned mantissa contains only ASCII digits and these separators.
    // Derive its digit count once, without an extra loop-carried counter.
    let digits = end - body - dots - commas;
    if digits == 0 {
        return Err(Failure::Value(
            body,
            "an ASCII floating-point number is required",
        ));
    }
    let (decimal, group) = if grouping && dots + commas > 1 {
        if dots == 0 || commas == 0 {
            let sep = if dots == 0 { 44 } else { 46 };
            groups(input, body, end, sep)?;
            (None, Some(sep as u8))
        } else if let Some(decimal) = last {
            let ch = input.get(decimal);
            if ch == 46 && dots != 1 || ch == 44 && commas != 1 {
                return Err(Failure::Value(
                    decimal,
                    "inconsistent decimal/grouping symbols",
                ));
            }
            let sep = if ch == 46 { 44 } else { 46 };
            groups(input, body, decimal, sep)?;
            (Some(decimal), Some(sep as u8))
        } else {
            return Err(Failure::Value(end, "invalid grouping"));
        }
    } else {
        (last, None)
    };
    let mut short = digits <= 15;
    if let Some(exponent) = exponent_end(input, end) {
        short = false;
        end = exponent;
        if grouping && separator(input.get(end)) {
            return Err(Failure::Value(
                end,
                "grouping is not allowed in an exponent",
            ));
        }
    }
    if strict && end != input.len() {
        return Err(Failure::Value(end, "unexpected character after the float"));
    }
    Ok(FloatSpan {
        start,
        end,
        decimal,
        group,
        short,
    })
}

/// Both operands are exact binary64 integers: at most 15 mantissa digits and
/// a denominator no larger than 10^15. One hardware division therefore rounds
/// the exact decimal rational once. Exponents/long mantissas use std conversion.
#[inline(never)]
fn short_decimal(input: &impl CharacterRead, span: &FloatSpan) -> f64 {
    debug_assert!(span.short);
    const POW10: [f64; 16] = [
        1.0,
        10.0,
        100.0,
        1_000.0,
        10_000.0,
        100_000.0,
        1_000_000.0,
        10_000_000.0,
        100_000_000.0,
        1_000_000_000.0,
        10_000_000_000.0,
        100_000_000_000.0,
        1_000_000_000_000.0,
        10_000_000_000_000.0,
        100_000_000_000_000.0,
        1_000_000_000_000_000.0,
    ];
    let (body, negative) = body(input, span.start);
    let mut mantissa = 0_u64;
    if span.group.is_none() {
        // The span already validated every character. Split once at its single
        // decimal mark, then fold only digits without repeating delimiter tests.
        let mut digits = |start, end| {
            for pos in start..end {
                mantissa = mantissa * 10 + u64::from(input.get(pos) - 48);
            }
        };
        if let Some(decimal) = span.decimal {
            digits(body, decimal);
            digits(decimal + 1, span.end);
        } else {
            digits(body, span.end);
        }
    } else {
        for pos in body..span.end {
            let ch = input.get(pos);
            if span.decimal == Some(pos) || span.group.is_some_and(|sep| ch == u32::from(sep)) {
                continue;
            }
            // FloatSpan validated every character; digits <= 15 proves capacity.
            mantissa = mantissa * 10 + u64::from(ch - 48);
        }
    }
    let places = span.decimal.map_or(0, |pos| span.end - pos - 1);
    let value = (mantissa as f64) / POW10[places];
    if negative { -value } else { value }
}

fn converted_float(bytes: &[u8], position: usize) -> Result<f64> {
    let text = std::str::from_utf8(bytes)
        .map_err(|_| Failure::Value(position, "invalid numeric characters"))?;
    let value = text
        .parse::<f64>()
        .map_err(|_| Failure::Value(position, "invalid floating-point syntax"))?;
    if value.is_finite() {
        Ok(value)
    } else {
        Err(Failure::Overflow(position))
    }
}

fn floating(input: &impl CharacterRead, strict: bool, grouping: bool) -> Result<f64> {
    let span = float_span(input, strict, grouping)?;
    if span.short {
        return Ok(short_decimal(input, &span));
    }
    let comma = span.decimal.is_some_and(|pos| input.get(pos) == 44);
    if span.group.is_none()
        && !comma
        && let Some(bytes) = input.byte_slice()
    {
        return converted_float(&bytes[span.start..span.end], span.start);
    }
    // Currency-sized numbers and numeric fragments in wide Unicode text fit on
    // the stack. Long mantissas use a fallible allocation, never unchecked writes.
    let mut stack = [0_u8; 128];
    let mut heap = Vec::new();
    let needed = span.end - span.start;
    let normalized: &mut [u8] = if needed <= stack.len() {
        &mut stack[..needed]
    } else {
        heap.try_reserve_exact(needed)
            .map_err(|_| Failure::Memory)?;
        heap.resize(needed, 0);
        &mut heap
    };
    let mut length = 0;
    for pos in span.start..span.end {
        let ch = input.get(pos);
        if span.group.is_some_and(|sep| ch == u32::from(sep)) {
            continue;
        }
        normalized[length] = if span.decimal == Some(pos) {
            b'.'
        } else {
            ch as u8
        };
        length += 1;
    }
    converted_float(&normalized[..length], span.start)
}

/// The mature parser already validates the entire ordinary ASCII token. Avoid
/// first scanning the same common dot-decimal token with another grammar.
fn direct_float(bytes: &[u8]) -> Option<Result<f64>> {
    let body = usize::from(matches!(bytes.first(), Some(b'+' | b'-')));
    let first = bytes.get(body).copied()?;
    if !first.is_ascii_digit()
        && !(first == b'.' && bytes.get(body + 1).is_some_and(u8::is_ascii_digit))
    {
        return None;
    }
    let value = std::str::from_utf8(bytes).ok()?.parse::<f64>().ok()?;
    Some(if value.is_finite() {
        Ok(value)
    } else {
        Err(Failure::Overflow(0))
    })
}

#[cold]
fn failure(py: Python<'_>, entry: &str, token: &Bound<'_, PyAny>, error: Failure) -> PyErr {
    let error = match error {
        Failure::Value(pos, reason) => {
            crate::error_context::value_error(format!("{reason} at position {pos}"))
        }
        Failure::Overflow(pos) => crate::error_context::overflow(format!(
            "numeric value exceeds the supported range at position {pos}"
        )),
        Failure::Memory => {
            return PyMemoryError::new_err("numeric normalization allocation failed");
        }
    };
    crate::error_context::argument(py, error, entry, "token", token)
}

fn text<'a, 'py>(
    py: Python<'py>,
    token: &'a Bound<'py, PyAny>,
    entry: &str,
) -> PyResult<&'a Bound<'py, PyString>> {
    token.cast::<PyString>().map_err(|_| {
        crate::error_context::argument(
            py,
            crate::error_context::type_error("must be a string"),
            entry,
            "token",
            token,
        )
    })
}

/// Parse a whole integer or extract its first contiguous occurrence.
///
/// Parameters
/// ----------
/// token : str
///     Text or a str subclass; stored Unicode is read without user callbacks.
/// strict : bool, default True
///     Require the complete token without stripping whitespace. False skips a
///     nonnumeric prefix and reads the first contiguous integer fragment.
/// allow_grouping : bool, default False
///     Accept consistent dot/comma grouping: first group 1..3 digits, others 3.
///     Malformed groups and decimal/exponent candidates raise even in loose mode.
///
/// Returns
/// -------
/// int
///     A Python integer in [-2**127, 2**127-1], without float conversion.
///
/// Raises
/// ------
/// TypeError
///     Unsupported token/option types. Flags accept bool and numpy.bool_ only.
/// ValueError
///     No number, invalid syntax/grouping, or unmatched strict input.
/// OverflowError
///     Signed 128-bit capacity is exceeded in either strict mode.
///
/// Examples
/// --------
/// >>> parse_to_integer("9223372036854775808")
/// 9223372036854775808
/// >>> parse_to_integer("quantity 1.234 items", strict=False, allow_grouping=True)
/// 1234
#[pyfunction]
#[pyo3(signature=(token, *, strict=Flag::<false, false>(true), allow_grouping=Flag::<false, true>(false)),
text_signature="(token, *, strict=True, allow_grouping=False)")]
fn parse_to_integer<'py>(
    py: Python<'py>,
    token: &Bound<'py, PyAny>,
    strict: Flag<false, false>,
    allow_grouping: Flag<false, true>,
) -> PyResult<Bound<'py, PyInt>> {
    let input = text(py, token, "parse_to_integer")?;
    let view = TextView::new(input);
    let value = if let Some(bytes) = view.byte_slice() {
        integer(&Bytes(bytes), strict.0, allow_grouping.0)
    } else {
        integer(&view, strict.0, allow_grouping.0)
    }
    .map_err(|error| failure(py, "parse_to_integer", token, error))?;
    if let Ok(small) = i64::try_from(value) {
        Ok(small.into_pyobject(py)?)
    } else {
        Ok(value.into_pyobject(py)?)
    }
}

/// Parse a whole float or extract its first contiguous occurrence.
///
/// Parameters
/// ----------
/// token : str
///     Text or a str subclass, with ASCII decimal/scientific syntax.
/// strict : bool, default True
///     Require the whole input; False extracts the first complete numeric prefix.
/// allow_grouping : bool, default False
///     Validate three-digit groups. One dot/comma prefers a decimal, repeated
///     identical marks mean grouping, mixed marks use the final one as decimal
///     with valid preceding groups. Invalid groups raise even when strict=False.
///     Without grouping, a second mark ends a loose numeric prefix.
///
/// Returns
/// -------
/// float
///     Correctly rounded binary64. Dot/comma decimals, signed zero and ordinary
///     underflow are supported. NaN/inf are not number syntax.
///
/// Raises
/// ------
/// TypeError
///     Unsupported token/option types. Flags accept bool and numpy.bool_ only.
/// ValueError
///     No number, malformed syntax/grouping or unmatched strict input.
/// OverflowError
///     Numeric text exceeds the finite float range.
///
/// Examples
/// --------
/// >>> parse_to_float("0.3")
/// 0.3
/// >>> parse_to_float("price 1.234,56 EUR", strict=False, allow_grouping=True)
/// 1234.56
/// >>> parse_to_float("1,234", allow_grouping=True)
/// 1.234
#[pyfunction]
#[pyo3(signature=(token, *, strict=Flag::<true, false>(true), allow_grouping=Flag::<true, true>(false)),
text_signature="(token, *, strict=True, allow_grouping=False)")]
fn parse_to_float(
    py: Python<'_>,
    token: &Bound<'_, PyAny>,
    strict: Flag<true, false>,
    allow_grouping: Flag<true, true>,
) -> PyResult<f64> {
    let input = text(py, token, "parse_to_float")?;
    let view = TextView::new(input);
    if let Some(bytes) = view.byte_slice() {
        if strict.0
            && !allow_grouping.0
            && let Some(value) = direct_float(bytes)
        {
            return value.map_err(|error| failure(py, "parse_to_float", token, error));
        }
        floating(&Bytes(bytes), strict.0, allow_grouping.0)
    } else {
        floating(&view, strict.0, allow_grouping.0)
    }
    .map_err(|error| failure(py, "parse_to_float", token, error))
}

/// Register the utilities without changing the date grammar or its hot paths.
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(parse_to_integer, module)?)?;
    module.add_function(wrap_pyfunction!(parse_to_float, module)?)?;
    for name in ["parse_to_integer", "parse_to_float"] {
        module
            .getattr(name)?
            .setattr("__module__", "rstimes.parser")?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn signed128_endpoints_and_overflow_are_checked() {
        assert_eq!(
            integer(&Bytes(i128::MIN.to_string().as_bytes()), true, false).unwrap(),
            i128::MIN
        );
        assert_eq!(
            integer(&Bytes(i128::MAX.to_string().as_bytes()), true, false).unwrap(),
            i128::MAX
        );
        assert!(matches!(
            integer(
                &Bytes(b"170141183460469231731687303715884105728"),
                true,
                false
            ),
            Err(Failure::Overflow(_))
        ));
    }
    #[test]
    fn ambiguous_separator_obeys_result_type() {
        assert_eq!(integer(&Bytes(b"1,234"), true, true).unwrap(), 1234);
        assert_eq!(floating(&Bytes(b"1,234"), true, true).unwrap(), 1.234);
    }
    #[test]
    fn long_float_uses_binary64_conversion() {
        assert_eq!(
            floating(&Bytes(b"18446744073709551616"), true, false).unwrap(),
            18446744073709551616_f64
        );
        assert_eq!(
            floating(&Bytes(b"0.99999999999999999999"), true, false).unwrap(),
            1.0
        );
    }
    #[test]
    fn loose_mode_cannot_evade_invalid_groups() {
        assert!(floating(&Bytes(b"price 1,23,456 EUR"), false, true).is_err());
        assert!(integer(&Bytes(b"quantity 12,34 items"), false, true).is_err());
    }

    #[test]
    fn exact_short_decimal_keeps_binary64_rounding_and_negative_zero() {
        assert_eq!(
            floating(&Bytes(b"price 0,3 EUR"), false, true)
                .unwrap()
                .to_bits(),
            0.3_f64.to_bits()
        );
        assert_eq!(
            floating(&Bytes(b"-0,000"), true, false).unwrap().to_bits(),
            (-0.0_f64).to_bits()
        );
        assert_eq!(
            floating(&Bytes(b"9,999,999,999,999.99"), true, true)
                .unwrap()
                .to_bits(),
            9_999_999_999_999.99_f64.to_bits()
        );
    }

    #[test]
    fn prefix_and_zero_shortcuts_keep_adjacent_fields_and_error_position() {
        assert_eq!(floating(&Bytes(b"USD -.5"), false, false).unwrap(), -0.5);
        assert_eq!(integer(&Bytes(b"USD -.5"), false, false).unwrap(), 5);
        assert_eq!(
            integer(&Bytes(b"-0000000000000000"), true, false).unwrap(),
            0
        );
        assert!(matches!(
            integer(&Bytes(b"000x"), true, false),
            Err(Failure::Value(3, _))
        ));
    }
}
