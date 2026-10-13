//! Delta storage, checked normalization and the Python-facing methods.
//!
//! Snapshot order is seven relative fields (years, months, days, hours, minutes,
//! seconds, microseconds) followed by eight absolute fields (year, month, day,
//! weekday, hour, minute, second, microsecond). Unset absolute fields use -1.
//! Packed values are fully initialized once and never rewritten. Only the hash
//! cache is atomic. The accepted runtime remains the ordinary GIL interpreter.

use pyo3::exceptions::{PyOverflowError, PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{
    PyBool, PyDate, PyDelta, PyDeltaAccess, PyDict, PyFloat, PyInt, PyList, PyString, PyTuple,
    PyType,
};
use std::borrow::Cow;
use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};

static NATIVE_TUPLE_HASH: AtomicBool = AtomicBool::new(false);
static KEYWORD_NAMES: PyOnceLock<[Py<PyString>; 19]> = PyOnceLock::new();

/// Cache native keyword identities for the multi-argument constructor boundary.
///
/// These are existing interned names. No per-call Python object is created;
/// arbitrary strings still use the complete text-validation path below.
fn keyword_names(py: Python<'_>) -> &[Py<PyString>; 19] {
    KEYWORD_NAMES.get_or_init(py, || {
        [
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
        ]
        .map(|name| PyString::intern(py, name).unbind())
    })
}

/// Enable allocation-free integer tuple hashing only for the verified interpreter.
///
/// Other interpreter versions and pointer widths retain Python's tuple hash.
pub(crate) fn configure_hash(py: Python<'_>) {
    let version = py.version_info();
    NATIVE_TUPLE_HASH.store(
        cfg!(target_pointer_width = "64") && version.major == 3 && version.minor == 13,
        Ordering::Relaxed,
    );
}

/// Compute CPython 3.13's 64-bit hash for the integer-only field tuple.
///
/// Uses the integer modulus and tuple mixing defined in CPython v3.13.3,
/// Objects/longobject.c and Objects/tupleobject.c. Signed i64::MIN and Python's
/// reserved -1 sentinel are handled explicitly. This preserves the original
/// tuple value and cache contract without allocating 15 Python integers.
/// The CPython license and attribution are included in NOTICE-CPYTHON.txt/NOTICE.
///
/// # Preconditions
/// The snapshot is canonical. Only years (index0) and days (index2) may exceed
/// signed32; all remaining magnitudes are below the integer-hash modulus.
fn integer_tuple_hash(fields: &[i64; 15]) -> isize {
    const MODULUS: u64 = (1_u64 << 61) - 1;
    const PRIME1: u64 = 11_400_714_785_074_694_791;
    const PRIME2: u64 = 14_029_467_366_897_019_727;
    const PRIME5: u64 = 2_870_177_450_012_600_261;
    let mut accumulator = PRIME5;
    for (index, &number) in fields.iter().enumerate() {
        let absolute = number.unsigned_abs();
        let magnitude = if index == 0 || index == 2 {
            absolute % MODULUS
        } else {
            absolute
        } as i64;
        let signed = if number < 0 { -magnitude } else { magnitude };
        let lane = if signed == -1 { -2_i64 } else { signed } as u64;
        accumulator = accumulator.wrapping_add(lane.wrapping_mul(PRIME2));
        accumulator = accumulator.rotate_left(31).wrapping_mul(PRIME1);
    }
    accumulator = accumulator.wrapping_add(15 ^ (PRIME5 ^ 3_527_539));
    if accumulator == u64::MAX {
        1_546_275_796
    } else {
        accumulator as isize
    }
}

// Atomic fields avoid holding a mutable PyO3 borrow across Python callbacks.
// The accepted interpreter has the GIL; field commits contain no callbacks.
/// Calendar changes with relative amounts and absolute replacements.
///
/// Add a Delta to a date or datetime to move it, set selected parts, or both.
/// A Delta keeps its value after construction. Its 15 field properties are read-only.
///
/// Parameters
/// ----------
/// years : int, default 0
///     Years to add.
/// quarters : int, default 0
///     Quarters to add; each quarter is three months.
/// months : int, default 0
///     Months to add; every twelve months become one year.
/// weeks : int or float, default 0
///     Weeks to add; each week is seven days.
/// days : int or float, default 0
///     Days to add. This positional parameter follows weeks.
/// hours : int or float, default 0
///     Hours to add.
/// minutes : int or float, default 0
///     Minutes to add.
/// seconds : int or float, default 0
///     Seconds to add.
/// milliseconds : int or float, default 0
///     Milliseconds to add; one millisecond is 1000 microseconds.
/// microseconds : int or float, default 0
///     Microseconds to add. Combined fractions round once to the nearest microsecond;
///     an exact halfway value rounds to the even microsecond.
/// year : int, default -1
///     Year to set. Positive values above 9999 become 9999; zero or negative means unset.
/// month : int, default -1
///     Month to set. Positive values above 12 become 12; zero or negative means unset.
/// day : int, default -1
///     Day to set. Positive values above 31 become 31; zero or negative means unset.
/// weekday : int, default -1
///     Day of the week to set, Monday=0 through Sunday=6. Larger values become 6;
///     negative means unset. This selects a day in the same Monday-to-Sunday week.
/// hour : int, default -1
///     Hour to set, limited to 23. Negative means unset; zero is a real setting.
/// minute : int, default -1
///     Minute to set, limited to 59. Negative means unset.
/// second : int, default -1
///     Second to set, limited to 59. Negative means unset.
/// millisecond : int, default -1
///     Millisecond part to set, limited to 999. If set, it replaces the millisecond
///     part of microsecond, which then supplies only its last three digits.
/// microsecond : int, default -1
///     Microsecond to set, limited to 999999 when millisecond is unset.
///     Negative means unset.
///
/// Raises
/// ------
/// TypeError
///     An argument name, count or numeric conversion is unsupported.
/// OverflowError
///     An integer or a calculation is outside the signed 64-bit range.
/// ValueError
///     A fractional duration is NaN.
///
/// Notes
/// -----
/// Relative amounts are carried into larger units. For example, 25 hours become
/// one day and one hour; -1 hour becomes -1 day and 23 hours. Fractional years,
/// quarters, months and absolute settings discard their fractional part.
/// Objects providing __int__ can supply integer values.
///
/// Date operations set absolute parts, add relative amounts, then adjust weekday.
/// A missing day at month end becomes that month's last day. These moves need not
/// be reversible: January 31 plus one month, then minus one month, may end on
/// January 29. Dates outside Python's supported range raise an error.
///
/// Delta values compare by their fields with other Delta values, including
/// subclasses that inherit the same behavior. Equal values have equal, stable
/// hashes. Calling __init__ again leaves the value unchanged. Create another Delta
/// to use different values. Sorting Delta values is unsupported.
///
/// Examples
/// --------
/// >>> from datetime import date
/// >>> date(2024, 1, 31) + Delta(months=1)
/// datetime.date(2024, 2, 29)
/// >>> (Delta(hours=1.5).hours, Delta(hours=1.5).minutes)
/// (1, 30)
/// >>> d = Delta(microseconds=-1)
/// >>> (d.days, d.hours, d.minutes, d.seconds, d.microseconds)
/// (-1, 23, 59, 59, 999999)
/// >>> Delta(millisecond=2, microsecond=123456).microsecond
/// 2456
#[pyclass(frozen, subclass, immutable_type, module = "rstimes.delta")]
pub struct Delta {
    // Bounded pairs share64-bit words; years use word0, months word7 high.
    // Logical slot2 stores derived flags; actual days stay separately64-bit.
    // Immutable packed words permit ordinary reads/copies; only hash changes.
    fields: [u64; 8],
    days: i64,
    hash_code: AtomicIsize,
}

impl Delta {
    /// Parse and normalize all public arguments before an object is allocated.
    ///
    /// # Errors
    /// Propagates shape, conversion and checked normalization errors. A failed
    /// callback cannot expose a partially initialized native value.
    pub(crate) fn construct(
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        if args.is_empty() && kwargs.is_none_or(|values| values.is_empty()) {
            // The common empty constructor has no conversions or carries.
            // Keep its value explicit so normalization has no work to perform.
            return Ok(Self::from_normalized(
                [0, 0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1, -1],
                -1,
            ));
        }
        if args.len() == 1 && kwargs.is_none_or(|values| values.is_empty()) {
            if let Some(value) = crate::state::construction_value(args)? {
                return Ok(value);
            }
        }
        let fields =
            normalize(parse_inputs(args, kwargs)?.rounded()?).map_err(PyOverflowError::new_err)?;
        Ok(Self::from_normalized(fields, -1))
    }
    /// Construct Delta by mapping a 15-field snapshot back through normalization.
    ///
    /// # Errors
    /// Raises OverflowError if any required intermediate exceeds its original width.
    #[inline]
    pub(crate) fn from_fields(fields: [i64; 15]) -> PyResult<Self> {
        let normalized = normalize_external_fields(fields).map_err(PyOverflowError::new_err)?;
        Ok(Self::from_normalized(normalized, -1))
    }

    /// Normalize relative arithmetic performed on validated native Delta fields.
    ///
    /// # Preconditions
    /// Clock and month inputs are sums, differences or negations of canonical
    /// native components, including decomposed normalized timedelta components.
    /// Absolute inputs are validated native fields or raw zeroes.
    /// Foreign fields continue through from_fields and its complete constructor rules.
    ///
    /// # Errors
    /// Preserves checked day carries and signed64 year arithmetic.
    #[inline(always)]
    fn from_native_fields(fields: [i64; 15]) -> PyResult<Self> {
        let normalized = normalize_native_fields(fields).map_err(PyOverflowError::new_err)?;
        Ok(Self::from_normalized(normalized, -1))
    }

