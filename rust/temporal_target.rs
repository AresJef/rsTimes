//! Shared scalar date target reading, preserving the actual Python protocol.
use crate::epoch::{Options, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::{PyFloat, PyString};
#[derive(Clone, Copy)]
pub(crate) struct Date {
    pub(crate) nanos: i128,
    pub(crate) aware: bool,
}
pub(crate) fn read(value: &Bound<'_, PyAny>, opts: &Options<'_, '_>) -> PyResult<Option<Date>> {
    if crate::date_input::missing(value) {
        return Ok(None);
    }
    if crate::numeric::is_bool(value) {
        return Err(crate::error_context::type_error(
            "boolean values are not date or epoch inputs",
        ));
    }
    if let Ok(text) = value.cast::<PyString>() {
        let converted;
        let text = if value.is_exact_instance_of::<PyString>() {
            text
        } else {
            converted = value.str().map_err(crate::error_context::external)?;
            &converted
        };
        if crate::date_input::missing_text(text)? {
            return Ok(None);
        }
        let p = crate::epoch::read(text.as_any(), opts)?;
        return Ok(Some(Date {
            nanos: p.nanos,
            aware: !matches!(p.zone, Zone::Naive),
        }));
    }
    if let Some((tick, code, multiplier)) = crate::numpy_scalar::datetime_ticks(value)? {
        crate::date_input::scalar_unit(code)?;
        if tick == i64::MIN {
            return Ok(None);
        }
        return crate::epoch::numpy_ticks(tick, code, multiplier).map(|p| {
            Some(Date {
                nanos: p.nanos,
                aware: false,
            })
        });
    }
    if value.is_instance_of::<pyo3::types::PyDelta>()
        || crate::numpy_scalar::duration_ticks(value)?.is_some()
    {
        return Err(crate::error_context::type_error(
            "a duration is not a date target",
        ));
    }
    if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) != 0 } {
        let nanos = crate::numeric::index_i128(value)?
            .checked_mul(1_000_000_000)
            .ok_or_else(|| {
                crate::error_context::overflow("numeric seconds exceed the native range")
            })?;
        return Ok(Some(Date {
            nanos,
            aware: false,
        }));
    }
    if crate::numeric::supported_float(value) {
        let number = if value.is_instance_of::<PyFloat>() {
            value.extract::<f64>()?
        } else {
            crate::numeric::float_value(value)?
        };
        if number.is_nan() {
            return Ok(None);
        }
        return crate::epoch::float_nanos(number, Unit::Second).map(|nanos| {
            Some(Date {
                nanos,
                aware: false,
            })
        });
    }
    let p = crate::epoch::read(value, opts)?;
    Ok(Some(Date {
        nanos: p.nanos,
        aware: !matches!(p.zone, Zone::Naive),
    }))
}
pub(crate) fn domain(value: Option<Date>, aware: bool) -> PyResult<Option<Date>> {
    if value.is_some_and(|v| v.aware != aware) {
        Err(crate::error_context::type_error(
            "cannot mix naive and aware date targets; prepare the target timezone explicitly",
        ))
    } else {
        Ok(value)
    }
}
