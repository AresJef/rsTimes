//! Immutable exact-value operations and Python boundary completion.

use super::prepare::{self, RelativeFields};
use super::value::{AbsoluteField as Field, DeltaValue};
use super::{Delta, NATIVE_TUPLE_HASH, RepresentationCache};
use pyo3::prelude::*;
use pyo3::types::{PyDateTime, PyDelta, PyDeltaAccess, PyDict, PyString, PyTimeAccess, PyTuple};
use std::sync::atomic::{AtomicIsize, Ordering};

impl Delta {
    /// Construct a fully prepared immutable value, with an empty display cache.
    pub(crate) fn from_value(value: DeltaValue) -> Self {
        Self {
            value,
            hash_code: AtomicIsize::new(-1),
            representation: RepresentationCache::new(),
        }
    }

    /// Validate public binding and source values before exposing an instance.
    pub(crate) fn construct(
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        if args.is_empty() && kwargs.is_none_or(|values| values.is_empty()) {
            return Ok(Self::from_value(DeltaValue::ZERO));
        }
        if args.len() == 1
            && kwargs.is_none_or(|values| values.is_empty())
            && let Some(value) = crate::state::construction_value(args)?
        {
            return Ok(value);
        }
        prepare::construct(args, kwargs)
            .map(Self::from_value)
            .map_err(|error| {
                crate::error_context::argument(
                    args.py(),
                    error,
                    "Delta",
                    "arguments",
                    args.as_any(),
                )
            })
    }

    /// Consume an already interpreted relativedelta source without re-reading it.
    pub(crate) fn from_fields(fields: RelativeFields) -> PyResult<Self> {
        Ok(Self::from_value(fields.0))
    }

    /// Combine the two relative groups and independently present absolute fields.
    pub(crate) fn combine(&self, other: &Self, subtract: bool) -> PyResult<Self> {
        self.value
            .combine(other.value, subtract)
            .map(Self::from_value)
            .map_err(prepare::python_error)
    }

    /// Preserve which operand supplies the preferred absolute fields.
    pub(crate) fn with_relative_fields(
        &self,
        other: RelativeFields,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        let value = if reverse {
            other.0.combine(self.value, subtract)
        } else {
            self.value.combine(other.0, subtract)
        };
        value.map(Self::from_value).map_err(prepare::python_error)
    }

    /// Merge an exact fixed duration without constructing another Python Delta.
    pub(crate) fn with_nanoseconds(
        &self,
        ns: i128,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        self.with_fixed_parts(
            ns.div_euclid(super::value::NS_PER_DAY),
            ns.rem_euclid(super::value::NS_PER_DAY) as u64,
            subtract,
            reverse,
        )
    }

    /// Merge a wide source split before ns scaling. Only the final day group is
    /// narrowed; a large source may legitimately cancel the existing Delta.
    pub(crate) fn with_fixed_parts(
        &self,
        days: i128,
        clock_ns: u64,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        self.value
            .with_fixed_parts(days, clock_ns, subtract, reverse)
            .map(Self::from_value)
            .map_err(prepare::python_error)
    }

