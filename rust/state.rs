//! Versioned serialization and copying for this package's Delta objects.
//!
//! The state marker is rstimes.delta and the format version is 2. External state
//! is fully validated before native fields are committed; trusted native copies
//! reuse that validated payload. Pickle can execute Python code and is supported
//! only for trusted data. Old cyTimes pickle and Cython entry points are excluded.

use crate::delta::Delta;

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyInt, PyString, PyTuple};

static DEFAULT_STATE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static DELTA_STATE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static DELTA_REDUCE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// Retain the original native definitions before the class is exposed to users.
pub(crate) fn configure(py: Python<'_>) -> PyResult<()> {
    let class = py.get_type::<Delta>();
    for (name, cache) in [
        ("__getstate__", &DELTA_STATE),
        ("__reduce__", &DELTA_REDUCE),
    ] {
        let method = crate::protocol::method_definition(&class, name)?
            .ok_or_else(|| crate::error_context::runtime("Delta state method is unavailable"))?;
        let _ = cache.set(py, method.unbind());
    }
    Ok(())
}

/// Compare the live inherited hook with the original saved base definition.
fn overrides(
    slf: &Bound<'_, Delta>,
    name: &str,
    original: &PyOnceLock<Py<PyAny>>,
) -> PyResult<bool> {
    // The declared immutable_type base cannot acquire new state hooks. Mutable
    // Python subclasses still inspect their live definitions on every call.
    if slf.is_exact_instance_of::<Delta>() {
        return Ok(false);
    }
    let original = original
        .get(slf.py())
        .ok_or_else(|| crate::error_context::runtime("Delta state methods are not initialized"))?;
    Ok(crate::protocol::method_definition(&slf.get_type(), name)?
        .is_none_or(|method| !method.is(original.bind(slf.py()))))
}

/// Preserve an explicit whole-recipe override when pickle calls reduce_ex.
pub(crate) fn reduce_ex<'py>(slf: &Bound<'py, Delta>) -> PyResult<Bound<'py, PyAny>> {
    if overrides(slf, "__reduce__", &DELTA_REDUCE)? {
        return slf
            .call_method0("__reduce__")
            .map_err(crate::error_context::external);
    }
    reduce(slf)
}

/// Capture ordinary dictionaries and inherited slots using Python's default protocol.
fn capture_metadata<'py>(slf: &Bound<'py, Delta>) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    if slf.is_exact_instance_of::<Delta>() {
        return Ok(py.None().into_bound(py));
    }
    capture_object_metadata(slf.as_any())
}

/// Capture an independent dictionary/slot snapshot without a type-specific payload.
/// Explicit user getstate hooks remain the calling protocol's responsibility.
pub(crate) fn capture_object_metadata<'py>(slf: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    let getstate =
        crate::python_cache::get_or_prepare(&DEFAULT_STATE, py, || -> PyResult<Py<PyAny>> {
            Ok(py
                .import("builtins")?
                .getattr("object")
                .map_err(crate::error_context::external)?
                .getattr("__getstate__")
                .map_err(crate::error_context::external)?
                .unbind())
        })?;
    let state = getstate
        .bind(py)
        .call1((slf,))
        .map_err(crate::error_context::external)?;
    if let Ok(dictionary) = state.cast::<PyDict>() {
        return dictionary.copy().map(Bound::into_any);
    }
    if let Ok(tuple) = state.cast::<PyTuple>() {
        let dictionary = tuple.get_item(0)?;
        let dictionary = if dictionary.is_none() {
            dictionary
        } else {
            dictionary.cast::<PyDict>()?.copy()?.into_any()
        };
        return Ok((dictionary, tuple.get_item(1)?.cast::<PyDict>()?.copy()?)
            .into_pyobject(py)?
            .into_any());
    }
    Ok(state)
}

/// Capture the version-two four-item state without derived caches.
/// (marker,2,core17,metadata); business metadata retains its own real protocol.
pub fn capture<'py>(slf: &Bound<'py, Delta>) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    let fields = PyTuple::new(py, slf.get().snapshot())?;
    let metadata = capture_metadata(slf)?;
    Ok(("rstimes.delta", 2, fields, metadata)
        .into_pyobject(py)?
        .into_any())
}

