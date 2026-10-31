//! Shared pure calendar facts; container, validity and timezone are adapters.
const DAY: i128 = 86_400_000_000_000;
#[derive(Debug)]
pub(crate) enum Error {
    Capacity(&'static str),
    Internal(&'static str),
}
pub(crate) fn iso_at(year: i64, ordinal: i64) -> Result<[i64; 3], Error> {
    let start = crate::calendar::checked_ordinal(year, 1, 1).map_err(Error::Capacity)?;
    let weekday = (ordinal - 1).rem_euclid(7) + 1;
    let mut week = (ordinal - start + 1 - weekday + 10).div_euclid(7);
    let mut iso_year = year;
    if week < 1 {
        iso_year = year
            .checked_sub(1)
            .ok_or(Error::Capacity("ISO year overflow"))?;
        week = 52 + i64::from(long_year(iso_year)?);
    } else if week == 53 && !long_year(year)? {
        iso_year = year
            .checked_add(1)
            .ok_or(Error::Capacity("ISO year overflow"))?;
        week = 1;
    }
    Ok([iso_year, week, weekday])
}
pub(crate) fn long_year(year: i64) -> Result<bool, Error> {
    let start = crate::calendar::checked_ordinal(year, 1, 1).map_err(Error::Capacity)?;
    let weekday = (start - 1).rem_euclid(7);
    Ok(weekday == 3 || (weekday == 2 && crate::calendar::leap(year)))
}
fn leap_count(year: i64) -> i128 {
    let before = i128::from(year) - 1;
    before.div_euclid(4) - before.div_euclid(100) + before.div_euclid(400)
}
pub(crate) fn fact<const Q: u8>(
    wall: i128,
    target: Option<i64>,
    cached: &mut Option<(i64, [i64; 3])>,
) -> Result<i64, Error> {
    // Scalar clock and weekday requests need no full calendar decomposition.
    let clock = wall.rem_euclid(DAY);
    match Q {
        10 => return Ok((clock / 1_000_000 % 1000) as i64),
        23 => return Ok((clock / 3_600_000_000_000) as i64),
        24 => return Ok((clock / 60_000_000_000 % 60) as i64),
        25 => return Ok((clock / 1_000_000_000 % 60) as i64),
        26 => return Ok((clock / 1000 % 1_000_000) as i64),
        27 => return Ok((clock % 1000) as i64),
        _ => {}
    }
    let ordinal = i64::try_from(wall.div_euclid(DAY) + 719_163)
        .map_err(|_| Error::Capacity("calendar day overflow"))?;
    if Q == 2 || Q == 28 {
        return Ok((ordinal - 1).rem_euclid(7) + i64::from(Q == 2));
    }
    if Q == 103 {
        return Ok(i64::from(Some((ordinal - 1).rem_euclid(7)) == target));
    }
    let [year, month, day] = match *cached {
        Some((previous, fields)) if previous == ordinal => fields,
        _ => {
            let fields = crate::calendar::from_ordinal(ordinal).map_err(Error::Capacity)?;
            *cached = Some((ordinal, fields));
            fields
        }
    };
    let start = || crate::calendar::checked_ordinal(year, 1, 1).map_err(Error::Capacity);
    let quarter = (month - 1) / 3 * 3 + 1;
    let month_start = || crate::calendar::checked_ordinal(year, month, 1).map_err(Error::Capacity);
    let quarter_start =
        || crate::calendar::checked_ordinal(year, quarter, 1).map_err(Error::Capacity);
    Ok(match Q {
        0..=2 => iso_at(year, ordinal)?[usize::from(Q)],
        3 => 365 + i64::from(crate::calendar::leap(year)),
        4 => start()? - 1,
        5 => (quarter..quarter + 3)
            .map(|m| crate::calendar::days_in_month(year, m))
            .sum(),
        6 => quarter_start()? - start()?,
        7 => ordinal - quarter_start()? + 1,
        8 => month_start()? - start()?,
        9 | 22 => day,
        11 => i64::try_from(
            (leap_count(year) - leap_count(target.ok_or(Error::Internal("missing year target"))?))
                .abs(),
        )
        .map_err(|_| Error::Capacity("leap count overflow"))?,
        20 | 200 => year,
        21 => month,
        29 => ordinal - start()? + 1,
        30 => crate::calendar::days_in_month(year, month),
        31 => (month - 1) / 3 + 1,
        100 => i64::from(Some(year) == target),
        101 => i64::from(Some((month - 1) / 3 + 1) == target),
        102 => i64::from(Some(month) == target),
        104 => i64::from(Some(day) == target),
        105 => i64::from(long_year(year)?),
        109 => i64::from(crate::calendar::leap(year)),
        _ => return Err(Error::Internal("unknown calendar fact")),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn signed_iso_and_direct_facts_run_without_python() {
        std::thread::spawn(|| {
            let day = crate::calendar::ordinal(2021, 1, 1);
            assert_eq!(iso_at(2021, day).unwrap(), [2020, 53, 5]);
            let zero = crate::calendar::ordinal(0, 1, 4);
            assert_eq!(iso_at(0, zero).unwrap(), [0, 1, 2]);
            let mut memo = None;
            assert_eq!(fact::<28>(-1, None, &mut memo).unwrap(), 2);
            assert!(memo.is_none());
            assert_eq!(fact::<27>(-1, None, &mut memo).unwrap(), 999);
            assert!(memo.is_none());
        })
        .join()
        .unwrap();
    }
}
