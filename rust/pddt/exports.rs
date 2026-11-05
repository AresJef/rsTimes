//! Direct calendar tables and final scalar/string exports over native date ticks.
use super::common::NS_DAY;
use crate::epoch::{Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::{
    PyBytes, PyDate, PyDateTime, PyDict, PyList, PyString, PyTime, PyTimeAccess, PyTzInfo,
};

struct View<'a, 'py> {
    zone: Option<&'a Bound<'py, PyAny>>,
    fixed: Option<i64>,
}
struct Local<'py> {
    nanos: i128,
    offset: Option<i64>,
    fold: bool,
    carrier: Option<Bound<'py, PyDateTime>>,
}
impl<'a, 'py> View<'a, 'py> {
    fn new(py: Python<'py>, zone: Option<&'a Bound<'py, PyAny>>) -> PyResult<Self> {
        let zone = zone.filter(|z| !z.is_none());
        let fixed = super::common::fixed_offset(
            py,
            &zone.map_or(Zone::Naive, |z| Zone::Object(z.clone().unbind())),
        )?;
        Ok(Self { zone, fixed })
    }
    fn local(&self, nanos: i128) -> PyResult<Local<'py>> {
        if let Some(offset) = self.fixed {
            Ok(Local {
                nanos: nanos + i128::from(offset) * 1000,
                offset: self.zone.map(|_| offset),
                fold: false,
                carrier: None,
            })
        } else {
            let zone = self
                .zone
                .ok_or_else(|| crate::error_context::runtime("missing export region"))?;
            let (carrier, offset, nanos) = super::zones::utc_local(nanos, zone)?;
            Ok(Local {
                nanos,
                offset: Some(offset),
                fold: carrier.get_fold(),
                carrier: Some(carrier),
            })
        }
    }
    fn dst(
        &self,
        py: Python<'py>,
        local: &Local<'py>,
        fixed: &mut Option<Option<i64>>,
    ) -> PyResult<Option<i64>> {
        let Some(zone) = self.zone else {
            return Ok(None);
        };
        if let Some(carrier) = &local.carrier {
            return crate::epoch::offset_us(
                &zone
                    .call_method1("dst", (carrier,))
                    .map_err(crate::error_context::external)?,
            );
        }
        if let Some(value) = fixed {
            return Ok(*value);
        }
        let value = crate::epoch::offset_us(
            &zone
                .call_method1("dst", (py.None(),))
                .map_err(crate::error_context::external)?,
        )?;
        *fixed = Some(value);
        Ok(value)
    }
}

use crate::temporal_output::{iso_text, seconds_float};