    /// Negate selected canonical groups while retaining absolute fields and flags.
    ///
    /// Negation preserves whether either relative group or its lower clock part
    /// is zero. Therefore the validated truth/time flags remain exact, and no
    /// absolute field needs to be decoded or revalidated.
    ///
    /// # Errors
    /// Checked year/day negation still precedes clock/month normalization, so
    /// i64::MIN is rejected even if a later carry could make the result fit.
    #[inline(always)]
    fn negate_groups(
        &self,
        year_month: bool,
        day_time: bool,
        error: &'static str,
    ) -> PyResult<Self> {
        let years = if year_month {
            self.relative(0)
                .checked_neg()
                .ok_or_else(|| PyOverflowError::new_err(error))?
        } else {
            self.relative(0)
        };
        let mut days = if day_time {
            self.days
                .checked_neg()
                .ok_or_else(|| PyOverflowError::new_err(error))?
        } else {
            self.days
        };
        let mut words = self.fields;
        if day_time && words[1] & 2 != 0 {
            // Each clock component is canonical and bounded. Its negation fits
            // i64; only the final carry into unbounded days requires checking.
            let (us, seconds) = carry_once(-self.relative(6), -self.relative(5), 1_000_000)
                .map_err(PyOverflowError::new_err)?;
            let (seconds, minutes) =
                carry_once(seconds, -self.relative(4), 60).map_err(PyOverflowError::new_err)?;
            let (minutes, hours) =
                carry_once(minutes, -self.relative(3), 60).map_err(PyOverflowError::new_err)?;
            let (hours, new_days) =
                carry_once(hours, days, 24).map_err(PyOverflowError::new_err)?;
            days = new_days;
            words[1] = (words[1] & u64::from(u32::MAX)) | ((hours as u64) << 32);
            words[2] = minutes as u64 | ((seconds as u64) << 32);
            words[3] = (words[3] & (u64::from(u32::MAX) << 32)) | us as u64;
        }
        if year_month {
            let (months, years) =
                carry_once(-self.relative(1), years, 12).map_err(PyOverflowError::new_err)?;
            words[0] = years as u64;
            words[7] = (words[7] & u64::from(u32::MAX)) | ((months as u64) << 32);
        }
        Ok(Self {
            fields: words,
            days,
            hash_code: AtomicIsize::new(-1),
        })
    }

    /// Add or subtract relative fields and apply the frozen absolute-field priority.
    ///
    /// # Errors
    /// Rejects checked relative arithmetic or normalization overflow.
    #[inline(always)]
    pub(crate) fn combine(&self, other: &Self, subtract: bool) -> PyResult<Self> {
        if (self.fields[1] | other.fields[1]) & 4 == 0 {
            // Both immutable flag words prove that all replacement fields are
            // unset. Read only the relative components; normalization and its
            // year/day overflow ordering stay identical to the general path.
            let mut fields = [0_i64; 15];
            fields[7..].fill(-1);
            for (index, field) in fields.iter_mut().take(7).enumerate() {
                *field = if subtract {
                    self.relative(index).checked_sub(other.relative(index))
                } else {
                    self.relative(index).checked_add(other.relative(index))
                }
                .ok_or_else(|| PyOverflowError::new_err("integer overflow in Delta arithmetic"))?;
            }
            return Self::from_native_fields(fields);
        }
        Self::combine_snapshots(self.snapshot(), other.snapshot(), subtract)
    }

    /// Combine canonical snapshots without constructing a temporary atomic payload.
    ///
    /// # Errors
    /// Retains relative checked arithmetic and native normalization overflow.
    #[inline(always)]
    fn combine_snapshots(mut fields: [i64; 15], rhs: [i64; 15], subtract: bool) -> PyResult<Self> {
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
        Self::from_native_fields(fields)
    }

    /// Normalize foreign fields before reading this Delta, then combine in operand order.
    ///
    /// Python callbacks have already completed in relativedelta_fields. Full foreign
    /// normalization still precedes the self snapshot and preserves all checked widths.
    /// # Errors
    /// Propagates full normalization and arithmetic overflow exactly as from_fields/combine.
    pub(crate) fn with_relative_fields(
        &self,
        foreign: [i64; 15],
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        let foreign = normalize_external_fields(foreign).map_err(PyOverflowError::new_err)?;
        let own = self.snapshot();
        if reverse {
            Self::combine_snapshots(foreign, own, subtract)
        } else {
            Self::combine_snapshots(own, foreign, subtract)
        }
    }

