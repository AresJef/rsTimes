use pyo3::exceptions::{PyOverflowError, PyTypeError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyInt, PyString, PyTuple};
use std::sync::atomic::{AtomicI64, AtomicIsize, Ordering};

// Atomic fields avoid holding a mutable PyO3 borrow across Python callbacks.
// The accepted interpreter has the GIL; field commits contain no callbacks.
/// Relative increments and absolute date/time replacements.
#[pyclass(frozen, subclass, immutable_type, module = "rstimes.delta")]
pub struct Delta {
    fields: [AtomicI64; 15],
    hash_code: AtomicIsize,
}

impl Delta {
    fn snapshot(&self) -> [i64; 15] {
        std::array::from_fn(|index| self.relative(index))
    }
    fn relative(&self, index: usize) -> i64 {
        self.fields[index].load(Ordering::Relaxed)
    }

    fn absolute(&self, index: usize) -> Option<i64> {
        let value = self.relative(index);
        (value != -1).then_some(value)
    }
}

const PARAMETERS: [&str; 19] = [
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
];

fn input_integer(value: &Bound<'_, PyAny>, narrow: bool) -> PyResult<i64> {
    let converted;
    let integer = if value.cast::<PyInt>().is_ok() {
        value
    } else {
        // Unlike int(), Cython requires an __int__ slot, not only __index__.
        if !value.get_type().hasattr("__int__")? {
            return Err(PyTypeError::new_err("an integer is required"));
        }
        converted = value.py().get_type::<PyInt>().call1((value,))?;
        &converted
    };
    let number = integer.extract::<i64>().map_err(|error| {
        if error.is_instance_of::<PyOverflowError>(value.py()) {
            PyOverflowError::new_err(if narrow {
                "value too large to convert to int"
            } else {
                "Python int too large to convert to C long"
            })
        } else {
            error
        }
    })?;
    if narrow && i32::try_from(number).is_err() {
        return Err(PyOverflowError::new_err(
            "value too large to convert to int",
        ));
    }
    Ok(number)
}

fn parse_inputs(
    args: &Bound<'_, PyTuple>,
    kwargs: Option<&Bound<'_, PyDict>>,
) -> PyResult<[i64; 19]> {
    if args.len() > 19 {
        return Err(PyTypeError::new_err(format!(
            "__init__() takes at most 19 positional arguments ({} given)",
            args.len()
        )));
    }
    let mut values: [Option<Bound<'_, PyAny>>; 19] = std::array::from_fn(|_| None);
    for (index, value) in args.iter().enumerate() {
        values[index] = Some(value);
    }
    if let Some(kwargs) = kwargs {
        for (key, value) in kwargs.iter() {
            let name = key.cast::<PyString>()?.to_str()?;
            let Some(index) = PARAMETERS.iter().position(|parameter| *parameter == name) else {
                return Err(PyTypeError::new_err(format!(
                    "__init__() got an unexpected keyword argument '{name}'"
                )));
            };
            if values[index].is_some() {
                return Err(PyTypeError::new_err(format!(
                    "__init__() got multiple values for keyword argument '{name}'"
                )));
            }
            values[index] = Some(value);
        }
    }
    let mut inputs = [0_i64; 19];
    inputs[10..].fill(-1);
    for (index, value) in values.iter().enumerate() {
        if let Some(value) = value {
            inputs[index] = input_integer(value, index < 4 || index >= 10)?;
        }
    }
    Ok(inputs)
}

const OVERFLOW: &str = "integer overflow in Delta normalization";

fn narrow(number: i64) -> Result<i32, &'static str> {
    i32::try_from(number).map_err(|_| OVERFLOW)
}

fn carry(value: i64, parent: i64, base: i64) -> Result<(i64, i64), &'static str> {
    Ok((
        value.rem_euclid(base),
        parent.checked_add(value.div_euclid(base)).ok_or(OVERFLOW)?,
    ))
}

fn absolute(number: i64, maximum: i64, zero_allowed: bool) -> i64 {
    if number > 0 || (zero_allowed && number == 0) {
        number.min(maximum)
    } else {
        -1
    }
}

/// Follow the original evaluation order and widths, rejecting real overflow.
fn normalize(inputs: [i64; 19]) -> Result<[i64; 15], &'static str> {
    let us = inputs[9]
        .checked_add(inputs[8].checked_mul(1_000).ok_or(OVERFLOW)?)
        .ok_or(OVERFLOW)?;
    let (us, seconds) = carry(us, inputs[7], 1_000_000)?;
    let (seconds, minutes) = carry(seconds, inputs[6], 60)?;
    let (minutes, hours) = carry(minutes, inputs[5], 60)?;
    let (hours, days) = carry(hours, inputs[4], 24)?;
    let days = days
        .checked_add(i64::from(
            narrow(inputs[3])?.checked_mul(7).ok_or(OVERFLOW)?,
        ))
        .ok_or(OVERFLOW)?;
    let months = narrow(inputs[2])?
        .checked_add(narrow(inputs[1])?.checked_mul(3).ok_or(OVERFLOW)?)
        .ok_or(OVERFLOW)?;
    let years = narrow(inputs[0])?
        .checked_add(months.div_euclid(12))
        .ok_or(OVERFLOW)?;
    let months = months.rem_euclid(12);
    let absolute_us = if inputs[17] >= 0 {
        inputs[17].min(999) * 1_000
            + if inputs[18] > 0 {
                inputs[18] % 1_000
            } else {
                0
            }
    } else if inputs[18] >= 0 {
        inputs[18].min(999_999)
    } else {
        -1
    };
    Ok([
        i64::from(years),
        i64::from(months),
        days,
        hours,
        minutes,
        seconds,
        us,
        absolute(inputs[10], 9_999, false),
        absolute(inputs[11], 12, false),
        absolute(inputs[12], 31, false),
        absolute(inputs[13], 6, true),
        absolute(inputs[14], 23, true),
        absolute(inputs[15], 59, true),
        absolute(inputs[16], 59, true),
        absolute_us,
    ])
}

