//! One-time public/source numeric preparation for the exact Delta value.

use super::fixed::{FixedNsAccumulator, round_scaled};
use super::value::{AbsoluteField, AbsoluteFields, DeltaValue, NS_PER_DAY, ValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFloat, PyInt, PyString, PyTuple};

pub(crate) const NAMES: [&str; 21] = [
    "years",
    "quarters",
    "months",
    "weeks",
    "days",
    "hours",
    "minutes",
    "seconds",
    "milliseconds",
    "microseconds",
    "year",
    "month",
    "day",
    "weekday",
    "hour",
    "minute",
    "second",
    "millisecond",
    "microsecond",
    "nanoseconds",
    "nanosecond",
];

const FIXED: [(usize, u64); 8] = [
    (3, 604_800_000_000_000),
    (4, 86_400_000_000_000),
    (5, 3_600_000_000_000),
    (6, 60_000_000_000),
    (7, 1_000_000_000),
    (8, 1_000_000),
    (9, 1000),
    (19, 1),
];

/// Match public names once; callbacks and normalization use the captured role.
fn parameter_index(name: &str) -> Option<usize> {
    Some(match name {
        "years" => 0,
        "quarters" => 1,
        "months" => 2,
        "weeks" => 3,
        "days" => 4,
        "hours" => 5,
        "minutes" => 6,
        "seconds" => 7,
        "milliseconds" => 8,
        "microseconds" => 9,
        "year" => 10,
        "month" => 11,
        "day" => 12,
        "weekday" => 13,
        "hour" => 14,
        "minute" => 15,
        "second" => 16,
        "millisecond" => 17,
        "microsecond" => 18,
        "nanoseconds" => 19,
        "nanosecond" => 20,
        _ => return None,
    })
}

/// Lazily prepared fractional contributions. One float uses no heap scratch;
/// multiple actual fractional contributions share one bounded exact accumulator.
#[derive(Default)]
pub(crate) struct FixedFractions {
    single: Option<(f64, u64)>,
    multiple: Option<Box<FixedNsAccumulator>>,
}

impl FixedFractions {
    fn add(&mut self, number: f64, coefficient: u64) -> Result<(), ValueError> {
        if number == 0.0 {
            return Ok(());
        }
        if let Some(multiple) = self.multiple.as_mut() {
            return multiple.add(number, coefficient);
        }
        if let Some((old, old_coefficient)) = self.single.take() {
            let mut multiple = Box::new(FixedNsAccumulator::new());
            multiple.add(old, old_coefficient)?;
            multiple.add(number, coefficient)?;
            self.multiple = Some(multiple);
        } else {
            self.single = Some((number, coefficient));
        }
        Ok(())
    }

    fn finish(self, integer_ns: i128) -> Result<i128, ValueError> {
        if let Some(multiple) = self.multiple {
            multiple.rounded(integer_ns)
        } else if let Some((number, coefficient)) = self.single {
            round_scaled(number, coefficient, integer_ns)
        } else {
            Ok(integer_ns)
        }
    }
}

/// A completely interpreted foreign source, already using the new exact value.
pub(crate) struct RelativeFields(pub(crate) DeltaValue);

/// Convert a native preparation error at the Python entry boundary.
pub(crate) fn python_error(error: ValueError) -> PyErr {
    match error {
        ValueError::Overflow => {
            crate::error_context::overflow("integer overflow in Delta normalization")
        }
        ValueError::NotANumber => {
            crate::error_context::value_error("Delta duration must be finite; NaN is not accepted")
        }
        ValueError::AbsoluteRange(field) => crate::error_context::value_error(format!(
            "Delta absolute field {field:?} is outside its legal range"
        )),
        ValueError::NonCanonical => {
            crate::error_context::value_error("Delta state must contain canonical fields")
        }
    }
}

#[inline]
fn coefficient(index: usize) -> Option<u64> {
    match index {
        3..=9 => Some(FIXED[index - 3].1),
        19 => Some(1),
        _ => None,
    }
}

