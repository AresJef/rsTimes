//! Versioned serialization and copying for this package's Delta objects.
//!
//! The state marker is rstimes.delta and the format version is 1. External state
//! is fully validated before native fields are committed; trusted native copies
//! reuse that validated payload. Pickle can execute Python code and is supported
//! only for trusted data. Old cyTimes pickle and Cython entry points are excluded.

use crate::delta::Delta;
use pyo3::exceptions::{PyAttributeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyInt, PyString, PyTuple};

/// Capture this package's five-item versioned pickle state.
///
/// # Returns
/// (marker, version, fields, cached_hash, dictionary), where marker is
/// rstimes.delta, version is 1, fields contains 15 integers, and dictionary is
/// None or a shallow copy of a subclass dictionary.
///
/// # Errors
/// Propagates allocation and subclass dictionary access errors.
pub fn capture<'py>(slf: &Bound<'py, Delta>) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    let value = slf.borrow();
    let fields = PyTuple::new(py, value.snapshot())?;
    let cache = value.cached_hash();
    drop(value);
    let dictionary = if slf.is_exact_instance_of::<Delta>() {
        py.None().into_bound(py)
    } else {
        match slf.as_any().getattr(pyo3::intern!(py, "__dict__")) {
            Ok(value) => value.cast::<PyDict>()?.copy()?.into_any(),
            Err(error) if error.is_instance_of::<PyAttributeError>(py) => py.None().into_bound(py),
            Err(error) => return Err(error),
        }
    };
    Ok(("rstimes.delta", 1, fields, cache, dictionary)
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
        return Err(PyTypeError::new_err(
            "Delta state integers must be exact int values",
        ));
    }
    value.extract()
}

/// Validate canonical serialized fields and their optional cached hash.
///
/// # Errors
/// Rejects malformed containers, noncanonical ranges and forged hash caches.
fn decode_fields(
    data: &Bound<'_, PyAny>,
    cache: &Bound<'_, PyAny>,
) -> PyResult<([i64; 15], isize)> {
    if !data.is_exact_instance_of::<PyTuple>() {
        return Err(PyTypeError::new_err("Delta state fields must be a tuple"));
    }
    let data = data.cast::<PyTuple>()?;
    if data.len() != 15 {
        return Err(PyValueError::new_err("Delta state must contain 15 fields"));
    }
    let mut fields = [0; 15];
    for (index, value) in data.iter().enumerate() {
        fields[index] = integer(&value)?;
    }
    let cache = isize::try_from(integer(cache)?).map_err(|_| {
        pyo3::exceptions::PyOverflowError::new_err("Delta hash cache is out of range")
    })?;
    validate_fields(&fields)?;
    if cache != -1 && cache != data.hash()? {
        return Err(PyValueError::new_err(
            "Delta state hash does not match its fields",
        ));
    }
    Ok((fields, cache))
}

/// Check canonical native ranges independently of their external encoding.
/// # Errors
/// Rejects invalid relative/absolute fields before any native value is allocated.
fn validate_fields(fields: &[i64; 15]) -> PyResult<()> {
    if !(0..12).contains(&fields[1]) {
        return Err(PyValueError::new_err(
            "Delta state relative year/month is out of range",
        ));
    }
    for (index, maximum) in [(3, 23), (4, 59), (5, 59), (6, 999_999)] {
        if !(0..=maximum).contains(&fields[index]) {
            return Err(PyValueError::new_err(
                "Delta state relative time is out of range",
            ));
        }
    }
    for (offset, maximum) in [9_999, 12, 31, 6, 23, 59, 59, 999_999]
        .into_iter()
        .enumerate()
    {
        let value = fields[7 + offset];
        let minimum = if offset < 3 { 1 } else { 0 };
        if value != -1 && !(minimum..=maximum).contains(&value) {
            return Err(PyValueError::new_err(
                "Delta state absolute field is out of range",
            ));
        }
    }
    Ok(())
}

const PAYLOAD_MARKER: &[u8; 8] = b"rstDlt\0\x01";

