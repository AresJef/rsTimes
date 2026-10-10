use pyo3::exceptions::{PyOverflowError, PyTypeError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDelta, PyDeltaAccess, PyDict, PyInt, PyString, PyTuple, PyType};
use std::fmt::Write;
use std::sync::atomic::{AtomicI64, AtomicIsize, AtomicU64, Ordering};

// Atomic fields avoid holding a mutable PyO3 borrow across Python callbacks.
// The accepted interpreter has the GIL; field commits contain no callbacks.
/// Relative increments and absolute date/time replacements.
#[pyclass(frozen, subclass, immutable_type, module = "rstimes.delta")]
pub struct Delta {
    // Two bounded signed32 fields share one atomic64 word. Logical slot2
    // stores derived truth; actual days stays64-bit. The last half-word is0.
    // Pairing reduces atomic loads in equality/snapshots without changing size.
    fields: [AtomicU64; 8],
    days: AtomicI64,
    hash_code: AtomicIsize,
}

impl Delta {
    pub(crate) fn raw() -> Self {
        Self::from_normalized([0; 15], 0)
    }
    #[inline]
    pub(crate) fn from_fields(fields: [i64; 15]) -> PyResult<Self> {
        let mut inputs = [0; 19];
        for (field, parameter) in [0, 2, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18]
            .into_iter()
            .enumerate()
        {
            inputs[parameter] = fields[field];
        }
        inputs[17] = -1;
        let normalized = normalize(inputs).map_err(PyOverflowError::new_err)?;
        Ok(Self::from_normalized(normalized, -1))
    }

    fn combine(&self, other: &Self, subtract: bool) -> PyResult<Self> {
        let mut fields = self.snapshot();
        let rhs = other.snapshot();
        for index in 0..7 {
            fields[index] = if subtract {
                fields[index].checked_sub(rhs[index])
            } else {
                fields[index].checked_add(rhs[index])
            }
            .ok_or_else(|| PyOverflowError::new_err("integer overflow in Delta arithmetic"))?;
        }
        for index in 7..15 {
            if (subtract && fields[index] == -1) || (!subtract && rhs[index] != -1) {
                fields[index] = rhs[index];
            }
        }
        Self::from_fields(fields)
    }

    fn with_duration(
        &self,
        other: &Bound<'_, PyDelta>,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        let mut fields = self.snapshot();
        if reverse {
            for value in &mut fields[..7] {
                *value = value.checked_neg().ok_or_else(|| {
                    PyOverflowError::new_err("integer overflow in Delta negation")
                })?;
            }
        }
        for (index, value) in [
            (2, i64::from(other.get_days())),
            (5, i64::from(other.get_seconds())),
            (6, i64::from(other.get_microseconds())),
        ] {
            fields[index] = if subtract && !reverse {
                fields[index].checked_sub(value)
            } else {
                fields[index].checked_add(value)
            }
            .ok_or_else(|| PyOverflowError::new_err("integer overflow in Delta arithmetic"))?;
        }
        Self::from_fields(fields)
    }
    pub(crate) fn copied(&self) -> Self {
        Self::from_normalized(self.snapshot(), self.cached_hash())
    }

    // Only normalize(), fully checked external restore, or trusted snapshots
    // produce this input. They establish i32 bounds for every field except days.
    fn from_normalized(fields: [i64; 15], cache: isize) -> Self {
        let truth = storage_flags(&fields);
        Self {
            fields: std::array::from_fn(|pair| AtomicU64::new(pack_pair(&fields, truth, pair))),
            days: AtomicI64::new(fields[2]),
            hash_code: AtomicIsize::new(cache),
        }
    }

    pub(crate) fn snapshot(&self) -> [i64; 15] {
        let mut fields = [0; 15];
        for (pair, word) in self.fields.iter().enumerate() {
            let bits = word.load(Ordering::Relaxed);
            let first = pair * 2;
            fields[first] = i64::from(bits as u32 as i32);
            if first + 1 < 15 {
                fields[first + 1] = i64::from((bits >> 32) as u32 as i32);
            }
        }
        fields[2] = self.days.load(Ordering::Relaxed);
        fields
    }