    /// Combine a standard timedelta with this Delta in the requested direction.
    ///
    /// # Errors
    /// Rejects unrepresentable negation, relative addition/subtraction or normalization.
    #[inline(always)]
    pub(crate) fn with_duration(
        &self,
        other: &Bound<'_, PyDelta>,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        self.with_duration_parts(
            i64::from(other.get_days()),
            i64::from(other.get_seconds()),
            i64::from(other.get_microseconds()),
            subtract,
            reverse,
        )
    }

    /// Combine validated duration parts without constructing an intermediate Python object.
    ///
    /// # Preconditions
    /// seconds is 0..86400 and microseconds is 0..1000000; days fits signed32.
    /// # Errors
    /// Preserves checked negation, day-first arithmetic and native normalization.
    #[inline(always)]
    fn with_duration_parts(
        &self,
        days: i64,
        seconds: i64,
        microseconds: i64,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        // Timedelta changes only relative amounts. Keep the eight validated
        // replacements in their packed words instead of unpacking and scanning
        // them again for each result.
        let mut fields: [i64; 7] = std::array::from_fn(|index| self.relative(index));
        if reverse {
            for index in [0, 2] {
                fields[index] = fields[index].checked_neg().ok_or_else(|| {
                    PyOverflowError::new_err("integer overflow in Delta negation")
                })?;
            }
            // Months and clock components are canonical nonnegative bounded
            // values. Their negation cannot overflow; only years/days are wide.
            for index in [1, 3, 4, 5, 6] {
                fields[index] = -fields[index];
            }
        }
        // Timedelta's native seconds are 0..86399. Decomposing them keeps each
        // clock component inside the same single-carry bounds as Delta arithmetic.
        // The original day addition still happens first and remains checked, even
        // when a later clock carry could cancel an overflowing intermediate.
        for (index, value) in [
            (2, days),
            (3, seconds / 3_600),
            (4, seconds / 60 % 60),
            (5, seconds % 60),
            (6, microseconds),
        ] {
            fields[index] = if subtract && !reverse {
                fields[index].checked_sub(value)
            } else {
                fields[index].checked_add(value)
            }
            .ok_or_else(|| PyOverflowError::new_err("integer overflow in Delta arithmetic"))?;
        }
        let (us, seconds) =
            carry_once(fields[6], fields[5], 1_000_000).map_err(PyOverflowError::new_err)?;
        let (seconds, minutes) =
            carry_once(seconds, fields[4], 60).map_err(PyOverflowError::new_err)?;
        let (minutes, hours) =
            carry_once(minutes, fields[3], 60).map_err(PyOverflowError::new_err)?;
        let (hours, days) = carry_once(hours, fields[2], 24).map_err(PyOverflowError::new_err)?;
        let (months, years) =
            carry_once(fields[1], fields[0], 12).map_err(PyOverflowError::new_err)?;
        let mut words = self.fields;
        let retained = words[1] as u32 & 12;
        let clock = hours | minutes | seconds | us;
        let truth = retained & 4 != 0 || years | months | days | clock != 0;
        let flags = retained | u32::from(truth) | (u32::from(retained & 8 != 0 || clock != 0) << 1);
        words[0] = years as u64;
        words[1] = u64::from(flags) | ((hours as u64) << 32);
        words[2] = minutes as u64 | ((seconds as u64) << 32);
        words[3] = (words[3] & (u64::from(u32::MAX) << 32)) | us as u64;
        words[7] = (words[7] & u64::from(u32::MAX)) | ((months as u64) << 32);
        Ok(Self {
            fields: words,
            days,
            hash_code: AtomicIsize::new(-1),
        })
    }

    /// Combine checked NumPy microseconds using the same normalized duration parts.
    ///
    /// An i64 microsecond count spans at most 106751992 days, within Python's
    /// timedelta day range. Floor division preserves negative subsecond values.
    /// # Errors
    /// Retains with_duration_parts' checked arithmetic and normalization errors.
    fn with_microseconds(&self, value: i64, subtract: bool, reverse: bool) -> PyResult<Self> {
        let days = value.div_euclid(86_400_000_000);
        let rest = value.rem_euclid(86_400_000_000);
        self.with_duration_parts(days, rest / 1_000_000, rest % 1_000_000, subtract, reverse)
    }
    /// Clone canonical immutable words and their valid cached hash.
    pub(crate) fn copied(&self) -> Self {
        // All words and derived flags are immutable and already canonical.
        // A fresh atomic retains the valid hash without unpacking/re-encoding.
        Self {
            fields: self.fields,
            days: self.days,
            hash_code: AtomicIsize::new(self.cached_hash()),
        }
    }

    // Only normalize(), fully checked external restore, or trusted snapshots
    // produce this input. They establish i32 bounds for every field except years and days.
    /// Encode a validated immutable snapshot and derive its cached flags.
    ///
    /// # Preconditions
    /// Years and days fit i64; all other fields fit i32. Only checked normalization,
    /// validated external restore or a trusted snapshot may supply fields.
    #[inline(always)]
    fn from_normalized(fields: [i64; 15], cache: isize) -> Self {
        let truth = storage_flags(&fields);
        Self {
            fields: std::array::from_fn(|pair| pack_pair(&fields, truth, pair)),
            days: fields[2],
            hash_code: AtomicIsize::new(cache),
        }
    }

    /// Read the immutable packed words once for a trusted native operation.
    #[inline(always)]
    fn words(&self) -> [u64; 8] {
        self.fields
    }

    /// Return the 15 signed fields in relative-then-absolute public field order.
    ///
    /// Reads occur while the accepted GIL interpreter is attached; no callback runs
    /// between field loads.
    #[inline(always)]
    pub(crate) fn snapshot(&self) -> [i64; 15] {
        let mut fields = [0; 15];
        fields[0] = self.fields[0] as i64;
        for pair in 1..8 {
            let bits = self.fields[pair];
            let first = pair * 2;
            fields[first] = i64::from(bits as u32 as i32);
            if pair == 7 {
                fields[1] = i64::from((bits >> 32) as u32 as i32);
            } else {
                fields[first + 1] = i64::from((bits >> 32) as u32 as i32);
            }
        }
        fields[2] = self.days;
        fields
    }

    // A date has no clock fields. If no Delta clock component can contribute
    // a day, omit those reads/unpacks; absolute0 and unset-1 both contribute0.
    // Datetime always receives every actual field, including explicit zeroes.
    /// Read calendar fields, omitting clock reads only when a date needs no carry.
    ///
    /// Datetime callers always receive every field, including explicit zero values.
    #[inline(always)]
    pub(crate) fn calendar_snapshot(&self, datetime: bool) -> [i64; 15] {
        if datetime || self.fields[1] & 2 != 0 {
            return self.snapshot();
        }
        let relative = self.fields[0];
        let year = self.fields[3];
        let month_day = self.fields[4];
        let weekday = self.fields[5];
        [
            relative as i64,
            i64::from((self.fields[7] >> 32) as u32 as i32),
            self.days,
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

    /// Compare every trusted native field encoding, excluding the hash cache.
    #[inline]
    pub(crate) fn native_eq(&self, other: &Self) -> bool {
        self.days == other.days
            && self
                .fields
                .iter()
                .zip(&other.fields)
                .all(|(left, right)| left == right)
    }

    /// Recognize clock replacements that leave a checked datetime unchanged.
    ///
    /// Relative and calendar replacements must be absent. Clock access uses the
    /// same native datetime fields as the calendar kernel and invokes no callbacks.
    #[inline(always)]
    pub(crate) fn preserves_datetime_clock(&self, dt: &Bound<'_, pyo3::types::PyDateTime>) -> bool {
        use pyo3::types::PyTimeAccess;
        if self.fields[1] & 4 == 0 {
            return false;
        }
        // A different explicit clock value cheaply rejects this shortcut;
        // the complete calendar path still handles any cancelling increment.
        let same = |field: i32, actual: i32| field == -1 || field == actual;
        same(
            (self.fields[5] >> 32) as u32 as i32,
            i32::from(dt.get_hour()),
        ) && same(self.fields[6] as u32 as i32, i32::from(dt.get_minute()))
            && same(
                (self.fields[6] >> 32) as u32 as i32,
                i32::from(dt.get_second()),
            )
            && same(self.fields[7] as u32 as i32, dt.get_microsecond() as i32)
            && self.fields[0] == 0
            && self.days == 0
            && self.fields[7] >> 32 == 0
            && self.fields[1] >> 32 == 0
            && self.fields[2] == 0
            && self.fields[3] as u32 == 0
            && self.fields[3] >> 32 == u64::from(u32::MAX)
            && self.fields[4] == u64::MAX
            && self.fields[5] as u32 == u32::MAX
    }

    /// Return the Python tuple hash cache, where -1 means not yet calculated.
    #[inline(always)]
    pub(crate) fn cached_hash(&self) -> isize {
        self.hash_code.load(Ordering::Relaxed)
    }

    /// Calculate and cache the Python hash of the 15-field snapshot tuple.
    ///
    /// # Errors
    /// Propagates tuple allocation/hash errors on the interpreter fallback.
    #[cold]
    #[inline(never)]
    fn compute_hash(&self, py: Python<'_>) -> PyResult<isize> {
        let fields = self.snapshot();
        let value = if NATIVE_TUPLE_HASH.load(Ordering::Relaxed) {
            integer_tuple_hash(&fields)
        } else {
            PyTuple::new(py, fields)?.hash()?
        };
        self.hash_code.store(value, Ordering::Relaxed);
        Ok(value)
    }

    /// Build an immutable payload from a checked serialization or native snapshot.
    ///
    /// # Preconditions
    /// Fields are canonical and in range; cache is -1 or their verified hash.
    pub(crate) fn from_snapshot(fields: [i64; 15], cache: isize) -> Self {
        Self::from_normalized(fields, cache)
    }
    /// Read relative field index 0..=6; days retains its separate signed 64-bit width.
    #[inline(always)]
    pub(crate) fn relative(&self, index: usize) -> i64 {
        if index == 0 {
            self.fields[0] as i64
        } else if index == 1 {
            i64::from((self.fields[7] >> 32) as u32 as i32)
        } else if index == 2 {
            self.days
        } else {
            let word = self.fields[index / 2];
            i64::from((word >> ((index & 1) * 32)) as u32 as i32)
        }
    }

    /// Read absolute field index 7..=14, mapping the unset -1 marker to None.
    fn absolute(&self, index: usize) -> Option<i64> {
        let value = self.relative(index);
        (value != -1).then_some(value)
    }
}

/// A right-hand Delta prepared once for a batch of additions.
///
/// Relative components are canonical; absolute masks retain the left field
/// wherever the right-hand value is unset. No Python objects or callbacks live
/// in this preparation.
pub(crate) struct PreparedAddition {
    relative: [i64; 7],
    masks: [u64; 8],
    replacements: [u64; 8],
    words: [u64; 8],
    absolute_set: bool,
    absolute_clock_set: bool,
    absolute_clock_positive: bool,
    lower_clock_empty: bool,
    day_hour_only: bool,
}

impl PreparedAddition {
    /// Report whether this immutable right operand contains any replacements.
    #[inline]
    pub(crate) fn has_absolute(&self) -> bool {
        self.absolute_set
    }

    /// Capture the immutable, checked right-hand value once.
    pub(crate) fn new(value: &Delta) -> Self {
        let fields = value.snapshot();
        let mut masks = [u64::MAX; 8];
        let mut replacements = [0; 8];
        for index in 7..15 {
            if fields[index] != -1 {
                let shift = (index & 1) * 32;
                masks[index / 2] &= !(u64::from(u32::MAX) << shift);
                replacements[index / 2] |= u64::from(fields[index] as i32 as u32) << shift;
            }
        }
        Self {
            relative: std::array::from_fn(|index| fields[index]),
            masks,
            replacements,
            words: value.words(),
            absolute_set: fields[7..].iter().any(|value| *value != -1),
            absolute_clock_set: fields[11..].iter().any(|value| *value != -1),
            absolute_clock_positive: fields[11..].iter().any(|value| *value > 0),
            lower_clock_empty: fields[4] | fields[5] | fields[6] == 0,
            day_hour_only: fields[0] | fields[1] | fields[4] | fields[5] | fields[6] == 0,
        }
    }

    /// Normalize only the seven relative components and retain the absolute words.
    ///
    /// # Preconditions
    /// left and words came from canonical native values or a builtin timedelta.
    /// # Errors
    /// Preserves day-first addition and checked signed64 year/month carries.
    #[inline(always)]
    fn finish(
        &self,
        left: [i64; 7],
        mut words: [u64; 8],
        left_absolute: bool,
        left_absolute_clock: bool,
    ) -> PyResult<Delta> {
        let failure = || PyOverflowError::new_err("integer overflow in Delta arithmetic");
        // Match scalar addition: wide year addition is checked before day
        // addition and clock carries, even when several inputs would overflow.
        let mut years = left[0].checked_add(self.relative[0]).ok_or_else(failure)?;
        let mut days = left[2].checked_add(self.relative[2]).ok_or_else(failure)?;
        let mut hours = left[3] + self.relative[3];
        let (microseconds, seconds, minutes) = if self.lower_clock_empty {
            // A zero RHS component cannot carry a canonical left component.
            // One prepared branch replaces repeated lower-unit additions and
            // checks for day/hour and replacement-only batches.
            (left[6], left[5], left[4])
        } else {
            let mut minutes = left[4] + self.relative[4];
            let mut seconds = left[5] + self.relative[5];
            let mut microseconds = left[6] + self.relative[6];
            if microseconds >= 1_000_000 {
                microseconds -= 1_000_000;
                seconds += 1;
            }
            if seconds >= 60 {
                seconds -= 60;
                minutes += 1;
            }
            if minutes >= 60 {
                minutes -= 60;
                hours += 1;
            }
            (microseconds, seconds, minutes)
        };
        if hours >= 24 {
            hours -= 24;
            days = days
                .checked_add(1)
                .ok_or_else(|| PyOverflowError::new_err(OVERFLOW))?;
        }
        let mut months = left[1] + self.relative[1];
        if months >= 12 {
            months -= 12;
            years = years
                .checked_add(1)
                .ok_or_else(|| PyOverflowError::new_err(OVERFLOW))?;
        }
        let absolute = left_absolute || self.absolute_set;
        let absolute_clock = if self.absolute_clock_positive {
            true
        } else if !self.absolute_clock_set {
            left_absolute_clock
        } else {
            // Explicit zero can remove a previous positive replacement. Inspect
            // the merged clock words rather than inheriting a stale carry flag.
            ((words[5] >> 32) as u32 as i32 > 0)
                | (words[6] as u32 as i32 > 0)
                | ((words[6] >> 32) as u32 as i32 > 0)
                | (words[7] as u32 as i32 > 0)
        };
        let time = hours | minutes | seconds | microseconds;
        let truth = absolute || years | months | days | time != 0;
        let flags = i32::from(truth)
            | (i32::from(absolute_clock || time != 0) << 1)
            | (i32::from(absolute) << 2)
            | (i32::from(absolute_clock) << 3);
        // Values were checked or bounded by canonical single-carry arithmetic.
        // Absolute bits were merged only from validated native replacements.
        words[0] = years as u64;
        words[7] = (words[7] & u64::from(u32::MAX)) | ((months as u64) << 32);
        words[1] = u64::from(flags as u32) | ((hours as u64) << 32);
        words[2] = minutes as u64 | ((seconds as u64) << 32);
        words[3] = (words[3] & (u64::from(u32::MAX) << 32)) | microseconds as u64;
        Ok(Delta {
            fields: words,
            days,
            hash_code: AtomicIsize::new(-1),
        })
    }

    /// Add a canonical native left operand without unpacking its absolute fields.
    ///
    /// # Errors
    /// Preserves the finish helper's checked arithmetic errors.
    #[inline(always)]
    pub(crate) fn add_delta(&self, value: &Delta) -> PyResult<Delta> {
        if self.absolute_set {
            self.add_delta_prepared::<true>(value)
        } else {
            self.add_delta_prepared::<false>(value)
        }
    }

    /// Apply the replacement mode selected once for a native batch.
    ///
    /// # Preconditions
    /// REPLACE must equal has_absolute(); this value remains immutable throughout
    /// the batch. Each left operand still has its own validated native fields.
    ///
    /// # Errors
    /// Preserves checked day/year arithmetic and single-carry normalization.
    #[inline(always)]
    pub(crate) fn add_delta_prepared<const REPLACE: bool>(&self, value: &Delta) -> PyResult<Delta> {
        let mut words = value.words();
        let flags = words[1] as u32;
        if self.day_hour_only {
            // Unchanged canonical years/months and lower clock words need no
            // unpack/repack or carry. This applies to any day/hour increment
            // with arbitrary replacements, not particular amounts or sizes.
            let mut days = value
                .days
                .checked_add(self.relative[2])
                .ok_or_else(|| PyOverflowError::new_err("integer overflow in Delta arithmetic"))?;
            let mut hours = (words[1] >> 32) + self.relative[3] as u64;
            if hours >= 24 {
                hours -= 24;
                days = days
                    .checked_add(1)
                    .ok_or_else(|| PyOverflowError::new_err(OVERFLOW))?;
            }
            if REPLACE {
                for (index, word) in words.iter_mut().enumerate().skip(3) {
                    *word = (*word & self.masks[index]) | self.replacements[index];
                }
            }
            let absolute = flags & 4 != 0 || REPLACE;
            let absolute_clock = if !REPLACE {
                flags & 8 != 0
            } else if self.absolute_clock_positive {
                true
            } else if !self.absolute_clock_set {
                flags & 8 != 0
            } else {
                ((words[5] >> 32) as u32 as i32 > 0)
                    | (words[6] as u32 as i32 > 0)
                    | ((words[6] >> 32) as u32 as i32 > 0)
                    | (words[7] as u32 as i32 > 0)
            };
            let time = hours | words[2] | (words[3] & u64::from(u32::MAX));
            let truth = absolute || words[0] | (words[7] >> 32) | days as u64 | time != 0;
            let flags = u64::from(truth)
                | (u64::from(absolute_clock || time != 0) << 1)
                | (u64::from(absolute) << 2)
                | (u64::from(absolute_clock) << 3);
            words[1] = flags | (hours << 32);
            return Ok(Delta {
                fields: words,
                days,
                hash_code: AtomicIsize::new(-1),
            });
        }
        let left = [
            words[0] as i64,
            i64::from((words[7] >> 32) as u32 as i32),
            value.days,
            i64::from((words[1] >> 32) as u32 as i32),
            i64::from(words[2] as u32 as i32),
            i64::from((words[2] >> 32) as u32 as i32),
            i64::from(words[3] as u32 as i32),
        ];
        if REPLACE {
            for (index, word) in words.iter_mut().enumerate().skip(3) {
                *word = (*word & self.masks[index]) | self.replacements[index];
            }
        }
        self.finish(left, words, flags & 4 != 0, flags & 8 != 0)
    }

    /// Add foreign fields through their full normalization and the prepared kernel.
    /// # Errors
    /// Preserves foreign normalization and scalar arithmetic overflow ordering.
    #[inline(always)]
    pub(crate) fn add_fields(&self, fields: [i64; 15]) -> PyResult<Delta> {
        let fields = normalize_external_fields(fields).map_err(PyOverflowError::new_err)?;
        let mut words = self.words;
        for (index, field) in fields.iter().enumerate().skip(7) {
            let shift = (index & 1) * 32;
            let mask = u64::from(u32::MAX) << shift;
            if self.masks[index / 2] & mask != 0 {
                words[index / 2] =
                    (words[index / 2] & !mask) | (u64::from(*field as i32 as u32) << shift);
            }
        }
        self.finish(
            std::array::from_fn(|index| fields[index]),
            words,
            fields[7..].iter().any(|field| *field != -1),
            fields[11..].iter().any(|field| *field > 0),
        )
    }

    /// Add checked NumPy microseconds using canonical primitive duration parts.
    /// # Errors
    /// Preserves checked day carries and the same normalization as timedelta.
    #[inline(always)]
    pub(crate) fn add_microseconds(&self, micros: i64) -> PyResult<Delta> {
        let seconds = micros.rem_euclid(86_400_000_000) / 1_000_000;
        self.finish(
            [
                0,
                0,
                micros.div_euclid(86_400_000_000),
                seconds / 3600,
                seconds / 60 % 60,
                seconds % 60,
                micros.rem_euclid(1_000_000),
            ],
            self.words,
            false,
            false,
        )
    }

    /// Add a builtin timedelta with the right-hand Delta's absolute words.
    ///
    /// # Errors
    /// Preserves checked day carries and normalization errors.
    #[inline(always)]
    pub(crate) fn add_duration(&self, value: &Bound<'_, PyDelta>) -> PyResult<Delta> {
        let seconds = i64::from(value.get_seconds());
        let left = [
            0,
            0,
            i64::from(value.get_days()),
            seconds / 3600,
            seconds / 60 % 60,
            seconds % 60,
            i64::from(value.get_microseconds()),
        ];
        self.finish(left, self.words, false, false)
    }
}

// Bit0 is ordinary truth; bit1 marks clock components that may contribute
// days when applied to a date. Bit2 marks any absolute replacement, bit3 a
// positive absolute clock component. All are derived at each checked commit.
/// Derive truth and date clock-carry flags from a validated field snapshot.
fn storage_flags(fields: &[i64; 15]) -> i32 {
    // Canonical replacements are either -1 or nonnegative. Their bitwise AND
    // is -1 exactly when every replacement is unset; relative OR is zero
    // exactly when all increments are zero. This avoids per-field branches.
    let relative = fields[..7].iter().fold(0, |bits, value| bits | value);
    let absolute = fields[7..].iter().fold(-1, |bits, value| bits & value);
    let truth = relative != 0 || absolute != -1;
    let time = fields[3] | fields[4] | fields[5] | fields[6];
    let clock =
        time != 0 || (fields[11] > 0) | (fields[12] > 0) | (fields[13] > 0) | (fields[14] > 0);
    i32::from(truth)
        | (i32::from(clock) << 1)
        | (i32::from(absolute != -1) << 2)
        | (i32::from((fields[11] > 0) | (fields[12] > 0) | (fields[13] > 0) | (fields[14] > 0))
            << 3)
}

// Storage encoding only: all bounded fields were checked before reaching
// here. Casting to u32 preserves signed32 bits; reads sign-extend them again.
// pair is an internal0..8 array index, so both shifts and indices are bounded.
/// Encode bounded field pairs, full years, and month placement into eight words.
///
/// # Preconditions
/// pair is0..8; years/days fit i64, other fields fit i32. Slot2 stores derived flags.
/// Years occupy word0; months reuse the former padding half of word7.
#[inline]
const fn pack_pair(fields: &[i64; 15], truth: i32, pair: usize) -> u64 {
    if pair == 0 {
        return fields[0] as u64;
    }
    let first = pair * 2;
    let low = if first == 2 {
        truth as u32
    } else {
        fields[first] as i32 as u32
    };
    let high = if pair == 7 {
        fields[1] as u32
    } else {
        fields[first + 1] as i32 as u32
    };
    // Lossless widening is const-evaluable on the project's stable Rust.
    low as u64 | ((high as u64) << 32)
}

/// Map each of the 19 public constructor keyword names to its positional index.
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

/// Convert a Python value using the frozen __int__ contract and integer width.
///
/// # Arguments
/// All public numeric inputs use checked signed 64-bit conversion.
/// An __index__-only object is not sufficient for a non-int input.
///
/// # Errors
/// Raises TypeError for unsupported numeric conversion and OverflowError for
/// unrepresentable values; Python conversion callback exceptions propagate.
#[inline]
pub(crate) fn input_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
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
    converted_integer(integer)
}

