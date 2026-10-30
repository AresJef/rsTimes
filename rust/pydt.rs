//! Calendar operations for the real Python datetime subclass.
//!
//! Instances retain only datetime's native value. Each operation borrows that
//! value, computes with integers, then creates one result of the requested type.

use crate::epoch::offset_us;
use crate::parser::Truth;
use pyo3::exceptions::{PyKeyError, PyOverflowError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{
    PyDate, PyDateAccess, PyDateTime, PyDelta, PyDeltaAccess, PyInt, PyTime, PyTimeAccess, PyTuple,
    PyType, PyTzInfo, PyTzInfoAccess,
};
use pyo3::{Borrowed, ffi};

/// Integer-only public arguments retain their established signed32 boundary.
#[derive(Clone, Copy)]
struct Integer(i64);
impl<'a, 'py> FromPyObject<'a, 'py> for Integer {
    type Error = PyErr;
    fn extract(value: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let n = crate::numeric::index_i64(&value)?;
        i32::try_from(n).map_err(|_| {
            crate::error_context::overflow("Pydt integer exceeds the signed 32-bit range")
        })?;
        Ok(Self(n))
    }
}
/// Checked integer protocol for exact epoch microseconds.
struct WideInteger(i64);
impl<'a, 'py> FromPyObject<'a, 'py> for WideInteger {
    type Error = PyErr;
    fn extract(value: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        crate::numeric::index_i64(&value).map(Self)
    }
}

/// Standard datetime constructors accept the integer index protocol, not floats.
#[derive(Clone, Copy)]
struct IndexInteger(i64);
impl<'a, 'py> FromPyObject<'a, 'py> for IndexInteger {
    type Error = PyErr;
    fn extract(value: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        Integer::extract(value).map(|n| Self(n.0))
    }
}

/// Optional replacement fields use checked wide extraction before calendar bounds.
#[derive(Clone, Copy)]
struct FieldIndex(i64);
impl<'a, 'py> FromPyObject<'a, 'py> for FieldIndex {
    type Error = PyErr;
    fn extract(value: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        crate::numeric::index_i64(&value).map(Self)
    }
}

static CLASS: PyOnceLock<Py<PyType>> = PyOnceLock::new();
static DATETIME_NEW: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static REPLACE_TIMEZONE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static ZONEINFO: PyOnceLock<Py<PyType>> = PyOnceLock::new();
static ZONEINFO_KEY: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static REGION_OFFSET: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
// Only immutable standard-base descriptors are retained. A mutable child's
// effective bound methods are still read on every qualification.
type RegionMethod = (Py<PyAny>, ffi::PyCFunction);
static REGION_METHODS: PyOnceLock<Option<[RegionMethod; 2]>> = PyOnceLock::new();
static UTC_REGIONS: PyOnceLock<Vec<Py<PyAny>>> = PyOnceLock::new();
static SUB: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static ORIGINAL_REDUCE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static OBJECT_STATE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static TZINFO_FROMUTC: std::sync::OnceLock<ffi::PyCFunction> = std::sync::OnceLock::new();

/// Register the ordinary Python subclass; no PyO3 object tail is allocated.
#[pyfunction]
fn _pydt_register(class: &Bound<'_, PyType>, resolve_timezone: &Bound<'_, PyAny>) -> PyResult<()> {
    if !class.is_subclass_of::<PyDateTime>()? {
        return Err(crate::error_context::type_error(
            "Pydt must inherit datetime",
        ));
    }
    CLASS.get_or_try_init(class.py(), || -> PyResult<_> { Ok(class.clone().unbind()) })?;
    let registered = CLASS
        .get(class.py())
        .ok_or_else(|| crate::error_context::runtime("Pydt class is unavailable"))?;
    let original = crate::protocol::method_definition(registered.bind(class.py()), "__reduce__")?
        .ok_or_else(|| crate::error_context::runtime("Pydt reduction is unavailable"))?;
    let _ = ORIGINAL_REDUCE.set(class.py(), original.unbind());
    crate::python_cache::get_or_prepare(&OBJECT_STATE, class.py(), || {
        Ok::<_, PyErr>(
            class
                .py()
                .import("builtins")?
                .getattr("object")
                .map_err(crate::error_context::external)?
                .getattr("__getstate__")
                .map_err(crate::error_context::external)?
                .unbind(),
        )
    })?;
    crate::python_cache::get_or_prepare(&REPLACE_TIMEZONE, class.py(), || -> PyResult<_> {
        Ok(resolve_timezone.clone().unbind())
    })?;
    let builtin = class
        .py()
        .get_type::<PyTzInfo>()
        .call0()
        .map_err(crate::error_context::external)?
        .getattr("fromutc")
        .map_err(crate::error_context::external)?;
    // SAFETY: this is the immutable builtin tzinfo instance's bound C method.
    if let Some(function) = unsafe { ffi::PyCFunction_GetFunction(builtin.as_ptr()) } {
        let _ = TZINFO_FROMUTC.set(function);
    }
    Ok(())
}

/// Cheap exact native class gate for shared foreign-scalar adapters.
#[inline]
pub(crate) fn is_exact(value: &Bound<'_, PyAny>) -> bool {
    CLASS
        .get(value.py())
        .is_some_and(|base| value.get_type().is(base.bind(value.py())))
}

/// Borrow checked date fields without invoking overridable Python properties.
#[inline(always)]
pub(crate) fn parts(value: &Bound<'_, PyDateTime>) -> [i64; 7] {
    [
        i64::from(value.get_year()),
        i64::from(value.get_month()),
        i64::from(value.get_day()),
        i64::from(value.get_hour()),
        i64::from(value.get_minute()),
        i64::from(value.get_second()),
        i64::from(value.get_microsecond()),
    ]
}

/// Borrow the stored timezone without invoking a subclass's visible properties.
#[pyfunction]
fn _pydt_stored_timezone<'py>(value: &Bound<'py, PyDateTime>) -> Bound<'py, PyAny> {
    // SAFETY: value is a checked live datetime. The returned owned reference
    // keeps its timezone alive independently of the source instance.
    unsafe { Bound::from_borrowed_ptr(value.py(), ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr())) }
}

/// Read and divide the stored microseconds in one native call.
#[pyfunction]
fn _pydt_millisecond(value: &Bound<'_, PyDateTime>) -> u32 {
    value.get_microsecond() / 1000
}

/// Build an exact Pydt through datetime's C API; child classes keep construction hooks.
fn result<'py>(
    value: &Bound<'py, PyDateTime>,
    fields: [i64; 7],
    local: bool,
) -> PyResult<Bound<'py, PyAny>> {
    result_inner::<false>(value, fields, local)
}
fn selected_result<'py>(
    value: &Bound<'py, PyDateTime>,
    fields: [i64; 7],
) -> PyResult<Bound<'py, PyAny>> {
    result_inner::<true>(value, fields, true)
}
fn result_inner<'py, const SELECTION: bool>(
    value: &Bound<'py, PyDateTime>,
    fields: [i64; 7],
    local: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let py = value.py();
    if !(1..=9999).contains(&fields[0]) {
        return Err(crate::error_context::overflow(
            "result is outside years 1 through 9999",
        ));
    }
    if parts(value) == fields {
        return Ok(value.clone().into_any());
    }
    let class = value.get_type();
    // SAFETY: the checked live datetime owns its timezone reference.
    let tz =
        unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr())) };
    let (fields, fold) = if local && !ordinary_zone(&tz) {
        calendar_target::<SELECTION>(value, fields, &tz)?
    } else {
        (fields, i32::from(value.get_fold()))
    };
    build_selected(&class, fields, &tz, fold)
}

/// Prepare Pydt calendar results while retaining Delta's public subtype call.
pub(crate) fn delta_calendar_fields(
    value: &Bound<'_, PyDateTime>,
    fields: [i64; 7],
) -> PyResult<Option<([i64; 7], i32)>> {
    let Some(base) = CLASS.get(value.py()) else {
        return Ok(None);
    };
    if !value.get_type().is_subclass(base.bind(value.py()))? {
        return Ok(None);
    }
    if !(1..=9999).contains(&fields[0]) {
        return Ok(None);
    }
    let zone = _pydt_stored_timezone(value);
    calendar_target::<false>(value, fields, &zone).map(Some)
}

/// Finish an external calendar computation without reparsing its native fields.
#[pyfunction]
fn _pydt_from_calendar<'py>(
    original: &Bound<'py, PyDateTime>,
    target: &Bound<'py, PyDateTime>,
) -> PyResult<Bound<'py, PyAny>> {
    let zone = _pydt_stored_timezone(target);
    let (fields, fold) = calendar_target::<false>(original, parts(target), &zone)?;
    if fields == parts(original)
        && fold == i32::from(original.get_fold())
        && zone.is(_pydt_stored_timezone(original))
    {
        return Ok(original.clone().into_any());
    }
    build_selected(&original.get_type(), fields, &zone, fold)
}

/// Only exact standard ZoneInfo can prove a date-independent offset with None.
/// CPython's fixed rule is checked once when Configs registers/restores a zone;
/// custom tzinfo and mutable ZoneInfo subtypes must remain dynamic.
pub(crate) fn is_zoneinfo_instance(zone: &Bound<'_, PyAny>) -> bool {
    ZONEINFO.get(zone.py()).is_some_and(|base| {
        // SAFETY: retained actual types belong to the attached interpreter.
        unsafe {
            ffi::PyType_IsSubtype(
                ffi::Py_TYPE(zone.as_ptr()),
                base.bind(zone.py()).as_type_ptr(),
            ) != 0
        }
    })
}

pub(crate) fn is_exact_zoneinfo(zone: &Bound<'_, PyAny>) -> bool {
    ZONEINFO
        .get(zone.py())
        .is_some_and(|base| zone.get_type().is(base.bind(zone.py())))
}

pub(crate) fn fixed_zoneinfo_offset(zone: &Bound<'_, PyAny>) -> PyResult<Option<i64>> {
    let py = zone.py();
    let Some(base) = ZONEINFO.get(py) else {
        return Ok(None);
    };
    if !zone.get_type().is(base.bind(py)) {
        return Ok(None);
    }
    let offset = zone
        .call_method1(pyo3::intern!(py, "utcoffset"), (py.None(),))
        .map_err(crate::error_context::external)?;
    offset_us(&offset)
}

/// Read a real region's stored key, without a subclass display-property facade.
/// The outer option distinguishes non-regions; a real unkeyed region stays None.
pub(crate) fn zoneinfo_key(zone: &Bound<'_, PyAny>) -> PyResult<Option<Option<String>>> {
    let py = zone.py();
    let Some(base) = ZONEINFO.get(py) else {
        return Ok(None);
    };
    // SAFETY: both retained base and live input type belong to this interpreter.
    if unsafe { ffi::PyType_IsSubtype(ffi::Py_TYPE(zone.as_ptr()), base.bind(py).as_type_ptr()) }
        == 0
    {
        return Ok(None);
    }
    ZONEINFO_KEY
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("ZoneInfo key descriptor is unavailable"))?
        .bind(py)
        .call_method1("__get__", (zone, base.bind(py)))
        .map_err(crate::error_context::external)?
        .extract::<Option<String>>()
        .map(Some)
}

/// Extract a real datetime's clock only after rejecting a missing pandas value.
#[pyfunction]
fn _pydt_clock<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyTime>> {
    crate::interop::reject_nat(value, "Pydt.combine", "time")?;
    PyTime::new_with_fold(
        value.py(),
        value.get_hour(),
        value.get_minute(),
        value.get_second(),
        value.get_microsecond(),
        value.get_tzinfo().as_ref(),
        value.get_fold(),
    )
}

/// Call the stored timezone protocol, bypassing datetime-subclass method overrides.
pub(crate) fn utc_offset<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyAny>> {
    let py = value.py();
    // SAFETY: the checked live datetime retains its tzinfo for this call.
    let tz =
        unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr())) };
    if tz.is_none() {
        Ok(py.None().into_bound(py))
    } else {
        tz.call_method1(pyo3::intern!(py, "utcoffset"), (value,))
            .map_err(crate::error_context::external)
    }
}

/// Compare the two regional occurrences using builtin carriers only.
pub(crate) fn regional_offsets(
    value: &Bound<'_, PyDateTime>,
    tz: &Bound<'_, PyAny>,
) -> PyResult<Option<(i64, i64)>> {
    let opposite = PyDateTime::new_with_fold(
        value.py(),
        value.get_year(),
        value.get_month(),
        value.get_day(),
        value.get_hour(),
        value.get_minute(),
        value.get_second(),
        value.get_microsecond(),
        Some(tz.cast::<PyTzInfo>()?),
        !value.get_fold(),
    )?;
    // Exact standard regions have an immutable public method descriptor. Keep
    // subclass attribute lookup on its original protocol path.
    let direct = ZONEINFO
        .get(value.py())
        .filter(|kind| tz.get_type().is(kind.bind(value.py())))
        .and_then(|_| REGION_OFFSET.get(value.py()));
    let read_offset = |dt: &Bound<'_, PyDateTime>| -> PyResult<Option<i64>> {
        let result = match direct {
            Some(method) => method
                .bind(value.py())
                .call1((tz, dt))
                .map_err(crate::error_context::external),
            None => utc_offset(dt),
        }?;
        offset_us(&result)
    };
    let (before, after) = if value.get_fold() {
        (read_offset(&opposite)?, read_offset(value)?)
    } else {
        (read_offset(value)?, read_offset(&opposite)?)
    };
    Ok(before.zip(after))
}

/// An unmodified ZoneInfo subtype has the same fold rules as its base. Keep
/// custom overrides on the protocol path instead of silently replacing them.
pub(crate) fn standard_region(zone: &Bound<'_, PyAny>) -> PyResult<bool> {
    let Some(base) = ZONEINFO.get(zone.py()) else {
        return Ok(false);
    };
    let base = base.bind(zone.py());
    let actual = zone.get_type();
    if actual.is(base) {
        return Ok(true);
    }
    if !actual.is_subclass(base)? {
        return Ok(false);
    }
    let originals =
        crate::python_cache::get_or_prepare(&REGION_METHODS, zone.py(), || -> PyResult<_> {
            // SAFETY: base is a live type. C methods can be reused only while its
            // public immutable-type flag forbids replacing these definitions.
            if unsafe { (*base.as_type_ptr()).tp_flags & ffi::Py_TPFLAGS_IMMUTABLETYPE } == 0 {
                return Ok(None);
            }
            let mut methods = Vec::with_capacity(2);
            for name in [
                pyo3::intern!(zone.py(), "fromutc"),
                pyo3::intern!(zone.py(), "utcoffset"),
            ] {
                let Some(descriptor) = crate::protocol::method_definition(base, name.to_str()?)?
                else {
                    return Ok(None);
                };
                // SAFETY: only an exact standard C descriptor can supply reusable
                // code. A custom descriptor remains on the dynamic protocol path.
                if unsafe {
                    ffi::Py_TYPE(descriptor.as_ptr())
                        != std::ptr::addr_of_mut!(ffi::PyMethodDescr_Type)
                } {
                    return Ok(None);
                }
                let bound = descriptor
                    .call_method1("__get__", (zone, &actual))
                    .map_err(crate::error_context::external)?;
                // SAFETY: the public predicate proves the accessor's C-function layout.
                if unsafe { ffi::PyCFunction_Check(bound.as_ptr()) } == 0 {
                    return Ok(None);
                }
                let Some(function) = (unsafe { ffi::PyCFunction_GetFunction(bound.as_ptr()) })
                else {
                    return Ok(None);
                };
                methods.push((descriptor.unbind(), function));
            }
            Ok(methods.try_into().ok())
        })?;
    let Some(originals) = originals else {
        return Ok(false);
    };
    for (name, (_, expected)) in [
        pyo3::intern!(zone.py(), "fromutc"),
        pyo3::intern!(zone.py(), "utcoffset"),
    ]
    .into_iter()
    .zip(originals)
    {
        // Ordinary bound-method lookup is observable: an instance or a dynamic
        // __getattribute__ can override a method inherited unchanged by its class.
        let effective = zone.getattr(name).map_err(crate::error_context::external)?;
        // The builtin C-function family includes CPython's bound C methods;
        // both forms support these public accessors (neither is a Python hook).
        // identity of both function and receiver proves the current binding.
        let original = unsafe {
            ffi::PyCFunction_Check(effective.as_ptr()) != 0
                && ffi::PyCFunction_GetSelf(effective.as_ptr()) == zone.as_ptr()
                && ffi::PyCFunction_GetFunction(effective.as_ptr())
                    .is_some_and(|function| std::ptr::fn_addr_eq(function, *expected))
        };
        if !original {
            return Ok(false);
        }
    }
    Ok(true)
}

/// Reject a regional gap after the caller has already selected its timezone.
fn validate_regional(dt: &Bound<'_, PyDateTime>, tz: &Bound<'_, PyAny>) -> PyResult<()> {
    if regional_offsets(dt, tz)?.is_some_and(|(before, after)| after > before) {
        return Err(crate::error_context::value_error(format!(
            "local time {:04}-{:02}-{:02} {:02}:{:02}:{:02} does not exist in {}; choose an existing local time. fold selects repeated times only",
            dt.get_year(),
            dt.get_month(),
            dt.get_day(),
            dt.get_hour(),
            dt.get_minute(),
            dt.get_second(),
            crate::error_context::preview(tz)?
        )));
    }
    Ok(())
}