    // A date has no clock fields. If no Delta clock component can contribute
    // a day, omit those reads/unpacks; absolute0 and unset-1 both contribute0.
    // Datetime always receives every actual field, including explicit zeroes.
    #[inline(always)]
    pub(crate) fn calendar_snapshot(&self, datetime: bool) -> [i64; 15] {
        if datetime || self.fields[1].load(Ordering::Relaxed) & 2 != 0 {
            return self.snapshot();
        }
        let relative = self.fields[0].load(Ordering::Relaxed);
        let year = self.fields[3].load(Ordering::Relaxed);
        let month_day = self.fields[4].load(Ordering::Relaxed);
        let weekday = self.fields[5].load(Ordering::Relaxed);
        [
            i64::from(relative as u32 as i32),
            i64::from((relative >> 32) as u32 as i32),
            self.days.load(Ordering::Relaxed),
            0,
            0,
            0,
            0,
            i64::from((year >> 32) as u32 as i32),
            i64::from(month_day as u32 as i32),
            i64::from((month_day >> 32) as u32 as i32),
            i64::from(weekday as u32 as i32),
            -1,
            -1,
            -1,
            -1,
        ]
    }

    #[inline]
    pub(crate) fn native_eq(&self, other: &Self) -> bool {
        self.days.load(Ordering::Relaxed) == other.days.load(Ordering::Relaxed)
            && self
                .fields
                .iter()
                .zip(&other.fields)
                .all(|(left, right)| left.load(Ordering::Relaxed) == right.load(Ordering::Relaxed))
    }

    pub(crate) fn cached_hash(&self) -> isize {
        self.hash_code.load(Ordering::Relaxed)
    }

    #[cold]
    #[inline(never)]
    fn compute_hash(&self, py: Python<'_>) -> PyResult<isize> {
        let value = PyTuple::new(py, self.snapshot())?.hash()?;
        self.hash_code.store(value, Ordering::Relaxed);
        Ok(value)
    }

    pub(crate) fn restore_fields(&self, fields: [i64; 15], cache: isize) {
        // Same validated ranges as from_normalized(); no callbacks during commit.
        let truth = storage_flags(&fields);
        for (pair, word) in self.fields.iter().enumerate() {
            word.store(pack_pair(&fields, truth, pair), Ordering::Relaxed);
        }
        self.days.store(fields[2], Ordering::Relaxed);
        self.hash_code.store(cache, Ordering::Relaxed);
    }
    #[inline]
    pub(crate) fn relative(&self, index: usize) -> i64 {
        if index == 2 {
            self.days.load(Ordering::Relaxed)
        } else {
            let word = self.fields[index / 2].load(Ordering::Relaxed);
            i64::from((word >> ((index & 1) * 32)) as u32 as i32)
        }
    }

    fn absolute(&self, index: usize) -> Option<i64> {
        let value = self.relative(index);
        (value != -1).then_some(value)
    }

    fn equals_duration(&self, other: &Bound<'_, PyDelta>) -> PyResult<bool> {
        let fields = self.snapshot();
        if fields[0] != 0 || fields[1] != 0 || fields[7..].iter().any(|value| *value != -1) {
            return Ok(false);
        }
        let total = |days: i64, seconds: i64, microseconds: i64| -> PyResult<i64> {
            days.checked_mul(86_400)
                .and_then(|value| value.checked_add(seconds))
                .and_then(|value| value.checked_mul(1_000_000))
                .and_then(|value| value.checked_add(microseconds))
                .ok_or_else(|| {
                    PyOverflowError::new_err("integer overflow in Delta duration comparison")
                })
        };
        let left = total(
            fields[2],
            fields[3] * 3_600 + fields[4] * 60 + fields[5],
            fields[6],
        )?;
        let right = total(
            i64::from(other.get_days()),
            i64::from(other.get_seconds()),
            i64::from(other.get_microseconds()),
        )?;
        Ok(left == right)
    }
}

