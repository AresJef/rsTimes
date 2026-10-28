//! Calendar role resolution and explicit-default century completion.
use super::fields::{Fields, ParseError, ParseResult, Policy};
use crate::calendar;

/// Resolve the three ordered calendar fields using the frozen precedence.
///
/// A short year requires the caller-provided default year; never read the clock.
#[inline]
pub(super) fn resolve<P: Policy>(
    f: &mut Fields<P>,
    yearfirst: bool,
    dayfirst: bool,
    reference_year: Option<i32>,
) -> ParseResult<bool> {
    if f.resolved {
        return Ok(f.valid());
    }
    // Clock-only ordinary input has no calendar slots or conflict history.
    // Its missing date is supplied by build; calendar role resolution cannot
    // change any field. Keep the resolved flag used by error representations.
    if !f.strict() && f.idx < 0 {
        f.resolved = true;
        return Ok(f.valid());
    }
    // An unambiguous full year and month need neither century conversion nor
    // the general three-field resolver. Invalid values and short years retain
    // the complete checked path. A missing day still comes from build/default.
    if !f.strict() && f.idx == 1 && f.century_specified && f.doy == -1 {
        let [a, b, _] = f.ymd;
        let pair = match (f.yidx, f.midx) {
            (0, 1) => Some((a, b)),
            (1, 0) => Some((b, a)),
            (0, -1) if a > 31 || (b == 2 && a > 29) => Some((a, b)),
            _ => None,
        };
        match pair {
            Some((year, month)) if (1..=9999).contains(&year) && (1..=12).contains(&month) => {
                f.year = year;
                f.month = month;
                f.day = -1;
                f.resolved = true;
                return Ok(true);
            }
            _ => {}
        }
    }
    resolve_unresolved(f, yearfirst, dayfirst, reference_year)
}

