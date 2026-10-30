//! Shared nanosecond parser result, before Python datetime/array construction.
use crate::parser::Truth;
use crate::parser::fields::{Fields, Iso, Lenient, Nano, Policy, Precision, Strict};

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDateTime, PyTzInfoAccess};

static POLARS_ADAPTER: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static POLARS_SERIES: PyOnceLock<Option<Py<PyType>>> = PyOnceLock::new();

/// Retain the actual Series class from the single shared dependency attempt.
pub(crate) fn prepare_polars_type(series: &Bound<'_, PyAny>) -> PyResult<()> {
    let candidate = if series.is_none() {
        None
    } else {
        Some(series.cast::<PyType>()?.clone().unbind())
    };
    let _ = POLARS_SERIES.set(series.py(), candidate);
    Ok(())
}

/// Test the real cached Series ancestry without imports or name-based hints.
fn is_polars_series(value: &Bound<'_, PyAny>) -> bool {
    let Some(Some(series)) = POLARS_SERIES.get(value.py()) else {
        return false;
    };
    // SAFETY: both the live object and interpreter-owned class remain valid.
    unsafe {
        ffi::PyType_IsSubtype(
            ffi::Py_TYPE(value.as_ptr()),
            series.bind(value.py()).as_type_ptr(),
        ) != 0
    }
}
use pyo3::types::{PyDelta, PyDeltaAccess, PyFloat, PyInt, PyString, PyType};

/// Supported output resolutions, ordered from coarse to fine.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum Unit {
    Second,
    Millisecond,
    Microsecond,
    Nanosecond,
}
impl Unit {
    /// Validate a public unit name before processing any input.
    pub(crate) fn parse(value: &str) -> PyResult<Self> {
        match value {
            "s" => Ok(Self::Second),
            "ms" => Ok(Self::Millisecond),
            "us" => Ok(Self::Microsecond),
            "ns" => Ok(Self::Nanosecond),
            _ => Err(crate::error_context::value_error(
                "unit must be 's', 'ms', 'us' or 'ns'",
            )),
        }
    }
    /// Number of nanoseconds in one tick of this resolution.
    pub(crate) fn nanos(self) -> i128 {
        match self {
            Self::Second => 1_000_000_000,
            Self::Millisecond => 1_000_000,
            Self::Microsecond => 1000,
            Self::Nanosecond => 1,
        }
    }
    /// NumPy/pandas spelling for this resolution.
    pub(crate) fn name(self) -> &'static str {
        match self {
            Self::Second => "s",
            Self::Millisecond => "ms",
            Self::Microsecond => "us",
            Self::Nanosecond => "ns",
        }
    }
}

/// Convert numeric ticks directly at nanosecond precision, keeping whole ticks exact.
/// The fractional multiplication uses the input float's normal arithmetic; a
/// coarser output is selected afterwards, never through a microsecond carrier.
pub(crate) fn float_nanos(number: f64, unit: Unit) -> PyResult<i128> {
    if number.is_nan() {
        return Err(crate::error_context::value_error(
            "numeric epoch must not be NaN",
        ));
    }
    if !number.is_finite() || number < i128::MIN as f64 || number >= i128::MAX as f64 {
        return Err(crate::error_context::overflow("numeric epoch is too large"));
    }
    let whole = number.trunc();
    let fraction = ((number - whole) * unit.nanos() as f64).floor() as i128;
    (whole as i128)
        .checked_mul(unit.nanos())
        .and_then(|value| value.checked_add(fraction))
        .ok_or_else(|| crate::error_context::overflow("numeric epoch is too large"))
}

/// A timezone boundary value; ordinary parsing owns no Python object.
pub(crate) enum Zone {
    Naive,
    Offset(i64),
    Object(Py<PyAny>),
}
/// Integer time and source precision shared by scalar and batch output builders.
pub(crate) struct Parsed {
    pub nanos: i128,
    pub unit: Unit,
    pub zone: Zone,
}