// Bit0 is ordinary truth; bit1 marks clock components that may contribute
// days when applied to a date. Both flags are derived at each checked commit.
fn storage_flags(fields: &[i64; 15]) -> i32 {
    let truth =
        fields[..7].iter().any(|value| *value != 0) || fields[7..].iter().any(|value| *value != -1);
    let clock =
        fields[3..7].iter().any(|value| *value != 0) || fields[11..].iter().any(|value| *value > 0);
    i32::from(truth) | (i32::from(clock) << 1)
}

// Storage encoding only: all non-day fields were checked before reaching
// here. Casting to u32 preserves signed32 bits; reads sign-extend them again.
// pair is an internal0..8 array index, so both shifts and indices are bounded.
#[inline]
const fn pack_pair(fields: &[i64; 15], truth: i32, pair: usize) -> u64 {
    let first = pair * 2;
    let low = if first == 2 {
        truth as u32
    } else {
        fields[first] as i32 as u32
    };
    let high = if first + 1 < 15 {
        fields[first + 1] as i32 as u32
    } else {
        0
    };
    // Lossless widening is const-evaluable on the project's stable Rust.
    low as u64 | ((high as u64) << 32)
}

fn parameter_index(name: &str) -> Option<usize> {
    match name {
        "years" => Some(0),
        "quarters" => Some(1),
        "months" => Some(2),
        "weeks" => Some(3),
        "days" => Some(4),
        "hours" => Some(5),
        "minutes" => Some(6),
        "seconds" => Some(7),
        "milliseconds" => Some(8),
        "microseconds" => Some(9),
        "year" => Some(10),
        "month" => Some(11),
        "day" => Some(12),
        "weekday" => Some(13),
        "hour" => Some(14),
        "minute" => Some(15),
        "second" => Some(16),
        "millisecond" => Some(17),
        "microsecond" => Some(18),
        _ => None,
    }
}

