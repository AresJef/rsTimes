//! Necessary host timezone protocol shared by explicit Python exits.
use crate::pydt;
use pyo3::prelude::*;
use pyo3::types::PyDateTime;
/// Necessary dynamic protocol carrier, offset and wall value from one conversion.
pub(crate) fn utc_local<'py>(
    ns: i128,
    zone: &Bound<'py, PyAny>,
) -> PyResult<(Bound<'py, PyDateTime>, i64, i128)> {
    let py = zone.py();
    let fields = crate::parser::objects::wide_microsecond_fields(ns.div_euclid(1000))?;
    if !(1..=9999).contains(&fields[0]) {
        return Err(crate::error_context::overflow(
            "this dynamic fromutc protocol requires UTC years 1 through 9999",
        ));
    }
    let carrier = pydt::wall_carrier(py, fields, zone)?;
    let local = zone
        .call_method1("fromutc", (carrier,))
        .map_err(crate::error_context::external)?;
    let local = local.cast_into::<PyDateTime>()?;
    let f = pydt::parts(&local);
    let offset = crate::epoch::offset_us(&pydt::utc_offset(&local)?)?.ok_or_else(|| {
        crate::error_context::value_error("fromutc result has no valid UTC offset")
    })?;
    let ordinal = crate::calendar::checked_ordinal(f[0], f[1], f[2])
        .map_err(crate::error_context::overflow)?;
    let wall = (i128::from(ordinal) - 719_163) * 86_400_000_000_000
        + ((i128::from(f[3]) * 60 + i128::from(f[4])) * 60 + i128::from(f[5])) * 1_000_000_000
        + i128::from(f[6]) * 1000;
    if wall - i128::from(offset) * 1000 != ns.div_euclid(1000) * 1000 {
        return Err(crate::error_context::value_error(
            "tzinfo.fromutc() did not preserve the actual instant",
        ));
    }
    Ok((local, offset, wall + ns.rem_euclid(1000)))
}