/// Strict wall-time validation; None and standard fixed offsets need no work.
fn normalize_local<'py>(value: Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let dt = value.cast::<PyDateTime>()?;
    let py = value.py();
    // SAFETY: the live datetime owns its timezone and registration imported the API.
    let tz = unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(dt.as_ptr())) };
    if ordinary_zone(&tz) {
        return Ok(value);
    }
    if standard_region(&tz)? {
        validate_regional(dt, &tz)?;
    } else if let Some(back) = roundtrip(dt, &tz)? {
        if parts(back.cast::<PyDateTime>()?) != parts(dt) {
            return Err(crate::error_context::value_error(
                "local time does not exist according to tzinfo.fromutc(); choose an existing local time",
            ));
        }
    }
    Ok(value)
}

/// Select a valid calendar target using the original offset, not numeric fold.
/// Ordinary None/fixed-offset paths do no regional probing or round trips.
fn calendar_target<const RETAIN_DAY: bool>(
    original: &Bound<'_, PyDateTime>,
    fields: [i64; 7],
    tz: &Bound<'_, PyAny>,
) -> PyResult<([i64; 7], i32)> {
    let py = original.py();
    if ordinary_zone(tz) {
        return Ok((fields, i32::from(original.get_fold())));
    }
    let carrier = PyDateTime::new_with_fold(
        py,
        fields[0] as i32,
        fields[1] as u8,
        fields[2] as u8,
        fields[3] as u8,
        fields[4] as u8,
        fields[5] as u8,
        fields[6] as u32,
        Some(tz.cast::<PyTzInfo>()?),
        false,
    )?;
    if standard_region(tz)? {
        let Some((before, after)) = regional_offsets(&carrier, tz)? else {
            return Ok((fields, 0));
        };
        if after == before {
            return Ok((fields, 0));
        }
        let source_offset = offset_us(&utc_offset(original)?)?;
        if after < before {
            return Ok((fields, i32::from(source_offset == Some(after))));
        }
        let target_wall = epoch_microseconds(&carrier, false)?;
        let forward = if source_offset == Some(before) {
            true
        } else if source_offset == Some(after) {
            false
        } else {
            target_wall >= epoch_microseconds(original, false)?
        };
        if !RETAIN_DAY {
            let shift = (after - before) * if forward { 1 } else { -1 };
            let wall = target_wall
                .checked_add(shift)
                .ok_or_else(|| crate::error_context::overflow("Pydt local adjustment overflow"))?;
            if !existing_wall(wall, tz)? {
                return Err(crate::error_context::value_error(
                    "timezone cannot confirm a valid calendar target",
                ));
            }
            return Ok((from_us(wall)?, 0));
        }
        for candidate in crate::calendar::calendar_gap_targets(
            i128::from(target_wall) * 1000,
            i128::from(after - before) * 1000,
            forward,
        )
        .into_iter()
        .flatten()
        {
            let wall = i64::try_from(candidate.div_euclid(1000))
                .map_err(|_| crate::error_context::overflow("Pydt local adjustment overflow"))?;
            if existing_wall(wall, tz)? {
                return Ok((from_us(wall)?, 0));
            }
        }
        return Err(crate::error_context::value_error(
            "the selected calendar day has no valid local result; choose another date",
        ));
    }
    // Resolve the first occurrence through its own current fromutc method.
    let Some(before) = offset_us(&utc_offset(&carrier)?)? else {
        return Ok((fields, 0));
    };
    let method = tz
        .getattr(pyo3::intern!(py, "fromutc"))
        .map_err(crate::error_context::external)?;
    // SAFETY: the exact C-method predicate precedes both public accessors;
    // the owned method and timezone remain alive for pointer comparison.
    let builtin = unsafe {
        ffi::PyCFunction_Check(method.as_ptr()) != 0
            && ffi::PyCFunction_GetSelf(method.as_ptr()) == tz.as_ptr()
            && ffi::PyCFunction_GetFunction(method.as_ptr()).is_some_and(|actual| {
                TZINFO_FROMUTC
                    .get()
                    .is_some_and(|base| std::ptr::fn_addr_eq(actual, *base))
            })
    };
    let back = roundtrip_method(&carrier, tz, before, &method)?;
    let back = back.cast::<PyDateTime>()?;
    // datetime.tzinfo.fromutc always returns a fold=0 carrier. It cannot
    // confirm a distinct fold=1 occurrence; a successful first round trip
    // therefore already determines its only valid candidate. Custom methods
    // keep the full two-candidate protocol below, including live overrides.
    if builtin && parts(back) == fields && !back.get_fold() {
        return Ok((fields, 0));
    }
    let opposite = builtin_with_fold(&carrier, true)?;
    let Some(after) = offset_us(&utc_offset(&opposite)?)? else {
        return Ok((fields, 0));
    };
    let valid_before = parts(back) == fields && offset_us(&utc_offset(back)?)? == Some(before);
    if before == after && valid_before {
        return Ok((fields, 0));
    }
    let later = roundtrip_offset(&opposite, tz, after)?;
    let later = later.cast::<PyDateTime>()?;
    let valid_after = parts(later) == fields && offset_us(&utc_offset(later)?)? == Some(after);
    let source_offset = if valid_before && !valid_after {
        return Ok((fields, 0));
    } else if valid_after && !valid_before {
        return Ok((fields, 1));
    } else {
        offset_us(&utc_offset(original)?)?
    };
    if valid_before && valid_after {
        return Ok((
            fields,
            i32::from(before != after && source_offset == Some(after)),
        ));
    }
    let wall = epoch_microseconds(&carrier, false)?;
    let displacement = epoch_microseconds(back, false)? - wall;
    let forward = if source_offset == Some(before) {
        true
    } else if source_offset == Some(after) {
        false
    } else {
        wall >= epoch_microseconds(original, false)?
    };
    if !RETAIN_DAY {
        let candidate = from_us(
            wall.checked_add(displacement.abs() * if forward { 1 } else { -1 })
                .ok_or_else(|| crate::error_context::overflow("Pydt local adjustment overflow"))?,
        )?;
        let probe = wall_carrier(py, candidate, tz)?;
        if let Some(back) = roundtrip(&probe, tz)? {
            if parts(back.cast::<PyDateTime>()?) != candidate {
                return Err(crate::error_context::value_error(
                    "timezone cannot confirm a valid calendar target",
                ));
            }
        }
        return Ok((candidate, 0));
    }
    for candidate in crate::calendar::calendar_gap_targets(
        i128::from(wall) * 1000,
        i128::from(displacement).abs() * 1000,
        forward,
    )
    .into_iter()
    .flatten()
    {
        let fields = from_us(
            i64::try_from(candidate.div_euclid(1000))
                .map_err(|_| crate::error_context::overflow("Pydt local adjustment overflow"))?,
        )?;
        let probe = wall_carrier(py, fields, tz)?;
        if let Some(back) = roundtrip(&probe, tz)? {
            if parts(back.cast::<PyDateTime>()?) != fields {
                continue;
            }
        }
        return Ok((fields, 0));
    }
    Err(crate::error_context::value_error(
        "the selected calendar day has no valid local result; choose another date",
    ))
}

/// Native wall-clock microseconds for already validated calendar fields.
fn wall_us(fields: [i64; 7]) -> i64 {
    (crate::calendar::ordinal(fields[0], fields[1], fields[2]) - 719_163) * 86_400_000_000
        + fields[3] * 3_600_000_000
        + fields[4] * 60_000_000
        + fields[5] * 1_000_000
        + fields[6]
}

/// Create a builtin probe; user subclass construction is reserved for the result.
pub(crate) fn wall_carrier<'py>(
    py: Python<'py>,
    fields: [i64; 7],
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyDateTime>> {
    PyDateTime::new_with_fold(
        py,
        fields[0] as i32,
        fields[1] as u8,
        fields[2] as u8,
        fields[3] as u8,
        fields[4] as u8,
        fields[5] as u8,
        fields[6] as u32,
        Some(tz.cast::<PyTzInfo>()?),
        false,
    )
}

/// Change only a builtin probe's fold; its date fields were already validated.
fn builtin_with_fold<'py>(
    value: &Bound<'py, PyDateTime>,
    fold: bool,
) -> PyResult<Bound<'py, PyDateTime>> {
    let zone = _pydt_stored_timezone(value);
    PyDateTime::new_with_fold(
        value.py(),
        value.get_year(),
        value.get_month(),
        value.get_day(),
        value.get_hour(),
        value.get_minute(),
        value.get_second(),
        value.get_microsecond(),
        Some(zone.cast::<PyTzInfo>()?),
        fold,
    )
}

/// Standard immutable offsets and None never need local-time existence checks.
#[inline]
fn ordinary_zone(zone: &Bound<'_, PyAny>) -> bool {
    // SAFETY: registration initialized the datetime API; both type pointers are live.
    if zone.is_none()
        || unsafe {
            ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
        }
    {
        return true;
    }
    // Keep canonical UTC objects alive: a from_file() object can advertise an
    // arbitrary key, and key text alone does not prove fixed UTC rules.
    UTC_REGIONS
        .get(zone.py())
        .is_some_and(|zones| zones.iter().any(|known| known.as_ptr() == zone.as_ptr()))
}

/// Check fold sensitivity directly for immutable standard timezone rules.
/// The caller must already have proven that the stored datetime fields are real.
/// Dynamic timezone protocols retain their original replacement path instead.
pub(crate) fn standard_fold_dependent(value: &Bound<'_, PyDateTime>) -> PyResult<Option<bool>> {
    let py = value.py();
    // SAFETY: the checked datetime keeps its stored timezone alive throughout.
    let zone = unsafe { Borrowed::from_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr())) };
    if ordinary_zone(&zone) {
        return Ok(Some(false));
    }
    if !standard_region(&zone)? {
        return Ok(None);
    }
    Ok(Some(
        regional_offsets(value, &zone)?.is_some_and(|(before, after)| before != after),
    ))
}

/// Whether native wall fields denote an existing time, without creating Pydt.
pub(crate) fn existing_wall(wall: i64, tz: &Bound<'_, PyAny>) -> PyResult<bool> {
    let carrier = wall_carrier(tz.py(), from_us(wall)?, tz)?;
    if standard_region(tz)? {
        return Ok(regional_offsets(&carrier, tz)?.is_none_or(|(before, after)| after <= before));
    }
    Ok(roundtrip(&carrier, tz)?.is_none_or(|back| {
        back.cast::<PyDateTime>()
            .is_ok_and(|dt| parts(dt) == parts(&carrier))
    }))
}

/// Find the exact valid edges of a missing interval; never assume an hour-long gap.
pub(crate) fn gap_edges(wall: i64, gap: i64, tz: &Bound<'_, PyAny>) -> PyResult<(i64, i64)> {
    let mut low = wall
        .checked_sub(gap)
        .ok_or_else(|| crate::error_context::overflow("gap boundary overflow"))?;
    let mut high = wall;
    if !existing_wall(low, tz)? {
        return Err(crate::error_context::value_error(
            "timezone cannot confirm the beginning of a missing interval",
        ));
    }
    while high - low > 1 {
        let middle = low + (high - low) / 2;
        if existing_wall(middle, tz)? {
            low = middle;
        } else {
            high = middle;
        }
    }
    let before = low;
    low = wall;
    high = wall
        .checked_add(gap)
        .ok_or_else(|| crate::error_context::overflow("gap boundary overflow"))?;
    if !existing_wall(high, tz)? {
        return Err(crate::error_context::value_error(
            "timezone cannot confirm the end of a missing interval",
        ));
    }
    while high - low > 1 {
        let middle = low + (high - low) / 2;
        if existing_wall(middle, tz)? {
            high = middle;
        } else {
            low = middle;
        }
    }
    Ok((before, high))
}

/// Select the first/last existing instant inside the requested native period.
fn optional_period_target(
    value: &Bound<'_, PyDateTime>,
    fields: [i64; 7],
    lower: i64,
    upper: i64,
    end: bool,
    clock_cycle: bool,
) -> PyResult<Option<([i64; 7], i32)>> {
    let zone = _pydt_stored_timezone(value);
    if ordinary_zone(&zone) {
        return Ok(Some((fields, i32::from(value.get_fold()))));
    }
    let carrier = wall_carrier(value.py(), fields, &zone)?;
    if let Some((before, after)) = regional_offsets(&carrier, &zone)? {
        if after <= before {
            let fold = if after < before && clock_cycle {
                let original = offset_us(&utc_offset(value)?)?;
                i32::from(original == Some(after) || original != Some(before) && end)
            } else {
                i32::from(end && after < before)
            };
            if !standard_region(&zone)? {
                let probe = wall_carrier(value.py(), fields, &zone)?;
                let selected = if fold == 0 {
                    probe
                } else {
                    builtin_with_fold(&probe, true)?
                };
                if let Some(back) = roundtrip(&selected, &zone)? {
                    if parts(back.cast::<PyDateTime>()?) != fields {
                        return Err(crate::error_context::value_error(
                            "custom timezone cannot confirm the requested period boundary",
                        ));
                    }
                }
            }
            return Ok(Some((fields, fold)));
        }
        let (last, first) = gap_edges(wall_us(fields), after - before, &zone)?;
        let target = if end { last } else { first };
        if target < lower || target > upper {
            return Ok(None);
        }
        return Ok(Some((from_us(target)?, 0)));
    }
    // A timezone without an offset is timezone-naive by Python's own protocol.
    Ok(Some((fields, i32::from(value.get_fold()))))
}

fn period_target(
    value: &Bound<'_, PyDateTime>,
    fields: [i64; 7],
    lower: i64,
    upper: i64,
    end: bool,
    clock_cycle: bool,
) -> PyResult<([i64; 7], i32)> {
    optional_period_target(value, fields, lower, upper, end, clock_cycle)?.ok_or_else(|| {
        crate::error_context::value_error("the requested period has no existing local time")
    })
}

/// Enforce rounding direction after local-time selection, retaining aligned results.
fn rounded_target(
    value: &Bound<'_, PyDateTime>,
    fields: [i64; 7],
    factor: i64,
    mode: u8,
) -> PyResult<([i64; 7], i32)> {
    let zone = _pydt_stored_timezone(value);
    if ordinary_zone(&zone) {
        return Ok((fields, i32::from(value.get_fold())));
    }
    let carrier = wall_carrier(value.py(), fields, &zone)?;
    let Some((before, after)) = regional_offsets(&carrier, &zone)? else {
        return Ok((fields, i32::from(value.get_fold())));
    };
    let original = wall_us(parts(value)) - offset_us(&utc_offset(value)?)?.unwrap_or(0);
    let wall = wall_us(fields);
    if after <= before {
        let choices = [(before, 0), (after, 1)];
        let mut best = None;
        for (offset, fold) in choices {
            if !ZONEINFO
                .get(value.py())
                .is_some_and(|class| zone.get_type().is(class.bind(value.py())))
            {
                let selected = if fold == 0 {
                    carrier.clone()
                } else {
                    builtin_with_fold(&carrier, true)?
                };
                if let Some(back) = roundtrip(&selected, &zone)? {
                    if parts(back.cast::<PyDateTime>()?) != fields {
                        continue;
                    }
                }
            }
            let instant = wall - offset;
            if (mode == 1 && instant < original) || (mode == 2 && instant > original) {
                continue;
            }
            let distance = (instant - original).abs();
            if best.is_none_or(|(old, _)| distance < old) {
                best = Some((distance, fold));
            }
        }
        return best.map(|(_, fold)| (fields, fold)).ok_or_else(|| {
            crate::error_context::value_error(
                "no rounded local occurrence preserves the requested direction",
            )
        });
    }
    let (last, first) = gap_edges(wall, after - before, &zone)?;
    let lower = last.div_euclid(factor) * factor;
    let upper = first.div_euclid(factor) * factor
        + if first.rem_euclid(factor) == 0 {
            0
        } else {
            factor
        };
    let candidates = [(lower, before), (upper, after)];
    let mut best = None;
    for (wall, offset) in candidates {
        let instant = wall - offset;
        if (mode == 1 && instant < original) || (mode == 2 && instant > original) {
            continue;
        }
        let distance = (instant - original).abs();
        // With no representable even target inside a gap, prefer the later equal candidate.
        if best.is_none_or(|(old, _, _)| distance <= old) {
            best = Some((distance, wall, 0));
        }
    }
    let (_, wall, fold) = best.ok_or_else(|| {
        crate::error_context::value_error(
            "no valid rounded boundary preserves the requested direction",
        )
    })?;
    if !existing_wall(wall, &zone)? {
        return Err(crate::error_context::value_error(
            "timezone cannot confirm a valid rounded boundary",
        ));
    }
    Ok((from_us(wall)?, fold))
}

/// Perform one standard fromutc round trip without local-time repair recursion.
fn roundtrip<'py>(
    value: &Bound<'py, PyDateTime>,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let Some(offset) = offset_us(&utc_offset(value)?)? else {
        return Ok(None);
    };
    roundtrip_offset(value, tz, offset).map(Some)
}

/// Round-trip one candidate using its already consumed, validated offset.
pub(crate) fn roundtrip_offset<'py>(
    value: &Bound<'py, PyDateTime>,
    tz: &Bound<'py, PyAny>,
    offset: i64,
) -> PyResult<Bound<'py, PyAny>> {
    let method = tz
        .getattr(pyo3::intern!(value.py(), "fromutc"))
        .map_err(crate::error_context::external)?;
    roundtrip_method(value, tz, offset, &method)
}

