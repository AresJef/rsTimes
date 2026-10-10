//! Direct arithmetic methods must differ from CPython's shared numeric slots.
//! Checked CPython callbacks share the existing Rust methods and preserve the
//! direct-method contract, including reflected Delta rejection. Allocation of
//! Python subclasses remains with PyO3; exact Delta uses PyO3's safe allocator.
use crate::delta::Delta;
use pyo3::exceptions::PyRuntimeError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyTuple};
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::ptr;
use std::sync::OnceLock;

static ORIGINAL_NEW: OnceLock<ffi::newfunc> = OnceLock::new();

// CPython validates subtype before dispatching tp_new. Exact Delta uses PyO3's
// safe allocator (which calls tp_alloc, not tp_new); subclasses retain PyO3's
// original allocator and its Python subclass dictionary/weakref handling.
unsafe extern "C" fn allocate(
    class: *mut ffi::PyTypeObject,
    args: *mut ffi::PyObject,
    kwargs: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    if class.cast::<ffi::PyObject>() != py.get_type::<Delta>().as_ptr() {
        return match ORIGINAL_NEW.get() {
            Some(original) => unsafe { original(class, args, kwargs) },
            None => {
                PyRuntimeError::new_err("Delta allocator is missing").restore(py);
                ptr::null_mut()
            }
        };
    }
    let result = catch_unwind(AssertUnwindSafe(|| {
        Bound::new(py, Delta::raw()).map(Bound::into_ptr)
    }));
    match result {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while allocating Delta").restore(py);
            ptr::null_mut()
        }
    }
}

// CPython invokes this type's rich-comparison slot with a live Delta receiver
// (possibly a subclass). Direct-method descriptors retain their receiver checks.
unsafe extern "C" fn compare(
    receiver: *mut ffi::PyObject,
    other: *mut ffi::PyObject,
    operation: std::ffi::c_int,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let result = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let other = unsafe { Borrowed::from_ptr(py, other) };
        let value = receiver.get();
        if matches!(operation, ffi::Py_EQ | ffi::Py_NE) {
            // Both pointers are live. Matching their actual CPython types means
            // the other operand is the same Delta subtype as this slot receiver.
            if unsafe { ffi::Py_TYPE(receiver.as_ptr()) == ffi::Py_TYPE(other.as_ptr()) } {
                let right = unsafe { other.cast_unchecked::<Delta>() };
                let equal = value.native_eq(right.get());
                return Ok(PyBool::new(
                    py,
                    if operation == ffi::Py_EQ {
                        equal
                    } else {
                        !equal
                    },
                )
                .to_owned()
                .into_ptr());
            }
            if let Ok(right) = other.cast::<Delta>() {
                let equal = value.native_eq(right.get());
                return Ok(PyBool::new(
                    py,
                    if operation == ffi::Py_EQ {
                        equal
                    } else {
                        !equal
                    },
                )
                .to_owned()
                .into_ptr());
            }
        }
        match operation {
            ffi::Py_EQ => value.__eq__(&other),
            ffi::Py_NE => value.__ne__(&other),
            _ => Ok(py.NotImplemented().into_bound(py)),
        }
        .map(Bound::into_ptr)
    }));
    match result {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while comparing Delta").restore(py);
            ptr::null_mut()
        }
    }
}

unsafe fn direct(
    receiver: *mut ffi::PyObject,
    other: *mut ffi::PyObject,
    operation: usize,
) -> *mut ffi::PyObject {
    // CPython calls METH_O with non-null live objects and an attached thread.
    // Borrowed references stay within the complete callback. CPython keeps
    // both objects alive; receiver is checked before any Rust payload access.
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver) };
        let other = unsafe { Borrowed::from_ptr(py, other) };
        let checked = receiver.cast::<Delta>()?;
        let value = checked.get();
        match operation {
            0 => value.__add__(&other),
            1 => value.__radd__(&other),
            2 => value.__sub__(&other),
            _ => value.__rsub__(&other),
        }
        .map(Bound::into_ptr)
    }));
    let result = match outcome {
        Ok(result) => result,
        Err(_) => Err(PyRuntimeError::new_err(
            "Rust panic while calling Delta arithmetic",
        )),
    };
    match result {
        Ok(value) => value,
        Err(error) => {
            error.restore(py);
            ptr::null_mut()
        }
    }
}

macro_rules! callback {
    ($name:ident, $operation:expr) => {
        unsafe extern "C" fn $name(
            receiver: *mut ffi::PyObject,
            other: *mut ffi::PyObject,
        ) -> *mut ffi::PyObject {
            unsafe { direct(receiver, other, $operation) }
        }
    };
}
callback!(add, 0);
callback!(radd, 1);
callback!(sub, 2);
callback!(rsub, 3);

