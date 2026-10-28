//! Object conversion for the public parser entry.
use pyo3::exceptions::PyOverflowError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::PyInt;

/// Convert a non-string input, preserving the reference exception chain.
pub(crate) fn convert(
    py: Python<'_>,
    value: &Bound<'_, PyAny>,
    dtclass: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyAny>> {
    convert_inner(py, value, dtclass)?.ok_or_else(|| {
        crate::error_context::expected_type(
            value,
            "parse",
            "dtobj",
            "a date, datetime, date string, numeric epoch seconds or numpy.datetime64",
        )
    })
}

fn convert_inner(
    py: Python<'_>,
    value: &Bound<'_, PyAny>,
    dtclass: Option<&Bound<'_, PyAny>>,
) -> PyResult<Option<Py<PyAny>>> {
    // SAFETY: parser registration initializes the datetime capsule. These real
    // native predicates validate layout before any date/time payload is read;
    // Python __class__ overrides cannot authorize a field read.
    unsafe {
        let pointer = value.as_ptr();
        let builtin = (*ffi::PyDateTimeAPI()).DateTimeType.cast::<ffi::PyObject>();
        let target = dtclass.filter(|class| !class.is_none());
        if ffi::PyDateTime_Check(pointer) != 0 {
            if crate::interop::needs_true_year(ffi::PyDateTime_GET_YEAR(pointer))
                && ffi::Py_TYPE(pointer).cast::<ffi::PyObject>() != builtin
            {
                return convert_datetime_carrier(py, value, target).map(Some);
            }
            let target_pointer = target.map_or(builtin, Bound::as_ptr);
            if ffi::Py_TYPE(pointer).cast::<ffi::PyObject>() == target_pointer {
                return Ok(Some(value.clone().unbind()));
            }
            let fields = [
                ffi::PyDateTime_GET_YEAR(pointer),
                ffi::PyDateTime_GET_MONTH(pointer),
                ffi::PyDateTime_GET_DAY(pointer),
                ffi::PyDateTime_DATE_GET_HOUR(pointer),
                ffi::PyDateTime_DATE_GET_MINUTE(pointer),
                ffi::PyDateTime_DATE_GET_SECOND(pointer),
                ffi::PyDateTime_DATE_GET_MICROSECOND(pointer),
            ]
            .map(i64::from);
            let timezone = Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(pointer));
            if !timezone.is_none()
                && let Some(copied) =
                    crate::pydt::try_pytz_copy(value.cast::<pyo3::types::PyDateTime>()?, target)?
            {
                return Ok(Some(copied.unbind()));
            }
            return construct(
                py,
                fields,
                &timezone,
                i32::from(ffi::PyDateTime_DATE_GET_FOLD(pointer)),
                target,
            )
            .map(Some);
        }
        if ffi::PyDate_Check(pointer) != 0 {
            if target.is_none_or(|class| class.as_ptr() == builtin) {
                // The real date predicate proves these stored calendar fields
                // already fit CPython's date range. Construct midnight directly;
                // dynamic targets keep the complete field/keyword path below.
                return Bound::from_owned_ptr_or_err(
                    py,
                    ((*ffi::PyDateTimeAPI()).DateTime_FromDateAndTimeAndFold)(
                        ffi::PyDateTime_GET_YEAR(pointer),
                        ffi::PyDateTime_GET_MONTH(pointer),
                        ffi::PyDateTime_GET_DAY(pointer),
                        0,
                        0,
                        0,
                        0,
                        ffi::Py_None(),
                        0,
                        (*ffi::PyDateTimeAPI()).DateTimeType,
                    ),
                )
                .map(|value: Bound<'_, PyAny>| Some(value.unbind()));
            }
            let fields = [
                i64::from(ffi::PyDateTime_GET_YEAR(pointer)),
                i64::from(ffi::PyDateTime_GET_MONTH(pointer)),
                i64::from(ffi::PyDateTime_GET_DAY(pointer)),
                0,
                0,
                0,
                0,
            ];
            return construct(py, fields, py.None().bind(py), 0, target).map(Some);
        }
        if ffi::PyLong_Check(pointer) != 0 || ffi::PyFloat_Check(pointer) != 0 {
            if ffi::PyBool_Check(pointer) != 0 {
                return Err(crate::error_context::type_error(
                    "boolean values are not date or epoch inputs",
                ));
            }
            if ffi::PyLong_CheckExact(pointer) != 0 || ffi::PyBool_Check(pointer) != 0 {
                let mut overflow = 0;
                // SAFETY: exact int/bool was proved above. The public overflow
                // flag distinguishes a wider native path without creating a
                // temporary Python exception for an otherwise accepted number.
                let seconds = ffi::PyLong_AsLongLongAndOverflow(pointer, &mut overflow);
                if !ffi::PyErr_Occurred().is_null() {
                    return Err(crate::error_context::fetch(py));
                }
                if overflow == 0
                    && let Some(micros) = seconds.checked_mul(1_000_000)
                {
                    return from_microseconds(py, micros, target).map(Some);
                }
                return construct(
                    py,
                    wide_microsecond_fields(integer_microseconds_wide(value)?)?,
                    py.None().bind(py),
                    0,
                    target,
                )
                .map(Some);
            }
            // Dynamic numeric conversion runs once. In particular, an OverflowError
            // raised by user __float__ must not cause a second callback.
            let seconds = ffi::PyFloat_AsDouble(pointer);
            if seconds == -1.0 && !ffi::PyErr_Occurred().is_null() {
                return Err(crate::error_context::fetch(py));
            }
            if let Some(micros) = rounded_microseconds(seconds) {
                return from_microseconds(py, micros, target).map(Some);
            }
            return construct(
                py,
                wide_microsecond_fields(seconds_to_wide_us(seconds)?)?,
                py.None().bind(py),
                0,
                target,
            )
            .map(Some);
        }
    }
    // The trusted public NumPy API supplies the identity; names and Python
    // module aliases cannot authorize reading a native scalar payload.
    if crate::numpy_scalar::is_datetime(value)? {
        match crate::numpy_scalar::microseconds(value, true) {
            Ok(Some((micros, true))) => return from_microseconds(py, micros, dtclass).map(Some),
            Err(error) if error.is_instance_of::<PyOverflowError>(py) => {
                if let Some(parsed) = crate::epoch::read_numpy(value)? {
                    return construct(
                        py,
                        wide_microsecond_fields(parsed.nanos.div_euclid(1000))?,
                        py.None().bind(py),
                        0,
                        dtclass,
                    )
                    .map(Some);
                }
                return Err(error);
            }
            Err(error) => return Err(error),
            _ => {}
        }
    }
    Ok(None)
}

/// Decode actual foreign wall fields outside the ordinary object conversion frame.
/// # Errors
/// Rejects missing values and preserves actual-value and output-constructor errors.
#[inline(never)]
fn convert_datetime_carrier(
    py: Python<'_>,
    value: &Bound<'_, PyAny>,
    target: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyAny>> {
    crate::interop::reject_nat(value, "parse", "dtobj")?;
    let pointer = value.as_ptr();
    // SAFETY: the native datetime predicate precedes this helper. A matching
    // output retains its value and metadata; NaT was rejected above first.
    unsafe {
        let builtin = (*ffi::PyDateTimeAPI()).DateTimeType.cast::<ffi::PyObject>();
        if ffi::Py_TYPE(pointer).cast::<ffi::PyObject>() == target.map_or(builtin, Bound::as_ptr) {
            return Ok(value.clone().unbind());
        }
    }
    let fields = if let Some((fields, _)) = crate::interop::timestamp_parts(value)? {
        fields
    } else {
        // SAFETY: this helper is called only after the native datetime predicate.
        unsafe {
            [
                ffi::PyDateTime_GET_YEAR(pointer),
                ffi::PyDateTime_GET_MONTH(pointer),
                ffi::PyDateTime_GET_DAY(pointer),
                ffi::PyDateTime_DATE_GET_HOUR(pointer),
                ffi::PyDateTime_DATE_GET_MINUTE(pointer),
                ffi::PyDateTime_DATE_GET_SECOND(pointer),
                ffi::PyDateTime_DATE_GET_MICROSECOND(pointer),
            ]
            .map(i64::from)
        }
    };
    // SAFETY: value is a checked live datetime and owns its borrowed timezone.
    let timezone =
        unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(pointer)) };
    let fold = unsafe { i32::from(ffi::PyDateTime_DATE_GET_FOLD(pointer)) };
    if !timezone.is_none()
        && let Some(copied) =
            crate::pydt::try_pytz_copy(value.cast::<pyo3::types::PyDateTime>()?, target)?
    {
        return Ok(copied.unbind());
    }
    construct(py, fields, &timezone, fold, target)
}

