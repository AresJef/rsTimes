//! Ordered bulk addition with shared immutable Delta fields.
//!
//! Only exact builtin operands use the checked native kernels directly.
//! Subclasses and foreign objects retain Python's full reflected dispatch.
//! Owned item references survive user callbacks that mutate an input list.

use crate::delta::{Delta, PreparedAddition};

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
    fields: &'a crate::delta::value::DeltaValue,
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
        let pointer =
            unsafe { crate::protocol::new_delta(self.slf.py(), value, self.types.delta)? };
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
                return crate::interop::apply_builtin_datetime_fields(
                    self.fields,
                    self.empty,
                    value,
                    unsafe { value.cast_unchecked::<PyDateTime>() },
                    1,
                )?
                .ok_or_else(|| {
                    crate::error_context::runtime("Datetime kernel returned no result")
                });
            }
            if actual == self.types.date {
                return crate::interop::apply_date_only_fields(
                    self.fields,
                    self.empty,
                    value,
                    unsafe { value.cast_unchecked::<PyDate>() },
                    1,
                )?
                .ok_or_else(|| crate::error_context::runtime("Date kernel returned no result"));
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
                if let Some(source) = numpy.delta_scalar(value, true)? {
                    match source {
                        crate::numpy_scalar::DeltaScalar::Date { civil, coarse } => {
                            return crate::numpy_scalar::apply_delta_date(
                                self.slf.py(),
                                self.fields,
                                civil,
                                1,
                                coarse,
                            );
                        }
                        crate::numpy_scalar::DeltaScalar::Duration {
                            days,
                            clock_ns,
                            calendar_unit: false,
                        } => {
                            return self
                                .allocate_delta(self.addition.add_fixed_parts(days, clock_ns)?);
                        }
                        crate::numpy_scalar::DeltaScalar::Duration {
                            calendar_unit: true,
                            ..
                        } => {}
                    }
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
        crate::interop::reject_nat(value, "Delta.apply_many", "value")?;
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
        .map_err(crate::error_context::external)
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
    start: usize,
) -> PyResult<Bound<'py, PyList>> {
    let mut index = start;
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
            batch.add(&value)
        } else {
            batch.add_foreign(&value)
        }
        .map_err(|error| {
            // A foreign callback may have removed this borrowed slot. Its
            // item was owned during that callback and its error was fetched
            // before release; reporting the index needs no later item access.
            crate::error_context::item(
                values.py(),
                error,
                "Delta.apply_many",
                "values",
                index,
                None,
                false,
            )
        })?;
        output.push(result)?;
        index += 1;
    }
    output.finish()
}

