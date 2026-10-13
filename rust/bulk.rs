//! Ordered bulk addition with shared immutable Delta fields.
//!
//! Only exact builtin operands use the checked native kernels directly.
//! Subclasses and foreign objects retain Python's full reflected dispatch.
//! Owned item references survive user callbacks that mutate an input list.

use crate::delta::{Delta, PreparedAddition};
use pyo3::exceptions::PyRuntimeError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyDate, PyDateTime, PyDelta, PyList, PyString, PyTuple};
use std::panic::{AssertUnwindSafe, catch_unwind};

// These types remain alive through CPython/PyO3's interpreter type caches.
// The batch holds the GIL and never writes their pointers or shares the table.
struct Types {
    delta: *mut ffi::PyTypeObject,
    datetime: *mut ffi::PyTypeObject,
    date: *mut ffi::PyTypeObject,
    duration: *mut ffi::PyTypeObject,
}

/// Shared batch context, kept visible to the loop rather than behind a closure call.
struct Batch<'a, 'py> {
    slf: &'a Bound<'py, Delta>,
    fields: &'a [i64; 15],
    date_fields: &'a [i64; 15],
    empty: bool,
    native: bool,
    types: &'a Types,
    addition: &'a PreparedAddition,
    numpy: Option<crate::numpy_scalar::ExactTypes>,
}

impl<'py> Batch<'_, 'py> {
    /// Allocate an independent base Delta using the batch's already checked type.
    ///
    /// # Errors
    /// Propagates the same PyO3 allocation and initialization errors as Bound::new.
    #[inline(always)]
    fn allocate_delta(&self, value: Delta) -> PyResult<Bound<'py, PyAny>> {
        // SAFETY: types.delta is the ready exact Delta type from py.get_type;
        // the GIL and interpreter cache keep it live. This pinned SDK helper
        // initializes the complete Rust payload and all Python storage; no
        // private payload offsets or allocator layout are reproduced here.
        let pointer = unsafe {
            pyo3::impl_::pymethods::tp_new_impl::<_, Delta>(
                self.slf.py(),
                pyo3::PyClassInitializer::from(value),
                self.types.delta,
            )?
        };
        Ok(unsafe { Bound::from_owned_ptr(self.slf.py(), pointer) })
    }

    /// Compute an item from primitive native data, preserving foreign callbacks.
    /// # Errors
    /// Preserves overflow, date boundaries, allocation and Python exceptions.
    #[inline(always)]
    fn add(&self, value: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        if self.native {
            // SAFETY: value is owned for this call. Exact type equality below
            // establishes the native layout before each unchecked borrowed cast.
            let actual = unsafe { ffi::Py_TYPE(value.as_ptr()) };
            if actual == self.types.delta {
                return self.allocate_delta(
                    self.addition
                        .add_delta(unsafe { value.cast_unchecked::<Delta>() }.get())?,
                );
            }
            if actual == self.types.datetime {
                return crate::interop::apply_datetime_fields(
                    self.fields,
                    self.empty,
                    value,
                    unsafe { value.cast_unchecked::<PyDateTime>() },
                    1,
                )?
                .ok_or_else(|| PyRuntimeError::new_err("Datetime kernel returned no result"));
            }
            if actual == self.types.date {
                return crate::interop::apply_date_only_fields(
                    self.date_fields,
                    self.empty,
                    value,
                    unsafe { value.cast_unchecked::<PyDate>() },
                    1,
                )?
                .ok_or_else(|| PyRuntimeError::new_err("Date kernel returned no result"));
            }
            if actual == self.types.duration {
                return self.allocate_delta(
                    self.addition
                        .add_duration(unsafe { value.cast_unchecked::<PyDelta>() })?,
                );
            }
        }
        if self.native {
            if let Some(numpy) = &self.numpy {
                if let Some((micros, datetime)) = numpy.microseconds(value)? {
                    if datetime {
                        return crate::numpy_scalar::apply_datetime_fields_us(
                            self.slf.py(),
                            self.fields,
                            self.empty,
                            micros,
                            1,
                        );
                    }
                    return self.allocate_delta(self.addition.add_microseconds(micros)?);
                }
            }
        }
        self.add_foreign(value)
    }

    /// Retain the current item and run the complete Python addition protocol.
    /// # Errors
    /// Preserves callback, allocation and reflected-operation errors.
    #[inline(always)]
    fn add_foreign(&self, value: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        // Foreign callbacks may resize the input list and remove its current item.
        // Own a reference before dispatch; exact native kernels finish all input
        // reads before allocation and do not call user arithmetic methods.
        let value = value.clone();
        // SAFETY: Both operands are live owned/borrowed Bound values. PyNumber_Add
        // performs full Python reflected dispatch and returns a new reference or
        // null with an exception; it never steals either operand reference.
        unsafe {
            Bound::from_owned_ptr_or_err(
                self.slf.py(),
                ffi::PyNumber_Add(value.as_ptr(), self.slf.as_ptr()),
            )
        }
    }
}