/// Read an exact builtin int from external state without numeric callbacks.
///
/// # Errors
/// Rejects bool, int subclasses and non-int values with TypeError, and
/// unrepresentable signed 64-bit values with OverflowError.
fn integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    if !value.is_exact_instance_of::<PyInt>() {
        return Err(crate::error_context::type_error(
            "Delta state integers must be exact int values",
        ));
    }
    value.extract()
}

/// Validate exact builtin integers in the complete new core tuple.
fn decode_fields(data: &Bound<'_, PyAny>) -> PyResult<[i64; 17]> {
    if !data.is_exact_instance_of::<PyTuple>() {
        return Err(crate::error_context::type_error(
            "Delta state fields must be a tuple",
        ));
    }
    let data = data.cast::<PyTuple>()?;
    if data.len() != 17 {
        return Err(crate::error_context::value_error(
            "Delta state must contain 17 fields",
        ));
    }
    let mut fields = [0; 17];
    for (index, value) in data.iter().enumerate() {
        fields[index] = integer(&value).map_err(|error| {
            crate::error_context::argument(data.py(), error, "", FIELD_NAMES[index], &value)
        })?;
    }
    validate_fields(&fields)?;
    Ok(fields)
}

/// Check canonical native ranges independently of their external encoding.
/// # Errors
/// Rejects invalid relative/absolute fields before any native value is allocated.
fn validate_fields(fields: &[i64; 17]) -> PyResult<()> {
    if !(0..12).contains(&fields[1]) {
        return Err(crate::error_context::value_error(format!(
            "state.fields.months={} must be from 0 through 11, inclusive, in normalized state",
            fields[1]
        )));
    }
    for (index, maximum) in [(3, 23), (4, 59), (5, 59), (6, 999_999), (7, 999)] {
        if !(0..=maximum).contains(&fields[index]) {
            return Err(crate::error_context::value_error(format!(
                "state.fields.{}={} must be from 0 through {maximum}, inclusive, in normalized state",
                FIELD_NAMES[index], fields[index]
            )));
        }
    }
    for (offset, maximum) in [9_999, 12, 31, 6, 23, 59, 59, 999_999, 999]
        .into_iter()
        .enumerate()
    {
        let value = fields[8 + offset];
        let minimum = if offset < 3 { 1 } else { 0 };
        if value != -1 && !(minimum..=maximum).contains(&value) {
            return Err(crate::error_context::value_error(format!(
                "state.fields.{}={value} must be -1 (unset) or from {minimum} through {maximum}, inclusive",
                FIELD_NAMES[8 + offset]
            )));
        }
    }
    Ok(())
}

const FIELD_NAMES: [&str; 17] = [
    "years",
    "months",
    "days",
    "hours",
    "minutes",
    "seconds",
    "microseconds",
    "nanoseconds",
    "year",
    "month",
    "day",
    "weekday",
    "hour",
    "minute",
    "second",
    "microsecond",
    "nanosecond",
];
const PAYLOAD_MARKER: &[u8; 8] = b"rstDlt\0\x02";

/// Encode only the new17-field core, in fixed little-endian order.
fn encode<'py>(py: Python<'py>, fields: [i64; 17]) -> Bound<'py, PyBytes> {
    let mut bytes = [0_u8; 144];
    bytes[..8].copy_from_slice(PAYLOAD_MARKER);
    for (index, value) in fields.into_iter().enumerate() {
        bytes[8 + index * 8..16 + index * 8].copy_from_slice(&value.to_le_bytes());
    }
    PyBytes::new(py, &bytes)
}

/// Reject every old/unknown payload before allocating a Delta.
fn decode_bytes(value: &Bound<'_, PyBytes>) -> PyResult<[i64; 17]> {
    let bytes = value.as_bytes();
    if bytes.len() != 144 || bytes[..8] != *PAYLOAD_MARKER {
        return Err(crate::error_context::value_error(
            "Unsupported Delta reconstruction payload; requires version 2",
        ));
    }
    let mut fields = [0_i64; 17];
    for (index, chunk) in bytes[8..].as_chunks::<8>().0.iter().enumerate() {
        fields[index] = i64::from_le_bytes(std::array::from_fn(|offset| chunk[offset]));
    }
    validate_fields(&fields)?;
    Ok(fields)
}

