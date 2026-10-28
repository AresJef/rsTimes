//! Owned batch fields and checked final date-buffer materialization.
use crate::epoch::{Parsed, Unit, Zone};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::PyBytes;

pub(super) const NS_DAY: i128 = 86_400_000_000_000;
static RESOLVE_ZONE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// Reserve a source-sized output without turning allocation failure into abort.
pub(super) fn vector<T>(count: usize) -> PyResult<Vec<T>> {
    let mut values = Vec::new();
    values.try_reserve_exact(count).map_err(|_| {
        pyo3::exceptions::PyMemoryError::new_err("cannot allocate date-query output")
    })?;
    Ok(values)
}

pub(super) fn missing_mask(mask: &mut Option<Vec<u8>>, count: usize, index: usize) -> PyResult<()> {
    if mask.is_none() {
        let mut values = vector(count)?;
        values.resize(count, 0);
        *mask = Some(values);
    }
    if let Some(mask) = mask {
        mask[index] = 1;
    }
    Ok(())
}

pub(super) fn register_zone_resolver(py: Python<'_>, resolver: Py<PyAny>) {
    let _ = RESOLVE_ZONE.set(py, resolver);
}

pub(super) fn local_zone(py: Python<'_>) -> PyResult<Bound<'_, PyAny>> {
    RESOLVE_ZONE
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("Pddt timezone resolver is not registered"))?
        .bind(py)
        .call1(("local",))
        .map_err(crate::error_context::external)
}

/// Each row holds only native metadata; live Python zones are shared by identity.
#[derive(Clone, Copy)]
pub(super) struct Source {
    pub zone: usize,
    pub instant: bool,
}

pub(super) struct Rows {
    pub values: Vec<Option<i128>>,
    pub sources: Vec<Source>,
    pub zones: Vec<Zone>,
    pub unit: Unit,
    /// Prepared scalar metadata survives broadcasting to zero output rows.
    pub empty_zone: usize,
    aliases: Vec<(Py<PyAny>, usize)>,
}
impl Rows {
    pub fn new(unit: Unit) -> Self {
        Self {
            values: Vec::new(),
            sources: Vec::new(),
            zones: vec![Zone::Naive],
            unit,
            empty_zone: 0,
            aliases: Vec::new(),
        }
    }
    pub fn reserve(&mut self, count: usize) -> PyResult<()> {
        if count
            .checked_mul(std::mem::size_of::<Option<i128>>())
            .is_none_or(|n| n > isize::MAX as usize)
        {
            return Err(crate::error_context::overflow(
                "requested date array is too large",
            ));
        }
        self.values
            .try_reserve_exact(count)
            .map_err(|_| pyo3::exceptions::PyMemoryError::new_err("cannot allocate date values"))?;
        self.sources.try_reserve_exact(count).map_err(|_| {
            pyo3::exceptions::PyMemoryError::new_err("cannot allocate date source metadata")
        })?;
        Ok(())
    }
    pub fn missing(&mut self) {
        self.values.push(None);
        self.sources.push(Source {
            zone: 0,
            instant: false,
        });
    }
    pub fn push(&mut self, py: Python<'_>, mut parsed: Parsed, instant: bool) -> PyResult<()> {
        self.unit = self.unit.max(parsed.unit);
        let mut id = None;
        let mut original = None;
        if let Zone::Object(value) = &parsed.zone {
            id = self.zones.iter().position(|zone| matches!(zone, Zone::Object(previous) if previous.bind(py).is(value.bind(py))))
                .or_else(|| self.aliases.iter().find(|(previous, _)| previous.bind(py).is(value.bind(py))).map(|(_, id)| *id));
            let zone = value.bind(py);
            // Standard regions and fixed offsets need no optional dependency adaptation.
            let standard_fixed = unsafe {
                ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
            };
            if id.is_none()
                && !standard_fixed
                && !crate::pydt::is_zoneinfo_instance(zone)
                && crate::localization::loaded_pytz(zone)?
            {
                let resolver = RESOLVE_ZONE.get(py).ok_or_else(|| {
                    crate::error_context::runtime("Pddt timezone resolver is not registered")
                })?;
                let resolved = resolver
                    .bind(py)
                    .call1((zone,))
                    .map_err(crate::error_context::external)?;
                original = Some(value.clone_ref(py));
                parsed.zone = Zone::Object(resolved.unbind());
            }
        }
        for (i, previous) in self.zones.iter().enumerate() {
            if id.is_some() {
                break;
            }
            if same_zone(py, previous, &parsed.zone)? {
                id = Some(i);
                break;
            }
        }
        let zone = id.unwrap_or_else(|| {
            self.zones.push(parsed.zone);
            self.zones.len() - 1
        });
        if let Some(original) = original {
            self.aliases.push((original, zone));
        }
        self.values.push(Some(parsed.nanos));
        self.sources.push(Source { zone, instant });
        Ok(())
    }
}

/// Fixed zones are prepared once per zone, never once per date.
pub(super) fn fixed_offset(py: Python<'_>, zone: &Zone) -> PyResult<Option<i64>> {
    match zone {
        Zone::Naive => Ok(Some(0)),
        Zone::Offset(us) => Ok(Some(*us)),
        Zone::Object(value) => {
            let zone = value.bind(py);
            // SAFETY: datetime's initialized capsule owns its standard UTC object.
            let fixed = unsafe {
                ffi::Py_TYPE(zone.as_ptr()) == ffi::Py_TYPE((*ffi::PyDateTimeAPI()).TimeZone_UTC)
            };
            if fixed {
                return crate::epoch::offset_us(
                    &zone
                        .call_method1("utcoffset", (py.None(),))
                        .map_err(crate::error_context::external)?,
                );
            }
            crate::pydt::fixed_zoneinfo_offset(zone)
        }
    }
}