/// Convert completed fields to a wide integer without allocating a datetime.
fn from_fields<P: Policy>(
    py: Python<'_>,
    parsed: &crate::parser::ParsedFields<P>,
    default: Option<&Bound<'_, PyAny>>,
    ignoretz: bool,
) -> PyResult<Parsed> {
    let f = &parsed.fields;
    let region = parsed.region.as_deref().filter(|_| !ignoretz);
    if let Some(region) = region.filter(|zone| zone.fixed_offset_us.is_none()) {
        return from_region_fields(py, f, region, default, parsed.default_date);
    }
    let [y, m, d, h, minute, s, us] = crate::parser::complete(f, parsed.default_date)?;
    if !(1..=12).contains(&m) || d < 1 {
        return Err(crate::error_context::value_error(
            "parsed date is outside the supported calendar range",
        ));
    }
    let days = crate::calendar::ordinal(i64::from(y), i64::from(m), i64::from(d)) - 719_163;
    let mut ns = (((i128::from(days) * 24 + i128::from(h)) * 60 + i128::from(minute)) * 60
        + i128::from(s))
        * 1_000_000_000
        + i128::from(us) * 1000
        + i128::from(f.fraction.tail());
    let zone = if let Some(region) = region {
        // Only a configuration-time proof reaches this branch. Retain the
        // actual zone identity for array consumers, without a date carrier.
        let offset = region.fixed_offset_us.ok_or_else(|| {
            crate::error_context::runtime("registered fixed zone lost its offset")
        })?;
        ns -= i128::from(offset) * 1000;
        let object = region.object.as_ref().ok_or_else(|| {
            crate::error_context::runtime("registered fixed zone lost its object")
        })?;
        Zone::Object(object.clone_ref(py))
    } else if !ignoretz && f.is_tzoffset_set() {
        if !(-86_400_000_000..86_400_000_000).contains(&f.timezone_microseconds())
            || f.timezone_microseconds() == -86_400_000_000
        {
            return Err(crate::parser::invalid_offset(py, f.timezone_microseconds()));
        }
        ns -= i128::from(f.timezone_microseconds()) * 1000;
        Zone::Offset(f.timezone_microseconds())
    } else {
        Zone::Naive
    };
    Ok(Parsed {
        nanos: ns,
        unit: if f.fraction.has_nanos() {
            Unit::Nanosecond
        } else {
            Unit::Microsecond
        },
        zone,
    })
}

/// Resolve only regional wall times at the ZoneInfo boundary, keeping the
/// original nanosecond tail and using integer UTC conversion afterwards.
#[inline(never)]
fn from_region_fields<P: Policy>(
    py: Python<'_>,
    f: &Fields<P>,
    region: &crate::parser::zones::RegisteredZone,
    default: Option<&Bound<'_, PyAny>>,
    default_date: Option<[i32; 3]>,
) -> PyResult<Parsed> {
    let values = crate::parser::complete(f, default_date)?;
    let date = crate::parser::zones::resolve(py, region, values, default, f.strict())?;
    // resolve creates an exact builtin datetime with these checked fields.
    // Keep that necessary callback receiver and its single real offset read,
    // without reclassifying the freshly constructed date through read().
    let offset = offset_us(
        &date
            .call_method0("utcoffset")
            .map_err(crate::error_context::external)?,
    )?;
    let [y, m, d, h, minute, s, us] = values.map(i64::from);
    let days = crate::calendar::ordinal(y, m, d) - 719_163;
    let mut nanos = (((i128::from(days) * 24 + i128::from(h)) * 60 + i128::from(minute)) * 60
        + i128::from(s))
        * 1_000_000_000
        + i128::from(us) * 1000
        + i128::from(f.fraction.tail());
    let zone = if let Some(offset) = offset {
        nanos -= i128::from(offset) * 1000;
        Zone::Object(crate::parser::zones::object(py, region)?.clone().unbind())
    } else {
        Zone::Naive
    };
    Ok(Parsed {
        nanos,
        unit: if f.fraction.has_nanos() {
            Unit::Nanosecond
        } else {
            Unit::Microsecond
        },
        zone,
    })
}