/// Extract an already-qualified integer using the frozen width and error text.
///
/// The caller established PyInt membership or completed the numeric conversion.
/// # Errors
/// Propagates conversion errors and rejects inputs outside signed 64-bit range.
#[inline(always)]
fn converted_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    let number = value.extract::<i64>().map_err(|error| {
        if error.is_instance_of::<PyOverflowError>(value.py()) {
            PyOverflowError::new_err("Python int too large to convert to C long")
        } else {
            error
        }
    })?;
    Ok(number)
}

/// Native constructor inputs with a bounded fractional microsecond remainder.
/// Integers stay exact and separate from floating point even beyond 2**53.
struct Inputs {
    whole: [i64; 19],
    fraction: f64,
}

impl Inputs {
    /// Round the combined fractional duration once, including integer parity.
    /// # Errors
    /// Rejects a real microsecond addition outside the checked integer range.
    #[inline]
    fn rounded(mut self) -> PyResult<[i64; 19]> {
        if self.fraction != 0.0 {
            // Seven fractional parts scaled by fixed, finite unit factors fit
            // well inside i64. Whole integer microseconds determine half parity.
            let floor = self.fraction.floor() as i64;
            let remainder = self.fraction - floor as f64;
            let up = remainder > 0.5 || (remainder == 0.5 && ((self.whole[9] ^ floor) & 1 != 0));
            let rounded = floor + i64::from(up);
            self.whole[9] = self.whole[9]
                .checked_add(rounded)
                .ok_or_else(|| PyOverflowError::new_err(OVERFLOW))?;
        }
        Ok(self.whole)
    }
}

