//! Native Polars column adapters and official expression-plugin registration.
//!
//! Owned native rules execute without Python; real host protocols stay at the
//! explicit calling boundary. Query/date/format kernels live in small modules.
mod arithmetic;
mod calendar;
mod combine;
mod dates;
mod difference;
mod factory;
mod finish;
mod format;
mod input;
mod iso;
mod operations;
mod output;
mod periods;
mod queries;
mod range;
mod text;
mod timezone;
mod zones;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::export::polars_ffi::version_0::export_series;
use std::mem::ManuallyDrop;

pub(super) fn export<'py>(
    _py: Python<'py>,
    result: &Series,
    target: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let export = ManuallyDrop::new(export_series(result));
    target.call_method1("_import", ((&raw const export).addr(),))
}

/// Adapt known native failure categories only at the eager Python boundary.
/// Plugin execution retains the engine's native error protocol instead.
pub(super) fn eager_error(error: PolarsError) -> PyErr {
    match error {
        PolarsError::SchemaMismatch(message) => {
            crate::error_context::type_error(message.to_string())
        }
        PolarsError::OutOfBounds(message) => crate::error_context::overflow(message.to_string()),
        PolarsError::ShapeMismatch(message)
        | PolarsError::InvalidOperation(message)
        | PolarsError::ComputeError(message) => {
            crate::error_context::value_error(message.to_string())
        }
        PolarsError::Python { error } => crate::error_context::external(error.0),
        PolarsError::Context { .. } | PolarsError::ExprContext { .. } => {
            eager_error(error.context_trace())
        }
        other => pyo3_polars::error::PyPolarsErr::from(other).into(),
    }
}

/// Register the eager adapter without importing or requiring Python Polars.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    input::configure(module)?;
    text::configure(module)?;
    factory::configure(module)?;
    dates::configure(module)?;
    iso::configure(module)?;
    operations::configure(module)?;
    output::configure(module)?;
    format::configure(module)?;
    periods::configure(module)?;
    queries::configure(module)?;
    difference::configure(module)?;
    range::configure(module)?;
    calendar::configure(module)?;
    arithmetic::configure(module)?;
    combine::configure(module)?;
    zones::configure(module)?;
    timezone::configure(module)
}
