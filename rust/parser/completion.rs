//! Pure field completion shared by Python results and native column workers.
use super::fields::{Fields, ParseError, ParseResult, Policy};

/// Fill only missing YMD, fit an inherited day, and enforce the existing strict
/// weekday rule. Target date capacity and zone existence belong to the exit.
#[inline(always)]
pub(crate) fn complete<P: Policy>(
    f: &Fields<P>,
    default: Option<[i32; 3]>,
) -> ParseResult<[i32; 7]> {
    let yy = if f.is_year_set() {
        f.year
    } else if let Some(date) = default {
        date[0]
    } else {
        return Err(ParseError::Value(
            "year is missing; provide a complete default date".into(),
        ));
    };
    let mm = if f.is_month_set() {
        f.month
    } else if let Some(date) = default {
        date[1]
    } else {
        return Err(ParseError::Value(
            "month is missing; provide a complete default date".into(),
        ));
    };
    let dd = if f.is_day_set() {
        f.day
    } else if let Some(date) = default {
        date[2]
    } else {
        return Err(ParseError::Value(
            "day is missing; provide a complete default date".into(),
        ));
    };
    let dd = if dd > 28 {
        let last = crate::calendar::days_in_month(i64::from(yy), i64::from(mm)) as i32;
        if f.strict() && f.is_day_set() && dd > last {
            return Err(ParseError::Value(format!(
                "day={dd} is invalid for {yy:04}-{mm:02}; expected 1 through {last}, inclusive"
            )));
        }
        dd.min(last)
    } else {
        dd
    };
    let (mut yy, mut mm, mut dd) = (yy, mm, dd);
    if f.is_weekday_set() {
        let ordinal =
            crate::calendar::ordinal(i64::from(yy), i64::from(mm.clamp(1, 12)), i64::from(dd));
        let weekday = (ordinal - 1).rem_euclid(7) as i32;
        if weekday != f.weekday {
            if f.strict() && f.is_year_set() && f.is_month_set() && f.is_day_set() {
                return Err(ParseError::Value(format!(
                    "conflicting weekday: {yy:04}-{mm:02}-{dd:02} has weekday {weekday}, not {}",
                    f.weekday
                )));
            }
            let adjustment = f.weekday.checked_sub(weekday).ok_or_else(|| {
                ParseError::Overflow(
                    "weekday adjustment exceeds the supported integer range".into(),
                )
            })?;
            let date = crate::calendar::from_ordinal(ordinal + i64::from(adjustment))
                .map_err(|message| ParseError::Overflow(message.into()))?;
            yy = i32::try_from(date[0]).map_err(|_| {
                ParseError::Overflow("weekday adjustment exceeds the native year range".into())
            })?;
            mm = date[1] as i32;
            dd = date[2] as i32;
        }
    }
    Ok([
        yy,
        mm,
        dd,
        if f.is_hour_set() { f.hour } else { 0 },
        if f.is_minute_set() { f.minute } else { 0 },
        if f.is_second_set() { f.second } else { 0 },
        if f.is_microsecond_set() {
            f.microsecond
        } else {
            0
        },
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::fields::{Lenient, Strict};

    #[test]
    fn incomplete_and_invalid_fields_return_native_errors_without_python() {
        let mut fields = Fields::<Lenient>::new();
        assert!(matches!(complete(&fields, None), Err(ParseError::Value(_))));
        fields.year = 2024;
        fields.month = 2;
        fields.day = 30;
        assert_eq!(complete(&fields, None).unwrap(), [2024, 2, 29, 0, 0, 0, 0]);
        let mut strict = Fields::<Strict>::new();
        strict.year = 2024;
        strict.month = 2;
        strict.day = 30;
        assert!(matches!(complete(&strict, None), Err(ParseError::Value(_))));
        strict.day = -1;
        assert_eq!(
            complete(&strict, Some([2000, 1, 31])).unwrap(),
            [2024, 2, 29, 0, 0, 0, 0]
        );
    }
}