/// Invoke the method retained after offset consumption, without looking it up twice.
fn roundtrip_method<'py>(
    value: &Bound<'py, PyDateTime>,
    tz: &Bound<'py, PyAny>,
    offset: i64,
    method: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let fields = from_us(epoch_microseconds(value, false)? - offset)?;
    // An internal UTC carrier must not invoke a child's public constructor.
    let carrier = PyDateTime::new_with_fold(
        value.py(),
        fields[0] as i32,
        fields[1] as u8,
        fields[2] as u8,
        fields[3] as u8,
        fields[4] as u8,
        fields[5] as u8,
        fields[6] as u32,
        Some(tz.cast::<PyTzInfo>()?),
        false,
    )?;
    let returned = method
        .call1((carrier,))
        .map_err(crate::error_context::external)?;
    let dt = returned
        .cast::<PyDateTime>()
        .map_err(|_| crate::error_context::type_error("tzinfo.fromutc() must return a datetime"))?;
    // SAFETY: the live returned object was checked as a real datetime.
    if unsafe { ffi::PyDateTime_DATE_GET_TZINFO(dt.as_ptr()) } != tz.as_ptr() {
        return Err(crate::error_context::value_error(
            "tzinfo.fromutc() returned a different timezone",
        ));
    }
    Ok(returned)
}

/// Apply the local-time policy to an explicitly localized convenience value.
#[pyfunction]
fn _pydt_normalize<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyAny>> {
    normalize_local(value.clone().into_any())
}

/// Validate regional construction, including genuine ZoneInfo subtypes.
/// Arbitrary tzinfo construction retains datetime's no-callback behavior.
fn normalize_construct<'py>(value: Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let dt = value.cast::<PyDateTime>()?;
    let py = value.py();
    let zone = _pydt_stored_timezone(dt);
    if ordinary_zone(&zone) {
        return Ok(value);
    }
    if let Some(kind) = ZONEINFO.get(py) {
        let actual = zone.get_type();
        if actual.is(kind.bind(py)) {
            validate_regional(dt, &zone)?;
        } else if actual.is_subclass(kind.bind(py))? {
            return normalize_local(value);
        }
    }
    Ok(value)
}

/// Invoke the public Python constructor with retained positional and keyword values.
fn call_datetime_fields<'py>(
    class: &Bound<'py, PyType>,
    fields: [Bound<'py, PyAny>; 7],
    zone: &Bound<'py, PyAny>,
    fold: i32,
) -> PyResult<Bound<'py, PyAny>> {
    static KEYWORDS: PyOnceLock<Py<PyTuple>> = PyOnceLock::new();
    let py = class.py();
    let names = KEYWORDS.get_or_try_init(py, || -> PyResult<_> {
        Ok(PyTuple::new(py, ["tzinfo", "fold"])?.unbind())
    })?;
    let [year, month, day, hour, minute, second, microsecond] = fields;
    let args = [
        year,
        month,
        day,
        hour,
        minute,
        second,
        microsecond,
        zone.clone(),
        PyInt::new(py, fold).into_any(),
    ];
    let pointers = args.each_ref().map(Bound::as_ptr);
    // SAFETY: the class, nine values and two keyword names remain owned for
    // the whole public call. Seven arguments are positional; no reference is stolen.
    unsafe {
        Bound::from_owned_ptr_or_err(
            py,
            ffi::PyObject_Vectorcall(
                class.as_ptr(),
                pointers.as_ptr(),
                7,
                names.bind(py).as_ptr(),
            ),
        )
    }
}

/// Allocate calendar fields for the registered ordinary datetime subclass.
/// Callers must verify the exact registered class before entering: arbitrary
/// native subclasses require their own constructors to initialize their payload.
fn allocate<'py>(
    class: &Bound<'py, PyType>,
    fields: [i64; 7],
    tz: &Bound<'py, PyAny>,
    fold: i32,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    // SAFETY: value is a checked live datetime and registration accepts only
    // the ordinary Python subclass. It has no foreign native instance tail.
    // Fields are normalized by the shared calendar; the SDK validates them.
    let pointer = unsafe {
        let api = ffi::PyDateTimeAPI()
            .as_ref()
            .ok_or_else(|| crate::error_context::runtime("datetime API unavailable"))?;
        (api.DateTime_FromDateAndTimeAndFold)(
            fields[0] as i32,
            fields[1] as i32,
            fields[2] as i32,
            fields[3] as i32,
            fields[4] as i32,
            fields[5] as i32,
            fields[6] as i32,
            tz.as_ptr(),
            fold,
            class.as_type_ptr(),
        )
    };
    unsafe { Bound::from_owned_ptr_or_err(py, pointer) }
}

/// Prepare public integer fields once; subclasses retain datetime's allocator.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One datetime constructor boundary"
)]
fn _pydt_create<'py>(
    class: &Bound<'py, PyType>,
    year: &Bound<'py, PyAny>,
    month: &Bound<'py, PyAny>,
    day: &Bound<'py, PyAny>,
    hour: &Bound<'py, PyAny>,
    minute: &Bound<'py, PyAny>,
    second: &Bound<'py, PyAny>,
    microsecond: &Bound<'py, PyAny>,
    zone: &Bound<'py, PyAny>,
    fold: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    let mut fields = [0_i64; 7];
    for (i, item) in [year, month, day, hour, minute, second, microsecond]
        .iter()
        .enumerate()
    {
        // Read protocols inside this boundary: generic argument extraction would
        // add its own note to a callback exception before our public context.
        fields[i] = Integer::extract(item.as_borrowed())?.0;
    }
    let fold = if crate::numeric::is_bool(fold) {
        i64::from(crate::numeric::boolean(fold)?)
    } else {
        crate::numeric::index_i64(fold)?
    };
    if !(0..=1).contains(&fold) {
        return Err(crate::error_context::value_error("fold must be 0 or 1"));
    }
    if CLASS.get(py).is_some_and(|base| class.is(base.bind(py))) {
        return allocate(class, fields, zone, fold as i32);
    }
    let kwargs = pyo3::types::PyDict::new(py);
    kwargs.set_item("fold", fold)?;
    DATETIME_NEW
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("datetime allocator is unavailable"))?
        .bind(py)
        .call(
            (
                class, fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[6],
                zone,
            ),
            Some(&kwargs),
        )
        .map_err(crate::error_context::external)
}

/// Construct one validated result with a live timezone and class.
fn build<'py>(
    class: &Bound<'py, PyType>,
    fields: [i64; 7],
    tz: &Bound<'py, PyAny>,
    fold: i32,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    if !(1..=9999).contains(&fields[0]) {
        return Err(crate::error_context::overflow(
            "result is outside years 1 through 9999",
        ));
    }
    if CLASS.get(py).is_some_and(|base| class.is(base.bind(py))) {
        return normalize_construct(allocate(class, fields, tz, fold)?);
    }
    call_datetime_fields(
        class,
        fields.map(|field| PyInt::new(py, field).into_any()),
        tz,
        fold,
    )
}

/// Finish fields whose local validity was already established by the calendar,
/// period, rounding or instant path. Python subclass constructors still run.
#[inline]
fn build_selected<'py>(
    class: &Bound<'py, PyType>,
    fields: [i64; 7],
    tz: &Bound<'py, PyAny>,
    fold: i32,
) -> PyResult<Bound<'py, PyAny>> {
    if CLASS
        .get(class.py())
        .is_some_and(|base| class.is(base.bind(class.py())))
    {
        allocate(class, fields, tz, fold)
    } else {
        build(class, fields, tz, fold)
    }
}

/// Finish a copied value; child constructors retain full ownership of their result.
fn copied<'py>(
    class: &Bound<'py, PyType>,
    fields: [i64; 7],
    tz: &Bound<'py, PyAny>,
    fold: i32,
) -> PyResult<Bound<'py, PyAny>> {
    build(class, fields, tz, fold)
}

/// Allocate the library's exact base type; dynamic constructors stay with Parser.
pub(crate) fn try_from_fields<'py>(
    class: &Bound<'py, PyAny>,
    fields: [i64; 7],
    zone: &Bound<'py, PyAny>,
    fold: i32,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = class.py();
    let Some(base) = CLASS.get(py).filter(|base| class.is(base.bind(py))) else {
        return Ok(None);
    };
    // SAFETY: Parser initialized the datetime capsule before constructing values.
    let fixed = unsafe {
        ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
    };
    if !zone.is_none()
        && !fixed
        && !ZONEINFO
            .get(py)
            .is_some_and(|kind| zone.get_type().is(kind.bind(py)))
    {
        return Ok(None);
    }
    // This is a parsed input boundary, rather than a calendar arithmetic result.
    // Preserve datetime's invalid-field category without narrowing wide parser
    // fields before the target class has been selected.
    if !(1..=9999).contains(&fields[0]) {
        return Err(crate::error_context::value_error(
            "year must be in 1 through 9999",
        ));
    }
    normalize_construct(allocate(base.bind(py), fields, zone, fold)?).map(Some)
}

/// Copy the result of a standard instant factory without wall-time repair.
/// The Python wrapper selects only the exact base Pydt and standard factory
/// sources; user subclasses and custom timezone protocols retain their hooks.
#[pyfunction]
fn _pydt_from_instant<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyAny>> {
    let py = value.py();
    let class = CLASS
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("Pydt class is unavailable"))?;
    // SAFETY: this live datetime owns the borrowed timezone. build retains it
    // on the new instance before the borrowed source can be released.
    let zone =
        unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr())) };
    allocate(
        class.bind(py),
        parts(value),
        &zone,
        i32::from(value.get_fold()),
    )
}

/// Copy stored datetime fields without creating seven Python integers first.
#[pyfunction]
#[pyo3(signature=(class, value, tz=None, preserve_instant=false))]
fn _pydt_copy_datetime<'py>(
    class: &Bound<'py, PyType>,
    value: &Bound<'py, PyDateTime>,
    tz: Option<&Bound<'py, PyAny>>,
    mut preserve_instant: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let zone = match tz {
        Some(zone) => zone.clone(),
        // SAFETY: the checked, live datetime owns its timezone reference.
        None => {
            let stored = unsafe {
                Bound::from_borrowed_ptr(
                    value.py(),
                    ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()),
                )
            };
            if ordinary_zone(&stored)
                || ZONEINFO
                    .get(value.py())
                    .is_some_and(|kind| stored.get_type().is(kind.bind(value.py())))
            {
                stored
            } else {
                let resolved = REPLACE_TIMEZONE
                    .get(value.py())
                    .ok_or_else(|| crate::error_context::runtime("timezone resolver unavailable"))?
                    .bind(value.py())
                    .call1((&stored,))
                    .map_err(crate::error_context::external)?;
                preserve_instant |= !resolved.is(&stored);
                resolved
            }
        }
    };
    let fields = if crate::interop::needs_true_year(value.get_year())
        && !value.is_exact_instance_of::<PyDateTime>()
    {
        crate::interop::reject_nat(value.as_any(), "Pydt.fromdatetime", "dt")?;
        crate::interop::timestamp_parts(value.as_any())?
            .map_or_else(|| parts(value), |parts| parts.0)
    } else {
        parts(value)
    };
    let fold = if preserve_instant {
        copied_fold(value, fields, &zone)?
    } else {
        i32::from(value.get_fold())
    };
    if preserve_instant
        && (ordinary_zone(&zone)
            || ZONEINFO
                .get(value.py())
                .is_some_and(|kind| zone.get_type().is(kind.bind(value.py()))))
    {
        // copied_fold already rejected a gap and matched the actual source
        // offset. Standard immutable zones need no second fold probe; child
        // constructors still run through build_selected's public-class branch.
        return build_selected(class, fields, &zone, fold);
    }
    copied(class, fields, &zone, fold)
}

/// Match a copied aware source to a valid occurrence in its resolved region.
fn copied_fold(
    value: &Bound<'_, PyDateTime>,
    fields: [i64; 7],
    zone: &Bound<'_, PyAny>,
) -> PyResult<i32> {
    if !(1..=9999).contains(&fields[0]) {
        return Err(crate::error_context::overflow(
            "result is outside years 1 through 9999",
        ));
    }
    let original_offset = offset_us(&utc_offset(value)?)?
        .ok_or_else(|| crate::error_context::value_error("source timezone has no usable offset"))?;
    let probe = wall_carrier(value.py(), fields, zone)?;
    let (before, after) = regional_offsets(&probe, zone)?
        .ok_or_else(|| crate::error_context::value_error("target timezone has no usable offset"))?;
    if after > before || (original_offset != before && original_offset != after) {
        return Err(crate::error_context::value_error(
            "source offset does not match a valid occurrence in the target ZoneInfo",
        ));
    }
    Ok(i32::from(
        before != original_offset && after == original_offset,
    ))
}

/// Supply the same copied-fold rule to the Python child combine boundary.
#[pyfunction]
fn _pydt_copy_fold(value: &Bound<'_, PyDateTime>, zone: &Bound<'_, PyAny>) -> PyResult<i32> {
    copied_fold(value, parts(value), zone)
}

/// Adapt a copied datetime only when the requested output is a real Pydt class.
pub(crate) fn try_pytz_copy<'py>(
    value: &Bound<'py, PyDateTime>,
    target: Option<&Bound<'py, PyAny>>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let zone = _pydt_stored_timezone(value);
    if ordinary_zone(&zone) {
        return Ok(None);
    }
    let Some(target) = target.and_then(|target| target.cast::<PyType>().ok()) else {
        return Ok(None);
    };
    let Some(base) = CLASS.get(value.py()) else {
        return Ok(None);
    };
    if !target.is_subclass(base.bind(value.py()))? {
        return Ok(None);
    }
    if !crate::localization::loaded_pytz(&zone)? {
        return Ok(None);
    }
    let resolve = REPLACE_TIMEZONE
        .get(value.py())
        .ok_or_else(|| crate::error_context::runtime("timezone resolver is unavailable"))?;
    let target_zone = resolve
        .bind(value.py())
        .call1((&zone,))
        .map_err(crate::error_context::external)?;
    _pydt_copy_datetime(target, value, Some(&target_zone), true).map(Some)
}

/// Read a real calendar date without changing child factory call shapes.
#[inline(always)]
fn calendar_date_parts(
    value: &Bound<'_, PyDate>,
    entry: &str,
    parameter: &str,
) -> PyResult<[i64; 3]> {
    if crate::interop::needs_true_year(value.get_year()) {
        crate::interop::reject_nat(value.as_any(), entry, parameter)?;
        if let Some((fields, _)) = crate::interop::timestamp_parts(value.as_any())? {
            return Ok([fields[0], fields[1], fields[2]]);
        }
    }
    Ok([
        i64::from(value.get_year()),
        i64::from(value.get_month()),
        i64::from(value.get_day()),
    ])
}

/// Supply actual date fields to the Python child combine path; never construct a date.
#[pyfunction]
fn _pydt_calendar_date(value: &Bound<'_, PyDate>) -> PyResult<[i64; 3]> {
    calendar_date_parts(value, "Pydt.combine", "date")
}

/// Copy a date's stored fields at midnight, retaining child constructor hooks.
#[pyfunction]
fn _pydt_copy_date<'py>(
    class: &Bound<'py, PyType>,
    value: &Bound<'py, PyDate>,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    let [year, month, day] = calendar_date_parts(value, "Pydt.fromdate", "date")?;
    if !CLASS.get(py).is_some_and(|base| class.is(base.bind(py))) {
        static KEYWORDS: PyOnceLock<Py<PyTuple>> = PyOnceLock::new();
        let names = KEYWORDS.get_or_try_init(py, || -> PyResult<_> {
            Ok(PyTuple::new(py, ["tzinfo"])?.unbind())
        })?;
        let args = [
            PyInt::new(py, year).into_any(),
            PyInt::new(py, month).into_any(),
            PyInt::new(py, day).into_any(),
            tz.clone(),
        ];
        let pointers = args.each_ref().map(Bound::as_ptr);
        // SAFETY: all four argument values, the callable and its single keyword
        // name outlive the public call. Preserve three positional fields and no fold.
        return unsafe {
            Bound::from_owned_ptr_or_err(
                py,
                ffi::PyObject_Vectorcall(
                    class.as_ptr(),
                    pointers.as_ptr(),
                    3,
                    names.bind(py).as_ptr(),
                ),
            )
        };
    }
    copied(class, [year, month, day, 0, 0, 0, 0], tz, 0)
}

/// Combine stored date and clock fields after the wrapper resolves the timezone.
#[pyfunction(signature=(class, date, time, zone=None, preserve_instant=false))]
fn _pydt_combine<'py>(
    class: &Bound<'py, PyType>,
    date: &Bound<'py, PyDate>,
    time: &Bound<'py, PyAny>,
    zone: Option<&Bound<'py, PyAny>>,
    preserve_instant: bool,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let (clock, fold, clock_zone) = if let Ok(clock) = time.cast::<PyTime>() {
        // SAFETY: a checked live time retains its timezone throughout this call.
        (
            [
                u32::from(clock.get_hour()),
                u32::from(clock.get_minute()),
                u32::from(clock.get_second()),
                clock.get_microsecond(),
            ],
            clock.get_fold(),
            unsafe { ffi::PyDateTime_TIME_GET_TZINFO(clock.as_ptr()) },
        )
    } else if let Ok(clock) = time.cast::<PyDateTime>() {
        crate::interop::reject_nat(clock, "Pydt.combine", "time")?;
        // Date fields are intentionally ignored: combine copies its clock
        // directly, without allocating an intermediate Python time object.
        (
            [
                u32::from(clock.get_hour()),
                u32::from(clock.get_minute()),
                u32::from(clock.get_second()),
                clock.get_microsecond(),
            ],
            clock.get_fold(),
            unsafe { ffi::PyDateTime_DATE_GET_TZINFO(clock.as_ptr()) },
        )
    } else {
        return Err(crate::error_context::type_error(
            "time must provide time or datetime fields",
        ));
    };
    let stored;
    let zone = match zone {
        Some(zone) => zone,
        None => {
            // SAFETY: the validated live clock retains this timezone pointer.
            stored = unsafe { Bound::from_borrowed_ptr(time.py(), clock_zone) };
            let fixed = unsafe {
                ffi::Py_TYPE(stored.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
            };
            if !stored.is_none()
                && !fixed
                && !ZONEINFO
                    .get(time.py())
                    .is_some_and(|kind| stored.get_type().is(kind.bind(time.py())))
            {
                return Ok(None);
            }
            &stored
        }
    };
    let [year, month, day] = calendar_date_parts(date, "Pydt.combine", "date")?;
    let fold = if preserve_instant {
        if let Ok(original) = time.cast::<PyDateTime>() {
            let original_date =
                calendar_date_parts(original.as_any().cast::<PyDate>()?, "Pydt.combine", "time")?;
            if original_date == [year, month, day] {
                copied_fold(
                    original,
                    [
                        year,
                        month,
                        day,
                        i64::from(clock[0]),
                        i64::from(clock[1]),
                        i64::from(clock[2]),
                        i64::from(clock[3]),
                    ],
                    zone,
                )?
            } else {
                i32::from(fold)
            }
        } else {
            i32::from(fold)
        }
    } else {
        i32::from(fold)
    };
    copied(
        class,
        [
            year,
            month,
            day,
            i64::from(clock[0]),
            i64::from(clock[1]),
            i64::from(clock[2]),
            i64::from(clock[3]),
        ],
        zone,
        fold,
    )
    .map(Some)
}

