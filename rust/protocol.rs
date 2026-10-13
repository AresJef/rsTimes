//! Install checked CPython descriptors and numeric slots for Delta.
//!
//! Direct arithmetic methods retain their own operand contract even when CPython
//! numeric slots perform reflected dispatch. PyO3 owns allocation and payloads;
//! static descriptor tables retain names, documentation and callbacks for their
//! full lifetime. Every unsafe callback states its CPython preconditions.

use crate::delta::Delta;
use pyo3::exceptions::PyRuntimeError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBool, PyCapsule, PyDate, PyDateTime, PyDelta, PyDict, PyTuple, PyType};
use std::cell::UnsafeCell;
use std::ffi::c_void;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::ptr;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicPtr, Ordering};

static ORIGINAL_NEW: OnceLock<ffi::newfunc> = OnceLock::new();
static ORIGINAL_ALLOC: OnceLock<ffi::allocfunc> = OnceLock::new();
static EXACT_ALLOC_TYPE: AtomicPtr<ffi::PyTypeObject> = AtomicPtr::new(ptr::null_mut());

/// Own dead, fixed-size storage under the ordinary CPython GIL.
struct AllocationCache {
    blocks: Vec<ptr::NonNull<c_void>>,
    limit: usize,
}

struct AttachedCache(UnsafeCell<AllocationCache>);
// SAFETY: Installation requires an enabled GIL. Allocation, tp_free and capsule
// destruction all hold it. No borrow of the cache crosses any CPython call,
// so callbacks cannot reenter while a mutable cache borrow is alive.
unsafe impl Sync for AttachedCache {}
static ALLOCATION_CACHE: AttachedCache = AttachedCache(UnsafeCell::new(AllocationCache {
    blocks: Vec::new(),
    limit: 0,
}));

/// Disable reuse and return every cached block when its module owner disappears.
struct CacheGuard {
    _ownership: u8,
}
impl Drop for CacheGuard {
    /// Release the disabled module's dead storage while its capsule holds the GIL.
    fn drop(&mut self) {
        EXACT_ALLOC_TYPE.store(ptr::null_mut(), Ordering::Relaxed);
        // SAFETY: This guard is created under the GIL and exclusively owned by
        // a Python capsule. Disabling first makes all later callbacks fall back.
        let blocks = unsafe { std::mem::take(&mut (*ALLOCATION_CACHE.0.get()).blocks) };
        for block in blocks {
            unsafe { ffi::PyObject_Free(block.as_ptr()) };
        }
    }
}

/// Retain fully destroyed exact-base storage within a fixed byte budget.
///
/// # Safety
/// PyO3 calls tp_free after dropping the complete Rust contents. The type still
/// has its instance reference until this callback returns. Subclasses and a
/// disabled cache use the public allocator's corresponding release function.
unsafe extern "C" fn free_exact(memory: *mut c_void) {
    let Some(block) = ptr::NonNull::new(memory) else {
        return;
    };
    let class = unsafe { ffi::Py_TYPE(memory.cast()) };
    if class == EXACT_ALLOC_TYPE.load(Ordering::Relaxed) {
        // SAFETY: The ordinary GIL excludes all cache mutations. Capacity was
        // reserved before installation, so this push cannot allocate or panic.
        let cache = unsafe { &mut *ALLOCATION_CACHE.0.get() };
        if cache.blocks.len() < cache.limit {
            cache.blocks.push(block);
            return;
        }
    }
    if unsafe { ffi::PyType_IS_GC(class) } != 0 {
        unsafe { ffi::PyObject_GC_Del(memory) };
    } else {
        unsafe { ffi::PyObject_Free(memory) };
    }
}