fn resolve_unresolved<P: Policy>(
    f: &mut Fields<P>,
    yearfirst: bool,
    dayfirst: bool,
    reference_year: Option<i32>,
) -> ParseResult<bool> {
    let slots = f.ymd_slots_filled();
    let roles = f.ymd_roles_resolved();
    let (y, m, d) = (f.yidx, f.midx, f.didx);
    let [a, b, c] = f.ymd;
    let get = |idx: i32| f.ymd[idx as usize];
    if slots == roles && roles > 1 {
        f.year = if y != -1 { get(y) } else { -1 };
        f.month = if m != -1 { get(m) } else { -1 };
        f.day = if d != -1 { get(d) } else { -1 };
    } else if slots == 1 {
        if y != -1 {
            f.year = a;
        } else if m != -1 {
            f.month = a;
        } else {
            f.day = a;
        }
    } else if slots == 2 {
        if m != -1 {
            if m == 0 {
                if b > 31 || (a == 2 && b > 29) {
                    f.month = a;
                    f.year = b;
                } else {
                    f.month = a;
                    f.day = b;
                }
            } else if a > 31 || (b == 2 && a > 29) {
                f.year = a;
                f.month = b;
            } else {
                f.day = a;
                f.month = b;
            }
        } else if a > 31 || (b == 2 && a > 29) {
            f.year = a;
            f.month = b;
        } else if b > 31 || (a == 2 && b > 29) {
            f.month = a;
            f.year = b;
        } else if dayfirst && (1..=12).contains(&b) {
            f.day = a;
            f.month = b;
        } else {
            f.month = a;
            f.day = b;
        }
    } else if slots == 3 {
        if roles == 2 {
            if m != -1 {
                f.month = get(m);
                if y != -1 {
                    f.year = get(y);
                    f.day = get(3 - y - m);
                } else {
                    f.day = get(d);
                    f.year = get(3 - m - d);
                }
            } else {
                f.year = get(y);
                f.day = get(d);
                f.month = get(3 - y - d);
            }
        } else if m == 0 {
            f.month = a;
            if b > 31 {
                f.year = b;
                f.day = c;
            } else {
                f.day = b;
                f.year = c;
            }
        } else if m == 1 {
            f.month = b;
            if a > 31 || (yearfirst && (1..=31).contains(&c)) {
                f.year = a;
                f.day = c;
            } else {
                f.day = a;
                f.year = c;
            }
        } else if m == 2 {
            f.month = c;
            if b > 31 {
                f.day = a;
                f.year = b;
            } else {
                f.year = a;
                f.day = b;
            }
        } else if y == 1 {
            f.year = b;
            if a > 12 || dayfirst {
                f.day = a;
                f.month = c;
            } else {
                f.month = a;
                f.day = c;
            }
        } else if y == 2 {
            f.year = c;
            if a > 12 || (dayfirst && (1..=12).contains(&b)) {
                f.day = a;
                f.month = b;
            } else {
                f.month = a;
                f.day = b;
            }
        } else if a > 31 || y == 0 || (yearfirst && (1..=12).contains(&b) && (1..=31).contains(&c))
        {
            f.year = a;
            if dayfirst && (1..=12).contains(&c) {
                f.day = b;
                f.month = c;
            } else {
                f.month = b;
                f.day = c;
            }
        } else if a > 12 || (dayfirst && (1..=12).contains(&b)) {
            f.day = a;
            f.month = b;
            f.year = c;
        } else {
            f.month = a;
            f.day = b;
            f.year = c;
        }
    }
    f.year = complete_year(f.year, f.century_specified, f.strict(), reference_year)?;
    if f.month_override != -1 {
        let month = f.month_override;
        if f.strict() && f.month != -1 && f.month != month {
            return Err(Fields::<P>::conflict("month", f.month, month));
        }
        f.month = month;
    }
    if f.doy != -1 && f.year != -1 {
        let mut day = f.bounded(
            "day-of-year",
            i64::from(f.doy),
            1,
            365 + i32::from(calendar::leap(i64::from(f.year))),
        )?;
        let mut month = 1;
        while day > calendar::days_in_month(i64::from(f.year), i64::from(month)) as i32 {
            day -= calendar::days_in_month(i64::from(f.year), i64::from(month)) as i32;
            month += 1;
        }
        f.month = month;
        f.day = day;
    }
    if f.month != -1 && !(1..=12).contains(&f.month) {
        f.month = f.bounded("month", i64::from(f.month), 1, 12)?;
    }
    if f.day != -1 && !(1..=31).contains(&f.day) {
        f.day = f.bounded("day", i64::from(f.day), 1, 31)?;
    }
    if let Some(prior_dates) = f.take_prior_dates() {
        for snapshot in prior_dates {
            let mut prior = snapshot.into_fields::<P>();
            resolve(&mut prior, yearfirst, dayfirst, reference_year)?;
            for (name, old, new) in [
                ("year", prior.year, f.year),
                ("month", prior.month, f.month),
                ("day", prior.day, f.day),
            ] {
                if old != -1 && new != -1 && old != new {
                    return Err(Fields::<P>::conflict(name, old, new));
                }
            }
            if prior.is_year_set() && prior.month > 0 && prior.day > 0 {
                let last =
                    calendar::days_in_month(i64::from(prior.year), i64::from(prior.month)) as i32;
                prior.bounded("day", i64::from(prior.day), 1, last)?;
            }
        }
    }
    f.resolved = true;
    Ok(f.valid())
}

/// Complete a written short year before ISO conversion, sharing the normal rule.
pub(super) fn complete_year(
    mut value: i32,
    century_specified: bool,
    strict: bool,
    reference_year: Option<i32>,
) -> ParseResult<i32> {
    if !century_specified && (0..100).contains(&value) {
        if strict {
            return Err(ParseError::Value(format!(
                "Two-digit year '{:02}' is not allowed when strict=True. Use a four-digit year. To interpret a two-digit year, set strict=False and provide a date or datetime as default.",
                value
            )));
        }
        let local_year = reference_year.ok_or_else(|| ParseError::Value(format!(
            "Two-digit year '{:02}' requires default when strict=False. Pass a date or datetime whose year defines the reference window, or use a four-digit year.", value
        )))?;
        let local_year = i64::from(local_year);
        let mut year = i64::from(value) + local_year.div_euclid(100) * 100;
        if year >= local_year + 50 {
            year -= 100;
        } else if year < local_year - 50 {
            year += 100;
        }
        value = i32::try_from(year).map_err(|_| {
            ParseError::Overflow(
                "two-digit year reference window exceeds native integer range".into(),
            )
        })?;
    }
    Ok(value)
}
