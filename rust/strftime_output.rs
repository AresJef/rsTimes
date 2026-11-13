//! Host adapters around the shared pure fractional output plan.
use crate::parser::text::{CharacterRead, TextView};
use crate::strftime_plan::{Plan, SystemFormat};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyAny, PyBytes, PyDateTime, PyDict, PyList, PyString, PyTimeAccess};

static STANDARD: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
pub(crate) fn standard(py: Python<'_>) -> PyResult<&Py<PyAny>> {
    crate::python_cache::get_or_prepare(&STANDARD, py, || {
        py.import("datetime")?
            .getattr("datetime")?
            .getattr("strftime")
            .map(Bound::unbind)
    })
}
#[pyclass(frozen, skip_from_py_object, name = "_StrftimeContext")]
pub(crate) struct Context {
    pub(crate) plan: Plan,
}
#[pymethods]
impl Context {
    fn native(&self) -> bool {
        self.plan.native()
    }
    fn modified(&self) -> bool {
        self.plan.modified()
    }
    fn plugin_data<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        Ok(PyBytes::new(
            py,
            &serde_json::to_vec(&self.plan)
                .map_err(|e| crate::error_context::runtime(e.to_string()))?,
        ))
    }
}
#[pyfunction]
fn _strftime_prepare(format: &Bound<'_, PyAny>) -> PyResult<Context> {
    let format = format.cast::<PyString>().map_err(|_| {
        crate::error_context::type_error("format must be a string; an empty string is allowed")
    })?;
    let view = TextView::new(format)?;
    Ok(Context {
        plan: Plan::parse_points((0..view.len()).map(|index| CharacterRead::get(&view, index)))
            .map_err(crate::error_context::value_error)?,
    })
}

/// Host-only reconstruction; worker plans contain Rust-owned data exclusively.
pub(crate) fn system_format<'py>(
    py: Python<'py>,
    plan: &Plan,
    nanos: u32,
    digits: u8,
) -> PyResult<Bound<'py, PyAny>> {
    match plan.system_format(nanos, digits) {
        SystemFormat::Utf8(text) => Ok(PyString::new(py, &text).into_any()),
        SystemFormat::Codepoints(points) => {
            crate::parser::text::unicode(py, &points).map(Bound::into_any)
        }
    }
}
#[pyfunction]
fn _pydt_strftime<'py>(
    value: &Bound<'py, PyDateTime>,
    format: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = value.py();
    let context = _strftime_prepare(format)?;
    let standard = standard(py)?;
    if !context.plan.modified() {
        return standard
            .bind(py)
            .call1((value, format))
            .map_err(crate::error_context::external);
    }
    let nanos = if context.plan.has_fraction() {
        value.get_microsecond() * 1000
    } else {
        0
    };
    let prepared = system_format(py, &context.plan, nanos, 6)?;
    standard
        .bind(py)
        .call1((value, prepared))
        .map_err(crate::error_context::external)
}
struct NumericZone {
    wall_offset: i128,
    offset: Option<i32>,
    name: Option<String>,
}

/// Only proved date-independent zones and platform-independent numeric forms
/// can bypass the mature host formatter. Custom and dynamic protocols stay there.
fn numeric_zone(
    py: Python<'_>,
    zone: &Bound<'_, PyAny>,
    plan: &Plan,
) -> PyResult<Option<NumericZone>> {
    if !plan.system_numeric() {
        return Ok(None);
    }
    let source = if zone.is_none() {
        crate::epoch::Zone::Naive
    } else {
        crate::epoch::Zone::Object(zone.clone().unbind())
    };
    let Some(offset) = crate::date_input::fixed_offset(py, &source)? else {
        return Ok(None);
    };
    if offset % 1_000_000 != 0 {
        return Ok(None);
    }
    let name = if plan.needs_name() && !zone.is_none() {
        let name = zone
            .call_method1("tzname", (py.None(),))
            .map_err(crate::error_context::external)?;
        if name.is_none() {
            None
        } else {
            let text = name.cast::<PyString>()?;
            // SAFETY: the live immutable PyString owns ready storage under the
            // GIL. These kind/data/length APIs are also used by TextView on all
            // supported Python versions. One-byte storage includes Latin1, so
            // inspect its bytes before UTF8 decoding; wider names use the host.
            let ascii = unsafe {
                pyo3::ffi::PyUnicode_KIND(text.as_ptr()) == pyo3::ffi::PyUnicode_1BYTE_KIND
                    && std::slice::from_raw_parts(
                        pyo3::ffi::PyUnicode_DATA(text.as_ptr()).cast::<u8>(),
                        pyo3::ffi::PyUnicode_GET_LENGTH(text.as_ptr()) as usize,
                    )
                    .is_ascii()
            };
            if !ascii {
                return Ok(None);
            }
            let text = text.to_str()?;
            if text.contains('\0') {
                return Ok(None);
            }
            Some(text.to_owned())
        }
    } else {
        None
    };
    Ok(Some(NumericZone {
        wall_offset: i128::from(offset) * 1000,
        offset: if zone.is_none() {
            None
        } else {
            Some(i32::try_from(offset / 1_000_000).map_err(|_| {
                crate::error_context::overflow("fixed timezone exceeds integer seconds")
            })?)
        },
        name,
    }))
}

