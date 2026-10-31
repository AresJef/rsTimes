//! One-time public/source numeric preparation for the exact Delta value.

use super::fixed::{BinaryTerm, FixedNsAccumulator, round_scaled};
use super::value::{AbsoluteField, AbsoluteFields, DeltaValue, NS_PER_DAY, ValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
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

static KEYWORD_NAMES: PyOnceLock<[Py<PyString>; 21]> = PyOnceLock::new();

/// Prepare module-owned keyword identities once, retaining full text fallback.
pub(crate) fn configure_names(py: Python<'_>) {
    let _ = keyword_names(py);
}

fn keyword_names(py: Python<'_>) -> &[Py<PyString>; 21] {
    KEYWORD_NAMES.get_or_init(py, || NAMES.map(|name| PyString::intern(py, name).unbind()))
}

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

/// Common dyadic sums stay compact; widely separated exponents retain the
/// bounded exact accumulator. Both representations round only once at finish.
#[derive(Default)]
pub(crate) struct FixedFractions {
    state: FractionState,
}

#[derive(Default)]
enum FractionState {
    #[default]
    Empty,
    Single(f64, u64),
    Compact(BinaryTerm),
    Wide(Box<FixedNsAccumulator>),
}

impl FractionState {
    #[inline]
    fn combine(left: BinaryTerm, right: BinaryTerm) -> Result<Self, ValueError> {
        if let Some(sum) = left.combined(right) {
            Ok(Self::Compact(sum))
        } else {
            Self::wide_pair(left, right)
        }
    }

    #[cold]
    #[inline(never)]
    fn wide_pair(left: BinaryTerm, right: BinaryTerm) -> Result<Self, ValueError> {
        let mut wide = Box::new(FixedNsAccumulator::new());
        wide.add_term(left)?;
        wide.add_term(right)?;
        Ok(Self::Wide(wide))
    }
}

impl FixedFractions {
    #[inline]
    fn add(&mut self, number: f64, coefficient: u64) -> Result<(), ValueError> {
        if number == 0.0 {
            return Ok(());
        }
        match &mut self.state {
            FractionState::Empty => self.state = FractionState::Single(number, coefficient),
            FractionState::Single(old, old_coefficient) => {
                self.state = FractionState::combine(
                    BinaryTerm::scaled(*old, *old_coefficient)?,
                    BinaryTerm::scaled(number, coefficient)?,
                )?;
            }
            FractionState::Compact(old) => {
                self.state =
                    FractionState::combine(*old, BinaryTerm::scaled(number, coefficient)?)?;
            }
            FractionState::Wide(wide) => wide.add(number, coefficient)?,
        }
        Ok(())
    }

    #[inline]
    fn finish(self, integer_ns: i128) -> Result<i128, ValueError> {
        match self.state {
            FractionState::Empty => Ok(integer_ns),
            FractionState::Single(number, coefficient) => {
                round_scaled(number, coefficient, integer_ns)
            }
            FractionState::Compact(term) => term.rounded(integer_ns),
            FractionState::Wide(wide) => wide.rounded(integer_ns),
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

/// Finish a single captured argument without rebinding a full parameter table.
/// The primitive path remains first; actual protocols still run exactly once
/// while the caller owns this value, with the same field-specific completion.
fn single_input(value: &Bound<'_, PyAny>, index: usize) -> PyResult<DeltaValue> {
    if let Some(result) = single_primitive(value, index) {
        return result;
    }
    if crate::numeric::is_bool(value) {
        return Err(crate::error_context::type_error(
            "boolean values are not accepted as numeric fields",
        ));
    }
    let mut fraction = FixedFractions::default();
    let number = if index < 10 || index == 19 {
        relative_input(value, index, &mut fraction)?
    } else {
        absolute_input(value, index)?
    };
    if index >= 10 && index != 19 && number == -1 {
        return Ok(DeltaValue::ZERO);
    }
    if matches!(fraction.state, FractionState::Empty) {
        return single_integer(index, number);
    }
    let mut components = Components::default();
    components.add(index, number).map_err(python_error)?;
    components.finish(fraction).map_err(python_error)
}

/// Accumulate each already-read role directly. Eight signed64 fixed inputs and
/// their bounded unit factors fit i128; final group bounds remain in DeltaValue.
/// The paired fractional-second aliases need only their two native option values.
#[derive(Default)]
struct Components {
    months: i128,
    fixed_ns: i128,
    absolute: AbsoluteFields,
    millisecond: Option<i64>,
    microsecond: Option<i64>,
}

impl Components {
    #[inline]
    fn add(&mut self, index: usize, number: i64) -> Result<(), ValueError> {
        match index {
            0 => self.months += i128::from(number) * 12,
            1 => self.months += i128::from(number) * 3,
            2 => self.months += i128::from(number),
            3..=9 | 19 => {
                let factor = if index == 19 { 1 } else { FIXED[index - 3].1 };
                self.fixed_ns += i128::from(number) * i128::from(factor);
            }
            17 => self.millisecond = (number != -1).then_some(number),
            18 => self.microsecond = (number != -1).then_some(number),
            10..=16 | 20 => {
                if number != -1 {
                    let field = if index == 20 {
                        AbsoluteField::Nanosecond
                    } else {
                        AbsoluteField::ALL[index - 10]
                    };
                    self.absolute.set(field, Some(number))?;
                }
            }
            _ => unreachable!("validated public or relativedelta role"),
        }
        Ok(())
    }

    #[inline]
    fn finish(mut self, fraction: FixedFractions) -> Result<DeltaValue, ValueError> {
        let microsecond = self.millisecond.map_or(self.microsecond, |ms| {
            Some(ms * 1000 + self.microsecond.map_or(0, |us| us % 1000))
        });
        if microsecond.is_some() {
            self.absolute.set(AbsoluteField::Microsecond, microsecond)?;
        }
        if self.months == 0 && self.fixed_ns == 0 && matches!(fraction.state, FractionState::Empty)
        {
            // The lanes are validated above; no relative quantity remains to
            // normalize. Explicit zero absolute clock selections stay present.
            return Ok(DeltaValue {
                absolute: self.absolute,
                ..DeltaValue::ZERO
            });
        }
        DeltaValue::from_totals(self.months, fraction.finish(self.fixed_ns)?, self.absolute)
    }
}

/// Reuse the proven S0 public-dictionary borrow for a callback-free primitive
/// keyword set. All names/types are captured before declared-order conversion;
/// arbitrary numeric protocols, bool and None use the owned binding instead.
fn small_keywords<const COUNT: usize>(kwargs: &Bound<'_, PyDict>) -> Option<PyResult<DeltaValue>> {
    let py = kwargs.py();
    let names = keyword_names(py);
    let mut entries = [(0usize, std::ptr::null_mut(), false); COUNT];
    let mut position = 0;
    let mut key = std::ptr::null_mut();
    let mut value = std::ptr::null_mut();
    for entry in &mut entries {
        // SAFETY: the caller proved exact COUNT while holding the ordinary GIL.
        // Qualification invokes no Python callbacks; kwargs owns every entry.
        if unsafe { pyo3::ffi::PyDict_Next(kwargs.as_ptr(), &mut position, &mut key, &mut value) }
            != 1
        {
            return None;
        }
        let index = if let Some(index) = names.iter().position(|name| name.as_ptr() == key) {
            index
        } else {
            let key = unsafe { Borrowed::from_ptr(py, key) };
            let text = match key.cast::<PyString>() {
                Ok(text) => text,
                Err(error) => return Some(Err(error.into())),
            };
            let text = match text.to_str() {
                Ok(text) => text,
                Err(error) => return Some(Err(error)),
            };
            let Some(index) = parameter_index(text) else {
                return Some(Err(crate::error_context::type_error(format!(
                    "Delta() got an unexpected keyword argument '{text}'"
                ))));
            };
            index
        };
        let floating = unsafe {
            if pyo3::ffi::Py_TYPE(value) == std::ptr::addr_of_mut!(pyo3::ffi::PyLong_Type) {
                false
            } else if pyo3::ffi::PyLong_Check(value) != 0 {
                if pyo3::ffi::PyBool_Check(value) != 0 {
                    return None;
                }
                false
            } else {
                true
            }
        };
        if floating
            && (coefficient(index).is_none() || unsafe { pyo3::ffi::PyFloat_Check(value) } == 0)
        {
            return None;
        }
        *entry = (index, value, floating);
    }
    entries.sort_unstable_by_key(|entry| entry.0);
    if let Some(pair) = entries.windows(2).find(|pair| pair[0].0 == pair[1].0) {
        return Some(Err(crate::error_context::type_error(format!(
            "Delta() got multiple values for keyword argument '{}'",
            NAMES[pair[0].0]
        ))));
    }
    Some((|| {
        let mut components = Components::default();
        let mut fraction = FixedFractions::default();
        for (index, value, floating) in entries {
            // SAFETY: kwargs still owns each qualified primitive. Hold this
            // current value across fallible conversion/error formatting: a cold
            // error can allocate or run user repr. On error we return without
            // reading later borrowed entries; successful primitive reads have
            // no Python callback. Arbitrary protocols use the fully owned path.
            let value = unsafe { Borrowed::from_ptr(py, value) }.to_owned();
            let read = if floating {
                relative_input(&value, index, &mut fraction)
            } else {
                super::converted_integer(&value).and_then(|number| {
                    if index < 10 || index == 19 {
                        Ok(number)
                    } else {
                        absolute_number(number, index)
                    }
                })
            };
            let number = read.map_err(|error| {
                crate::error_context::argument(py, error, "Delta", NAMES[index], &value)
            })?;
            components.add(index, number).map_err(python_error)?;
        }
        components.finish(fraction).map_err(python_error)
    })())
}

/// Bind all names before conversion, then read each provided argument in its
/// established declaration order, retaining its owner across actual callbacks.
pub(crate) fn construct(
    args: &Bound<'_, PyTuple>,
    kwargs: Option<&Bound<'_, PyDict>>,
) -> PyResult<DeltaValue> {
    if args.is_empty() && kwargs.is_none_or(|values| values.is_empty()) {
        return Ok(DeltaValue::ZERO);
    }
    if args.is_empty()
        && let Some(kwargs) = kwargs.filter(|values| values.len() == 1)
        && let Some((key, value)) = kwargs.iter().next()
        && let Some(index) = parameter_index(key.cast::<PyString>()?.to_str()?)
    {
        return single_input(&value, index).map_err(|error| {
            crate::error_context::argument(args.py(), error, "Delta", NAMES[index], &value)
        });
    }
    if args.len() > 19 {
        return Err(crate::error_context::type_error(format!(
            "Delta() takes at most 19 positional arguments ({} given)",
            args.len()
        )));
    }
    if args.is_empty()
        && let Some(kwargs) = kwargs.filter(|values| (2..=4).contains(&values.len()))
    {
        let result = match kwargs.len() {
            2 => small_keywords::<2>(kwargs),
            3 => small_keywords::<3>(kwargs),
            _ => small_keywords::<4>(kwargs),
        };
        if let Some(result) = result {
            return result;
        }
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
    let mut components = Components::default();
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
        let number = read().map_err(|error| {
            crate::error_context::argument(value.py(), error, "Delta", NAMES[index], value)
        })?;
        components.add(index, number).map_err(python_error)?;
    }
    components.finish(fraction).map_err(python_error)
}

/// Interpret dateutil's fifteen source fields into the new Delta value. This is
/// its external source format, not a legacy Delta storage/serialization layer.
pub(crate) fn normalize_relative_fields(
    fields: [i64; 15],
    fraction: FixedFractions,
) -> PyResult<RelativeFields> {
    // Source roles and all actual Python callbacks were already resolved.
    // Fold their fixed units directly, rather than redispatching fifteen public
    // constructor roles. Seven signed64 fields at these factors fit i128.
    let months = i128::from(fields[0]) * 12 + i128::from(fields[1]);
    let fixed_ns =
        (((i128::from(fields[2]) * 24 + i128::from(fields[3])) * 60 + i128::from(fields[4])) * 60
            + i128::from(fields[5]))
            * 1_000_000_000
            + i128::from(fields[6]) * 1000;
    let mut absolute = AbsoluteFields::EMPTY;
    for (field, &number) in AbsoluteField::ALL[..8].iter().zip(&fields[7..]) {
        if number != -1 {
            absolute.set(*field, Some(number)).map_err(python_error)?;
        }
    }
    let fixed_ns = fraction.finish(fixed_ns).map_err(python_error)?;
    DeltaValue::from_totals(months, fixed_ns, absolute)
        .map(RelativeFields)
        .map_err(python_error)
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

    fn normalize(fields: [i64; 21], fraction: FixedFractions) -> Result<DeltaValue, ValueError> {
        let mut components = Components::default();
        for (index, number) in fields.into_iter().enumerate() {
            components.add(index, number)?;
        }
        components.finish(fraction)
    }

    fn defaults() -> [i64; 21] {
        let mut fields = [0; 21];
        fields[10..19].fill(-1);
        fields[20] = -1;
        fields
    }

    #[test]
    fn mixed_fraction_shortcuts_keep_exact_sum_and_final_parity() {
        let fractions = [0.5, -0.5, 0.25, -0.125, 0.1, -0.1, f64::from_bits(1)];
        for a in fractions {
            for b in fractions {
                for c in fractions {
                    for base in [-1001, -1, 0, 1, 1001] {
                        let mut prepared = FixedFractions::default();
                        let mut exact = FixedNsAccumulator::new();
                        for (number, coefficient) in [(a, 1_000_000_000), (b, 1000), (c, 1)] {
                            prepared.add(number, coefficient).unwrap();
                            exact.add(number, coefficient).unwrap();
                        }
                        assert_eq!(
                            prepared.finish(base),
                            exact.rounded(base),
                            "{a} {b} {c} base={base}"
                        );
                    }
                }
            }
        }
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
