//! Actual temporal source values and live arithmetic eligibility at host boundaries.
use crate::delta::Delta;
use crate::epoch::{Options, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::{PyDate, PyDelta, PyDeltaAccess};
const NS_DAY: i128 = 86_400_000_000_000;
#[derive(Clone, Copy)]
pub(crate) enum Value {
    Delta(crate::delta::value::DeltaValue),
    Span(i128),
    Date(i128, bool),
    Missing(u8),
}
pub(crate) fn numpy_code(name: &str) -> PyResult<i32> {
    match name {
        "Y" => Ok(0),
        "M" => Ok(1),
        "W" => Ok(2),
        "D" => Ok(4),
        "h" => Ok(5),
        "m" => Ok(6),
        "s" => Ok(7),
        "ms" => Ok(8),
        "us" => Ok(9),
        "ns" => Ok(10),
        _ => Err(crate::error_context::type_error(
            "unsupported native temporal unit",
        )),
    }
}
pub(crate) fn span(ticks: i64, code: i32, multiplier: i32) -> PyResult<Value> {
    if multiplier < 1 {
        return Err(crate::error_context::value_error(
            "invalid temporal unit multiplier",
        ));
    }
    let scale = match code {
        2 => 7 * NS_DAY,
        4 => NS_DAY,
        5 => 3_600_000_000_000,
        6 => 60_000_000_000,
        7 => 1_000_000_000,
        8 => 1_000_000,
        9 => 1000,
        10 => 1,
        _ => {
            return Err(crate::error_context::type_error(
                "fixed durations support W, D, h, m, s, ms, us and ns",
            ));
        }
    };
    if ticks == i64::MIN {
        return Ok(Value::Missing(2));
    }
    i128::from(ticks)
        .checked_mul(i128::from(multiplier))
        .and_then(|v| v.checked_mul(scale))
        .map(Value::Span)
        .ok_or_else(|| crate::error_context::overflow("duration exceeds native range"))
}
pub(crate) fn read(value: &Bound<'_, PyAny>, unit: &mut Unit) -> PyResult<Option<Value>> {
    if crate::date_input::missing(value) {
        return Ok(Some(Value::Missing(0)));
    }
    if let Ok(delta) = value.cast::<Delta>() {
        return Ok(Some(Value::Delta(delta.get().native_value())));
    }
    if let Ok(delta) = value.cast::<PyDelta>() {
        let ns = if let Some(v) = crate::interop::duration_nanoseconds(value)? {
            v
        } else {
            (i128::from(delta.get_days()) * 86400 + i128::from(delta.get_seconds())) * 1_000_000_000
                + i128::from(delta.get_microseconds()) * 1000
        };
        return Ok(Some(Value::Span(ns)));
    }
    if let Some((ticks, code, multiplier)) = crate::numpy_scalar::duration_ticks(value)? {
        return span(ticks, code, multiplier).map(Some);
    }
    if let Some((ticks, code, multiplier)) = crate::numpy_scalar::datetime_ticks(value)? {
        *unit = (*unit).max(crate::date_input::scalar_unit(code)?);
        if ticks == i64::MIN {
            return Ok(Some(Value::Missing(3)));
        }
        let parsed = crate::epoch::numpy_ticks(ticks, code, multiplier)?;
        return Ok(Some(Value::Date(parsed.nanos, false)));
    }
    if value.is_instance_of::<PyDate>() {
        let opts = Options {
            default: None,
            yearfirst: None,
            dayfirst: None,
            ignoretz: false,
            isoformat: true,
            strict: false,
            iso_only: false,
            cfg: None,
            input_unit: Unit::Second,
        };
        let parsed = crate::epoch::read(value, &opts)?;
        *unit = (*unit).max(parsed.unit);
        return Ok(Some(Value::Date(
            parsed.nanos,
            !matches!(parsed.zone, Zone::Naive),
        )));
    }
    Ok(None)
}
pub(crate) fn overridden(
    value: &Bound<'_, PyAny>,
    base: &Bound<'_, pyo3::types::PyType>,
    subtract: bool,
) -> PyResult<bool> {
    overrides_method(value, base, if subtract { "__rsub__" } else { "__radd__" })
}

pub(crate) fn overrides_method(
    value: &Bound<'_, PyAny>,
    base: &Bound<'_, pyo3::types::PyType>,
    name: &str,
) -> PyResult<bool> {
    if value.get_type().is(base) {
        return Ok(false);
    }
    let own = crate::protocol::method_definition(&value.get_type(), name)?;
    let base = crate::protocol::method_definition(base, name)?;
    Ok(match (own, base) {
        (Some(a), Some(b)) => !a.is(&b),
        (None, None) => false,
        _ => true,
    })
}

pub(crate) fn column_callback(
    value: &Bound<'_, PyAny>,
    parsed: &Value,
    subtract: bool,
    reflected: bool,
    bases: &(
        Bound<'_, pyo3::types::PyType>,
        Bound<'_, pyo3::types::PyType>,
        Option<Bound<'_, pyo3::types::PyType>>,
    ),
) -> PyResult<Option<&'static str>> {
    // SAFETY: actual and base types are ready and retained under the GIL. A
    // genuine inherited C arithmetic slot proves no Python override needs
    // dispatch. Slot changes are observed afresh, not cached by class name.
    let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
    if actual == bases.0.as_type_ptr() || actual == bases.1.as_type_ptr() {
        return Ok(None);
    }
    let name = if reflected {
        "__add__"
    } else if subtract {
        "__rsub__"
    } else {
        "__radd__"
    };
    let base = match parsed {
        Value::Delta(_) => &bases.0,
        Value::Span(_) if value.is_instance_of::<PyDelta>() => {
            if inherits_stdlib_span_slot(actual, bases.1.as_type_ptr(), subtract) {
                return Ok(None);
            }
            match &bases.2 {
                Some(base) if value.get_type().is_subclass(base)? => base,
                _ => &bases.1,
            }
        }
        _ => return Ok(None),
    };
    // A third-party base may itself use CPython's generic numeric slot. Its
    // subclasses can share that address while overriding the actual methods.
    // Only the known stdlib timedelta C slot above proves native inheritance.
    Ok(overrides_method(value, base, name)?.then_some(name))
}