/// Prepare text options once; all grammar work keeps native integer fields.
pub(crate) struct Options<'a, 'py> {
    pub default: Option<&'a Bound<'py, PyAny>>,
    pub yearfirst: Option<bool>,
    pub dayfirst: Option<bool>,
    pub ignoretz: bool,
    pub isoformat: bool,
    pub strict: bool,
    pub iso_only: bool,
    pub cfg: Option<&'a Bound<'py, PyAny>>,
    pub input_unit: Unit,
}

/// Parse one supported input while retaining its precision and timezone identity.
pub(crate) fn read(value: &Bound<'_, PyAny>, opts: &Options<'_, '_>) -> PyResult<Parsed> {
    let py = value.py();
    if value.is_none() {
        return Err(crate::error_context::type_error(
            "dtobj must be a date/time value, not None",
        ));
    }
    if let Ok(text) = value.cast::<PyString>() {
        let text = if value.is_exact_instance_of::<PyString>() {
            text.clone()
        } else {
            value.str().map_err(crate::error_context::external)?
        };
        return if opts.iso_only {
            let f = crate::parser::read_fields::<Iso<Nano<Strict>>>(
                py,
                &text,
                opts.default,
                opts.yearfirst,
                opts.dayfirst,
                opts.ignoretz,
                true,
                opts.cfg,
            )?;
            from_fields(py, &f, opts.default, opts.ignoretz)
        } else if opts.strict {
            let f = crate::parser::read_fields::<Nano<Strict>>(
                py,
                &text,
                opts.default,
                opts.yearfirst,
                opts.dayfirst,
                opts.ignoretz,
                opts.isoformat,
                opts.cfg,
            )?;
            from_fields(py, &f, opts.default, opts.ignoretz)
        } else {
            let f = crate::parser::read_fields::<Nano<Lenient>>(
                py,
                &text,
                opts.default,
                opts.yearfirst,
                opts.dayfirst,
                opts.ignoretz,
                opts.isoformat,
                opts.cfg,
            )?;
            from_fields(py, &f, opts.default, opts.ignoretz)
        };
    }
    // Missing date identity must not depend on a mutable Python class name.
    if unsafe {
        ffi::PyDate_Check(value.as_ptr()) != 0 && ffi::PyDateTime_GET_YEAR(value.as_ptr()) == 1
    } {
        crate::interop::reject_nat(value, "parse_to_epoch", "dtobj")?;
    }
    if unsafe { ffi::PyDateTime_Check(value.as_ptr()) != 0 } && crate::interop::is_timestamp(value)?
    {
        let mut result = crate::interop::timestamp_ticks(value)?;
        let [year, month, day, hour, minute, second, microsecond] =
            crate::interop::timestamp_local_fields(value)?;
        let days = crate::calendar::ordinal(year, month, day) - 719_163;
        result.nanos = i128::from(days) * 86_400_000_000_000
            + ((i128::from(hour) * 60 + i128::from(minute)) * 60 + i128::from(second))
                * 1_000_000_000
            + i128::from(microsecond) * 1000
            + result.nanos.rem_euclid(1000);
        result.zone = Zone::Naive;
        if !opts.ignoretz {
            if let Some(tz) = value.cast::<PyDateTime>()?.get_tzinfo() {
                if let Some(offset) = offset_us(
                    &value
                        .call_method0("utcoffset")
                        .map_err(crate::error_context::external)?,
                )? {
                    result.nanos -= i128::from(offset) * 1000;
                    result.zone = Zone::Object(tz.into_any().unbind());
                }
            }
        }
        return Ok(result);
    }
    // SAFETY: the imported datetime API proves the native date payload before
    // reading it. Existing datetime subclasses retain their actual UTC callback.
    unsafe {
        let ptr = value.as_ptr();
        if ffi::PyDate_Check(ptr) != 0 {
            let days = crate::calendar::ordinal(
                i64::from(ffi::PyDateTime_GET_YEAR(ptr)),
                i64::from(ffi::PyDateTime_GET_MONTH(ptr)),
                i64::from(ffi::PyDateTime_GET_DAY(ptr)),
            ) - 719_163;
            let mut ns = i128::from(days) * 86_400_000_000_000;
            let mut zone = Zone::Naive;
            if ffi::PyDateTime_Check(ptr) != 0 {
                ns += ((i128::from(ffi::PyDateTime_DATE_GET_HOUR(ptr)) * 60
                    + i128::from(ffi::PyDateTime_DATE_GET_MINUTE(ptr)))
                    * 60
                    + i128::from(ffi::PyDateTime_DATE_GET_SECOND(ptr)))
                    * 1_000_000_000
                    + i128::from(ffi::PyDateTime_DATE_GET_MICROSECOND(ptr)) * 1000;
                if !opts.ignoretz && ffi::PyDateTime_DATE_GET_TZINFO(ptr) != ffi::Py_None() {
                    if let Some(offset) = offset_us(
                        &value
                            .call_method0("utcoffset")
                            .map_err(crate::error_context::external)?,
                    )? {
                        ns -= i128::from(offset) * 1000;
                        zone = Zone::Object(
                            value
                                .getattr("tzinfo")
                                .map_err(crate::error_context::external)?
                                .unbind(),
                        );
                    }
                }
            }
            return Ok(Parsed {
                nanos: ns,
                unit: if ffi::PyDateTime_Check(ptr) != 0 {
                    Unit::Microsecond
                } else {
                    Unit::Second
                },
                zone,
            });
        }
    }
    if value.is_instance_of::<PyInt>() {
        if crate::numeric::is_bool(value) {
            return Err(crate::error_context::type_error(
                "boolean values are not date or epoch inputs",
            ));
        }
        let n = value.extract::<i128>()?;
        let ns = n
            .checked_mul(opts.input_unit.nanos())
            .ok_or_else(|| crate::error_context::overflow("numeric epoch is too large"))?;
        return Ok(Parsed {
            nanos: ns,
            unit: opts.input_unit,
            zone: Zone::Naive,
        });
    }
    if value.is_instance_of::<PyFloat>() {
        let number = value.extract::<f64>()?;
        return Ok(Parsed {
            nanos: float_nanos(number, opts.input_unit)?,
            unit: if number.fract() == 0.0 {
                opts.input_unit
            } else {
                Unit::Nanosecond
            },
            zone: Zone::Naive,
        });
    }
    if let Some(result) = read_numpy(value)? {
        return Ok(result);
    }
    if is_polars_series(value) {
        // The adapter module depends on this extension, so initialize its
        // callable once on first use after module construction has finished.
        let adapter =
            crate::python_cache::get_or_prepare(&POLARS_ADAPTER, py, || -> PyResult<_> {
                Ok(py
                    .import("rstimes.parser")?
                    .getattr("_polars_epoch_value")
                    .map_err(crate::error_context::external)?
                    .unbind())
            })?;
        // This retained package helper marks its own failures and externalizes
        // each actual Series callback. Do not reclassify that known origin.
        let scalar = adapter.bind(py).call1((value, opts.ignoretz))?;
        return read_numpy(&scalar)?
            .ok_or_else(|| crate::error_context::type_error("invalid Polars datetime export"));
    }
    Err(crate::error_context::type_error(
        "expected date/time text, datetime, date, numeric seconds, numpy.datetime64 or a one-element Polars Datetime Series",
    ))
}