/// Split a real float's integer and fixed-unit fractional parts without Python
/// temporary numbers. Non-finite values and whole-part overflow are explicit.
/// # Errors
/// Raises ValueError for NaN and OverflowError for infinity/unrepresentable input.
#[inline]
fn fractional_input(value: &Bound<'_, PyAny>, index: usize, fraction: &mut f64) -> PyResult<i64> {
    // Caller proved actual PyFloat membership before this unchecked layout cast.
    let number = unsafe { value.cast_unchecked::<PyFloat>() }.value();
    if number.is_nan() {
        return Err(PyValueError::new_err("Delta duration must be finite"));
    }
    if !number.is_finite()
        || !(-9_223_372_036_854_775_808.0..9_223_372_036_854_775_808.0).contains(&number)
    {
        return Err(PyOverflowError::new_err(
            "Delta duration is outside the signed 64-bit input range",
        ));
    }
    let whole = number.trunc() as i64;
    let factor = [
        604_800_000_000.0,
        86_400_000_000.0,
        3_600_000_000.0,
        60_000_000.0,
        1_000_000.0,
        1_000.0,
        1.0,
    ][index - 3];
    *fraction += (number - number.trunc()) * factor;
    Ok(whole)
}

/// Keep integer conversion first; only the seven fixed units read float data.
/// # Errors
/// Retains legacy custom conversion callbacks and new fractional input errors.
#[inline]
fn constructor_input(value: &Bound<'_, PyAny>, index: usize, fraction: &mut f64) -> PyResult<i64> {
    if value.cast::<PyInt>().is_ok() {
        return converted_integer(value);
    }
    if (3..10).contains(&index) && value.cast::<PyFloat>().is_ok() {
        return fractional_input(value, index, fraction);
    }
    input_integer(value)
}

/// Read up to 19 positional/keyword arguments without committing object fields.
///
/// # Errors
/// Rejects excess/unknown/duplicate arguments and propagates numeric conversion
/// errors. The single-keyword path applies the same conversion rules.
fn parse_inputs(args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Inputs> {
    if args.is_empty() && kwargs.is_none_or(|values| values.is_empty()) {
        // No argument can invoke a conversion callback or carry an error.
        // Avoid scanning the borrowed multi-argument slots for the empty form.
        let mut inputs = [0; 19];
        inputs[10..].fill(-1);
        return Ok(Inputs {
            whole: inputs,
            fraction: 0.0,
        });
    }
    if args.len() > 19 {
        return Err(PyTypeError::new_err(format!(
            "__init__() takes at most 19 positional arguments ({} given)",
            args.len()
        )));
    }
    if !args.is_empty() || kwargs.is_some_and(|values| values.len() > 1) {
        if args.is_empty()
            && let Some(kwargs) = kwargs.filter(|values| values.len() == 2)
            && let Some(result) = parse_two_keywords(kwargs)
        {
            return result;
        }
        if let Some(result) = parse_plain_inputs(args, kwargs) {
            return result;
        }
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
                    let mut fraction = 0.0;
                    inputs[index] = constructor_input(&value, index, &mut fraction)?;
                    return Ok(Inputs {
                        whole: inputs,
                        fraction,
                    });
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
    let mut fraction = 0.0;
    for (index, value) in values.iter().enumerate() {
        if let Some(value) = value {
            inputs[index] = constructor_input(value, index, &mut fraction)?;
        }
    }
    Ok(Inputs {
        whole: inputs,
        fraction,
    })
}

/// Read two primitive keyword values without preparing 19 pointer slots.
///
/// Both keyword names are validated before conversion. Only actual integers
/// and fixed-unit floats qualify, so the live dictionary retains both values
/// without any intervening Python callback. Other inputs use the owned path.
/// # Preconditions
/// The caller proved kwargs contains exactly two entries under the GIL.
/// # Errors
/// Preserves shape errors, ascending parameter conversion and numeric errors.
fn parse_two_keywords(kwargs: &Bound<'_, PyDict>) -> Option<PyResult<Inputs>> {
    let py = kwargs.py();
    let mut entries = [(0_usize, std::ptr::null_mut(), false); 2];
    let names = keyword_names(py);
    let mut position = 0;
    let mut key = std::ptr::null_mut();
    let mut value = std::ptr::null_mut();
    for entry in &mut entries {
        // SAFETY: the checked dictionary has exactly two entries. No callback
        // or mutation occurs while its borrowed entries are captured.
        unsafe { pyo3::ffi::PyDict_Next(kwargs.as_ptr(), &mut position, &mut key, &mut value) };
        let index = if let Some(index) = names.iter().position(|name| name.as_ptr() == key) {
            index
        } else {
            let key_value = unsafe { Borrowed::from_ptr(py, key) };
            let key_value = match key_value.cast::<PyString>() {
                Ok(key) => key,
                Err(error) => return Some(Err(error.into())),
            };
            let name = match key_value.to_str() {
                Ok(name) => name,
                Err(error) => return Some(Err(error)),
            };
            let Some(index) = parameter_index(name) else {
                return Some(Err(PyTypeError::new_err(format!(
                    "__init__() got an unexpected keyword argument '{name}'"
                ))));
            };
            index
        };
        let floating = unsafe { pyo3::ffi::PyLong_Check(value) } == 0;
        if floating
            && (!(3..10).contains(&index) || unsafe { pyo3::ffi::PyFloat_Check(value) } == 0)
        {
            return None;
        }
        *entry = (index, value, floating);
    }
    if entries[0].0 == entries[1].0 {
        let name = keyword_names(py)[entries[0].0].bind(py);
        let name = match name.to_str() {
            Ok(name) => name,
            Err(error) => return Some(Err(error)),
        };
        return Some(Err(PyTypeError::new_err(format!(
            "__init__() got multiple values for keyword argument '{name}'"
        ))));
    }
    if entries[1].0 < entries[0].0 {
        entries.swap(0, 1);
    }
    let mut inputs = [0_i64; 19];
    inputs[10..].fill(-1);
    let mut fraction = 0.0;
    for (index, value, floating) in entries {
        // SAFETY: primitive qualification above excludes numeric callbacks;
        // the live dictionary still owns both borrowed values.
        let value = unsafe { Borrowed::from_ptr(py, value) };
        let number = if floating {
            fractional_input(&value, index, &mut fraction)
        } else {
            converted_integer(&value)
        };
        match number {
            Ok(number) => inputs[index] = number,
            Err(error) => return Some(Err(error)),
        }
    }
    Some(Ok(Inputs {
        whole: inputs,
        fraction,
    }))
}

/// Borrow constructor values only when every supplied value is a native integer
/// or a fixed-unit float that cannot invoke a conversion callback.
///
/// Integer extraction cannot invoke Python callbacks, so the live tuple/dictionary
/// keeps all pointers valid until conversion finishes. Non-int objects fall back
/// to the owned snapshot path before any conversion. Shape validation still
/// precedes conversion, and conversion still follows the 19-parameter order.
///
/// # Errors
/// Returns the existing shape/conversion errors; None requests the callback-safe path.
fn parse_plain_inputs(
    args: &Bound<'_, PyTuple>,
    kwargs: Option<&Bound<'_, PyDict>>,
) -> Option<PyResult<Inputs>> {
    let py = args.py();
    let mut values = [std::ptr::null_mut(); 19];
    let mut floats = 0_u32;
    for (index, slot) in values.iter_mut().take(args.len()).enumerate() {
        // A checked, live tuple owns the item; the caller bounded its length.
        let value = unsafe { pyo3::ffi::PyTuple_GET_ITEM(args.as_ptr(), index as isize) };
        if unsafe { pyo3::ffi::PyLong_Check(value) } == 0 {
            if (3..10).contains(&index) && unsafe { pyo3::ffi::PyFloat_Check(value) } != 0 {
                floats |= 1 << index;
            } else {
                return None;
            }
        }
        *slot = value;
    }
    if let Some(kwargs) = kwargs {
        let mut position = 0;
        let mut key = std::ptr::null_mut();
        let mut value = std::ptr::null_mut();
        let names = keyword_names(py);
        // The live dictionary is never mutated and no Python callback executes
        // during this scan or native-int conversion. PyDict_Next borrows its entries.
        while unsafe {
            pyo3::ffi::PyDict_Next(kwargs.as_ptr(), &mut position, &mut key, &mut value)
        } != 0
        {
            let index = if let Some(index) = names.iter().position(|name| name.as_ptr() == key) {
                index
            } else {
                // Uninterned strings and string subclasses retain the original
                // validation, unknown-key error and numeric-callback ordering.
                let key = unsafe { Borrowed::from_ptr(py, key) };
                let key = match key.cast::<PyString>() {
                    Ok(key) => key,
                    Err(error) => return Some(Err(error.into())),
                };
                let name = match key.to_str() {
                    Ok(name) => name,
                    Err(error) => return Some(Err(error)),
                };
                let Some(index) = parameter_index(name) else {
                    return Some(Err(PyTypeError::new_err(format!(
                        "__init__() got an unexpected keyword argument '{name}'"
                    ))));
                };
                index
            };
            if !values[index].is_null() {
                let name = match names[index].bind(py).to_str() {
                    Ok(name) => name,
                    Err(error) => return Some(Err(error)),
                };
                return Some(Err(PyTypeError::new_err(format!(
                    "__init__() got multiple values for keyword argument '{name}'"
                ))));
            }
            if unsafe { pyo3::ffi::PyLong_Check(value) } == 0 {
                if (3..10).contains(&index) && unsafe { pyo3::ffi::PyFloat_Check(value) } != 0 {
                    floats |= 1 << index;
                } else {
                    return None;
                }
            }
            values[index] = value;
        }
    }
    let mut inputs = [0_i64; 19];
    inputs[10..].fill(-1);
    let mut fraction = 0.0;
    if floats == 0 {
        // Preserve the existing all-integer loop, without per-value float tests.
        for (index, &value) in values.iter().enumerate() {
            if !value.is_null() {
                let value = unsafe { Borrowed::from_ptr(py, value) };
                match converted_integer(&value) {
                    Ok(number) => inputs[index] = number,
                    Err(error) => return Some(Err(error)),
                }
            }
        }
    } else {
        for (index, &value) in values.iter().enumerate() {
            if !value.is_null() {
                let value = unsafe { Borrowed::from_ptr(py, value) };
                let result = if floats & (1 << index) != 0 {
                    fractional_input(&value, index, &mut fraction)
                } else {
                    converted_integer(&value)
                };
                match result {
                    Ok(number) => inputs[index] = number,
                    Err(error) => return Some(Err(error)),
                }
            }
        }
    }
    Some(Ok(Inputs {
        whole: inputs,
        fraction,
    }))
}

const OVERFLOW: &str = "integer overflow in Delta normalization";

/// Normalize a child unit using floor division and checked parent addition.
///
/// # Errors
/// Rejects parent overflow; base is a positive internal unit constant.
fn carry(value: i64, parent: i64, base: i64) -> Result<(i64, i64), &'static str> {
    if (0..base).contains(&value) {
        return Ok((value, parent));
    }
    Ok((
        value.rem_euclid(base),
        parent.checked_add(value.div_euclid(base)).ok_or(OVERFLOW)?,
    ))
}

/// Carry a sum/difference of two canonical components without division.
///
/// # Preconditions
/// value is in -base..2*base; a lower-unit carry is already included. These
/// bounds follow from validated native clock fields, including the all-zero raw
/// state. This helper never accepts an external constructor or restore value.
///
/// # Errors
/// Rejects parent overflow; the unbounded day field always retains this check.
#[inline(always)]
fn carry_once(value: i64, parent: i64, base: i64) -> Result<(i64, i64), &'static str> {
    if value >= base {
        Ok((value - base, parent.checked_add(1).ok_or(OVERFLOW)?))
    } else if value < 0 {
        Ok((value + base, parent.checked_sub(1).ok_or(OVERFLOW)?))
    } else {
        Ok((value, parent))
    }
}