/// Format only stored numeric fields; Python retains timezone and class hooks.
#[pyfunction]
fn _pydt_repr_fields(value: &Bound<'_, PyDateTime>) -> String {
    let [year, month, day, hour, minute, second, microsecond] = parts(value);
    if microsecond == 0 {
        format!("{year}, {month}, {day}, {hour}, {minute}, {second}")
    } else {
        format!("{year}, {month}, {day}, {hour}, {minute}, {second}, {microsecond}")
    }
}

/// Create a builtin carrier directly; never invoke a public child constructor.
#[pyfunction]
fn _pydt_carrier<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyDateTime>> {
    // SAFETY: the checked, live datetime retains the borrowed timezone.
    let zone = unsafe {
        Bound::from_borrowed_ptr(value.py(), ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()))
    };
    PyDateTime::new_with_fold(
        value.py(),
        value.get_year(),
        value.get_month(),
        value.get_day(),
        value.get_hour(),
        value.get_minute(),
        value.get_second(),
        value.get_microsecond(),
        if zone.is_none() {
            None
        } else {
            Some(zone.cast::<PyTzInfo>()?)
        },
        value.get_fold(),
    )
}

/// Replace base Pydt fields in one native entry, sharing the stored field snapshot.
#[pyfunction]
fn _pydt_replace<'py>(
    value: &Bound<'py, PyDateTime>,
    supplied: &Bound<'py, PyTuple>,
    zone: &Bound<'py, PyAny>,
    fold: &Bound<'py, PyAny>,
    unset: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let original = parts(value);
    if let Some(result) = replace_fast(value, supplied, zone, fold, unset, original)? {
        return Ok(result);
    }
    replace_general(
        value,
        supplied,
        zone,
        fold,
        unset,
        REPLACE_TIMEZONE
            .get(value.py())
            .ok_or_else(|| {
                crate::error_context::runtime("replacement timezone resolver unavailable")
            })?
            .bind(value.py()),
        original,
    )
}

/// Replace ordinary fields without invoking Python conversion callbacks.
fn replace_fast<'py>(
    value: &Bound<'py, PyDateTime>,
    supplied: &Bound<'py, PyTuple>,
    zone: &Bound<'py, PyAny>,
    fold: &Bound<'py, PyAny>,
    unset: &Bound<'py, PyAny>,
    original: [i64; 7],
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = value.py();
    if supplied.len() != 7 {
        return Ok(None);
    }
    let mut fields = original;
    for (i, item) in supplied.iter().enumerate() {
        if item.is_none() || item.is(unset) {
            continue;
        }
        if crate::numeric::is_bool(&item) {
            return Err(crate::error_context::type_error(
                "replacement fields must be integers; boolean values are not accepted",
            ));
        }
        if !item.is_exact_instance_of::<PyInt>() {
            return Ok(None);
        }
        let mut overflow = 0;
        // SAFETY: item is a live exact int. The overflow flag avoids creating
        // or swallowing an exception before the general path validates inputs.
        let number = unsafe { ffi::PyLong_AsLongLongAndOverflow(item.as_ptr(), &mut overflow) };
        if unsafe { !ffi::PyErr_Occurred().is_null() } {
            return Err(crate::error_context::fetch(py));
        }
        if overflow != 0 || i32::try_from(number).is_err() {
            return Ok(None);
        }
        fields[i] = number;
    }
    // The public constructor reports invalid calendar years as ValueError;
    // build's OverflowError is reserved for computed results, not replacements.
    if !(1..=9999).contains(&fields[0]) {
        return Ok(None);
    }
    // SAFETY: the checked live datetime owns its timezone reference.
    let previous_zone =
        unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr())) };
    let zone = if zone.is(unset) { &previous_zone } else { zone };
    let fixed = unsafe {
        ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
    };
    if !zone.is_none()
        && !fixed
        && !ZONEINFO
            .get(py)
            .is_some_and(|class| zone.get_type().is(class.bind(py)))
    {
        return Ok(None);
    }
    let previous_fold = value.get_fold();
    let new_fold = if fold.is_none() || fold.is(unset) {
        previous_fold
    } else if fold.is_exact_instance_of::<PyInt>() {
        if fold.eq(0)? {
            false
        } else if fold.eq(1)? {
            true
        } else {
            return Ok(None);
        }
    } else if crate::numeric::is_bool(fold) {
        crate::numeric::boolean(fold)?
    } else {
        return Ok(None);
    };
    if fields == original && zone.is(&previous_zone) && new_fold == previous_fold {
        return Ok(Some(value.clone().into_any()));
    }
    copied(&value.get_type(), fields, zone, i32::from(new_fold)).map(Some)
}

/// Prepare replacement fields natively while preserving dynamic constructor hooks.
/// Index values remain Python integers until construction so timezone and fold
/// validation retain their established precedence over calendar range errors.
#[pyfunction]
fn _pydt_replace_general<'py>(
    value: &Bound<'py, PyDateTime>,
    supplied: &Bound<'py, PyTuple>,
    zone: &Bound<'py, PyAny>,
    fold: &Bound<'py, PyAny>,
    unset: &Bound<'py, PyAny>,
    resolve_timezone: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    replace_general(
        value,
        supplied,
        zone,
        fold,
        unset,
        resolve_timezone,
        parts(value),
    )
}

/// Retain dynamic index and timezone validation before constructing a replacement.
fn replace_general<'py>(
    value: &Bound<'py, PyDateTime>,
    supplied: &Bound<'py, PyTuple>,
    zone: &Bound<'py, PyAny>,
    fold: &Bound<'py, PyAny>,
    unset: &Bound<'py, PyAny>,
    resolve_timezone: &Bound<'py, PyAny>,
    original: [i64; 7],
) -> PyResult<Bound<'py, PyAny>> {
    let py = value.py();
    if supplied.len() != 7 {
        return Err(crate::error_context::type_error(
            "replacement requires seven fields",
        ));
    }
    let mut fields = original.map(|field| PyInt::new(py, field).into_any());
    let mut unchanged = true;
    for (i, item) in supplied.iter().enumerate() {
        if item.is_none() || item.is(unset) {
            continue;
        }
        if crate::numeric::is_bool(&item) {
            return Err(crate::error_context::type_error(
                "replacement fields must be integers; boolean values are not accepted",
            ));
        }
        // SAFETY: item is live and PyNumber_Index returns a new reference or
        // exception. Unset fields already own their stored Python integers.
        let field = unsafe { Bound::from_owned_ptr_or_err(py, ffi::PyNumber_Index(item.as_ptr())) }
            .map_err(crate::error_context::external)?;
        unchanged &= field.eq(original[i])?;
        fields[i] = field;
    }
    // SAFETY: the live datetime owns its stored timezone reference.
    let previous_zone =
        unsafe { Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr())) };
    let zone = if zone.is(unset) {
        previous_zone.clone()
    } else {
        resolve_timezone
            .call1((zone, "tzinfo"))
            .map_err(crate::error_context::external)?
    };
    let previous_fold = i32::from(value.get_fold());
    let new_fold = if fold.is_none() || fold.is(unset) {
        previous_fold
    } else if crate::numeric::is_bool(fold) {
        i32::from(crate::numeric::boolean(fold)?)
    } else {
        // SAFETY: fold is live; the owned integer remains valid for comparison.
        let number =
            unsafe { Bound::from_owned_ptr_or_err(py, ffi::PyNumber_Index(fold.as_ptr())) }
                .map_err(crate::error_context::external)?;
        if number.eq(0)? {
            0
        } else if number.eq(1)? {
            1
        } else {
            return Err(crate::error_context::value_error(format!(
                "fold={number} must be 0 or 1",
                number = crate::error_context::preview(&number)?
            )));
        }
    };
    if unchanged && zone.is(&previous_zone) && new_fold == previous_fold {
        return Ok(value.clone().into_any());
    }
    let class = value.get_type();
    if CLASS.get(py).is_some_and(|base| class.is(base.bind(py))) {
        // Failed construction retains the public constructor's error context.
        if let Ok(values) = (|| -> PyResult<[i32; 7]> {
            Ok([
                fields[0].extract()?,
                fields[1].extract()?,
                fields[2].extract()?,
                fields[3].extract()?,
                fields[4].extract()?,
                fields[5].extract()?,
                fields[6].extract()?,
            ])
        })() {
            let [y, m, d, h, minute, second, us] = &values;
            if (1..=9999).contains(y)
                && (1..=12).contains(m)
                && (1..=crate::calendar::days_in_month(i64::from(*y), i64::from(*m)))
                    .contains(&i64::from(*d))
                && (0..24).contains(h)
                && (0..60).contains(minute)
                && (0..60).contains(second)
                && (0..1_000_000).contains(us)
            {
                let final_zone = if zone.is_none() {
                    zone.clone()
                } else {
                    resolve_timezone
                        .call1((&zone, "tzinfo"))
                        .map_err(crate::error_context::external)?
                };
                return normalize_construct(allocate(
                    &class,
                    values.map(i64::from),
                    &final_zone,
                    new_fold,
                )?);
            }
        }
    }
    call_datetime_fields(&class, fields, &zone, new_fold)
}

/// Split epoch microseconds into calendar fields using the shared ordinal decoder.
fn from_us(us: i64) -> PyResult<[i64; 7]> {
    let ordinal = us.div_euclid(86_400_000_000) + 719_163;
    if !(1..=3_652_059).contains(&ordinal) {
        return Err(crate::error_context::overflow(
            "result is outside years 1 through 9999",
        ));
    }
    let [y, m, d] =
        crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)?;
    let t = us.rem_euclid(86_400_000_000);
    Ok([
        y,
        m,
        d,
        t / 3_600_000_000,
        t / 60_000_000 % 60,
        t / 1_000_000 % 60,
        t % 1_000_000,
    ])
}

/// Construct once for immutable standard zones; dynamic zones retain replace callbacks.
fn factory_result<'py>(
    class: &Bound<'py, PyType>,
    fields: [i64; 7],
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    // Publicly reachable private entry points must never allocate a foreign
    // datetime subclass's native payload without its own constructor.
    if !CLASS.get(py).is_some_and(|base| class.is(base.bind(py))) {
        return normalize_construct(call_datetime_fields(
            class,
            fields.map(|n| PyInt::new(py, n).into_any()),
            tz,
            0,
        )?);
    }
    // These exact immutable classes are returned unchanged by the public
    // timezone adapter. Keep names, pytz and custom tzinfo on that adapter.
    // SAFETY: configure() initialized the datetime API; tz and its type are live.
    let direct = tz.is_none()
        || unsafe { ffi::Py_TYPE(tz.as_ptr()) == ffi::Py_TYPE(ffi::PyDateTime_TimeZone_UTC()) }
        || ZONEINFO
            .get(py)
            .is_some_and(|known| tz.get_type().is(known.bind(py)));
    let zone = if direct {
        tz.clone()
    } else {
        REPLACE_TIMEZONE
            .get(py)
            .ok_or_else(|| crate::error_context::value_error("Pydt not registered"))?
            .bind(py)
            .call1((tz,))
            .map_err(crate::error_context::external)?
    };
    let fixed =
        unsafe { ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE(ffi::PyDateTime_TimeZone_UTC()) };
    let regional = ZONEINFO
        .get(py)
        .is_some_and(|class| zone.get_type().is(class.bind(py)));
    if zone.is_none() || fixed || regional {
        return normalize_construct(allocate(class, fields, &zone, 0)?);
    }
    let naive = allocate(class, fields, py.None().bind(py), 0)?;
    let kwargs = pyo3::types::PyDict::new(py);
    kwargs.set_item("tzinfo", zone)?;
    naive
        .call_method("replace", (), Some(&kwargs))
        .map_err(crate::error_context::external)
}

/// Build ordinary numeric factories directly; child classes keep the parser route.
#[pyfunction]
fn _pydt_from_seconds<'py>(
    class: &Bound<'py, PyType>,
    value: &Bound<'py, PyAny>,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    // Python's public adapter preserves the original numeric coercion policy.
    let numeric = unsafe {
        ffi::PyLong_Check(value.as_ptr()) != 0 || ffi::PyFloat_Check(value.as_ptr()) != 0
    };
    if !numeric {
        return crate::parser::objects::convert(py, value, Some(class.as_any()))
            .map(|v| v.into_bound(py));
    }
    let fields = (|| -> PyResult<_> {
        let micros = crate::parser::objects::numeric_microseconds(value)?;
        crate::parser::objects::microsecond_fields(micros)
    })()
    .map_err(|error| crate::parser::entry_error(py, "Pydt.fromseconds", "seconds", value, error))?;
    factory_result(class, fields, tz)
}

/// Create an epoch-wall-clock value without floating point or a Python timedelta.
#[pyfunction]
fn _pydt_from_us<'py>(
    class: &Bound<'py, PyType>,
    us: WideInteger,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    build(class, from_us(us.0)?, tz, 0)
}

/// Compute native epoch microseconds after the public bool conversion is complete.
fn epoch_microseconds(value: &Bound<'_, PyDateTime>, utc: bool) -> PyResult<i64> {
    let f = parts(value);
    let mut us = (crate::calendar::ordinal(f[0], f[1], f[2]) - 719_163) * 86_400_000_000
        + f[3] * 3_600_000_000
        + f[4] * 60_000_000
        + f[5] * 1_000_000
        + f[6];
    if utc {
        if let Some(offset) = offset_us(&utc_offset(value)?)? {
            us -= offset;
        }
    }
    Ok(us)
}

/// Return exact epoch microseconds, consulting timezone callbacks only when requested.
#[pyfunction(signature=(value, utc=Truth(false)), text_signature="(value, utc=False)")]
fn _pydt_to_us(value: &Bound<'_, PyDateTime>, utc: Truth) -> PyResult<i64> {
    epoch_microseconds(value, utc.0)
}

/// Compare with one clock reading, keeping ordinary timezone rules in native code.
/// Dynamic offsets are read once; queries never require their fromutc protocol.
#[pyfunction]
fn _pydt_compare_now(
    value: &Bound<'_, PyDateTime>,
    clock: &Bound<'_, PyAny>,
    future: bool,
) -> PyResult<bool> {
    let py = value.py();
    let zone = _pydt_stored_timezone(value);
    let fixed = zone.is_none()
        // SAFETY: registration initialized the datetime API and its UTC singleton.
        || unsafe {
            ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
        };
    let region = ZONEINFO
        .get(py)
        .is_some_and(|class| zone.get_type().is(class.bind(py)));
    let order = if fixed || region {
        let current = clock
            .call1((&zone,))
            .map_err(crate::error_context::external)?;
        let current = current.cast::<PyDateTime>()?;
        if fixed || value.get_fold() == current.get_fold() {
            // For an existing ZoneInfo wall time, selecting the same occurrence
            // preserves wall ordering. Only opposite folds can reverse its sign.
            parts(value).cmp(&parts(current))
        } else {
            let wall = epoch_microseconds(value, false)?;
            let now_wall = epoch_microseconds(current, false)?;
            if (wall - now_wall).abs() > 172_800_000_000 {
                // Every legal UTC offset is inside +/-24h, so larger wall gaps
                // have the same sign without consuming either regional offset.
                wall.cmp(&now_wall)
            } else {
                let carrier = _pydt_carrier(value)?;
                let offset = offset_us(&utc_offset(&carrier)?)?.unwrap_or(0);
                let now_offset = offset_us(&utc_offset(current)?)?.unwrap_or(0);
                (wall - offset).cmp(&(now_wall - now_offset))
            }
        }
    } else {
        let offset = offset_us(&utc_offset(value)?)?;
        let current = match offset {
            Some(_) => {
                // SAFETY: the datetime API retains this immutable UTC singleton.
                let utc = unsafe { Borrowed::from_ptr(py, (*ffi::PyDateTimeAPI()).TimeZone_UTC) };
                clock.call1((utc,))
            }
            None => clock.call0(),
        }
        .map_err(crate::error_context::external)?;
        let current = current.cast::<PyDateTime>()?;
        let value_us = epoch_microseconds(value, false)? - offset.unwrap_or(0);
        value_us.cmp(&epoch_microseconds(current, false)?)
    };
    Ok(if future { order.is_gt() } else { order.is_lt() })
}