/// Decode all supported NumPy datetime units without a microsecond round trip.
pub(crate) fn read_numpy(value: &Bound<'_, PyAny>) -> PyResult<Option<Parsed>> {
    let Some((ticks, code, multiplier)) = crate::numpy_scalar::datetime_ticks(value)? else {
        return Ok(None);
    };
    numpy_ticks(ticks, code, multiplier).map(Some)
}

/// Decode a checked NumPy buffer element with the scalar decoder's unit rules.
pub(crate) fn numpy_ticks(ticks: i64, code: i32, multiplier: i32) -> PyResult<Parsed> {
    if ticks == i64::MIN {
        return Err(crate::error_context::value_error("NaT has no epoch value"));
    }
    native_datetime_ticks(ticks, code, multiplier)
}

/// Decode a physically valid native date tick. Its caller has already applied
/// the source's sentinel or independent validity rule; MIN itself is a value.
pub(crate) fn native_datetime_ticks(ticks: i64, code: i32, multiplier: i32) -> PyResult<Parsed> {
    let ticks = crate::numpy_scalar::scaled_ticks(ticks, multiplier)?;
    let (ns, unit) = match code {
        0 | 1 => {
            let months = if code == 0 {
                ticks
                    .checked_mul(12)
                    .ok_or_else(|| crate::error_context::overflow("NumPy year overflow"))?
            } else {
                ticks
            };
            let year = i64::try_from(months.div_euclid(12) + 1970)
                .map_err(|_| crate::error_context::overflow("NumPy year overflow"))?;
            let month = (months.rem_euclid(12) + 1) as i64;
            let days = i128::from(
                crate::calendar::checked_ordinal(year, month, 1)
                    .map_err(crate::error_context::overflow)?,
            ) - 719_163;
            (days * 86_400_000_000_000, Unit::Second)
        }
        2 | 4..=10 => {
            let (scale, unit) = match code {
                2 => (604_800_000_000_000, Unit::Second),
                4 => (86_400_000_000_000, Unit::Second),
                5 => (3_600_000_000_000, Unit::Second),
                6 => (60_000_000_000, Unit::Second),
                7 => (1_000_000_000, Unit::Second),
                8 => (1_000_000, Unit::Millisecond),
                9 => (1000, Unit::Microsecond),
                _ => (1, Unit::Nanosecond),
            };
            (
                ticks.checked_mul(scale).ok_or_else(|| {
                    crate::error_context::overflow("NumPy datetime epoch overflow")
                })?,
                unit,
            )
        }
        _ => {
            return Err(crate::error_context::value_error(
                "unsupported NumPy datetime unit; use years through nanoseconds",
            ));
        }
    };
    Ok(Parsed {
        nanos: ns,
        unit,
        zone: Zone::Naive,
    })
}

