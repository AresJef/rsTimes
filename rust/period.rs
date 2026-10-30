//! Common pure calendar periods, output-lattice alignment and Snap geometry.
const NS_DAY: i128 = 86_400_000_000_000;
#[derive(Debug)]
pub(crate) enum Error {
    Value(String),
    Capacity(&'static str),
    Internal(&'static str),
}
impl Error {
    fn value(message: impl Into<String>) -> Self {
        Self::Value(message.into())
    }
}
impl From<crate::date_transform::Error> for Error {
    fn from(error: crate::date_transform::Error) -> Self {
        match error {
            crate::date_transform::Error::Value(message) => Self::Value(message),
            crate::date_transform::Error::Capacity(message) => Self::Capacity(message),
        }
    }
}
#[derive(Clone, Copy, serde::Serialize, serde::Deserialize)]
pub(crate) enum Period {
    Year,
    Quarter,
    Month,
    Week,
    Day,
    Tick(#[serde(with = "crate::serde_values::signed_128")] i128),
    NamedMonth(i64),
    NamedWeekday(i64),
}
impl Period {
    pub fn parse(text: &str, clock: bool) -> Result<Self, Error> {
        let value = match text {
            "Y" => Self::Year,
            "Q" => Self::Quarter,
            "M" => Self::Month,
            "W" => Self::Week,
            "D" => Self::Day,
            "h" => Self::Tick(3_600_000_000_000),
            "m" | "min" => Self::Tick(60_000_000_000),
            "s" => Self::Tick(1_000_000_000),
            "ms" => Self::Tick(1_000_000),
            "us" => Self::Tick(1000),
            "ns" => Self::Tick(1),
            _ => {
                let (month, weekday) = crate::pydt::boundary_names(text);
                if month > 0 {
                    Self::NamedMonth(i64::from(month))
                } else if clock && weekday >= 0 {
                    Self::NamedWeekday(i64::from(weekday))
                } else {
                    return Err(Error::value(
                        "unknown or empty period or stored name; use Y, Q, M, W and supported clock units or stored names",
                    ));
                }
            }
        };
        if !clock && matches!(value, Self::Day | Self::Tick(_) | Self::NamedWeekday(_)) {
            return Err(Error::value(
                "first/last require Y, Q, M, W or a stored month name",
            ));
        }
        Ok(value)
    }
    pub fn clock(self) -> bool {
        matches!(self, Self::Tick(_))
    }
    pub fn bounds(self, wall: i128) -> Result<(i128, i128), Error> {
        if let Self::Tick(step) = self {
            let lower = wall.div_euclid(step) * step;
            return Ok((
                lower,
                lower
                    .checked_add(step)
                    .ok_or(Error::Capacity("period boundary overflow"))?,
            ));
        }
        let day = wall.div_euclid(NS_DAY);
        if matches!(self, Self::Day) {
            return Ok((day * NS_DAY, (day + 1) * NS_DAY));
        }
        if matches!(self, Self::Week | Self::NamedWeekday(_)) {
            let weekday = (day + 3).rem_euclid(7);
            let lower = day - weekday;
            return Ok(match self {
                Self::NamedWeekday(value) => (
                    (lower + i128::from(value)) * NS_DAY,
                    (lower + i128::from(value) + 1) * NS_DAY,
                ),
                _ => (lower * NS_DAY, (lower + 7) * NS_DAY),
            });
        }
        let f = crate::date_transform::fields(wall).map_err(Error::from)?;
        let (month, width) = match self {
            Self::Year => (1, 12),
            Self::Quarter => ((f[1] - 1) / 3 * 3 + 1, 3),
            Self::Month => (f[1], 1),
            Self::NamedMonth(month) => (month, 1),
            _ => return Err(Error::Internal("invalid calendar period")),
        };
        let first = crate::calendar::checked_ordinal(f[0], month, 1).map_err(Error::Capacity)?;
        let next = crate::calendar::move_date([f[0], month, 1], width, 0, None, None)
            .map_err(Error::Capacity)?;
        let last =
            crate::calendar::checked_ordinal(next[0], next[1], next[2]).map_err(Error::Capacity)?;
        Ok((
            (i128::from(first) - 719_163) * NS_DAY,
            (i128::from(last) - 719_163) * NS_DAY,
        ))
    }
}

#[derive(Clone, Copy)]
pub(crate) struct Snap {
    pub(crate) period: Period,
    pub(crate) months: i64,
    pub(crate) step: i128,
    pub(crate) width_months: i64,
    pub(crate) width: i128,
}

impl Snap {
    pub(crate) fn prepare(period: Period, wall: i128) -> Result<(Self, i128), Error> {
        let (months, step, width_months, width) = match period {
            Period::Year => (12, 0, 12, 0),
            Period::Quarter => (3, 0, 3, 0),
            Period::Month => (1, 0, 1, 0),
            Period::NamedMonth(_) => (12, 0, 1, 0),
            Period::Week => (0, 7 * NS_DAY, 0, 7 * NS_DAY),
            Period::NamedWeekday(_) => (0, 7 * NS_DAY, 0, NS_DAY),
            Period::Day => (0, NS_DAY, 0, NS_DAY),
            Period::Tick(step) => (0, step, 0, step),
        };
        let spec = Self {
            period,
            months,
            step,
            width_months,
            width,
        };
        let mut lower = period.bounds(wall)?.0;
        if lower > wall {
            lower = spec.shift(lower, -1)?;
        }
        Ok((spec, lower))
    }
    pub(crate) fn shift(self, start: i128, direction: i64) -> Result<i128, Error> {
        if self.months != 0 {
            self.month_boundary(start, self.months * direction)
        } else {
            start
                .checked_add(self.step * i128::from(direction))
                .ok_or(Error::Capacity("Snap period overflow"))
        }
    }
    pub(crate) fn month_boundary(self, start: i128, months: i64) -> Result<i128, Error> {
        let f = crate::date_transform::fields(start).map_err(Error::from)?;
        let date = crate::calendar::move_date([f[0], f[1], 1], i128::from(months), 0, None, None)
            .map_err(Error::Capacity)?;
        crate::date_transform::nanos([date[0], date[1], date[2], 0, 0, 0, 0, 0])
            .map_err(Error::from)
    }
    pub(crate) fn end(self, start: i128) -> Result<i128, Error> {
        if self.width_months != 0 {
            self.month_boundary(start, self.width_months)
        } else {
            start
                .checked_add(self.width)
                .ok_or(Error::Capacity("Snap period overflow"))
        }
    }
}

/// Earlier/end or later/start lattice point; capacity is checked at the output.
pub(crate) fn align(value: i128, unit: i128, end: bool) -> Result<i128, Error> {
    let q = value.div_euclid(unit);
    q.checked_add(i128::from(!end && value.rem_euclid(unit) != 0))
        .and_then(|value| value.checked_mul(unit))
        .ok_or(Error::Capacity("period output overflow"))
}
/// Round ties to even; ceil/floor refer to integer wall coordinates here.
pub(crate) fn rounded(wall: i128, step: i128, mode: u8) -> Result<i128, Error> {
    let q = wall.div_euclid(step);
    let r = wall.rem_euclid(step);
    if r == 0 {
        return Ok(wall);
    }
    let up = match mode {
        0 => r > step - r || (r == step - r && q.rem_euclid(2) != 0),
        1 => true,
        _ => false,
    };
    q.checked_add(i128::from(up))
        .and_then(|value| value.checked_mul(step))
        .ok_or(Error::Capacity("rounded date overflow"))
}
/// Preserve true-instant direction after the caller has resolved a local grid.
pub(crate) fn direction(value: i128, source: i128, mode: u8) -> bool {
    (mode != 1 || value >= source) && (mode != 2 || value <= source)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn period_math_needs_no_python_thread_and_handles_signed_grid() {
        std::thread::spawn(|| {
            assert_eq!(Period::Month.bounds(0).unwrap(), (0, 31 * NS_DAY));
            let zero_year = crate::date_transform::nanos([0, 2, 15, 1, 2, 3, 4, 5]).unwrap();
            let (begin, end) = Period::Month.bounds(zero_year).unwrap();
            assert_eq!(end - begin, 29 * NS_DAY);
            let (snap, start) = Snap::prepare(Period::Month, zero_year).unwrap();
            assert_eq!(snap.shift(start, 1).unwrap(), end);
            assert_eq!(rounded(500, 1000, 0).unwrap(), 0);
            assert_eq!(rounded(1500, 1000, 0).unwrap(), 2000);
            assert_eq!(rounded(-500, 1000, 0).unwrap(), 0);
            assert_eq!(rounded(-1500, 1000, 0).unwrap(), -2000);
            assert_eq!(rounded(-1, 1000, 1).unwrap(), 0);
            assert_eq!(rounded(-1, 1000, 2).unwrap(), -1000);
            assert_eq!(align(-1, 1000, true).unwrap(), -1000);
            assert_eq!(align(-1, 1000, false).unwrap(), 0);
        })
        .join()
        .unwrap();
    }
}