/// Return floating-point seconds without an intermediate Python integer.
#[pyfunction(signature=(value, utc=Truth(false)), text_signature="(value, utc=False)")]
fn _pydt_to_seconds(value: &Bound<'_, PyDateTime>, utc: Truth) -> PyResult<f64> {
    epoch_microseconds(value, utc.0).map(|us| us as f64 * 1e-6)
}

/// Query immutable default month/weekday vocabulary, without Python Configs.
#[pyfunction]
#[pyo3(name = "_pydt_lookup")]
#[inline]
pub(crate) fn lookup_selector(py: Python<'_>, token: &str, weekday: bool) -> PyResult<i32> {
    let value = lookup_default_name(token, weekday);
    if value < 0 {
        Err(crate::error_context::value_error(format!(
            "unknown {} name {}",
            if weekday { "weekday" } else { "month" },
            crate::error_context::text_preview(py, token)?,
        )))
    } else {
        Ok(value)
    }
}

/// Let an internal caller try a name without using exceptions as control flow.
#[pyfunction]
fn _pydt_lookup_optional(token: &str, weekday: bool) -> Option<i32> {
    let found = lookup_default_name(token, weekday);
    (found >= 0).then_some(found)
}

/// Share the immutable vocabulary lookup without creating an exception for a miss.
fn with_default_token<R>(token: &str, lookup: impl FnOnce(&[u32]) -> R) -> R {
    // Common names fit in a small stack buffer; longer names retain the same
    // complete Unicode lookup without truncation or a new token-length limit.
    let mut inline = [0u32; 16];
    let owned;
    let token = if token.len() <= inline.len() {
        let mut count = 0;
        for character in token.chars() {
            inline[count] = u32::from(character);
            count += 1;
        }
        &inline[..count]
    } else {
        owned = token.chars().map(u32::from).collect::<Vec<_>>();
        owned.as_slice()
    };
    lookup(token)
}

/// Query one default name using shared inline storage for common words.
fn lookup_default_name(token: &str, weekday: bool) -> i32 {
    let rule = if weekday {
        crate::parser::fields::Rule::Weekday
    } else {
        crate::parser::fields::Rule::Month
    };
    with_default_token(token, |token| {
        crate::parser::config::default_lookup(rule, token)
    })
}

/// Prepare a boundary name once, keeping month-before-weekday precedence.
pub(crate) fn boundary_names(token: &str) -> (i32, i32) {
    with_default_token(token, |token| {
        let month =
            crate::parser::config::default_lookup(crate::parser::fields::Rule::Month, token);
        (
            month,
            if month >= 1 {
                -1
            } else {
                crate::parser::config::default_lookup(crate::parser::fields::Rule::Weekday, token)
            },
        )
    })
}

/// Match a real Unicode name or integer selector against stored calendar fields.
/// Native dispatch avoids a second Python type test; fake displayed classes
/// never authorize name handling or change the existing integer protocol.
#[pyfunction]
fn _pydt_name_matches(
    value: &Bound<'_, PyDateTime>,
    token: &Bound<'_, PyAny>,
    weekday: bool,
) -> PyResult<bool> {
    // SAFETY: the live Python object is checked by its real Unicode type flag.
    if unsafe { ffi::PyUnicode_Check(token.as_ptr()) } == 0 {
        return _pydt_matches(value, if weekday { 4 } else { 3 }, token.extract()?);
    }
    let token = token.cast::<pyo3::types::PyString>()?.to_str()?;
    let actual = if weekday {
        (crate::calendar::ordinal(
            i64::from(value.get_year()),
            i64::from(value.get_month()),
            i64::from(value.get_day()),
        ) - 1)
            % 7
    } else {
        i64::from(value.get_month())
    };
    Ok(actual == i64::from(lookup_selector(value.py(), token, weekday)?))
}

/// Read one ISO calendar field without allocating the complete Python result.
#[pyfunction]
fn _pydt_iso(value: &Bound<'_, PyDateTime>, year_field: bool) -> i64 {
    let mut year = i64::from(value.get_year());
    let jan1 = crate::calendar::ordinal(year, 1, 1);
    let ordinal = crate::calendar::ordinal(
        year,
        i64::from(value.get_month()),
        i64::from(value.get_day()),
    );
    let weekday = (ordinal - 1) % 7;
    let mut week = (ordinal - jan1 + 1 - weekday + 9) / 7;
    let long_year = |y| {
        let day = (crate::calendar::ordinal(y, 1, 1) - 1) % 7;
        day == 3 || (day == 2 && crate::calendar::leap(y))
    };
    if week == 0 {
        year -= 1;
        week = if long_year(year) { 53 } else { 52 };
    } else if week == 53 && !long_year(year) {
        year += 1;
        week = 1;
    }
    if year_field { year } else { week }
}

/// Reuse NumPy's checked scalar decoder and Parser's established constructor shape.
#[pyfunction]
fn _pydt_from_numpy<'py>(
    py: Python<'py>,
    class: &Bound<'py, PyAny>,
    value: &Bound<'py, PyAny>,
) -> PyResult<Py<PyAny>> {
    let Some(micros) = crate::numpy_scalar::datetime_microseconds(value).map_err(|error| {
        crate::parser::entry_error(py, "Pydt.fromdatetime64", "dt64", value, error)
    })?
    else {
        return Err(crate::error_context::type_error(format!(
            "Pydt.fromdatetime64(): dt64 must be numpy.datetime64; got {}",
            crate::error_context::preview(value)?
        )));
    };
    crate::parser::objects::from_microseconds(py, micros, Some(class)).map_err(|error| {
        crate::parser::entry_error(py, "Pydt.fromdatetime64", "dt64", value, error)
    })
}

/// Apply an explicit timezone without adding arguments to the ordinary NumPy entry.
#[pyfunction]
fn _pydt_from_numpy_zoned<'py>(
    py: Python<'py>,
    class: &Bound<'py, PyType>,
    value: &Bound<'py, PyAny>,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let Some(micros) = crate::numpy_scalar::datetime_microseconds(value).map_err(|error| {
        crate::parser::entry_error(py, "Pydt.fromdatetime64", "dt64", value, error)
    })?
    else {
        return Err(crate::error_context::type_error(format!(
            "Pydt.fromdatetime64(): dt64 must be numpy.datetime64; got {}",
            crate::error_context::preview(value)?
        )));
    };
    let fields = crate::parser::objects::microsecond_fields(micros).map_err(|error| {
        crate::parser::entry_error(py, "Pydt.fromdatetime64", "dt64", value, error)
    })?;
    factory_result(class, fields, tz)
}

/// Read the year position directly for the readonly Python property.
#[pyfunction]
fn _pydt_day_of_year(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    let date = value.cast::<PyDateTime>().map_err(|error| {
        crate::error_context::argument(
            value.py(),
            error.into(),
            "Pydt.day_of_year",
            "arguments",
            value,
        )
    })?;
    let year = i64::from(date.get_year());
    Ok(
        crate::calendar::ordinal(year, i64::from(date.get_month()), i64::from(date.get_day()))
            - crate::calendar::ordinal(year, 1, 1)
            + 1,
    )
}

/// Read month capacity without a Python property function frame.
#[pyfunction]
fn _pydt_days_in_month(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    let date = value.cast::<PyDateTime>().map_err(|error| {
        crate::error_context::argument(
            value.py(),
            error.into(),
            "Pydt.days_in_month",
            "arguments",
            value,
        )
    })?;
    Ok(crate::calendar::days_in_month(
        i64::from(date.get_year()),
        i64::from(date.get_month()),
    ))
}

/// Read leap status without a Python property function frame.
#[pyfunction]
fn _pydt_is_leap_year(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    let date = value.cast::<PyDateTime>().map_err(|error| {
        crate::error_context::argument(
            value.py(),
            error.into(),
            "Pydt.is_leap_year",
            "arguments",
            value,
        )
    })?;
    Ok(crate::calendar::leap(i64::from(date.get_year())))
}

/// Read calendar facts from the same Gregorian helpers used by Delta and Parser.
#[pyfunction]
fn _pydt_calendar(value: &Bound<'_, PyDateTime>, query: u8) -> PyResult<i64> {
    let f = parts(value);
    let [y, m, d, _, _, _, _] = f;
    // Simple facts need no ordinal lookup. Compute date positions only in the
    // branches that use them, rather than before selecting the requested fact.
    let start = || crate::calendar::ordinal(y, 1, 1);
    let qmonth = (m - 1) / 3 * 3 + 1;
    let qstart = || crate::calendar::ordinal(y, qmonth, 1);
    let ordinal = || crate::calendar::ordinal(y, m, d);
    Ok(match query {
        0 => (m - 1) / 3 + 1,
        1 => 365 + i64::from(crate::calendar::leap(y)),
        2 => start() - 1,
        3 => ordinal() - start() + 1,
        4 => (qmonth..qmonth + 3)
            .map(|month| crate::calendar::days_in_month(y, month))
            .sum(),
        5 => qstart() - start(),
        6 => ordinal() - qstart() + 1,
        7 => crate::calendar::days_in_month(y, m),
        8 => crate::calendar::ordinal(y, m, 1) - start(),
        9 => d,
        10 => i64::from(crate::calendar::leap(y)),
        11 => {
            let jan1 = (start() - 1) % 7;
            i64::from(jan1 == 3 || (jan1 == 2 && crate::calendar::leap(y)))
        }
        12 => (ordinal() - 1) % 7,
        _ => {
            return Err(crate::error_context::runtime("unknown Pydt calendar query"));
        }
    })
}

/// Keep short date movements on fields without adding work to ordinal-validated shifts.
#[inline(always)]
fn shifted_days(fields: [i64; 3], days: i64, message: &'static str) -> PyResult<[i64; 3]> {
    let [y, m, d] = fields;
    if (-27..=27).contains(&days) {
        let result = crate::calendar::shift_small_days(y, m, d, days)
            .map_err(crate::error_context::overflow)?;
        if !(1..=9999).contains(&result[0]) {
            return Err(crate::error_context::overflow(message));
        }
        Ok(result)
    } else {
        let ordinal = crate::calendar::ordinal(y, m, d)
            .checked_add(days)
            .ok_or_else(|| crate::error_context::overflow(message))?;
        if !(1..=3_652_059).contains(&ordinal) {
            return Err(crate::error_context::overflow(message));
        }
        // The validated ordinal already proves the final year range.
        crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)
    }
}

/// Parse native fields, then preserve the existing final child fromdatetime hook.
#[pyfunction]
#[pyo3(signature=(class,text,format,cfg=None))]
fn _pydt_strptime<'py>(
    class: &Bound<'py, PyType>,
    text: &Bound<'py, PyAny>,
    format: PyRef<'_, crate::parser::formatted::Format>,
    cfg: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = text.py();
    let converted;
    let text = if text.is_exact_instance_of::<pyo3::types::PyString>() {
        text.cast::<pyo3::types::PyString>()?
    } else if text.is_instance_of::<pyo3::types::PyString>() {
        converted = text.str().map_err(crate::error_context::external)?;
        &converted
    } else {
        return Err(crate::error_context::expected_type(
            text,
            "Pydt.strptime",
            "dtstr",
            "a string",
        ));
    };
    let context = crate::parser::formatted::Context::prepare(&format, cfg)?;
    let parsed = crate::parser::formatted::read(&context, text)?;
    let fields = parsed.fields;
    if !(1..=9999).contains(&fields[0]) {
        return Err(crate::error_context::value_error(format!(
            "year {} is out of range",
            fields[0]
        )));
    }
    let zone = crate::epoch::zone_object(py, &parsed.zone)?;
    let zone = zone.bind(py);
    if CLASS.get(py).is_some_and(|base| class.is(base.bind(py))) {
        return normalize_construct(allocate(class, fields, zone, 0)?);
    }
    // A builtin datetime is the required input to the real child's fromdatetime
    // hook; bypassing it would change already approved callback semantics.
    let carrier = PyDateTime::new(
        py,
        fields[0] as i32,
        fields[1] as u8,
        fields[2] as u8,
        fields[3] as u8,
        fields[4] as u8,
        fields[5] as u8,
        fields[6] as u32,
        if zone.is_none() {
            None
        } else {
            Some(zone.cast::<PyTzInfo>()?)
        },
    )?;
    class
        .getattr("fromdatetime")
        .map_err(crate::error_context::external)?
        .call1((carrier,))
        .map_err(crate::error_context::external)
}

/// Read one actual DST duration, retaining the callback's legal return object.
fn daylight<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<(Bound<'py, PyAny>, i64)> {
    let zone = _pydt_stored_timezone(value);
    if zone.is_none() {
        return Ok((value.py().None().into_bound(value.py()), -1));
    }
    let adjustment = zone
        .call_method1(pyo3::intern!(value.py(), "dst"), (value,))
        .map_err(crate::error_context::external)?;
    if adjustment.is_none() {
        return Ok((adjustment, -1));
    }
    let duration = adjustment
        .cast::<PyDelta>()
        .map_err(|_| crate::error_context::type_error("dst() must return None or timedelta"))?;
    let nanos = if unsafe { ffi::PyDelta_CheckExact(adjustment.as_ptr()) != 0 } {
        None
    } else {
        crate::interop::duration_nanoseconds(&adjustment)?
    };
    let nanos = nanos.unwrap_or_else(|| {
        (i128::from(duration.get_days()) * 86_400_000_000
            + i128::from(duration.get_seconds()) * 1_000_000
            + i128::from(duration.get_microseconds()))
            * 1000
    });
    if !(-86_400_000_000_000 < nanos && nanos < 86_400_000_000_000) {
        return Err(crate::error_context::value_error(
            "dst() must be strictly between -24 and +24 hours",
        ));
    }
    Ok((adjustment, i64::from(nanos != 0)))
}

/// Return the same legal duration after checking its actual value once.
#[pyfunction]
fn _pydt_dst<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyAny>> {
    daylight(value).map(|(adjustment, _)| adjustment)
}

/// Ignore user-defined truthiness of timedelta subclasses.
#[pyfunction]
fn _pydt_is_dst(value: &Bound<'_, PyDateTime>) -> PyResult<bool> {
    daylight(value).map(|(_, marker)| marker > 0)
}

/// Assemble the nine standard fields directly, calling DST only for local output.
fn tuple_fields(value: &Bound<'_, PyDateTime>, utc: bool) -> PyResult<[i64; 9]> {
    let zone = _pydt_stored_timezone(value);
    let [y, m, d, h, minute, second, _] = if utc && !zone.is_none() {
        from_us(epoch_microseconds(value, true)?)?
    } else {
        parts(value)
    };
    let ordinal = crate::calendar::ordinal(y, m, d);
    Ok([
        y,
        m,
        d,
        h,
        minute,
        second,
        (ordinal - 1).rem_euclid(7),
        ordinal - crate::calendar::ordinal(y, 1, 1) + 1,
        if utc { 0 } else { daylight(value)?.1 },
    ])
}

/// Build the standard tuple without reading datetime's foreign carrier duration.
#[pyfunction]
fn _pydt_timetuple<'py>(value: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyAny>> {
    static STRUCT_TIME: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
    let py = value.py();
    let fields = tuple_fields(value, false)?;
    let constructor = crate::python_cache::get_or_prepare(&STRUCT_TIME, py, || {
        Ok::<_, PyErr>(
            py.import("time")?
                .getattr("struct_time")
                .map_err(crate::error_context::external)?
                .unbind(),
        )
    })?;
    constructor
        .bind(py)
        .call1((PyTuple::new(py, fields)?,))
        .map_err(crate::error_context::external)
}

/// Assemble a calendar dictionary without an intermediate time tuple.
#[pyfunction]
fn _pydt_timedict<'py>(
    value: &Bound<'py, PyDateTime>,
    utc: bool,
) -> PyResult<Bound<'py, pyo3::types::PyDict>> {
    let py = value.py();
    let fields = tuple_fields(value, utc)?;
    let dictionary = pyo3::types::PyDict::new(py);
    static KEY_OBJECTS: PyOnceLock<Py<PyTuple>> = PyOnceLock::new();
    const KEYS: [&str; 9] = [
        "tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec", "tm_wday", "tm_yday",
        "tm_isdst",
    ];
    let keys = KEY_OBJECTS
        .get_or_try_init(py, || -> PyResult<_> {
            Ok(PyTuple::new(py, KEYS)?.unbind())
        })?
        .bind(py);
    for (key, field) in keys.iter().zip(fields) {
        dictionary.set_item(key, field)?;
    }
    Ok(dictionary)
}

/// Shift calendar months/days, clamping the final day only after selecting the month.
#[pyfunction(signature=(value, month_delta=Integer(0), day_delta=Integer(0), month=None, day=None))]
fn _pydt_shift<'py>(
    value: &Bound<'py, PyDateTime>,
    month_delta: Integer,
    day_delta: Integer,
    month: Option<FieldIndex>,
    day: Option<FieldIndex>,
) -> PyResult<Bound<'py, PyAny>> {
    let month = optional_field(month, 1, 12, "month")?;
    let day = optional_field(day, 1, 31, "day")?;
    let mut f = parts(value);
    let date = crate::calendar::move_date(
        [f[0], f[1], f[2]],
        i128::from(month_delta.0),
        i128::from(day_delta.0),
        month,
        day,
    )
    .map_err(crate::error_context::overflow)?;
    if !(1..=9999).contains(&date[0]) {
        return Err(crate::error_context::overflow(
            "result is outside years 1 through 9999",
        ));
    }
    f[..3].copy_from_slice(&date);
    selected_result(value, f)
}

