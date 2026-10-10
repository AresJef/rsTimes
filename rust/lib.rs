use pyo3::prelude::*;
mod calendar;
mod delta;
mod interop;

#[pyfunction]
fn runtime_info() -> &'static str {
    "rsTimes Rust/PyO3 native kernel"
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<delta::Delta>()?;
    module.add_function(wrap_pyfunction!(runtime_info, module)?)?;
    Ok(())
}