/// Read relative input once. Source adapters retain their meaningful bool role;
/// the public constructor rejects bool before calling this helper.
pub(crate) fn relative_input(
    value: &Bound<'_, PyAny>,
    index: usize,
    fraction: &mut FixedFractions,
) -> PyResult<i64> {
    if value.is_instance_of::<PyInt>() {
        return super::converted_integer(value);
    }
    if let Some(coefficient) = coefficient(index)
        && crate::numeric::supported_float(value)
    {
        let number = if let Ok(number) = value.cast::<PyFloat>() {
            number.value()
        } else {
            crate::numeric::float_value(value)?
        };
        if number.is_nan() {
            return Err(python_error(ValueError::NotANumber));
        }
        if !number.is_finite()
            || !(-9_223_372_036_854_775_808.0..9_223_372_036_854_775_808.0).contains(&number)
        {
            return Err(python_error(ValueError::Overflow));
        }
        let whole = number.trunc();
        fraction
            .add(number - whole, coefficient)
            .map_err(python_error)?;
        return Ok(whole as i64);
    }
    super::index_integer(value)
}

fn absolute_input(value: &Bound<'_, PyAny>, index: usize) -> PyResult<i64> {
    if value.is_none() {
        return Ok(-1);
    }
    // Qualify the public role before conversion. A genuine index callback still
    // runs once and keeps its original exception; unsupported inputs get the
    // established field-specific explanation rather than a generic cast error.
    if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) == 0 } {
        return Err(crate::error_context::type_error(format!(
            "{} must be an integer or None",
            NAMES[index]
        )));
    }
    absolute_number(super::index_integer(value)?, index)
}

/// Validate the same absolute role after an already qualified integer read.
fn absolute_number(number: i64, index: usize) -> PyResult<i64> {
    let maximum = match index {
        10 => 9999,
        11 => 12,
        12 => 31,
        13 => 6,
        14 => 23,
        15 | 16 => 59,
        17 | 20 => 999,
        18 => 999_999,
        _ => unreachable!("absolute input index"),
    };
    if index <= 12 {
        if number <= 0 {
            return Err(crate::error_context::value_error(format!(
                "{} must be a positive integer or None",
                NAMES[index]
            )));
        }
        Ok(number.min(maximum))
    } else if !(0..=maximum).contains(&number) {
        Err(crate::error_context::value_error(format!(
            "{} must be from 0 through {maximum}, inclusive, or None",
            NAMES[index]
        )))
    } else {
        Ok(number)
    }
}

/// Canonicalize one integer amount directly into the exact ns representation.
/// No temporary21-field binding or fractional scratch is needed on this path.
fn single_integer(index: usize, number: i64) -> PyResult<DeltaValue> {
    let mut value = DeltaValue::ZERO;
    match index {
        0 => value.years = number,
        1 => {
            value.years = number.div_euclid(4);
            value.months = (number.rem_euclid(4) * 3) as u8;
        }
        2 => {
            value.years = number.div_euclid(12);
            value.months = number.rem_euclid(12) as u8;
        }
        3 => {
            value.days = number
                .checked_mul(7)
                .ok_or_else(|| python_error(ValueError::Overflow))?
        }
        4 => value.days = number,
        5..=9 | 19 => {
            let per_day = match index {
                5 => 24,
                6 => 1440,
                7 => 86_400,
                8 => 86_400_000,
                9 => 86_400_000_000,
                _ => 86_400_000_000_000,
            };
            value.days = number.div_euclid(per_day);
            value.clock_ns = number.rem_euclid(per_day) as u64 * coefficient(index).unwrap();
        }
        10..=18 | 20 => {
            let number = absolute_number(number, index)?;
            let (field, number) = match index {
                17 => (AbsoluteField::Microsecond, number * 1000),
                18 => (AbsoluteField::Microsecond, number),
                20 => (AbsoluteField::Nanosecond, number),
                _ => (AbsoluteField::ALL[index - 10], number),
            };
            value
                .absolute
                .set(field, Some(number))
                .map_err(python_error)?;
        }
        _ => unreachable!("validated public parameter role"),
    }
    Ok(value)
}