/// Validate an ordinary timedelta offset without entering foreign adapters.
#[inline(always)]
fn native_offset_us(td: &Bound<'_, PyDelta>) -> PyResult<Option<i64>> {
    let days = i64::from(td.get_days());
    // A normalized offset shorter than a day can only have day 0 or -1.
    // Proving this first keeps the arithmetic safely in i64.
    if !(-1..=0).contains(&days) {
        return Err(crate::error_context::value_error(
            "utcoffset() must be strictly between -24 and +24 hours",
        ));
    }
    let value = (days * 86_400 + i64::from(td.get_seconds())) * 1_000_000
        + i64::from(td.get_microseconds());
    if !(-86_400_000_000 < value && value < 86_400_000_000) {
        return Err(crate::error_context::value_error(
            "utcoffset() must be strictly between -24 and +24 hours",
        ));
    }
    Ok(Some(value))
}

/// Validate a Python timezone callback before integer arithmetic.
#[inline(always)]
pub(crate) fn offset_us(value: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    // SAFETY: module registration imported the datetime C API. The exact type
    // predicate reads only the live object's type, without Python callbacks.
    if unsafe { ffi::PyDelta_CheckExact(value.as_ptr()) != 0 } {
        // SAFETY: the exact timedelta type proves its native layout.
        return native_offset_us(unsafe { value.cast_unchecked::<PyDelta>() });
    }
    foreign_offset_us(value)
}

