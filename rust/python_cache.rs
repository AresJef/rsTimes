//! Prepare Python-dependent values before publishing interpreter-owned caches.

use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;

/// Reuse a complete value, allowing preparation callbacks to publish first.
///
/// User code runs only in `prepare`, outside the cache's initialization lock.
/// Failed preparation publishes nothing; a nested successful preparation wins.
///
/// # Errors
/// Propagates preparation errors and never exposes partially prepared values.
pub(crate) fn get_or_prepare<'a, T>(
    cache: &'a PyOnceLock<T>,
    py: Python<'_>,
    prepare: impl FnOnce() -> PyResult<T>,
) -> PyResult<&'a T> {
    if let Some(value) = cache.get(py) {
        return Ok(value);
    }
    let candidate = prepare()?;
    let _ = cache.set(py, candidate);
    cache
        .get(py)
        .ok_or_else(|| crate::error_context::runtime("Python cache publication did not complete"))
}