pub(super) fn same_zone(py: Python<'_>, a: &Zone, b: &Zone) -> PyResult<bool> {
    match (a, b) {
        (Zone::Naive, Zone::Naive) => Ok(true),
        (Zone::Offset(a), Zone::Offset(b)) => Ok(a == b),
        (Zone::Object(a), Zone::Object(b)) if a.bind(py).is(b.bind(py)) => Ok(true),
        (Zone::Naive, _) | (_, Zone::Naive) => Ok(false),
        _ => {
            let a_key = match a {
                Zone::Object(value) => crate::pydt::zoneinfo_key(value.bind(py))?,
                _ => None,
            };
            let b_key = match b {
                Zone::Object(value) => crate::pydt::zoneinfo_key(value.bind(py))?,
                _ => None,
            };
            match (a_key, b_key) {
                (Some(Some(a)), Some(Some(b))) => return Ok(a == b),
                (Some(_), _) | (_, Some(_)) => return Ok(false),
                (None, None) => {}
            }
            let (a, b) = (fixed_offset(py, a)?, fixed_offset(py, b)?);
            Ok(a.is_some() && a == b)
        }
    }
}

pub(super) use crate::epoch::zone_object;

/// Pack only after every row succeeds; reserved NaT cannot swallow a valid value.
pub(super) fn pack<'py>(
    py: Python<'py>,
    values: &[Option<i128>],
    unit: Unit,
    lossless: bool,
    entry: &str,
) -> PyResult<Bound<'py, PyBytes>> {
    let size = values
        .len()
        .checked_mul(8)
        .ok_or_else(|| crate::error_context::overflow("date array is too large"))?;
    PyBytes::new_with(py, size, |bytes| {
        for (i, (value, out)) in values.iter().zip(bytes.chunks_exact_mut(8)).enumerate() {
            let tick = if let Some(ns) = value {
                if lossless && ns.rem_euclid(unit.nanos()) != 0 {
                    return Err(crate::error_context::location(
                        py,
                        crate::error_context::value_error(
                            "cannot preserve this date at the requested unit; choose a finer unit",
                        ),
                        entry,
                        &format!("result[{i}]"),
                    ));
                }
                i64::try_from(ns.div_euclid(unit.nanos())).ok().filter(|v|*v!=i64::MIN)
                    .ok_or_else(||crate::error_context::location(py,crate::error_context::overflow(
                        "date is outside the requested unit; explicitly choose a coarser unit"),entry,&format!("result[{i}]")))?
            } else {
                i64::MIN
            };
            out.copy_from_slice(&tick.to_ne_bytes());
        }
        Ok(())
    })
}

/// Finish known instants and naive/fixed local fields before final pandas wrapping.
pub(super) fn finish<'py>(
    py: Python<'py>,
    rows: Rows,
    requested: Option<Unit>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
    policy: &super::zones::Policies,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    finalize::<true>(py, rows, requested, target, entry, policy)
}

/// Formatted fractional precision is intentionally reduced only at final output.
pub(super) fn finish_truncated<'py>(
    py: Python<'py>,
    rows: Rows,
    requested: Option<Unit>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
    policy: &super::zones::Policies,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    finalize::<false>(py, rows, requested, target, entry, policy)
}

fn finalize<'py, const LOSSLESS: bool>(
    py: Python<'py>,
    mut rows: Rows,
    requested: Option<Unit>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
    policy: &super::zones::Policies,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let selected = if let Some(target) = target.filter(|t| !t.is_none()) {
        rows.zones.push(Zone::Object(target.clone().unbind()));
        rows.zones.len() - 1
    } else {
        let mut selected = None;
        for (value, source) in rows.values.iter().zip(&rows.sources) {
            if value.is_none() {
                continue;
            }
            if let Some(previous) = selected {
                if previous != source.zone {
                    return Err(crate::error_context::value_error(
                        "cannot combine naive dates or different timezones; pass an explicit target tz",
                    ));
                }
            } else {
                selected = Some(source.zone);
            }
        }
        selected.unwrap_or(rows.empty_zone)
    };
    let unit = requested.unwrap_or(rows.unit);
    policy.check_len(rows.values.len())?;
    let length = rows.values.len();
    let mut offsets = vec![None; rows.zones.len()];
    let mut pending = Vec::new();
    for (i, (value, source)) in rows.values.iter_mut().zip(&rows.sources).enumerate() {
        let Some(ns) = value else {
            continue;
        };
        if source.instant {
            continue;
        }
        let zone = if source.zone == 0 {
            selected
        } else {
            source.zone
        };
        let offset = if let Some(value) = offsets[zone] {
            value
        } else {
            let value = fixed_offset(py, &rows.zones[zone])?;
            offsets[zone] = Some(value);
            value
        };
        if let Some(offset) = offset {
            *ns = ns
                .checked_sub(i128::from(offset) * 1000)
                .ok_or_else(|| crate::error_context::overflow("date offset overflow"))?;
        } else {
            if policy.infers() && pending.is_empty() {
                pending.resize(length, None);
            }
            let Zone::Object(object) = &rows.zones[zone] else {
                return Err(crate::error_context::runtime(
                    "missing regional timezone object",
                ));
            };
            *value =
                super::zones::localize(*ns, object.bind(py), policy, unit, i, zone, &mut pending)
                    .map_err(|error| {
                    crate::error_context::location(py, error, entry, &format!("result[{i}]"))
                })?;
        }
    }
    if !pending.is_empty() {
        super::zones::infer(&mut rows.values, &pending)?;
    }
    Ok((
        pack(py, &rows.values, unit, LOSSLESS, entry)?,
        unit.name(),
        zone_object(py, &rows.zones[selected])?,
    ))
}