/// Keep native arithmetic lists ahead of calendar and foreign preparation.
///
/// Each item is checked independently. A later foreign item still receives full
/// dispatch, and the live input length is reread after every possible callback.
/// Calendar preparation is deferred until the first mixed item; the remaining
/// suffix then uses the ordinary loop without assuming a homogeneous list.
///
/// # Errors
/// Preserves checked arithmetic, foreign callbacks and output allocation errors.
#[inline(never)]
fn fill_arithmetic_list<'py, const REPLACE: bool>(
    slf: &Bound<'py, Delta>,
    values: &Bound<'py, PyList>,
    addition: &PreparedAddition,
    arithmetic_types: (*mut ffi::PyTypeObject, *mut ffi::PyTypeObject),
    numpy: Option<crate::numpy_scalar::ExactTypes>,
    mut output: Output<'py>,
    first: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyList>> {
    let (delta_type, duration_type) = arithmetic_types;
    // The first item was already taken before preparation/output allocation.
    // Keep that object even if a collection callback changed the live list.
    let actual = unsafe { ffi::Py_TYPE(first.as_ptr()) };
    let first_result = (|| -> PyResult<Bound<'py, PyAny>> {
        Ok(if actual == delta_type || actual == duration_type {
            let result = if actual == delta_type {
                addition
                    .add_delta_prepared::<REPLACE>(unsafe { first.cast_unchecked::<Delta>() }.get())
            } else {
                addition.add_duration(unsafe { first.cast_unchecked::<PyDelta>() })
            }?;
            let pointer = unsafe { crate::protocol::new_delta(slf.py(), result, delta_type)? };
            unsafe { Bound::from_owned_ptr(slf.py(), pointer) }
        } else {
            first.add(slf).map_err(crate::error_context::external)?
        })
    })()
    .map_err(|error| {
        crate::error_context::argument(
            values.py(),
            error,
            "Delta.apply_many",
            "values[0]",
            values.as_any(),
        )
    })?;
    output.push(first_result)?;
    let mut index = 1;
    while index < values.len() {
        // SAFETY: The live input list owns this slot under the GIL. The exact
        // type check proves the Delta layout; its complete payload is read
        // before allocation. Other items enter the ordinary loop at this index,
        // retaining Batch::add's callback ownership.
        let value = unsafe {
            Borrowed::from_ptr(
                values.py(),
                ffi::PyList_GET_ITEM(values.as_ptr(), index as isize),
            )
        };
        let actual = unsafe { ffi::Py_TYPE(value.as_ptr()) };
        let result = if actual == delta_type {
            addition.add_delta_prepared::<REPLACE>(unsafe { value.cast_unchecked::<Delta>() }.get())
        } else if actual == duration_type {
            let duration = unsafe { value.cast_unchecked::<PyDelta>() };
            addition.add_duration(&duration)
        } else {
            break;
        }
        .map_err(|error| {
            // A foreign callback may have removed this borrowed slot. Its
            // item was owned during that callback and its error was fetched
            // before release; reporting the index needs no later item access.
            crate::error_context::item(
                values.py(),
                error,
                "Delta.apply_many",
                "values",
                index,
                None,
                false,
            )
        })?;
        // SAFETY: delta_type is the ready exact Delta type; all input reads
        // finished before the SDK allocator initializes the complete payload.
        let pointer = unsafe { crate::protocol::new_delta(slf.py(), result, delta_type)? };
        output.push(unsafe { Bound::from_owned_ptr(slf.py(), pointer) })?;
        index += 1;
    }
    if index >= values.len() {
        return output.finish();
    }
    // Build the complete context once at the first mixed item, then retain
    // ordinary native/foreign dispatch for the remaining live list.
    let fields = slf.get().native_value();
    let types = Types {
        delta: delta_type,
        datetime: slf.py().get_type::<PyDateTime>().as_type_ptr(),
        date: slf.py().get_type::<PyDate>().as_type_ptr(),
        duration: duration_type,
    };
    let batch = Batch {
        slf,
        fields: &fields,
        empty: !slf.get().__bool__(),
        native: true,
        types: &types,
        addition,
        numpy,
    };
    fill_list::<true>(&batch, values, output, index)
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
                    .ok_or_else(|| crate::error_context::runtime("Missing relative names"))?,
            )
        } else {
            let value = unsafe { Borrowed::from_ptr(py, item) };
            crate::interop::reject_nat(&value, "Delta.apply_many", "value").and_then(|()| {
                let result = unsafe { ffi::PyNumber_Add(item, slf.as_ptr()) };
                unsafe { Bound::from_owned_ptr_or_err(py, result) }
                    .map_err(crate::error_context::external)
            })
        };
        // Keep the current item alive while formatting failure context. Python
        // callbacks may already have removed this item from the input list.
        let result = result.map_err(|error| {
            let value = unsafe { Borrowed::from_ptr(py, item) };
            crate::error_context::item(
                py,
                error,
                "Delta.apply_many",
                "values",
                output.used,
                Some(&value),
                false,
            )
        });
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
    crate::interop::reject_nat(value, "Delta.apply_many", "value")?;
    let slf = batch.slf;
    // SAFETY: Caller owns both objects, has checked actual date inheritance and
    // exact Delta identity, and holds the GIL. The ready type owns its slots.
    let number = unsafe { (*ffi::Py_TYPE(value.as_ptr())).tp_as_number };
    if let Some(slot) = unsafe { number.as_ref() }.and_then(|number| number.nb_add) {
        let result = unsafe { slot(value.as_ptr(), slf.as_ptr()) };
        if result != unsafe { ffi::Py_NotImplemented() } {
            return unsafe { Bound::from_owned_ptr_or_err(slf.py(), result) }
                .map_err(crate::error_context::external);
        }
        unsafe { ffi::Py_DECREF(result) };
    }
    catch_unwind(AssertUnwindSafe(|| {
        if let Ok(dt) = value.cast::<PyDateTime>() {
            crate::interop::apply_datetime_fields_vector(batch.fields, batch.empty, value, dt, 1)?
                .ok_or_else(|| crate::error_context::runtime("Datetime kernel returned no result"))
        } else {
            slf.get().__radd__(value)
        }
    }))
    .unwrap_or_else(|_| {
        Err(crate::error_context::runtime(
            "Rust panic while applying Delta",
        ))
    })
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
    keys: &[Py<PyString>; 16],
) -> PyResult<Bound<'py, PyAny>> {
    // SAFETY: The GIL and the caller's strong references protect the current
    // type and its live slots. The unrelated exact Delta takes the second turn.
    let number = unsafe { (*ffi::Py_TYPE(value.as_ptr())).tp_as_number };
    if let Some(slot) = unsafe { number.as_ref() }.and_then(|number| number.nb_add) {
        let result = unsafe { slot(value.as_ptr(), batch.slf.as_ptr()) };
        if result != unsafe { ffi::Py_NotImplemented() } {
            return unsafe { Bound::from_owned_ptr_or_err(batch.slf.py(), result) }
                .map_err(crate::error_context::external);
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
    .unwrap_or_else(|_| {
        Err(crate::error_context::runtime(
            "Rust panic while applying Delta",
        ))
    })
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
    let py = slf.py();
    let initial_output =
        if values.is_exact_instance_of::<PyList>() && values.cast::<PyList>()?.is_empty() {
            let output = Output::new(py, 0)?;
            // Allocation may permit collection callbacks. Recheck the live input;
            // if it grew, reuse this output and retain ordinary dynamic traversal.
            if values.cast::<PyList>()?.is_empty() {
                return output.finish();
            }
            Some(output)
        } else {
            None
        };
    let list = values.cast_exact::<PyList>().ok();
    let first = list
        .filter(|list| !list.is_empty())
        .map(|list| list.get_item(0))
        .transpose()?;
    let addition = PreparedAddition::new(slf.get());
    // The installed exact-base cache already proves the receiver's live type;
    // other builds and subclasses retain the normal SDK identity lookup.
    let exact_delta = unsafe { crate::protocol::is_cached_exact_delta(slf.as_ptr()) }
        || slf.is_exact_instance_of::<Delta>();
    if exact_delta && values.is_exact_instance_of::<PyList>() {
        let values = values.cast::<PyList>()?;
        if !values.is_empty() {
            // SAFETY: exact_delta proves the registered base receiver. Reuse the
            // initialized public datetime capsule without repeated type preparation.
            let delta_type = unsafe { ffi::Py_TYPE(slf.as_ptr()) };
            let duration_type = match unsafe { ffi::PyDateTimeAPI().as_ref() } {
                Some(api) => api.DeltaType,
                None => py.get_type::<PyDelta>().as_type_ptr(),
            };
            // SAFETY: The nonempty exact list owns its first item under the GIL.
            // This selects a loop only; each later item is checked independently.
            let initial = first
                .as_ref()
                .ok_or_else(|| crate::error_context::runtime("missing initial list item"))?;
            let actual = unsafe { ffi::Py_TYPE(initial.as_ptr()) };
            if actual == delta_type || actual == duration_type {
                // Capture existing NumPy identities before any result allocation,
                // preserving the original first-item preparation across callbacks.
                // Exact arithmetic inputs reuse the proven native identities.
                let numpy = crate::numpy_scalar::ExactTypes::cached(py);
                let output = match initial_output {
                    Some(output) => output,
                    None => Output::new(py, values.len())?,
                };
                return if addition.has_absolute() {
                    fill_arithmetic_list::<true>(
                        slf,
                        values,
                        &addition,
                        (delta_type, duration_type),
                        numpy,
                        output,
                        initial,
                    )
                } else {
                    fill_arithmetic_list::<false>(
                        slf,
                        values,
                        &addition,
                        (delta_type, duration_type),
                        numpy,
                        output,
                        initial,
                    )
                };
            }
        }
    }
    let fields = slf.get().native_value();
    let empty = !slf.get().__bool__();
    let delta_type = if exact_delta {
        // SAFETY: The exact live receiver owns this ready base type.
        unsafe { ffi::Py_TYPE(slf.as_ptr()) }
    } else {
        py.get_type::<Delta>().as_type_ptr()
    };
    let types = match unsafe { ffi::PyDateTimeAPI().as_ref() } {
        Some(api) => Types {
            delta: delta_type,
            datetime: api.DateTimeType,
            date: api.DateType,
            duration: api.DeltaType,
        },
        None => Types {
            delta: delta_type,
            datetime: py.get_type::<PyDateTime>().as_type_ptr(),
            date: py.get_type::<PyDate>().as_type_ptr(),
            duration: py.get_type::<PyDelta>().as_type_ptr(),
        },
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
        let first = first
            .as_ref()
            .ok_or_else(|| crate::error_context::runtime("missing initial list item"))?;
        match crate::numpy_scalar::ExactTypes::cached(py) {
            Some(types) => Some(types),
            None => crate::numpy_scalar::ExactTypes::for_value(first)?,
        }
    } else {
        None
    };
    let native = if exact_delta && values.is_exact_instance_of::<PyList>() && capacity > 0 {
        let first = first
            .as_ref()
            .ok_or_else(|| crate::error_context::runtime("missing initial list item"))?;
        // SAFETY: The owned first object is live and its actual type is read only.
        let actual = unsafe { ffi::Py_TYPE(first.as_ptr()) };
        numpy.as_ref().is_some_and(|types| types.matches(first))
            || [types.delta, types.datetime, types.date, types.duration].contains(&actual)
    } else {
        exact_delta
    };
    // Callback-free native results benefit from one initialized allocation.
    // For subclasses/foreign operands, a growing list avoids initializing None
    // and makes cyclic GC scan only the completed prefix during callbacks.
    // An exact tuple has a stable length. Output still publishes only complete
    // objects, so callbacks may safely inspect or change its initialized prefix.
    let reserved = if exact_delta && values.is_exact_instance_of::<PyTuple>() {
        capacity
    } else if exact_delta && values.is_exact_instance_of::<PyList>() && capacity > 0 {
        let first = first
            .as_ref()
            .ok_or_else(|| crate::error_context::runtime("missing initial list item"))?;
        // SAFETY: The owned first item keeps its ready actual type alive.
        let actual = unsafe { ffi::Py_TYPE(first.as_ptr()) };
        if [types.delta, types.datetime, types.date, types.duration].contains(&actual)
            || numpy.as_ref().is_some_and(|types| types.matches(first))
        {
            capacity
        } else {
            0
        }
    } else {
        0
    };
    let mut output = match initial_output {
        Some(output) => output,
        None => Output::new(py, reserved)?,
    };
    let batch = Batch {
        slf,
        fields: &fields,
        empty,
        native,
        types: &types,
        addition: &addition,
        numpy,
    };
    if values.is_exact_instance_of::<PyList>() {
        let values = values.cast::<PyList>()?;
        if let Some(first) = &first {
            output.push(batch.add(first).map_err(|error| {
                crate::error_context::item(
                    py,
                    error,
                    "Delta.apply_many",
                    "values",
                    0,
                    Some(first),
                    false,
                )
            })?)?;
        }
        return if native {
            fill_list::<true>(&batch, values, output, usize::from(first.is_some()))
        } else {
            if exact_delta
                && first.as_ref().is_some_and(
                    |item| unsafe { ffi::PyObject_TypeCheck(item.as_ptr(), types.date) } != 0,
                )
            {
                fill_foreign_list::<true, false>(&batch, values, output)
            } else if exact_delta
                && first.as_ref().is_some_and(|item| {
                    crate::interop::exact_relative_type(py)
                        .is_some_and(|class| unsafe { ffi::Py_TYPE(item.as_ptr()) == class })
                })
            {
                fill_foreign_list::<false, true>(&batch, values, output)
            } else {
                fill_foreign_list::<false, false>(&batch, values, output)
            }
        };
    } else if values.is_exact_instance_of::<PyTuple>() {
        for (index, value) in values.cast::<PyTuple>()?.iter().enumerate() {
            output.push(batch.add(&value).map_err(|error| {
                crate::error_context::item(
                    py,
                    error,
                    "Delta.apply_many",
                    "values",
                    index,
                    Some(&value),
                    false,
                )
            })?)?;
        }
    } else {
        for (index, value) in values
            .try_iter()
            .map_err(crate::error_context::external)
            .map_err(|error| {
                crate::error_context::argument(py, error, "Delta.apply_many", "values", values)
            })?
            .enumerate()
        {
            let value = value
                .map_err(crate::error_context::external)
                .map_err(|error| {
                    crate::error_context::item(
                        py,
                        error,
                        "Delta.apply_many",
                        "values",
                        index,
                        None,
                        true,
                    )
                })?;
            output.push(batch.add(&value).map_err(|error| {
                crate::error_context::item(
                    py,
                    error,
                    "Delta.apply_many",
                    "values",
                    index,
                    Some(&value),
                    false,
                )
            })?)?;
        }
    }
    output.finish()
}

/// A result list publishing only initialized result slots.
///
/// Spare capacity stays outside the visible size. Checked replacement also
/// handles callbacks that discover and modify the published list through GC.
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
        // SAFETY: PyList_New allocated null slots, and no Python callback runs
        // before this full-ABI size update. No slot owns a reference yet. GC and
        // error cleanup must see size zero while allocated capacity is retained.
        unsafe {
            (*list.as_ptr().cast::<ffi::PyListObject>()).ob_base.ob_size = 0;
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
        // SAFETY: the exact list is live under the GIL. Read its current size
        // once before any callback; publication below still owns every slot.
        let list = self.list.as_ptr().cast::<ffi::PyListObject>();
        let length = unsafe { (*list).ob_base.ob_size };
        if self.used < length as usize {
            // SAFETY: Every visible slot is initialized before callbacks. The GIL
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

    /// Preserve final reservation-based trimming after a shortened input.
    /// # Errors
    /// Propagates truncation allocation errors.
    fn finish(self) -> PyResult<Bound<'py, PyList>> {
        if self.used < self.reserved {
            self.list.del_slice(self.used, self.reserved)?;
        }
        Ok(self.list)
    }
}
