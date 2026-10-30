//! Small integer output rules shared by scalar and column container adapters.

/// Failure after a real value has reached its final target resolution.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum TickError {
    /// An exact conversion would discard a nonzero remainder.
    Precision,
    /// The final tick cannot fit signed64.
    Capacity,
}

/// Scalar epoch conversion has a distinct NaN rejection from date-missing input.
#[derive(Clone, Copy, Debug)]
pub(crate) enum FloatEpochError {
    NaN,
    Capacity,
}

/// Preserve whole numeric ticks before the approved fractional floor operation.
#[inline]
pub(crate) fn float_epoch_nanos(number: f64, scale: i128) -> Result<i128, FloatEpochError> {
    if number.is_nan() {
        return Err(FloatEpochError::NaN);
    }
    if !number.is_finite() || number < i128::MIN as f64 || number >= i128::MAX as f64 {
        return Err(FloatEpochError::Capacity);
    }
    let whole = number.trunc();
    let fraction = ((number - whole) * scale as f64).floor() as i128;
    (whole as i128)
        .checked_mul(scale)
        .and_then(|value| value.checked_add(fraction))
        .ok_or(FloatEpochError::Capacity)
}

/// Encode an epoch value at a positive, already prepared tick size.
///
/// This function has no missing sentinel: each container applies that boundary.
/// Explicit rounding means the earlier tick, including negative epochs.
#[inline]
pub(crate) fn epoch_tick(nanos: i128, tick_ns: i128, round_ok: bool) -> Result<i64, TickError> {
    debug_assert!(tick_ns > 0);
    if !round_ok && nanos.rem_euclid(tick_ns) != 0 {
        return Err(TickError::Precision);
    }
    i64::try_from(nanos.div_euclid(tick_ns)).map_err(|_| TickError::Capacity)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn epoch_float_rules_preserve_fraction_until_nanoseconds() {
        assert!(matches!(
            float_epoch_nanos(f64::NAN, 1_000_000_000),
            Err(FloatEpochError::NaN)
        ));
        assert!(matches!(
            float_epoch_nanos(f64::INFINITY, 1_000_000_000),
            Err(FloatEpochError::Capacity)
        ));
        assert_eq!(float_epoch_nanos(1e-9, 1_000_000_000).unwrap(), 1);
        assert_eq!(float_epoch_nanos(-1e-9, 1_000_000_000).unwrap(), -1);
        assert_eq!(
            float_epoch_nanos(1.5, 1_000_000_000).unwrap(),
            1_500_000_000
        );
    }

    #[test]
    fn exact_or_earlier_tick_and_full_domain() {
        assert_eq!(epoch_tick(1500, 1000, false), Err(TickError::Precision));
        assert_eq!(epoch_tick(-1500, 1000, false), Err(TickError::Precision));
        assert_eq!(epoch_tick(1500, 1000, true), Ok(1));
        assert_eq!(epoch_tick(-1500, 1000, true), Ok(-2));
        assert_eq!(epoch_tick(i128::from(i64::MIN), 1, false), Ok(i64::MIN));
        assert_eq!(epoch_tick(i128::from(i64::MAX), 1, false), Ok(i64::MAX));
        assert_eq!(
            epoch_tick(i128::from(i64::MAX) + 1, 1, true),
            Err(TickError::Capacity)
        );
    }
}