/// Ordinary numeric fractional output shares the native plan. Every system
/// extension, dynamic zone and small/wide year retains mature pandas formatting.
#[pyfunction]
fn _pddt_strftime<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: &Bound<'py, PyAny>,
    context: PyRef<'_, Context>,
) -> PyResult<Bound<'py, PyList>> {
    if !data.len().is_multiple_of(8) {
        return Err(crate::error_context::runtime("invalid date output buffer"));
    }
    let timestamp = crate::interop::timestamp_class(py)?;
    let quantum = crate::epoch::Unit::parse(unit)?.nanos();
    let kwargs = PyDict::new(py);
    kwargs.set_item("unit", unit)?;
    kwargs.set_item("tz", zone)?;
    let numeric = numeric_zone(py, zone, &context.plan)?;
    let lower = i128::from(crate::calendar::ordinal(1000, 1, 1) - 719_163) * 86_400_000_000_000;
    let upper = i128::from(crate::calendar::ordinal(10000, 1, 1) - 719_163) * 86_400_000_000_000;
    let digits = if unit == "ns" { 9 } else { 6 };
    let out = PyList::empty(py);
    let mut text = String::new();
    for (row, raw) in data.as_chunks::<8>().0.iter().enumerate() {
        let tick = i64::from_ne_bytes(*raw);
        let result = (|| -> PyResult<()> {
            if tick == i64::MIN {
                out.append(f64::NAN)?;
                return Ok(());
            }
            if let Some(zone) = &numeric {
                let wall = i128::from(tick) * quantum + zone.wall_offset;
                if (lower..upper).contains(&wall) {
                    context
                        .plan
                        .render_into(wall, digits, zone.offset, zone.name.as_deref(), &mut text)
                        .map_err(|error| match error {
                            crate::calendar_query::Error::Capacity(message) => {
                                crate::error_context::overflow(message)
                            }
                            crate::calendar_query::Error::Internal(message) => {
                                crate::error_context::runtime(message)
                            }
                        })?;
                    // PyO3 copies into an owned Python string before scratch reuse.
                    out.append(text.as_str())?;
                    return Ok(());
                }
            }
            let value = timestamp
                .call((tick,), Some(&kwargs))
                .map_err(crate::error_context::external)?;
            let fraction = if context.plan.has_fraction() {
                let micros = value.getattr("microsecond")?.extract::<u32>()?;
                let tail = (i128::from(tick) * quantum).rem_euclid(1000) as u32;
                micros * 1000 + tail
            } else {
                0
            };
            let format = system_format(py, &context.plan, fraction, digits)?;
            out.append(
                value
                    .call_method1("strftime", (format,))
                    .map_err(crate::error_context::external)?,
            )?;
            Ok(())
        })();
        result.map_err(|e| {
            crate::error_context::location(py, e, "Pddt.strftime", &format!("data[{row}]"))
        })?;
    }
    Ok(out)
}
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_strftime_prepare, module)?)?;
    module.add_function(wrap_pyfunction!(_pydt_strftime, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_strftime, module)?)
}