/// Read foreign duration values only when the offset is not a builtin timedelta.
#[cold]
fn foreign_offset_us(value: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    if value.is_none() {
        return Ok(None);
    }
    let td = value.cast::<PyDelta>().map_err(|_| {
        crate::error_context::type_error("utcoffset() must return None or timedelta")
    })?;
    if let Some(nanos) = crate::interop::duration_nanoseconds(value)? {
        if !(-86_400_000_000_000 < nanos && nanos < 86_400_000_000_000) {
            return Err(crate::error_context::value_error(
                "utcoffset() must be strictly between -24 and +24 hours",
            ));
        }
        // Validate both the original span and the floor-to-microsecond result:
        // a legal -24h+1ns would otherwise become the forbidden -24h boundary.
        let micros = nanos.div_euclid(1000) as i64;
        if !(-86_400_000_000 < micros && micros < 86_400_000_000) {
            return Err(crate::error_context::value_error(
                "utcoffset() must be strictly between -24 and +24 hours",
            ));
        }
        return Ok(Some(micros));
    }
    native_offset_us(td)
}

/// Convert one supported date/time value to integer epoch ticks.
///
/// Returns a Python int directly, without selecting a datetime result class. Regional wall times use their timezone offset and fold without repairing or rejecting missing local times. A datetime default supplies its stored fold; otherwise fold=0. Explicit invalid fields follow strict. The integer result is not limited by datetime years or NumPy integer storage; actual arithmetic and timezone-conversion limits still raise errors.
///
/// Parameters
/// ----------
/// dtobj : object
///     One supported date/time input: text, a Python date/datetime, numeric epoch
///     seconds, or a NumPy datetime64 scalar. With Polars installed, a one-value
///     Datetime Series is also accepted. NaT, null values and longer Series are
///     rejected. Polars remains an optional dependency.
/// unit : str, default 'us'
///     Output tick resolution: s, ms, us or ns. A finer remainder is floored,
///     including for dates before 1970.
/// default : date-like | None, default None
///     An independently complete date used to fill missing year, month and day
///     only. Date/datetime subclasses, complete date text, numeric epoch seconds
///     and NumPy datetime64 are supported. A datetime also supplies its stored
///     fold; its clock and timezone are not defaults. Pandas NaT is rejected.
///     Complete defaults need not fit the standard datetime year range.
/// yearfirst : bool | None, default None
///     Prefer a year in the first position of an ambiguous numeric date. None uses
///     Configs when this parser option is optional.
/// dayfirst : bool | None, default None
///     Prefer a day before a month in an ambiguous numeric date. None uses Configs
///     when this parser option is optional.
/// ignoretz : bool, default False
///     False applies timezone offsets to obtain UTC epoch ticks. True uses local
///     clock fields without their offset, including for aware Python datetime,
///     pandas Timestamp and Polars Datetime inputs. Naive values and numeric or
///     NumPy ticks have no timezone offset to discard.
/// isoformat : bool, default True
///     Try ISO date/time forms before the general grammar. This does not restrict
///     input to ISO text.
/// strict : bool, default False
///     True rejects explicit invalid fields, conflicting repeated fields and a
///     weekday inconsistent with a full written date. False clips invalid fields
///     without carrying and allows later conflicting fields to win. A two-digit
///     year requires False and a complete default date.
/// cfg : Configs | None, default None
///     Optional Configs vocabulary and ordering rules for text. None uses the
///     library defaults.
/// input_unit : str, default 's'
///     Resolution of numeric input ticks only: s, ms, us or ns. The default s means
///     a number such as 1 denotes one epoch second; native temporal values keep
///     their own unit.
///
/// Returns
/// -------
/// int
///     Integer ticks since 1970-01-01T00:00:00. Naive dates use the same epoch
///     without a host-local conversion; Python integers are not restricted to int64
///     storage.
///
/// Raises
/// ------
/// TypeError
///     An argument has an unsupported type.
/// ParseError
///     Text cannot be interpreted under the requested rules.
/// ValueError
///     A numeric scalar is NaN or a date input is missing.
/// OverflowError
///     An integer conversion or result exceeds the supported range.
///
/// Notes
/// -----
/// Native NumPy, pandas and Polars values retain their supported fine precision.
/// Python datetime retains its microsecond precision. Numeric data is converted
/// directly at nanosecond precision before selecting the requested output unit;
/// coarser units select the earlier boundary. Numeric defaults retain their
/// microsecond date role. Boolean options accept only bool and numpy.bool_.
///
/// Examples
/// --------
/// >>> from datetime import datetime, timezone, timedelta
/// >>> value = datetime(1970, 1, 1, 8, tzinfo=timezone(timedelta(hours=8)))
/// >>> parse_to_epoch(value)
/// 0
/// >>> parse_to_epoch(value, ignoretz=True)
/// 28800000000
/// >>> parse_to_epoch(1, "ms")
/// 1000
/// >>> parse_to_epoch(1, "ms", input_unit="ms")
/// 1
/// >>> parse_to_epoch("10000-01-02", "ns") > 2**63
/// True
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature=(dtobj,unit="us",default=None,yearfirst=None,dayfirst=None,ignoretz=Truth(false),isoformat=Truth(true),strict=Truth(false),cfg=None,*,input_unit="s"), text_signature="(dtobj, unit='us', default=None, yearfirst=None, dayfirst=None, ignoretz=False, isoformat=True, strict=False, cfg=None, *, input_unit='s')")]
fn parse_to_epoch(
    dtobj: &Bound<'_, PyAny>,
    unit: &str,
    default: Option<&Bound<'_, PyAny>>,
    yearfirst: Option<Truth>,
    dayfirst: Option<Truth>,
    ignoretz: Truth,
    isoformat: Truth,
    strict: Truth,
    cfg: Option<&Bound<'_, PyAny>>,
    input_unit: &str,
) -> PyResult<i128> {
    let unit = Unit::parse(unit).map_err(|error| {
        crate::error_context::argument(
            dtobj.py(),
            error,
            "parse_to_epoch",
            "unit",
            &pyo3::types::PyString::new(dtobj.py(), unit).into_any(),
        )
    })?;
    let opts = Options {
        default,
        yearfirst: yearfirst.map(|flag| flag.0),
        dayfirst: dayfirst.map(|flag| flag.0),
        ignoretz: ignoretz.0,
        isoformat: isoformat.0,
        strict: strict.0,
        iso_only: false,
        cfg,
        input_unit: Unit::parse(input_unit).map_err(|error| {
            crate::error_context::argument(
                dtobj.py(),
                error,
                "parse_to_epoch",
                "input_unit",
                &PyString::new(dtobj.py(), input_unit).into_any(),
            )
        })?,
    };
    read(dtobj, &opts)
        .map(|result| result.nanos.div_euclid(unit.nanos()))
        .map_err(|error| {
            crate::parser::entry_error(dtobj.py(), "parse_to_epoch", "dtobj", dtobj, error)
        })
}

/// Register the scalar epoch API beside the existing datetime parser APIs.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(parse_to_epoch, module)?)?;
    module
        .getattr("parse_to_epoch")
        .map_err(crate::error_context::external)?
        .setattr("__module__", "rstimes.parser")?;
    Ok(())
}

/// Materialize a completed native zone only at an actual Python output boundary.
pub(crate) fn zone_object(py: Python<'_>, zone: &Zone) -> PyResult<Py<PyAny>> {
    match zone {
        Zone::Naive => Ok(py.None()),
        Zone::Object(value) => Ok(value.clone_ref(py)),
        Zone::Offset(us) => {
            // SAFETY: checked offsets fit a normalized one-day timedelta. Bound
            // retains its owner through the SDK's timezone constructor.
            let delta = unsafe {
                Bound::from_owned_ptr_or_err(
                    py,
                    ffi::PyDelta_FromDSU(
                        0,
                        us.div_euclid(1_000_000) as i32,
                        us.rem_euclid(1_000_000) as i32,
                    ),
                )?
            };
            unsafe { Bound::from_owned_ptr_or_err(py, ffi::PyTimeZone_FromOffset(delta.as_ptr())) }
                .map(Bound::unbind)
        }
    }
}