/// Complete a single proven primitive value without executing any user hook.
fn single_primitive(value: &Bound<'_, PyAny>, index: usize) -> Option<PyResult<DeltaValue>> {
    if value.is_exact_instance_of::<PyInt>() {
        return Some(
            super::converted_integer(value).and_then(|number| single_integer(index, number)),
        );
    }
    if (index < 10 || index == 19)
        && value.is_instance_of::<PyFloat>()
        && coefficient(index).is_some()
    {
        return Some((|| {
            let mut fraction = FixedFractions::default();
            let number = relative_input(value, index, &mut fraction)?;
            let ns = fraction
                .finish(i128::from(number) * i128::from(coefficient(index).unwrap()))
                .map_err(python_error)?;
            DeltaValue::from_totals(0, ns, AbsoluteFields::EMPTY).map_err(python_error)
        })());
    }
    if index >= 10 && index != 19 && value.is_none() {
        return Some(Ok(DeltaValue::ZERO));
    }
    None
}

fn normalize(whole: [i64; 21], fraction: FixedFractions) -> PyResult<DeltaValue> {
    let months = i128::from(whole[0]) * 12 + i128::from(whole[1]) * 3 + i128::from(whole[2]);
    let fixed_ns = FIXED
        .iter()
        .map(|&(index, coefficient)| i128::from(whole[index]) * i128::from(coefficient))
        .sum();
    let fixed_ns = fraction.finish(fixed_ns).map_err(python_error)?;
    let mut absolute = AbsoluteFields::EMPTY;
    for (index, field) in AbsoluteField::ALL[..7].iter().copied().enumerate() {
        let number = whole[index + 10];
        absolute
            .set(field, (number != -1).then_some(number))
            .map_err(python_error)?;
    }
    let microsecond = if whole[17] == -1 {
        whole[18]
    } else {
        whole[17] * 1000 + if whole[18] == -1 { 0 } else { whole[18] % 1000 }
    };
    absolute
        .set(
            AbsoluteField::Microsecond,
            (microsecond != -1).then_some(microsecond),
        )
        .map_err(python_error)?;
    absolute
        .set(
            AbsoluteField::Nanosecond,
            (whole[20] != -1).then_some(whole[20]),
        )
        .map_err(python_error)?;
    DeltaValue::from_totals(months, fixed_ns, absolute).map_err(python_error)
}

