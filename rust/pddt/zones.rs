//! Explicit array localization policies, prepared once and resolved over native rows.
use crate::epoch::Unit;
use crate::pydt;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDateTime, PyDelta, PyDeltaAccess, PyString};

#[derive(Clone, Copy)]
enum Ambiguous {
    Raise,
    Missing,
    Infer,
    Choose(bool),
    Mask,
}
#[derive(Clone, Copy)]
enum Nonexistent {
    Raise,
    Missing,
    Forward,
    Backward,
    Shift(i128),
}

/// Private immutable boundary object: its row loop contains only native policy data.
#[pyclass(frozen, module = "rstimes._native", name = "_PddtPolicies")]
pub(super) struct Policies {
    ambiguous: Ambiguous,
    mask: Vec<u8>,
    nonexistent: Nonexistent,
}
impl Policies {
    /// A range endpoint uses its first/last row choice; the full generated
    /// mask is independently checked before final localization and slicing.
    pub fn endpoint(&self, end: bool) -> Self {
        let ambiguous = if matches!(self.ambiguous, Ambiguous::Mask) {
            let value = if end {
                self.mask.last()
            } else {
                self.mask.first()
            };
            value.map_or(Ambiguous::Raise, |v| Ambiguous::Choose(*v != 0))
        } else {
            self.ambiguous
        };
        Self {
            ambiguous,
            mask: Vec::new(),
            nonexistent: self.nonexistent,
        }
    }
    pub fn infers(&self) -> bool {
        matches!(self.ambiguous, Ambiguous::Infer)
    }
    pub fn check_len(&self, length: usize) -> PyResult<()> {
        if matches!(self.ambiguous, Ambiguous::Mask) && self.mask.len() != length {
            return Err(crate::error_context::value_error(format!(
                "ambiguous mask length {} does not match data length {length}",
                self.mask.len()
            )));
        }
        Ok(())
    }
}

#[pyfunction]
fn _pddt_policies(
    ambiguous: &Bound<'_, PyAny>,
    nonexistent: &Bound<'_, PyAny>,
) -> PyResult<Policies> {
    let py = ambiguous.py();
    let mut mask = Vec::new();
    let policy=(||->PyResult<Ambiguous>{
        if crate::numeric::is_bool(ambiguous) {
            return crate::numeric::boolean(ambiguous).map(Ambiguous::Choose);
        }
        if let Ok(text)=ambiguous.cast::<PyString>() {
            return match text.to_str()? {
                "raise"=>Ok(Ambiguous::Raise),"NaT"=>Ok(Ambiguous::Missing),"infer"=>Ok(Ambiguous::Infer),
                _=>Err(crate::error_context::value_error("ambiguous must be 'raise', 'NaT', 'infer', a boolean scalar or an equal-length boolean collection")),
            };
        }
        let values=ambiguous.try_iter().map_err(crate::error_context::external)?;
        for (i,value) in values.enumerate() {
            let value=value.map_err(crate::error_context::external)?;
            mask.push(u8::from(crate::numeric::boolean(&value).map_err(|e|
                crate::error_context::item(py,e,"Pddt","ambiguous",i,Some(&value),false))?));
        }
        Ok(Ambiguous::Mask)
    })().map_err(|e|crate::error_context::argument(py,e,"Pddt","ambiguous",ambiguous))?;
    let missing=(||->PyResult<Nonexistent>{
        if let Ok(text)=nonexistent.cast::<PyString>() {
            return match text.to_str()? {
                "raise"=>Ok(Nonexistent::Raise),"NaT"=>Ok(Nonexistent::Missing),
                "shift_forward"=>Ok(Nonexistent::Forward),"shift_backward"=>Ok(Nonexistent::Backward),
                _=>Err(crate::error_context::value_error("nonexistent must be 'raise', 'NaT', 'shift_forward', 'shift_backward' or a timedelta")),
            };
        }
        let delta=nonexistent.cast::<PyDelta>().map_err(|_|crate::error_context::type_error(
            "nonexistent must be a supported string policy or one timedelta"))?;
        let nanos=if let Some(nanos)=crate::interop::duration_nanoseconds(nonexistent)? {nanos}
            else {(i128::from(delta.get_days())*86400+i128::from(delta.get_seconds()))*1_000_000_000
                +i128::from(delta.get_microseconds())*1000};
        Ok(Nonexistent::Shift(nanos))
    })().map_err(|e|crate::error_context::argument(py,e,"Pddt","nonexistent",nonexistent))?;
    Ok(Policies {
        ambiguous: policy,
        mask,
        nonexistent: missing,
    })
}

