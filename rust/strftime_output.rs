//! Host adapters around the shared pure fractional output plan.
use crate::strftime_plan::Plan;
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
    let format = format
        .cast::<PyString>()
        .map_err(|_| {
            crate::error_context::type_error("format must be a string; an empty string is allowed")
        })?
        .to_str()?;
    Ok(Context {
        plan: Plan::parse(format).map_err(crate::error_context::value_error)?,
    })
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
    let prepared = context.plan.system_format(nanos, 6);
    standard
        .bind(py)
        .call1((value, prepared))
        .map_err(crate::error_context::external)
}
/// Pddt retains pandas scalar formatting for all nonfraction platform rules.
/// The native loop prepares our fraction nodes before the mature call; it does
/// not post-process formatted strings or construct temporary date indexes.
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
    let out = PyList::empty(py);
    for (row, raw) in data.as_chunks::<8>().0.iter().enumerate() {
        let tick = i64::from_ne_bytes(*raw);
        let result = (|| -> PyResult<()> {
            if tick == i64::MIN {
                out.append(f64::NAN)?;
                return Ok(());
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
            let format = context
                .plan
                .system_format(fraction, if unit == "ns" { 9 } else { 6 });
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
