//! Rust/PyO3 implementation of rstimes calendar deltas.
//!
//! Python consumers import rstimes.Delta or rstimes.delta.Delta. This crate is an
//! implementation library, not a separately supported public Rust API. Private
//! modules separate checked calendar arithmetic, Python object conversion,
//! versioned state and the CPython descriptor boundary.
//!
//! Calendar behavior follows the frozen cyTimes 3.1.0 reference, except for the
//! approved OverflowError policy and new-package serialization identity. The
//! accepted native ABI targets ordinary CPython 3.13 on macOS arm64.

#![deny(missing_docs)]

use pyo3::prelude::*;
mod bulk;
mod calendar;
mod delta;
mod interop;
mod numpy_scalar;
mod protocol;
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
#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    delta::configure_hash(module.py());
    module.add_class::<delta::Delta>()?;
    protocol::install(module)?;
    module.add_function(wrap_pyfunction!(state::_restore_delta, module)?)?;
    module.add_function(wrap_pyfunction!(runtime_info, module)?)?;
    module.add_function(wrap_pyfunction!(release_build, module)?)?;
    Ok(())
}