/// Resolve an optional field once, before native calendar arithmetic.
fn optional_field(
    value: Option<FieldIndex>,
    minimum: i64,
    maximum: i64,
    name: &str,
) -> PyResult<Option<i64>> {
    value
        .map(|value| {
            let number = value.0;
            if !(minimum..=maximum).contains(&number) {
                return Err(crate::error_context::value_error(format!(
                    "{name} must be from {minimum} through {maximum}, inclusive, or None; got {number}"
                )));
            }
            Ok(number)
        })
        .transpose()
}

/// Resolve a stored name or integer selector; only None preserves the field.
fn selector(value: Option<&Bound<'_, PyAny>>, weekday: bool) -> PyResult<i64> {
    let Some(value) = value.filter(|v| !v.is_none()) else {
        return Ok(-1);
    };
    let name = if weekday { "weekday" } else { "month" };
    let n = if value.is_instance_of::<pyo3::types::PyString>() {
        i64::from(lookup_selector(
            value.py(),
            value.extract::<&str>()?,
            weekday,
        )?)
    } else if unsafe { ffi::PyIndex_Check(value.as_ptr()) != 0 } {
        crate::numeric::index_i64(value)?
    } else {
        return Err(crate::error_context::argument(
            value.py(),
            crate::error_context::type_error("must be an integer, a stored name, or None"),
            "",
            name,
            value,
        ));
    };
    let (low, high) = if weekday { (0, 6) } else { (1, 12) };
    if (low..=high).contains(&n) {
        Ok(n)
    } else {
        Err(crate::error_context::value_error(format!(
            "{name}={n} must be from {low} through {high}, inclusive; use None to retain it"
        )))
    }
}

/// Apply a year, quarter, month, week or day movement in one native operation.
#[pyfunction(signature=(value, kind, offset, selection=None, day=None))]
fn _pydt_move<'py>(
    value: &Bound<'py, PyDateTime>,
    kind: u8,
    offset: Integer,
    selection: Option<&Bound<'py, PyAny>>,
    day: Option<FieldIndex>,
) -> PyResult<Bound<'py, PyAny>> {
    let offset = offset.0;
    let mut month = -1;
    let mut months = 0;
    let mut days = 0;
    let overflow = || crate::error_context::overflow("Pydt calendar offset overflow");
    match kind {
        0 => {
            months = offset.checked_mul(12).ok_or_else(overflow)?;
            month = selector(selection, false)?;
        }
        1 => {
            months = offset.checked_mul(3).ok_or_else(overflow)?;
            let part = optional_field(
                selection
                    .filter(|v| !v.is_none())
                    .map(|v| v.extract::<FieldIndex>())
                    .transpose()?,
                1,
                3,
                "month within quarter",
            )?
            .unwrap_or(-1);
            if part > 0 {
                month = (i64::from(value.get_month()) - 1) / 3 * 3 + part.min(3);
            }
        }
        2 => months = offset,
        3 => {
            days = offset.checked_mul(7).ok_or_else(overflow)?;
            let target = selector(selection, true)?;
            if target >= 0 {
                days = days
                    .checked_add(target - _pydt_calendar(value, 12)?)
                    .ok_or_else(overflow)?;
            }
        }
        4 => days = offset,
        _ => {
            return Err(crate::error_context::runtime("unknown calendar movement"));
        }
    }
    // All supplied selectors are already checked. An unchanged movement needs
    // neither date-field work nor another shared shift call.
    if months == 0 && days == 0 && month < 0 && day.is_none() {
        return Ok(value.clone().into_any());
    }
    _pydt_shift(
        value,
        Integer(months),
        Integer(days),
        (month >= 0).then_some(FieldIndex(month)),
        day,
    )
}

/// Set optional fields and clamp only a valid requested day to the target month.
#[pyfunction(signature=(value, year=None, month=None, day=None, hour=None, minute=None, second=None, microsecond=None))]
#[expect(
    clippy::too_many_arguments,
    reason = "Mirrors the public date/time field interface"
)]
fn _pydt_adjust<'py>(
    value: &Bound<'py, PyDateTime>,
    year: Option<FieldIndex>,
    month: Option<FieldIndex>,
    day: Option<FieldIndex>,
    hour: Option<FieldIndex>,
    minute: Option<FieldIndex>,
    second: Option<FieldIndex>,
    microsecond: Option<FieldIndex>,
) -> PyResult<Bound<'py, PyAny>> {
    let mut fields = parts(value);
    let requested = [year, month, day, hour, minute, second, microsecond];
    let names = [
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
        "microsecond",
    ];
    let maximum = [9999, 12, 31, 23, 59, 59, 999999];
    for (index, value) in requested.into_iter().enumerate() {
        if let Some(number) =
            optional_field(value, i64::from(index < 3), maximum[index], names[index])?
        {
            fields[index] = number;
        }
    }
    fields[2] = fields[2].min(crate::calendar::days_in_month(fields[0], fields[1]));
    selected_result(value, fields)
}

/// Compute a period boundary and optionally its clock boundary without chained calls.
fn boundary_fields<'py>(
    value: &Bound<'py, PyDateTime>,
    unit: &str,
    end: bool,
    clock: bool,
) -> PyResult<[i64; 7]> {
    let mut f = parts(value);
    let mut days = 0;
    match unit {
        "Y" => {
            f[1] = if end { 12 } else { 1 };
            f[2] = if end { 31 } else { 1 };
        }
        "Q" => {
            f[1] = (f[1] - 1) / 3 * 3 + if end { 3 } else { 1 };
            f[2] = if end {
                crate::calendar::days_in_month(f[0], f[1])
            } else {
                1
            };
        }
        "M" => {
            f[2] = if end {
                crate::calendar::days_in_month(f[0], f[1])
            } else {
                1
            }
        }
        "W" => days = if end { 6 } else { 0 } - _pydt_calendar(value, 12)?,
        "D" | "h" | "m" | "min" | "s" | "ms" | "us" | "ns" if clock => {}
        _ => {
            let (month, weekday_name) = boundary_names(unit);
            if month >= 1 {
                f[1] = i64::from(month);
                f[2] = if end {
                    crate::calendar::days_in_month(f[0], f[1])
                } else {
                    1
                };
            } else if clock {
                let weekday = weekday_name;
                if weekday < 0 {
                    return Err(crate::error_context::value_error(
                        "unknown period, month or weekday name",
                    ));
                }
                days = i64::from(weekday) - _pydt_calendar(value, 12)?;
            } else {
                return Err(crate::error_context::value_error(
                    "unknown period or month name",
                ));
            }
        }
    }
    if days != 0 {
        let date = shifted_days(
            [f[0], f[1], f[2]],
            days,
            "Pydt boundary outside years 1..9999",
        )?;
        f[..3].copy_from_slice(&date);
    }
    if clock {
        let first = match unit {
            "h" => 4,
            "m" | "min" => 5,
            "s" | "ms" => 6,
            "us" | "ns" => 7,
            _ => 3,
        };
        let last = [23, 59, 59, 999999];
        for index in first..7 {
            f[index] = if end { last[index - 3] } else { 0 };
        }
        if unit == "ms" {
            f[6] = (parts(value)[6] / 1000) * 1000 + if end { 999 } else { 0 };
        }
    }
    Ok(f)
}

/// Build the same native period definition used by the boundary predicates.
#[pyfunction]
fn _pydt_boundary<'py>(
    value: &Bound<'py, PyDateTime>,
    unit: &str,
    end: bool,
    clock: bool,
) -> PyResult<Bound<'py, PyAny>> {
    if clock && matches!(unit, "us" | "ns") {
        return Ok(value.clone().into_any());
    }
    let fields = boundary_fields(value, unit, end, clock)?;
    if !clock {
        let zone = _pydt_stored_timezone(value);
        if ordinary_zone(&zone) {
            return result(value, fields, false);
        }
        let (mut selected, mut fold) = calendar_target::<false>(value, fields, &zone)?;
        if selected[..3] != fields[..3] {
            let start = wall_us([fields[0], fields[1], fields[2], 0, 0, 0, 0]);
            (selected, fold) = period_target(
                value,
                fields,
                start,
                start + 86_400_000_000 - 1,
                selected[..3] > fields[..3],
                false,
            )?;
        }
        if selected == parts(value) && fold == i32::from(value.get_fold()) {
            return Ok(value.clone().into_any());
        }
        return build_selected(&value.get_type(), selected, &zone, fold);
    }
    let zone = _pydt_stored_timezone(value);
    if ordinary_zone(&zone) {
        return result(value, fields, false);
    }
    let start = boundary_fields(value, unit, false, true)?;
    let finish = boundary_fields(value, unit, true, true)?;
    let (fields, fold) = period_target(
        value,
        fields,
        wall_us(start),
        wall_us(finish),
        end,
        matches!(unit, "h" | "m" | "min" | "s" | "ms"),
    )?;
    if fields == parts(value) && fold == i32::from(value.get_fold()) {
        return Ok(value.clone().into_any());
    }
    build_selected(&value.get_type(), fields, &zone, fold)
}

/// Inspect native fields directly; regional boundaries additionally confirm validity.
#[pyfunction]
fn _pydt_is_boundary(
    value: &Bound<'_, PyDateTime>,
    unit: &str,
    end: bool,
    clock: bool,
) -> PyResult<bool> {
    // Classify once. The same compact kind drives validation, clock precision
    // and the final calendar predicate; names are looked up only on this miss.
    let (kind, named_month, named_weekday) = match unit {
        "Y" => (0, 0, -1),
        "Q" => (1, 0, -1),
        "M" => (2, 0, -1),
        "W" => (3, 0, -1),
        "D" => (4, 0, -1),
        "h" => (5, 0, -1),
        "m" | "min" => (6, 0, -1),
        "s" => (7, 0, -1),
        "ms" => (8, 0, -1),
        "us" | "ns" => (9, 0, -1),
        _ => {
            let (month, weekday) = boundary_names(unit);
            if month >= 1 {
                (10, month, weekday)
            } else if clock && weekday >= 0 {
                (11, month, weekday)
            } else {
                return Err(crate::error_context::value_error(
                    "unknown or empty period, month or weekday name",
                ));
            }
        }
    };
    if !clock && (4..=9).contains(&kind) {
        return Err(crate::error_context::value_error(
            "first/last queries require a calendar period or month name",
        ));
    }
    if clock && kind == 9 {
        return Ok(true);
    }
    if clock {
        // SAFETY: the checked live datetime retains this timezone pointer.
        let timezone = unsafe { ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()) };
        if timezone != unsafe { ffi::Py_None() } {
            let zone = _pydt_stored_timezone(value);
            if !ordinary_zone(&zone) {
                return regional_is_boundary(value, unit, end, kind, named_month, named_weekday);
            }
        }
        let us = value.get_microsecond();
        let matches = match kind {
            9 => return Ok(true),
            8 => return Ok(us % 1000 == if end { 999 } else { 0 }),
            7 => us == if end { 999_999 } else { 0 },
            6 => {
                us == if end { 999_999 } else { 0 }
                    && value.get_second() == if end { 59 } else { 0 }
            }
            5 => {
                us == if end { 999_999 } else { 0 }
                    && value.get_second() == if end { 59 } else { 0 }
                    && value.get_minute() == if end { 59 } else { 0 }
            }
            _ => {
                us == if end { 999_999 } else { 0 }
                    && value.get_second() == if end { 59 } else { 0 }
                    && value.get_minute() == if end { 59 } else { 0 }
                    && value.get_hour() == if end { 23 } else { 0 }
            }
        };
        if !matches {
            return Ok(false);
        }
        if (4..=7).contains(&kind) {
            return Ok(true);
        }
    }
    Ok(calendar_boundary_matches(
        value,
        kind,
        named_month,
        named_weekday,
        end,
    ))
}

/// Inspect only the calendar fields needed by the already validated period.
#[inline(always)]
fn calendar_boundary_matches(
    value: &Bound<'_, PyDateTime>,
    kind: i32,
    named_month: i32,
    named_weekday: i32,
    end: bool,
) -> bool {
    let month_edge = || {
        i64::from(value.get_day())
            == if end {
                crate::calendar::days_in_month(
                    i64::from(value.get_year()),
                    i64::from(value.get_month()),
                )
            } else {
                1
            }
    };
    let weekday = || {
        (crate::calendar::ordinal(
            i64::from(value.get_year()),
            i64::from(value.get_month()),
            i64::from(value.get_day()),
        ) - 1)
            .rem_euclid(7)
    };
    match kind {
        0 => {
            value.get_month() == if end { 12 } else { 1 }
                && value.get_day() == if end { 31 } else { 1 }
        }
        1 => (value.get_month() - 1) % 3 == if end { 2 } else { 0 } && month_edge(),
        2 => month_edge(),
        3 => weekday() == if end { 6 } else { 0 },
        10 => i32::from(value.get_month()) == named_month && month_edge(),
        11 => weekday() == i64::from(named_weekday),
        _ => false,
    }
}

/// Regional boundary probes keep their arrays and callback frame off ordinary queries.
#[inline(never)]
fn regional_is_boundary(
    value: &Bound<'_, PyDateTime>,
    unit: &str,
    end: bool,
    kind: i32,
    named_month: i32,
    named_weekday: i32,
) -> PyResult<bool> {
    if kind == 11 && _pydt_calendar(value, 12)? != i64::from(named_weekday)
        || kind == 10 && i32::from(value.get_month()) != named_month
    {
        return Ok(false);
    }
    // These native calendar helpers have no user callbacks. A boundary beyond
    // datetime's range cannot equal the checked current value; it is a nonmatch.
    let boundary = |end| -> PyResult<Option<[i64; 7]>> {
        match boundary_fields(value, unit, end, true) {
            Ok(fields) => Ok(Some(fields)),
            Err(error) if error.is_instance_of::<PyOverflowError>(value.py()) => Ok(None),
            Err(error) => Err(error),
        }
    };
    let (Some(first), Some(last)) = (boundary(false)?, boundary(true)?) else {
        return Ok(false);
    };
    let selected = if end { last } else { first };
    let Some((fields, fold)) = optional_period_target(
        value,
        selected,
        wall_us(first),
        wall_us(last),
        end,
        (5..=8).contains(&kind),
    )?
    else {
        return Ok(false);
    };
    if parts(value) != fields {
        return Ok(false);
    }
    if fields == first && first == last || fold == i32::from(value.get_fold()) {
        return Ok(true);
    }
    // An unused fold flag is not a different instant. Only compare offsets
    // after the actual boundary fields match and the fold flags differ.
    let zone = _pydt_stored_timezone(value);
    let candidate = builtin_with_fold(value, fold != 0)?;
    Ok(offset_us(&utc_offset(value)?)? == offset_us(&utc_offset(&candidate)?)? && !zone.is_none())
}

/// Calendar-aligned starts; month names repeat annually, weekday names weekly.
#[derive(Clone, Copy)]
struct SnapPeriod {
    months: i64,
    step: i64,
    width_months: i64,
    width: i64,
}

fn shift_snap(start: i64, period: SnapPeriod, direction: i64) -> PyResult<i64> {
    if period.months != 0 {
        let [year, month, _] =
            crate::calendar::from_ordinal(start.div_euclid(86_400_000_000) + 719_163)
                .map_err(crate::error_context::overflow)?;
        let absolute = year * 12 + month - 1 + direction * period.months;
        Ok(
            (crate::calendar::ordinal(absolute.div_euclid(12), absolute.rem_euclid(12) + 1, 1)
                - 719_163)
                * 86_400_000_000,
        )
    } else {
        start
            .checked_add(direction * period.step)
            .ok_or_else(|| crate::error_context::overflow("period arithmetic overflow"))
    }
}

fn snap_period_end(start: i64, period: SnapPeriod) -> PyResult<i64> {
    if period.width_months != 0 {
        shift_snap(
            start,
            SnapPeriod {
                months: period.width_months,
                ..period
            },
            1,
        )
        .map(|end| end - 1)
    } else {
        Ok(start + period.width - 1)
    }
}

/// Find the adjacent existing start, skipping a wholly missing aligned period.
fn snap_candidate(
    value: &Bound<'_, PyDateTime>,
    mut start: i64,
    period: SnapPeriod,
    later: bool,
) -> PyResult<([i64; 7], i32)> {
    for _ in 0..4 {
        let fields = from_us(start)?;
        if let Some(result) = optional_period_target(
            value,
            fields,
            start,
            snap_period_end(start, period)?,
            false,
            false,
        )? {
            return Ok(result);
        }
        if period.months != 0 {
            start = shift_snap(start, period, if later { 1 } else { -1 })?;
        } else {
            let zone = _pydt_stored_timezone(value);
            let carrier = wall_carrier(value.py(), fields, &zone)?;
            let (before, after) = regional_offsets(&carrier, &zone)?.ok_or_else(|| {
                crate::error_context::value_error(
                    "timezone cannot confirm an existing adjacent period",
                )
            })?;
            let (last, first) = gap_edges(start, after - before, &zone)?;
            let edge = if later { first } else { last };
            let slots = (edge - start).div_euclid(period.step);
            let mut next = start + slots * period.step;
            // Keep the period containing the first existing instant. Its
            // beginning may be clipped by the gap, but is still a valid start.
            if next == start {
                next = shift_snap(start, period, if later { 1 } else { -1 })?;
            }
            start = next;
        }
    }
    Err(crate::error_context::value_error(
        "timezone cannot confirm adjacent existing periods",
    ))
}

