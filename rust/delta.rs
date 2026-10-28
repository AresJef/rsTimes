//! Delta storage, checked normalization and the Python-facing methods.
//!
//! Snapshot order is seven relative fields (years, months, days, hours, minutes,
//! seconds, microseconds) followed by eight absolute fields (year, month, day,
//! weekday, hour, minute, second, microsecond). Unset absolute fields use -1.
//! Packed values are fully initialized once and never rewritten. Hash and display
//! caches never change the value. The accepted runtime is the ordinary GIL interpreter.

use pyo3::exceptions::PyOverflowError;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{
    PyBool, PyDate, PyDateAccess, PyDateTime, PyDelta, PyDeltaAccess, PyDict, PyFloat, PyInt,
    PyList, PyString, PyTuple, PyType,
};
use std::borrow::Cow;
use std::cell::OnceCell;
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

/// Own one display string only on the registered ordinary-GIL base path.
/// Other runtimes never access this cell. PyO3 retains responsibility for the
/// owned string's destruction, including deferred decref outside an attachment.
struct RepresentationCache(OnceCell<Py<PyString>>);
// SAFETY: get/set are private unsafe entry points. Their callers prove the
// registered non-free-threaded GIL path before every access, retain the instance,
// and never keep a cell borrow across a Python call or a discarded value's Drop.
unsafe impl Sync for RepresentationCache {}

impl RepresentationCache {
    const fn new() -> Self {
        Self(OnceCell::new())
    }

    /// Clone a saved string without exposing a cell borrow.
    /// # Safety
    /// The caller holds the conventional GIL and a live registered base instance.
    #[inline(always)]
    unsafe fn get<'py>(&self, py: Python<'py>) -> Option<Bound<'py, PyString>> {
        self.0.get().map(|text| text.bind(py).clone())
    }

    /// Save the first completed display; drop a reentrant loser's value normally.
    /// # Safety
    /// The same GIL qualification must be checked after formatting callbacks.
    #[inline(always)]
    unsafe fn set(&self, _py: Python<'_>, text: Py<PyString>) {
        let _ = self.0.set(text);
    }
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
/// The native value is canonical. Only years (index 0) and days (index 2) may
/// exceed signed 32 bits; all remaining magnitudes are below the hash modulus.
fn integer_tuple_hash(value: &Delta) -> isize {
    const MODULUS: u64 = (1_u64 << 61) - 1;
    const PRIME1: u64 = 11_400_714_785_074_694_791;
    const PRIME2: u64 = 14_029_467_366_897_019_727;
    const PRIME5: u64 = 2_870_177_450_012_600_261;
    #[inline(always)]
    fn mix_lane<const WIDE: bool>(accumulator: u64, number: i64) -> u64 {
        let absolute = number.unsigned_abs();
        let magnitude = if WIDE { absolute % MODULUS } else { absolute } as i64;
        let signed = if number < 0 { -magnitude } else { magnitude };
        let lane = if signed == -1 { -2_i64 } else { signed } as u64;
        accumulator
            .wrapping_add(lane.wrapping_mul(PRIME2))
            .rotate_left(31)
            .wrapping_mul(PRIME1)
    }
    let mut accumulator = PRIME5;
    accumulator = mix_lane::<true>(accumulator, value.relative(0));
    accumulator = mix_lane::<false>(accumulator, value.relative(1));
    accumulator = mix_lane::<true>(accumulator, value.relative(2));
    accumulator = mix_lane::<false>(accumulator, value.relative(3));
    accumulator = mix_lane::<false>(accumulator, value.relative(4));
    accumulator = mix_lane::<false>(accumulator, value.relative(5));
    accumulator = mix_lane::<false>(accumulator, value.relative(6));
    accumulator = mix_lane::<false>(accumulator, value.relative(7));
    accumulator = mix_lane::<false>(accumulator, value.relative(8));
    accumulator = mix_lane::<false>(accumulator, value.relative(9));
    accumulator = mix_lane::<false>(accumulator, value.relative(10));
    accumulator = mix_lane::<false>(accumulator, value.relative(11));
    accumulator = mix_lane::<false>(accumulator, value.relative(12));
    accumulator = mix_lane::<false>(accumulator, value.relative(13));
    accumulator = mix_lane::<false>(accumulator, value.relative(14));
    accumulator = accumulator.wrapping_add(15 ^ (PRIME5 ^ 3_527_539));
    if accumulator == u64::MAX {
        1_546_275_796
    } else {
        accumulator as isize
    }
}

// Atomic fields avoid holding a mutable PyO3 borrow across Python callbacks.
// The accepted interpreter has the GIL; field commits contain no callbacks.
// Relative widths: months 4, hours 5, minutes 6, seconds 6, microseconds 20,
// flags 4, totaling 45 bits. Years and days retain their full signed 64-bit widths.
const MONTHS_BITS: u32 = 4;
const HOURS_BITS: u32 = 5;
const MINUTES_BITS: u32 = 6;
const SECONDS_BITS: u32 = 6;
const MICROSECONDS_BITS: u32 = 20;
const FLAGS_BITS: u32 = 4;
const MONTHS_SHIFT: u32 = 0;
const HOURS_SHIFT: u32 = 4;
const MINUTES_SHIFT: u32 = 9;
const SECONDS_SHIFT: u32 = 15;
const MICROSECONDS_SHIFT: u32 = 21;
const FLAGS_SHIFT: u32 = 41;

// Absolute year/month/day store their positive value, with 0 meaning unset.
// The remaining fields store value + 1: 0 means unset and explicit zero is 1.
// Encoded maxima 9999/12/31/7/24/60/60/1000000 fit 14/4/5/3/5/6/6/20 bits.
const ABSOLUTE_WIDTHS: [u32; 8] = [14, 4, 5, 3, 5, 6, 6, 20];
const ABSOLUTE_SHIFTS: [u32; 8] = [0, 14, 18, 23, 26, 31, 37, 43];

/// Three immutable words holding all native fields except the separate days.
///
/// The upper 19 relative bits and top absolute bit are always zero. Encoding
/// accepts only validated canonical fields; Python state keeps its 15-field form.
#[derive(Clone, Copy, PartialEq, Eq)]
struct PackedFields {
    years: u64,
    relative: u64,
    absolute: u64,
}

impl PackedFields {
    /// Encode already-validated fields directly, without temporary legacy words.
    ///
    /// Months and clock fields must be canonical; replacements must be unset or
    /// within their documented limits, with zero forbidden for year/month/day.
    /// Flags occupy four bits and have already been derived from the same value.
    #[inline(always)]
    fn from_normalized(fields: &[i64; 15], flags: i32) -> Self {
        let relative = (fields[1] as u64) << MONTHS_SHIFT
            | (fields[3] as u64) << HOURS_SHIFT
            | (fields[4] as u64) << MINUTES_SHIFT
            | (fields[5] as u64) << SECONDS_SHIFT
            | (fields[6] as u64) << MICROSECONDS_SHIFT
            | (flags as u64) << FLAGS_SHIFT;
        let mut absolute = 0;
        for index in 0..8 {
            let value = fields[index + 7];
            let encoded = if index < 3 {
                if value == -1 { 0 } else { value as u64 }
            } else {
                (value + 1) as u64
            };
            absolute |= encoded << ABSOLUTE_SHIFTS[index];
        }
        Self {
            years: fields[0] as u64,
            relative,
            absolute,
        }
    }

    /// Pack canonical relative result fields while retaining encoded replacements.
    /// Days remains separate; all bounded fields and four flags were validated.
    #[inline(always)]
    fn from_relative(fields: [i64; 7], absolute: u64, flags: u32) -> Self {
        Self {
            years: fields[0] as u64,
            relative: (fields[1] as u64) << MONTHS_SHIFT
                | (fields[3] as u64) << HOURS_SHIFT
                | (fields[4] as u64) << MINUTES_SHIFT
                | (fields[5] as u64) << SECONDS_SHIFT
                | (fields[6] as u64) << MICROSECONDS_SHIFT
                | u64::from(flags) << FLAGS_SHIFT,
            absolute,
        }
    }

    /// Read the four derived flags without expanding a legacy word.
    #[inline(always)]
    fn flags(&self) -> u32 {
        ((self.relative >> FLAGS_SHIFT) & ((1_u64 << FLAGS_BITS) - 1)) as u32
    }

    /// Merge encoded lanes using the original right-add/left-subtract priority.
    /// A zero lane is unset; explicit zero in clock/weekday lanes is code one.
    #[inline(always)]
    fn merged_absolute(&self, other: &Self, subtract: bool) -> u64 {
        let mut absolute = self.absolute;
        if absolute | other.absolute != 0 {
            for offset in 0..8 {
                let shift = ABSOLUTE_SHIFTS[offset];
                let mask = ((1_u64 << ABSOLUTE_WIDTHS[offset]) - 1) << shift;
                let own = absolute & mask;
                let incoming = other.absolute & mask;
                if (subtract && own == 0) || (!subtract && incoming != 0) {
                    absolute = (absolute & !mask) | incoming;
                }
            }
        }
        absolute
    }

    /// Codes greater than one represent positive absolute clock replacements.
    #[inline(always)]
    fn absolute_clock_positive(absolute: u64) -> bool {
        (4..8).any(|offset| {
            ((absolute >> ABSOLUTE_SHIFTS[offset]) & ((1_u64 << ABSOLUTE_WIDTHS[offset]) - 1)) > 1
        })
    }

    /// Read a canonical bounded relative component from its named packed lane.
    #[inline(always)]
    fn relative(&self, index: usize) -> i64 {
        let (shift, width) = match index {
            1 => (MONTHS_SHIFT, MONTHS_BITS),
            3 => (HOURS_SHIFT, HOURS_BITS),
            4 => (MINUTES_SHIFT, MINUTES_BITS),
            5 => (SECONDS_SHIFT, SECONDS_BITS),
            6 => (MICROSECONDS_SHIFT, MICROSECONDS_BITS),
            _ => unreachable!("bounded relative field index"),
        };
        ((self.relative >> shift) & ((1_u64 << width) - 1)) as i64
    }