/// Convert the parser's accepted numeric seconds without dispatching other input types.
/// # Errors
/// Preserves integer range checks and Python's dynamic float conversion errors.
#[inline]
pub(crate) fn numeric_microseconds(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    let py = value.py();
    let pointer = value.as_ptr();
    // SAFETY: callers have verified a real Python integer or float object.
    unsafe {
        Ok(
            if ffi::PyLong_CheckExact(pointer) != 0 || ffi::PyBool_Check(pointer) != 0 {
                value
                    .extract::<i64>()?
                    .checked_mul(1_000_000)
                    .ok_or_else(|| {
                        crate::error_context::overflow(
                            "seconds exceed the supported microsecond range",
                        )
                    })?
            } else {
                let seconds = ffi::PyFloat_AsDouble(pointer);
                if seconds == -1.0 && !ffi::PyErr_Occurred().is_null() {
                    return Err(crate::error_context::fetch(py));
                }
                seconds_to_us(seconds)?
            },
        )
    }
}

pub(crate) fn seconds_to_us(seconds: f64) -> PyResult<i64> {
    if seconds.is_nan() {
        return Err(crate::error_context::value_error("seconds must not be NaN"));
    }
    if !seconds.is_finite() {
        return Err(crate::error_context::overflow(format!(
            "Seconds value must be finite, got '{seconds}'"
        )));
    }
    rounded_microseconds(seconds).ok_or_else(|| {
        crate::error_context::overflow("seconds exceed the supported microsecond range")
    })
}