/// Recognize internal reconstruction forms while ordinary numeric inputs continue.
/// # Errors
/// Complete byte payloads receive the same strict canonical-field validation as state.
#[inline]
pub(crate) fn construction_value(args: &Bound<'_, PyTuple>) -> PyResult<Option<Delta>> {
    // The caller checked a one-item tuple; it owns the borrowed item throughout.
    let value =
        unsafe { Borrowed::from_ptr(args.py(), pyo3::ffi::PyTuple_GET_ITEM(args.as_ptr(), 0)) };
    if let Ok(bytes) = value.cast::<PyBytes>()
        && bytes.as_bytes().starts_with(&PAYLOAD_MARKER[..7])
    {
        let fields = decode_bytes(&bytes)?;
        return Ok(Some(Delta::from_snapshot(fields)?));
    }
    Ok(None)
}

/// Validate the dictionary portion of trusted package state.
///
/// # Errors
/// Requires an exact dictionary with string keys, or None.
fn decode_dictionary<'py>(value: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyDict>>> {
    if value.is_none() {
        return Ok(None);
    }
    if !value.is_exact_instance_of::<PyDict>() {
        return Err(crate::error_context::type_error(
            "Delta state dictionary must be dict or None",
        ));
    }
    let dictionary = value.cast::<PyDict>()?;
    for key in dictionary.keys().iter() {
        if !key.is_exact_instance_of::<PyString>() {
            return Err(crate::error_context::type_error(
                "Delta state dictionary keys must be strings",
            ));
        }
    }
    dictionary.copy().map(Some)
}

/// Restore subclass metadata without changing the already constructed value.
///
/// # Errors
/// Rejects a dictionary on a base or slot-only object; setter errors propagate.
fn apply_dictionary(
    slf: &Bound<'_, Delta>,
    dictionary: Option<&Bound<'_, PyDict>>,
) -> PyResult<()> {
    let py = slf.py();
    let has_dictionary = !slf.is_exact_instance_of::<Delta>()
        && slf.as_any().hasattr(pyo3::intern!(py, "__dict__"))?;
    if !has_dictionary {
        if dictionary.is_some() {
            return Err(crate::error_context::value_error(
                "This Delta object cannot restore a dictionary",
            ));
        }
        return Ok(());
    }
    let replacement = match dictionary {
        Some(dictionary) => dictionary.clone(),
        None => PyDict::new(py),
    };
    slf.as_any()
        .setattr(pyo3::intern!(py, "__dict__"), replacement)
        .map_err(crate::error_context::external)
}

/// Restore Python's dictionary/slot metadata without touching immutable native fields.
fn apply_metadata(slf: &Bound<'_, Delta>, state: &Bound<'_, PyAny>) -> PyResult<()> {
    let py = slf.py();
    if let Ok(pair) = state.cast::<PyTuple>() {
        if pair.len() != 2 {
            return Err(crate::error_context::value_error(
                "Delta metadata must contain dictionary and slots",
            ));
        }
        let dictionary = decode_dictionary(&pair.get_item(0)?)?;
        let slots = decode_dictionary(&pair.get_item(1)?)?;
        if slf.is_exact_instance_of::<Delta>()
            && slots.as_ref().is_some_and(|slots| !slots.is_empty())
        {
            return Err(crate::error_context::value_error(
                "A base Delta cannot restore slots",
            ));
        }
        // A setter may mutate the caller's state dictionary. Retain the entry
        // references before any callback, rather than resuming its live iterator.
        let entries: Vec<_> = slots
            .as_ref()
            .map(|slots| {
                slots
                    .iter()
                    .map(|(k, v)| (k.unbind(), v.unbind()))
                    .collect()
            })
            .unwrap_or_default();
        apply_dictionary(slf, dictionary.as_ref())?;
        for (name, value) in entries {
            slf.setattr(name.bind(py).cast::<PyString>()?, value.bind(py))
                .map_err(crate::error_context::external)
                .map_err(|error| {
                    crate::error_context::attribute(py, error, "Delta.__setstate__", name.bind(py))
                })?;
        }
        return Ok(());
    }
    apply_dictionary(slf, decode_dictionary(state)?.as_ref())
}

