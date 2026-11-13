//! One native integer realtime clock value, independent of the output container.
use std::time::{SystemTime, UNIX_EPOCH};

/// Convert the platform clock without a float or Python datetime carrier.
pub(crate) fn system_nanos(time: SystemTime) -> Result<i128, &'static str> {
    match time.duration_since(UNIX_EPOCH) {
        Ok(value) => i128::try_from(value.as_nanos()),
        Err(value) => i128::try_from(value.duration().as_nanos()).map(|value| -value),
    }
    .map_err(|_| "system clock exceeds native integer range")
}