/// Bind all names before conversion, then read each provided argument in its
/// established declaration order, retaining its owner across actual callbacks.
pub(crate) fn construct(
    args: &Bound<'_, PyTuple>,
    kwargs: Option<&Bound<'_, PyDict>>,
) -> PyResult<DeltaValue> {
    if args.is_empty()
        && let Some(kwargs) = kwargs.filter(|values| values.len() == 1)
        && let Some((key, value)) = kwargs.iter().next()
        && let Some(index) = parameter_index(key.cast::<PyString>()?.to_str()?)
        && let Some(result) = single_primitive(&value, index)
    {
        return result.map_err(|error| {
            crate::error_context::argument(args.py(), error, "Delta", NAMES[index], &value)
        });
    }
    if args.len() > 19 {
        return Err(crate::error_context::type_error(format!(
            "Delta() takes at most 19 positional arguments ({} given)",
            args.len()
        )));
    }
    let mut values: [Option<Bound<'_, PyAny>>; 21] = std::array::from_fn(|_| None);
    for (index, value) in args.iter().enumerate() {
        values[index] = Some(value);
    }
    if let Some(kwargs) = kwargs {
        for (key, value) in kwargs.iter() {
            let name = key.cast::<PyString>()?.to_str()?;
            let index = parameter_index(name).ok_or_else(|| {
                crate::error_context::type_error(format!(
                    "Delta() got an unexpected keyword argument '{name}'"
                ))
            })?;
            if values[index].is_some() {
                return Err(crate::error_context::type_error(format!(
                    "Delta() got multiple values for keyword argument '{name}'"
                )));
            }
            values[index] = Some(value);
        }
    }
    let mut whole = [0; 21];
    whole[10..19].fill(-1);
    whole[20] = -1;
    let mut fraction = FixedFractions::default();
    for (index, value) in values.iter().enumerate() {
        let Some(value) = value else {
            continue;
        };
        let mut read = || {
            if crate::numeric::is_bool(value) {
                return Err(crate::error_context::type_error(
                    "boolean values are not accepted as numeric fields",
                ));
            }
            if index < 10 || index == 19 {
                relative_input(value, index, &mut fraction)
            } else {
                absolute_input(value, index)
            }
        };
        whole[index] = read().map_err(|error| {
            crate::error_context::argument(value.py(), error, "Delta", NAMES[index], value)
        })?;
    }
    normalize(whole, fraction)
}

/// Interpret dateutil's fifteen source fields into the new Delta value. This is
/// its external source format, not a legacy Delta storage/serialization layer.
pub(crate) fn normalize_relative_fields(
    fields: [i64; 15],
    fraction: FixedFractions,
) -> PyResult<RelativeFields> {
    let mut whole = [0; 21];
    whole[10..19].fill(-1);
    whole[20] = -1;
    for (field, parameter) in [0, 2, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18]
        .into_iter()
        .enumerate()
    {
        whole[parameter] = fields[field];
    }
    // Source adaptation has already validated its distinct absolute semantics.
    normalize(whole, fraction).map(RelativeFields)
}

/// Prepare an integer-only fixed span without a public Python constructor.
pub(crate) fn fixed_duration(days: i64, seconds: i64, microseconds: i64) -> PyResult<DeltaValue> {
    let total = i128::from(days) * NS_PER_DAY
        + i128::from(seconds) * 1_000_000_000
        + i128::from(microseconds) * 1000;
    DeltaValue::from_totals(0, total, AbsoluteFields::EMPTY).map_err(python_error)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> [i64; 21] {
        let mut fields = [0; 21];
        fields[10..19].fill(-1);
        fields[20] = -1;
        fields
    }

    #[test]
    fn negative_microsecond_carries_to_previous_day() {
        let mut fields = defaults();
        fields[9] = -1;
        assert_eq!(
            &normalize(fields, FixedFractions::default())
                .unwrap()
                .core17()[2..8],
            &[-1, 23, 59, 59, 999_999, 0]
        );
    }

    #[test]
    fn negative_month_carries_to_previous_year() {
        let mut fields = defaults();
        fields[2] = -1;
        assert_eq!(
            &normalize(fields, FixedFractions::default())
                .unwrap()
                .core17()[..2],
            &[-1, 11]
        );
    }

    #[test]
    fn absolute_millisecond_replaces_only_that_part() {
        let mut fields = defaults();
        fields[17] = 2;
        fields[18] = 123_456;
        let value = normalize(fields, FixedFractions::default()).unwrap();
        assert_eq!(value.absolute.get(AbsoluteField::Microsecond), Some(2456));
        assert_eq!(value.absolute.get(AbsoluteField::Nanosecond), None);
    }

    #[test]
    fn wide_intermediate_is_normalized_before_final_range_check() {
        let mut fields = defaults();
        fields[8] = i64::MAX;
        fields[9] = i64::MIN;
        let result = normalize(fields, FixedFractions::default()).unwrap();
        let expected_ns = (i128::from(i64::MAX) * 1000 + i128::from(i64::MIN)) * 1000;
        assert_eq!(i128::from(result.days), expected_ns.div_euclid(NS_PER_DAY));
        assert_eq!(
            i128::from(result.clock_ns),
            expected_ns.rem_euclid(NS_PER_DAY)
        );
        assert!(
            DeltaValue::from_totals(
                0,
                i128::from(i64::MAX) * 7 * NS_PER_DAY,
                AbsoluteFields::EMPTY
            )
            .is_err()
        );
        assert!(
            DeltaValue::from_totals(i128::from(i64::MAX) * 12 + 12, 0, AbsoluteFields::EMPTY)
                .is_err()
        );
    }
}