type Output<'py> = (Bound<'py, PyBytes>, Option<Bound<'py, PyBytes>>);
#[pyfunction]
#[pyo3(signature=(data,unit,zone,kind,entry,utc=false))]
fn _pddt_export<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    kind: u8,
    entry: &str,
    utc: bool,
) -> PyResult<Output<'py>> {
    if !data.len().is_multiple_of(8) || kind > 5 {
        return Err(crate::error_context::runtime("invalid export metadata"));
    }
    let unit = Unit::parse(unit)?;
    let count = data.len() / 8;
    let aware = zone.is_some_and(|z| !z.is_none());
    let utc_only = kind == 5
        || (kind == 0 || kind == 1) && utc
        || kind == 3 && zone.is_some_and(|z| !z.is_none());
    let view = View::new(py, if utc_only { None } else { zone })?;
    let size = count
        .checked_mul(if kind >= 4 { 72 } else { 8 })
        .ok_or_else(|| crate::error_context::overflow("export array is too large"))?;
    let mut mask = None;
    let mut fixed_dst = None;
    let mut local_zone = None;
    let packed = PyBytes::new_with(py, size, |out| {
        for (i, (raw, out)) in data
            .as_chunks::<8>()
            .0
            .iter()
            .zip(out.chunks_exact_mut(if kind >= 4 { 72 } else { 8 }))
            .enumerate()
        {
            let tick = i64::from_ne_bytes(*raw);
            if tick == i64::MIN {
                if kind == 0 || kind == 3 {
                    out.copy_from_slice(&f64::NAN.to_ne_bytes());
                } else {
                    out.fill(0);
                    super::common::missing_mask(&mut mask, count, i)?;
                }
                continue;
            }
            let ns = i128::from(tick) * unit.nanos();
            let result = (|| -> PyResult<()> {
                let local = if utc_only {
                    Local {
                        nanos: ns,
                        offset: None,
                        fold: false,
                        carrier: None,
                    }
                } else {
                    view.local(ns)?
                };
                let ns = if kind == 3 && !aware {
                    if local_zone.is_none() {
                        let zone = super::common::local_zone(py)?;
                        let fixed =
                            super::common::fixed_offset(py, &Zone::Object(zone.clone().unbind()))?;
                        local_zone = Some((zone, fixed));
                    }
                    let (zone, fixed) = local_zone
                        .as_ref()
                        .ok_or_else(|| crate::error_context::runtime("missing local timezone"))?;
                    if let Some(offset) = fixed {
                        local.nanos - i128::from(*offset) * 1000
                    } else {
                        match super::zones::candidates(local.nanos, zone)? {
                            super::zones::Candidates::One(v) => v,
                            super::zones::Candidates::Repeated(..) => {
                                return Err(crate::error_context::value_error(
                                    "local time occurs twice; call tz_localize with an explicit ambiguous policy before timestamp()",
                                ));
                            }
                            super::zones::Candidates::Gap { .. } => {
                                return Err(crate::error_context::value_error(
                                    "local time does not exist; call tz_localize with an explicit nonexistent policy before timestamp()",
                                ));
                            }
                        }
                    }
                } else {
                    local.nanos
                };
                if kind == 0 || kind == 3 {
                    out.copy_from_slice(&seconds_float(ns, 1_000_000_000).to_ne_bytes());
                } else if kind == 1 {
                    let value = i64::try_from(ns.div_euclid(1000)).map_err(|_| {
                        crate::error_context::overflow("microseconds exceed int64 capacity")
                    })?;
                    out.copy_from_slice(&value.to_ne_bytes());
                } else if kind == 2 {
                    let value = i64::try_from(ns.div_euclid(NS_DAY) + 719_163).map_err(|_| {
                        crate::error_context::overflow("ordinal exceeds int64 capacity")
                    })?;
                    out.copy_from_slice(&value.to_ne_bytes());
                } else {
                    let f = super::operations::fields(ns)?;
                    let ordinal = crate::calendar::checked_ordinal(f[0], f[1], f[2])
                        .map_err(crate::error_context::overflow)?;
                    let start = crate::calendar::checked_ordinal(f[0], 1, 1)
                        .map_err(crate::error_context::overflow)?;
                    let dst = if kind == 5 {
                        0
                    } else {
                        view.dst(py, &local, &mut fixed_dst)?
                            .map_or(-1, |v| i64::from(v != 0))
                    };
                    let values = [
                        f[0],
                        f[1],
                        f[2],
                        f[3],
                        f[4],
                        f[5],
                        (ordinal - 1).rem_euclid(7),
                        ordinal - start + 1,
                        dst,
                    ];
                    for (cell, value) in out.as_chunks_mut::<8>().0.iter_mut().zip(values) {
                        cell.copy_from_slice(&value.to_ne_bytes());
                    }
                }
                Ok(())
            })();
            result.map_err(|e| {
                crate::error_context::location(py, e, entry, &format!("result[{i}]"))
            })?;
        }
        Ok(())
    })?;
    Ok((packed, mask.map(|m| PyBytes::new(py, &m))))
}

