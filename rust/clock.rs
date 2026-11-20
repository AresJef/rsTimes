//! One native integer realtime clock value, independent of the output container.
use std::time::{SystemTime, UNIX_EPOCH};

/// Convert the platform clock without a float or Python datetime carrier.
pub(crate) fn system_nanos(time: SystemTime) -> i128 {
    // Duration stores u64 seconds plus fewer than 1e9 nanos: its total is
    // below 2^94, so either sign fits i128 before final output-unit checks.
    match time.duration_since(UNIX_EPOCH) {
        Ok(value) => value.as_nanos() as i128,
        Err(value) => -(value.duration().as_nanos() as i128),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn duration_extremes_fit_integer_nanos_for_either_sign() {
        let value = Duration::MAX.as_nanos();
        assert!(value < 1_u128 << 94);
        assert_eq!((value as i128) as u128, value);
        assert!(-(value as i128) > i128::MIN);
        for delta in [
            Duration::ZERO,
            Duration::new(0, 1),
            Duration::new(1, 123_456_789),
        ] {
            assert_eq!(system_nanos(UNIX_EPOCH + delta), delta.as_nanos() as i128);
            assert_eq!(
                system_nanos(UNIX_EPOCH - delta),
                -(delta.as_nanos() as i128)
            );
        }
    }
}