/// Match fixed-point formatting to seven decimal places, then discard digit seven.
fn rounded_microseconds(seconds: f64) -> Option<i64> {
    let bits = seconds.to_bits();
    let exponent = ((bits >> 52) & 0x7ff) as i32;
    let fraction = bits & ((1_u64 << 52) - 1);
    let (mantissa, power) = if exponent == 0 {
        (fraction, -1074)
    } else {
        ((1_u64 << 52) | fraction, exponent - 1023 - 52)
    };
    // A nonnegative binary power is already beyond the supported i64
    // microsecond magnitude. This also rejects infinities and NaNs.
    if power >= 0 {
        return None;
    }
    // The 53-bit significand times 10^7 fits below 2^77. Exact integer
    // quotient/remainder rounding reproduces CPython's ties-to-even fixed f
    // formatting without a floating multiplication or a decimal allocation.
    let scaled = u128::from(mantissa) * 10_000_000;
    let shift = (-power) as u32;
    let rounded = if shift >= 128 {
        // scaled < 2^77, so even the nearest half is far above it. Handle
        // this before shifting because Rust shifts by 128 are invalid.
        0
    } else {
        let quotient = scaled >> shift;
        let remainder = scaled & ((1_u128 << shift) - 1);
        let half = 1_u128 << (shift - 1);
        quotient + u128::from(remainder > half || (remainder == half && quotient & 1 != 0))
    };
    // Check the absolute value first: F0 rejects both signs when the
    // magnitude reaches 2^63, even though i64::MIN itself is representable.
    let micros = i64::try_from(rounded / 10).ok()?;
    Some(if bits >> 63 != 0 { -micros } else { micros })
}

/// Decode exact wide integer seconds only after the ordinary i64 path overflows.
/// # Errors
/// Rejects integer multiplication beyond signed128 microseconds.
#[inline(never)]
fn integer_microseconds_wide(value: &Bound<'_, PyAny>) -> PyResult<i128> {
    value
        .extract::<i128>()?
        .checked_mul(1_000_000)
        .ok_or_else(|| {
            crate::error_context::overflow("numeric seconds exceed the supported arithmetic range")
        })
}