/// Allocate the checked fixed-size base using public CPython object APIs.
///
/// # Safety
/// CPython supplies a live ready type under the GIL. Only the registered exact
/// non-GC, no-dict/weakref, fixed-size Delta uses this path; all other requests
/// delegate to the original allocator. The whole allocation remains zeroed,
/// and PyO3 initializes its full contents before the object is exposed.
unsafe extern "C" fn allocate_exact(
    class: *mut ffi::PyTypeObject,
    count: ffi::Py_ssize_t,
) -> *mut ffi::PyObject {
    if count != 0 || class != EXACT_ALLOC_TYPE.load(Ordering::Relaxed) {
        return match ORIGINAL_ALLOC.get() {
            Some(original) => unsafe { original(class, count) },
            None => unsafe { ffi::PyType_GenericAlloc(class, count) },
        };
    }
    // SAFETY: install validated a positive fixed tp_basicsize and matching
    // Object_Free ownership. Calloc preserves all initial zero storage seen by
    // ref tracers; Init owns the heap type and creates the standard header.
    let reused = unsafe { (*ALLOCATION_CACHE.0.get()).blocks.pop() };
    let size = unsafe { (*class).tp_basicsize as usize };
    let memory = match reused {
        Some(block) => {
            // The prior object has been destroyed. Clear its entire storage,
            // then create a fresh header, type reference and SDK-owned payload.
            unsafe { ptr::write_bytes(block.as_ptr().cast::<u8>(), 0, size) };
            block.as_ptr()
        }
        None => unsafe { ffi::PyObject_Calloc(1, size) },
    };
    if memory.is_null() {
        unsafe { ffi::PyErr_NoMemory() };
        return ptr::null_mut();
    }
    unsafe { ffi::PyObject_Init(memory.cast(), class) }
}
static ORIGINAL_FACTORY: OnceLock<ffi::PyCFunctionFastWithKeywords> = OnceLock::new();
static FACTORY_OWNER: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static FACTORY_METHOD: OnceLock<FactoryMethod> = OnceLock::new();

/// Recognize the original Delta allocation slot without invoking Python hooks.
/// Pickle can use NEWOBJ only when that slot accepts complete native payloads.
pub(crate) fn uses_native_new(class: &Bound<'_, PyType>) -> bool {
    // SAFETY: The owned ready type is read while attached. A Python __new__
    // override replaces this slot and therefore selects explicit reconstruction.
    unsafe {
        (*class.as_type_ptr())
            .tp_new
            .is_some_and(|slot| slot as *const () == allocate as *const ())
    }
}

/// Retain the original immutable method metadata with one checked callback substitution.
struct FactoryMethod(ffi::PyMethodDef);
// SAFETY: Names/docs remain alive through FACTORY_OWNER. The static method is
// initialized once, then only read by attached CPython descriptor calls.
unsafe impl Send for FactoryMethod {}
unsafe impl Sync for FactoryMethod {}

/// Avoid generic argument extraction for the normal one-positional-argument factory.
///
/// # Safety
/// The class-method descriptor provides a live subtype receiver and a live
/// FASTCALL argument array. Nonstandard shapes delegate to the original callback
/// unchanged; the common path borrows exactly its one live argument.
unsafe extern "C" fn from_relative(
    receiver: *mut ffi::PyObject,
    args: *const *mut ffi::PyObject,
    count: ffi::Py_ssize_t,
    keywords: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    if count != 1 || !keywords.is_null() {
        return match ORIGINAL_FACTORY.get() {
            Some(original) => unsafe { original(receiver, args, count, keywords) },
            None => {
                let py = unsafe { Python::assume_attached() };
                PyRuntimeError::new_err("Delta factory callback is missing").restore(py);
                ptr::null_mut()
            }
        };
    }
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        // SAFETY: CPython's class descriptor validated receiver as a subtype.
        // count==1 establishes args[0]; all borrows end before returning.
        let class = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<PyType>() };
        let value = unsafe { Borrowed::from_ptr(py, *args) };
        Bound::new(py, Delta::from_relativedelta(&class, &value)?).map(Bound::into_ptr)
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while converting relativedelta").restore(py);
            ptr::null_mut()
        }
    }
}