/// Normalize native relative arithmetic, retaining validated replacements.
///
/// # Preconditions
/// Relative clock/month inputs come only from addition, subtraction or negation
/// of normalized native components. Months are -11..22; clock components can
/// require at most one carry/borrow. Absolute fields are already validated; only
/// raw year/month/day zeroes need conversion to the constructor's unset marker.
///
/// # Errors
/// Preserves clock-to-day order and checked signed64 day/year/month carries.
#[inline(always)]
fn normalize_native_fields(mut fields: [i64; 15]) -> Result<[i64; 15], &'static str> {
    let (us, seconds) = carry_once(fields[6], fields[5], 1_000_000)?;
    let (seconds, minutes) = carry_once(seconds, fields[4], 60)?;
    let (minutes, hours) = carry_once(minutes, fields[3], 60)?;
    let (hours, days) = carry_once(hours, fields[2], 24)?;
    let mut years = fields[0];
    let mut months = fields[1];
    if months >= 12 {
        months -= 12;
        years = years.checked_add(1).ok_or(OVERFLOW)?;
    } else if months < 0 {
        months += 12;
        years = years.checked_sub(1).ok_or(OVERFLOW)?;
    }
    fields[..7].copy_from_slice(&[years, months, days, hours, minutes, seconds, us]);
    for value in &mut fields[7..10] {
        if *value == 0 {
            *value = -1;
        }
    }
    Ok(fields)
}

/// Clamp a constructor replacement, retaining allowed zeroes and unset -1.
fn absolute(number: i64, maximum: i64, zero_allowed: bool) -> i64 {
    if number > 0 || (zero_allowed && number == 0) {
        number.min(maximum)
    } else {
        -1
    }
}

/// Append a signed decimal field using bounded ASCII digits without formatting state.
///
/// unsigned_abs handles i64::MIN. The twenty-byte buffer covers every u64 value;
/// converting each generated ASCII digit to char requires no unsafe UTF-8 operation.
fn append_integer(text: &mut String, value: i64) {
    let mut digits = [0_u8; 20];
    let mut cursor = digits.len();
    let mut number = value.unsigned_abs();
    loop {
        cursor -= 1;
        digits[cursor] = b'0' + (number % 10) as u8;
        number /= 10;
        if number == 0 {
            break;
        }
    }
    if value < 0 {
        text.push('-');
    }
    text.extend(digits[cursor..].iter().map(|digit| char::from(*digit)));
}

/// Format the fixed native class name and integer fields without a temporary heap string.
///
/// All labels are ASCII and fields are validated integers. The 512-byte stack
/// buffer exceeds the maximum 15-field native representation; checked slices
/// retain a bounded error path if the internal labels ever grow.
///
/// # Errors
/// Raises RuntimeError for an inconsistent internal buffer; allocation errors
/// from the public Python Unicode constructor propagate unchanged.
fn exact_representation<'py>(
    py: Python<'py>,
    fields: &[i64; 15],
    names: &[&str; 15],
) -> PyResult<Bound<'py, PyString>> {
    let mut bytes = [0_u8; 512];
    let mut length = 0;
    let mut append = |text: &[u8]| -> PyResult<()> {
        let end = length + text.len();
        bytes
            .get_mut(length..end)
            .ok_or_else(|| PyRuntimeError::new_err("Delta representation buffer exceeded"))?
            .copy_from_slice(text);
        length = end;
        Ok(())
    };
    append(b"<'Delta' (")?;
    let mut separated = false;
    for (index, (&name, &value)) in names.iter().zip(fields).enumerate() {
        if (index < 7 && value == 0) || (index >= 7 && value == -1) {
            continue;
        }
        if separated {
            append(b", ")?;
        }
        separated = true;
        append(name.as_bytes())?;
        append(b"=")?;
        if index == 10 {
            append([b"MO", b"TU", b"WE", b"TH", b"FR", b"SA", b"SU"][value as usize])?;
        } else {
            if value < 0 {
                append(b"-")?;
            }
            let mut digits = [0_u8; 20];
            let mut cursor = digits.len();
            let mut number = value.unsigned_abs();
            loop {
                cursor -= 1;
                digits[cursor] = b'0' + (number % 10) as u8;
                number /= 10;
                if number == 0 {
                    break;
                }
            }
            append(&digits[cursor..])?;
        }
    }
    append(b")>")?;
    // SAFETY: Only fixed ASCII labels, punctuation and integer digits were
    // appended. The checked buffer remains live through this public API call,
    // which copies its one-byte code points into an owned Unicode object.
    // Subclass names keep the separate Unicode-aware path below.
    let value = unsafe {
        pyo3::ffi::PyUnicode_FromKindAndData(
            pyo3::ffi::PyUnicode_1BYTE_KIND as std::ffi::c_int,
            bytes.as_ptr().cast(),
            length as pyo3::ffi::Py_ssize_t,
        )
    };
    let value = unsafe { Bound::from_owned_ptr_or_err(py, value) }?;
    // The public constructor guarantees a Unicode result after a non-null return.
    Ok(unsafe { value.cast_into_unchecked::<PyString>() })
}

/// Apply the full constructor rules to a foreign 15-field snapshot.
///
/// # Errors
/// Retains clock-first overflow, checked month/year widths and absolute clamping.
#[inline]
fn normalize_external_fields(fields: [i64; 15]) -> Result<[i64; 15], &'static str> {
    let mut inputs = [0; 19];
    for (field, parameter) in [0, 2, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18]
        .into_iter()
        .enumerate()
    {
        inputs[parameter] = fields[field];
    }
    inputs[17] = -1;
    normalize(inputs)
}