/// Fill a live exact list using one fixed batch dispatch mode.
///
/// Foreign-first batches already select full Python dispatch for every item.
/// Keep their loop frame independent of the unused native calendar/Delta paths;
/// both modes still own items across callbacks and reread the live input size.
/// # Errors
/// Propagates the same input, arithmetic and output errors as the general loop.
#[inline(never)]
fn fill_list<'py, const NATIVE: bool>(
    batch: &Batch<'_, 'py>,
    values: &Bound<'py, PyList>,
    mut output: Output<'py>,
) -> PyResult<Bound<'py, PyList>> {
    let mut index = 0;
    while index < values.len() {
        // SAFETY: The live length was checked under the GIL. No callback runs
        // before borrowing this slot; foreign dispatch owns it before calling
        // Python, and native kernels finish reads before any allocation.
        let value = unsafe {
            Borrowed::from_ptr(
                values.py(),
                ffi::PyList_GET_ITEM(values.as_ptr(), index as isize),
            )
        };
        let result = if NATIVE {
            batch.add(&value)?
        } else {
            batch.add_foreign(&value)?
        };
        output.push(result)?;
        index += 1;
    }
    output.finish()
}

/// Keep ordinary Delta additions in a compact loop, using the shared kernels.
///
/// Each item is checked independently. A later foreign item still receives full
/// dispatch, and the live input length is reread after every possible callback.
/// Separating this loop avoids carrying the calendar and NumPy branches through
/// the common Delta-only path without assuming that a list is homogeneous.
///
/// # Errors
/// Preserves checked arithmetic, foreign callbacks and output allocation errors.
#[inline(never)]
fn fill_delta_list<'py, const REPLACE: bool>(
    batch: &Batch<'_, 'py>,
    values: &Bound<'py, PyList>,
    mut output: Output<'py>,
) -> PyResult<Bound<'py, PyList>> {
    let mut index = 0;
    while index < values.len() {
        // SAFETY: The live input list owns this slot under the GIL. The exact
        // type check proves the Delta layout; its complete payload is read
        // before allocation. Other items retain Batch::add's callback ownership.
        let value = unsafe {
            Borrowed::from_ptr(
                values.py(),
                ffi::PyList_GET_ITEM(values.as_ptr(), index as isize),
            )
        };
        let result = if unsafe { ffi::Py_TYPE(value.as_ptr()) } == batch.types.delta {
            batch.allocate_delta(batch.addition.add_delta_prepared::<REPLACE>(
                unsafe { value.cast_unchecked::<Delta>() }.get(),
            )?)?
        } else {
            batch.add(&value)?
        };
        output.push(result)?;
        index += 1;
    }
    output.finish()
}