/// Restore only metadata or validate a snapshot matching the existing value.
///
/// Native fields are never rewritten, even if a subclass setter reenters Python.
/// # Errors
/// Rejects malformed state, unknown versions or changed fields.
/// Pickle validation does not make untrusted pickle safe to load.
pub fn restore(slf: &Bound<'_, Delta>, state: &Bound<'_, PyAny>) -> PyResult<()> {
    if state.is_none() || state.is_exact_instance_of::<PyDict>() {
        return apply_metadata(slf, state);
    }
    if !state.is_exact_instance_of::<PyTuple>() {
        return Err(crate::error_context::type_error(
            "Delta state must be a tuple",
        ));
    }
    let state = state.cast::<PyTuple>()?;
    if state.len() == 2 {
        return apply_metadata(slf, state.as_any());
    }
    if state.len() != 4 {
        return Err(crate::error_context::value_error(
            "Delta state must contain 4 items",
        ));
    }
    let marker = state.get_item(0)?;
    if !marker.is_exact_instance_of::<PyString>()
        || marker.cast::<PyString>()?.to_str()? != "rstimes.delta"
        || integer(&state.get_item(1)?)? != 2
    {
        return Err(crate::error_context::value_error(
            "Unsupported Delta state version",
        ));
    }
    let fields = decode_fields(&state.get_item(2)?)?;
    if fields != slf.get().snapshot() {
        return Err(crate::error_context::value_error(
            "Delta values are immutable; state cannot replace fields",
        ));
    }
    apply_metadata(slf, &state.get_item(3)?)
}

use pyo3::sync::PyOnceLock;
use pyo3::types::PyType;
static RECONSTRUCTOR: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static NEWOBJ: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// Allocate a complete native snapshot, bypassing user subclass constructors.
///
/// # Preconditions
/// class is Delta or a real subtype, and all core fields are already validated.
/// # Errors
/// Propagates allocation and inherited native constructor errors.
fn allocate_snapshot<'py>(
    py: Python<'py>,
    class: &Bound<'py, PyType>,
    fields: [i64; 17],
) -> PyResult<Bound<'py, PyAny>> {
    allocate_value(py, class, Delta::from_snapshot(fields)?)
}

/// Allocate an already complete native value without unpacking unchanged fields.
/// # Preconditions
/// class is Delta or its genuine subtype; value is fully validated and immutable.
/// # Errors
/// Propagates the same checked PyO3 allocation errors as ordinary construction.
fn allocate_value<'py>(
    py: Python<'py>,
    class: &Bound<'py, PyType>,
    value: Delta,
) -> PyResult<Bound<'py, PyAny>> {
    if class.is(py.get_type::<Delta>()) {
        return Bound::new(py, value).map(Bound::into_any);
    }
    // SAFETY: Every caller proved class is Delta or a genuine subtype. This
    // pinned PyO3 0.29.3 generated-new helper delegates to its own initializer
    // and allocator, including subtype dict/weakref storage. A complete native
    // value is supplied before exposure; no payload layout is reconstructed here.
    let result = unsafe {
        let pointer = pyo3::impl_::pymethods::tp_new_impl::<_, Delta>(
            py,
            pyo3::PyClassInitializer::from(value),
            class.as_type_ptr(),
        )?;
        Bound::from_owned_ptr(py, pointer)
    };
    Ok(result)
}

/// Reconstruct a complete immutable Delta from this package's trusted pickle.
///
/// # Errors
/// Rejects non-Delta classes and malformed fields; cached hashes never replace field-derived values.
#[pyfunction]
#[pyo3(signature = (class, data))]
pub fn _restore_delta<'py>(
    class: &Bound<'py, PyType>,
    data: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    if !class.is_subclass(&py.get_type::<Delta>())? {
        return Err(crate::error_context::type_error(
            "Delta reconstruction requires a Delta class",
        ));
    }
    let fields = if let Ok(bytes) = data.cast::<PyBytes>() {
        decode_bytes(bytes)?
    } else {
        decode_fields(data)?
    };
    allocate_snapshot(py, class, fields)
}

