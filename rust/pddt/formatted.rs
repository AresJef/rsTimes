//! Batch formatted strings use one native format and one effective rules snapshot.
use super::common::{Rows, finish_truncated};
use crate::epoch::Unit;
use crate::parser::formatted::{Context, Format};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared format/rules and one-dimensional data boundary"
)]
#[pyo3(signature=(data,format,policy,cfg=None,size=None,column=false,unit=None,entry="Pddt.strptime"))]
fn _pddt_strptime<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    format: PyRef<'_, Format>,
    policy: PyRef<'_, super::zones::Policies>,
    cfg: Option<&Bound<'py, PyAny>>,
    size: Option<usize>,
    column: bool,
    unit: Option<&str>,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let context = Context::prepare(&format, cfg)?;
    let requested = unit.map(Unit::parse).transpose()?;
    let mut rows = Rows::new(Unit::Microsecond);
    let mut read = |value: &Bound<'py, PyAny>| -> PyResult<()> {
        if let Ok(text) = value.cast::<PyString>() {
            let converted;
            let text = if value.is_exact_instance_of::<PyString>() {
                text
            } else {
                converted = value.str().map_err(crate::error_context::external)?;
                &converted
            };
            if super::prepare::missing_text(text)? {
                rows.missing();
                return Ok(());
            }
            rows.push(
                py,
                crate::parser::formatted::read(&context, text)?.into_epoch()?,
                false,
            )
        } else if super::arguments::date_missing(value)? {
            rows.missing();
            Ok(())
        } else {
            Err(crate::error_context::type_error(
                "strptime requires text values, not dates or numeric input",
            ))
        }
    };
    let scalar = !column
        && (data.is_instance_of::<PyString>()
            || super::arguments::date_missing(data)?
            || unsafe {
                pyo3::ffi::PyIndex_Check(data.as_ptr()) != 0
                    || pyo3::ffi::PyDate_Check(data.as_ptr()) != 0
            }
            || crate::numeric::supported_float(data)
            || data.is_instance_of::<pyo3::types::PyBytes>()
            || data.is_instance_of::<pyo3::types::PyByteArray>());
    if scalar {
        let size = size.ok_or_else(|| {
            crate::error_context::value_error("a scalar strptime input requires size")
        })?;
        read(data).map_err(|e| crate::error_context::argument(py, e, entry, "dtstr", data))?;
        rows.reserve(size)?;
        rows.empty_zone = rows.sources[0].zone;
        rows.values.resize(size, rows.values[0]);
        rows.sources.resize(size, rows.sources[0]);
        if size == 0 {
            rows.values.clear();
            rows.sources.clear();
        }
    } else {
        if size.is_some() {
            return Err(crate::error_context::value_error(
                "omit size for a collection",
            ));
        }
        for (i, item) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let item = item
                .map_err(crate::error_context::external)
                .map_err(|e| crate::error_context::item(py, e, entry, "dtstr", i, None, true))?;
            read(&item).map_err(|e| {
                crate::error_context::item(py, e, entry, "dtstr", i, Some(&item), false)
            })?;
        }
    }
    finish_truncated(py, rows, requested, None, entry, &policy)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_strptime, module)?)
}