/// Snap to an adjacent valid calendar start; an equal distance selects the later one.
#[pyfunction(signature=(value,unit="s"))]
fn _pydt_snap<'py>(value: &Bound<'py, PyDateTime>, unit: &str) -> PyResult<Bound<'py, PyAny>> {
    if matches!(unit, "us" | "ns") {
        return Ok(value.clone().into_any());
    }
    let fields = parts(value);
    let wall = wall_us(fields);
    let day = 86_400_000_000;
    let mut period = SnapPeriod {
        months: 0,
        step: 0,
        width_months: 0,
        width: 0,
    };
    let lower = match unit {
        "Y" | "Q" | "M" => {
            let months = match unit {
                "Y" => 12,
                "Q" => 3,
                _ => 1,
            };
            period.months = months;
            period.width_months = months;
            let month = (fields[1] - 1) / months * months + 1;
            wall_us([fields[0], month, 1, 0, 0, 0, 0])
        }
        "W" => {
            period.step = 7 * day;
            period.width = 7 * day;
            (wall.div_euclid(day)
                - (crate::calendar::ordinal(fields[0], fields[1], fields[2]) - 1).rem_euclid(7))
                * day
        }
        "D" | "h" | "m" | "min" | "s" | "ms" | "us" => {
            let step = match unit {
                "D" => day,
                "h" => 3_600_000_000,
                "m" | "min" => 60_000_000,
                "s" => 1_000_000,
                "ms" => 1000,
                _ => 1,
            };
            period.step = step;
            period.width = step;
            wall.div_euclid(step) * step
        }
        _ => {
            let (month, weekday) = boundary_names(unit);
            if month >= 1 {
                period.months = 12;
                period.width_months = 1;
                let mut start = wall_us([fields[0], i64::from(month), 1, 0, 0, 0, 0]);
                if start > wall {
                    start = shift_snap(start, period, -1)?;
                }
                start
            } else if weekday >= 0 {
                period.step = 7 * day;
                period.width = day;
                let current =
                    (crate::calendar::ordinal(fields[0], fields[1], fields[2]) - 1).rem_euclid(7);
                let mut start = wall.div_euclid(day) * day + (i64::from(weekday) - current) * day;
                if start > wall {
                    start -= 7 * day;
                }
                start
            } else {
                return Err(crate::error_context::value_error(
                    "unit must be Y, Q, M, W, D, h, m, min, s, ms, us, or a stored month/weekday name",
                ));
            }
        }
    };
    let zone = _pydt_stored_timezone(value);
    if lower == wall && ordinary_zone(&zone) {
        return Ok(value.clone().into_any());
    }
    let upper = shift_snap(lower, period, 1)?;
    if ordinary_zone(&zone) {
        let chosen = if wall - lower < upper - wall {
            lower
        } else {
            upper
        };
        return build_selected(
            &value.get_type(),
            from_us(chosen)?,
            &zone,
            i32::from(value.get_fold()),
        );
    }
    // Outside the target range, a far endpoint cannot win even with a full offset change.
    if upper > 253_402_300_799_999_999 && wall - lower + 2 * day < upper - wall {
        let (fields, fold) = snap_candidate(value, lower, period, false)?;
        return build_selected(&value.get_type(), fields, &zone, fold);
    }
    if lower < -62_135_596_800_000_000 && upper - wall + 2 * day < wall - lower {
        let (fields, fold) = snap_candidate(value, upper, period, true)?;
        return build_selected(&value.get_type(), fields, &zone, fold);
    }
    let left = snap_candidate(value, lower, period, false)?;
    let right = snap_candidate(value, upper, period, true)?;
    let source_offset = offset_us(&utc_offset(value)?)?.unwrap_or(0);
    let source = wall - source_offset;
    let instant = |candidate: ([i64; 7], i32)| -> PyResult<i64> {
        let carrier = PyDateTime::new_with_fold(
            value.py(),
            candidate.0[0] as i32,
            candidate.0[1] as u8,
            candidate.0[2] as u8,
            candidate.0[3] as u8,
            candidate.0[4] as u8,
            candidate.0[5] as u8,
            candidate.0[6] as u32,
            Some(zone.cast::<PyTzInfo>()?),
            candidate.1 != 0,
        )?;
        Ok(wall_us(candidate.0) - offset_us(&utc_offset(&carrier)?)?.unwrap_or(0))
    };
    let mut chosen = left;
    let mut selected_instant = 0;
    let mut distance = i64::MAX;
    // A repeated clock boundary has two real occurrences. Calendar periods
    // still use their first existing start, as the boundary operations do.
    let clock_period = period.months == 0 && period.step > 0 && period.step < day;
    let mut candidates = vec![left, right];
    let mut raw_starts = vec![lower, upper];
    let mut expanded = false;
    let mut next = 0;
    while next < candidates.len() {
        let candidate = candidates[next];
        next += 1;
        let offsets = if clock_period {
            let carrier = wall_carrier(value.py(), candidate.0, &zone)?;
            regional_offsets(&carrier, &zone)?
        } else {
            None
        };
        let repeated = offsets.is_some_and(|(a, b)| b < a);
        if repeated && !expanded {
            expanded = true;
            let (before, after) = offsets
                .ok_or_else(|| crate::error_context::value_error("missing repeated offsets"))?;
            // Project the source instant into each offset regime, then include
            // its adjacent grid boundaries. One neighbour on either side
            // covers the clipped edge of the other regime at a backward jump.
            // The candidate count is fixed; no per-second or historical scan.
            for offset in [before, after] {
                let projected = wall + offset - source_offset;
                let aligned = projected.div_euclid(period.step) * period.step;
                for raw in [aligned - period.step, aligned, aligned + period.step] {
                    if !raw_starts.contains(&raw)
                        && (-62_135_596_800_000_000..=253_402_300_799_999_999).contains(&raw)
                    {
                        raw_starts.push(raw);
                        candidates.push(snap_candidate(value, raw, period, raw >= wall)?);
                    }
                }
            }
        }
        for fold in 0..=i32::from(repeated) {
            let candidate = (candidate.0, if repeated { fold } else { candidate.1 });
            let at = instant(candidate)?;
            let delta = (source - at).abs();
            if delta < distance || delta == distance && at > selected_instant {
                chosen = candidate;
                selected_instant = at;
                distance = delta;
            }
        }
    }
    if chosen.0 == fields && distance == 0 {
        return Ok(value.clone().into_any());
    }
    build_selected(&value.get_type(), chosen.0, &zone, chosen.1)
}

/// Round wall-clock epoch microseconds with integer half-to-even arithmetic.
#[pyfunction]
fn _pydt_round<'py>(
    value: &Bound<'py, PyDateTime>,
    unit: &str,
    mode: u8,
) -> PyResult<Bound<'py, PyAny>> {
    let factor = match unit {
        "D" => 86_400_000_000,
        "h" => 3_600_000_000,
        "m" | "min" => 60_000_000,
        "s" => 1_000_000,
        "ms" => 1000,
        "us" | "ns" => 1,
        _ => {
            return Err(crate::error_context::value_error(
                "freq must be D, h, m, min, s, ms, us or ns",
            ));
        }
    };
    let clock = i64::from(value.get_hour()) * 3_600_000_000
        + i64::from(value.get_minute()) * 60_000_000
        + i64::from(value.get_second()) * 1_000_000
        + i64::from(value.get_microsecond());
    let mut q = clock / factor;
    let r = clock % factor;
    match mode {
        0 => {
            // Every sub-day factor occurs an even number of times per day.
            // Only a noon tie needs the epoch day's parity, including pre-1970.
            let odd = r * 2 == factor
                && if factor == 86_400_000_000 {
                    (crate::calendar::ordinal(
                        i64::from(value.get_year()),
                        i64::from(value.get_month()),
                        i64::from(value.get_day()),
                    ) - 719_163)
                        % 2
                        != 0
                } else {
                    q % 2 != 0
                };
            if r * 2 > factor || odd {
                q += 1;
            }
        }
        1 => {
            if r != 0 {
                q += 1;
            }
        }
        2 => {}
        _ => return Err(crate::error_context::value_error("invalid rounding mode")),
    }
    if r == 0 {
        return Ok(value.clone().into_any());
    }
    let mut fields = parts(value);
    let mut rounded = q * factor;
    if rounded == 86_400_000_000 {
        let date = shifted_days(
            [fields[0], fields[1], fields[2]],
            1,
            "Pydt rounding is outside years 1 through 9999",
        )?;
        fields[..3].copy_from_slice(&date);
        rounded = 0;
    }
    fields[3] = rounded / 3_600_000_000;
    fields[4] = rounded / 60_000_000 % 60;
    fields[5] = rounded / 1_000_000 % 60;
    fields[6] = rounded % 1_000_000;
    let zone = _pydt_stored_timezone(value);
    if ordinary_zone(&zone) {
        return build_selected(
            &value.get_type(),
            fields,
            &zone,
            i32::from(value.get_fold()),
        );
    }
    let (fields, fold) = rounded_target(value, fields, factor, mode)?;
    build_selected(&value.get_type(), fields, &zone, fold)
}

/// Trim fractional second digits directly, retaining date/timezone/fold.
#[pyfunction]
fn _pydt_fsp<'py>(
    value: &Bound<'py, PyDateTime>,
    precision: Integer,
) -> PyResult<Bound<'py, PyAny>> {
    let precision = precision.0;
    if precision < 0 {
        return Err(crate::error_context::value_error(
            "precision must be nonnegative",
        ));
    }
    if precision >= 6 {
        return Ok(value.clone().into_any());
    }
    let mut f = parts(value);
    let factor = 10_i64.pow((6 - precision) as u32);
    f[6] = f[6] / factor * factor;
    result(value, f, false)
}

/// Create midnight from an ordinal, keeping the original integer conversion.
#[pyfunction]
fn _pydt_from_ordinal<'py>(
    class: &Bound<'py, PyType>,
    ordinal: Integer,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    if !(1..=3_652_059).contains(&ordinal.0) {
        return Err(crate::error_context::value_error(
            "ordinal must be in 1..3652059",
        ));
    }
    let [y, m, d] =
        crate::calendar::from_ordinal(ordinal.0).map_err(crate::error_context::overflow)?;
    build(class, [y, m, d, 0, 0, 0, 0], tz, 0)
}
/// Clamp a day-of-year only after validating the requested calendar year.
#[pyfunction]
fn _pydt_from_doy<'py>(
    class: &Bound<'py, PyType>,
    year: Integer,
    doy: Integer,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let year = year.0;
    if !(1..=9999).contains(&year) {
        return Err(crate::error_context::value_error("year must be in 1..9999"));
    }
    if doy.0 < 1 {
        return Err(crate::error_context::value_error("doy must be at least 1"));
    }
    let ordinal =
        crate::calendar::year_day_ordinal(year, doy.0).map_err(crate::error_context::overflow)?;
    let [y, m, d] =
        crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)?;
    build(class, [y, m, d, 0, 0, 0, 0], tz, 0)
}

/// Select the final ISO week/day for high convenience inputs; reject low values.
#[pyfunction]
fn _pydt_from_iso<'py>(
    class: &Bound<'py, PyType>,
    year: IndexInteger,
    week: IndexInteger,
    weekday: IndexInteger,
    tz: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let year = year.0;
    if !(1..=9999).contains(&year) {
        return Err(crate::error_context::value_error("year must be in 1..9999"));
    }
    if week.0 < 1 || weekday.0 < 1 {
        return Err(crate::error_context::value_error(
            "week and weekday must be at least 1",
        ));
    }
    let ordinal = crate::calendar::iso_ordinal(year, week.0, weekday.0)
        .map_err(crate::error_context::overflow)?;
    let [y, m, d] =
        crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)?;
    build(class, [y, m, d, 0, 0, 0, 0], tz, 0)
}
/// Count Gregorian leap years in the half-open interval between two years.
#[pyfunction]
fn _pydt_leaps(value: &Bound<'_, PyDateTime>, year: Integer) -> PyResult<i64> {
    if !(1..=9999).contains(&year.0) {
        return Err(crate::error_context::value_error("year must be in 1..9999"));
    }
    let before = |y: i64| {
        let n = y - 1;
        n.div_euclid(4) - n.div_euclid(100) + n.div_euclid(400)
    };
    Ok((before(i64::from(value.get_year())) - before(year.0)).abs())
}

/// Add a checked duration to wall-clock fields before one local-time repair.
fn duration_result<'py>(value: &Bound<'py, PyDateTime>, us: i128) -> PyResult<Bound<'py, PyAny>> {
    if us == 0 {
        return Ok(value.clone().into_any());
    }
    let mut fields = parts(value);
    let clock =
        fields[3] * 3_600_000_000 + fields[4] * 60_000_000 + fields[5] * 1_000_000 + fields[6];
    let total = i128::from(clock) + us;
    let clock = if (0..86_400_000_000).contains(&total) {
        total as i64
    } else {
        // Any valid date displacement is under 3652059 days, far inside i64
        // microseconds. Wider values cannot produce a year in 1..=9999.
        let total = i64::try_from(total).map_err(|_| {
            crate::error_context::overflow("Pydt arithmetic result is outside years 1 through 9999")
        })?;
        let days = total.div_euclid(86_400_000_000);
        let date = shifted_days(
            [fields[0], fields[1], fields[2]],
            days,
            "Pydt arithmetic result is outside years 1 through 9999",
        )?;
        fields[..3].copy_from_slice(&date);
        total.rem_euclid(86_400_000_000)
    };
    fields[3] = clock / 3_600_000_000;
    fields[4] = clock / 60_000_000 % 60;
    fields[5] = clock / 1_000_000 % 60;
    fields[6] = clock % 1_000_000;
    result(value, fields, true)
}

/// Read timedelta's native fields, preserving the input datetime's fold.
#[pyfunction]
fn _pydt_timedelta<'py>(
    value: &Bound<'py, PyDateTime>,
    duration: &Bound<'py, PyDelta>,
    subtract: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let mut us = i128::from(duration.get_days()) * 86_400_000_000
        + i128::from(duration.get_seconds()) * 1_000_000
        + i128::from(duration.get_microseconds());
    // pandas' coarse out-of-bounds durations have a zero builtin carrier.
    // Preserve the ordinary native read; only that ambiguous carrier needs ticks.
    if us == 0 && !duration.is_exact_instance_of::<PyDelta>() {
        if let Some(nanos) = crate::interop::duration_nanoseconds(duration.as_any())? {
            us = nanos.div_euclid(1000);
        }
    }
    duration_result(value, if subtract { -us } else { us })
}

/// Dispatch public Pydt arithmetic by real types in the existing native call.
///
/// # Errors
/// Preserves arithmetic and callback errors; unsupported operands negotiate via
/// NotImplemented instead of trusting an object's displayed __class__.
#[pyfunction]
fn _pydt_binary<'py>(
    value: &Bound<'py, PyDateTime>,
    operand: &Bound<'py, PyAny>,
    subtract: bool,
) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(duration) = operand.cast::<PyDelta>() {
        return _pydt_timedelta(value, duration, subtract);
    }
    if subtract {
        if let Ok(other) = operand.cast::<PyDateTime>() {
            return crate::pydt_compare::_pydt_datetime_sub(value, other);
        }
    }
    if crate::interop::is_relativedelta(operand)? {
        let carrier = _pydt_carrier(value)?;
        let answer = operand
            .call_method1(if subtract { "__rsub__" } else { "__radd__" }, (carrier,))
            .map_err(crate::error_context::external)?;
        return if let Ok(date) = answer.cast::<PyDateTime>() {
            _pydt_from_calendar(value, date)
        } else {
            Ok(answer)
        };
    }
    if subtract {
        if let Ok(date) = operand.cast::<PyDate>() {
            let date = PyDateTime::new(
                value.py(),
                date.get_year(),
                date.get_month(),
                date.get_day(),
                0,
                0,
                0,
                0,
                None,
            )?;
            return crate::pydt_compare::_pydt_datetime_sub(value, &date);
        }
        if operand.cast::<pyo3::types::PyString>().is_ok() {
            let Some(parsed) = crate::parser::arithmetic_date(operand)? else {
                return Ok(value.py().NotImplemented().into_bound(value.py()));
            };
            let py = value.py();
            let parsed = parsed.bind(py);
            // This remains datetime's standard string-subtraction result rule.
            let standard = SUB.get(py).ok_or_else(|| {
                crate::error_context::runtime("datetime subtraction is unavailable")
            })?;
            return standard
                .bind(py)
                .call1((value, parsed))
                .map_err(crate::error_context::external);
        }
    }
    _pydt_numpy(value, operand, subtract)
}

/// Normalize relative integers before sharing Delta's checked calendar algorithm.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Mirrors the existing calendar-duration interface"
)]
fn _pydt_add<'py>(
    value: &Bound<'py, PyDateTime>,
    subtract: bool,
    years: Integer,
    quarters: Integer,
    months: Integer,
    weeks: Integer,
    days: Integer,
    hours: Integer,
    minutes: Integer,
    seconds: Integer,
    milliseconds: Integer,
    microseconds: Integer,
) -> PyResult<Bound<'py, PyAny>> {
    let sign = if subtract { -1_i64 } else { 1 };
    // Each original input fits signed32. These scaled sums therefore fit i64,
    // including the negation of i32::MIN. Normalize before calendar::apply,
    // whose compact clock/month fields are not an arbitrary-duration interface.
    let months = (years.0 * 12 + quarters.0 * 3 + months.0) * sign;
    let clock = ((hours.0 * 60 + minutes.0) * 60 + seconds.0) * 1_000_000
        + milliseconds.0 * 1000
        + microseconds.0;
    if months == 0 {
        let total = i128::from(weeks.0 * 7 + days.0) * 86_400_000_000 + i128::from(clock);
        return duration_result(value, total * i128::from(sign));
    }
    let clock = clock * sign;
    let days = (weeks.0 * 7 + days.0) * sign + clock.div_euclid(86_400_000_000);
    let clock = clock.rem_euclid(86_400_000_000);
    let fields = crate::delta::value::DeltaValue::from_totals(
        i128::from(months),
        i128::from(days) * crate::delta::value::NS_PER_DAY + i128::from(clock) * 1000,
        crate::delta::value::AbsoluteFields::EMPTY,
    )
    .map_err(|_| crate::error_context::overflow("calendar duration overflow"))?;
    let (out, _) = crate::calendar::apply(&fields, parts(value), 1, true)
        .map_err(crate::error_context::overflow)?;
    result(value, out, true)
}