/// Preserve factory descriptor flags, docs/signature and unusual-call error handling.
///
/// # Errors
/// Propagates descriptor allocation or dictionary insertion errors. An unrecognized
/// CPython descriptor shape is left unchanged rather than read through a cast.
fn install_factory(
    py: Python<'_>,
    class: &Bound<'_, PyType>,
    dictionary: &Bound<'_, PyDict>,
) -> PyResult<()> {
    if py.version_info().minor != 13 {
        return Ok(());
    }
    let owner = FACTORY_OWNER.get_or_try_init(py, || -> PyResult<_> {
        Ok(dictionary
            .get_item("from_relativedelta")?
            .ok_or_else(|| PyRuntimeError::new_err("Delta factory is missing"))?
            .unbind())
    })?;
    // SAFETY: Verify the actual CPython descriptor type before accessing its
    // full-ABI PyMethodDescrObject layout; spoofed __class__ cannot qualify.
    if unsafe { ffi::Py_TYPE(owner.bind(py).as_ptr()) }
        != ptr::addr_of_mut!(ffi::PyClassMethodDescr_Type)
    {
        return Ok(());
    }
    let definition =
        unsafe { (*owner.bind(py).as_ptr().cast::<ffi::PyMethodDescrObject>()).d_method };
    if definition.is_null() {
        return Ok(());
    }
    let original = unsafe { *definition };
    if original.ml_name.is_null()
        || original.ml_flags != (ffi::METH_FASTCALL | ffi::METH_KEYWORDS | ffi::METH_CLASS)
    {
        return Ok(());
    }
    let _ = ORIGINAL_FACTORY.set(unsafe { original.ml_meth.PyCFunctionFastWithKeywords });
    let method = FACTORY_METHOD.get_or_init(|| {
        FactoryMethod(ffi::PyMethodDef {
            ml_meth: ffi::PyMethodDefPointer {
                PyCFunctionFastWithKeywords: from_relative,
            },
            ..original
        })
    });
    let descriptor = unsafe {
        Bound::from_owned_ptr_or_err(
            py,
            ffi::PyDescr_NewClassMethod(class.as_type_ptr(), ptr::addr_of!(method.0).cast_mut()),
        )
    }?;
    dictionary.set_item("from_relativedelta", descriptor)
}