#[pyfunction]
fn _pddt_check_policies(policy: PyRef<'_, Policies>, length: usize) -> PyResult<()> {
    policy.check_len(length)
}

#[derive(Clone, Copy)]
pub(super) enum Candidates {
    One(i128),
    Repeated(i128, i128),
    Gap { before: i64, after: i64 },
}

/// Standard regional probes use builtin carriers, retaining the independent ns tail.
/// Naive and fixed offsets never enter this function.
pub(super) fn candidates(wall: i128, zone: &Bound<'_, PyAny>) -> PyResult<Candidates> {
    let fields = crate::parser::objects::wide_microsecond_fields(wall.div_euclid(1000))?;
    if !(1..=9999).contains(&fields[0]) {
        return Err(crate::error_context::overflow(
            "this regional tzinfo protocol requires years 1 through 9999; naive and fixed-offset dates retain the full unit range",
        ));
    }
    let carrier = pydt::wall_carrier(zone.py(), fields, zone)?;
    let (before, after) = pydt::regional_offsets(&carrier, zone)?.ok_or_else(|| {
        crate::error_context::value_error(
            "timezone cannot provide a valid UTC offset for this local date",
        )
    })?;
    let left = wall - i128::from(before) * 1000;
    let right = wall - i128::from(after) * 1000;
    if pydt::standard_region(zone)? {
        return if after > before {
            Ok(Candidates::Gap { before, after })
        } else if before == after {
            Ok(Candidates::One(left))
        } else {
            Ok(Candidates::Repeated(left, right))
        };
    }
    // A real custom protocol may not follow ZoneInfo's offset ordering.
    // Validate candidates through the already-consumed offsets, without asking
    // utcoffset a second time for the same probe.
    let valid = |offset| -> PyResult<bool> {
        let back = pydt::roundtrip_offset(&carrier, zone, offset)?;
        Ok(pydt::parts(back.cast::<pyo3::types::PyDateTime>()?) == fields)
    };
    let (a, b) = (valid(before)?, valid(after)?);
    match (a, b) {
        (true, true) if left != right => Ok(Candidates::Repeated(left.min(right), left.max(right))),
        (true, _) => Ok(Candidates::One(left)),
        (_, true) => Ok(Candidates::One(right)),
        _ if before != after => Ok(Candidates::Gap {
            before: before.min(after),
            after: before.max(after),
        }),
        _ => Err(crate::error_context::value_error(
            "timezone cannot confirm any existing local date",
        )),
    }
}

#[derive(Clone, Copy)]
pub(super) struct Pending {
    pub first: i128,
    pub second: i128,
    pub zone: usize,
}

fn choose(
    policy: &Policies,
    candidate: Candidates,
    index: usize,
    zone: usize,
    pending: &mut [Option<Pending>],
) -> PyResult<Option<i128>> {
    match candidate {
        Candidates::One(value) => Ok(Some(value)),
        Candidates::Repeated(first, second) => match policy.ambiguous {
            Ambiguous::Raise => Err(crate::error_context::value_error(
                "local time occurs twice; set ambiguous to True, False, 'infer', 'NaT' or a boolean collection",
            )),
            Ambiguous::Missing => Ok(None),
            Ambiguous::Choose(first_choice) => Ok(Some(if first_choice { first } else { second })),
            Ambiguous::Mask => Ok(Some(if policy.mask[index] != 0 {
                first
            } else {
                second
            })),
            Ambiguous::Infer => {
                pending[index] = Some(Pending {
                    first,
                    second,
                    zone,
                });
                Ok(None)
            }
        },
        Candidates::Gap { .. } => Err(crate::error_context::value_error(
            "the requested nonexistent-time adjustment still lands in a missing local time",
        )),
    }
}

/// Apply one explicit missing-time adjustment, then select actual UTC candidates.
pub(super) fn localize(
    wall: i128,
    zone: &Bound<'_, PyAny>,
    policy: &Policies,
    unit: Unit,
    index: usize,
    zone_id: usize,
    pending: &mut [Option<Pending>],
) -> PyResult<Option<i128>> {
    let initial = candidates(wall, zone)?;
    let Candidates::Gap { before, after } = initial else {
        return choose(policy, initial, index, zone_id, pending);
    };
    let shifted = match policy.nonexistent {
        Nonexistent::Raise => {
            return Err(crate::error_context::value_error(
                "local time does not exist; choose an existing time or set nonexistent to a supported policy",
            ));
        }
        Nonexistent::Missing => return Ok(None),
        Nonexistent::Shift(delta) => wall
            .checked_add(delta)
            .ok_or_else(|| crate::error_context::overflow("nonexistent adjustment overflow"))?,
        Nonexistent::Forward | Nonexistent::Backward => {
            let us = i64::try_from(wall.div_euclid(1000))
                .map_err(|_| crate::error_context::overflow("regional local date overflow"))?;
            let (last, first) = pydt::gap_edges(us, after - before, zone)?;
            if matches!(policy.nonexistent, Nonexistent::Forward) {
                let boundary = i128::from(first) * 1000;
                -(-boundary).div_euclid(unit.nanos()) * unit.nanos()
            } else {
                ((i128::from(last) + 1) * 1000 - 1).div_euclid(unit.nanos()) * unit.nanos()
            }
        }
    };
    choose(policy, candidates(shifted, zone)?, index, zone_id, pending)
}