/// Adapt NumPy operands through the same checked native decoder as Delta/Parser.
#[pyfunction]
fn _pydt_numpy<'py>(
    value: &Bound<'py, PyDateTime>,
    operand: &Bound<'py, PyAny>,
    subtract: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let py = value.py();
    let Some((us, date)) = crate::numpy_scalar::microseconds(operand, true)? else {
        return Ok(py.NotImplemented().into_bound(py));
    };
    if date && !subtract {
        return Ok(py.NotImplemented().into_bound(py));
    }
    if !date {
        return duration_result(
            value,
            if subtract {
                -i128::from(us)
            } else {
                i128::from(us)
            },
        );
    }
    let other = {
        let f = from_us(us)?;
        PyDateTime::new(
            py,
            f[0] as i32,
            f[1] as u8,
            f[2] as u8,
            f[3] as u8,
            f[4] as u8,
            f[5] as u8,
            f[6] as u32,
            None,
        )?
        .into_any()
    };
    let method = SUB
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("datetime arithmetic unavailable"))?;
    method
        .bind(py)
        .call1((value, other))
        .map_err(crate::error_context::external)
}

/// Count a unit's calendar buckets, using integer UTC adjustment for aware values.
fn bucket(value: &Bound<'_, PyDateTime>, unit: &str, us: i64, aware: bool) -> PyResult<i64> {
    match unit {
        "Y" | "Q" | "M" => {
            let f = if aware {
                crate::parser::objects::wide_microsecond_fields(i128::from(us))?
            } else {
                parts(value)
            };
            let year = f[0] - 1970;
            Ok(match unit {
                "Y" => year,
                "Q" => year * 4 + (f[1] - 1) / 3,
                _ => year * 12 + f[1] - 1,
            })
        }
        "W" => Ok((us.div_euclid(86_400_000_000) + 3).div_euclid(7)),
        "D" => Ok(us.div_euclid(86_400_000_000)),
        "h" => Ok(us.div_euclid(3_600_000_000)),
        "m" | "min" => Ok(us.div_euclid(60_000_000)),
        "s" => Ok(us.div_euclid(1_000_000)),
        "ms" => Ok(us.div_euclid(1000)),
        "us" => Ok(us),
        _ => Err(crate::error_context::value_error(
            "unit must be Y, Q, M, W, D, h, m, min, s, ms or us",
        )),
    }
}

/// Apply the frozen boundary-count inclusive rule without datetime subtraction.
#[pyfunction]
fn _pydt_diff(
    value: &Bound<'_, PyDateTime>,
    other: &Bound<'_, PyDateTime>,
    unit: &str,
    absolute: bool,
    inclusive: &str,
) -> PyResult<i64> {
    let off1 = offset_us(&utc_offset(value)?)?;
    let off2 = offset_us(&utc_offset(other)?)?;
    if off1.is_some() != off2.is_some() {
        return Err(crate::error_context::type_error(
            "cannot mix naive and aware datetimes",
        ));
    }
    let (a, b) = if off1.is_none() && matches!(unit, "Y" | "Q" | "M") {
        // Calendar buckets consume only year/month for naive inputs.
        (0, 0)
    } else {
        (
            epoch_microseconds(value, false)? - off1.unwrap_or(0),
            epoch_microseconds(other, false)? - off2.unwrap_or(0),
        )
    };
    let difference =
        bucket(value, unit, a, off1.is_some())? - bucket(other, unit, b, off2.is_some())?;
    let adjustment = match inclusive {
        "one" => 0,
        "both" => 1,
        "neither" => -1,
        _ => {
            return Err(crate::error_context::value_error(
                "inclusive must be one, both or neither",
            ));
        }
    };
    Ok(if absolute {
        difference.abs() + adjustment
    } else if difference < 0 {
        difference - adjustment
    } else {
        difference + adjustment
    })
}

/// Build one date-first recipe using live definitions and normal user callbacks.
#[pyfunction]
fn _pydt_reduce<'py>(
    value: &Bound<'py, PyDateTime>,
    restore: &Bound<'py, PyAny>,
    check_reduce: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let py = value.py();
    let original = ORIGINAL_REDUCE
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("Pydt state methods are unavailable"))?;
    if check_reduce
        && crate::protocol::method_definition(&value.get_type(), "__reduce__")?
            .is_none_or(|method| !method.is(original.bind(py)))
    {
        return value
            .call_method0("__reduce__")
            .map_err(crate::error_context::external);
    }
    let fields = PyTuple::new(py, parts(value))?;
    let zone = _pydt_stored_timezone(value);
    let fold = i32::from(value.get_fold());
    let default = OBJECT_STATE
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("object state method is unavailable"))?;
    let ordinary = crate::protocol::method_definition(&value.get_type(), "__getstate__")?
        .is_some_and(|method| method.is(default.bind(py)));
    let state = if ordinary {
        crate::state::capture_object_metadata(value.as_any())?
    } else {
        value
            .call_method0("__getstate__")
            .map_err(crate::error_context::external)?
    };
    (restore, (value.get_type(), 1, fields, zone, fold), state)
        .into_pyobject(py)
        .map(Bound::into_any)
}

/// Return calendar predicates directly without an intermediate Python integer.
#[pyfunction]
fn _pydt_flag(value: &Bound<'_, PyDateTime>, query: u8) -> PyResult<bool> {
    let year = i64::from(value.get_year());
    match query {
        2 => Ok(crate::calendar::leap(year)),
        3 => {
            let jan1 = (crate::calendar::ordinal(year, 1, 1) - 1) % 7;
            Ok(jan1 == 3 || (jan1 == 2 && crate::calendar::leap(year)))
        }
        _ => Err(crate::error_context::runtime("unknown Pydt boolean query")),
    }
}

/// Compare the stored zone directly with the standard UTC singleton.
#[pyfunction]
fn _pydt_is_utc(value: &Bound<'_, PyDateTime>) -> bool {
    // SAFETY: datetime registration initialized the capsule and the value is live.
    unsafe {
        ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()) == (*ffi::PyDateTimeAPI()).TimeZone_UTC
    }
}

/// Only resolve the local zone when a stored timezone can actually match it.
#[pyfunction]
fn _pydt_is_local(value: &Bound<'_, PyDateTime>, local: &Bound<'_, PyAny>) -> PyResult<bool> {
    // SAFETY: the live datetime owns this timezone throughout the resolver call.
    let zone = unsafe { ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()) };
    if zone == unsafe { ffi::Py_None() } {
        return Ok(false);
    }
    Ok(local
        .call0()
        .map_err(crate::error_context::external)?
        .as_ptr()
        == zone)
}

/// Test integer calendar fields with the frozen convenience conversion.
#[pyfunction]
fn _pydt_matches(
    value: &Bound<'_, PyDateTime>,
    query: u8,
    expected: IndexInteger,
) -> PyResult<bool> {
    let actual = match query {
        0 => i64::from(value.get_year()),
        1 => _pydt_calendar(value, 0)?,
        2 => i64::from(value.get_day()),
        3 => i64::from(value.get_month()),
        4 => _pydt_calendar(value, 12)?,
        _ => return Err(crate::error_context::runtime("unknown calendar field")),
    };
    Ok(actual == expected.0)
}

/// Read a validated complete offset before flooring to whole seconds.
#[pyfunction]
fn _pydt_offset_seconds(value: &Bound<'_, PyDateTime>) -> PyResult<Option<i64>> {
    Ok(offset_us(&utc_offset(value)?)?.map(|n| n.div_euclid(1_000_000)))
}

/// Convert Pydt values with standard timezones, keeping UTC work raw.
/// Children retain their public constructor; dynamic timezone protocols keep
/// the Python carrier path used by datetime.astimezone.
#[pyfunction(signature=(value, target, offset=None, strip_timezone=false, astimezone=false, output_class=None))]
fn _pydt_convert<'py>(
    value: &Bound<'py, PyDateTime>,
    target: &Bound<'py, PyAny>,
    offset: Option<&Bound<'py, PyAny>>,
    strip_timezone: bool,
    astimezone: bool,
    output_class: Option<&Bound<'py, PyType>>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = value.py();
    let Some(base) = CLASS.get(py) else {
        return Ok(None);
    };
    if astimezone {
        let source = _pydt_stored_timezone(value);
        if source.is(target) && (ordinary_zone(&source) || standard_region(&source)?) {
            return Ok(Some(value.clone().into_any()));
        }
        if source.is_none() {
            return Ok(None);
        }
    }
    let class = output_class.cloned().unwrap_or_else(|| value.get_type());
    // A child's precomputed offset must keep the existing caller's carrier
    // semantics: custom tzinfo may distinguish the child from builtin datetime.
    if !class.is(base.bind(py)) && (offset.is_some() || !class.is_subclass(base.bind(py))?) {
        if let Some(offset) = offset {
            offset_us(offset)?;
        }
        return Ok(None);
    }
    // SAFETY: the datetime capsule was initialized at module registration.
    let utc = unsafe { ffi::PyDateTime_TimeZone_UTC() };
    let fixed = unsafe { ffi::Py_TYPE(target.as_ptr()) == ffi::Py_TYPE(utc) };
    let zone = ZONEINFO
        .get(py)
        .is_some_and(|class| target.get_type().is(class.bind(py)));
    let implicit_offset;
    let offset = match offset {
        Some(offset) => offset,
        None => {
            // astimezone's dynamic source protocol receives a builtin carrier.
            // Keep that path intact; only standard immutable zones come here.
            // SAFETY: this checked live datetime retains its source timezone.
            let source = unsafe {
                Bound::from_borrowed_ptr(py, ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()))
            };
            let source_fixed = unsafe { ffi::Py_TYPE(source.as_ptr()) == ffi::Py_TYPE(utc) };
            let source_zone = ZONEINFO
                .get(py)
                .is_some_and(|class| source.get_type().is(class.bind(py)));
            implicit_offset = if source_fixed || source_zone {
                utc_offset(value)?
            } else {
                // Keep datetime.astimezone's established builtin-carrier
                // callback receiver, then consume that one validated result.
                utc_offset(&_pydt_carrier(value)?)?
            };
            &implicit_offset
        }
    };
    let Some(source_offset) = offset_us(offset)? else {
        if astimezone {
            return Ok(None);
        }
        return Err(crate::error_context::value_error(
            "timezone-naive value requires tz_localize first",
        ));
    };
    if strip_timezone {
        if !class.is(base.bind(py)) || target.as_ptr() != utc {
            return Ok(None);
        }
        // The old UTC-identity route kept fold before removing the zone.
        // Every converted UTC value has fold=0. Preserve both cases directly.
        let same_zone = unsafe { ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()) == utc };
        let fields = from_us(epoch_microseconds(value, false)? - source_offset)?;
        return build(
            &class,
            fields,
            py.None().bind(py),
            if same_zone {
                i32::from(value.get_fold())
            } else {
                0
            },
        )
        .map(Some);
    }
    // SAFETY: a real live datetime owns its borrowed timezone.
    if output_class.is_none()
        && unsafe { ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()) } == target.as_ptr()
    {
        return Ok(Some(value.clone().into_any()));
    }
    let utc_us = epoch_microseconds(value, false)? - source_offset;
    if fixed {
        let target_offset = if target.as_ptr() == utc {
            0
        } else {
            offset_us(
                &target
                    .call_method1("utcoffset", (py.None(),))
                    .map_err(crate::error_context::external)?,
            )?
            .ok_or_else(|| crate::error_context::value_error("fixed timezone has no UTC offset"))?
        };
        // Validate the UTC intermediate too, matching datetime's supported range.
        let utc_fields = from_us(utc_us)?;
        let fields = if target_offset == 0 {
            utc_fields
        } else {
            from_us(utc_us + target_offset)?
        };
        return build(&value.get_type(), fields, target, 0).map(Some);
    }
    let f = from_us(utc_us)?;
    let tz = target.cast::<PyTzInfo>()?;
    let carrier = PyDateTime::new_with_fold(
        py,
        f[0] as i32,
        f[1] as u8,
        f[2] as u8,
        f[3] as u8,
        f[4] as u8,
        f[5] as u8,
        f[6] as u32,
        Some(tz),
        false,
    )?;
    let local = target
        .call_method1("fromutc", (carrier,))
        .map_err(crate::error_context::external)?;
    let local = local.cast::<PyDateTime>()?;
    // SAFETY: local is a checked datetime; its timezone must be the requested one.
    if zone && unsafe { ffi::PyDateTime_DATE_GET_TZINFO(local.as_ptr()) } != target.as_ptr() {
        return Err(crate::error_context::value_error(
            "tzinfo.fromutc() returned a different timezone",
        ));
    }
    if !zone {
        // A custom fromutc implementation may use the stdlib's narrow duration
        // carrier internally. Validate its actual resulting offset before use.
        offset_us(&utc_offset(local)?)?;
        if output_class.is_some() {
            return class
                .call_method1("fromdatetime", (local,))
                .map_err(crate::error_context::external)
                .map(Some);
        }
        let from = base
            .bind(py)
            .getattr("fromdatetime")
            .map_err(crate::error_context::external)?
            .getattr("__func__")
            .map_err(crate::error_context::external)?;
        return from
            .call1((&class, local))
            .map_err(crate::error_context::external)
            .map(Some);
    }
    if class.is(base.bind(py)) {
        // ZoneInfo.fromutc already supplied a valid instant and stored fold.
        // Copy the verified native fields once, without localizing them again.
        return allocate(&class, parts(local), target, i32::from(local.get_fold())).map(Some);
    }
    build(&class, parts(local), target, i32::from(local.get_fold())).map(Some)
}

/// Install private entry points used by the Python Pydt class.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::python_cache::get_or_prepare(&DATETIME_NEW, module.py(), || -> PyResult<_> {
        Ok(module
            .py()
            .get_type::<PyDateTime>()
            .getattr("__new__")?
            .unbind())
    })?;
    module.add_function(wrap_pyfunction!(_pydt_create, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_copy_fold, module)?)?;
    crate::python_cache::get_or_prepare(&ZONEINFO, module.py(), || -> PyResult<_> {
        Ok(module
            .py()
            .import("zoneinfo")?
            .getattr("ZoneInfo")
            .map_err(crate::error_context::external)?
            .cast_into::<PyType>()?
            .unbind())
    })?;
    crate::python_cache::get_or_prepare(&REGION_OFFSET, module.py(), || -> PyResult<_> {
        let kind = ZONEINFO
            .get(module.py())
            .ok_or_else(|| crate::error_context::runtime("ZoneInfo class is unavailable"))?;
        Ok(kind
            .bind(module.py())
            .getattr("utcoffset")
            .map_err(crate::error_context::external)?
            .unbind())
    })?;
    crate::python_cache::get_or_prepare(&ZONEINFO_KEY, module.py(), || -> PyResult<_> {
        Ok(ZONEINFO
            .get(module.py())
            .ok_or_else(|| crate::error_context::runtime("ZoneInfo class is unavailable"))?
            .bind(module.py())
            .getattr("key")?
            .unbind())
    })?;
    crate::python_cache::get_or_prepare(&UTC_REGIONS, module.py(), || -> PyResult<_> {
        let class = ZONEINFO
            .get(module.py())
            .ok_or_else(|| crate::error_context::runtime("ZoneInfo class is unavailable"))?
            .bind(module.py());
        let mut zones = Vec::with_capacity(4);
        for key in ["UTC", "Etc/UTC", "Etc/GMT", "GMT"] {
            match class.call1((key,)).map_err(crate::error_context::external) {
                Ok(zone) => zones.push(zone.unbind()),
                // Missing tzdata must not prevent naive/fixed-offset use.
                Err(error) if error.is_instance_of::<PyKeyError>(module.py()) => {}
                Err(error) => return Err(error),
            }
        }
        Ok(zones)
    })?;
    crate::python_cache::get_or_prepare(&SUB, module.py(), || -> PyResult<_> {
        Ok(module
            .py()
            .get_type::<PyDateTime>()
            .getattr("__sub__")
            .map_err(crate::error_context::external)?
            .unbind())
    })?;
    module.add_function(wrap_pyfunction!(_pydt_name_matches, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_iso, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_numpy, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_is_utc, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_flag, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_is_local, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_offset_seconds, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_compare_now, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_convert, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_matches, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_add, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_numpy, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_timedelta, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_binary, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_diff, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_normalize, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_ordinal, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_doy, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_iso, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_leaps, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_register, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_copy_datetime, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_instant, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_calendar, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_copy_date, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_combine, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_calendar_date, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_repr_fields, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_carrier, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_replace, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_replace_general, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_stored_timezone, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_millisecond, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_clock, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_shift, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_us, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_to_us, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_to_seconds, module)?)?;
    module.add_function(wrap_pyfunction!(lookup_selector, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_lookup_optional, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_calendar, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_day_of_year, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_days_in_month, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_is_leap_year, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_move, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_adjust, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_boundary, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_is_boundary, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_round, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_snap, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_fsp, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_numpy_zoned, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_strptime, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_from_seconds, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_reduce, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_timedict, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_dst, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_is_dst, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_timetuple, module)?)?;
    Ok(())
}