// CPython validates subtype before dispatching tp_new. Exact Delta uses PyO3's
// safe allocator (which calls tp_alloc, not tp_new); subclasses retain PyO3's
// original allocator and its Python subclass dictionary/weakref handling.
/// Allocate exact Delta through PyO3, preserving the original subtype allocator.
///
/// # Safety
/// CPython supplies a live ready subtype, live argument tuple and optional keyword
/// dictionary while attached to Python. Returned owned references follow tp_new
/// ownership rules; panics are translated to RuntimeError.
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
        let args = unsafe { Borrowed::from_ptr(py, args).cast_unchecked::<PyTuple>() };
        let kwargs = if kwargs.is_null() {
            None
        } else {
            Some(unsafe { Borrowed::from_ptr(py, kwargs).cast_unchecked::<PyDict>() })
        };
        Bound::new(py, Delta::construct(&args, kwargs.as_deref())?).map(Bound::into_ptr)
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
/// Implement equality slots while retaining direct-method operand validation.
///
/// # Safety
/// CPython supplies live operands and a Delta receiver for this comparison slot.
/// Borrowed Rust payload references stay inside the attached callback. Returns
/// an owned Python result or null with an active exception.
unsafe extern "C" fn compare(
    receiver: *mut ffi::PyObject,
    other: *mut ffi::PyObject,
    operation: std::ffi::c_int,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    if matches!(operation, ffi::Py_EQ | ffi::Py_NE)
        && unsafe { ffi::Py_TYPE(receiver) == ffi::Py_TYPE(other) }
    {
        // SAFETY: This native slot guarantees the receiver's Delta layout;
        // identical actual types guarantee the other layout. Immutable field
        // equality and immortal bool access cannot panic or invoke Python.
        let left = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let right = unsafe { Borrowed::from_ptr(py, other).cast_unchecked::<Delta>() };
        let equal = left.get().native_eq(right.get());
        // SAFETY: CPython owns these builtin singleton values. The slot returns
        // a new reference; no Python callback or fallible conversion is needed.
        return unsafe {
            ffi::Py_NewRef(if equal == (operation == ffi::Py_EQ) {
                ffi::Py_True()
            } else {
                ffi::Py_False()
            })
        };
    }
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

/// Call one checked direct arithmetic method using its fixed operation index.
///
/// # Safety
/// METH_O supplies live receiver/operand pointers while attached to Python.
/// CPython's method descriptor has checked the actual Delta receiver type;
/// 0..=3 select add, reflected add, subtract and reflected subtract.
unsafe fn direct(
    receiver: *mut ffi::PyObject,
    other: *mut ffi::PyObject,
    operation: usize,
) -> *mut ffi::PyObject {
    // CPython calls METH_O with non-null live objects and an attached thread.
    // Borrowed references stay within the complete callback. CPython keeps
    // both objects alive. PyDescr_NewMethod checks its d_type receiver before
    // invoking METH_O, including an explicit Delta.__add__(receiver, operand).
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver) };
        let other = unsafe { Borrowed::from_ptr(py, other) };
        // SAFETY: this callback is installed only in Delta's METH_O descriptors;
        // their actual-subtype check precedes entry and rejects forged receivers.
        let checked = unsafe { receiver.cast_unchecked::<Delta>() };
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
// Names and docstrings are static C strings as well. CPython retains their
// addresses but never writes them; no mutable access
// exists in Rust. They therefore remain valid across all descriptor lifetimes.
unsafe impl Sync for Definitions {}
/// Build a readonly method descriptor with process-lifetime name and doc text.
const fn definition(
    name: &'static std::ffi::CStr,
    function: ffi::PyCFunction,
    doc: &'static std::ffi::CStr,
) -> ffi::PyMethodDef {
    ffi::PyMethodDef {
        ml_name: name.as_ptr(),
        ml_meth: ffi::PyMethodDefPointer {
            PyCFunction: function,
        },
        ml_flags: ffi::METH_O,
        ml_doc: doc.as_ptr(),
    }
}
static METHODS: Definitions = Definitions([
    definition(c"__add__", add, c"Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.\n\nParameters\n----------\nother : object\n    Increment or date operand; NumPy arrays are unsupported.\n\nReturns\n-------\nDelta | date | datetime | NotImplemented\n    A base Delta for increment operands,\n        the input date subtype for Python dates, or a naive builtin datetime for\n        NumPy datetime64. Unsupported operands return NotImplemented.\n\nRaises\n------\nOverflowError\n    Numeric conversion or calendar arithmetic overflows.\nValueError\n    Invalid dates or a failing custom date constructor.\nException\n    Third-party conversion and other Python callback errors propagate.\n\nNotes\n-----\nDate operations apply absolute fields, relative increments, then weekday;\ndatetime timezone and fold are preserved. Arrays are not supported."),
    definition(c"__radd__", radd, c"Apply reflected addition using the same date and duration rules as __add__.\n\nParameters\n----------\nother : object\n    Left-hand date, duration or relativedelta operand.\n\nA direct reflected call with another Delta returns NotImplemented. Conversion,\ncalendar and custom-constructor errors follow __add__."),
    definition(c"__sub__", sub, c"Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.\n\nParameters\n----------\nother : object\n    Increment to subtract; dates are unsupported here.\n\nReturns\n-------\nDelta | NotImplemented\n    A base Delta or NotImplemented for unsupported types,\n        including dates and NumPy datetime64 in this direction.\n\nRaises\n------\nOverflowError\n    Numeric conversion, subtraction or normalization overflows.\nException\n    Third-party conversion and Python callback errors propagate."),
    definition(c"__rsub__", rsub, c"Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.\n\nParameters\n----------\nother : object\n    Left-hand date, duration or relativedelta operand.\n\nrelativedelta is also supported; direct reflected Delta calls return\nNotImplemented. Return types and calendar errors follow reflected dispatch,\nwith OverflowError for unrepresentable negation or subtraction."),
]);

