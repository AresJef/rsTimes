//! Prepare separate date/clock sources once and assemble one final native column.
use super::arguments::{Column, date_missing, length};
use super::common::{NS_DAY, Rows, finish};
use crate::date_parts::{Piece, Reader};
use crate::epoch::{self, Parsed, Unit, Zone};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};

#[pyclass(frozen, name = "_PddtParts")]
struct Parts {
    values: Column<Option<Piece>>,
    zones: Vec<Zone>,
    today: bool,
    declared_zone: Option<usize>,
}

fn clone_zone(py: Python<'_>, zone: &Zone) -> Zone {
    match zone {
        Zone::Naive => Zone::Naive,
        Zone::Offset(v) => Zone::Offset(*v),
        Zone::Object(v) => Zone::Object(v.clone_ref(py)),
    }
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Once-prepared date or clock component"
)]
#[pyo3(signature=(data,resolver,clock,column,entry,buffer=None,source=None,multiplier=1,source_zone=None,time_buffer=false,mask=None))]
fn _pddt_parts<'py>(
    data: &Bound<'py, PyAny>,
    resolver: &Bound<'py, PyAny>,
    clock: bool,
    column: bool,
    entry: &str,
    buffer: Option<&[u8]>,
    source: Option<&str>,
    multiplier: i32,
    source_zone: Option<&Bound<'py, PyAny>>,
    time_buffer: bool,
    mask: Option<&[u8]>,
) -> PyResult<Parts> {
    let py = data.py();
    let parameter = if clock { "time" } else { "date" };
    let mut reader = Reader::new(clock, resolver);
    if let Some(bytes) = buffer {
        if bytes.len() % 8 != 0 || multiplier < 1 {
            return Err(crate::error_context::runtime(
                "invalid date component buffer",
            ));
        }
        let validity = super::validity::TemporalValidity::new(mask, bytes.len() / 8)?;
        let code = if time_buffer {
            10
        } else {
            super::dates::numpy_code(source.unwrap_or(""))?
        };
        let source_zone = source_zone.filter(|z| !z.is_none());
        let id = if let Some(zone) = source_zone {
            reader.zone(zone.clone())?
        } else {
            0
        };
        let fixed = super::common::fixed_offset(py, &reader.zones[id])?;
        let mut values = Vec::with_capacity(bytes.len() / 8);
        for (i, bytes) in bytes.chunks_exact(8).enumerate() {
            let raw: [u8; 8] = bytes
                .try_into()
                .map_err(|_| crate::error_context::runtime("invalid date component bytes"))?;
            let ticks = i64::from_ne_bytes(raw);
            if validity.missing(i, ticks) {
                values.push(None);
                continue;
            }
            let value = (|| -> PyResult<i128> {
                if time_buffer {
                    if !clock || !(0..NS_DAY).contains(&i128::from(ticks)) {
                        return Err(crate::error_context::value_error(
                            "a native Time clock must be within one day",
                        ));
                    }
                    return Ok(i128::from(ticks));
                }
                let mut ns = epoch::native_datetime_ticks(ticks, code, multiplier)?.nanos;
                if let Some(zone) = source_zone {
                    ns = super::zones::utc_wall(ns, zone, fixed)?;
                }
                Ok(if clock {
                    ns.rem_euclid(NS_DAY)
                } else {
                    ns.div_euclid(NS_DAY)
                })
            })()
            .map_err(|e| {
                crate::error_context::location(py, e, entry, &format!("{parameter}[{i}]"))
            })?;
            values.push(Some(Piece {
                value,
                zone: if clock { id } else { 0 },
            }));
        }
        return Ok(Parts {
            values: Column::Values(values),
            zones: reader.zones,
            today: false,
            declared_zone: if clock && source_zone.is_some() {
                Some(id)
            } else {
                None
            },
        });
    }
    let scalar = !column
        && (data.is_none()
            || date_missing(data)?
            || data.is_instance_of::<PyString>()
            || unsafe {
                ffi::PyDate_Check(data.as_ptr()) != 0
                    || ffi::PyTime_Check(data.as_ptr()) != 0
                    || ffi::PyIndex_Check(data.as_ptr()) != 0
            }
            || crate::numeric::supported_float(data)
            || crate::numpy_scalar::datetime_ticks(data)?.is_some());
    let today = scalar && data.is_none() && !clock;
    let values = if scalar {
        if data.is_none() {
            Column::Scalar(Some(Piece { value: 0, zone: 0 }))
        } else {
            Column::Scalar(
                reader
                    .read(data)
                    .map_err(|e| crate::error_context::argument(py, e, entry, parameter, data))?,
            )
        }
    } else {
        let mut values = Vec::new();
        for (i, item) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let item = item
                .map_err(crate::error_context::external)
                .map_err(|e| crate::error_context::item(py, e, entry, parameter, i, None, true))?;
            values.push(reader.read(&item).map_err(|e| {
                crate::error_context::item(py, e, entry, parameter, i, Some(&item), false)
            })?);
        }
        Column::Values(values)
    };
    let declared_zone = if clock {
        match &values {
            Column::Scalar(Some(piece)) => Some(piece.zone),
            _ => None,
        }
    } else {
        None
    };
    Ok(Parts {
        values,
        zones: reader.zones,
        today,
        declared_zone,
    })
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared date and clock pieces plus output policy"
)]
#[pyo3(signature=(date,time,policy,local,size=None,unit=None,target=None,entry="Pddt.combine"))]
fn _pddt_combine<'py>(
    py: Python<'py>,
    date: PyRef<'_, Parts>,
    time: PyRef<'_, Parts>,
    policy: PyRef<'_, super::zones::Policies>,
    local: &Bound<'py, PyAny>,
    size: Option<usize>,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let length = length([date.values.len(), time.values.len()], size)?;
    let requested = unit.map(Unit::parse).transpose()?;
    let replace = target.is_some_and(|t| !t.is_none());
    let mut today = None;
    let mut rows = Rows::new(Unit::Microsecond);
    rows.reserve(length)?;
    if length == 0 {
        if let Column::Scalar(Some(clock)) = &time.values {
            if !replace {
                rows.zones.push(clone_zone(py, &time.zones[clock.zone]));
                rows.empty_zone = rows.zones.len() - 1;
            }
            if clock.value.rem_euclid(1000) != 0 {
                rows.unit = Unit::Nanosecond;
            }
        }
    }
    for i in 0..length {
        let (Some(day), Some(clock)) = (date.values.get(i), time.values.get(i)) else {
            rows.missing();
            continue;
        };
        let day = if date.today {
            if let Some(day) = today {
                day
            } else {
                let zone = local.call0().map_err(crate::error_context::external)?;
                let fixed = super::common::fixed_offset(py, &Zone::Object(zone.clone().unbind()))?;
                let day = super::zones::utc_wall(
                    super::factory::system_nanos(std::time::SystemTime::now())?,
                    &zone,
                    fixed,
                )?
                .div_euclid(NS_DAY);
                today = Some(day);
                day
            }
        } else {
            day.value
        };
        let nanos = day
            .checked_mul(NS_DAY)
            .and_then(|v| v.checked_add(clock.value))
            .ok_or_else(|| crate::error_context::overflow("combined date exceeds native range"))?;
        let zone = if replace {
            Zone::Naive
        } else {
            clone_zone(py, &time.zones[clock.zone])
        };
        rows.push(
            py,
            Parsed {
                nanos,
                unit: if clock.value.rem_euclid(1000) == 0 {
                    Unit::Microsecond
                } else {
                    Unit::Nanosecond
                },
                zone,
            },
            false,
        )?;
    }
    // No valid combined row may reach push (empty/all-null date or clock),
    // but a typed clock still declares a source zone. This O(1) fallback does
    // not rescan data or change the actual-precision default unit.
    if !replace && rows.zones.len() == 1 {
        if let Some(id) = time.declared_zone.filter(|&id| id != 0) {
            rows.zones.push(clone_zone(py, &time.zones[id]));
            rows.empty_zone = rows.zones.len() - 1;
        }
    }
    finish(py, rows, requested, target, entry, &policy)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_parts, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_combine, module)?)
}
