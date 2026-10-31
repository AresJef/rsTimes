//! One-pass collection preparation, with no Python datetime text intermediate.
use super::common::{Rows, finish};
use crate::epoch::{self, Options, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

#[pyfunction]
fn _pddt_register(py: Python<'_>, na: Py<PyAny>, nat: Py<PyAny>, resolver: Py<PyAny>) {
    crate::date_input::register_missing(py, na, nat);
    super::common::register_zone_resolver(py, resolver);
}

// This specialization retains the adopted pandas NaT numeric-sentinel contract.
pub(super) type Reader<'a, 'py> = crate::date_input::Reader<'a, 'py, true>;
pub(super) use crate::date_input::{missing, missing_text, nat, scalar_unit};

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One prepared collection boundary"
)]
#[pyo3(signature=(data,policy,unit=None,base_unit=None,default=None,yearfirst=None,dayfirst=None,isoformat=true,strict=false,cfg=None,target=None,entry="Pddt"))]
fn _pddt_prepare<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    policy: PyRef<'_, super::zones::Policies>,
    unit: Option<&str>,
    base_unit: Option<&str>,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    strict: bool,
    cfg: Option<&Bound<'py, PyAny>>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let requested = unit.map(Unit::parse).transpose()?;
    if let Some(cfg) = cfg.filter(|c| !c.is_none()) {
        cfg.cast::<crate::parser::config::Configs>().map_err(|_| {
            crate::error_context::expected_type(cfg, entry, "cfg", "a Configs instance or None")
        })?;
    }
    let mut rows = Rows::new(
        base_unit
            .map(Unit::parse)
            .transpose()?
            .unwrap_or(Unit::Second),
    );
    let numeric = requested.unwrap_or(Unit::Nanosecond);
    let opts = Options {
        default,
        yearfirst,
        dayfirst,
        ignoretz: false,
        isoformat,
        strict,
        iso_only: false,
        cfg,
        input_unit: numeric,
    };
    let mut reader = Reader::new(opts, rows.unit);
    let iterator = data
        .try_iter()
        .map_err(crate::error_context::external)
        .map_err(|e| crate::error_context::argument(py, e, entry, "data", data))?;
    for (i, item) in iterator.enumerate() {
        let item = item
            .map_err(crate::error_context::external)
            .map_err(|e| crate::error_context::item(py, e, entry, "data", i, None, true))?;
        let row = reader
            .read(&item, entry)
            .map_err(|e| crate::error_context::item(py, e, entry, "data", i, Some(&item), false))?;
        rows.unit = reader.unit;
        if let Some((parsed, instant)) = row {
            rows.push(py, parsed, instant)?;
        } else {
            rows.missing();
        }
    }
    finish(py, rows, requested, target, entry, &policy)
}

/// Decode a homogeneous owned date snapshot without creating scalar objects.
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared buffer metadata boundary"
)]
#[pyo3(signature=(data,policy,source,multiplier=1,unit=None,source_zone=None,target=None,entry="Pddt",mask=None))]
fn _pddt_dates<'py>(
    py: Python<'py>,
    data: &[u8],
    policy: PyRef<'_, super::zones::Policies>,
    source: &str,
    multiplier: i32,
    unit: Option<&str>,
    source_zone: Option<&Bound<'py, PyAny>>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
    mask: Option<&[u8]>,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let code = match source {
        "Y" => 0,
        "M" => 1,
        "W" => 2,
        "D" => 4,
        "h" => 5,
        "m" => 6,
        "s" => 7,
        "ms" => 8,
        "us" => 9,
        "ns" => 10,
        _ => {
            return Err(crate::error_context::value_error(
                "unsupported NumPy date unit; use years through nanoseconds",
            ));
        }
    };
    if !data.len().is_multiple_of(8) || multiplier < 1 {
        return Err(crate::error_context::value_error(
            "invalid date buffer metadata",
        ));
    }
    let validity = super::validity::TemporalValidity::new(mask, data.len() / 8)?;
    let requested = unit.map(Unit::parse).transpose()?;
    let mut rows = Rows::new(scalar_unit(code)?);
    let source_zone = source_zone.filter(|z| !z.is_none());
    // A homogeneous native-unit snapshot has one known source role. Decode
    // its ticks directly; mixed zones and calendar units keep full preparation.
    let native_scale = (multiplier == 1 && source_zone.is_none() && (7..=10).contains(&code))
        .then_some(rows.unit.nanos());
    let mut raw = [0; 8];
    for (index, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        raw.copy_from_slice(bytes);
        let ticks = i64::from_ne_bytes(raw);
        if validity.missing(index, ticks) {
            rows.missing();
            continue;
        }
        if let Some(scale) = native_scale {
            rows.values.push(Some(i128::from(ticks) * scale));
            rows.sources.push(super::common::Source {
                zone: 0,
                instant: false,
            });
            continue;
        }
        let mut parsed =
            epoch::native_datetime_ticks(ticks, code, multiplier).map_err(|error| {
                crate::error_context::location(py, error, entry, &format!("data[{index}]"))
            })?;
        if let Some(zone) = source_zone {
            parsed.zone = Zone::Object(zone.clone().unbind());
        }
        rows.push(py, parsed, source_zone.is_some())?;
    }
    // Typed all-NaT/empty aware sources retain their declared timezone too.
    finish(py, rows, requested, target.or(source_zone), entry, &policy)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_result_type, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_register, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_prepare, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_dates, module)?)
}

/// New date results require real ancestry, never a displayed class or ABC hook.
#[pyfunction]
fn _pddt_result_type(
    value: &Bound<'_, PyAny>,
    class: &Bound<'_, pyo3::types::PyType>,
    base: &Bound<'_, pyo3::types::PyType>,
) -> bool {
    // SAFETY: the live value and both validated Python type objects are held
    // under the GIL. The C predicate reads actual inheritance without callbacks.
    unsafe {
        let actual = pyo3::ffi::Py_TYPE(value.as_ptr());
        pyo3::ffi::PyType_IsSubtype(actual, class.as_type_ptr()) != 0
            && pyo3::ffi::PyType_IsSubtype(actual, base.as_type_ptr()) != 0
    }
}