// Only CPython's checked getset descriptor calls this callback. Receiver
// ownership and its actual Delta subtype have already been checked by CPython.
/// Read the field selected by a checked CPython getset descriptor.
///
/// # Safety
/// The descriptor verifies a live Delta subtype receiver. closure encodes one of
/// our 15 field indices, not a dereferenceable address. No borrow escapes and the
/// result follows getset owned-reference conventions.
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
/// Read the derived truth flag through the native numeric slot.
///
/// # Safety
/// CPython supplies a live Delta receiver while attached. No Rust borrow escapes;
/// -1 reports an active Python error.
unsafe extern "C" fn truth(receiver: *mut ffi::PyObject) -> std::ffi::c_int {
    let py = unsafe { Python::assume_attached() };
    // SDK's frozen payload read and one bounded flag read cannot panic or call
    // Python. Keep the numeric leaf free of unrelated exception machinery.
    let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
    i32::from(receiver.get().__bool__())
}

// CPython hash dispatch guarantees a live Delta receiver. The raw hash value
// is returned only after the existing Rust hash/cache implementation succeeds.
/// Return the checked cached Python tuple hash through tp_hash.
///
/// # Safety
/// CPython supplies a live Delta receiver while attached. Errors set a Python
/// exception and return -1; normal hashes retain Python's sentinel convention.
unsafe extern "C" fn hash(receiver: *mut ffi::PyObject) -> ffi::Py_hash_t {
    let py = unsafe { Python::assume_attached() };
    let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
    // The immutable value's initialized atomic cache read cannot panic or call
    // Python. Keep tuple construction and exception handling on the cold path.
    let cached = receiver.get().cached_hash();
    if cached != -1 {
        return cached;
    }
    hash_uncached(py, &receiver)
}