struct Definitions([ffi::PyMethodDef; 4]);
// These definitions only contain static C strings and function pointers.
// CPython retains their addresses, but never writes them; no mutable access
// exists in Rust. They therefore remain valid across all descriptor lifetimes.
unsafe impl Sync for Definitions {}
const fn definition(name: &'static std::ffi::CStr, function: ffi::PyCFunction) -> ffi::PyMethodDef {
    ffi::PyMethodDef {
        ml_name: name.as_ptr(),
        ml_meth: ffi::PyMethodDefPointer {
            PyCFunction: function,
        },
        ml_flags: ffi::METH_O,
        ml_doc: ptr::null(),
    }
}
static METHODS: Definitions = Definitions([
    definition(c"__add__", add),
    definition(c"__radd__", radd),
    definition(c"__sub__", sub),
    definition(c"__rsub__", rsub),
]);

// Only CPython's checked getset descriptor calls this callback. Receiver
// ownership and its actual Delta subtype have already been checked by CPython.
unsafe extern "C" fn getter(
    receiver: *mut ffi::PyObject,
    closure: *mut std::ffi::c_void,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let result = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let index = closure as usize;
        if index >= 15 {
            return Err(PyRuntimeError::new_err("Invalid Delta property index"));
        }
        // Borrow is confined to this callback; the descriptor keeps receiver
        // alive. No Rust reference escapes, and no mutable borrow is held.
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let value = receiver.get().relative(index);
        if index >= 7 && value == -1 {
            return Ok(py.None().into_ptr());
        }
        Ok(unsafe { ffi::PyLong_FromLongLong(value) })
    }));
    match result {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while reading Delta property").restore(py);
            ptr::null_mut()
        }
    }
}
// CPython truth testing supplies a live receiver whose numeric slot belongs
// to Delta. The borrow and Python token do not leave this C callback.
unsafe extern "C" fn truth(receiver: *mut ffi::PyObject) -> std::ffi::c_int {
    let py = unsafe { Python::assume_attached() };
    let result = catch_unwind(AssertUnwindSafe(|| {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        i32::from(receiver.get().__bool__())
    }));
    match result {
        Ok(value) => value,
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while checking Delta truth").restore(py);
            -1
        }
    }
}

// CPython hash dispatch guarantees a live Delta receiver. The raw hash value
// is returned only after the existing Rust hash/cache implementation succeeds.
unsafe extern "C" fn hash(receiver: *mut ffi::PyObject) -> ffi::Py_hash_t {
    let py = unsafe { Python::assume_attached() };
    let result = catch_unwind(AssertUnwindSafe(|| {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        receiver.get().__hash__(py)
    }));
    match result {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            -1
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while hashing Delta").restore(py);
            -1
        }
    }
}

// Numeric slots can receive Delta on either side. Check actual Python types
// before reading either Rust payload; a forged __class__ is never sufficient.
unsafe fn binary(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
    subtract: bool,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let left = unsafe { Borrowed::from_ptr(py, left) };
        let right = unsafe { Borrowed::from_ptr(py, right) };
        // Fetch the interpreter-aware Delta type once for both operands.
        // CPython's actual type check admits subclasses without consulting a
        // spoofable __class__; only then may either Rust payload be accessed.
        let class = py.get_type::<Delta>().as_type_ptr();
        let result = if unsafe { ffi::PyObject_TypeCheck(left.as_ptr(), class) } != 0 {
            let value = unsafe { left.cast_unchecked::<Delta>() };
            if subtract {
                value.get().__sub__(&right)
            } else {
                value.get().__add__(&right)
            }
        } else if unsafe { ffi::PyObject_TypeCheck(right.as_ptr(), class) } != 0 {
            let value = unsafe { right.cast_unchecked::<Delta>() };
            if subtract {
                value.get().__rsub__(&left)
            } else {
                value.get().__radd__(&left)
            }
        } else {
            Ok(py.NotImplemented().into_bound(py))
        }?;
        Ok(result.into_ptr())
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while applying Delta").restore(py);
            ptr::null_mut()
        }
    }
}
unsafe extern "C" fn number_add(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    unsafe { binary(left, right, false) }
}
unsafe extern "C" fn number_sub(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    unsafe { binary(left, right, true) }
}

