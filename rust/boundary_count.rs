//! Pure boundary-count plans and exact final integer result, shared by columns.
use crate::epoch::Unit;
const NS_DAY: i128 = 86_400_000_000_000;
#[derive(Debug)]
pub(crate) enum Error {
    Value(&'static str),
    Capacity(&'static str),
}
#[derive(Clone, Copy)]
pub(crate) enum Bucket {
    Calendar(u8),
    Week,
    Fixed(i128),
}
impl Bucket {
    pub(crate) fn parse(unit: &str) -> Result<Self, Error> {
        Ok(match unit {
            "Y" => Self::Calendar(0),
            "Q" => Self::Calendar(1),
            "M" => Self::Calendar(2),
            "W" => Self::Week,
            "D" => Self::Fixed(NS_DAY),
            "h" => Self::Fixed(3_600_000_000_000),
            "m" | "min" => Self::Fixed(60_000_000_000),
            "s" => Self::Fixed(1_000_000_000),
            "ms" => Self::Fixed(1_000_000),
            "us" => Self::Fixed(1000),
            "ns" => Self::Fixed(1),
            _ => {
                return Err(Error::Value(
                    "unit must be Y, Q, M, W, D, h, m, min, s, ms, us or ns",
                ));
            }
        })
    }
    pub(crate) fn index(self, value: i128) -> Result<i128, Error> {
        match self {
            Self::Fixed(step) => Ok(value.div_euclid(step)),
            Self::Week => Ok((value.div_euclid(NS_DAY) + 3).div_euclid(7)),
            Self::Calendar(kind) => calendar_index(kind, calendar_ordinal(value)?),
        }
    }
}

fn calendar_ordinal(value: i128) -> Result<i64, Error> {
    i64::try_from(value.div_euclid(NS_DAY) + 719_163)
        .map_err(|_| Error::Capacity("calendar day exceeds the native range"))
}

fn calendar_index(kind: u8, ordinal: i64) -> Result<i128, Error> {
    let [year, month, _] = crate::calendar::from_ordinal(ordinal).map_err(Error::Capacity)?;
    let year = i128::from(year) - 1970;
    Ok(match kind {
        0 => year,
        1 => year * 4 + i128::from((month - 1) / 3),
        _ => year * 12 + i128::from(month - 1),
    })
}

/// One operation owns its calendar kind and last completed day result.
/// Target reads and errors still occur before this pure integer lookup.
#[derive(Clone, Copy)]
struct CalendarMemo {
    kind: u8,
    last: Option<(i64, i128)>,
}
impl CalendarMemo {
    pub(crate) fn new(kind: u8) -> Self {
        Self { kind, last: None }
    }
    fn index(&mut self, ordinal: i64) -> Result<i128, Error> {
        if let Some((previous, index)) = self.last
            && previous == ordinal
        {
            return Ok(index);
        }
        let index = calendar_index(self.kind, ordinal)?;
        self.last = Some((ordinal, index));
        Ok(index)
    }
}

/// A fixed boundary can be counted in storage ticks without a wide division per row.
#[derive(Clone, Copy)]
pub(crate) enum TickBucket {
    Scale(i128),
    Divide(i64),
    Calendar(Bucket, Unit),
}
impl TickBucket {
    pub(crate) fn new(bucket: Bucket, unit: Unit) -> Self {
        // Supported fixed steps and storage units divide exactly; the largest
        // quotient is one day in nanoseconds, comfortably inside i64.
        match bucket {
            Bucket::Fixed(step) if unit.nanos() >= step => Self::Scale(unit.nanos() / step),
            Bucket::Fixed(step) => Self::Divide((step / unit.nanos()) as i64),
            _ => Self::Calendar(bucket, unit),
        }
    }
    pub(crate) fn index(self, tick: i64) -> Result<i128, Error> {
        match self {
            Self::Scale(factor) => Ok(i128::from(tick) * factor),
            Self::Divide(divisor) => Ok(i128::from(tick.div_euclid(divisor))),
            Self::Calendar(bucket, unit) => bucket.index(i128::from(tick) * unit.nanos()),
        }
    }
}

/// These two native plans are chosen once, keeping calendar state out of the
/// fixed-unit loop. Static dispatch preserves one shared result/error writer.
pub(crate) trait BoundaryIndex {
    fn source(&mut self, tick: i64) -> Result<i128, Error>;
    fn target(&mut self, nanos: i128) -> Result<i128, Error>;
}

pub(crate) struct FixedIndex {
    pub(crate) source: TickBucket,
    pub(crate) target: Bucket,
}
impl BoundaryIndex for FixedIndex {
    #[inline]
    fn source(&mut self, tick: i64) -> Result<i128, Error> {
        self.source.index(tick)
    }
    #[inline]
    fn target(&mut self, nanos: i128) -> Result<i128, Error> {
        self.target.index(nanos)
    }
}

pub(crate) struct CalendarIndex {
    ticks_per_day: i64,
    source: CalendarMemo,
    target: CalendarMemo,
}
impl CalendarIndex {
    pub(crate) fn new(kind: u8, unit: Unit) -> Self {
        // All four storage resolutions divide a day exactly within i64.
        Self {
            ticks_per_day: (NS_DAY / unit.nanos()) as i64,
            source: CalendarMemo::new(kind),
            target: CalendarMemo::new(kind),
        }
    }
}
impl BoundaryIndex for CalendarIndex {
    #[inline]
    fn source(&mut self, tick: i64) -> Result<i128, Error> {
        let ordinal = tick
            .div_euclid(self.ticks_per_day)
            .checked_add(719_163)
            .ok_or(Error::Capacity("calendar day exceeds the native range"))?;
        self.source.index(ordinal)
    }
    #[inline]
    fn target(&mut self, nanos: i128) -> Result<i128, Error> {
        self.target.index(calendar_ordinal(nanos)?)
    }
}

pub(crate) fn finish(
    left: i128,
    right: i128,
    absolute: bool,
    adjustment: i128,
) -> Result<i64, Error> {
    let mut value = left
        .checked_sub(right)
        .ok_or(Error::Capacity("date difference exceeds native range"))?;
    if absolute {
        value = value
            .checked_abs()
            .ok_or(Error::Capacity("absolute difference exceeds native range"))?;
    }
    value = value
        .checked_add(if value < 0 { -adjustment } else { adjustment })
        .ok_or(Error::Capacity("inclusive difference exceeds native range"))?;
    i64::try_from(value).map_err(|_| {
        Error::Capacity("difference exceeds the full int64 range; choose a coarser diff unit")
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_boundary_math_is_python_free_and_checks_only_final_capacity() {
        std::thread::spawn(|| {
            assert_eq!(Bucket::parse("W").unwrap().index(0).unwrap(), 0);
            assert_eq!(Bucket::parse("D").unwrap().index(-1).unwrap(), -1);
            assert_eq!(Bucket::parse("M").unwrap().index(0).unwrap(), 0);
            assert_eq!(
                TickBucket::new(Bucket::Fixed(NS_DAY), Unit::Microsecond)
                    .index(i64::MIN)
                    .unwrap(),
                i128::from(i64::MIN.div_euclid(86_400_000_000))
            );
            assert_eq!(finish(0, 0, false, -1).unwrap(), -1);
            assert_eq!(finish(-2, 0, true, 1).unwrap(), 3);
            assert_eq!(
                finish(i128::from(i64::MAX) + 1, 0, false, -1).unwrap(),
                i64::MAX
            );
            assert_eq!(finish(i128::from(i64::MIN), 0, false, 0).unwrap(), i64::MIN);
            assert!(finish(i128::from(i64::MIN), 0, true, 0).is_err());
        })
        .join()
        .unwrap();
    }
}