/// Compute an uncached hash and keep exception handling outside the cached slot.
/// # Errors
/// Returns -1 after restoring a computation exception; no borrow escapes.
#[cold]
#[inline(never)]
fn hash_uncached(py: Python<'_>, receiver: &Bound<'_, Delta>) -> ffi::Py_hash_t {
    let result = catch_unwind(AssertUnwindSafe(|| receiver.get().__hash__(py)));
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
/// Dispatch a numeric add/subtract slot without changing reflected behavior.
///
/// # Safety
/// Both operands are live CPython objects while attached. Actual Python type
/// checks precede any Delta payload access. Returns an owned result or null with
/// an exception; unsupported combinations return owned NotImplemented.
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
        // Two exact native operands need no foreign/date dispatch. Actual type
        // equality establishes both payloads; subclass slots and direct reflected
        // methods retain the original checked dispatch below.
        if unsafe { ffi::Py_TYPE(left.as_ptr()) == class && ffi::Py_TYPE(right.as_ptr()) == class }
        {
            let left = unsafe { left.cast_unchecked::<Delta>() };
            let right = unsafe { right.cast_unchecked::<Delta>() };
            return Bound::new(py, left.get().combine(right.get(), subtract)?).map(Bound::into_ptr);
        }
        // Reuse PyO3's initialized public datetime C API. A null cache simply
        // takes the original path, which initializes it when needed. CPython
        // owns this process-global capsule and its static timedelta type.
        let datetime_api = unsafe { ffi::PyDateTimeAPI() };
        if !datetime_api.is_null() {
            // Exact builtin dates need no repeated membership tests. Left-hand
            // Delta subtraction still takes the original unsupported-date path.
            let left_type = unsafe { ffi::Py_TYPE(left.as_ptr()) };
            let right_type = unsafe { ffi::Py_TYPE(right.as_ptr()) };
            let date_class = unsafe { (*datetime_api).DateType };
            let datetime_class = unsafe { (*datetime_api).DateTimeType };
            let pair = if right_type == class {
                Some((&right, &left, left_type, if subtract { -1 } else { 1 }))
            } else if left_type == class && !subtract {
                Some((&left, &right, right_type, 1))
            } else {
                None
            };
            if let Some((delta, other, actual, sign)) = pair {
                let delta = unsafe { delta.cast_unchecked::<Delta>() };
                // Empty Delta returns a checked date subtype unchanged. This
                // includes Pydt, and avoids unrelated foreign-type dispatch.
                // Python's left-hand operation has already had its normal turn;
                // subclass constructors are not called by this identity result.
                if !delta.get().__bool__()
                    && (actual == datetime_class
                        || actual == date_class
                        || unsafe { ffi::PyObject_TypeCheck(other.as_ptr(), date_class) } != 0)
                {
                    // SAFETY: other is a live date/datetime subtype under the GIL;
                    // the numeric slot must return an owned reference.
                    return Ok(unsafe { ffi::Py_NewRef(other.as_ptr()) });
                }
                let result = if actual == datetime_class {
                    let datetime = unsafe { other.cast_unchecked::<PyDateTime>() };
                    crate::interop::apply_datetime(delta.get(), other, &datetime, sign)?
                } else if actual == date_class {
                    let date = unsafe { other.cast_unchecked::<PyDate>() };
                    crate::interop::apply_date_only(delta.get(), other, &date, sign)?
                } else {
                    None
                };
                if let Some(result) = result {
                    return Ok(result.into_ptr());
                }
            }
            let duration_class = unsafe { (*datetime_api).DeltaType };
            if unsafe {
                ffi::Py_TYPE(left.as_ptr()) == class
                    && ffi::Py_TYPE(right.as_ptr()) == duration_class
            } {
                // Both actual types match their ready native types. No forged
                // __class__ or subclass constructor can reach this payload cast.
                let delta = unsafe { left.cast_unchecked::<Delta>() };
                let duration = unsafe { right.cast_unchecked::<PyDelta>() };
                return Bound::new(py, delta.get().with_duration(&duration, subtract, false)?)
                    .map(Bound::into_ptr);
            }
            if unsafe {
                ffi::Py_TYPE(right.as_ptr()) == class
                    && ffi::Py_TYPE(left.as_ptr()) == duration_class
            } {
                let delta = unsafe { right.cast_unchecked::<Delta>() };
                let duration = unsafe { left.cast_unchecked::<PyDelta>() };
                return Bound::new(
                    py,
                    delta.get().with_duration(&duration, subtract, subtract)?,
                )
                .map(Bound::into_ptr);
            }
        }
        // Exact native Delta/relativedelta operands bypass the generic date and
        // duration tests. Non-exact objects retain both original instance checks.
        if unsafe { ffi::Py_TYPE(left.as_ptr()) } == class {
            if let Some(fields) = crate::interop::exact_relative_fields(&right)? {
                let delta = unsafe { left.cast_unchecked::<Delta>() };
                return Bound::new(
                    py,
                    delta.get().with_relative_fields(fields, subtract, false)?,
                )
                .map(Bound::into_ptr);
            }
        } else if unsafe { ffi::Py_TYPE(right.as_ptr()) } == class {
            if let Some(fields) = crate::interop::exact_relative_fields(&left)? {
                let delta = unsafe { right.cast_unchecked::<Delta>() };
                return Bound::new(
                    py,
                    delta.get().with_relative_fields(fields, subtract, true)?,
                )
                .map(Bound::into_ptr);
            }
        }
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
/// Delegate the numeric addition slot to the checked binary dispatcher.
///
/// # Safety
/// Inherits binary's live-operand and attached-thread requirements.
unsafe extern "C" fn number_add(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    unsafe { binary(left, right, false) }
}
/// Delegate the numeric subtraction slot to the checked binary dispatcher.
///
/// # Safety
/// Inherits binary's live-operand and attached-thread requirements.
unsafe extern "C" fn number_sub(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    unsafe { binary(left, right, true) }
}

/// Apply a native unary operation without repeating Python descriptor checks.
///
/// # Safety
/// CPython's inherited numeric slot supplies a live Delta or Delta subclass
/// under the GIL. The native value remains borrowed only during the callback;
/// the result is a new owned base Delta. Errors and panics never cross the ABI.
#[inline(always)]
unsafe fn unary(receiver: *mut ffi::PyObject, absolute: bool) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let value = if absolute {
            receiver.get().__abs__()?
        } else {
            receiver.get().__neg__()?
        };
        Bound::new(py, value).map(Bound::into_ptr)
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            PyRuntimeError::new_err("Rust panic while applying a unary Delta operation")
                .restore(py);
            ptr::null_mut()
        }
    }
}