    /// Decode an absolute field, retaining unset and explicit zero separately.
    #[inline(always)]
    fn absolute(&self, index: usize) -> i64 {
        let offset = index - 7;
        let encoded =
            (self.absolute >> ABSOLUTE_SHIFTS[offset]) & ((1_u64 << ABSOLUTE_WIDTHS[offset]) - 1);
        if offset < 3 {
            if encoded == 0 { -1 } else { encoded as i64 }
        } else {
            encoded as i64 - 1
        }
    }

    /// Recreate one legacy word for existing checked arithmetic and predicates.
    #[inline(always)]
    fn word(&self, index: usize) -> u64 {
        let signed_lane = |value: i64| u64::from(value as i32 as u32);
        match index {
            0 => self.years,
            1 => {
                ((self.relative >> FLAGS_SHIFT) & ((1_u64 << FLAGS_BITS) - 1))
                    | ((self.relative(3) as u64) << 32)
            }
            2 => self.relative(4) as u64 | ((self.relative(5) as u64) << 32),
            3 => self.relative(6) as u64 | (signed_lane(self.absolute(7)) << 32),
            4..=6 => {
                signed_lane(self.absolute(index * 2))
                    | (signed_lane(self.absolute(index * 2 + 1)) << 32)
            }
            7 => signed_lane(self.absolute(14)) | ((self.relative(1) as u64) << 32),
            _ => unreachable!("legacy word index"),
        }
    }
}

/// An immutable calendar increment with relative amounts and optional field settings.
///
/// Parameters
/// ----------
/// years : int or SupportsIndex, default 0
///     Signed calendar years to add. Negative values reverse that direction; zero
///     is a real zero increment.
/// quarters : int or SupportsIndex, default 0
///     Signed calendar quarters to add. Negative values reverse that direction;
///     zero is a real zero increment.
/// months : int or SupportsIndex, default 0
///     Signed calendar months to add. Negative values reverse that direction; zero
///     is a real zero increment.
/// weeks : int, float or numpy.float16/float32/float64, default 0
///     Signed weeks to add. Negative values reverse that direction; zero is a real
///     zero increment. Fixed-duration floats are combined and rounded once to
///     microseconds.
/// days : int, float or numpy.float16/float32/float64, default 0
///     Signed days to add. Negative values reverse that direction; zero is a real
///     zero increment. Fixed-duration floats are combined and rounded once to
///     microseconds.
/// hours : int, float or numpy.float16/float32/float64, default 0
///     Signed hours to add. Negative values reverse that direction; zero is a real
///     zero increment. Fixed-duration floats are combined and rounded once to
///     microseconds.
/// minutes : int, float or numpy.float16/float32/float64, default 0
///     Signed minutes to add. Negative values reverse that direction; zero is a
///     real zero increment. Fixed-duration floats are combined and rounded once to
///     microseconds.
/// seconds : int, float or numpy.float16/float32/float64, default 0
///     Signed seconds to add. Negative values reverse that direction; zero is a
///     real zero increment. Fixed-duration floats are combined and rounded once to
///     microseconds.
/// milliseconds : int, float or numpy.float16/float32/float64, default 0
///     Signed milliseconds to add. Negative values reverse that direction; zero is
///     a real zero increment. Fixed-duration floats are combined and rounded once
///     to microseconds.
/// microseconds : int, float or numpy.float16/float32/float64, default 0
///     Signed microseconds to add. Negative values reverse that direction; zero is
///     a real zero increment. Fixed-duration floats are combined and rounded once
///     to microseconds.
/// year : int | None, default None
///     Absolute year replacement. None leaves it unset; explicit integers must be
///     positive. Values above 9999 are limited to that maximum.
/// month : int | None, default None
///     Absolute month replacement. None leaves it unset; explicit integers must be
///     positive. Values above 12 are limited to that maximum.
/// day : int | None, default None
///     Absolute day replacement. None leaves it unset; explicit integers must be
///     positive. Values above 31 are limited to that maximum.
/// weekday : int | None, default None
///     Absolute weekday replacement in 0 (Monday) through 6 (Sunday). None leaves
///     it unset; zero is an actual setting. Floats and out-of-range numbers are
///     rejected.
/// hour : int | None, default None
///     Absolute hour replacement in 0 through 23. None leaves it unset; zero is an
///     actual setting. Floats and out-of-range numbers are rejected.
/// minute : int | None, default None
///     Absolute minute replacement in 0 through 59. None leaves it unset; zero is
///     an actual setting. Floats and out-of-range numbers are rejected.
/// second : int | None, default None
///     Absolute second replacement in 0 through 59. None leaves it unset; zero is
///     an actual setting. Floats and out-of-range numbers are rejected.
/// millisecond : int | None, default None
///     Absolute millisecond replacement in 0 through 999. None leaves it unset;
///     zero is an actual setting. Floats and out-of-range numbers are rejected.
/// microsecond : int | None, default None
///     Absolute microsecond replacement in 0 through 999999. None leaves it unset;
///     zero is an actual setting. Floats and out-of-range numbers are rejected. If
///     millisecond is also set, only the final three microsecond digits are used.
///
/// Returns
/// -------
/// Delta
///     A completed instance of this class.
///
/// Notes
/// -----
/// Relative amounts add or subtract time; singular fields replace date or clock fields. None leaves an absolute field unset, while an explicit clock zero sets that field to zero. Positive year/month/day selections keep their upper limiting and month-end behavior. Other absolute fields require their stated ranges. Integer-like values such as NumPy integers are accepted for absolute fields; floats are rejected.
///
/// Fixed-duration fractions are combined and rounded once to microseconds, with halfway cases rounded to an even microsecond. Relative years, quarters and months require the integer index protocol; floats are rejected. Public numeric fields reject boolean values. Fixed-duration inputs accept the listed real floating types and integer index values, not arbitrary numeric conversions. Calendar month moves need not be reversible: January 31 plus one month and then minus one month may finish on January 29.
///
/// Values compare and hash by their fields with other Delta values. Fields cannot be changed in place; calling __init__ again leaves the existing value unchanged.
///
/// Examples
/// --------
/// >>> Delta(hour=None).hour is None
/// True
/// >>> Delta(hour=0).hour
/// 0
/// >>> from datetime import date
/// >>> date(2024, 1, 31) + Delta(months=1)
/// datetime.date(2024, 2, 29)
#[pyclass(frozen, subclass, immutable_type, module = "rstimes.delta")]
pub struct Delta {
    // Years, bounded relative fields/flags, and replacements occupy three words.
    // Days retain their separate 64-bit width. Packed fields are immutable.
    fields: PackedFields,
    days: i64,
    hash_code: AtomicIsize,
    representation: RepresentationCache,
}

impl Delta {
    /// Build a fixed span from canonical core fields, without public argument work.
    /// The public caller adds its entry only if validation or allocation fails.
    ///
    /// # Errors
    /// Rejects calendar replacements or days outside timedelta's range, and
    /// propagates an allocation failure from the Python result constructor.
    #[inline]
    pub(crate) fn fixed_timedelta<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDelta>> {
        // A zero absolute word means all replacements are unset. Explicit zero
        // clock settings have nonzero encodings and are still rejected here.
        // Read only required lanes;
        // a fixed span does not need a decoded fifteen-field public snapshot.
        if self.fields.years != 0 || self.fields.relative(1) != 0 || self.fields.absolute != 0 {
            return Err(crate::error_context::value_error(
                "start is required for years, months or absolute fields",
            ));
        }
        if !(-999_999_999..=999_999_999).contains(&self.days) {
            return Err(crate::error_context::overflow(
                "duration is outside timedelta's supported range",
            ));
        }
        // Canonical clock fields and the checked day range fit these C arguments.
        PyDelta::new(
            py,
            self.days as i32,
            (self.fields.relative(3) * 3600
                + self.fields.relative(4) * 60
                + self.fields.relative(5)) as i32,
            self.fields.relative(6) as i32,
            false,
        )
    }