/// Fill a foreign-first list using the public Python addition protocol.
///
/// Every input has a strong reference across callbacks. Errors are fetched
/// before releasing it; the visible output always contains complete objects.
/// # Errors
/// Propagates Python operation and output allocation errors unchanged.
#[inline(never)]
fn fill_foreign_list<'py, const DATE: bool, const RELATIVE: bool>(
    batch: &Batch<'_, 'py>,
    values: &Bound<'py, PyList>,
    mut output: Output<'py>,
) -> PyResult<Bound<'py, PyList>> {
    let slf = batch.slf;
    let py = values.py();
    let relative_type = crate::interop::exact_relative_type(py).unwrap_or(std::ptr::null_mut());
    let relative_keys = RELATIVE.then(|| crate::interop::relative_keys(py));
    let date_type = if DATE {
        py.get_type::<PyDate>().as_type_ptr()
    } else {
        std::ptr::null_mut()
    };
    // used is also the number of consumed inputs; callbacks can change Python
    // lists, but cannot change this Rust counter. Keep only one live index.
    while output.used < values.len() {
        // SAFETY: The GIL and freshly checked live size protect the slot.
        // Its new reference survives callbacks which remove it from the list.
        let item =
            unsafe { ffi::Py_NewRef(ffi::PyList_GET_ITEM(values.as_ptr(), output.used as isize)) };
        let result = if DATE && unsafe { ffi::PyObject_TypeCheck(item, date_type) } != 0 {
            let value = unsafe { Borrowed::from_ptr(py, item) };
            add_date_subclass(batch, &value)
        } else if RELATIVE && unsafe { ffi::Py_TYPE(item) } == relative_type {
            let value = unsafe { Borrowed::from_ptr(py, item) };
            add_relative(
                batch,
                &value,
                relative_keys
                    .as_ref()
                    .ok_or_else(|| PyRuntimeError::new_err("Missing relative names"))?,
            )
        } else {
            let result = unsafe { ffi::PyNumber_Add(item, slf.as_ptr()) };
            unsafe { Bound::from_owned_ptr_or_err(py, result) }
        };
        // Preserve error-fetch-before-destructor ordering of the Bound path.
        unsafe { ffi::Py_DECREF(item) };
        output.push(result?)?;
    }
    output.finish()
}

/// Run both required addition turns for a date subtype and an exact Delta.
///
/// These native layouts cannot inherit from each other, so Python always gives
/// the date's live addition slot the first turn. Patched methods, user results,
/// errors and NotImplemented all retain that order. The immutable Delta then
/// uses the same reflected method as its numeric slot, without redispatching.
/// # Errors
/// Propagates either operation's exception; preserves the numeric panic policy.
#[inline(never)]
fn add_date_subclass<'py>(
    batch: &Batch<'_, 'py>,
    value: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let slf = batch.slf;
    // SAFETY: Caller owns both objects, has checked actual date inheritance and
    // exact Delta identity, and holds the GIL. The ready type owns its slots.
    let number = unsafe { (*ffi::Py_TYPE(value.as_ptr())).tp_as_number };
    if let Some(slot) = unsafe { number.as_ref() }.and_then(|number| number.nb_add) {
        let result = unsafe { slot(value.as_ptr(), slf.as_ptr()) };
        if result != unsafe { ffi::Py_NotImplemented() } {
            return unsafe { Bound::from_owned_ptr_or_err(slf.py(), result) };
        }
        unsafe { ffi::Py_DECREF(result) };
    }
    catch_unwind(AssertUnwindSafe(|| {
        if let Ok(dt) = value.cast::<PyDateTime>() {
            crate::interop::apply_datetime_fields_vector(batch.fields, batch.empty, value, dt, 1)?
                .ok_or_else(|| PyRuntimeError::new_err("Datetime kernel returned no result"))
        } else {
            slf.get().__radd__(value)
        }
    }))
    .unwrap_or_else(|_| Err(PyRuntimeError::new_err("Rust panic while applying Delta")))
}

/// Preserve the live foreign addition turn, then use the prepared native fallback.
///
/// Exact identity is rechecked after callbacks; a changed class uses the same
/// reflected method as ordinary addition. Both operands remain live throughout.
/// # Errors
/// Propagates foreign callback, normalization, arithmetic and allocation errors.
#[inline(never)]
fn add_relative<'py>(
    batch: &Batch<'_, 'py>,
    value: &Bound<'py, PyAny>,
    keys: &[Py<PyString>; 17],
) -> PyResult<Bound<'py, PyAny>> {
    // SAFETY: The GIL and the caller's strong references protect the current
    // type and its live slots. The unrelated exact Delta takes the second turn.
    let number = unsafe { (*ffi::Py_TYPE(value.as_ptr())).tp_as_number };
    if let Some(slot) = unsafe { number.as_ref() }.and_then(|number| number.nb_add) {
        let result = unsafe { slot(value.as_ptr(), batch.slf.as_ptr()) };
        if result != unsafe { ffi::Py_NotImplemented() } {
            return unsafe { Bound::from_owned_ptr_or_err(batch.slf.py(), result) };
        }
        unsafe { ffi::Py_DECREF(result) };
    }
    catch_unwind(AssertUnwindSafe(|| {
        if crate::interop::exact_relative_type(value.py())
            .is_some_and(|class| unsafe { ffi::Py_TYPE(value.as_ptr()) } == class)
        {
            let fields = crate::interop::relative_fields_named(value, keys)?;
            batch.allocate_delta(batch.addition.add_fields(fields)?)
        } else {
            batch.slf.get().__radd__(value)
        }
    }))
    .unwrap_or_else(|_| Err(PyRuntimeError::new_err("Rust panic while applying Delta")))
}