/// Delegate the numeric negation slot to checked native negation.
///
/// # Safety
/// Inherits unary's live-Delta and attached-thread requirements.
unsafe extern "C" fn number_negative(receiver: *mut ffi::PyObject) -> *mut ffi::PyObject {
    unsafe { unary(receiver, false) }
}

/// Delegate the numeric absolute-value slot to checked grouped-sign behavior.
///
/// # Safety
/// Inherits unary's live-Delta and attached-thread requirements.
unsafe extern "C" fn number_absolute(receiver: *mut ffi::PyObject) -> *mut ffi::PyObject {
    unsafe { unary(receiver, true) }
}

// type_call invokes tp_init with an instance of this type, a live argument
// tuple, and either a live dictionary or NULL. No borrowed value escapes.
/// Preserve an already initialized immutable Delta in CPython's tp_init slot.
///
/// # Safety
/// receiver is a live instance of this type; args is a live tuple and kwargs is
/// null or a live dict. No borrowed reference escapes. Errors return -1 and
/// preserve the Python exception.
unsafe extern "C" fn initialize(
    _receiver: *mut ffi::PyObject,
    _args: *mut ffi::PyObject,
    _kwargs: *mut ffi::PyObject,
) -> std::ffi::c_int {
    // Construction has already validated all arguments and installed the value.
    // Inherited initialization and direct repeated calls cannot overwrite it.
    0
}

struct Getters([ffi::PyGetSetDef; 15]);
// Static readonly names/docstrings/callback pointers; closure encodes an index and is
// never dereferenced as a memory address. CPython does not mutate this table.
unsafe impl Sync for Getters {}
/// Build a readonly field descriptor with static name and documentation.
///
/// index identifies one of the 15 validated native fields; it is never read as a
/// memory address.
const fn property(
    name: &'static std::ffi::CStr,
    index: usize,
    doc: &'static std::ffi::CStr,
) -> ffi::PyGetSetDef {
    ffi::PyGetSetDef {
        name: name.as_ptr(),
        get: Some(getter),
        set: None,
        doc: doc.as_ptr(),
        closure: index as *mut std::ffi::c_void,
    }
}
static GETTERS: Getters = Getters([
    property(
        c"years",
        0,
        c"int: Normalized relative years; months are carried into this value.",
    ),
    property(
        c"months",
        1,
        c"int: Relative months after grouping years, in 0..11.",
    ),
    property(
        c"days",
        2,
        c"int: Relative days, including normalized weeks and clock carries.",
    ),
    property(c"hours", 3, c"int: Normalized relative hours, in 0..23."),
    property(
        c"minutes",
        4,
        c"int: Normalized relative minutes, in 0..59.",
    ),
    property(
        c"seconds",
        5,
        c"int: Normalized relative seconds, in 0..59.",
    ),
    property(
        c"microseconds",
        6,
        c"int: Normalized relative microseconds, in 0..999999.",
    ),
    property(
        c"year",
        7,
        c"int | None: Absolute year replacement, or None when unset.",
    ),
    property(
        c"month",
        8,
        c"int | None: Absolute month replacement (1..12), or None when unset.",
    ),
    property(
        c"day",
        9,
        c"int | None: Absolute day replacement (1..31), or None when unset.",
    ),
    property(
        c"weekday",
        10,
        c"int | None: Absolute weekday replacement (Monday=0 to Sunday=6), or None.",
    ),
    property(
        c"hour",
        11,
        c"int | None: Absolute hour replacement (0..23), or None when unset.",
    ),
    property(
        c"minute",
        12,
        c"int | None: Absolute minute replacement (0..59), or None when unset.",
    ),
    property(
        c"second",
        13,
        c"int | None: Absolute second replacement (0..59), or None when unset.",
    ),
    property(
        c"microsecond",
        14,
        c"int | None: Absolute microsecond replacement (0..999999), or None.",
    ),
]);

