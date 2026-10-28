//! Select public Python C APIs with PyO3's interpreter-version configuration.

/// Keep old interpreters on their existing supported public-structure path.
fn main() {
    pyo3_build_config::use_pyo3_cfgs();
}