/// Apply value + Delta in input order and return a complete Python list.
///
/// Exact lists use live indexed iteration, matching list iteration after a
/// callback changes their length. Tuple and general iterables preserve their
/// normal iteration. The immutable Delta snapshot is safe across all callbacks.
/// # Errors
/// Propagates iteration/addition errors and translates allocation failures.
pub(crate) fn apply<'py>(
    slf: &Bound<'py, Delta>,
    values: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyList>> {
    let addition = PreparedAddition::new(slf.get());
    let fields = slf.get().snapshot();
    let date_fields = slf.get().calendar_snapshot(false);
    let empty = !slf.get().__bool__();
    let exact_delta = slf.is_exact_instance_of::<Delta>();
    let py = slf.py();
    let types = Types {
        delta: py.get_type::<Delta>().as_type_ptr(),
        datetime: py.get_type::<PyDateTime>().as_type_ptr(),
        date: py.get_type::<PyDate>().as_type_ptr(),
        duration: py.get_type::<PyDelta>().as_type_ptr(),
    };
    let capacity = if values.is_exact_instance_of::<PyList>() {
        values.cast::<PyList>()?.len()
    } else if values.is_exact_instance_of::<PyTuple>() {
        values.cast::<PyTuple>()?.len()
    } else {
        0
    };
    // A first foreign operand chooses full Python dispatch for the whole
    // sequence. This is correct for later builtin values too, and avoids four
    // redundant type comparisons per item in ordinary foreign batches.
    let numpy = if exact_delta && values.is_exact_instance_of::<PyList>() && capacity > 0 {
        let first = values.cast::<PyList>()?.get_item(0)?;
        match crate::numpy_scalar::ExactTypes::cached(py) {
            Some(types) => Some(types),
            None => crate::numpy_scalar::ExactTypes::for_first(&first)?,
        }
    } else {
        None
    };
    let native = if exact_delta && values.is_exact_instance_of::<PyList>() && capacity > 0 {
        let first = values.cast::<PyList>()?.get_item(0)?;
        // SAFETY: The owned first object is live and its actual type is read only.
        let actual = unsafe { ffi::Py_TYPE(first.as_ptr()) };
        numpy.as_ref().is_some_and(|types| types.matches(&first))
            || [types.delta, types.datetime, types.date, types.duration].contains(&actual)
    } else {
        exact_delta
    };
    // Callback-free native results benefit from one initialized allocation.
    // For subclasses/foreign operands, a growing list avoids initializing None
    // and makes cyclic GC scan only the completed prefix during callbacks.
    let reserved = if exact_delta && values.is_exact_instance_of::<PyList>() && capacity > 0 {
        let first = values.cast::<PyList>()?.get_item(0)?;
        // SAFETY: The owned first item keeps its ready actual type alive.
        let actual = unsafe { ffi::Py_TYPE(first.as_ptr()) };
        if [types.delta, types.datetime, types.date, types.duration].contains(&actual)
            || numpy.as_ref().is_some_and(|types| types.matches(&first))
        {
            capacity
        } else {
            0
        }
    } else {
        0
    };
    let mut output = Output::new(py, reserved)?;
    let batch = Batch {
        slf,
        fields: &fields,
        date_fields: &date_fields,
        empty,
        native,
        types: &types,
        addition: &addition,
        numpy,
    };
    if values.is_exact_instance_of::<PyList>() {
        let values = values.cast::<PyList>()?;
        return if native {
            if !values.is_empty()
                && unsafe { ffi::Py_TYPE(ffi::PyList_GET_ITEM(values.as_ptr(), 0)) } == types.delta
            {
                if addition.has_absolute() {
                    fill_delta_list::<true>(&batch, values, output)
                } else {
                    fill_delta_list::<false>(&batch, values, output)
                }
            } else {
                fill_list::<true>(&batch, values, output)
            }
        } else {
            if exact_delta
                && !values.is_empty()
                && unsafe {
                    ffi::PyObject_TypeCheck(ffi::PyList_GET_ITEM(values.as_ptr(), 0), types.date)
                } != 0
            {
                fill_foreign_list::<true, false>(&batch, values, output)
            } else if exact_delta
                && !values.is_empty()
                && crate::interop::exact_relative_type(py).is_some_and(|class| unsafe {
                    ffi::Py_TYPE(ffi::PyList_GET_ITEM(values.as_ptr(), 0)) == class
                })
            {
                fill_foreign_list::<false, true>(&batch, values, output)
            } else {
                fill_foreign_list::<false, false>(&batch, values, output)
            }
        };
    } else if values.is_exact_instance_of::<PyTuple>() {
        for value in values.cast::<PyTuple>()?.iter() {
            output.push(batch.add(&value)?)?;
        }
    } else {
        for value in values.try_iter()? {
            output.push(batch.add(&value?)?)?;
        }
    }
    output.finish()
}