/// Return a complete-value reconstructor and separate subclass state for pickle.
///
/// Fields exist before pickle installs metadata, so self references and cycles
/// cannot observe or modify an incomplete value. User constructors are bypassed.
/// # Errors
/// Propagates class/state lookup and allocation errors.
pub fn reduce<'py>(slf: &Bound<'py, Delta>) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    let constructor = crate::python_cache::get_or_prepare(&RECONSTRUCTOR, py, || {
        Ok::<_, PyErr>(
            py.import("rstimes._native")?
                .getattr("_restore_delta")
                .map_err(crate::error_context::external)?
                .unbind(),
        )
    })?;
    let payload = encode(py, slf.get().snapshot());
    let dictionary = if overrides(slf, "__getstate__", &DELTA_STATE)? {
        slf.call_method0("__getstate__")
            .map_err(crate::error_context::external)?
    } else {
        capture_metadata(slf)?
    };
    if crate::protocol::uses_native_new(&slf.get_type()) {
        let constructor = crate::python_cache::get_or_prepare(&NEWOBJ, py, || {
            Ok::<_, PyErr>(
                py.import("copyreg")?
                    .getattr("__newobj__")
                    .map_err(crate::error_context::external)?
                    .unbind(),
            )
        })?;
        return Ok(
            (constructor.bind(py), (slf.get_type(), payload), dictionary)
                .into_pyobject(py)?
                .into_any(),
        );
    }
    Ok(
        (constructor.bind(py), (slf.get_type(), payload), dictionary)
            .into_pyobject(py)?
            .into_any(),
    )
}

/// Return a distinct shallow/deep copy with the same immutable values and subtype.
///
/// Deepcopy registers the new object before recursive metadata copying so shared
/// references and cycles retain Python's normal copy behavior.
/// # Errors
/// Propagates allocation, dictionary setter and deepcopy callback errors.
pub fn copy_object<'py>(
    slf: &Bound<'py, Delta>,
    memo: Option<&Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    if slf.is_exact_instance_of::<Delta>() {
        let result = Bound::new(py, slf.get().copied())?.into_any();
        if let Some(memo) = memo {
            memo.set_item(slf.as_ptr() as usize, &result)?;
        }
        return Ok(result);
    }
    let result = allocate_value(py, &slf.get_type(), slf.get().copied())?;
    if let Some(memo) = memo {
        memo.set_item(slf.as_ptr() as usize, &result)?;
    }
    let metadata = capture_metadata(slf)?;
    let metadata = if let Some(memo) = memo {
        py.import("copy")?
            .getattr("deepcopy")
            .map_err(crate::error_context::external)?
            .call1((&metadata, memo))
            .map_err(crate::error_context::external)?
    } else {
        metadata
    };
    // These dictionaries were just captured and copied here, rather than read
    // from external state. Attach each owned copy once without recopying it.
    if let Ok(pair) = metadata.cast::<PyTuple>() {
        let dictionary = pair.get_item(0)?;
        let dictionary = if dictionary.is_none() {
            dictionary
        } else {
            dictionary.cast::<PyDict>()?.copy()?.into_any()
        };
        // deepcopy can expose its copied slot dictionary through memo. Retain
        // every entry before either a __dict__ setter or a slot setter runs.
        let entries = pair
            .get_item(1)?
            .cast::<PyDict>()?
            .iter()
            .map(|(name, value)| Ok((name.cast_into::<PyString>()?, value)))
            .collect::<PyResult<Vec<_>>>()?;
        if !dictionary.is_none() {
            result.setattr(pyo3::intern!(py, "__dict__"), dictionary)?;
        }
        for (name, value) in entries {
            result.setattr(name, value)?;
        }
    } else if !metadata.is_none() {
        let dictionary = metadata.cast::<PyDict>()?.copy()?;
        result.setattr(pyo3::intern!(py, "__dict__"), dictionary)?;
    }
    Ok(result)
}