    /// Finish a previously qualified NumPy scalar through the exact value or
    /// civil model. Ordinary reflected coarse dates request a date-only exit.
    pub(crate) fn apply_numpy<'py>(
        &self,
        py: Python<'py>,
        input: crate::numpy_scalar::DeltaScalar,
        subtract: bool,
        reverse: bool,
        coarse_date: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        match input {
            crate::numpy_scalar::DeltaScalar::Date { civil, coarse } => {
                if subtract && !reverse {
                    return Ok(py.NotImplemented().into_bound(py));
                }
                crate::numpy_scalar::apply_delta_date(
                    py,
                    &self.value,
                    civil,
                    if subtract { -1 } else { 1 },
                    coarse_date && coarse,
                )
            }
            crate::numpy_scalar::DeltaScalar::Duration { days, clock_ns, .. } => Bound::new(
                py,
                self.with_fixed_parts(days, clock_ns, subtract, reverse)?,
            )
            .map(Bound::into_any),
        }
    }

    /// Read a timedelta's actual native/source precision before merging it.
    pub(crate) fn with_duration(
        &self,
        other: &Bound<'_, PyDelta>,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        if !other.is_exact_instance_of::<PyDelta>()
            && let Some(ns) = crate::interop::duration_nanoseconds(other.as_any())?
        {
            return self.with_nanoseconds(ns, subtract, reverse);
        }
        self.with_duration_parts(
            i64::from(other.get_days()),
            i64::from(other.get_seconds()),
            i64::from(other.get_microseconds()),
            subtract,
            reverse,
        )
    }

    /// Combine known standard timedelta fields, preserving exact integer units.
    pub(crate) fn with_duration_parts(
        &self,
        days: i64,
        seconds: i64,
        microseconds: i64,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        let other = prepare::fixed_duration(days, seconds, microseconds)?;
        let value = if reverse {
            other.combine(self.value, subtract)
        } else {
            self.value.combine(other, subtract)
        };
        value.map(Self::from_value).map_err(prepare::python_error)
    }

    /// A fresh wrapper preserves only the valid immutable hash cache.
    pub(crate) fn copied(&self) -> Self {
        Self {
            value: self.value,
            hash_code: AtomicIsize::new(self.cached_hash()),
            representation: RepresentationCache::new(),
        }
    }

    /// Explicit state/format expansion; ordinary date operations use DeltaValue.
    pub(crate) fn snapshot(&self) -> [i64; 17] {
        self.value.core17()
    }

    /// Prepare the same exact value for either date or datetime projection.
    pub(crate) fn native_value(&self) -> DeltaValue {
        self.value
    }

    /// Read one named state's canonical component without allocating a snapshot.
    #[inline]
    pub(crate) fn relative(&self, index: usize) -> i64 {
        let clock = self.value.clock_ns;
        match index {
            0 => self.value.years,
            1 => i64::from(self.value.months),
            2 => self.value.days,
            3 => (clock / 3_600_000_000_000) as i64,
            4 => (clock / 60_000_000_000 % 60) as i64,
            5 => (clock / 1_000_000_000 % 60) as i64,
            6 => (clock / 1000 % 1_000_000) as i64,
            7 => (clock % 1000) as i64,
            8..=16 => self.value.absolute.get(Field::ALL[index - 8]).unwrap_or(-1),
            _ => unreachable!("validated native Delta field index"),
        }
    }

    pub(super) fn absolute(&self, index: usize) -> Option<i64> {
        self.value.absolute.get(Field::ALL[index - 8])
    }

    /// Compare the complete immutable value, including nanosecond presence.
    #[inline]
    pub(crate) fn native_eq(&self, other: &Self) -> bool {
        self.value == other.value
    }

    /// Recognize exactly preserved builtin clocks without invoking callbacks.
    pub(crate) fn preserves_datetime_clock(&self, dt: &Bound<'_, PyDateTime>) -> bool {
        let value = self.value;
        let absolute = value.absolute;
        if value.calendar_months() != 0 || value.fixed_ns() != 0 {
            return false;
        }
        if [Field::Year, Field::Month, Field::Day, Field::Weekday]
            .into_iter()
            .any(|field| absolute.get(field).is_some())
        {
            return false;
        }
        let same = |field, actual| absolute.get(field).is_none_or(|number| number == actual);
        same(Field::Hour, i64::from(dt.get_hour()))
            && same(Field::Minute, i64::from(dt.get_minute()))
            && same(Field::Second, i64::from(dt.get_second()))
            && same(Field::Microsecond, i64::from(dt.get_microsecond()))
            && same(Field::Nanosecond, 0)
    }

    /// Return the immutable hash cache; -1 means not calculated.
    pub(crate) fn cached_hash(&self) -> isize {
        self.hash_code.load(Ordering::Relaxed)
    }

    /// Clone a cached display under the caller's ordinary-GIL qualification.
    /// # Safety
    /// The same live exact-type/GIL checks as RepresentationCache must hold.
    pub(crate) unsafe fn cached_representation<'py>(
        &self,
        py: Python<'py>,
    ) -> Option<Bound<'py, PyString>> {
        unsafe { self.representation.get(py) }
    }

    /// Native CPython3.13 tuple hashing, over the complete17-field new state.
    pub(crate) fn native_hash(&self) -> Option<isize> {
        if !NATIVE_TUPLE_HASH.load(Ordering::Relaxed) {
            return None;
        }
        const PRIME1: u64 = 11_400_714_785_074_694_791;
        const PRIME2: u64 = 14_029_467_366_897_019_727;
        const PRIME5: u64 = 2_870_177_450_012_600_261;
        const MODULUS: u64 = (1_u64 << 61) - 1;
        let mut acc = PRIME5;
        for index in 0..17 {
            let number = self.relative(index);
            let magnitude = (number.unsigned_abs() % MODULUS) as i64;
            let lane = if number < 0 { -magnitude } else { magnitude };
            let lane = if lane == -1 { -2 } else { lane } as u64;
            acc = acc
                .wrapping_add(lane.wrapping_mul(PRIME2))
                .rotate_left(31)
                .wrapping_mul(PRIME1);
        }
        acc = acc.wrapping_add(17 ^ (PRIME5 ^ 3_527_539));
        let hash = if acc == u64::MAX {
            1_546_275_796
        } else {
            acc as isize
        };
        self.hash_code.store(hash, Ordering::Relaxed);
        Some(hash)
    }

    /// Complete hashing on other supported interpreters through the tuple API.
    pub(super) fn compute_hash(&self, py: Python<'_>) -> PyResult<isize> {
        if let Some(hash) = self.native_hash() {
            return Ok(hash);
        }
        let hash = PyTuple::new(py, self.snapshot())?.hash()?;
        self.hash_code.store(hash, Ordering::Relaxed);
        Ok(hash)
    }

    /// Restore a canonical new state; no serialized cache is trusted.
    pub(crate) fn from_snapshot(fields: [i64; 17]) -> PyResult<Self> {
        DeltaValue::from_core17(fields)
            .map(Self::from_value)
            .map_err(prepare::python_error)
    }

    /// Project a pure fixed Delta to standard timedelta only at this exit.
    pub(crate) fn fixed_timedelta<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDelta>> {
        if self.value.years != 0 || self.value.months != 0 || !self.value.absolute.is_empty() {
            return Err(crate::error_context::value_error(
                "start is required for years, months or absolute fields",
            ));
        }
        let floor = self.value.clock_ns / 1000;
        let rem = self.value.clock_ns % 1000;
        let micros = floor + u64::from(rem > 500 || (rem == 500 && floor % 2 != 0));
        let days = self
            .value
            .days
            .checked_add(i64::from(micros == 86_400_000_000))
            .ok_or_else(|| prepare::python_error(super::value::ValueError::Overflow))?;
        if !(-999_999_999..=999_999_999).contains(&days) {
            return Err(crate::error_context::overflow(
                "duration is outside timedelta's supported range",
            ));
        }
        let clock = if micros == 86_400_000_000 { 0 } else { micros };
        PyDelta::new(
            py,
            days as i32,
            (clock / 1_000_000) as i32,
            (clock % 1_000_000) as i32,
            false,
        )
    }
}

