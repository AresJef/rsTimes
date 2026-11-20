//! Necessary host timezone protocol shared by explicit Python exits.
use crate::pydt;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{
    PyDateTime, PyDelta, PyDeltaAccess, PyDict, PyType, PyWeakrefMethods, PyWeakrefReference,
};
use std::collections::VecDeque;
use std::sync::Mutex;
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

static ZONE_ORIGIN: PyOnceLock<ZoneOrigins> = PyOnceLock::new();

struct OriginEntry {
    identity: usize,
    owner: Py<PyWeakrefReference>,
    named: bool,
}

struct ZoneOrigins {
    reduce: Py<PyAny>,
    file_error: Py<PyType>,
    entries: Mutex<VecDeque<OriginEntry>>,
}

impl ZoneOrigins {
    /// Cache only the immutable C origin flag. Live capabilities are checked
    /// before every call. Weak owners prevent lifetime changes and pointer
    /// reuse; identity lookup never executes business hash/equality methods.
    fn named(&self, value: &Bound<'_, PyAny>) -> PyResult<bool> {
        let py = value.py();
        let identity = value.as_ptr() as usize;
        let prior = {
            let entries = self.entries.lock().map_err(|_| {
                crate::error_context::runtime("timezone origin cache lock poisoned")
            })?;
            entries
                .iter()
                .rev()
                .find(|entry| entry.identity == identity)
                .map(|entry| (entry.owner.clone_ref(py), entry.named))
        };
        if let Some((owner, named)) = prior
            && owner
                .bind(py)
                .upgrade()
                .is_some_and(|owner| owner.is(value))
        {
            return Ok(named);
        }
        // The original descriptor's file signal precedes _unpickle lookup.
        // No Python call or referent lifetime drop occurs under the cache lock.
        let named = match self.reduce.bind(py).call1((value,)) {
            Ok(_) => true,
            Err(error) if error.is_instance(py, self.file_error.bind(py)) => false,
            Err(error) => return Err(error),
        };
        let owner = PyWeakrefReference::new(value)?.unbind();
        let discarded = {
            let mut entries = self.entries.lock().map_err(|_| {
                crate::error_context::runtime("timezone origin cache lock poisoned")
            })?;
            let discarded =
                if let Some(index) = entries.iter().position(|entry| entry.identity == identity) {
                    entries.remove(index)
                } else if entries.len() == 128 {
                    entries.pop_front()
                } else {
                    None
                };
            entries.try_reserve(1).map_err(|_| {
                pyo3::exceptions::PyMemoryError::new_err("timezone origin cache allocation failed")
            })?;
            entries.push_back(OriginEntry {
                identity,
                owner,
                named,
            });
            discarded
        };
        drop(discarded);
        Ok(named)
    }
}

/// Check immutable named provenance and current native ZoneInfo capabilities.
/// The caller supplies retained builtin types; no business capability is cached.
pub(crate) fn native_named_zone_rules(
    value: &Bound<'_, PyAny>,
    base: &Bound<'_, PyType>,
    storage_type: &Bound<'_, PyType>,
) -> PyResult<bool> {
    const NAMES: [&str; 7] = [
        "key",
        "utcoffset",
        "dst",
        "tzname",
        "fromutc",
        "__getattribute__",
        "_unpickle",
    ];
    let py = value.py();
    let class = value.get_type();
    if !class.is(base) {
        let (inherited, storage_descriptor) =
            crate::protocol::inherited_methods(&class, base, &NAMES)?;
        if !inherited {
            return Ok(false);
        }
        if let Some(descriptor) = storage_descriptor {
            if !descriptor.get_type().is(storage_type) {
                return Ok(false);
            }
            let storage = descriptor.call_method1("__get__", (value,))?;
            let storage = storage.cast::<PyDict>()?;
            if !storage.is_empty() {
                for name in NAMES {
                    if storage.contains(name)? {
                        return Ok(false);
                    }
                }
            }
        }
    }
    let origin = crate::python_cache::get_or_prepare(&ZONE_ORIGIN, py, || {
        Ok(ZoneOrigins {
            reduce: base.getattr("__reduce__")?.unbind(),
            file_error: py
                .import("pickle")?
                .getattr("PicklingError")?
                .cast_into::<PyType>()?
                .unbind(),
            entries: Mutex::new(VecDeque::new()),
        })
    })?;
    // The original standard descriptor reports file provenance before doing
    // any _unpickle lookup. The live check above makes that lookup safe too.
    // No object pickle override, private C layout or key-based guess is used.
    origin.named(value)
}

/// A stored key proves rule equality only for reliable live named rules.
/// The outer option preserves the existing region/non-region distinction.
/// File zones and real business overrides remain supported by their host path.
pub(crate) fn reliable_named_key(value: &Bound<'_, PyAny>) -> PyResult<Option<Option<String>>> {
    if !pydt::is_zoneinfo_instance(value) {
        return Ok(None);
    }
    let py = value.py();
    let base = pydt::zoneinfo_class(py)
        .ok_or_else(|| crate::error_context::runtime("ZoneInfo class is unavailable"))?;
    static STORAGE_TYPE: PyOnceLock<Py<PyType>> = PyOnceLock::new();
    let storage_type = crate::python_cache::get_or_prepare(&STORAGE_TYPE, py, || {
        Ok::<_, PyErr>(
            py.import("types")?
                .getattr("GetSetDescriptorType")?
                .cast_into::<PyType>()?
                .unbind(),
        )
    })?;
    if !native_named_zone_rules(value, base, storage_type.bind(py))? {
        return Ok(Some(None));
    }
    pydt::zoneinfo_key(value)
}

/// Classify one already-read DST return without projecting away sub-us values.
/// None is unknown (-1); valid zero is 0 and either nonzero sign is 1.
/// The caller retains the return owner, callback timing and error location.
pub(crate) fn daylight_marker(adjustment: &Bound<'_, PyAny>) -> PyResult<i64> {
    if adjustment.is_none() {
        return Ok(-1);
    }
    let duration = adjustment
        .cast::<PyDelta>()
        .map_err(|_| crate::error_context::type_error("dst() must return None or timedelta"))?;
    let nanos = if adjustment.is_exact_instance_of::<PyDelta>() {
        None
    } else {
        crate::interop::duration_nanoseconds(adjustment)?
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
    Ok(i64::from(nanos != 0))
}