/// A result list initialized before any allocation or foreign callback.
///
/// Even gc.get_objects() must never expose uninitialized list slots. Reserved
/// slots start as None; checked replacement also handles an unusual callback
/// that discovers and changes this list through the garbage collector.
struct Output<'py> {
    list: Bound<'py, PyList>,
    reserved: usize,
    used: usize,
}

impl<'py> Output<'py> {
    /// Allocate the expected list once, checking allocation before any writes.
    /// # Errors
    /// Propagates Python allocation failure.
    fn new(py: Python<'py>, length: usize) -> PyResult<Self> {
        // Input list/tuple length already fits Py_ssize_t.
        let list = unsafe { Bound::from_owned_ptr_or_err(py, ffi::PyList_New(length as isize))? }
            .cast_into::<PyList>()?;
        for index in 0..length {
            // SAFETY: No callback runs between allocation and complete slot
            // initialization. Each bounded null slot receives an owned None.
            unsafe { ffi::PyList_SET_ITEM(list.as_ptr(), index as isize, py.None().into_ptr()) };
        }
        Ok(Self {
            list,
            reserved: length,
            used: 0,
        })
    }

    /// Install an owned result or append if callbacks expanded the input.
    /// # Errors
    /// Preserves growth allocation errors without exposing a partial result.
    #[inline(always)]
    fn push(&mut self, value: Bound<'py, PyAny>) -> PyResult<()> {
        if self.used < self.list.len() {
            // SAFETY: Every slot was initialized before any callback. The GIL
            // and freshly checked live size protect GET/SET with no intervening
            // callback. Install the new owned reference before decref can run a
            // destructor; no access to old follows that decref.
            unsafe {
                let old = ffi::PyList_GET_ITEM(self.list.as_ptr(), self.used as isize);
                ffi::PyList_SET_ITEM(self.list.as_ptr(), self.used as isize, value.into_ptr());
                ffi::Py_DECREF(old);
            }
        } else {
            // SAFETY: This owned exact CPython list is accessed with the GIL.
            // Its live size/capacity are read after callbacks. An allocated
            // slot beyond size has no owned reference. Store the owned result
            // before publishing size; neither action invokes Python, so GC can
            // only observe the fully initialized prefix. Public append handles
            // growth and allocation errors when no spare capacity remains.
            unsafe {
                let list = self.list.as_ptr().cast::<ffi::PyListObject>();
                let length = (*list).ob_base.ob_size;
                if (*list).allocated > length {
                    (*list).ob_item.add(length as usize).write(value.into_ptr());
                    (*list).ob_base.ob_size = length + 1;
                } else {
                    self.list.append(value)?;
                }
            }
        }
        self.used += 1;
        Ok(())
    }

    /// Remove unused initialized reservations after a shortened input.
    /// # Errors
    /// Propagates truncation allocation errors.
    fn finish(self) -> PyResult<Bound<'py, PyList>> {
        if self.used < self.reserved {
            self.list.del_slice(self.used, self.reserved)?;
        }
        Ok(self.list)
    }
}