/// Preserve the established seven-decimal conversion for large finite seconds.
/// Only the cold wide path formats text; normal conversion stays allocation-free.
pub(crate) fn seconds_to_wide_us(seconds: f64) -> PyResult<i128> {
    if seconds.is_nan() {
        return Err(crate::error_context::value_error("seconds must not be NaN"));
    }
    if let Some(micros) = rounded_microseconds(seconds) {
        return Ok(i128::from(micros));
    }
    if !seconds.is_finite() {
        return Err(crate::error_context::overflow(
            "numeric seconds must be finite",
        ));
    }
    let mut decimal = format!("{seconds:.7}");
    decimal.pop(); // Discard decimal digit seven after ties-to-even formatting.
    decimal.retain(|digit| digit != '.');
    decimal.parse().map_err(|_| {
        crate::error_context::overflow("numeric seconds exceed the supported arithmetic range")
    })
}

/// Decode a wide epoch to calendar fields without selecting a Python output range.
/// # Errors
/// Rejects only day numbers outside the shared checked Gregorian kernel.
pub(crate) fn wide_microsecond_fields(micros: i128) -> PyResult<[i64; 7]> {
    let days = i64::try_from(micros.div_euclid(86_400_000_000)).map_err(|_| {
        crate::error_context::overflow("epoch day exceeds the supported calendar range")
    })?;
    let ordinal = days
        .checked_add(719_163)
        .ok_or_else(|| crate::error_context::overflow("epoch day overflow"))?;
    let [year, month, day] =
        crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)?;
    let clock = micros.rem_euclid(86_400_000_000);
    Ok([
        year,
        month,
        day,
        (clock / 3_600_000_000) as i64,
        (clock / 60_000_000 % 60) as i64,
        (clock / 1_000_000 % 60) as i64,
        (clock % 1_000_000) as i64,
    ])
}

/// Decode exact epoch microseconds with the parser's established range errors.
pub(crate) fn microsecond_fields(micros: i64) -> PyResult<[i64; 7]> {
    let days = micros.div_euclid(86_400_000_000);
    let time = micros.rem_euclid(86_400_000_000);
    let [year, month, day] =
        crate::calendar::from_ordinal(days + 719_163).map_err(crate::error_context::overflow)?;
    Ok([
        year,
        month,
        day,
        time / 3_600_000_000,
        time / 60_000_000 % 60,
        time / 1_000_000 % 60,
        time % 1_000_000,
    ])
}

