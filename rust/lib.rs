//! Rust/PyO3 implementation of rstimes calendar deltas.
//!
//! Python consumers import rstimes.Delta or rstimes.delta.Delta. This crate is an
//! implementation library, not a separately supported public Rust API. Private
//! modules separate checked calendar arithmetic, Python object conversion,
//! versioned state and the CPython descriptor boundary.
//!
//! Calendar behavior follows this package's approved contracts, derived from
//! the frozen cyTimes 3.1.0 reference with explicit safety and behavior changes. The
//! accepted native ABI targets ordinary CPython 3.13 on macOS arm64.

#![deny(missing_docs)]

use pyo3::prelude::*;
mod bulk;
mod calendar;
mod delta;
mod epoch;
mod error_context;
mod interop;
mod localization;
mod numeric;
mod numpy_scalar;
mod parser;
mod pddt;
mod protocol;
mod pydt;
mod pydt_compare;
mod python_cache;
mod state;

/// Return the native implementation label for installation diagnostics.
#[pyfunction]
fn runtime_info() -> &'static str {
    "rsTimes Rust/PyO3 native kernel"
}

/// Report whether this extension was compiled without debug assertions.
///
/// Use this flag to reject debug wheels before release performance measurements.
#[pyfunction]
fn release_build() -> bool {
    !cfg!(debug_assertions)
}

/// Register Delta and diagnostic helpers in the rstimes native module.
///
/// # Errors
/// Propagates type registration and descriptor installation errors.
#[pymodule(gil_used = true)]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    delta::configure_hash(module.py());
    module.add_class::<delta::Delta>()?;
    numeric::configure(module)?;
    protocol::install(module)?;
    state::configure(module.py())?;
    localization::configure(module)?;
    parser::configure(module)?;
    pydt::configure(module)?;
    pydt_compare::configure(module)?;
    epoch::configure(module)?;
    pddt::configure(module)?;
    module.add_function(wrap_pyfunction!(state::_restore_delta, module)?)?;
    module.add_function(wrap_pyfunction!(interop::_configure_optional, module)?)?;
    module.add_function(wrap_pyfunction!(runtime_info, module)?)?;
    module.add_function(wrap_pyfunction!(release_build, module)?)?;
    Ok(())
}
