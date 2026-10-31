//! One date-range sequence algorithm; target containers own localization/limits.
use crate::epoch::Unit;
use crate::range_calendar::{Frequency, Kind};
#[derive(Debug)]
pub(crate) enum Error {
    Value(&'static str),
    Capacity(&'static str),
}
pub(crate) struct Input<'a> {
    pub(crate) start: Option<i128>,
    pub(crate) end: Option<i128>,
    pub(crate) periods: Option<usize>,
    pub(crate) frequency: Option<&'a Frequency>,
    pub(crate) unit: Unit,
    pub(crate) inclusive: (bool, bool),
    pub(crate) known_start: Option<i128>,
    pub(crate) known_end: Option<i128>,
}
pub(crate) struct Trim {
    pub(crate) left: usize,
    pub(crate) right: usize,
}
pub(crate) fn arity(start: bool, end: bool, periods: bool, frequency: bool) -> Result<(), Error> {
    if usize::from(start) + usize::from(end) + usize::from(periods) + usize::from(frequency) != 3 {
        Err(Error::Value(
            "exactly three of start, end, periods and freq must be specified",
        ))
    } else {
        Ok(())
    }
}
/// Emit in declared order before localization/mask validation and inclusive trim.
pub(crate) fn generate<E: From<Error>>(
    input: Input<'_>,
    mut emit: impl FnMut(i128, bool) -> Result<(), E>,
) -> Result<Trim, E> {
    let Input {
        start,
        end,
        periods,
        frequency,
        unit,
        inclusive: (left, right),
        known_start,
        known_end,
    } = input;
    arity(
        start.is_some(),
        end.is_some(),
        periods.is_some(),
        frequency.is_some(),
    )?;
    if let Some(plan) = frequency {
        let fraction = match plan.kind {
            Kind::Fixed(value) => value,
            _ => plan.offset,
        };
        if fraction.rem_euclid(unit.nanos()) != 0 {
            return Err(Error::Value(
                "frequency cannot be preserved at this unit; choose a finer unit",
            )
            .into());
        }
    }
    let mut length = 0;
    let mut first_value = None;
    let mut last_value = None;
    let mut append = |value, instant| -> Result<(), E> {
        emit(value, instant)?;
        if length == 0 {
            first_value = Some(value);
        }
        last_value = Some(value);
        length += 1;
        Ok(())
    };
    if let Some(frequency) = frequency {
        let instant = matches!(frequency.kind, Kind::Fixed(_));
        let direction = if let Kind::Fixed(step) = frequency.kind {
            if step < 0 { -1 } else { 1 }
        } else {
            frequency.n.signum()
        };
        let mut first = start
            .map(|value| frequency.roll(value, direction))
            .transpose()
            .map_err(Error::Capacity)?;
        let mut last = end;
        if let (Some(value), Some(_)) = (last, periods) {
            last = Some(frequency.roll(value, -direction).map_err(Error::Capacity)?);
        }
        if let Some(length) = periods {
            let offset = i64::try_from(length)
                .map_err(|_| Error::Capacity("period count exceeds native range"))?
                .checked_sub(1)
                .ok_or(Error::Capacity("period count underflow"))?;
            if first.is_none() {
                first = Some(
                    frequency
                        .apply(last.ok_or(Error::Value("end is required"))?, -offset)
                        .map_err(Error::Capacity)?,
                );
            }
            if last.is_none() {
                last = Some(
                    frequency
                        .apply(first.ok_or(Error::Value("start is required"))?, offset)
                        .map_err(Error::Capacity)?,
                );
            }
        }
        let (Some(mut current), Some(last)) = (first, last) else {
            return Err(Error::Value("range requires enough endpoint information").into());
        };
        if periods != Some(0) {
            while if direction > 0 {
                current <= last
            } else {
                current >= last
            } {
                let known = if start == Some(current) {
                    known_start
                } else if end == Some(current) {
                    known_end
                } else {
                    None
                };
                append(known.unwrap_or(current), known.is_some() || instant)?;
                if current == last {
                    break;
                }
                let next = frequency.apply(current, 1).map_err(Error::Capacity)?;
                if (direction > 0 && next <= current) || (direction < 0 && next >= current) {
                    return Err(Error::Value(
                        "frequency does not advance in its declared direction",
                    )
                    .into());
                }
                current = next;
            }
        }
    } else {
        let (Some(first), Some(last), Some(length)) = (start, end, periods) else {
            return Err(Error::Value("freq=None requires start, end and periods").into());
        };
        if first.rem_euclid(unit.nanos()) != 0 || last.rem_euclid(unit.nanos()) != 0 {
            return Err(Error::Value(
                "range endpoints cannot be preserved at this unit; choose a finer unit",
            )
            .into());
        }
        let (first, last) = (
            first.div_euclid(unit.nanos()),
            last.div_euclid(unit.nanos()),
        );
        let delta = last
            .checked_sub(first)
            .ok_or(Error::Capacity("range span exceeds native precision"))?;
        let denominator = length.saturating_sub(1) as i128;
        let (quotient, remainder) = if denominator > 0 {
            (delta.div_euclid(denominator), delta.rem_euclid(denominator))
        } else {
            (0, 0)
        };
        for row in 0..length {
            let value = if length == 1 {
                first
            } else {
                first
                    .checked_add(
                        quotient
                            .checked_mul(row as i128)
                            .and_then(|whole| {
                                remainder.checked_mul(row as i128).and_then(|part| {
                                    whole.checked_add(part.div_euclid(denominator))
                                })
                            })
                            .ok_or(Error::Capacity(
                                "range interpolation exceeds native precision",
                            ))?,
                    )
                    .ok_or(Error::Capacity("range interpolation overflow"))?
            };
            append(
                value
                    .checked_mul(unit.nanos())
                    .ok_or(Error::Capacity("range interpolation overflow"))?,
                true,
            )?;
        }
    }
    let (mut trim_left, mut trim_right) = (0, 0);
    if start == end && start.is_some() {
        if !left && !right {
            trim_left = usize::from(length > 0);
            trim_right = usize::from(length > 1);
        }
    } else {
        if !left && first_value == known_start.or(start) {
            trim_left = usize::from(length > 0);
        }
        if !right && last_value == known_end.or(end) {
            trim_right = usize::from(length > trim_left);
        }
    }
    Ok(Trim {
        left: trim_left,
        right: trim_right,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn signed_interpolation_uses_earlier_integer_lattice_and_zero_cases() {
        for (start, end, want) in [(0, 5, vec![0, 1, 3, 5]), (5, 0, vec![5, 3, 1, 0])] {
            let mut values = Vec::new();
            let result = generate::<Error>(
                Input {
                    start: Some(start),
                    end: Some(end),
                    periods: Some(4),
                    frequency: None,
                    unit: Unit::Nanosecond,
                    inclusive: (true, true),
                    known_start: None,
                    known_end: None,
                },
                |value, instant| {
                    assert!(instant);
                    values.push(value);
                    Ok(())
                },
            );
            assert!(result.is_ok());
            assert_eq!(values, want);
        }
    }
}