/// Normalize all 19 constructor values into the 15 stored Delta fields.
///
/// Evaluation order and intermediate integer widths match the frozen reference;
/// negative remainders use floor division. Absolute units retain their original
/// clamping and millisecond/microsecond replacement rules.
///
/// # Errors
/// Rejects any real intermediate overflow, even when a later input could cancel it.
#[inline(always)]
fn normalize(inputs: [i64; 19]) -> Result<[i64; 15], &'static str> {
    if inputs[..10].iter().all(|value| *value == 0) {
        // Pure replacements have no relative arithmetic or possible relative
        // overflow. Preserve the same clamping without evaluating zero carries.
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
        return Ok([
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            absolute(inputs[10], 9_999, false),
            absolute(inputs[11], 12, false),
            absolute(inputs[12], 31, false),
            absolute(inputs[13], 6, true),
            absolute(inputs[14], 23, true),
            absolute(inputs[15], 59, true),
            absolute(inputs[16], 59, true),
            absolute_us,
        ]);
    }
    let us = inputs[9]
        .checked_add(inputs[8].checked_mul(1_000).ok_or(OVERFLOW)?)
        .ok_or(OVERFLOW)?;
    let (us, seconds) = carry(us, inputs[7], 1_000_000)?;
    let (seconds, minutes) = carry(seconds, inputs[6], 60)?;
    let (minutes, hours) = carry(minutes, inputs[5], 60)?;
    let (hours, days) = carry(hours, inputs[4], 24)?;
    let days = days
        .checked_add(inputs[3].checked_mul(7).ok_or(OVERFLOW)?)
        .ok_or(OVERFLOW)?;
    let months = inputs[2]
        .checked_add(inputs[1].checked_mul(3).ok_or(OVERFLOW)?)
        .ok_or(OVERFLOW)?;
    let years = inputs[0]
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
        years,
        months,
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
    /// Create a Delta from supported relativedelta fields.
    ///
    /// Parameters
    /// ----------
    /// rd : dateutil.relativedelta
    ///     Relative amounts and absolute settings to convert.
    ///
    /// Returns
    /// -------
    /// Delta
    ///     A new Delta, including when called through a Delta subclass.
    ///
    /// Raises
    /// ------
    /// InvalidRelativeDelta
    ///     rd is not a relativedelta instance.
    /// ValueError
    ///     weekday is set or leapdays is nonzero; Delta cannot preserve those rules.
    /// OverflowError
    ///     A converted value or calculation is outside the supported integer range.
    ///
    /// Notes
    /// -----
    /// The usual Delta rules for absolute settings still apply. Errors from custom
    /// normalization or numeric conversion are passed to the caller.
    ///
    /// Examples
    /// --------
    /// >>> from dateutil.relativedelta import relativedelta
    /// >>> Delta.from_relativedelta(relativedelta(months=1)).months
    /// 1
    #[classmethod]
    pub(crate) fn from_relativedelta(
        _class: &Bound<'_, PyType>,
        rd: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        Self::from_fields(crate::interop::relativedelta_fields(rd)?)
    }
    /// Convert this Delta to an exact standard-library time span.
    ///
    /// Parameters
    /// ----------
    /// start : date or datetime, optional
    ///     Starting value for calendar years, months or absolute replacements.
    ///     With a start, the result is (start + self) - start.
    ///
    /// Returns
    /// -------
    /// datetime.timedelta
    ///     The fixed span, or the difference at the supplied starting value.
    ///
    /// Raises
    /// ------
    /// ValueError
    ///     No start was supplied for years, months or an absolute replacement.
    /// TypeError
    ///     start is not a date or datetime.
    /// OverflowError
    ///     The fixed span is outside timedelta's supported range.
    ///
    /// Notes
    /// -----
    /// A date start gives a whole-day difference. For datetimes in the same
    /// time zone, Python's wall-clock subtraction rules apply across clock changes.
    /// Months are never approximated as a fixed number of days. Errors from
    /// applying the Delta to the starting value propagate.
    ///
    /// Examples
    /// --------
    /// >>> Delta(hours=25).to_timedelta()
    /// datetime.timedelta(days=1, seconds=3600)
    /// >>> Delta(months=1).to_timedelta(date(2024, 1, 31))
    /// datetime.timedelta(days=29)
    #[pyo3(signature = (start=None))]
    fn to_timedelta<'py>(
        slf: &Bound<'py, Self>,
        start: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyDelta>> {
        let py = slf.py();
        if let Some(start) = start {
            if !start.is_instance_of::<PyDate>() {
                return Err(PyTypeError::new_err("start must be a date or datetime"));
            }
            if slf.is_exact_instance_of::<Self>()
                && let Some(span) = crate::interop::builtin_span(slf.get(), start)?
            {
                return Ok(span);
            }
            let difference = start.add(slf)?.sub(start)?;
            return difference
                .cast_into::<PyDelta>()
                .map_err(|_| PyTypeError::new_err("date arithmetic did not produce a timedelta"));
        }
        let fields = slf.get().snapshot();
        if fields[0] != 0 || fields[1] != 0 || fields[7..].iter().any(|value| *value != -1) {
            return Err(PyValueError::new_err(
                "start is required for years, months or absolute fields",
            ));
        }
        if !(-999_999_999..=999_999_999).contains(&fields[2]) {
            return Err(PyOverflowError::new_err(
                "Delta is outside timedelta's supported range",
            ));
        }
        // All clock components are canonical. The explicit range check above
        // ensures the signed day narrowing is lossless before calling Python.
        PyDelta::new(
            py,
            fields[2] as i32,
            (fields[3] * 3600 + fields[4] * 60 + fields[5]) as i32,
            fields[6] as i32,
            false,
        )
    }
    /// Add this Delta to each value and return the results in order.
    ///
    /// Parameters
    /// ----------
    /// values : iterable
    ///     Values supporting value + self, including dates, datetimes, Delta,
    ///     timedelta, supported third-party scalars, or a mixture of these.
    ///
    /// Returns
    /// -------
    /// list
    ///     One result per input, with the same values and types as
    ///     [value + self for value in values]. An empty input returns [].
    ///
    /// Raises
    /// ------
    /// TypeError
    ///     values is not iterable or an item does not support addition.
    /// Exception
    ///     Errors from iteration or addition propagate. No partial list is
    ///     returned; a consumed iterator is not rewound.
    ///
    /// Examples
    /// --------
    /// >>> Delta(days=1).apply_many([date(2024, 1, 1), date(2024, 1, 2)])
    /// [datetime.date(2024, 1, 2), datetime.date(2024, 1, 3)]
    fn apply_many<'py>(
        slf: &Bound<'py, Self>,
        values: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyList>> {
        crate::bulk::apply(slf, values)
    }

    /// Create a fully initialized Delta value.
    ///
    /// The arguments are the same as Delta(...). Calling this method directly
    /// also returns a complete value; there is no empty initialization stage.
    #[new]
    #[pyo3(signature = (*args, **kwargs), text_signature = "(years=0, quarters=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0, year=-1, month=-1, day=-1, weekday=-1, hour=-1, minute=-1, second=-1, millisecond=-1, microsecond=-1)")]
    fn new(args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        Self::construct(args, kwargs)
    }

    /// Leave the value unchanged after construction.
    ///
    /// Notes
    /// -----
    /// Values are set by __new__. Calling __init__ again does not change any
    /// field or the object's hash. Construct a new Delta to use different values.
    #[pyo3(signature = (*args, **kwargs))]
    pub(crate) fn __init__(&self, args: &Bound<'_, PyTuple>, kwargs: Option<&Bound<'_, PyDict>>) {
        let _ = (args, kwargs);
    }

    /// Return whether a relative field is nonzero or an absolute field is set.
    ///
    /// Explicit absolute zero is set and therefore makes a Delta truthy.
    pub(crate) fn __bool__(&self) -> bool {
        self.fields[1] as u32 & 1 != 0
    }

    /// Compare the values of two Delta objects.
    ///
    /// Returns
    /// -------
    /// bool or NotImplemented
    ///     Whether all relative and absolute fields match. Other object types
    ///     return NotImplemented and follow Python's reflected comparison rules.
    ///
    /// Notes
    /// -----
    /// Delta subclasses that inherit this comparison use the same value rules.
    /// Equal Delta values have equal hashes and can share dictionary keys.
    pub(crate) fn __eq__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = other.py();
        let Ok(rhs) = other.cast::<Self>() else {
            return Ok(py.NotImplemented().into_bound(py));
        };
        Ok(PyBool::new(py, self.native_eq(rhs.get()))
            .to_owned()
            .into_any())
    }

    /// Compare two Delta values for inequality.
    ///
    /// Returns
    /// -------
    /// bool or NotImplemented
    ///     The opposite of field equality for Delta objects. Other types return
    ///     NotImplemented without converting the operand.
    pub(crate) fn __ne__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let py = other.py();
        let Ok(rhs) = other.cast::<Self>() else {
            return Ok(py.NotImplemented().into_bound(py));
        };
        Ok(PyBool::new(py, !self.native_eq(rhs.get()))
            .to_owned()
            .into_any())
    }

    /// Return a separate object with the same Delta value and type.
    ///
    /// Returns
    /// -------
    /// Delta
    ///     A shallow copy. Additional attribute values remain shared.
    fn __copy__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::copy_object(slf, None)
    }
    /// Return a distinct deep copy, preserving subtype and tracking cycles.
    ///
    /// Parameters
    /// ----------
    /// memo : dict
    ///     Python deepcopy's object-identity table, reused for recursion.
    ///
    /// Raises
    /// ------
    /// Exception
    ///     Allocation, subclass and recursive deepcopy errors propagate.
    fn __deepcopy__<'py>(
        slf: &Bound<'py, Self>,
        memo: &Bound<'py, PyDict>,
    ) -> PyResult<Bound<'py, PyAny>> {
        crate::state::copy_object(slf, Some(memo))
    }

    /// Return the saved fields and additional attributes used by this package.
    ///
    /// Returns
    /// -------
    /// tuple
    ///     State used by the package's save/restore support.
    ///
    /// Notes
    /// -----
    /// Use pickle or copy for ordinary saving and copying.
    fn __getstate__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::capture(slf)
    }
    /// Restore saved extra attributes while keeping this Delta value.
    ///
    /// Parameters
    /// ----------
    /// state : tuple, dict or None
    ///     State returned by this package, or the extra attributes used by pickle.
    ///
    /// Returns
    /// -------
    /// None
    ///
    /// Raises
    /// ------
    /// TypeError
    ///     The state has unsupported containers or value types.
    /// ValueError
    ///     The state is invalid or tries to change the Delta's fields.
    /// OverflowError
    ///     A saved integer is too large.
    ///
    /// Notes
    /// -----
    /// The object's value and hash cannot be replaced. Only load pickle data from
    /// trusted sources. Errors from subclass attribute handling are passed through.
    fn __setstate__(slf: &Bound<'_, Self>, state: &Bound<'_, PyAny>) -> PyResult<()> {
        crate::state::restore(slf, state)
    }
    /// Return the recipe used by pickle to save this Delta.
    ///
    /// Parameters
    /// ----------
    /// protocol : int
    ///     The protocol selected by pickle.
    ///
    /// Returns
    /// -------
    /// tuple
    ///     A reconstruction recipe that preserves the value and additional attributes.
    ///
    /// Notes
    /// -----
    /// Only load pickle data from trusted sources.
    fn __reduce_ex__<'py>(slf: &Bound<'py, Self>, _protocol: i32) -> PyResult<Bound<'py, PyAny>> {
        crate::state::reduce(slf)
    }
    /// Return the reconstruction recipe used by pickle.
    ///
    /// Returns
    /// -------
    /// tuple
    ///     The same recipe as __reduce_ex__.
    ///
    /// Notes
    /// -----
    /// Only load pickle data from trusted sources.
    fn __reduce__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::reduce(slf)
    }

    /// Return a stable hash based on the Delta value.
    ///
    /// Returns
    /// -------
    /// int
    ///     Equal Delta values have equal hashes.
    ///
    /// Notes
    /// -----
    /// Additional subclass attributes do not change the Delta value or its hash.
    #[inline]
    pub(crate) fn __hash__(&self, py: Python<'_>) -> PyResult<isize> {
        let cached = self.hash_code.load(Ordering::Relaxed);
        if cached != -1 {
            return Ok(cached);
        }
        self.compute_hash(py)
    }

    /// Return the runtime class name and set fields in the frozen display order.
    ///
    /// Zero relative fields and unset absolute fields are omitted; weekdays use MO
    /// through SU. __str__ resolves to the same representation.
    fn __repr__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyString>> {
        let fields = slf.get().snapshot();
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
        if slf.is_exact_instance_of::<Self>() {
            return exact_representation(py, &fields, &names);
        }
        // Subclasses retain observable class/name lookup and Unicode conversion.
        let class_name = slf
            .as_any()
            .getattr(pyo3::intern!(py, "__class__"))?
            .getattr(pyo3::intern!(py, "__name__"))?;
        let class = class_name.extract::<Cow<'_, str>>()?;
        let mut text = String::with_capacity(256);
        text.push_str("<'");
        text.push_str(&class);
        text.push_str("' (");
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
                text.push_str(name);
                text.push('=');
                append_integer(&mut text, value);
            }
        }
        text.push_str(")>");
        Ok(PyString::new(py, &text))
    }

    /// Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Increment or date operand; NumPy arrays are unsupported.
    ///
    /// Returns
    /// -------
    /// Delta | date | datetime | NotImplemented
    ///     A base Delta for increment operands,
    ///         the input date subtype for Python dates, or a naive builtin datetime for
    ///         NumPy datetime64. Unsupported operands return NotImplemented.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     Numeric conversion or calendar arithmetic overflows.
    /// ValueError
    ///     Invalid dates or a failing custom date constructor.
    /// Exception
    ///     Third-party conversion and other Python callback errors propagate.
    ///
    /// Notes
    /// -----
    /// Date operations apply absolute fields, relative increments, then weekday;
    /// datetime timezone and fold are preserved. Arrays are not supported.
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
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::relativedelta_fields(other)?,
                    false,
                    false,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, true)? {
            if datetime {
                return crate::numpy_scalar::apply_datetime_us(other.py(), self, value, 1);
            }
            return Bound::new(other.py(), self.with_microseconds(value, false, false)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Apply reflected addition using the same date and duration rules as __add__.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Left-hand date, duration or relativedelta operand.
    ///
    /// A direct reflected call with another Delta returns NotImplemented. Conversion,
    /// calendar and custom-constructor errors follow __add__.
    pub(crate) fn __radd__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(result) = crate::interop::apply_date(self, other, 1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, false, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::relativedelta_fields(other)?,
                    false,
                    true,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, true)? {
            if datetime {
                return crate::numpy_scalar::apply_datetime_us(other.py(), self, value, 1);
            }
            return Bound::new(other.py(), self.with_microseconds(value, false, false)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Left-hand date, duration or relativedelta operand.
    ///
    /// relativedelta is also supported; direct reflected Delta calls return
    /// NotImplemented. Return types and calendar errors follow reflected dispatch,
    /// with OverflowError for unrepresentable negation or subtraction.
    pub(crate) fn __rsub__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(result) = crate::interop::apply_date(self, other, -1)? {
            return Ok(result);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, true, true)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::relativedelta_fields(other)?,
                    true,
                    true,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, true)? {
            if datetime {
                return crate::numpy_scalar::apply_datetime_us(other.py(), self, value, -1);
            }
            return Bound::new(other.py(), self.with_microseconds(value, true, true)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.
    ///
    /// Parameters
    /// ----------
    /// other : object
    ///     Increment to subtract; dates are unsupported here.
    ///
    /// Returns
    /// -------
    /// Delta | NotImplemented
    ///     A base Delta or NotImplemented for unsupported types,
    ///         including dates and NumPy datetime64 in this direction.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     Numeric conversion, subtraction or normalization overflows.
    /// Exception
    ///     Third-party conversion and Python callback errors propagate.
    pub(crate) fn __sub__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if let Ok(rhs) = other.cast::<Self>() {
            return Bound::new(other.py(), self.combine(&rhs.borrow(), true)?).map(Bound::into_any);
        }
        if let Ok(rhs) = other.cast::<PyDelta>() {
            return Bound::new(other.py(), self.with_duration(rhs, true, false)?)
                .map(Bound::into_any);
        }
        if crate::interop::is_relativedelta(other)? {
            return Bound::new(
                other.py(),
                self.with_relative_fields(
                    crate::interop::relativedelta_fields(other)?,
                    true,
                    false,
                )?,
            )
            .map(Bound::into_any);
        }
        if let Some((value, datetime)) = crate::numpy_scalar::microseconds(other, false)? {
            if datetime {
                return Ok(other.py().NotImplemented().into_bound(other.py()));
            }
            return Bound::new(other.py(), self.with_microseconds(value, true, false)?)
                .map(Bound::into_any);
        }
        Ok(other.py().NotImplemented().into_bound(other.py()))
    }

    /// Negate relative components and retain absolute replacements in a new Delta.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     A relative component cannot be negated or normalized.
    pub(crate) fn __neg__(&self) -> PyResult<Self> {
        self.negate_groups(true, true, "integer overflow in Delta negation")
    }

    /// Return a new Delta with the frozen grouped-sign absolute-value behavior.
    ///
    /// Year/month and day/time groups use their leading normalized component's sign;
    /// absolute replacement fields are retained.
    ///
    /// Raises
    /// ------
    /// OverflowError
    ///     Required negation or normalization cannot be represented.
    pub(crate) fn __abs__(&self) -> PyResult<Self> {
        self.negate_groups(
            self.relative(0) < 0,
            self.days < 0,
            "integer overflow in Delta absolute value",
        )
    }

    /// int: Normalized relative years; months are carried into this value.
    #[getter]
    fn years(&self) -> i64 {
        self.relative(0)
    }
    /// int: Relative months after grouping years, in 0..11.
    #[getter]
    fn months(&self) -> i64 {
        self.relative(1)
    }
    /// int: Relative days, including normalized weeks and clock carries.
    #[getter]
    fn days(&self) -> i64 {
        self.relative(2)
    }
    /// int: Normalized relative hours, in 0..23.
    #[getter]
    fn hours(&self) -> i64 {
        self.relative(3)
    }
    /// int: Normalized relative minutes, in 0..59.
    #[getter]
    fn minutes(&self) -> i64 {
        self.relative(4)
    }
    /// int: Normalized relative seconds, in 0..59.
    #[getter]
    fn seconds(&self) -> i64 {
        self.relative(5)
    }
    /// int: Normalized relative microseconds, in 0..999999.
    #[getter]
    fn microseconds(&self) -> i64 {
        self.relative(6)
    }
    /// int | None: Absolute year replacement, or None when unset.
    #[getter]
    fn year(&self) -> Option<i64> {
        self.absolute(7)
    }
    /// int | None: Absolute month replacement (1..12), or None when unset.
    #[getter]
    fn month(&self) -> Option<i64> {
        self.absolute(8)
    }
    /// int | None: Absolute day replacement (1..31), or None when unset.
    #[getter]
    fn day(&self) -> Option<i64> {
        self.absolute(9)
    }
    /// int | None: Absolute weekday replacement (Monday=0 to Sunday=6), or None.
    #[getter]
    fn weekday(&self) -> Option<i64> {
        self.absolute(10)
    }
    /// int | None: Absolute hour replacement (0..23), or None when unset.
    #[getter]
    fn hour(&self) -> Option<i64> {
        self.absolute(11)
    }
    /// int | None: Absolute minute replacement (0..59), or None when unset.
    #[getter]
    fn minute(&self) -> Option<i64> {
        self.absolute(12)
    }
    /// int | None: Absolute second replacement (0..59), or None when unset.
    #[getter]
    fn second(&self) -> Option<i64> {
        self.absolute(13)
    }
    /// int | None: Absolute microsecond replacement (0..999999), or None.
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
        inputs[3] = i64::MAX;
        assert!(normalize(inputs).is_err());
        let mut inputs = defaults();
        inputs[0] = i64::MAX;
        inputs[2] = 12;
        assert!(normalize(inputs).is_err());
    }
}