/// Attach checked methods, getters and selected slots to this extension's Delta.
///
/// # Errors
/// Propagates descriptor allocation/type-dictionary errors and raises RuntimeError
/// if the expected PyO3 allocation or numeric tables are unavailable.
///
/// # Lifetime contract
/// Descriptor names, docstrings and callback tables have static storage. Only
/// this ready heap type is modified, then PyType_Modified invalidates its caches.
pub fn install(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    let class = py.get_type::<Delta>();
    let class_ptr = class.as_ptr().cast::<ffi::PyTypeObject>();
    let version = py.version_info();
    // The public fixed-object shortcut is guarded by observed type features,
    // not reproduced Rust layout. Genuine subclasses keep the SDK allocator.
    let eligible = unsafe {
        version.major == 3
            && version.minor == 13
            && cfg!(target_pointer_width = "64")
            && (*class_ptr).tp_flags & ffi::Py_TPFLAGS_HAVE_GC == 0
            && (*class_ptr).tp_dictoffset == 0
            && (*class_ptr).tp_weaklistoffset == 0
            && (*class_ptr).tp_itemsize == 0
            && (*class_ptr).tp_basicsize > 0
            && (*class_ptr)
                .tp_free
                .is_some_and(|free| free as *const () == ffi::PyObject_Free as *const ())
    };
    if eligible
        && py
            .import("sys")?
            .getattr("_is_gil_enabled")?
            .call0()?
            .extract::<bool>()?
    {
        if let Some(original) = unsafe { (*class_ptr).tp_alloc } {
            // A byte budget bounds retained dead blocks and their pointer table;
            // it is independent of benchmark case sizes and user input lengths.
            let limit = (2 * 1024 * 1024)
                / (unsafe { (*class_ptr).tp_basicsize as usize }
                    + std::mem::size_of::<ptr::NonNull<c_void>>());
            let cache = unsafe { &mut *ALLOCATION_CACHE.0.get() };
            cache.blocks.try_reserve_exact(limit).map_err(|_| {
                pyo3::exceptions::PyMemoryError::new_err("cannot allocate Delta cache")
            })?;
            cache.limit = limit;
            module.add(
                "_allocation_cache",
                PyCapsule::new_with_value(
                    py,
                    CacheGuard { _ownership: 1 },
                    c"rstimes._native._allocation_cache",
                )?,
            )?;
            let _ = ORIGINAL_ALLOC.set(original);
            EXACT_ALLOC_TYPE.store(class_ptr, Ordering::Relaxed);
            unsafe {
                (*class_ptr).tp_alloc = Some(allocate_exact);
                (*class_ptr).tp_free = Some(free_exact);
            };
        }
    }
    let original = unsafe { (*class_ptr).tp_new }
        .ok_or_else(|| PyRuntimeError::new_err("Delta allocator is missing"))?;
    let _ = ORIGINAL_NEW.set(original);
    // Full CPython ABI: class is a live, ready PyTypeObject owned by `class`.
    // Its tp_dict remains owned by that type. Descriptors and selected slots
    // stay attached to our own type; PyType_Modified invalidates caches.
    let dictionary = unsafe { Bound::from_borrowed_ptr(py, (*class_ptr).tp_dict) };
    let dictionary = dictionary.cast::<PyDict>()?;
    install_factory(py, &class, dictionary)?;
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
        (*numbers).nb_negative = Some(number_negative);
        (*numbers).nb_absolute = Some(number_absolute);
        (*class_ptr).tp_hash = Some(hash);
        (*class_ptr).tp_init = Some(initialize);
        (*class_ptr).tp_new = Some(allocate);
        (*class_ptr).tp_richcompare = Some(compare)
    };
    unsafe { ffi::PyType_Modified(class_ptr) };
    Ok(())
}