    /// Parse and normalize all public arguments before an object is allocated.
    ///
    /// # Errors
    /// Propagates shape, conversion and checked normalization errors. A failed
    /// callback cannot expose a partially initialized native value.
    #[inline]
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
        Self::construct_nonempty(args, kwargs).map_err(|error| {
            if args.is_empty() {
                if let Some(kwargs) = kwargs.filter(|values| values.len() == 1) {
                    if let Some((name, value)) = kwargs.iter().next() {
                        if let Ok(name) = name.extract::<String>() {
                            return crate::error_context::argument(
                                args.py(),
                                error,
                                "Delta",
                                &name,
                                &value,
                            );
                        }
                    }
                }
            }
            crate::error_context::argument(args.py(), error, "Delta", "arguments", args.as_any())
        })
    }

    /// Keep the nonempty parser frame out of the empty constructor wrapper.
    #[inline(never)]
    fn construct_nonempty(
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        if args.len() == 1 && kwargs.is_none_or(|values| values.is_empty()) {
            if let Some(value) = crate::state::construction_value(args)? {
                return Ok(value);
            }
        }
        if args.is_empty()
            && let Some(kwargs) = kwargs.filter(|values| values.len() == 1)
            && let Some((key, value)) = kwargs.iter().next()
            && let Some(index) = parameter_index(key.cast::<PyString>()?.to_str()?)
        {
            // Exact int is already known not to be either boolean family.
            // Preserve checked extraction without two repeated subtype tests.
            if unsafe { pyo3::ffi::PyLong_CheckExact(value.as_ptr()) != 0 } {
                return single_numeric(index, validated_integer(&value, index)?, 0);
            }
            if value.is_instance_of::<PyInt>() {
                return single_numeric(index, constructor_integer(&value, index)?, 0);
            }
            if (3..10).contains(&index) && value.is_instance_of::<PyFloat>() {
                let (amount, scaled) = fixed_float_parts(&value, index)?;
                let whole = scaled.trunc();
                let parity = if index == 9 { amount } else { 0 };
                return single_numeric(
                    index,
                    amount,
                    FixedFractions::finish(parity, whole as i64, scaled - whole),
                );
            }
        }
        // Normalize primitive small-keyword values before returning their
        // snapshot, so fractional scratch storage never crosses parser frames.
        if args.is_empty()
            && let Some(kwargs) = kwargs.filter(|values| (2..=4).contains(&values.len()))
        {
            let result = match kwargs.len() {
                2 => parse_small_keywords::<2>(kwargs),
                3 => parse_small_keywords::<3>(kwargs),
                _ => parse_small_keywords::<4>(kwargs),
            };
            if let Some(result) = result {
                return Ok(Self::from_normalized(result?, -1));
            }
        }
        let fields = parse_inputs(args, kwargs)?
            .normalized()
            .map_err(crate::error_context::overflow)?;
        Ok(Self::from_normalized(fields, -1))
    }
    /// Construct from a fully checked source snapshot without normalizing twice.
    #[inline]
    pub(crate) fn from_fields(fields: RelativeFields) -> PyResult<Self> {
        Ok(Self::from_normalized(fields.0, -1))
    }

    /// Normalize relative arithmetic performed on validated native Delta fields.
    ///
    /// # Preconditions
    /// Clock and month inputs are sums, differences or negations of canonical
    /// native components, including decomposed normalized timedelta components.
    /// Absolute inputs are validated native fields or raw zeroes.
    /// Foreign source fields arrive as an already checked RelativeFields snapshot.
    ///
    /// # Errors
    /// Preserves checked day carries and signed64 year arithmetic.
    #[inline(always)]
    fn from_native_fields(fields: [i64; 15]) -> PyResult<Self> {
        let normalized = normalize_native_fields(fields).map_err(crate::error_context::overflow)?;
        Ok(Self::from_normalized(normalized, -1))
    }

    /// Negate selected canonical groups while retaining absolute fields and flags.
    ///
    /// Negation preserves whether either relative group or its lower clock part
    /// is zero. Therefore the validated truth/time flags remain exact, and no
    /// absolute field needs to be decoded or revalidated.
    ///
    /// # Errors
    /// Rejects negated values only when their normalized final fields cannot fit.
    #[inline(always)]
    fn negate_groups(
        &self,
        year_month: bool,
        day_time: bool,
        error: &'static str,
    ) -> PyResult<Self> {
        self.negate_groups_narrow(year_month, day_time, error)
            .or_else(|_| {
                let own = self.snapshot();
                let relative = std::array::from_fn(|index| {
                    let value = i128::from(own[index]);
                    if (index < 2 && year_month) || (index >= 2 && day_time) {
                        -value
                    } else {
                        value
                    }
                });
                let mut fields = normalize_relative_wide(relative)
                    .map_err(|_| crate::error_context::overflow(error))?;
                fields[7..].copy_from_slice(&own[7..]);
                Ok(Self::from_normalized(fields, -1))
            })
    }

    /// Keep the common canonical negation path free of wide integer division.
    #[inline(always)]
    fn negate_groups_narrow(
        &self,
        year_month: bool,
        day_time: bool,
        error: &'static str,
    ) -> PyResult<Self> {
        let mut days = self.days;
        let mut packed = self.fields;
        if day_time {
            let hours = self.relative(3);
            let minutes = self.relative(4);
            let seconds = self.relative(5);
            let us = self.relative(6);
            if hours | minutes | seconds | us != 0 {
                // A nonzero canonical clock borrows exactly one day. Combined
                // negation is -days-1, which is bitwise complement even at MIN.
                // Bounded components need neither division nor overflow checks.
                days = !self.days;
                let new_us = if us == 0 { 0 } else { 1_000_000 - us };
                let seconds = seconds + i64::from(us != 0);
                let new_seconds = if seconds == 0 { 0 } else { 60 - seconds };
                let minutes = minutes + i64::from(seconds != 0);
                let new_minutes = if minutes == 0 { 0 } else { 60 - minutes };
                let new_hours = 24 - hours - i64::from(minutes != 0);
                let clock_mask = ((1_u64 << FLAGS_SHIFT) - 1) & !((1_u64 << HOURS_SHIFT) - 1);
                packed.relative = (packed.relative & !clock_mask)
                    | (new_hours as u64) << HOURS_SHIFT
                    | (new_minutes as u64) << MINUTES_SHIFT
                    | (new_seconds as u64) << SECONDS_SHIFT
                    | (new_us as u64) << MICROSECONDS_SHIFT;
            } else {
                days = self
                    .days
                    .checked_neg()
                    .ok_or_else(|| crate::error_context::overflow(error))?;
            }
        }
        if year_month {
            let months = self.relative(1);
            let years = self.relative(0);
            let (months, years) = if months == 0 {
                (
                    0,
                    years
                        .checked_neg()
                        .ok_or_else(|| crate::error_context::overflow(error))?,
                )
            } else {
                (12 - months, !years)
            };
            packed.years = years as u64;
            let month_mask = (1_u64 << MONTHS_BITS) - 1;
            packed.relative = (packed.relative & !month_mask) | (months as u64) << MONTHS_SHIFT;
        }
        Ok(Self {
            fields: packed,
            days,
            hash_code: AtomicIsize::new(-1),
            representation: RepresentationCache::new(),
        })
    }

    /// Add or subtract relative fields and apply the frozen absolute-field priority.
    ///
    /// # Errors
    /// Rejects checked relative arithmetic or normalization overflow.
    #[inline(always)]
    pub(crate) fn combine(&self, other: &Self, subtract: bool) -> PyResult<Self> {
        self.combine_native_narrow(other, subtract)
            .or_else(|error| self.combine_after_overflow(other, subtract, error))
    }

    /// Decode wide snapshots only after checked compact arithmetic overflows.
    ///
    /// # Errors
    /// Retains the arithmetic error if the normalized wide result cannot fit.
    #[cold]
    #[inline(never)]
    fn combine_after_overflow(
        &self,
        other: &Self,
        subtract: bool,
        error: &'static str,
    ) -> PyResult<Self> {
        Self::combine_wide(self.snapshot(), other.snapshot(), subtract, error)
    }

    /// Combine canonical relative amounts and merge only set replacement halves.
    ///
    /// # Preconditions
    /// Both operands have validated immutable fields; replacement values are already clamped.
    /// # Errors
    /// Returns the existing arithmetic or carry error for the wide fallback.
    #[inline(always)]
    fn combine_native_narrow(&self, other: &Self, subtract: bool) -> Result<Self, &'static str> {
        let mut relative = [0_i64; 7];
        for index in [0, 2] {
            relative[index] = if subtract {
                self.relative(index).checked_sub(other.relative(index))
            } else {
                self.relative(index).checked_add(other.relative(index))
            }
            .ok_or("integer overflow in Delta arithmetic")?;
        }
        // Canonical months and clock components are bounded, so their signed
        // combinations fit i64 and require at most one carry or borrow.
        for index in [1, 3, 4, 5, 6] {
            relative[index] = self.relative(index)
                + if subtract {
                    -other.relative(index)
                } else {
                    other.relative(index)
                };
        }
        let (us, seconds) = carry_once(relative[6], relative[5], 1_000_000)?;
        let (seconds, minutes) = carry_once(seconds, relative[4], 60)?;
        let (minutes, hours) = carry_once(minutes, relative[3], 60)?;
        let (hours, days) = carry_once(hours, relative[2], 24)?;
        let (months, years) = carry_once(relative[1], relative[0], 12)?;
        let absolute_bits = self.fields.merged_absolute(&other.fields, subtract);
        let absolute = absolute_bits != 0;
        let absolute_clock = PackedFields::absolute_clock_positive(absolute_bits);
        let clock = hours | minutes | seconds | us;
        let truth = absolute || years | months | days | clock != 0;
        let flags = u32::from(truth)
            | (u32::from(clock != 0 || absolute_clock) << 1)
            | (u32::from(absolute) << 2)
            | (u32::from(absolute_clock) << 3);
        Ok(Self {
            fields: PackedFields::from_relative(
                [years, months, days, hours, minutes, seconds, us],
                absolute_bits,
                flags,
            ),
            days,
            hash_code: AtomicIsize::new(-1),
            representation: RepresentationCache::new(),
        })
    }

    /// Combine canonical snapshots without constructing a temporary atomic payload.
    ///
    /// # Errors
    /// Retains relative checked arithmetic and native normalization overflow.
    #[inline(always)]
    fn combine_snapshots(mut fields: [i64; 15], rhs: [i64; 15], subtract: bool) -> PyResult<Self> {
        let mut wide = [0_i64; 2];
        for (slot, index) in [0, 2].into_iter().enumerate() {
            let result = if subtract {
                fields[index].checked_sub(rhs[index])
            } else {
                fields[index].checked_add(rhs[index])
            };
            let Some(result) = result else {
                return Self::combine_wide(
                    fields,
                    rhs,
                    subtract,
                    "integer overflow in Delta arithmetic",
                );
            };
            wide[slot] = result;
        }
        fields[0] = wide[0];
        fields[2] = wide[1];
        for index in [1, 3, 4, 5, 6] {
            fields[index] += if subtract { -rhs[index] } else { rhs[index] };
        }
        for index in 7..15 {
            if (subtract && fields[index] == -1) || (!subtract && rhs[index] != -1) {
                fields[index] = rhs[index];
            }
        }
        Self::from_native_fields(fields)
    }

    /// Recover only a narrow intermediate overflow, checking the normalized final value.
    #[cold]
    fn combine_wide(
        left: [i64; 15],
        right: [i64; 15],
        subtract: bool,
        error: &'static str,
    ) -> PyResult<Self> {
        let relative = std::array::from_fn(|index| {
            i128::from(left[index])
                + if subtract {
                    -i128::from(right[index])
                } else {
                    i128::from(right[index])
                }
        });
        // Keep the checked native failure until the caller's one final error.
        let mut fields =
            normalize_relative_wide(relative).map_err(|_| crate::error_context::overflow(error))?;
        for index in 7..15 {
            fields[index] = if (subtract && left[index] == -1) || (!subtract && right[index] != -1)
            {
                right[index]
            } else {
                left[index]
            };
        }
        Ok(Self::from_normalized(fields, -1))
    }

    /// Normalize foreign fields before reading this Delta, then combine in operand order.
    ///
    /// Python callbacks and source normalization have completed before the self snapshot.
    /// # Errors
    /// Propagates full normalization and arithmetic overflow exactly as from_fields/combine.
    pub(crate) fn with_relative_fields(
        &self,
        foreign: RelativeFields,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        let foreign = foreign.0;
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
        // pandas uses an all-zero timedelta carrier only when a coarse-unit
        // value exceeds builtin bounds. Nonzero native fields are already real
        // (timedeltas.pyx:_timedelta_from_value_and_reso, pandas 2/3).
        if other.get_days() == 0
            && other.get_seconds() == 0
            && other.get_microseconds() == 0
            && !other.is_exact_instance_of::<PyDelta>()
        {
            return self.with_foreign_zero_duration(other, subtract, reverse);
        }
        self.with_duration_parts(
            i64::from(other.get_days()),
            i64::from(other.get_seconds()),
            i64::from(other.get_microseconds()),
            subtract,
            reverse,
        )
    }

    /// Read a genuine timedelta subtype whose base carrier may hide wide ticks.
    ///
    /// # Preconditions
    /// The caller has proved a non-exact timedelta with zero native carrier fields.
    /// # Errors
    /// Preserves real foreign conversion failures and checked final normalization.
    #[inline(never)]
    fn with_foreign_zero_duration(
        &self,
        other: &Bound<'_, PyDelta>,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        if let Some(nanos) = crate::interop::duration_nanoseconds(other.as_any())? {
            let micros = nanos.div_euclid(1000);
            let days = i64::try_from(micros.div_euclid(86_400_000_000)).map_err(|_| {
                crate::error_context::overflow("Delta duration days exceed the supported range")
            })?;
            let clock = micros.rem_euclid(86_400_000_000);
            return self.with_duration_parts(
                days,
                (clock / 1_000_000) as i64,
                (clock % 1_000_000) as i64,
                subtract,
                reverse,
            );
        }
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
    /// seconds is 0..86400 and microseconds is 0..1000000; days fits signed64.
    /// # Errors
    /// Checks the normalized final fields, recovering wide intermediate arithmetic.
    #[inline(always)]
    pub(crate) fn with_duration_parts(
        &self,
        days: i64,
        seconds: i64,
        microseconds: i64,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        match self.with_duration_parts_narrow(days, seconds, microseconds, subtract, reverse) {
            Ok(value) => Ok(value),
            Err(original) => self
                .with_duration_parts_wide(days, seconds, microseconds, subtract, reverse)
                .map_err(|_| original),
        }
    }

    /// Keep ordinary duration combinations on the compact, single-carry path.
    #[inline(always)]
    fn with_duration_parts_narrow(
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
                    crate::error_context::overflow("integer overflow in Delta negation")
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
        // Check the cheap day addition first. The caller recovers an intermediate
        // overflow when the final clock carry brings it back into range.
        fields[2] = if subtract && !reverse {
            fields[2].checked_sub(days)
        } else {
            fields[2].checked_add(days)
        }
        .ok_or_else(|| crate::error_context::overflow("integer overflow in Delta arithmetic"))?;
        // Canonical clock components and decomposed native duration components
        // are each bounded by one unit. Their sums/differences fit i64; only the
        // unbounded day/year values and final carries require overflow checks.
        for (index, value) in [
            (3, seconds / 3_600),
            (4, seconds / 60 % 60),
            (5, seconds % 60),
            (6, microseconds),
        ] {
            fields[index] += if subtract && !reverse { -value } else { value };
        }
        let (us, seconds) =
            carry_once(fields[6], fields[5], 1_000_000).map_err(crate::error_context::overflow)?;
        let (seconds, minutes) =
            carry_once(seconds, fields[4], 60).map_err(crate::error_context::overflow)?;
        let (minutes, hours) =
            carry_once(minutes, fields[3], 60).map_err(crate::error_context::overflow)?;
        let (hours, days) =
            carry_once(hours, fields[2], 24).map_err(crate::error_context::overflow)?;
        let (months, years) =
            carry_once(fields[1], fields[0], 12).map_err(crate::error_context::overflow)?;
        let retained = self.fields.flags() & 12;
        let clock = hours | minutes | seconds | us;
        let truth = retained & 4 != 0 || years | months | days | clock != 0;
        let flags = retained | u32::from(truth) | (u32::from(retained & 8 != 0 || clock != 0) << 1);
        Ok(Self {
            fields: PackedFields::from_relative(
                [years, months, days, hours, minutes, seconds, us],
                self.fields.absolute,
                flags,
            ),
            days,
            hash_code: AtomicIsize::new(-1),
            representation: RepresentationCache::new(),
        })
    }

    /// Recover exceptional intermediate overflow without changing absolute fields.
    #[cold]
    fn with_duration_parts_wide(
        &self,
        days: i64,
        seconds: i64,
        microseconds: i64,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
        let mut relative: [i128; 7] = std::array::from_fn(|index| {
            let value = i128::from(self.relative(index));
            if reverse { -value } else { value }
        });
        for (index, value) in [
            (2, days),
            (3, seconds / 3_600),
            (4, seconds / 60 % 60),
            (5, seconds % 60),
            (6, microseconds),
        ] {
            relative[index] += if subtract && !reverse {
                -i128::from(value)
            } else {
                i128::from(value)
            };
        }
        let mut fields =
            normalize_relative_wide(relative).map_err(crate::error_context::overflow)?;
        fields[7..].copy_from_slice(&self.snapshot()[7..]);
        Ok(Self::from_normalized(fields, -1))
    }

    /// Combine checked NumPy microseconds using the same normalized duration parts.
    ///
    /// An i64 microsecond count spans at most 106751992 days, within Python's
    /// timedelta day range. Floor division preserves negative subsecond values.
    /// # Errors
    /// Retains with_duration_parts' checked arithmetic and normalization errors.
    pub(crate) fn with_microseconds(
        &self,
        value: i64,
        subtract: bool,
        reverse: bool,
    ) -> PyResult<Self> {
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
            representation: RepresentationCache::new(),
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
            fields: PackedFields::from_normalized(&fields, truth),
            days: fields[2],
            hash_code: AtomicIsize::new(cache),
            representation: RepresentationCache::new(),
        }
    }

    /// Return the 15 signed fields in relative-then-absolute public field order.
    ///
    /// Reads occur while the accepted GIL interpreter is attached; no callback runs
    /// between field loads.
    #[inline(always)]
    pub(crate) fn snapshot(&self) -> [i64; 15] {
        let mut fields = [0; 15];
        fields[0] = self.fields.word(0) as i64;
        for pair in 1..8 {
            let bits = self.fields.word(pair);
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
        if datetime || self.fields.word(1) & 2 != 0 {
            return self.snapshot();
        }
        let relative = self.fields.word(0);
        let year = self.fields.word(3);
        let month_day = self.fields.word(4);
        let weekday = self.fields.word(5);
        [
            relative as i64,
            i64::from((self.fields.word(7) >> 32) as u32 as i32),
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
        self.days == other.days && self.fields == other.fields
    }

    /// Recognize clock replacements that leave a checked datetime unchanged.
    ///
    /// Relative and calendar replacements must be absent. Clock access uses the
    /// same native datetime fields as the calendar kernel and invokes no callbacks.
    #[inline(always)]
    pub(crate) fn preserves_datetime_clock(&self, dt: &Bound<'_, pyo3::types::PyDateTime>) -> bool {
        use pyo3::types::PyTimeAccess;
        if self.fields.word(1) & 4 == 0 {
            return false;
        }
        // A different explicit clock value cheaply rejects this shortcut;
        // the complete calendar path still handles any cancelling increment.
        let same = |field: i32, actual: i32| field == -1 || field == actual;
        same(
            (self.fields.word(5) >> 32) as u32 as i32,
            i32::from(dt.get_hour()),
        ) && same(
            self.fields.word(6) as u32 as i32,
            i32::from(dt.get_minute()),
        ) && same(
            (self.fields.word(6) >> 32) as u32 as i32,
            i32::from(dt.get_second()),
        ) && same(
            self.fields.word(7) as u32 as i32,
            dt.get_microsecond() as i32,
        ) && self.fields.word(0) == 0
            && self.days == 0
            && self.fields.word(7) >> 32 == 0
            && self.fields.word(1) >> 32 == 0
            && self.fields.word(2) == 0
            && self.fields.word(3) as u32 == 0
            && self.fields.word(3) >> 32 == u64::from(u32::MAX)
            && self.fields.word(4) == u64::MAX
            && self.fields.word(5) as u32 == u32::MAX
    }

    /// Clone the saved display without entering the formatting frame.
    /// # Safety
    /// The caller has just proved this is the live registered conventional-GIL
    /// base instance. No borrowed cache reference escapes the returned string.
    #[inline(always)]
    pub(crate) unsafe fn cached_representation<'py>(
        &self,
        py: Python<'py>,
    ) -> Option<Bound<'py, PyString>> {
        unsafe { self.representation.get(py) }
    }

    /// Return the Python tuple hash cache, where -1 means not yet calculated.
    #[inline(always)]
    pub(crate) fn cached_hash(&self) -> isize {
        self.hash_code.load(Ordering::Relaxed)
    }

    /// Calculate and cache the native hash on the verified interpreter.
    ///
    /// The caller already observed an empty hash cache. Immutable field reads,
    /// bounded snapshot indexing and wrapping integer arithmetic cannot fail or
    /// invoke Python; other interpreters request the checked tuple fallback.
    #[inline(never)]
    pub(crate) fn native_hash(&self) -> Option<isize> {
        if !NATIVE_TUPLE_HASH.load(Ordering::Relaxed) {
            return None;
        }
        let value = integer_tuple_hash(self);
        self.hash_code.store(value, Ordering::Relaxed);
        Some(value)
    }

    /// Calculate and cache the Python hash of the 15-field snapshot tuple.
    ///
    /// # Errors
    /// Propagates tuple allocation/hash errors on the interpreter fallback.
    #[cold]
    #[inline(never)]
    fn compute_hash(&self, py: Python<'_>) -> PyResult<isize> {
        if let Some(value) = self.native_hash() {
            return Ok(value);
        }
        let value = PyTuple::new(py, self.snapshot())?.hash()?;
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
    /// Read one canonical field in snapshot order; years and days retain 64-bit widths.
    #[inline(always)]
    pub(crate) fn relative(&self, index: usize) -> i64 {
        match index {
            0 => self.fields.years as i64,
            2 => self.days,
            1 | 3..=6 => self.fields.relative(index),
            7..=14 => self.fields.absolute(index),
            _ => unreachable!("native field index"),
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
    absolute_mask: u64,
    packed: PackedFields,
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
        let mut absolute_mask = u64::MAX;
        for offset in 0..8 {
            if fields[offset + 7] != -1 {
                absolute_mask &=
                    !(((1_u64 << ABSOLUTE_WIDTHS[offset]) - 1) << ABSOLUTE_SHIFTS[offset]);
            }
        }
        Self {
            relative: std::array::from_fn(|index| fields[index]),
            absolute_mask,
            packed: value.fields,
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
    /// Left relative fields and encoded replacements came from validated native values.
    /// # Errors
    /// Checks normalized final years and days, including exceptional intermediate carries.
    #[inline(always)]
    fn finish(
        &self,
        left: [i64; 7],
        absolute_bits: u64,
        left_absolute: bool,
        left_absolute_clock: bool,
    ) -> PyResult<Delta> {
        self.finish_narrow(left, absolute_bits, left_absolute, left_absolute_clock)
    }

    /// Keep prepared additions on their original bounded carry path when possible.
    #[inline(always)]
    fn finish_narrow(
        &self,
        left: [i64; 7],
        absolute_bits: u64,
        left_absolute: bool,
        left_absolute_clock: bool,
    ) -> PyResult<Delta> {
        let mut months = left[1] + self.relative[1];
        let month_carry = i64::from(months >= 12);
        months -= month_carry * 12;
        let years = normalized_sum(left[0], self.relative[0], month_carry)?;
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
        let day_carry = i64::from(hours >= 24);
        hours -= day_carry * 24;
        let days = normalized_sum(left[2], self.relative[2], day_carry)?;
        let absolute = left_absolute || self.absolute_set;
        let absolute_clock = if self.absolute_clock_positive {
            true
        } else if !self.absolute_clock_set {
            left_absolute_clock
        } else {
            // Explicit zero can remove a previous positive replacement. Inspect
            // the merged encoded clock rather than inheriting a stale carry flag.
            PackedFields::absolute_clock_positive(absolute_bits)
        };
        let time = hours | minutes | seconds | microseconds;
        let truth = absolute || years | months | days | time != 0;
        let flags = i32::from(truth)
            | (i32::from(absolute_clock || time != 0) << 1)
            | (i32::from(absolute) << 2)
            | (i32::from(absolute_clock) << 3);
        // Values were checked or bounded by canonical single-carry arithmetic.
        // Absolute bits were merged only from validated native replacements.
        Ok(Delta {
            fields: PackedFields::from_relative(
                [years, months, days, hours, minutes, seconds, microseconds],
                absolute_bits,
                flags as u32,
            ),
            days,
            hash_code: AtomicIsize::new(-1),
            representation: RepresentationCache::new(),
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
        let mut packed = value.fields;
        let flags = packed.flags();
        if REPLACE {
            packed.absolute = (packed.absolute & self.absolute_mask) | self.packed.absolute;
        }
        if self.day_hour_only {
            // Preserve untouched packed lanes, changing only hours and flags.
            let mut hours = value.relative(3) + self.relative[3];
            let carry = i64::from(hours >= 24);
            hours -= carry * 24;
            let days = normalized_sum(value.days, self.relative[2], carry)?;
            let absolute = flags & 4 != 0 || REPLACE;
            let absolute_clock = if !REPLACE {
                flags & 8 != 0
            } else if self.absolute_clock_positive {
                true
            } else if !self.absolute_clock_set {
                flags & 8 != 0
            } else {
                PackedFields::absolute_clock_positive(packed.absolute)
            };
            let hours_mask = ((1_u64 << HOURS_BITS) - 1) << HOURS_SHIFT;
            packed.relative = (packed.relative & !hours_mask) | (hours as u64) << HOURS_SHIFT;
            let relative_mask = (1_u64 << FLAGS_SHIFT) - 1;
            let clock_mask = relative_mask & !((1_u64 << HOURS_SHIFT) - 1);
            let time = packed.relative & clock_mask;
            let truth =
                absolute || packed.years | days as u64 | (packed.relative & relative_mask) != 0;
            let flags = u32::from(truth)
                | (u32::from(absolute_clock || time != 0) << 1)
                | (u32::from(absolute) << 2)
                | (u32::from(absolute_clock) << 3);
            let flag_mask = ((1_u64 << FLAGS_BITS) - 1) << FLAGS_SHIFT;
            packed.relative = (packed.relative & !flag_mask) | u64::from(flags) << FLAGS_SHIFT;
            return Ok(Delta {
                fields: packed,
                days,
                hash_code: AtomicIsize::new(-1),
                representation: RepresentationCache::new(),
            });
        }
        let left = std::array::from_fn(|index| value.relative(index));
        self.finish(left, packed.absolute, flags & 4 != 0, flags & 8 != 0)
    }

    /// Add checked source fields through the prepared integer kernel.
    /// # Errors
    /// Preserves foreign normalization and scalar arithmetic overflow ordering.
    #[inline(always)]
    pub(crate) fn add_fields(&self, fields: RelativeFields) -> PyResult<Delta> {
        let fields = fields.0;
        let packed = PackedFields::from_normalized(&fields, storage_flags(&fields));
        let absolute_bits = (packed.absolute & self.absolute_mask) | self.packed.absolute;
        self.finish(
            std::array::from_fn(|index| fields[index]),
            absolute_bits,
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
            self.packed.absolute,
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
        self.finish(left, self.packed.absolute, false, false)
    }
}

/// Add two canonical wide units and their bounded carry without retaining snapshots.
#[inline(always)]
fn normalized_sum(left: i64, right: i64, carry: i64) -> PyResult<i64> {
    if let Some(value) = left.checked_add(right) {
        return value
            .checked_add(carry)
            .ok_or_else(|| crate::error_context::overflow(OVERFLOW));
    }
    normalized_sum_wide(left, right, carry)
}

/// Recover only the three primitive operands needed for an exceptional carry.
#[cold]
fn normalized_sum_wide(left: i64, right: i64, carry: i64) -> PyResult<i64> {
    i64::try_from(i128::from(left) + i128::from(right) + i128::from(carry))
        .map_err(|_| crate::error_context::overflow("integer overflow in Delta arithmetic"))
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

/// Read an integer without accepting truncating float or text conversions.
///
/// Native integers keep the direct extraction path. Other values may implement
/// Python's integer index protocol; its callback completes before native work.
#[inline]
pub(crate) fn index_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    if value.is_instance_of::<PyInt>() {
        return converted_integer(value);
    }
    // No callback exists in this case; this is our unsupported-input error.
    if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) == 0 } {
        return Err(crate::error_context::type_error("an integer is required"));
    }
    index_protocol_integer(value)
}

/// Run an already-proven index protocol once and preserve its original failure.
#[inline]
fn index_protocol_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    // SAFETY: the live input is borrowed under the GIL. PyNumber_Index returns
    // a new owned integer or an exception; Bound takes that ownership exactly once.
    let integer = unsafe {
        Bound::from_owned_ptr_or_err(value.py(), pyo3::ffi::PyNumber_Index(value.as_ptr()))
    }
    .map_err(crate::error_context::external)?;
    converted_integer(&integer)
}

/// Validate one explicit absolute field, retaining the compact unset encoding.
#[inline]
fn constructor_integer(value: &Bound<'_, PyAny>, index: usize) -> PyResult<i64> {
    // All callers prequalified PyInt; only its real bool subtype is excluded.
    if value.is_instance_of::<PyBool>() {
        return Err(public_boolean_error(value, index));
    }
    validated_integer(value, index)
}

/// Convert a primitive already proved not to be bool, retaining field bounds.
#[inline]
fn validated_integer(value: &Bound<'_, PyAny>, index: usize) -> PyResult<i64> {
    let number = converted_integer(value)?;
    if index < 10 {
        return Ok(number);
    }
    validate_absolute_input(number, index)
}

/// Keep public numeric rejection separate from dateutil's meaningful bool fields.
#[cold]
fn public_boolean_error(value: &Bound<'_, PyAny>, index: usize) -> PyErr {
    let name = keyword_names(value.py())[index].bind(value.py());
    crate::error_context::argument(
        value.py(),
        crate::error_context::type_error("boolean values are not accepted as numeric fields"),
        "Delta",
        name.to_str().unwrap_or("arguments"),
        value,
    )
}

/// Public absolute fields distinguish None from every explicit numeric value.
#[inline]
fn validate_absolute_input(number: i64, index: usize) -> PyResult<i64> {
    let valid = if index < 13 {
        number > 0
    } else {
        let maximum = [6_u64, 23, 59, 59, 999, 999_999][index - 13];
        // A negative signed input becomes larger than every allowed clock field.
        number as u64 <= maximum
    };
    if valid {
        Ok(number)
    } else {
        Err(absolute_input_error(number, index))
    }
}

/// Format rejected public fields outside the successful numeric-conversion frame.
#[cold]
#[inline(never)]
fn absolute_input_error(number: i64, index: usize) -> PyErr {
    let name = [
        "year",
        "month",
        "day",
        "weekday",
        "hour",
        "minute",
        "second",
        "millisecond",
        "microsecond",
    ][index - 10];
    crate::error_context::value_error(if index < 13 {
        format!("{name} must be a positive integer or None; got {number}")
    } else {
        let maximum = [6, 23, 59, 59, 999, 999_999][index - 13];
        format!("{name} must be from 0 through {maximum}, inclusive, or None; got {number}")
    })
}

/// Extract an already-qualified integer using the frozen width and error text.
///
/// The caller established PyInt membership or completed the numeric conversion.
/// # Errors
/// Propagates conversion errors and rejects inputs outside signed 64-bit range.
#[inline(always)]
pub(crate) fn converted_integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    // SAFETY: the caller qualified this live value as an integer under the GIL.
    // The public API checks signed 64-bit range without reading private payloads.
    let number = unsafe { pyo3::ffi::PyLong_AsLongLong(value.as_ptr()) };
    if number == -1 && unsafe { !pyo3::ffi::PyErr_Occurred().is_null() } {
        let error = crate::error_context::fetch(value.py());
        if error.is_instance_of::<PyOverflowError>(value.py()) {
            return Err(crate::error_context::overflow(
                "Python int too large to convert to C long",
            ));
        }
        return Err(error);
    }
    Ok(number as i64)
}

/// Exact integral microseconds and lazily stored sub-microsecond tails.
/// Integers never enter the floating sum; tails use standard fixed-unit order.
#[derive(Default)]
pub(crate) struct FixedFractions {
    tails: Option<[f64; 7]>,
    whole: i64,
}

impl FixedFractions {
    /// Round only small tails, retaining parity from all exact microseconds.
    #[inline(always)]
    fn rounded(&self, parity: i64) -> i64 {
        let Some(tails) = &self.tails else {
            return self.whole;
        };
        let mut tail = 0.0;
        for value in tails.iter().rev() {
            tail += value;
        }
        Self::finish(parity, self.whole, tail)
    }
    /// Skip fractional work when every contribution is exactly zero.
    #[inline(always)]
    fn has_value(&self) -> bool {
        self.whole != 0 || self.tails.is_some()
    }
    /// Round a bounded tail using the parity of the exact integer contribution.
    #[inline(always)]
    fn finish(parity: i64, whole: i64, tail: f64) -> i64 {
        let floor = tail.floor() as i64;
        let remainder = tail - floor as f64;
        let up = remainder > 0.5 || (remainder == 0.5 && ((parity ^ whole ^ floor) & 1 != 0));
        whole + floor + i64::from(up)
    }
}

/// Native constructor inputs. Integers remain exact even beyond 2**53.
struct Inputs {
    whole: [i64; 19],
    fraction: FixedFractions,
}

impl Inputs {
    /// Round the combined fractional duration once, including integer parity.
    /// # Errors
    /// Rejects a normalized final value outside the stored year/day range.
    #[inline(always)]
    fn normalized(mut self) -> Result<[i64; 15], &'static str> {
        if self.fraction.has_value() {
            let rounded = self.fraction.rounded(self.whole[9]);
            let Some(micros) = self.whole[9].checked_add(rounded) else {
                return normalize_wide_extra(self.whole, rounded);
            };
            self.whole[9] = micros;
        }
        normalize(self.whole)
    }
}

/// Split a real float's integer and fixed-unit fractional parts without Python
/// temporary numbers. Non-finite values and whole-part overflow are explicit.
/// # Errors
/// Raises ValueError for NaN and OverflowError for infinity/unrepresentable input.
#[inline(always)]
fn fractional_input(
    value: &Bound<'_, PyAny>,
    index: usize,
    fraction: &mut FixedFractions,
) -> PyResult<i64> {
    let (whole, scaled) = fixed_float_parts(value, index)?;
    let integer = scaled.trunc();
    // Seven fractional units are bounded by their fixed factors and fit i64.
    fraction.whole += integer as i64;
    let tail = scaled - integer;
    if tail != 0.0 {
        fraction.tails.get_or_insert([0.0; 7])[index - 3] = tail;
    }
    Ok(whole)
}

/// Split one float without a container or Python temporary number.
/// The caller has proved a real float and one of the seven fixed-unit indices.
/// # Errors
/// Retains the constructor's non-finite and signed input range errors.
#[inline(always)]
fn fixed_float_parts(value: &Bound<'_, PyAny>, index: usize) -> PyResult<(i64, f64)> {
    let number = if let Ok(number) = value.cast::<PyFloat>() {
        number.value()
    } else {
        crate::numeric::float_value(value)?
    };
    if number.is_nan() {
        return Err(crate::error_context::value_error(
            "Delta duration must be finite",
        ));
    }
    if !number.is_finite()
        || !(-9_223_372_036_854_775_808.0..9_223_372_036_854_775_808.0).contains(&number)
    {
        return Err(crate::error_context::overflow(
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
    let scaled = (number - number.trunc()) * factor;
    Ok((whole, scaled))
}

/// Keep integer conversion first; only the seven fixed units read float data.
/// # Errors
/// Retains legacy custom conversion callbacks and new fractional input errors.
#[inline]
fn constructor_input(
    value: &Bound<'_, PyAny>,
    index: usize,
    fraction: &mut FixedFractions,
) -> PyResult<i64> {
    if index >= 10 && value.is_none() {
        return Ok(-1);
    }
    if crate::numeric::is_bool(value) {
        return Err(public_boolean_error(value, index));
    }
    if index >= 10 {
        let number = if value.is_instance_of::<PyInt>() {
            converted_integer(value)?
        } else {
            if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) == 0 } {
                return Err(absolute_integer_type_error(value, index));
            }
            index_protocol_integer(value)?
        };
        return validate_absolute_input(number, index);
    }
    relative_input(value, index, fraction)
}

/// Explain a missing absolute-field protocol without examining callback errors.
#[cold]
#[inline(never)]
fn absolute_integer_type_error(value: &Bound<'_, PyAny>, index: usize) -> PyErr {
    let name = [
        "year",
        "month",
        "day",
        "weekday",
        "hour",
        "minute",
        "second",
        "millisecond",
        "microsecond",
    ][index - 10];
    crate::error_context::argument(
        value.py(),
        crate::error_context::type_error(format!("{name} must be an integer or None")),
        "Delta",
        name,
        value,
    )
}

/// Convert a relative amount once, preserving Delta's established numeric rules.
/// # Errors
/// Propagates checked numeric conversion, non-finite and integer-range errors.
#[inline]
pub(crate) fn relative_input(
    value: &Bound<'_, PyAny>,
    index: usize,
    fraction: &mut FixedFractions,
) -> PyResult<i64> {
    if value.cast::<PyInt>().is_ok() {
        return converted_integer(value);
    }
    if (3..10).contains(&index) && crate::numeric::supported_float(value) {
        return fractional_input(value, index, fraction);
    }
    index_integer(value)
}

/// Normalize one primitive amount without preparing unused constructor slots.
///
/// All units use the same floor carry, absolute limits and fractional rounding
/// as the general constructor. Custom conversions remain on its owned path.
fn single_numeric(index: usize, amount: i64, fractional_micros: i64) -> PyResult<Delta> {
    let mut fields = [0_i64; 15];
    fields[7..].fill(-1);
    let mut clock = 0_i64;
    match index {
        0 => fields[0] = amount,
        1 => {
            fields[0] = amount.div_euclid(4);
            fields[1] = amount.rem_euclid(4) * 3;
        }
        2 => {
            fields[0] = amount.div_euclid(12);
            fields[1] = amount.rem_euclid(12);
        }
        3 => {
            fields[2] = amount
                .checked_mul(7)
                .ok_or_else(|| crate::error_context::overflow(OVERFLOW))?
        }
        4 => fields[2] = amount,
        5 => (fields[2], clock) = fixed_unit_parts::<24, 3_600_000_000>(amount),
        6 => (fields[2], clock) = fixed_unit_parts::<1_440, 60_000_000>(amount),
        7 => (fields[2], clock) = fixed_unit_parts::<86_400, 1_000_000>(amount),
        8 => (fields[2], clock) = fixed_unit_parts::<86_400_000, 1_000>(amount),
        9 => (fields[2], clock) = fixed_unit_parts::<86_400_000_000, 1>(amount),
        10..=16 => {
            fields[index - 3] = absolute(
                amount,
                [9_999, 12, 31, 6, 23, 59, 59][index - 10],
                index >= 13,
            )
        }
        17 => {
            fields[14] = if amount < 0 {
                -1
            } else {
                amount.min(999) * 1_000
            }
        }
        18 => fields[14] = absolute(amount, 999_999, true),
        _ => unreachable!("validated constructor index"),
    }
    if fractional_micros != 0 {
        clock += fractional_micros;
    }
    if clock != 0 {
        fields[2] = fields[2]
            .checked_add(clock.div_euclid(86_400_000_000))
            .ok_or_else(|| crate::error_context::overflow(OVERFLOW))?;
        let clock = clock.rem_euclid(86_400_000_000);
        fields[3] = clock / 3_600_000_000;
        fields[4] = clock / 60_000_000 % 60;
        fields[5] = clock / 1_000_000 % 60;
        fields[6] = clock % 1_000_000;
    }
    Ok(Delta::from_normalized(fields, -1))
}

/// Use each fixed unit's constant divisor while keeping its remainder within one day.
#[inline(always)]
fn fixed_unit_parts<const UNITS_PER_DAY: i64, const MICROSECONDS_PER_UNIT: i64>(
    amount: i64,
) -> (i64, i64) {
    (
        amount.div_euclid(UNITS_PER_DAY),
        amount.rem_euclid(UNITS_PER_DAY) * MICROSECONDS_PER_UNIT,
    )
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
            fraction: FixedFractions::default(),
        });
    }
    if args.len() > 19 {
        return Err(crate::error_context::type_error(format!(
            "Delta() takes at most 19 positional arguments ({} given)",
            args.len()
        )));
    }
    if !args.is_empty() || kwargs.is_some_and(|values| values.len() > 1) {
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
                    let mut fraction = FixedFractions::default();
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
                return Err(crate::error_context::type_error(format!(
                    "Delta() got an unexpected keyword argument '{name}'"
                )));
            };
            if values[index].is_some() {
                return Err(crate::error_context::type_error(format!(
                    "Delta() got multiple values for keyword argument '{name}'"
                )));
            }
            values[index] = Some(value);
        }
    }
    let mut inputs = [0_i64; 19];
    inputs[10..].fill(-1);
    let mut fraction = FixedFractions::default();
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

