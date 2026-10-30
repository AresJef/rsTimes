//! Python-side preparation only. The resulting worker context owns native
//! values and is never permitted to retain a cfg/default Python object.
use super::config::{Configs, NativeRules, NativeRulesData};
use super::{Truth, native};
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Versioned values accepted by the official plugin kwargs decoder.
#[derive(Clone, serde::Serialize, serde::Deserialize, pyo3::IntoPyObject)]
pub(crate) struct TextData {
    pub(crate) options: native::Options,
    pub(crate) strict: bool,
    pub(crate) rules: Option<NativeRulesData>,
}

/// A prepared eager call may reuse native Arc ownership directly. Expressions
/// export values through the official serde boundary; no process-global IDs.
#[pyclass(frozen, skip_from_py_object, name = "_PldtTextContext")]
pub(crate) struct TextContext {
    pub(crate) rules: NativeRules,
    pub(crate) options: native::Options,
    pub(crate) strict: bool,
    custom_rules: bool,
}

#[pymethods]
impl TextContext {
    /// Return immutable values for one versioned plugin preparation.
    fn plugin_kwargs<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        TextData {
            options: self.options,
            strict: self.strict,
            rules: self.custom_rules.then(|| self.rules.data()),
        }
        .into_pyobject(py)
    }
}

/// Expressions freeze cfg first, then resolve the independent default against
/// that snapshot. Immediate native-string callers resolve real default callbacks
/// first and snapshot the resulting live cfg, preserving the eager contract.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature=(*,cfg=None,default=None,yearfirst=None,dayfirst=None,isoformat=Truth(true),strict=Truth(false),expression=Truth(true)))]
fn _pldt_prepare_text(
    py: Python<'_>,
    cfg: Option<&Bound<'_, PyAny>>,
    default: Option<&Bound<'_, PyAny>>,
    yearfirst: Option<Truth>,
    dayfirst: Option<Truth>,
    isoformat: Truth,
    strict: Truth,
    expression: Truth,
) -> PyResult<TextContext> {
    let cfg = cfg.filter(|value| !value.is_none());
    if let Some(value) = cfg {
        value.cast::<Configs>().map_err(|_| {
            crate::error_context::expected_type(
                value,
                "Pldt.parse",
                "cfg",
                "a Configs instance or None",
            )
        })?;
    }
    let frozen = if expression.0 {
        cfg.map(|value| Py::new(py, value.cast::<Configs>()?.borrow().independent()))
            .transpose()?
    } else {
        None
    };
    let selected = frozen.as_ref().map(|value| value.bind(py).as_any()).or(cfg);
    let yearfirst = yearfirst.map(|value| value.0);
    let dayfirst = dayfirst.map(|value| value.0);
    let default = super::prepare_default(
        py,
        default,
        yearfirst,
        dayfirst,
        isoformat.0,
        selected,
        strict.0,
    )?;
    let rules = match selected {
        Some(value) => value.cast::<Configs>()?.borrow().native_snapshot(),
        None => NativeRules::library(),
    };
    Ok(TextContext {
        rules,
        options: native::Options {
            default,
            yearfirst,
            dayfirst,
            isoformat: isoformat.0,
        },
        strict: strict.0,
        custom_rules: cfg.is_some(),
    })
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<TextContext>()?;
    module.add_function(wrap_pyfunction!(_pldt_prepare_text, module)?)
}