/// Construct an epoch value through the same checked path used by object parse.
///
/// # Errors
/// Rejects dates outside years 1..9999 and propagates constructor callback errors.
pub(crate) fn from_microseconds(
    py: Python<'_>,
    micros: i64,
    dtclass: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyAny>> {
    construct(
        py,
        microsecond_fields(micros)?,
        py.None().bind(py),
        0,
        dtclass,
    )
}

fn construct(
    py: Python<'_>,
    fields: [i64; 7],
    timezone: &Bound<'_, PyAny>,
    fold: i32,
    dtclass: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyAny>> {
    // SAFETY: registration initialized the datetime capsule, whose builtin type
    // identity and constructor stay live for this attached interpreter.
    let builtin = unsafe { (*ffi::PyDateTimeAPI()).DateTimeType.cast::<ffi::PyObject>() };
    if let Some(class) = dtclass.filter(|class| !class.is_none() && class.as_ptr() != builtin) {
        return construct_custom(py, fields, timezone, fold, class);
    }
    let [year, month, day, hour, minute, second, microsecond] = fields;
    // This is now specifically the builtin output boundary; custom targets
    // above already received the same real fields without this range limit.
    if !(1..=9999).contains(&year) {
        return Err(crate::error_context::overflow(
            "date is outside years 1 through 9999",
        ));
    }
    let year = i32::try_from(year)
        .map_err(|_| crate::error_context::overflow("year exceeds the supported integer range"))?;
    // SAFETY: the builtin constructor validates all calendar fields and tzinfo;
    // timezone stays alive and the returned new reference is checked for NULL.
    unsafe {
        Bound::from_owned_ptr_or_err(
            py,
            ((*ffi::PyDateTimeAPI()).DateTime_FromDateAndTimeAndFold)(
                year,
                month as i32,
                day as i32,
                hour as i32,
                minute as i32,
                second as i32,
                microsecond as i32,
                timezone.as_ptr(),
                fold,
                (*ffi::PyDateTimeAPI()).DateTimeType,
            ),
        )
    }
    .map(Bound::unbind)
}

/// Retain dynamic constructors without their temporary arrays on builtin conversions.
#[inline(never)]
fn construct_custom(
    py: Python<'_>,
    fields: [i64; 7],
    timezone: &Bound<'_, PyAny>,
    fold: i32,
    class: &Bound<'_, PyAny>,
) -> PyResult<Py<PyAny>> {
    if let Some(value) = crate::pydt::try_from_fields(class, fields, timezone, fold)? {
        return Ok(value.unbind());
    }
    let integers = fields.map(|n| PyInt::new(py, n));
    let fold = PyInt::new(py, fold);
    let mut arguments = [std::ptr::null_mut(); 9];
    for (slot, integer) in arguments.iter_mut().zip(&integers) {
        *slot = integer.as_ptr();
    }
    arguments[7] = timezone.as_ptr();
    arguments[8] = fold.as_ptr();
    let keywords = super::DATETIME_KEYWORDS
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("datetime keyword names not initialized"))?;
    // SAFETY: all nine keyword values, the callable and keyword tuple remain
    // live for the synchronous vectorcall; there are no positional values.
    unsafe {
        Bound::from_owned_ptr_or_err(
            py,
            ffi::PyObject_Vectorcall(
                class.as_ptr(),
                arguments.as_ptr(),
                0,
                keywords.bind(py).as_ptr(),
            ),
        )
    }
    .map_err(crate::error_context::external)
    .and_then(|result| {
        // SAFETY: this predicate checks the actual returned native type.
        if !result.is_none() && unsafe { ffi::PyDateTime_Check(result.as_ptr()) } == 0 {
            Err(crate::error_context::expected_type(
                &result,
                "",
                "dtclass result",
                "a datetime or None",
            ))
        } else {
            Ok(result.unbind())
        }
    })
}

#[cfg(test)]
mod tests {
    use super::rounded_microseconds;

    #[test]
    fn tiny_values_and_signed_zero_round_to_zero() {
        for value in [
            0.0,
            -0.0,
            f64::from_bits(1),
            -f64::from_bits(1),
            f64::MIN_POSITIVE,
            -f64::MIN_POSITIVE,
            f64::from_bits(948_u64 << 52),
            f64::from_bits(947_u64 << 52),
        ] {
            assert_eq!(rounded_microseconds(value), Some(0));
        }
    }

    #[test]
    fn binary_halves_use_even_seventh_decimal_then_truncate() {
        for (value, expected) in [
            (1.0 / 256.0, 3906),
            (3.0 / 256.0, 11718),
            (127.0 / 256.0, 496093),
            (0.99999996, 1_000_000),
            (0.00000096, 1),
            (1.23456789, 1_234_567),
        ] {
            assert_eq!(rounded_microseconds(value), Some(expected));
            assert_eq!(rounded_microseconds(-value), Some(-expected));
        }
    }

    #[test]
    fn absolute_microsecond_overflow_is_symmetric() {
        let below = 9_223_372_036_854.775_f64;
        let limit = f64::from_bits(below.to_bits() + 1);
        for value in [
            limit,
            f64::from_bits(limit.to_bits() + 1),
            f64::MAX,
            f64::INFINITY,
            f64::NAN,
        ] {
            assert_eq!(rounded_microseconds(value), None);
            assert_eq!(rounded_microseconds(-value), None);
        }
        assert!(rounded_microseconds(below).is_some());
        assert!(rounded_microseconds(-below).is_some());
    }
}