/// Read a small primitive keyword set without preparing 19 pointer slots.
///
/// All keyword names are validated before conversion. Only actual integers
/// and fixed-unit floats qualify, so the live dictionary retains all values
/// without any intervening Python callback. Other inputs use the owned path.
/// # Preconditions
/// The caller proved kwargs contains exactly COUNT entries (2..=4) under the GIL.
/// # Errors
/// Preserves shape errors, ascending parameter conversion and numeric errors.
#[inline]
fn parse_small_keywords<const COUNT: usize>(
    kwargs: &Bound<'_, PyDict>,
) -> Option<PyResult<[i64; 15]>> {
    let py = kwargs.py();
    let mut entries = [(0_usize, std::ptr::null_mut(), false); COUNT];
    let names = keyword_names(py);
    let mut position = 0;
    let mut key = std::ptr::null_mut();
    let mut value = std::ptr::null_mut();
    for entry in &mut entries {
        // SAFETY: the checked dictionary has exactly COUNT entries. No callback
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
                return Some(Err(crate::error_context::type_error(format!(
                    "Delta() got an unexpected keyword argument '{name}'"
                ))));
            };
            index
        };
        // Exact integers need neither a subtype walk nor another boolean test
        // after sorting. Other integer subtypes retain direct stored extraction;
        // bool falls back before any conversion to the owned validation path.
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
            && (!(3..10).contains(&index) || unsafe { pyo3::ffi::PyFloat_Check(value) } == 0)
        {
            return None;
        }
        *entry = (index, value, floating);
    }
    // Two inputs need only one comparison and swap, as in the established
    // two-keyword path. Larger sets retain the shared bounded sort.
    let duplicate = if COUNT == 2 {
        if entries[0].0 == entries[1].0 {
            Some(entries[0].0)
        } else {
            if entries[1].0 < entries[0].0 {
                entries.swap(0, 1);
            }
            None
        }
    } else {
        entries.sort_unstable_by_key(|entry| entry.0);
        entries
            .windows(2)
            .find_map(|pair| (pair[0].0 == pair[1].0).then_some(pair[0].0))
    };
    if let Some(index) = duplicate {
        let name = keyword_names(py)[index].bind(py).to_str();
        return Some(Err(match name {
            Ok(name) => crate::error_context::type_error(format!(
                "Delta() got multiple values for keyword argument '{name}'"
            )),
            Err(error) => error,
        }));
    }
    let mut inputs = [0_i64; 19];
    inputs[10..].fill(-1);
    let mut fraction = FixedFractions::default();
    for (index, value, floating) in entries {
        // SAFETY: primitive qualification above excludes numeric callbacks;
        // the live dictionary still owns all borrowed values.
        let value = unsafe { Borrowed::from_ptr(py, value) };
        let number = if floating {
            fractional_input(&value, index, &mut fraction)
        } else {
            validated_integer(&value, index)
        };
        match number {
            Ok(number) => inputs[index] = number,
            Err(error) => return Some(Err(error)),
        }
    }
    Some(
        Inputs {
            whole: inputs,
            fraction,
        }
        .normalized()
        .map_err(crate::error_context::overflow),
    )
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
    if kwargs.is_none_or(|values| values.is_empty()) {
        return parse_plain_positional_inputs(args);
    }
    let py = args.py();
    let mut values = [std::ptr::null_mut(); 19];
    let mut floats = 0_u32;
    let mut present = (1_u32 << args.len()) - 1;
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
                    return Some(Err(crate::error_context::type_error(format!(
                        "Delta() got an unexpected keyword argument '{name}'"
                    ))));
                };
                index
            };
            if !values[index].is_null() {
                let name = match names[index].bind(py).to_str() {
                    Ok(name) => name,
                    Err(error) => return Some(Err(error)),
                };
                return Some(Err(crate::error_context::type_error(format!(
                    "Delta() got multiple values for keyword argument '{name}'"
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
            present |= 1 << index;
        }
    }
    Some(convert_native_values(py, present, floats, |index| {
        values[index]
    }))
}

/// Read primitive positional values in their parameter order.
///
/// Native integer and float extraction cannot call Python. If a custom input
/// appears, discard the local partial result and let the owned path preserve
/// callback handling. No caller-visible state changes during this scan.
/// # Preconditions
/// The caller bounded the tuple length to 19 and established no keywords.
/// # Errors
/// Preserves the first numeric error; None requests the owned path.
fn parse_plain_positional_inputs(args: &Bound<'_, PyTuple>) -> Option<PyResult<Inputs>> {
    let py = args.py();
    let mut inputs = [0_i64; 19];
    inputs[10..].fill(-1);
    let mut fraction = FixedFractions::default();
    for (index, slot) in inputs.iter_mut().take(args.len()).enumerate() {
        // SAFETY: the checked tuple owns this in-bounds item. Extraction from
        // native int/float objects cannot invoke conversion overrides.
        let pointer = unsafe { pyo3::ffi::PyTuple_GET_ITEM(args.as_ptr(), index as isize) };
        let value = unsafe { Borrowed::from_ptr(py, pointer) };
        let converted = if unsafe { pyo3::ffi::PyLong_Check(pointer) } != 0 {
            constructor_integer(&value, index)
        } else if (3..10).contains(&index) && unsafe { pyo3::ffi::PyFloat_Check(pointer) } != 0 {
            fractional_input(&value, index, &mut fraction)
        } else {
            return None;
        };
        match converted {
            Ok(number) => *slot = number,
            Err(error) => return Some(Err(error)),
        }
    }
    Some(Ok(Inputs {
        whole: inputs,
        fraction,
    }))
}

/// Convert prequalified native slots, preserving parameter order and errors.
/// The caller owns all present values and has already excluded callbacks.
#[inline(always)]
fn convert_native_values(
    py: Python<'_>,
    present: u32,
    floats: u32,
    value_at: impl Fn(usize) -> *mut pyo3::ffi::PyObject,
) -> PyResult<Inputs> {
    let mut inputs = [0_i64; 19];
    inputs[10..].fill(-1);
    let mut fraction = FixedFractions::default();
    if floats == 0 {
        let mut remaining = present;
        while remaining != 0 {
            let index = remaining.trailing_zeros() as usize;
            remaining &= remaining - 1;
            // SAFETY: qualification excludes callbacks; the caller keeps this
            // borrowed native integer alive throughout conversion.
            let value = value_at(index);
            let value = unsafe { Borrowed::from_ptr(py, value) };
            inputs[index] = constructor_integer(&value, index)?;
        }
    } else {
        let mut remaining = present;
        while remaining != 0 {
            let index = remaining.trailing_zeros() as usize;
            remaining &= remaining - 1;
            // SAFETY: all items were qualified without callbacks, and their
            // owner keeps this borrowed value alive throughout conversion.
            let value = value_at(index);
            let value = unsafe { Borrowed::from_ptr(py, value) };
            let result = if floats & (1 << index) != 0 {
                fractional_input(&value, index, &mut fraction)
            } else {
                constructor_integer(&value, index)
            };
            inputs[index] = result?;
        }
    }
    Ok(Inputs {
        whole: inputs,
        fraction,
    })
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
            .ok_or_else(|| crate::error_context::runtime("Delta representation buffer exceeded"))?
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

/// A source snapshot whose ranges and normalization have already been checked.
/// Its private payload prevents raw foreign fields from skipping validation.
pub(crate) struct RelativeFields([i64; 15]);

/// Normalize interpreted source fields with the same fixed-duration calculation
/// as Delta construction. Absolute source meanings must be resolved first.
/// # Errors
/// Rejects a normalized year/day outside the supported signed integer range.
pub(crate) fn normalize_relative_fields(
    fields: [i64; 15],
    fraction: FixedFractions,
) -> PyResult<RelativeFields> {
    let mut inputs = [0; 19];
    for (field, parameter) in [0, 2, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18]
        .into_iter()
        .enumerate()
    {
        inputs[parameter] = fields[field];
    }
    inputs[17] = -1;
    Inputs {
        whole: inputs,
        fraction,
    }
    .normalized()
    .map(RelativeFields)
    .map_err(crate::error_context::overflow)
}

/// Normalize all 19 constructor values into the 15 stored Delta fields.
///
/// Ordinary inputs retain the narrow fast path; necessary wider intermediates are checked by final range.
/// negative remainders use floor division. Absolute units retain their original
/// clamping and millisecond/microsecond replacement rules.
///
/// # Errors
/// Rejects a normalized year or day value outside the supported range.
#[inline(always)]
fn normalize(inputs: [i64; 19]) -> Result<[i64; 15], &'static str> {
    normalize_narrow(&inputs).or_else(|_| normalize_wide(inputs))
}

/// Preserve the ordinary constructor path without wide-integer work.
#[inline(always)]
fn normalize_narrow(inputs: &[i64; 19]) -> Result<[i64; 15], &'static str> {
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
    let (months, years) = carry(months, inputs[0], 12)?;
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

/// Normalize unbounded intermediates whose final year/day fields must fit i64.
/// Seven i64-derived values and fixed unit factors are safely bounded within i128.
#[cold]
fn normalize_relative_wide(relative: [i128; 7]) -> Result<[i64; 15], &'static str> {
    let months = relative[0] * 12 + relative[1];
    let micros = relative[2] * 86_400_000_000
        + relative[3] * 3_600_000_000
        + relative[4] * 60_000_000
        + relative[5] * 1_000_000
        + relative[6];
    let days = micros.div_euclid(86_400_000_000);
    let clock = micros.rem_euclid(86_400_000_000);
    let mut fields = [0; 15];
    fields[7..].fill(-1);
    fields[..7].copy_from_slice(&[
        i64::try_from(months.div_euclid(12)).map_err(|_| OVERFLOW)?,
        months.rem_euclid(12) as i64,
        i64::try_from(days).map_err(|_| OVERFLOW)?,
        (clock / 3_600_000_000) as i64,
        (clock / 60_000_000 % 60) as i64,
        (clock / 1_000_000 % 60) as i64,
        (clock % 1_000_000) as i64,
    ]);
    Ok(fields)
}

/// Handle constructor overflow without widening stored values or ordinary work.
#[cold]
fn normalize_wide(inputs: [i64; 19]) -> Result<[i64; 15], &'static str> {
    normalize_wide_extra(inputs, 0)
}

