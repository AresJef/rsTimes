//! Fresh Pddt boundaries over shared native parsing and calendar primitives.
mod arguments;
mod buffer;
mod combine;
mod common;
mod dates;
mod difference;
mod exports;
mod factory;
mod formatted;
mod operands;
mod operations;
mod periods;
mod prepare;
mod queries;
mod range;
mod validity;
mod zones;

use pyo3::prelude::*;

/// Install only the current rewrite's private entry points.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    buffer::configure(module)?;
    validity::configure(module)?;
    operations::configure(module)?;
    operands::configure(module)?;
    periods::configure(module)?;
    arguments::configure(module)?;
    dates::configure(module)?;
    combine::configure(module)?;
    zones::configure(module)?;
    factory::configure(module)?;
    formatted::configure(module)?;
    range::configure(module)?;
    queries::configure(module)?;
    difference::configure(module)?;
    exports::configure(module)?;
    prepare::configure(module)
}