struct ObjectOptions<'a, 'py> {
    class: Option<&'a Bound<'py, PyAny>>,
    sep: &'a str,
    precision: u8,
    group: usize,
}
fn objects<'py, const K: u8>(
    py: Python<'py>,
    data: &[u8],
    unit: Unit,
    view: View<'_, 'py>,
    options: &ObjectOptions<'_, 'py>,
    entry: &str,
) -> PyResult<Bound<'py, PyList>> {
    let out = PyList::empty(py);
    let mut fixed_name = None;
    for (i, raw) in data.as_chunks::<8>().0.iter().enumerate() {
        let tick = i64::from_ne_bytes(*raw);
        if tick == i64::MIN {
            out.append(if K <= 3 {
                super::prepare::nat(py)?
            } else {
                py.None().into_bound(py)
            })?;
            continue;
        }
        let result = (|| -> PyResult<Bound<'py, PyAny>> {
            if K == 4 && view.zone.is_none() {
                return Ok(py.None().into_bound(py));
            }
            let local = view.local(i128::from(tick) * unit.nanos())?;
            if K == 4 {
                let zone = view
                    .zone
                    .ok_or_else(|| crate::error_context::runtime("missing tzname zone"))?;
                let name = if let Some(carrier) = &local.carrier {
                    zone.call_method1("tzname", (carrier,))
                        .map_err(crate::error_context::external)?
                } else if let Some(name) = &fixed_name {
                    Bound::clone(name)
                } else {
                    let name = zone
                        .call_method1("tzname", (py.None(),))
                        .map_err(crate::error_context::external)?;
                    fixed_name = Some(name.clone());
                    name
                };
                if !name.is_none() && !name.is_instance_of::<PyString>() {
                    return Err(crate::error_context::type_error(
                        "tzname() must return a string or None",
                    ));
                }
                return Ok(name);
            }
            let f = super::operations::fields(local.nanos)?;
            if K == 0 {
                let class = options
                    .class
                    .ok_or_else(|| crate::error_context::runtime("missing Pydt output class"))?;
                let fields = [f[0], f[1], f[2], f[3], f[4], f[5], f[6]];
                let none = py.None().into_bound(py);
                let zone = view.zone.unwrap_or(&none);
                if let Some(value) =
                    crate::pydt::try_from_fields(class, fields, zone, i32::from(local.fold))?
                {
                    return Ok(value);
                }
                let kwargs = PyDict::new(py);
                kwargs.set_item("tzinfo", zone)?;
                kwargs.set_item("fold", local.fold)?;
                return class
                    .call((f[0], f[1], f[2], f[3], f[4], f[5], f[6]), Some(&kwargs))
                    .map_err(crate::error_context::external);
            }
            if K == 1 {
                if !(1..=9999).contains(&f[0]) {
                    return Err(crate::error_context::value_error(
                        "year must be in 1 through 9999 for a Python date",
                    ));
                }
                return PyDate::new(py, f[0] as i32, f[1] as u8, f[2] as u8).map(Bound::into_any);
            }
            if K == 2 || K == 3 {
                let zone = if K == 3 {
                    view.zone.map(|z| z.cast::<PyTzInfo>()).transpose()?
                } else {
                    None
                };
                return PyTime::new_with_fold(
                    py,
                    f[3] as u8,
                    f[4] as u8,
                    f[5] as u8,
                    f[6] as u32,
                    zone,
                    local.fold,
                )
                .map(Bound::into_any);
            }
            if K == 5 {
                return Ok(PyString::new(
                    py,
                    &iso_text(f, options.sep, options.precision, local.offset),
                )
                .into_any());
            }
            let ordinal = crate::calendar::checked_ordinal(f[0], f[1], f[2])
                .map_err(crate::error_context::overflow)?;
            let weekday = (ordinal - 1).rem_euclid(7) as usize;
            if K == 6 {
                const DAYS: [&str; 7] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
                const MONTHS: [&str; 12] = [
                    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                    "Dec",
                ];
                return Ok(PyString::new(
                    py,
                    &format!(
                        "{} {} {:2} {:02}:{:02}:{:02} {:04}",
                        DAYS[weekday],
                        MONTHS[(f[1] - 1) as usize],
                        f[2],
                        f[3],
                        f[4],
                        f[5],
                        f[0]
                    ),
                )
                .into_any());
            }
            let position = if K == 7 {
                (f[1] - 1) as usize
            } else {
                12 + weekday
            };
            crate::localization::calendar_name(py, options.group, position).map(Bound::into_any)
        })();
        out.append(
            result.map_err(|e| {
                crate::error_context::location(py, e, entry, &format!("result[{i}]"))
            })?,
        )?;
    }
    Ok(out)
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One final object export boundary with once-prepared output options"
)]
#[pyo3(signature=(data,unit,zone,kind,entry,class=None,option=None,timespec=None))]
fn _pddt_objects<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    kind: u8,
    entry: &str,
    class: Option<&Bound<'py, PyAny>>,
    option: Option<&Bound<'py, PyAny>>,
    timespec: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyList>> {
    if !data.len().is_multiple_of(8) {
        return Err(crate::error_context::runtime(
            "invalid object export buffer",
        ));
    }
    let unit = Unit::parse(unit)?;
    let view = View::new(py, zone)?;
    let mut options = ObjectOptions {
        class,
        sep: "T",
        precision: 0,
        group: 0,
    };
    if kind == 5 {
        options.sep = if let Some(sep) = option {
            sep.cast::<PyString>()
                .map_err(|_| crate::error_context::type_error("sep must be one Unicode character"))?
                .to_str()?
        } else {
            "T"
        };
        if options.sep.chars().count() != 1 {
            return Err(crate::error_context::value_error(
                "sep must be one Unicode character",
            ));
        }
        let spec = if let Some(spec) = timespec {
            spec.cast::<PyString>()
                .map_err(|_| crate::error_context::type_error("timespec must be a string"))?
                .to_str()?
        } else {
            "auto"
        };
        options.precision = match spec {
            "auto" => 0,
            "hours" | "h" => 1,
            "minutes" | "m" | "min" => 2,
            "seconds" | "s" => 3,
            "milliseconds" | "ms" => 4,
            "microseconds" | "us" => 5,
            "nanoseconds" | "ns" => 6,
            _ => {
                return Err(crate::error_context::value_error(
                    "unknown ISO timespec; use auto, hours, minutes, seconds, milliseconds, microseconds or nanoseconds",
                ));
            }
        };
    } else if kind == 7 || kind == 8 {
        options.group = crate::localization::name_group(py, option)?;
    }
    macro_rules! dispatch{($($id:literal),*)=>{match kind{$($id=>objects::<$id>(py,data,unit,view,&options,entry),)*_=>Err(crate::error_context::runtime("unknown object output kind"))}};}
    dispatch!(0, 1, 2, 3, 4, 5, 6, 7, 8)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_export, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_objects, module)?)
}