/// Preserve a rounded fractional contribution even when raw microseconds cannot hold it.
#[cold]
fn normalize_wide_extra(
    inputs: [i64; 19],
    extra_microseconds: i64,
) -> Result<[i64; 15], &'static str> {
    let wide = inputs.map(i128::from);
    let mut fields = normalize_relative_wide([
        wide[0],
        wide[1] * 3 + wide[2],
        wide[3] * 7 + wide[4],
        wide[5],
        wide[6],
        wide[7],
        wide[8] * 1_000 + wide[9] + i128::from(extra_microseconds),
    ])?;
    for (offset, (maximum, zero_allowed)) in [
        (9_999, false),
        (12, false),
        (31, false),
        (6, true),
        (23, true),
        (59, true),
        (59, true),
    ]
    .into_iter()
    .enumerate()
    {
        fields[7 + offset] = absolute(inputs[10 + offset], maximum, zero_allowed);
    }
    fields[14] = if inputs[17] >= 0 {
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
    Ok(fields)
}

#[pymethods]
impl Delta {
    /// Keep NumPy scalar operands intact until reflected Delta dispatch.
    #[classattr]
    fn __array_priority__() -> f64 {
        1000.0
    }
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
    /// TypeError
    ///     rd is not a relativedelta instance.
    /// ValueError
    ///     weekday is set or leapdays is nonzero; Delta cannot preserve those rules.
    /// OverflowError
    ///     A converted value or calculation is outside the supported integer range.
    ///
    /// Notes
    /// -----
    /// Fields follow the source relativedelta meaning: date zero means unset,
    /// clock zero is an explicit replacement, and relative years/months are applied
    /// before limiting a destination day. Unrepresentable rules are rejected.
    /// Raw fields are read directly; custom normalized() methods are not called.
    /// Fixed-duration fractions use the same microsecond rounding as Delta().
    /// The returned value follows Delta's own date, fold and arithmetic rules;
    /// it is not a transparent replacement for every source operation.
    /// Errors from actual field access or numeric conversion reach the caller.
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
        crate::interop::relativedelta_fields(rd)
            .and_then(Self::from_fields)
            .map_err(|error| {
                crate::error_context::argument(rd.py(), error, "Delta.from_relativedelta", "rd", rd)
            })
    }
    /// Convert this Delta to a standard-library time span.
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
    /// Standard pandas Timestamp anchors instead use elapsed instants, preserving
    /// nanoseconds and long spans until the final standard timedelta is created.
    /// Custom arithmetic methods retain control over their own results.
    /// Months are never approximated as a fixed number of days. Errors from
    /// applying the Delta to the starting value propagate.
    /// A nanosecond difference is rounded once to the nearest microsecond,
    /// with ties going to the even microsecond. Other timedelta subclasses
    /// are returned as a standard datetime.timedelta with the same span.
    ///
    /// Examples
    /// --------
    /// >>> Delta(hours=25).to_timedelta()
    /// datetime.timedelta(days=1, seconds=3600)
    /// >>> Delta(months=1).to_timedelta(date(2024, 1, 31))
    /// datetime.timedelta(days=29)
    #[pyo3(signature = (start=None))]
    pub(crate) fn to_timedelta<'py>(
        slf: &Bound<'py, Self>,
        start: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyDelta>> {
        let py = slf.py();
        (|| {
            if let Some(start) = start {
                crate::interop::reject_nat(start, "Delta.to_timedelta", "start")?;
                if !start.is_instance_of::<PyDate>() {
                    return Err(crate::error_context::type_error(
                        "start must be a date or datetime",
                    ));
                }
                if slf.is_exact_instance_of::<Self>()
                    && let Some(span) = crate::interop::builtin_span(slf.get(), start)?
                {
                    return Ok(span);
                }
                if let Some(span) = crate::interop::timestamp_span(slf, start)? {
                    return Ok(span);
                }
                let target = start.add(slf).map_err(crate::error_context::external)?;
                let difference = target.sub(start).map_err(crate::error_context::external)?;
                let difference = difference.cast_into::<PyDelta>().map_err(|_| {
                    crate::error_context::type_error("start arithmetic did not produce a timedelta")
                })?;
                return crate::interop::standard_span(&difference);
            }
            slf.get().fixed_timedelta(py)
        })()
        .map_err(|error| {
            let none = py.None();
            crate::error_context::argument(
                py,
                error,
                "Delta.to_timedelta",
                "start",
                start.unwrap_or(none.bind(py)),
            )
        })
    }
    /// Add this Delta to each value and return the results in order.
    /// NumPy inputs retain ordinary value + Delta return types and exceptions.
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
    #[pyo3(signature = (*args, **kwargs), text_signature = "(years=0, quarters=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0, milliseconds=0, microseconds=0, year=None, month=None, day=None, weekday=None, hour=None, minute=None, second=None, millisecond=None, microsecond=None)")]
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
        self.fields.word(1) as u32 & 1 != 0
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
    /// Delta subclasses that inherit equality, inequality and hashing use the same value rules.
    /// Equal Delta values have equal hashes and can share dictionary keys.
    pub(crate) fn __eq__<'py>(
        slf: &Bound<'py, Self>,
        other: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let py = other.py();
        if !crate::protocol::same_value_semantics(slf, other)? {
            return Ok(py.NotImplemented().into_bound(py));
        }
        let Ok(rhs) = other.cast::<Self>() else {
            return Ok(py.NotImplemented().into_bound(py));
        };
        Ok(PyBool::new(py, slf.get().native_eq(rhs.get()))
            .to_owned()
            .into_any())
    }

    /// Compare two Delta values for inequality.
    ///
    /// Returns
    /// -------
    /// bool or NotImplemented
    ///     The opposite of equality. A subclass overriding __eq__ inherits its
    ///     opposite here unless it defines __ne__ itself. Direct calls preserve
    ///     NotImplemented and equality callback exceptions.
    pub(crate) fn __ne__<'py>(
        slf: &Bound<'py, Self>,
        other: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let py = other.py();
        // Ordinary inherited values need only their existing semantic check.
        // Delegate to Python equality only when that native path does not apply.
        if crate::protocol::same_value_semantics(slf, other)? {
            if let Ok(rhs) = other.cast::<Self>() {
                return Ok(PyBool::new(py, !slf.get().native_eq(rhs.get()))
                    .to_owned()
                    .into_any());
            }
        }
        if let Some(result) = crate::protocol::inherited_inequality(slf, other)? {
            return Ok(result);
        }
        Ok(py.NotImplemented().into_bound(py))
    }

    /// Return a separate object with the same Delta value and type.
    ///
    /// Returns
    /// -------
    /// Delta
    ///     A shallow copy. Additional dictionary and slot attribute values remain shared.
    fn __copy__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::copy_object(slf, None).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__copy__",
                "arguments",
                slf.as_any(),
            )
        })
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
        crate::state::copy_object(slf, Some(memo)).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__deepcopy__",
                "memo",
                memo.as_any(),
            )
        })
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
    /// Use pickle or copy for ordinary saving and copying. Subclass dictionary
    /// and slot attributes are included.
    fn __getstate__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        crate::state::capture(slf).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__getstate__",
                "arguments",
                slf.as_any(),
            )
        })
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
        crate::state::restore(slf, state).map_err(|error| {
            crate::error_context::argument(slf.py(), error, "Delta.__setstate__", "state", state)
        })
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
        crate::state::reduce_ex(slf).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__reduce_ex__",
                "arguments",
                slf.as_any(),
            )
        })
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
        crate::state::reduce(slf).map_err(|error| {
            crate::error_context::argument(
                slf.py(),
                error,
                "Delta.__reduce__",
                "arguments",
                slf.as_any(),
            )
        })
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
    pub(crate) fn __repr__<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyString>> {
        let py = slf.py();
        // SAFETY: slf owns a live instance. A registered cache type proves the
        // conventional GIL path; SDK exact-type fallback never grants cell access.
        let cached_exact = unsafe { crate::protocol::is_cached_exact_delta(slf.as_ptr()) };
        let exact = cached_exact || slf.is_exact_instance_of::<Self>();
        if cached_exact && let Some(text) = unsafe { slf.get().representation.get(py) } {
            return Ok(text);
        }
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
        if exact {
            // Only the immutable base caches its own display. Subclasses keep
            // their observable name lookups. A Python string has no back-edge
            // to this value; PyO3 drops the owned reference before storage reuse.
            // Compute before claiming the one-time cell. This avoids detaching
            // for uncontended first formatting and permits safe reentrant lookup.
            // A reentrant winner has the same immutable fields; set() then drops
            // the unused owned string without replacing the saved one.
            let text = exact_representation(py, &fields, &names)?.unbind();
            // Formatting can reenter or destroy the cache owner. Recheck its
            // GIL qualification before touching the cell; otherwise return the
            // complete string through the standard SDK ownership path.
            if !unsafe { crate::protocol::is_cached_exact_delta(slf.as_ptr()) } {
                return Ok(text.into_bound(py));
            }
            // SAFETY: the refreshed qualification and live slf prove the GIL
            // contract. Neither cell operation retains a borrow across callbacks.
            unsafe { slf.get().representation.set(py, text) };
            return unsafe { slf.get().representation.get(py) }.ok_or_else(|| {
                crate::error_context::runtime("Delta representation was not initialized")
            });
        }
        // Subclasses retain observable class/name lookup and Unicode conversion.
        let class_name = slf
            .as_any()
            .getattr(pyo3::intern!(py, "__class__"))
            .map_err(crate::error_context::external)?
            .getattr(pyo3::intern!(py, "__name__"))
            .map_err(crate::error_context::external)?;
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
    ///     Invalid dates or NumPy NaT. Custom constructor errors propagate unchanged.
    /// Exception
    ///     Third-party conversion and other Python callback errors propagate.
    ///
    /// Notes
    /// -----
    /// Date operations apply absolute fields, relative increments, then weekday;
    /// datetime timezone and fold are preserved. Pandas Timestamp nanoseconds are
    /// retained unless an absolute microsecond or millisecond setting replaces
    /// the fractional second. Arrays are not supported.
    pub(crate) fn __add__<'py>(&self, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        // Delta operands cannot also have datetime's incompatible native layout.
        // Resolve the native increment pair before entering the date adapter.
        if let Ok(rhs) = other.cast::<Self>() {
            return Bound::new(other.py(), self.combine(&rhs.borrow(), false)?)
                .map(Bound::into_any);
        }
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
                    crate::interop::read_relative_fields(other)?,
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
    /// NumPy may convert a left-hand scalar before reflected dispatch. An
    /// expression such as value + delta can pass a different type from a direct
    /// delta.__radd__(value) call.
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
                    crate::interop::read_relative_fields(other)?,
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
                    crate::interop::read_relative_fields(other)?,
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
        if let Ok(date) = other.cast::<PyDateTime>()
            && date.get_year() == 1
        {
            crate::interop::reject_nat(other, "Delta.__sub__", "other")?;
        }
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
                    crate::interop::read_relative_fields(other)?,
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
    #[inline(always)]
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
    #[inline(always)]
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
    fn wide_intermediate_is_normalized_before_final_range_check() {
        let mut inputs = defaults();
        inputs[8] = i64::MAX;
        inputs[9] = i64::MIN;
        let result = normalize(inputs).expect("wide millisecond input fits final fields");
        let total = i128::from(i64::MAX) * 1_000 + i128::from(i64::MIN);
        assert_eq!(i128::from(result[2]), total.div_euclid(86_400_000_000));
        let mut inputs = defaults();
        inputs[3] = i64::MAX;
        assert!(normalize(inputs).is_err());
        let mut inputs = defaults();
        inputs[0] = i64::MAX;
        inputs[2] = 12;
        assert!(normalize(inputs).is_err());
    }
}
