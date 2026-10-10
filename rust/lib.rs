use pyo3::prelude::*;
mod calendar;
mod delta;
mod interop;
mod numpy_scalar;
mod protocol;
mod state;

#[pyfunction]
fn runtime_info() -> &'static str {
    "rsTimes Rust/PyO3 native kernel"
}

#[pyfunction]
fn release_build() -> bool {
    !cfg!(debug_assertions)
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<delta::Delta>()?;
    protocol::install(module.py())?;
    module.add_function(wrap_pyfunction!(runtime_info, module)?)?;
    module.add_function(wrap_pyfunction!(release_build, module)?)?;
    Ok(())
}
