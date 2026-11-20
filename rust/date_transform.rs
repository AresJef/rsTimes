//! Pure field merge and local calendar transforms, independent of containers.
#[derive(Debug)]
pub(crate) enum Error {
    Value(String),
    Capacity(&'static str),
}
const NS_DAY: i128 = 86_400_000_000_000;
fn split_wall(ns: i128) -> Result<([i64; 3], i128), Error> {
    let ordinal = i64::try_from(ns.div_euclid(NS_DAY) + 719_163)
        .map_err(|_| Error::Capacity("calendar day exceeds native range"))?;
    let date = crate::calendar::from_ordinal(ordinal).map_err(Error::Capacity)?;
    Ok((date, ns.rem_euclid(NS_DAY)))
}

fn compose_wall(date: [i64; 3], clock: i128) -> Result<i128, Error> {
    let [year, month, day] = date;
    let ordinal = crate::calendar::checked_ordinal(year, month, day).map_err(Error::Capacity)?;
    Ok((i128::from(ordinal) - 719_163) * NS_DAY + clock)
}

pub(crate) fn fields(ns: i128) -> Result<[i64; 8], Error> {
    let (date, clock) = split_wall(ns)?;
    Ok([
        date[0],
        date[1],
        date[2],
        (clock / 3_600_000_000_000) as i64,
        (clock / 60_000_000_000 % 60) as i64,
        (clock / 1_000_000_000 % 60) as i64,
        (clock / 1000 % 1_000_000) as i64,
        (clock % 1000) as i64,
    ])
}
pub(crate) fn nanos(f: [i64; 8]) -> Result<i128, Error> {
    let clock = ((i128::from(f[3]) * 60 + i128::from(f[4])) * 60 + i128::from(f[5]))
        * 1_000_000_000
        + i128::from(f[6]) * 1000
        + i128::from(f[7]);
    compose_wall([f[0], f[1], f[2]], clock)
}

pub(crate) fn transform(
    wall: i128,
    kind: &str,
    get: impl Fn(usize) -> Option<i64>,
) -> Result<i128, Error> {
    if matches!(kind, "replace" | "adjust") {
        let mut f = fields(wall)?;
        for (i, field) in f.iter_mut().enumerate() {
            if let Some(value) = get(i) {
                *field = value;
            }
        }
        if get(6).is_some() && get(7).is_none() {
            f[7] = 0;
        }
        let last = crate::calendar::days_in_month(f[0], f[1]);
        if f[2] > last {
            if kind == "replace" {
                return Err(Error::Value(format!(
                    "day {} is invalid for year {} and month {}",
                    f[2], f[0], f[1]
                )));
            }
            f[2] = last;
        }
        return nanos(f);
    }
    let (date, source_clock) = split_wall(wall)?;
    let required = |i| get(i).ok_or(Error::Capacity("required component was not prepared"));
    let (months, days, clock_delta, month, day) = if matches!(kind, "add" | "sub") {
        let sign = if kind == "sub" { -1 } else { 1 };
        let months = (i128::from(required(0)?) * 12
            + i128::from(required(1)?) * 3
            + i128::from(required(2)?))
            * sign;
        let days = (i128::from(required(3)?) * 7 + i128::from(required(4)?)) * sign;
        let clock = ((((i128::from(required(5)?) * 60 + i128::from(required(6)?)) * 60
            + i128::from(required(7)?))
            * 1000
            + i128::from(required(8)?))
            * 1000
            + i128::from(required(9)?))
            * 1000
            + i128::from(required(10)?);
        (months, days, clock * sign, None, None)
    } else {
        let offset = i128::from(required(0)?);
        match kind {
            "year" => (offset * 12, 0, 0, get(1), get(2)),
            "quarter" => (
                offset * 3,
                0,
                0,
                get(1).map(|v| (date[1] - 1) / 3 * 3 + v),
                get(2),
            ),
            "month" => (offset, 0, 0, None, get(1)),
            "weekday" => {
                let ordinal = crate::calendar::checked_ordinal(date[0], date[1], date[2])
                    .map_err(Error::Capacity)?;
                (
                    0,
                    offset * 7 + get(1).map_or(0, |v| i128::from(v - (ordinal - 1).rem_euclid(7))),
                    0,
                    None,
                    None,
                )
            }
            "day" => (0, offset, 0, None, None),
            _ => return Err(Error::Capacity("unknown calendar transform")),
        }
    };
    let moved =
        crate::calendar::move_date(date, months, days, month, day).map_err(Error::Capacity)?;
    compose_wall(moved, source_clock)?
        .checked_add(clock_delta)
        .ok_or(Error::Capacity("calendar clock increment overflow"))
}

#[cfg(test)]
mod tests {
    #[test]
    fn local_field_math_is_native_and_keeps_exact_nanoseconds() {
        std::thread::spawn(|| {
            let source = super::nanos([2024, 1, 31, 12, 0, 0, 123456, 789]).unwrap();
            let shifted = super::transform(source, "month", |i| [Some(1), None][i]).unwrap();
            assert_eq!(
                super::fields(shifted).unwrap(),
                [2024, 2, 29, 12, 0, 0, 123456, 789]
            );
            let leap = super::nanos([2024, 2, 29, 12, 0, 0, 0, 0]).unwrap();
            let args = [1, 0, -12, 0, 0, 0, 0, 0, 0, 1, -1000];
            assert_eq!(
                super::transform(leap, "add", |i| Some(args[i])).unwrap(),
                leap
            );
        })
        .join()
        .unwrap();
    }
}