pub(crate) fn input_integer(value: &Bound<'_, PyAny>, narrow: bool) -> PyResult<i64> {
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
    // A single keyword is common in date + Delta(months=...) calls. There
    // are no duplicates or later keywords to validate in this form, so retain
    // the owned value across its numeric callback without building 19 options.
    if args.is_empty() {
        if let Some(kwargs) = kwargs.filter(|values| values.len() == 1) {
            if let Some((key, value)) = kwargs.iter().next() {
                let name = key.cast::<PyString>()?.to_str()?;
                if let Some(index) = parameter_index(name) {
                    let mut inputs = [0_i64; 19];
                    inputs[10..].fill(-1);
                    inputs[index] = input_integer(&value, !(4..10).contains(&index))?;
                    return Ok(inputs);
                }
            }
        }
    }
    let mut values: [Option<Bound<'_, PyAny>>; 19] = std::array::from_fn(|_| None);
    for (index, value) in args.iter().enumerate() {
        values[index] = Some(value);
    }
    if let Some(kwargs) = kwargs {
        for (key, value) in kwargs.iter() {
            let name = key.cast::<PyString>()?.to_str()?;
            let Some(index) = parameter_index(name) else {
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
            inputs[index] = input_integer(value, !(4..10).contains(&index))?;
        }
    }
    Ok(inputs)
}

const OVERFLOW: &str = "integer overflow in Delta normalization";

fn narrow(number: i64) -> Result<i32, &'static str> {
    i32::try_from(number).map_err(|_| OVERFLOW)
}

fn carry(value: i64, parent: i64, base: i64) -> Result<(i64, i64), &'static str> {
    if (0..base).contains(&value) {
        return Ok((value, parent));
    }
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
#[inline(always)]
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
    #[classmethod]
    fn from_relativedelta(_class: &Bound<'_, PyType>, rd: &Bound<'_, PyAny>) -> PyResult<Self> {
        Self::from_fields(crate::interop::relativedelta_fields(rd)?)
    }
    #[new]
    #[pyo3(signature = (*args, **kwargs), text_signature = None)]
    fn new(args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) -> Self {
        let _ = (args, kwargs);
        Self::raw()
    }

    #[pyo3(signature = (*args, **kwargs))]
    pub(crate) fn __init__(
        &self,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        if args.is_empty() && kwargs.is_none_or(|values| values.is_empty()) {
            // Constant encoding of seven relative zeroes and eight unset
            // absolute fields; no numeric conversion or flag scan is needed.
            const EMPTY: [u64; 8] = {
                let fields = [0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1];
                let mut words = [0; 8];
                let mut index = 0;
                while index < 8 {
                    words[index] = pack_pair(&fields, 0, index);
                    index += 1;
                }
                words
            };
            for (word, value) in self.fields.iter().zip(EMPTY) {
                word.store(value, Ordering::Relaxed);
            }
            self.days.store(0, Ordering::Relaxed);
            self.hash_code.store(-1, Ordering::Relaxed);
            return Ok(());
        }
        let fields = normalize(parse_inputs(args, kwargs)?).map_err(PyOverflowError::new_err)?;
        self.restore_fields(fields, -1);
        Ok(())
    }

    pub(crate) fn __bool__(&self) -> bool {
        self.fields[1].load(Ordering::Relaxed) as u32 & 1 != 0
    }

    pub(crate) fn __eq__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = other.py();
        let answer = if let Ok(rhs) = other.cast::<Self>() {
            self.native_eq(rhs.get())
        } else if let Ok(rhs) = other.cast::<PyDelta>() {
            self.equals_duration(rhs)?
        } else if crate::interop::is_relativedelta(other)? {
            self.snapshot()
                == Self::from_fields(crate::interop::relativedelta_fields(other)?)?.snapshot()
        } else if let Some((value, _)) = crate::numpy_scalar::microseconds(other, false)? {
            self.equals_duration(&crate::numpy_scalar::timedelta_from_us(py, value)?)?
        } else {
            return Ok(py.NotImplemented().into_bound(py));
        };
        Ok(PyBool::new(py, answer).to_owned().into_any())
    }

    pub(crate) fn __ne__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let answer = self.__eq__(other)?;
        if answer.is(other.py().NotImplemented()) {
            return Ok(answer);
        }
        Ok(PyBool::new(other.py(), !answer.extract::<bool>()?)
            .to_owned()
            .into_any())
    }

    fn __copy__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::copy_object(slf, None)
    }
    fn __deepcopy__<'py>(
        slf: &Bound<'py, Self>,
        memo: &Bound<'py, PyDict>,
    ) -> PyResult<Bound<'py, PyAny>> {
        crate::state::copy_object(slf, Some(memo))
    }

    fn __getstate__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::capture(slf)
    }
    fn __setstate__(slf: &Bound<'_, Self>, state: &Bound<'_, PyAny>) -> PyResult<()> {
        crate::state::restore(slf, state)
    }
    fn __reduce_ex__<'py>(slf: &Bound<'py, Self>, _protocol: i32) -> PyResult<Bound<'py, PyAny>> {
        crate::state::reduce(slf)
    }
    fn __reduce__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::reduce(slf)
    }

    #[inline]
    pub(crate) fn __hash__(&self, py: Python<'_>) -> PyResult<isize> {
        let cached = self.hash_code.load(Ordering::Relaxed);
        if cached != -1 {
            return Ok(cached);
        }
        self.compute_hash(py)
    }

    fn __repr__(slf: &Bound<'_, Self>) -> PyResult<String> {
        let fields = slf.borrow().snapshot();
        let names = [
            "years",
            "months",
            "days",
            "hours",
            "minutes",
            "seconds",
            "microseconds",
            "year",
            "month",
            "day",
            "weekday",
            "hour",
            "minute",
            "second",
            "microsecond",
        ];
        let py = slf.py();
        let class = slf
            .as_any()
            .getattr(pyo3::intern!(py, "__class__"))?
            .getattr(pyo3::intern!(py, "__name__"))?
            .extract::<String>()?;
        let mut text = String::with_capacity(256);
        write!(&mut text, "<'{class}' (")
            .map_err(|_| PyTypeError::new_err("Cannot format Delta"))?;
        let mut separated = false;
        for (index, (&name, &value)) in names.iter().zip(&fields).enumerate() {
            if (index < 7 && value == 0) || (index >= 7 && value == -1) {
                continue;
            }
            if separated {
                text.push_str(", ");
            }
            separated = true;
            if index == 10 {
                text.push_str("weekday=");
                text.push_str(["MO", "TU", "WE", "TH", "FR", "SA", "SU"][value as usize]);
            } else {
                write!(&mut text, "{name}={value}")
                    .map_err(|_| PyTypeError::new_err("Cannot format Delta"))?;
            }
        }
        text.push_str(")>");
        Ok(text)
    }

    pub(crate) fn __add__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(result) = crate::interop::apply_date(self, other, 1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<Self>() {
            return Bound::new(other.py(), self.combine(&rhs.borrow(), false)?)
                .map(Bound::into_any);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, false, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            let rhs = Self::from_fields(crate::interop::relativedelta_fields(other)?)?;
            return Bound::new(other.py(), self.combine(&rhs, false)?).map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, true)? {
            if datetime {
                return crate::numpy_scalar::apply_datetime_us(other.py(), self, value, 1);
            }
            let duration = crate::numpy_scalar::timedelta_from_us(other.py(), value)?;
            return Bound::new(other.py(), self.with_duration(&duration, false, false)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    pub(crate) fn __radd__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(result) = crate::interop::apply_date(self, other, 1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, false, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            let lhs = Self::from_fields(crate::interop::relativedelta_fields(other)?)?;
            return Bound::new(other.py(), lhs.combine(self, false)?).map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, true)? {
            if datetime {
                return crate::numpy_scalar::apply_datetime_us(other.py(), self, value, 1);
            }
            let duration = crate::numpy_scalar::timedelta_from_us(other.py(), value)?;
            return Bound::new(other.py(), self.with_duration(&duration, false, false)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    pub(crate) fn __rsub__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(result) = crate::interop::apply_date(self, other, -1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, true, true)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            let lhs = Self::from_fields(crate::interop::relativedelta_fields(other)?)?;
            return Bound::new(other.py(), lhs.combine(self, true)?).map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, true)? {
            if datetime {
                return crate::numpy_scalar::apply_datetime_us(other.py(), self, value, -1);
            }
            let duration = crate::numpy_scalar::timedelta_from_us(other.py(), value)?;
            return Bound::new(other.py(), self.with_duration(&duration, true, true)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    pub(crate) fn __sub__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Ok(rhs) = other.cast::<Self>() {
            return Bound::new(other.py(), self.combine(&rhs.borrow(), true)?).map(Bound::into_any);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, true, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            let rhs = Self::from_fields(crate::interop::relativedelta_fields(other)?)?;
            return Bound::new(other.py(), self.combine(&rhs, true)?).map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, false)? {
            if datetime {
                return Ok(other.py().NotImplemented().into_bound(other.py()));
            }
            let duration = crate::numpy_scalar::timedelta_from_us(other.py(), value)?;
            return Bound::new(other.py(), self.with_duration(&duration, true, false)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    fn __neg__(&self) -> PyResult<Self> {
        let mut fields = self.snapshot();
        for value in &mut fields[..7] {
            *value = value
                .checked_neg()
                .ok_or_else(|| PyOverflowError::new_err("integer overflow in Delta negation"))?;
        }
        Self::from_fields(fields)
    }

    fn __abs__(&self) -> PyResult<Self> {
        let mut fields = self.snapshot();
        for (start, end) in [(0, 2), (2, 7)] {
            if fields[start] < 0 {
                for value in &mut fields[start..end] {
                    *value = value.checked_neg().ok_or_else(|| {
                        PyOverflowError::new_err("integer overflow in Delta absolute value")
                    })?;
                }
            }
        }
        Self::from_fields(fields)
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
