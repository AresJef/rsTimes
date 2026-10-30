//! Rust/PyO3 implementation of rstimes calendar deltas.
//!
//! Python consumers import rstimes.Delta or rstimes.delta.Delta. This crate is an
//! implementation library, not a separately supported public Rust API. Private
//! modules separate checked calendar arithmetic, Python object conversion,
//! versioned state and the CPython descriptor boundary.
//!
//! Calendar behavior follows this package's approved contracts, derived from
//! the frozen cyTimes 3.1.0 reference with explicit safety and behavior changes. The
//! release matrix targets ordinary, GIL-enabled 64-bit CPython 3.12 through 3.15.

#![deny(missing_docs)]

#[cfg(not(target_pointer_width = "64"))]
compile_error!(
    "rsTimes requires a 64-bit Python interpreter and target; 32-bit builds are unsupported."
);

use pyo3::prelude::*;
mod batch_shape;
mod bulk;
mod calendar;
mod civil;
mod clock;
mod date_input;
mod date_parts;
mod date_transform;
mod delta;
mod epoch;
mod error_context;
mod interop;
mod local_infer;
mod localization;
mod numeric;
mod numeric_epoch;
mod numpy_scalar;
mod parser;
mod pddt;
#[allow(missing_docs, unsafe_op_in_unsafe_fn)] // Official plugin macro generates C ABI wrappers.
mod pldt;
mod precision;
mod protocol;
mod pydt;
mod pydt_compare;
mod python_cache;
mod range_calendar;
mod range_frequency;
mod range_generate;
mod serde_values;
mod state;
mod temporal_operand;
mod temporal_zone;

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
    pldt::configure(module)?;
    range_frequency::configure(module)?;
    module.add_function(wrap_pyfunction!(state::_restore_delta, module)?)?;
    module.add_function(wrap_pyfunction!(interop::_configure_optional, module)?)?;
    module.add_function(wrap_pyfunction!(runtime_info, module)?)?;
    module.add_function(wrap_pyfunction!(release_build, module)?)?;
    Ok(())
}