/// Encode exact native values as versioned little-endian bytes, without PyInts.
fn encode<'py>(py: Python<'py>, fields: [i64; 15], cache: isize) -> Bound<'py, PyBytes> {
    let mut bytes = [0_u8; 136];
    bytes[..8].copy_from_slice(PAYLOAD_MARKER);
    for (index, value) in fields.into_iter().chain([cache as i64]).enumerate() {
        bytes[8 + index * 8..16 + index * 8].copy_from_slice(&value.to_le_bytes());
    }
    PyBytes::new(py, &bytes)
}

/// Decode the package's complete constructor payload before exposing an object.
/// # Errors
/// Rejects wrong version/length, noncanonical fields and forged cached hashes.
fn decode_bytes(value: &Bound<'_, PyBytes>) -> PyResult<([i64; 15], isize)> {
    let bytes = value.as_bytes();
    if bytes.len() != 136 || bytes[..8] != *PAYLOAD_MARKER {
        return Err(PyValueError::new_err(
            "Unsupported Delta reconstruction payload",
        ));
    }
    let mut fields = [0_i64; 15];
    let mut cache = -1;
    for (index, chunk) in bytes[8..].chunks_exact(8).enumerate() {
        let number = i64::from_le_bytes(std::array::from_fn(|offset| chunk[offset]));
        if index < 15 {
            fields[index] = number;
        } else {
            cache = isize::try_from(number).map_err(|_| {
                pyo3::exceptions::PyOverflowError::new_err("Delta hash cache is out of range")
            })?;
        }
    }
    validate_fields(&fields)?;
    if cache != -1 && Delta::from_snapshot(fields, -1).__hash__(value.py())? != cache {
        return Err(PyValueError::new_err(
            "Delta state hash does not match its fields",
        ));
    }
    Ok((fields, cache))
}

/// Recognize internal reconstruction forms while ordinary numeric inputs continue.
/// # Errors
/// Complete byte payloads receive the same strict range/hash validation as state.
#[inline]
pub(crate) fn construction_value(args: &Bound<'_, PyTuple>) -> PyResult<Option<Delta>> {
    // The caller checked a one-item tuple; it owns the borrowed item throughout.
    let value =
        unsafe { Borrowed::from_ptr(args.py(), pyo3::ffi::PyTuple_GET_ITEM(args.as_ptr(), 0)) };
    if let Ok(bytes) = value.cast::<PyBytes>() {
        if bytes.as_bytes().starts_with(&PAYLOAD_MARKER[..7]) {
            let (fields, cache) = decode_bytes(&bytes)?;
            return Ok(Some(Delta::from_snapshot(fields, cache)));
        }
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
        return Err(PyTypeError::new_err(
            "Delta state dictionary must be dict or None",
        ));
    }
    let dictionary = value.cast::<PyDict>()?;
    for key in dictionary.keys().iter() {
        if !key.is_exact_instance_of::<PyString>() {
            return Err(PyTypeError::new_err(
                "Delta state dictionary keys must be strings",
            ));
        }
    }
    Ok(Some(dictionary.clone()))
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
            return Err(PyValueError::new_err(
                "This Delta object cannot restore a dictionary",
            ));
        }
        return Ok(());
    }
    let replacement = match dictionary {
        Some(dictionary) => dictionary.copy()?,
        None => PyDict::new(py),
    };
    slf.as_any()
        .setattr(pyo3::intern!(py, "__dict__"), replacement)
}

/// Restore only metadata or validate a snapshot matching the existing value.
///
/// Native fields are never rewritten, even if a subclass setter reenters Python.
/// # Errors
/// Rejects malformed state, unknown versions, forged caches or changed fields.
/// Pickle validation does not make untrusted pickle safe to load.
pub fn restore(slf: &Bound<'_, Delta>, state: &Bound<'_, PyAny>) -> PyResult<()> {
    if state.is_none() || state.is_exact_instance_of::<PyDict>() {
        return apply_dictionary(slf, decode_dictionary(state)?.as_ref());
    }
    if !state.is_exact_instance_of::<PyTuple>() {
        return Err(PyTypeError::new_err("Delta state must be a tuple"));
    }
    let state = state.cast::<PyTuple>()?;
    if state.len() != 5 {
        return Err(PyValueError::new_err("Delta state must contain 5 items"));
    }
    let marker = state.get_item(0)?;
    if !marker.is_exact_instance_of::<PyString>()
        || marker.cast::<PyString>()?.to_str()? != "rstimes.delta"
        || integer(&state.get_item(1)?)? != 1
    {
        return Err(PyValueError::new_err("Unsupported Delta state version"));
    }
    let (fields, _) = decode_fields(&state.get_item(2)?, &state.get_item(3)?)?;
    let dictionary = decode_dictionary(&state.get_item(4)?)?;
    if fields != slf.get().snapshot() {
        return Err(PyValueError::new_err(
            "Delta values are immutable; state cannot replace fields",
        ));
    }
    apply_dictionary(slf, dictionary.as_ref())
}

