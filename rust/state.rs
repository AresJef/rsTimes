//! Versioned state for this package, checked completely before field commit.
use crate::delta::Delta;
use pyo3::exceptions::{PyAttributeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyInt, PyString, PyTuple};

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

fn integer(value: &Bound<'_, PyAny>) -> PyResult<i64> {
    if !value.is_exact_instance_of::<PyInt>() {
        return Err(PyTypeError::new_err(
            "Delta state integers must be exact int values",
        ));
    }
    value.extract()
}

pub fn restore(slf: &Bound<'_, Delta>, state: &Bound<'_, PyAny>) -> PyResult<()> {
    let py = slf.py();
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
    let data = state.get_item(2)?;
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
    let cache = integer(&state.get_item(3)?)? as isize;
    let raw = fields == [0; 15] && cache == 0;
    if i32::try_from(fields[0]).is_err() || !(0..12).contains(&fields[1]) {
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
        if !raw && value != -1 && !(minimum..=maximum).contains(&value) {
            return Err(PyValueError::new_err(
                "Delta state absolute field is out of range",
            ));
        }
    }
    if !raw && cache != -1 && cache != data.hash()? {
        return Err(PyValueError::new_err(
            "Delta state hash does not match its fields",
        ));
    }
    let dictionary = state.get_item(4)?;
    let has_dictionary = !slf.is_exact_instance_of::<Delta>()
        && slf.as_any().hasattr(pyo3::intern!(py, "__dict__"))?;
    if !dictionary.is_none() {
        if !dictionary.is_exact_instance_of::<PyDict>() {
            return Err(PyTypeError::new_err(
                "Delta state dictionary must be dict or None",
            ));
        }
        if !has_dictionary {
            return Err(PyValueError::new_err(
                "Base Delta cannot restore a dictionary",
            ));
        }
        for key in dictionary.cast::<PyDict>()?.keys().iter() {
            if !key.is_exact_instance_of::<PyString>() {
                return Err(PyTypeError::new_err(
                    "Delta state dictionary keys must be strings",
                ));
            }
        }
    }
    if has_dictionary {
        let replacement = if dictionary.is_none() {
            PyDict::new(py)
        } else {
            dictionary.cast::<PyDict>()?.copy()?
        };
        slf.as_any()
            .setattr(pyo3::intern!(py, "__dict__"), replacement)?;
    }
    // Everything has validated, and the possible Python setter has completed.
    slf.borrow().restore_fields(fields, cache);
    Ok(())
}

pub fn reduce<'py>(slf: &Bound<'py, Delta>) -> PyResult<Bound<'py, PyAny>> {
    let py = slf.py();
    // The standard new-object helper lets pickle use NEWOBJ for protocols >=2
    // and bypass __init__, including subclasses with required arguments.
    let restore = NEWOBJ.get_or_try_init(py, || -> PyResult<_> {
        Ok(py
            .import("copyreg")?
            .getattr(pyo3::intern!(py, "__newobj__"))?
            .unbind())
    })?;
    let class = slf.as_any().getattr(pyo3::intern!(py, "__class__"))?;
    Ok((restore.bind(py), (class,), capture(slf)?)
        .into_pyobject(py)?
        .into_any())
}

use pyo3::sync::PyOnceLock;
static NEW: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static NEWOBJ: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// Copy our already-validated native payload; serialized external state still
/// follows every check in restore(). Deepcopy uses Python's memo before dict
/// recursion, so cycles point to the newly allocated object.
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
    let fields = slf.get().snapshot();
    let cache = slf.get().cached_hash();
    let constructor = NEW.get_or_try_init(py, || -> PyResult<_> {
        Ok(py.get_type::<Delta>().getattr("__new__")?.unbind())
    })?;
    let result = constructor.bind(py).call1((slf.get_type(),))?;
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
    result.cast::<Delta>()?.get().restore_fields(fields, cache);
    Ok(result)
}