// type_call invokes tp_init with an instance of this type, a live argument
// tuple, and either a live dictionary or NULL. No borrowed value escapes.
unsafe extern "C" fn initialize(
    receiver: *mut ffi::PyObject,
    args: *mut ffi::PyObject,
    kwargs: *mut ffi::PyObject,
) -> std::ffi::c_int {
    let py = unsafe { Python::assume_attached() };
    let result = catch_unwind(AssertUnwindSafe(|| -> PyResult<()> {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let args = unsafe { Borrowed::from_ptr(py, args).cast_unchecked::<PyTuple>() };
        let kwargs = if kwargs.is_null() {
            None
        } else {
            Some(unsafe { Borrowed::from_ptr(py, kwargs).cast_unchecked::<PyDict>() })
        };
        receiver.get().__init__(&args, kwargs.as_deref())
    }));
    match result {
        Ok(Ok(())) => 0,
        Ok(Err(error)) => {
            error.restore(py);
            -1
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while initializing Delta").restore(py);
            -1
        }
    }
}

struct Getters([ffi::PyGetSetDef; 15]);
// Static readonly C strings/callback pointers; closure encodes an index and is
// never dereferenced as a memory address. CPython does not mutate this table.
unsafe impl Sync for Getters {}
const fn property(name: &'static std::ffi::CStr, index: usize) -> ffi::PyGetSetDef {
    ffi::PyGetSetDef {
        name: name.as_ptr(),
        get: Some(getter),
        set: None,
        doc: ptr::null(),
        closure: index as *mut std::ffi::c_void,
    }
}
static GETTERS: Getters = Getters([
    property(c"years", 0),
    property(c"months", 1),
    property(c"days", 2),
    property(c"hours", 3),
    property(c"minutes", 4),
    property(c"seconds", 5),
    property(c"microseconds", 6),
    property(c"year", 7),
    property(c"month", 8),
    property(c"day", 9),
    property(c"weekday", 10),
    property(c"hour", 11),
    property(c"minute", 12),
    property(c"second", 13),
    property(c"microsecond", 14),
]);

pub fn install(py: Python<'_>) -> PyResult<()> {
    let class = py.get_type::<Delta>();
    let class_ptr = class.as_ptr().cast::<ffi::PyTypeObject>();
    let original = unsafe { (*class_ptr).tp_new }
        .ok_or_else(|| PyRuntimeError::new_err("Delta allocator is missing"))?;
    let _ = ORIGINAL_NEW.set(original);
    // Full CPython ABI: class is a live, ready PyTypeObject owned by `class`.
    // Its tp_dict remains owned by that type. Descriptors and selected slots
    // stay attached to our own type; PyType_Modified invalidates caches.
    let dictionary = unsafe { Bound::from_borrowed_ptr(py, (*class_ptr).tp_dict) };
    let dictionary = dictionary.cast::<PyDict>()?;
    for (index, name) in ["__add__", "__radd__", "__sub__", "__rsub__"]
        .into_iter()
        .enumerate()
    {
        let method = ptr::addr_of!(METHODS.0[index]).cast_mut();
        let descriptor =
            unsafe { Bound::from_owned_ptr_or_err(py, ffi::PyDescr_NewMethod(class_ptr, method)) }?;
        dictionary.set_item(name, descriptor)?;
    }
    for (index, name) in [
        "years",
        "months",
        "days",
        "hours",
        "minutes",
        "seconds",
        "microseconds",
        "year",
        "month",
        "day",
        "weekday",
        "hour",
        "minute",
        "second",
        "microsecond",
    ]
    .into_iter()
    .enumerate()
    {
        let definition = ptr::addr_of!(GETTERS.0[index]).cast_mut();
        let descriptor = unsafe {
            Bound::from_owned_ptr_or_err(py, ffi::PyDescr_NewGetSet(class_ptr, definition))
        }?;
        dictionary.set_item(name, descriptor)?;
    }
    // This ready heap type owns a non-null numeric-method table because the
    // class already defines numeric methods. The callbacks share Rust logic.
    let numbers = unsafe { (*class_ptr).tp_as_number };
    if numbers.is_null() {
        return Err(PyRuntimeError::new_err("Delta numeric slots are missing"));
    }
    unsafe {
        (*numbers).nb_bool = Some(truth);
        (*numbers).nb_add = Some(number_add);
        (*numbers).nb_subtract = Some(number_sub);
        (*class_ptr).tp_hash = Some(hash);
        (*class_ptr).tp_init = Some(initialize);
        (*class_ptr).tp_new = Some(allocate);
        (*class_ptr).tp_richcompare = Some(compare)
    };
    unsafe { ffi::PyType_Modified(class_ptr) };
    Ok(())
}
