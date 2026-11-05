//! Pure numeric and ISO output shared by typed date containers.
/// Exact integer ratio, rounded once to binary64, retaining the reference algorithm.
/// Source ticks plus a legal offset fit 95 bits; the scaled significand fits u128.
pub(crate) fn seconds_float(tick: i128, denominator: u64) -> f64 {
    if tick == 0 {
        return 0.0;
    }
    let numerator = tick.unsigned_abs();
    let denominator = u128::from(denominator);
    let mut exponent =
        (127 - numerator.leading_zeros()) as i32 - (127 - denominator.leading_zeros()) as i32;
    if (exponent >= 0 && numerator < (denominator << exponent as u32))
        || (exponent < 0 && (numerator << (-exponent) as u32) < denominator)
    {
        exponent -= 1;
    }
    let shift = 52 - exponent;
    let (n, d) = if shift >= 0 {
        (numerator << shift as u32, denominator)
    } else {
        (numerator, denominator << (-shift) as u32)
    };
    let mut significand = n / d;
    let remainder = n % d;
    if remainder > d - remainder || remainder == d - remainder && significand & 1 != 0 {
        significand += 1;
    }
    if significand == 1_u128 << 53 {
        significand >>= 1;
        exponent += 1;
    }
    f64::from_bits(
        (u64::from(tick < 0) << 63)
            | (((exponent + 1023) as u64) << 52)
            | (significand as u64 & ((1_u64 << 52) - 1)),
    )
}

pub(crate) fn offset_text(offset: i64) -> String {
    let sign = if offset < 0 { '-' } else { '+' };
    let offset = offset.unsigned_abs();
    let second = offset / 1_000_000;
    let micros = offset % 1_000_000;
    let mut result = format!("{sign}{:02}:{:02}", second / 3600, second / 60 % 60);
    if !second.is_multiple_of(60) || micros != 0 {
        result.push_str(&format!(":{:02}", second % 60));
    }
    if micros != 0 {
        result.push_str(&format!(".{micros:06}"));
    }
    result
}
pub(crate) fn iso_text(fields: [i64; 8], sep: &str, precision: u8, offset: Option<i64>) -> String {
    let f = fields;
    let mut result = format!("{:04}-{:02}-{:02}{sep}{:02}", f[0], f[1], f[2], f[3]);
    if precision != 1 {
        result.push_str(&format!(":{:02}", f[4]));
    }
    if precision != 1 && precision != 2 {
        result.push_str(&format!(":{:02}", f[5]));
    }
    let digits = match precision {
        0 if f[7] != 0 => 9,
        0 if f[6] != 0 => 6,
        4 => 3,
        5 => 6,
        6 => 9,
        _ => 0,
    };
    if digits != 0 {
        let fraction = f[6] * 1000 + f[7];
        result.push('.');
        result.push_str(&format!("{fraction:09}")[..digits]);
    }
    if let Some(offset) = offset {
        result.push_str(&offset_text(offset));
    }
    result
}