fn inherits_stdlib_span_slot(
    actual: *mut pyo3::ffi::PyTypeObject,
    base: *mut pyo3::ffi::PyTypeObject,
    subtract: bool,
) -> bool {
    // SAFETY: callers retain both ready types. Number tables may be absent;
    // function addresses are inspected only, never called with guessed layout.
    unsafe {
        let a = (*actual).tp_as_number;
        let b = (*base).tp_as_number;
        if a.is_null() || b.is_null() {
            return false;
        }
        let left = if subtract {
            (*a).nb_subtract
        } else {
            (*a).nb_add
        };
        let right = if subtract {
            (*b).nb_subtract
        } else {
            (*b).nb_add
        };
        left.is_some() && left.map(|f| f as usize) == right.map(|f| f as usize)
    }
}

/// A per-call eligibility cache is valid only while CPython's live type version
/// remains nonzero and unchanged. Standard descriptors can populate that version
/// without invoking user code; custom metaclasses/descriptors stay uncached.
pub(crate) fn protocol_version(value: &Bound<'_, PyAny>, name: &str) -> PyResult<u32> {
    let actual = value.get_type();
    // SAFETY: the owned ready type remains live and attached throughout lookup.
    let mut version = unsafe { (*actual.as_type_ptr()).tp_version_tag };
    if version == 0
        && unsafe { pyo3::ffi::Py_TYPE(actual.as_ptr()) }
            == std::ptr::addr_of_mut!(pyo3::ffi::PyType_Type)
        && let Some(definition) = crate::protocol::method_definition(&actual, name)?
    {
        let kind = unsafe { pyo3::ffi::Py_TYPE(definition.as_ptr()) };
        if kind == std::ptr::addr_of_mut!(pyo3::ffi::PyMethodDescr_Type)
            || kind == std::ptr::addr_of_mut!(pyo3::ffi::PyWrapperDescr_Type)
            || unsafe { pyo3::ffi::PyFunction_Check(definition.as_ptr()) != 0 }
        {
            // Exact type's attribute machinery and these exact descriptor
            // types perform no Python callback. A live class edit clears
            // its version before the following input item can be read.
            let _ = actual
                .getattr(name)
                .map_err(crate::error_context::external)?;
            version = unsafe { (*actual.as_type_ptr()).tp_version_tag };
        }
    }
    Ok(version)
}
