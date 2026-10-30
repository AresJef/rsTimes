//! Direct native calendar queries with independent date validity.
use super::arguments::Integers;
use super::common::NS_DAY;
use crate::epoch::{Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use crate::calendar_query::{fact, iso_at};
impl From<crate::calendar_query::Error> for PyErr {
    fn from(error: crate::calendar_query::Error) -> Self {
        match error {
            crate::calendar_query::Error::Capacity(message) => {
                crate::error_context::overflow(message)
            }
            crate::calendar_query::Error::Internal(message) => {
                crate::error_context::runtime(message)
            }
        }
    }
}

type Output<'py> = (Bound<'py, PyBytes>, Option<Bound<'py, PyBytes>>);
fn loop_query<'py, const Q: u8>(
    py: Python<'py>,
    data: &[u8],
    unit: Unit,
    zone: Option<&Bound<'py, PyAny>>,
    target: Option<&Integers>,
    entry: &str,
) -> PyResult<Output<'py>> {
    let boolean = (100..200).contains(&Q);
    let count = data.len() / 8;
    let fixed = if Q == 107 || Q == 108 {
        Some(0)
    } else {
        super::common::fixed_offset(
            py,
            &zone.map_or(Zone::Naive, |z| Zone::Object(z.clone().unbind())),
        )?
    };
    let width = if boolean { 1 } else { 8 };
    let size = count
        .checked_mul(width)
        .ok_or_else(|| crate::error_context::overflow("query result is too large"))?;
    let mut mask: Option<Vec<u8>> = None;
    let mut now = None;
    let mut fixed_dst = None;
    let mut cached = None;
    // PyBytes::new_with zero-initializes and publishes only after this closure succeeds.
    let bytes = PyBytes::new_with(py, size, |out| {
        for (i, (bytes, cell)) in data
            .chunks_exact(8)
            .zip(out.chunks_exact_mut(width))
            .enumerate()
        {
            let raw: [u8; 8] = bytes
                .try_into()
                .map_err(|_| crate::error_context::runtime("invalid date tick"))?;
            let ticks = i64::from_ne_bytes(raw);
            let selected = target
                .map(|t| {
                    t.0.get(i).ok_or_else(|| {
                        crate::error_context::type_error("query targets cannot be missing")
                    })
                })
                .transpose()?;
            if ticks == i64::MIN {
                if boolean {
                    cell[0] = 0;
                } else {
                    cell.copy_from_slice(&0_i64.to_ne_bytes());
                    super::common::missing_mask(&mut mask, count, i)?;
                }
                continue;
            }
            let source = i128::from(ticks) * unit.nanos();
            if Q == 107 || Q == 108 {
                let current = if let Some(current) = now {
                    current
                } else {
                    let utc = super::factory::system_nanos(std::time::SystemTime::now())?;
                    let current = if zone.is_some() {
                        utc
                    } else {
                        let local = super::common::local_zone(py)?;
                        let fixed =
                            super::common::fixed_offset(py, &Zone::Object(local.clone().unbind()))?;
                        super::zones::utc_wall(utc, &local, fixed)?
                    };
                    now = Some(current);
                    current
                };
                cell[0] = u8::from(if Q == 107 {
                    source < current
                } else {
                    source > current
                });
                continue;
            }
            if Q == 12 || Q == 106 {
                let value = if let Some(zone) = zone {
                    if let Some(offset) = fixed {
                        if Q == 12 {
                            Some(offset)
                        } else {
                            if fixed_dst.is_none() {
                                fixed_dst = Some(crate::epoch::offset_us(
                                    &zone
                                        .call_method1("dst", (py.None(),))
                                        .map_err(crate::error_context::external)?,
                                )?);
                            }
                            fixed_dst.flatten()
                        }
                    } else {
                        let (local, offset, _) = super::zones::utc_local(source, zone)?;
                        if Q == 12 {
                            Some(offset)
                        } else {
                            crate::epoch::offset_us(
                                &zone
                                    .call_method1("dst", (&local,))
                                    .map_err(crate::error_context::external)?,
                            )?
                        }
                    }
                } else {
                    None
                };
                if Q == 106 {
                    cell[0] = u8::from(value.is_some_and(|v| v != 0));
                } else {
                    cell.copy_from_slice(
                        &value.map_or(0, |v| v.div_euclid(1_000_000)).to_ne_bytes(),
                    );
                    if value.is_none() {
                        super::common::missing_mask(&mut mask, count, i)?;
                    }
                }
                continue;
            }
            let wall = if let Some(offset) = fixed {
                source + i128::from(offset) * 1000
            } else {
                super::zones::utc_wall(
                    source,
                    zone.ok_or_else(|| crate::error_context::runtime("missing query region"))?,
                    None,
                )?
            };
            let value = fact::<Q>(wall, selected, &mut cached).map_err(|e| {
                crate::error_context::location(py, PyErr::from(e), entry, &format!("result[{i}]"))
            })?;
            if boolean {
                cell[0] = u8::from(value != 0);
            } else {
                cell.copy_from_slice(&value.to_ne_bytes());
            }
        }
        Ok(())
    })?;
    Ok((bytes, mask.map(|m| PyBytes::new(py, &m))))
}