#[pymethods]
impl Delta {
    #[new]
    #[pyo3(signature = (*args, **kwargs), text_signature = None)]
    fn new(args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) -> Self {
        let _ = (args, kwargs);
        Self {
            fields: std::array::from_fn(|_| AtomicI64::new(0)),
            hash_code: AtomicIsize::new(0),
        }
    }

    #[pyo3(signature = (*args, **kwargs))]
    fn __init__(
        &self,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let fields = if args.is_empty() && kwargs.is_none_or(|values| values.is_empty()) {
            let mut fields = [0; 15];
            fields[7..].fill(-1);
            fields
        } else {
            normalize(parse_inputs(args, kwargs)?).map_err(PyOverflowError::new_err)?
        };
        for (field, value) in self.fields.iter().zip(fields) {
            field.store(value, Ordering::Relaxed);
        }
        self.hash_code.store(-1, Ordering::Relaxed);
        Ok(())
    }

    fn __bool__(&self) -> bool {
        self.fields.iter().enumerate().any(|(index, field)| {
            let value = field.load(Ordering::Relaxed);
            if index < 7 { value != 0 } else { value != -1 }
        })
    }

    fn __add__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        Ok(crate::interop::apply_date(&self.snapshot(), other, 1)?
            .unwrap_or_else(|| other.py().NotImplemented().into_bound(other.py())))
    }

    fn __radd__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.__add__(other)
    }

    fn __rsub__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        Ok(crate::interop::apply_date(&self.snapshot(), other, -1)?
            .unwrap_or_else(|| other.py().NotImplemented().into_bound(other.py())))
    }

    fn __sub__<'py>(&self, other: &Bound<'py, PyAny>) -> Bound<'py, PyAny> {
        other.py().NotImplemented().into_bound(other.py())
    }

    #[getter]
    fn years(&self) -> i64 {
        self.relative(0)
    }
    #[getter]
    fn months(&self) -> i64 {
        self.relative(1)
    }
    #[getter]
    fn days(&self) -> i64 {
        self.relative(2)
    }
    #[getter]
    fn hours(&self) -> i64 {
        self.relative(3)
    }
    #[getter]
    fn minutes(&self) -> i64 {
        self.relative(4)
    }
    #[getter]
    fn seconds(&self) -> i64 {
        self.relative(5)
    }
    #[getter]
    fn microseconds(&self) -> i64 {
        self.relative(6)
    }
    #[getter]
    fn year(&self) -> Option<i64> {
        self.absolute(7)
    }
    #[getter]
    fn month(&self) -> Option<i64> {
        self.absolute(8)
    }
    #[getter]
    fn day(&self) -> Option<i64> {
        self.absolute(9)
    }
    #[getter]
    fn weekday(&self) -> Option<i64> {
        self.absolute(10)
    }
    #[getter]
    fn hour(&self) -> Option<i64> {
        self.absolute(11)
    }
    #[getter]
    fn minute(&self) -> Option<i64> {
        self.absolute(12)
    }
    #[getter]
    fn second(&self) -> Option<i64> {
        self.absolute(13)
    }
    #[getter]
    fn microsecond(&self) -> Option<i64> {
        self.absolute(14)
    }
}

#[cfg(test)]
mod tests {
    use super::normalize;

    fn defaults() -> [i64; 19] {
        let mut inputs = [0; 19];
        inputs[10..].fill(-1);
        inputs
    }

    #[test]
    fn negative_microsecond_carries_to_previous_day() {
        let mut inputs = defaults();
        inputs[9] = -1;
        assert_eq!(
            &normalize(inputs).expect("valid input")[2..7],
            &[-1, 23, 59, 59, 999_999]
        );
    }

    #[test]
    fn negative_month_carries_to_previous_year() {
        let mut inputs = defaults();
        inputs[2] = -1;
        assert_eq!(&normalize(inputs).expect("valid input")[0..2], &[-1, 11]);
    }

    #[test]
    fn absolute_millisecond_replaces_only_that_part() {
        let mut inputs = defaults();
        inputs[17] = 2;
        inputs[18] = 123_456;
        assert_eq!(normalize(inputs).expect("valid input")[14], 2_456);
    }

    #[test]
    fn intermediate_overflow_is_rejected_before_later_cancellation() {
        let mut inputs = defaults();
        inputs[8] = i64::MAX;
        inputs[9] = i64::MIN;
        assert!(normalize(inputs).is_err());
        let mut inputs = defaults();
        inputs[3] = i64::from(i32::MAX);
        assert!(normalize(inputs).is_err());
        let mut inputs = defaults();
        inputs[0] = i64::from(i32::MAX);
        inputs[2] = 12;
        assert!(normalize(inputs).is_err());
    }
}