/// Infer within each consecutive ambiguous run in input order, never by sorting.
/// One non-increasing step separates its first and second actual UTC candidates.
pub(super) fn infer(values: &mut [Option<i128>], pending: &[Option<Pending>]) -> PyResult<()> {
    let mut start = 0;
    while start < pending.len() {
        let Some(first) = pending[start] else {
            start += 1;
            continue;
        };
        let mut end = start + 1;
        while end < pending.len() && pending[end].is_some_and(|v| v.zone == first.zone) {
            end += 1;
        }
        let mut switch = None;
        for i in start + 1..end {
            let previous = pending[i - 1]
                .ok_or_else(|| crate::error_context::runtime("missing inference candidate"))?;
            let current = pending[i]
                .ok_or_else(|| crate::error_context::runtime("missing inference candidate"))?;
            if current.first <= previous.first && switch.replace(i).is_some() {
                return Err(crate::error_context::value_error(
                    "cannot infer local time: multiple clock reversals occur within one repeated interval",
                ));
            }
        }
        let split=switch.ok_or_else(||crate::error_context::value_error(
            "cannot infer this repeated local time from input order; provide a boolean or boolean collection"))?;
        for i in start..end {
            let item = pending[i]
                .ok_or_else(|| crate::error_context::runtime("missing inference candidate"))?;
            values[i] = Some(if i < split { item.first } else { item.second });
        }
        start = end;
    }
    Ok(())
}

/// Convert one known instant to wall coordinates without creating a Pddt.
pub(super) fn utc_wall(ns: i128, zone: &Bound<'_, PyAny>, offset: Option<i64>) -> PyResult<i128> {
    if let Some(offset) = offset {
        return Ok(ns + i128::from(offset) * 1000);
    }
    utc_local(ns, zone).map(|(_, _, wall)| wall)
}

/// Necessary dynamic protocol carrier, offset and wall value from one conversion.
pub(super) fn utc_local<'py>(
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
    let wall = (i128::from(ordinal) - 719_163) * super::common::NS_DAY
        + ((i128::from(f[3]) * 60 + i128::from(f[4])) * 60 + i128::from(f[5])) * 1_000_000_000
        + i128::from(f[6]) * 1000;
    if wall - i128::from(offset) * 1000 != ns.div_euclid(1000) * 1000 {
        return Err(crate::error_context::value_error(
            "tzinfo.fromutc() did not preserve the actual instant",
        ));
    }
    Ok((local, offset, wall + ns.rem_euclid(1000)))
}

/// Decode actual UTC instants to local fields; pure fixed offsets avoid carriers.
#[pyfunction]
fn _pddt_wall<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: &Bound<'py, PyAny>,
    entry: &str,
) -> PyResult<Bound<'py, PyBytes>> {
    let unit = Unit::parse(unit)?;
    if data.len() % 8 != 0 {
        return Err(crate::error_context::value_error("invalid date buffer"));
    }
    let object = crate::epoch::Zone::Object(zone.clone().unbind());
    let mut prepared = None;
    let mut values = Vec::with_capacity(data.len() / 8);
    for (index, bytes) in data.chunks_exact(8).enumerate() {
        let mut raw = [0; 8];
        raw.copy_from_slice(bytes);
        let tick = i64::from_ne_bytes(raw);
        if tick == i64::MIN {
            values.push(None);
            continue;
        }
        let result = (|| -> PyResult<i128> {
            let ns = i128::from(tick) * unit.nanos();
            let offset = if let Some(offset) = prepared {
                offset
            } else {
                let offset = super::common::fixed_offset(py, &object)?;
                prepared = Some(offset);
                offset
            };
            utc_wall(ns, zone, offset)
        })()
        .map_err(|e| crate::error_context::location(py, e, entry, &format!("data[{index}]")))?;
        values.push(Some(result));
    }
    super::common::pack(py, &values, unit, true, entry)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_wall, module)?)?;
    module.add_class::<Policies>()?;
    module.add_function(wrap_pyfunction!(_pddt_policies, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_check_policies, module)?)
}