use pyo3::sync::PyOnceLock;
use pyo3::types::PyType;
static RECONSTRUCTOR: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static NEWOBJ: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// Allocate a complete native snapshot, bypassing user subclass constructors.
///
/// # Preconditions
/// class is Delta or a real subtype, and fields/cache are already validated.
/// # Errors
/// Propagates allocation and inherited native constructor errors.
fn allocate_snapshot<'py>(
    py: Python<'py>,
    class: &Bound<'py, PyType>,
    fields: [i64; 15],
    cache: isize,
) -> PyResult<Bound<'py, PyAny>> {
    allocate_value(py, class, Delta::from_snapshot(fields, cache))
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
/// Rejects non-Delta classes, malformed fields and invalid hash caches.
#[pyfunction]
#[pyo3(signature = (class, data, cache=None))]
pub fn _restore_delta<'py>(
    class: &Bound<'py, PyType>,
    data: &Bound<'py, PyAny>,
    cache: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = class.py();
    if !class.is_subclass(&py.get_type::<Delta>())? {
        return Err(PyTypeError::new_err(
            "Delta reconstruction requires a Delta class",
        ));
    }
    let (fields, cache) = if let Ok(bytes) = data.cast::<PyBytes>() {
        if cache.is_some() {
            return Err(PyTypeError::new_err("Byte payload includes its hash cache"));
        }
        decode_bytes(bytes)?
    } else {
        decode_fields(
            data,
            cache.ok_or_else(|| PyTypeError::new_err("Delta state requires its hash cache"))?,
        )?
    };
    allocate_snapshot(py, class, fields, cache)
}

/// Return a complete-value reconstructor and separate subclass state for pickle.
///
/// Fields exist before pickle installs metadata, so self references and cycles
/// cannot observe or modify an incomplete value. User constructors are bypassed.
/// # Errors
/// Propagates class/state lookup and allocation errors.
pub fn reduce<'py>(slf: &Bound<'py, Delta>) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    let constructor = RECONSTRUCTOR.get_or_try_init(py, || {
        Ok::<_, PyErr>(
            py.import("rstimes._native")?
                .getattr("_restore_delta")?
                .unbind(),
        )
    })?;
    let payload = encode(py, slf.get().snapshot(), slf.get().cached_hash());
    let dictionary = if slf.is_exact_instance_of::<Delta>() {
        py.None().into_bound(py)
    } else {
        match slf.as_any().getattr(pyo3::intern!(py, "__dict__")) {
            Ok(dictionary) => dictionary.cast::<PyDict>()?.copy()?.into_any(),
            Err(error) if error.is_instance_of::<PyAttributeError>(py) => py.None().into_bound(py),
            Err(error) => return Err(error),
        }
    };
    if crate::protocol::uses_native_new(&slf.get_type()) {
        let constructor = NEWOBJ.get_or_try_init(py, || {
            Ok::<_, PyErr>(py.import("copyreg")?.getattr("__newobj__")?.unbind())
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
    let dictionary = match slf.as_any().getattr("__dict__") {
        Ok(value) => Some(value),
        Err(error) if error.is_instance_of::<PyAttributeError>(py) => None,
        Err(error) => return Err(error),
    };
    if let Some(dictionary) = dictionary {
        let dictionary = if let Some(memo) = memo {
            py.import("copy")?
                .getattr("deepcopy")?
                .call1((&dictionary, memo))?
        } else {
            dictionary.cast::<PyDict>()?.copy()?.into_any()
        };
        result.setattr("__dict__", dictionary)?;
    }
    Ok(result)
}