fn iso_table<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: Unit,
    zone: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<Output<'py>> {
    let count = data.len() / 8;
    let size = count
        .checked_mul(24)
        .ok_or_else(|| crate::error_context::overflow("ISO table is too large"))?;
    let fixed = super::common::fixed_offset(
        py,
        &zone.map_or(Zone::Naive, |z| Zone::Object(z.clone().unbind())),
    )?;
    let mut cached = None;
    let mut mask = None;
    let packed = PyBytes::new_with(py, size, |out| {
        for (i, (bytes, row)) in data
            .chunks_exact(8)
            .zip(out.chunks_exact_mut(24))
            .enumerate()
        {
            let tick = i64::from_ne_bytes(
                bytes
                    .try_into()
                    .map_err(|_| crate::error_context::runtime("invalid ISO source tick"))?,
            );
            if tick == i64::MIN {
                super::common::missing_mask(&mut mask, count, i)?;
                continue;
            }
            let value = i128::from(tick) * unit.nanos();
            let wall = if let Some(offset) = fixed {
                value + i128::from(offset) * 1000
            } else {
                super::zones::utc_wall(
                    value,
                    zone.ok_or_else(|| crate::error_context::runtime("missing ISO region"))?,
                    None,
                )?
            };
            let result = (|| {
            let day = i64::try_from(wall.div_euclid(NS_DAY) + 719_163)
                .map_err(|_| crate::error_context::overflow("calendar day overflow"))?;
            if let Some((previous, fields)) = cached
                && previous == day
            {
                return Ok(fields);
            }
            let [year, _, _] = crate::calendar::from_ordinal(day)
                .map_err(crate::error_context::overflow)?;
            let result = iso_at(year, day)?;
            if !(0..=i64::from(u32::MAX)).contains(&result[0]) {
                return Err(crate::error_context::overflow(
                    "ISO year is outside the UInt32 range; use isoyear() for signed calendar years",
                ));
            }
            cached = Some((day, result));
            Ok(result)
        })()
        .map_err(|e| crate::error_context::location(py, e, entry, &format!("result[{i}]")))?;
            for (cell, value) in row.chunks_exact_mut(8).zip(result) {
                cell.copy_from_slice(&value.to_ne_bytes());
            }
        }
        Ok(())
    })?;
    Ok((packed, mask.map(|m| PyBytes::new(py, &m))))
}
#[pyfunction]
#[pyo3(signature=(data,unit,zone,query,entry,target=None))]
fn _pddt_query<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    query: u8,
    entry: &str,
    target: Option<PyRef<'_, Integers>>,
) -> PyResult<Output<'py>> {
    if data.len() % 8 != 0 {
        return Err(crate::error_context::runtime("invalid query source buffer"));
    }
    let unit = Unit::parse(unit)?;
    let zone = zone.filter(|v| !v.is_none());
    if query == 201 {
        return iso_table(py, data, unit, zone, entry);
    }
    if let Some(target) = &target {
        if target.0.len().is_some_and(|n| n != data.len() / 8) {
            return Err(crate::error_context::value_error(
                "query target length must equal source length",
            ));
        }
    }
    let target = target.as_deref();
    macro_rules! dispatch {($($id:literal),*)=>{match query {$($id=>loop_query::<$id>(py,data,unit,zone,target,entry),)*_=>Err(crate::error_context::runtime("unknown native query"))}};}
    dispatch!(
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 100, 101, 102, 103, 104, 105, 106, 107, 108, 200
    )
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_query, module)?)
}