/// A batch's once-prepared right Delta, stored in its exact native value.
pub(crate) struct PreparedAddition {
    value: DeltaValue,
}
impl PreparedAddition {
    /// Prepare a stable immutable right operand once.
    pub(crate) fn new(value: &Delta) -> Self {
        Self { value: value.value }
    }
    /// Whether the right operand contains an actual absolute setting.
    pub(crate) fn has_absolute(&self) -> bool {
        !self.value.absolute.is_empty()
    }
    /// Combine an ordinary left Delta with the prepared right value.
    pub(crate) fn add_delta(&self, left: &Delta) -> PyResult<Delta> {
        left.value
            .combine(self.value, false)
            .map(Delta::from_value)
            .map_err(prepare::python_error)
    }
    /// Statically selected batch form; absolute presence remains part of value.
    pub(crate) fn add_delta_prepared<const REPLACE: bool>(&self, left: &Delta) -> PyResult<Delta> {
        let _ = REPLACE;
        self.add_delta(left)
    }
    /// Add an already interpreted relativedelta without Python intermediates.
    pub(crate) fn add_fields(&self, left: RelativeFields) -> PyResult<Delta> {
        left.0
            .combine(self.value, false)
            .map(Delta::from_value)
            .map_err(prepare::python_error)
    }
    /// Keep wide source scaling outside a temporary Python wrapper.
    pub(crate) fn add_fixed_parts(&self, days: i128, clock_ns: u64) -> PyResult<Delta> {
        self.value
            .with_fixed_parts(days, clock_ns, false, false)
            .map(Delta::from_value)
            .map_err(prepare::python_error)
    }
    /// Exact builtin timedelta source; subtype protocols stay outside this helper.
    pub(crate) fn add_duration(&self, value: &Bound<'_, PyDelta>) -> PyResult<Delta> {
        let left = prepare::fixed_duration(
            i64::from(value.get_days()),
            i64::from(value.get_seconds()),
            i64::from(value.get_microseconds()),
        )?;
        left.combine(self.value, false)
            .map(Delta::from_value)
            .map_err(prepare::python_error)
    }
}
