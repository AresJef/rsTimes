//! Install checked CPython descriptors and numeric slots for Delta.
//!
//! Direct arithmetic methods retain their own operand contract even when CPython
//! numeric slots perform reflected dispatch. PyO3 owns allocation and payloads;
//! static descriptor tables retain names, documentation and callbacks for their
//! full lifetime. Every unsafe callback states its CPython preconditions.

use crate::delta::Delta;
use pyo3::PyTypeInfo;

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{
    PyBool, PyCapsule, PyDate, PyDateTime, PyDelta, PyDeltaAccess, PyDict, PyString, PyTuple,
    PyType,
};
use std::cell::UnsafeCell;
use std::ffi::c_void;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::ptr;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicPtr, Ordering};

static ORIGINAL_NEW: OnceLock<ffi::newfunc> = OnceLock::new();
static ORIGINAL_ALLOC: OnceLock<ffi::allocfunc> = OnceLock::new();
static EXACT_ALLOC_TYPE: AtomicPtr<ffi::PyTypeObject> = AtomicPtr::new(ptr::null_mut());

/// Check the live base type whose cache was installed on a conventional GIL build.
/// # Safety
/// receiver must be a live Python object on its attached interpreter thread.
#[inline(always)]
pub(crate) unsafe fn is_cached_exact_delta(receiver: *mut ffi::PyObject) -> bool {
    let class = EXACT_ALLOC_TYPE.load(Ordering::Relaxed);
    !class.is_null() && unsafe { ffi::Py_TYPE(receiver) } == class
}

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
/// delegate to the original allocator. Fresh storage is zeroed; reused storage
/// receives a new header and PyO3 replaces every SDK-owned field before exposure.
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
    // Object_Free ownership. Fresh storage uses Calloc; Init owns the heap type
    // and creates the standard header. The exact base has no GC/dict/weakref slots.
    let reused = unsafe { (*ALLOCATION_CACHE.0.get()).blocks.pop() };
    let size = unsafe { (*class).tp_basicsize as usize };
    let memory = match reused {
        // PyO3 0.29.3's own freelist likewise reinitializes only the header.
        // Its initializer then writes complete PyClassObjectContents, including
        // the new Delta value/hash and all borrow/thread/dict/weakref fields.
        // The old contents have already been dropped by tp_free's caller.
        Some(block) => block.as_ptr(),
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
static SPAN: SimpleMethod = SimpleMethod::new();
static MANY: SimpleMethod = SimpleMethod::new();

/// Retain one original method and the immutable metadata of its direct entry.
struct SimpleMethod {
    original: OnceLock<ffi::PyCFunctionFastWithKeywords>,
    owner: PyOnceLock<Py<PyAny>>,
    definition: OnceLock<FactoryMethod>,
}

impl SimpleMethod {
    const fn new() -> Self {
        Self {
            original: OnceLock::new(),
            owner: PyOnceLock::new(),
            definition: OnceLock::new(),
        }
    }
}

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
                crate::error_context::runtime("Delta factory callback is missing").restore(py);
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
            crate::error_context::runtime("Rust panic while converting relativedelta").restore(py);
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
            .ok_or_else(|| crate::error_context::runtime("Delta factory is missing"))?
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

/// Call the existing fixed-duration kernel for omitted or positional None starts.
///
/// # Safety
/// The descriptor validates a live Delta receiver, and CPython holds its arguments
/// and the GIL. All other signatures retain the original SDK parser and errors.
unsafe extern "C" fn fixed_span(
    receiver: *mut ffi::PyObject,
    args: *const *mut ffi::PyObject,
    count: ffi::Py_ssize_t,
    keywords: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    if !keywords.is_null() || !(count == 0 || (count == 1 && unsafe { *args == ffi::Py_None() })) {
        return match SPAN.original.get() {
            Some(original) => unsafe { original(receiver, args, count, keywords) },
            None => {
                let py = unsafe { Python::assume_attached() };
                crate::error_context::runtime("Delta duration callback is missing").restore(py);
                ptr::null_mut()
            }
        };
    }
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        // SAFETY: The checked method descriptor owns the receiver through return.
        // The frozen payload is borrowed only while the original kernel runs.
        let value = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        value.get().fixed_timedelta(py).map(Bound::into_ptr)
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            let none = py.None();
            crate::error_context::argument(py, error, "Delta.to_timedelta", "start", none.bind(py))
                .restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            crate::error_context::runtime("Rust panic while converting Delta duration").restore(py);
            ptr::null_mut()
        }
    }
}

/// Keep the SDK's method name, signature and documentation with a narrow fast path.
/// # Errors
/// Propagates descriptor allocation and dictionary insertion errors.
fn install_simple_method(
    py: Python<'_>,
    class: &Bound<'_, PyType>,
    dictionary: &Bound<'_, PyDict>,
    name: &str,
    cache: &'static SimpleMethod,
    callback: ffi::PyCFunctionFastWithKeywords,
) -> PyResult<()> {
    if py.version_info().minor != 13 {
        return Ok(());
    }
    let owner = cache.owner.get_or_try_init(py, || -> PyResult<_> {
        Ok(dictionary
            .get_item(name)?
            .ok_or_else(|| crate::error_context::runtime("Delta method is missing"))?
            .unbind())
    })?;
    // SAFETY: Only an actual CPython method descriptor has this full-ABI layout.
    if unsafe { ffi::Py_TYPE(owner.bind(py).as_ptr()) }
        != ptr::addr_of_mut!(ffi::PyMethodDescr_Type)
    {
        return Ok(());
    }
    let definition =
        unsafe { (*owner.bind(py).as_ptr().cast::<ffi::PyMethodDescrObject>()).d_method };
    if definition.is_null() {
        return Ok(());
    }
    let original = unsafe { *definition };
    if original.ml_name.is_null() || original.ml_flags != (ffi::METH_FASTCALL | ffi::METH_KEYWORDS)
    {
        return Ok(());
    }
    let _ = cache
        .original
        .set(unsafe { original.ml_meth.PyCFunctionFastWithKeywords });
    let method = cache.definition.get_or_init(|| {
        FactoryMethod(ffi::PyMethodDef {
            ml_meth: ffi::PyMethodDefPointer {
                PyCFunctionFastWithKeywords: callback,
            },
            ..original
        })
    });
    // SAFETY: Original metadata is kept alive by cache.owner; the copied method
    // definition is immutable and lives for every replacement descriptor.
    let descriptor = unsafe {
        Bound::from_owned_ptr_or_err(
            py,
            ffi::PyDescr_NewMethod(class.as_type_ptr(), ptr::addr_of!(method.0).cast_mut()),
        )
    }?;
    dictionary.set_item(name, descriptor)
}

/// Borrow the one positional collection and call the unchanged bulk implementation.
/// # Safety
/// The descriptor validates the receiver and CPython owns all arguments under
/// the GIL. Keyword and malformed calls delegate to the original SDK callback.
unsafe extern "C" fn apply_many(
    receiver: *mut ffi::PyObject,
    args: *const *mut ffi::PyObject,
    count: ffi::Py_ssize_t,
    keywords: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    if count != 1 || !keywords.is_null() {
        return match MANY.original.get() {
            Some(original) => unsafe { original(receiver, args, count, keywords) },
            None => {
                let py = unsafe { Python::assume_attached() };
                crate::error_context::runtime("Delta collection callback is missing").restore(py);
                ptr::null_mut()
            }
        };
    }
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        // SAFETY: Receiver and args[0] stay owned throughout iteration and every
        // Python callback. No mutable Rust payload borrow crosses those callbacks.
        let delta = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let values = unsafe { Borrowed::from_ptr(py, *args) };
        crate::bulk::apply(&delta, &values).map(Bound::into_ptr)
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            crate::error_context::runtime("Rust panic while applying Delta collection").restore(py);
            ptr::null_mut()
        }
    }
}

/// Initialize a base Delta using the already verified ready type.
///
/// This is the same pinned PyO3 initializer bridge used by bulk allocation.
/// Keeping it here gives dependency upgrades one place to audit; PyO3 still
/// owns every payload, borrow, thread and Python storage initialization.
/// # Safety
/// class must be this interpreter's live exact Delta type while attached.
/// The returned pointer owns one reference; allocation errors propagate.
#[inline(always)]
pub(crate) unsafe fn new_delta(
    py: Python<'_>,
    value: Delta,
    class: *mut ffi::PyTypeObject,
) -> PyResult<*mut ffi::PyObject> {
    unsafe {
        pyo3::impl_::pymethods::tp_new_impl::<_, Delta>(
            py,
            pyo3::PyClassInitializer::from(value),
            class,
        )
    }
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
    if class != EXACT_ALLOC_TYPE.load(Ordering::Relaxed) && class != Delta::type_object_raw(py) {
        return match ORIGINAL_NEW.get() {
            Some(original) => unsafe { original(class, args, kwargs) },
            None => {
                crate::error_context::runtime("Delta allocator is missing").restore(py);
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
        unsafe { new_delta(py, Delta::construct(&args, kwargs.as_deref())?, class) }
    }));
    match result {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            crate::error_context::runtime("Rust panic while allocating Delta").restore(py);
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
    let base = EXACT_ALLOC_TYPE.load(Ordering::Relaxed);
    if matches!(operation, ffi::Py_EQ | ffi::Py_NE)
        && !base.is_null()
        && unsafe { ffi::Py_TYPE(receiver) == base && ffi::Py_TYPE(other) == base }
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
    // Subclass callbacks and panic recovery need their own stack frame; exact
    // immutable values above should not pay for that larger working area.
    unsafe { compare_general(receiver, other, operation) }
}

/// Compare subclass operands while preserving callback errors and panic recovery.
///
/// # Safety
/// The comparison slot supplies live operands and a Delta receiver. No borrowed
/// payload reference escapes this attached callback, including on error.
#[cold]
#[inline(never)]
unsafe fn compare_general(
    receiver: *mut ffi::PyObject,
    other: *mut ffi::PyObject,
    operation: std::ffi::c_int,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let result = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let other = unsafe { Borrowed::from_ptr(py, other) };
        if matches!(operation, ffi::Py_EQ | ffi::Py_NE)
            && same_value_semantics(&receiver, &other)?
            && let Ok(right) = other.cast::<Delta>()
        {
            let equal = receiver.get().native_eq(right.get());
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
        if operation == ffi::Py_NE
            && let Some(result) = inherited_inequality(&receiver, &other)?
        {
            return Ok(result.into_ptr());
        }
        Ok(py.NotImplemented().into_ptr())
    }));
    match result {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            crate::error_context::runtime("Rust panic while comparing Delta").restore(py);
            ptr::null_mut()
        }
    }
}

/// Check current comparison/hash slots before applying Delta's field equality.
/// Ordering-only overrides are allowed; custom equality or hashing is not assumed.
/// Match object.__ne__ for a child that supplies its own equality.
/// Explicit child __ne__ is dispatched by Python before this inherited method.
/// # Errors
/// Preserves equality callbacks and truth-conversion errors, including non-bool results.
#[inline(never)]
pub(crate) fn inherited_inequality<'py>(
    receiver: &Bound<'py, Delta>,
    other: &Bound<'py, PyAny>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    if receiver.is_exact_instance_of::<Delta>() {
        return Ok(None);
    }
    let py = receiver.py();
    let actual = receiver.get_type();
    let base = py.get_type::<Delta>();
    // Special methods are looked up in the real MRO, bypassing instance and
    // metaclass __getattribute__. Retain the tuple before descriptor callbacks.
    let mro = unsafe { Bound::from_borrowed_ptr(py, (*actual.as_type_ptr()).tp_mro) };
    let mut equality = None;
    for ancestor in mro.cast::<PyTuple>()?.iter() {
        let ancestor = ancestor.cast::<PyType>()?;
        // Reaching Delta proves no ancestor supplied a different equality.
        // Avoid looking up its descriptor again for ordinary inherited children.
        if ancestor.is(&base) {
            return Ok(None);
        }
        // SAFETY: a ready actual MRO type owns its namespace under the GIL.
        let namespace = unsafe { Bound::from_borrowed_ptr(py, (*ancestor.as_type_ptr()).tp_dict) };
        if let Some(entry) = namespace
            .cast::<PyDict>()?
            .get_item(pyo3::intern!(py, "__eq__"))?
        {
            equality = Some(entry);
            break;
        }
    }
    let equality = equality
        .ok_or_else(|| crate::error_context::runtime("Delta equality descriptor is missing"))?;
    if equality.is(py
        .get_type::<Delta>()
        .getattr(pyo3::intern!(py, "__eq__"))
        .map_err(crate::error_context::external)?)
    {
        return Ok(None);
    }
    // Bind arbitrary descriptors exactly like special-method dispatch. Plain
    // Python functions can skip an otherwise temporary bound-method object.
    let result = if unsafe { ffi::PyFunction_Check(equality.as_ptr()) != 0 } {
        equality
            .call1((receiver, other))
            .map_err(crate::error_context::external)?
    } else {
        // SAFETY: the owned descriptor and receiver remain live throughout
        // binding; its type owns this public slot. A null result propagates.
        let get = unsafe { (*ffi::Py_TYPE(equality.as_ptr())).tp_descr_get };
        let bound = if let Some(get) = get {
            unsafe {
                Bound::from_owned_ptr_or_err(
                    py,
                    get(equality.as_ptr(), receiver.as_ptr(), actual.as_ptr()),
                )?
            }
        } else {
            equality
        };
        bound
            .call1((other,))
            .map_err(crate::error_context::external)?
    };
    if result.is(py.NotImplemented()) {
        return Ok(Some(result));
    }
    Ok(Some(
        PyBool::new(
            py,
            !result.is_truthy().map_err(crate::error_context::external)?,
        )
        .to_owned()
        .into_any(),
    ))
}

pub(crate) fn same_value_semantics(
    receiver: &Bound<'_, Delta>,
    other: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let Ok(other) = other.cast::<Delta>() else {
        return Ok(false);
    };
    let py = receiver.py();
    let base = py.get_type::<Delta>();
    for class in [receiver.get_type(), other.get_type()] {
        let actual = class.as_type_ptr();
        let base_pointer = base.as_type_ptr();
        // SAFETY: Both owned ready types remain live under the GIL; reading
        // their slots invokes no metaclass hooks or user comparison methods.
        let (hash, comparison, base_hash, base_comparison) = unsafe {
            (
                (*actual).tp_hash.map(|slot| slot as *const ()),
                (*actual).tp_richcompare.map(|slot| slot as *const ()),
                (*base_pointer).tp_hash.map(|slot| slot as *const ()),
                (*base_pointer).tp_richcompare.map(|slot| slot as *const ()),
            )
        };
        if hash == base_hash && comparison == base_comparison {
            continue;
        }
        if !inherits_value_methods(&class, &base)? {
            return Ok(false);
        }
    }
    Ok(true)
}

/// Own a ready type's live namespace without invoking Python metaclass hooks.
#[inline]
fn type_namespace<'py>(class: &Bound<'py, PyType>) -> PyResult<Bound<'py, PyDict>> {
    let py = class.py();
    // SAFETY: the live ready type owns its actual dictionary when this public
    // field is set. CPython 3.12+ may store builtin dictionaries per interpreter.
    let direct = unsafe { (*class.as_type_ptr()).tp_dict };
    if !direct.is_null() {
        return unsafe { Bound::from_borrowed_ptr(py, direct) }
            .cast_into::<PyDict>()
            .map_err(PyErr::from);
    }
    #[cfg(Py_3_12)]
    {
        // SAFETY: the public API accepts this retained ready type and returns
        // a new reference. The dictionary is read only, never mutated here.
        unsafe { Bound::from_owned_ptr_or_err(py, ffi::PyType_GetDict(class.as_type_ptr())) }
            .and_then(|value| value.cast_into::<PyDict>().map_err(PyErr::from))
    }
    #[cfg(not(Py_3_12))]
    {
        Err(crate::error_context::runtime(
            "actual type namespace is unavailable",
        ))
    }
}

/// Reuse fixed lookup keys without caching any mutable method definition.
#[inline]
fn method_key<'py>(py: Python<'py>, name: &str) -> Bound<'py, PyString> {
    match name {
        "__getstate__" => pyo3::intern!(py, "__getstate__").clone(),
        "__reduce__" => pyo3::intern!(py, "__reduce__").clone(),
        "__add__" => pyo3::intern!(py, "__add__").clone(),
        "__sub__" => pyo3::intern!(py, "__sub__").clone(),
        "__eq__" => pyo3::intern!(py, "__eq__").clone(),
        "__ne__" => pyo3::intern!(py, "__ne__").clone(),
        "__hash__" => pyo3::intern!(py, "__hash__").clone(),
        "utcoffset" => pyo3::intern!(py, "utcoffset").clone(),
        "fromutc" => pyo3::intern!(py, "fromutc").clone(),
        _ => PyString::new(py, name),
    }
}

/// Read a special-method definition from the real MRO, bypassing metaclass hooks.
///
/// # Errors
/// Propagates allocation errors; retained MRO and dictionary entries stay owned.
pub(crate) fn method_definition<'py>(
    class: &Bound<'py, PyType>,
    name: &str,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = class.py();
    let key = method_key(py, name);
    // Some CPython static types keep their metadata in interpreter state.
    // The builtin type descriptor bypasses any user metaclass override.
    let metadata = |name: &str| {
        py.get_type::<PyType>()
            .getattr("__getattribute__")
            .map_err(crate::error_context::external)?
            .call1((class, name))
            .map_err(crate::error_context::external)
    };
    // SAFETY: a live ready heap type owns this MRO when its public field is set.
    let mro = match unsafe { Bound::from_borrowed_ptr_or_opt(py, (*class.as_type_ptr()).tp_mro) } {
        Some(mro) => mro,
        None => metadata("__mro__")?,
    };
    for base in mro.cast::<PyTuple>()?.iter() {
        let base = base.cast::<PyType>()?;
        if let Some(method) = type_namespace(base)?.get_item(&key)? {
            return Ok(Some(method));
        }
    }
    Ok(None)
}

/// Execute a real special-method descriptor without consulting instance aliases.
///
/// # Errors
/// Keeps the descriptor binding and callback's original exception.
pub(crate) fn call_special<'py>(
    receiver: &Bound<'py, PyAny>,
    name: &str,
    other: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = receiver.py();
    let actual = receiver.get_type();
    let definition = method_definition(&actual, name)?
        .ok_or_else(|| crate::error_context::type_error("arithmetic method is not defined"))?;
    if unsafe { ffi::PyFunction_Check(definition.as_ptr()) != 0 } {
        return definition
            .call1((receiver, other))
            .map_err(crate::error_context::external);
    }
    // SAFETY: the retained descriptor, receiver and ready actual type remain
    // owned under the GIL, including throughout arbitrary descriptor callbacks.
    let bound = if let Some(get) = unsafe { (*ffi::Py_TYPE(definition.as_ptr())).tp_descr_get } {
        unsafe {
            Bound::from_owned_ptr_or_err(
                py,
                get(definition.as_ptr(), receiver.as_ptr(), actual.as_ptr()),
            )
        }
        .map_err(crate::error_context::external)?
    } else {
        definition
    };
    bound
        .call1((other,))
        .map_err(crate::error_context::external)
}

/// Inspect inherited value methods once without running hooks during dict iteration.
/// # Errors
/// Preserves type/attribute errors; retained MRO and entries survive callbacks.
#[inline(never)]
fn inherits_value_methods<'py>(
    class: &Bound<'py, PyType>,
    base: &Bound<'py, PyType>,
) -> PyResult<bool> {
    let py = class.py();
    // SAFETY: ready types own their MRO and namespace. Own the MRO tuple and
    // each selected entry before any later descriptor lookup can run Python.
    let mro = unsafe { Bound::from_borrowed_ptr(py, (*class.as_type_ptr()).tp_mro) }
        .cast_into::<PyTuple>()?;
    let names = ["__eq__", "__ne__", "__hash__"];
    let mut found = [false; 3];
    for ancestor in mro.iter() {
        let ancestor = ancestor.cast::<PyType>()?;
        if ancestor.is(base) {
            return Ok(true);
        }
        let namespace = type_namespace(ancestor)?;
        let mut entries: [Option<Bound<'py, PyAny>>; 3] = [None, None, None];
        for (key, value) in namespace.cast::<PyDict>()?.iter() {
            if !key.is_exact_instance_of::<PyString>() {
                return Ok(false);
            }
            let index = match key.cast::<PyString>()?.to_str()? {
                "__eq__" => 0,
                "__ne__" => 1,
                "__hash__" => 2,
                _ => continue,
            };
            if !found[index] {
                entries[index] = Some(value);
            }
        }
        // The live dictionary iterator has ended before any descriptor lookup.
        for (index, entry) in entries.into_iter().enumerate() {
            if let Some(entry) = entry {
                if !entry.is(base
                    .getattr(names[index])
                    .map_err(crate::error_context::external)?)
                {
                    return Ok(false);
                }
                found[index] = true;
            }
        }
        if found.iter().all(|value| *value) {
            return Ok(true);
        }
    }
    Ok(false)
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
        Err(_) => Err(crate::error_context::runtime(
            "Rust panic while calling Delta arithmetic",
        )),
    };
    match result {
        Ok(value) => value,
        Err(error) => {
            // METH_O keeps both arguments alive even when a callback mutates a container.
            let other = unsafe { Borrowed::from_ptr(py, other) };
            crate::error_context::argument(
                py,
                error,
                [
                    "Delta.__add__",
                    "Delta.__radd__",
                    "Delta.__sub__",
                    "Delta.__rsub__",
                ][operation],
                "other",
                &other,
            )
            .restore(py);
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
    definition(c"__add__", add, c"Add a Delta, timedelta, relativedelta, date/datetime or NumPy scalar.\n\nParameters\n----------\nother : object\n    Increment or date operand; NumPy arrays are unsupported.\n\nReturns\n-------\nDelta | date | datetime | NotImplemented\n    A base Delta for increment operands,\n        the input date subtype for Python dates, or a naive builtin datetime for\n        NumPy datetime64. Unsupported operands return NotImplemented.\n\nRaises\n------\nOverflowError\n    Numeric conversion or calendar arithmetic overflows.\nValueError\n    Invalid dates or NumPy NaT. Custom constructor errors propagate unchanged.\nException\n    Third-party conversion and other Python callback errors propagate.\n\nNotes\n-----\nDate operations apply absolute fields, relative increments, then weekday;\ndatetime timezone and fold are preserved. Pandas Timestamp nanoseconds are\nretained unless absolute microsecond or millisecond settings replace them.\nArrays are not supported."),
    definition(c"__radd__", radd, c"Apply reflected addition using the same date and duration rules as __add__.\n\nParameters\n----------\nother : object\n    Left-hand date, duration or relativedelta operand.\n\nA direct reflected call with another Delta returns NotImplemented. Conversion,\ncalendar and custom-constructor errors follow __add__."),
    definition(c"__sub__", sub, c"Subtract Delta, timedelta, relativedelta or NumPy timedelta64 from this Delta.\n\nParameters\n----------\nother : object\n    Increment to subtract; dates are unsupported here.\n\nReturns\n-------\nDelta | NotImplemented\n    A base Delta or NotImplemented for unsupported types,\n        including dates and NumPy datetime64 in this direction.\n\nRaises\n------\nOverflowError\n    Numeric conversion, subtraction or normalization overflows.\nException\n    Third-party conversion and Python callback errors propagate."),
    definition(c"__rsub__", rsub, c"Subtract this Delta from a date/datetime, timedelta or supported NumPy scalar.\n\nParameters\n----------\nother : object\n    Left-hand date, duration or relativedelta operand.\n\nrelativedelta is also supported; direct reflected Delta calls return\nNotImplemented. Return types and calendar errors follow reflected dispatch,\nwith OverflowError for unrepresentable negation or subtraction."),
]);

// Only CPython's checked getset descriptor calls this callback. Receiver
// ownership and its actual Delta subtype have already been checked by CPython.
/// Read the field selected by a checked CPython getset descriptor.
///
/// # Safety
/// The descriptor verifies a live Delta subtype receiver. Its callback fixes
/// one valid field index at compile time. No borrow escapes and the
/// result follows getset owned-reference conventions.
unsafe extern "C" fn getter<const INDEX: usize>(
    receiver: *mut ffi::PyObject,
    _closure: *mut std::ffi::c_void,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let result = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        // Borrow is confined to this callback; the descriptor keeps receiver
        // alive. No Rust reference escapes, and no mutable borrow is held.
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let value = receiver.get().relative(INDEX);
        if INDEX >= 8 && value == -1 {
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
            crate::error_context::runtime("Rust panic while reading Delta property").restore(py);
            ptr::null_mut()
        }
    }
}
/// Return the ordinary representation through a checked native repr slot.
/// # Safety
/// CPython supplies a live Delta subtype while attached. Python subclass slot
/// overrides still dispatch normally. The result owns one string reference;
/// exceptions and Rust panics are translated before crossing the ABI.
unsafe extern "C" fn representation(receiver: *mut ffi::PyObject) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    if unsafe { is_cached_exact_delta(receiver) } {
        // SAFETY: the live exact registered base holds the conventional GIL.
        // Frozen payload access and cloning an owned string cannot allocate or
        // invoke Python. Keep all fallible formatting off this small hot frame.
        let value = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        if let Some(text) = unsafe { value.get().cached_representation(py) } {
            return text.into_ptr();
        }
    }
    unsafe { representation_uncached(py, receiver) }
}

/// Format through the full checked implementation after a cache miss.
/// # Safety
/// receiver has the same live attached-Delta contract as representation.
#[cold]
#[inline(never)]
unsafe fn representation_uncached(
    py: Python<'_>,
    receiver: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    let outcome = catch_unwind(AssertUnwindSafe(|| {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        Delta::__repr__(&receiver).map(Bound::into_ptr)
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            error.restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            crate::error_context::runtime("Rust panic while formatting Delta").restore(py);
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
    // The verified native calculation only reads immutable fields and performs
    // infallible integer operations. Keep the repeated cache check and fallible
    // interpreter fallback behind the existing exception/panic boundary.
    if let Some(value) = receiver.get().native_hash() {
        return value;
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
            crate::error_context::runtime("Rust panic while hashing Delta").restore(py);
            -1
        }
    }
}

/// Restore the original failure with its true public arithmetic direction.
///
/// # Safety
/// Both raw operands remain owned by the CPython caller and py is attached.
/// This branch must not enlarge the successful numeric slot's inlined body.
#[cold]
#[inline(never)]
unsafe fn restore_binary_error<const SUBTRACT: bool>(
    py: Python<'_>,
    error: PyErr,
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    let left = unsafe { Borrowed::from_ptr(py, left) };
    let right = unsafe { Borrowed::from_ptr(py, right) };
    crate::error_context::binary(
        py,
        error,
        match (SUBTRACT, unsafe {
            ffi::PyObject_TypeCheck(left.as_ptr(), py.get_type::<Delta>().as_type_ptr()) == 0
        }) {
            (false, false) => "Delta.__add__",
            (false, true) => "Delta.__radd__",
            (true, false) => "Delta.__sub__",
            (true, true) => "Delta.__rsub__",
        },
        &left,
        &right,
    )
    .restore(py);
    ptr::null_mut()
}

// Numeric slots can receive Delta on either side. Check actual Python types
// before reading either Rust payload; a forged __class__ is never sufficient.
/// Dispatch a numeric add/subtract slot without changing reflected behavior.
///
/// # Safety
/// Both operands are live CPython objects while attached. Actual Python type
/// checks precede any Delta payload access. Returns an owned result or null with
/// an exception; unsupported combinations return owned NotImplemented.
unsafe fn binary<const SUBTRACT: bool>(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let left = unsafe { Borrowed::from_ptr(py, left) };
        let right = unsafe { Borrowed::from_ptr(py, right) };
        // The module-owned allocation cache retains this ready exact type.
        // Both live operands prove its lifetime; a disabled cache takes the
        // SDK lookup below. No subclass or spoofable __class__ qualifies.
        let cached = EXACT_ALLOC_TYPE.load(Ordering::Relaxed);
        if !cached.is_null()
            && unsafe {
                ffi::Py_TYPE(left.as_ptr()) == cached && ffi::Py_TYPE(right.as_ptr()) == cached
            }
        {
            let left = unsafe { left.cast_unchecked::<Delta>() };
            let right = unsafe { right.cast_unchecked::<Delta>() };
            return unsafe { new_delta(py, left.get().combine(right.get(), SUBTRACT)?, cached) };
        }
        let class = if cached.is_null() {
            Delta::type_object_raw(py)
        } else {
            cached
        };
        let api = unsafe { ffi::PyDateTimeAPI() };
        if !api.is_null() {
            let left_type = unsafe { ffi::Py_TYPE(left.as_ptr()) };
            let right_type = unsafe { ffi::Py_TYPE(right.as_ptr()) };
            let date_pair = if right_type == class {
                Some((&right, &left, left_type))
            } else if left_type == class && !SUBTRACT {
                Some((&left, &right, right_type))
            } else {
                None
            };
            if let Some((delta, other, actual)) = date_pair {
                let delta = unsafe { delta.cast_unchecked::<Delta>() };
                if !delta.get().__bool__()
                    && (actual == unsafe { (*api).DateTimeType }
                        || actual == unsafe { (*api).DateType }
                        || (unsafe { ffi::PyObject_TypeCheck(other.as_ptr(), (*api).DateType) }
                            != 0
                            && unsafe { ffi::PyDateTime_GET_YEAR(other.as_ptr()) } != 1))
                {
                    // Year-one subtypes retain the checked NaT route below.
                    return Ok(unsafe { ffi::Py_NewRef(other.as_ptr()) });
                }
            }
            let duration_type = unsafe { (*api).DeltaType };
            let duration_pair = if left_type == class && right_type == duration_type {
                Some((&left, &right, false))
            } else if right_type == class && left_type == duration_type {
                Some((&right, &left, SUBTRACT))
            } else {
                None
            };
            if let Some((delta, duration, reverse)) = duration_pair {
                let delta = unsafe { delta.cast_unchecked::<Delta>() };
                let duration = unsafe { duration.cast_unchecked::<PyDelta>() };
                return unsafe {
                    builtin_duration_result::<SUBTRACT>(py, delta.get(), &duration, class, reverse)
                };
            }
        }
        if let Some(value) = unsafe { binary_builtin::<SUBTRACT>(py, left, right, class) }? {
            return Ok(value);
        }
        unsafe { binary_foreign::<SUBTRACT>(py, left, right, class) }
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => unsafe { restore_binary_error::<SUBTRACT>(py, error, left, right) },
        Err(_) => {
            crate::error_context::runtime("Rust panic while applying Delta").restore(py);
            ptr::null_mut()
        }
    }
}
/// Combine a proven exact timedelta in a frame that needs no date/foreign state.
///
/// # Errors
/// Preserves checked final normalization and native result-allocation errors.
/// # Safety
/// The caller proves the exact builtin duration and the live ready Delta class;
/// both immutable operands remain owned by the outer C call through completion.
#[inline(never)]
unsafe fn builtin_duration_result<const SUBTRACT: bool>(
    py: Python<'_>,
    delta: &Delta,
    duration: &Bound<'_, PyDelta>,
    class: *mut ffi::PyTypeObject,
    reverse: bool,
) -> PyResult<*mut ffi::PyObject> {
    let result = delta.with_duration_parts(
        i64::from(duration.get_days()),
        i64::from(duration.get_seconds()),
        i64::from(duration.get_microseconds()),
        SUBTRACT,
        reverse,
    )?;
    unsafe { new_delta(py, result, class) }
}
/// Apply the existing builtin date/datetime/duration routes in their own frame.
///
/// # Errors
/// Preserves calendar, normalization, allocation and actual callback failures.
/// A genuine unsupported pair returns None without creating a Python error.
///
/// # Safety
/// The attached caller owns both live operands and a ready Delta class. Actual
/// builtin/layout checks below precede every payload read; the caller catches panic.
#[inline(never)]
unsafe fn binary_builtin<'py, const SUBTRACT: bool>(
    py: Python<'py>,
    left: Borrowed<'_, 'py, PyAny>,
    right: Borrowed<'_, 'py, PyAny>,
    class: *mut ffi::PyTypeObject,
) -> PyResult<Option<*mut ffi::PyObject>> {
    let datetime_api = unsafe { ffi::PyDateTimeAPI() };
    if !datetime_api.is_null() {
        // Exact builtin dates need no repeated membership tests. Left-hand
        // Delta subtraction still takes the original unsupported-date path.
        let left_type = unsafe { ffi::Py_TYPE(left.as_ptr()) };
        let right_type = unsafe { ffi::Py_TYPE(right.as_ptr()) };
        let date_class = unsafe { (*datetime_api).DateType };
        let datetime_class = unsafe { (*datetime_api).DateTimeType };
        let pair = if right_type == class {
            Some((&right, &left, left_type, if SUBTRACT { -1 } else { 1 }))
        } else if left_type == class && !SUBTRACT {
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
                if actual != datetime_class
                    && actual != date_class
                    && unsafe { ffi::PyDateTime_GET_YEAR(other.as_ptr()) } == 1
                {
                    crate::interop::reject_nat(other, "Delta date arithmetic", "other")?;
                }
                // SAFETY: other is a live date/datetime subtype under the GIL;
                // the numeric slot must return an owned reference.
                return Ok(Some(unsafe { ffi::Py_NewRef(other.as_ptr()) }));
            }
            let result = if actual == datetime_class {
                let datetime = unsafe { other.cast_unchecked::<PyDateTime>() };
                // Exact builtin values have no foreign carrier or nanosecond tail.
                // Retain the no-change shortcut and reuse the batch's proven kernel.
                if delta.get().preserves_datetime_clock(&datetime) {
                    return Ok(Some(unsafe { ffi::Py_NewRef(other.as_ptr()) }));
                }
                crate::interop::apply_builtin_datetime_fields(
                    &delta.get().native_value(),
                    false,
                    other,
                    &datetime,
                    sign,
                )?
            } else if actual == date_class {
                let date = unsafe { other.cast_unchecked::<PyDate>() };
                crate::interop::apply_date_only(delta.get(), other, &date, sign)?
            } else {
                None
            };
            if let Some(result) = result {
                return Ok(Some(result.into_ptr()));
            }
        }
        let duration_class = unsafe { (*datetime_api).DeltaType };
        if unsafe {
            ffi::Py_TYPE(left.as_ptr()) == class
                && ffi::PyObject_TypeCheck(right.as_ptr(), duration_class) != 0
        } {
            // The exact Delta and genuine timedelta subtype have proven
            // native layouts. Python has already tried reflected overrides;
            // these C fields match the existing fallback's duration reads.
            let delta = unsafe { left.cast_unchecked::<Delta>() };
            let duration = unsafe { right.cast_unchecked::<PyDelta>() };
            return unsafe {
                new_delta(
                    py,
                    delta.get().with_duration(&duration, SUBTRACT, false)?,
                    class,
                )
            }
            .map(Some);
        }
        if unsafe {
            ffi::Py_TYPE(right.as_ptr()) == class
                && ffi::PyObject_TypeCheck(left.as_ptr(), duration_class) != 0
        } {
            let delta = unsafe { right.cast_unchecked::<Delta>() };
            let duration = unsafe { left.cast_unchecked::<PyDelta>() };
            return unsafe {
                new_delta(
                    py,
                    delta.get().with_duration(&duration, SUBTRACT, SUBTRACT)?,
                    class,
                )
            }
            .map(Some);
        }
    }
    Ok(None)
}

/// Dispatch non-exact or foreign operands outside the compact Delta frame.
///
/// # Errors
/// Preserves checked arithmetic and actual conversion or callback failures.
/// Returns an owned result pointer, possibly NotImplemented, on success.
///
/// # Safety
/// Both caller-owned operands remain live on the attached thread. Every payload
/// read retains its original actual-type check; the caller catches any panic.
#[inline(never)]
unsafe fn binary_foreign<'py, const SUBTRACT: bool>(
    py: Python<'py>,
    left: Borrowed<'_, 'py, PyAny>,
    right: Borrowed<'_, 'py, PyAny>,
    class: *mut ffi::PyTypeObject,
) -> PyResult<*mut ffi::PyObject> {
    // Preserve original temporal scalar identity before NumPy item conversion.
    // The exact-type cache qualifies public layout; real subclasses retain the
    // existing reflected protocol below. Both orientations share the ns model.
    if unsafe { ffi::Py_TYPE(left.as_ptr()) } == class
        && let Some(types) = crate::numpy_scalar::ExactTypes::cached(py)
        && let Some(source) = types.delta_scalar(&right, !SUBTRACT)?
    {
        let delta = unsafe { left.cast_unchecked::<Delta>() };
        return delta
            .get()
            .apply_numpy(py, source, SUBTRACT, false, false)
            .map(Bound::into_ptr);
    }
    // Exact native Delta/relativedelta operands bypass the generic date and
    // duration tests. Non-exact objects retain both original instance checks.
    if unsafe { ffi::Py_TYPE(left.as_ptr()) } == class {
        if let Some(fields) = crate::interop::exact_relative_fields(&right)? {
            let delta = unsafe { left.cast_unchecked::<Delta>() };
            return unsafe {
                new_delta(
                    py,
                    delta.get().with_relative_fields(fields, SUBTRACT, false)?,
                    class,
                )
            };
        }
    } else if unsafe { ffi::Py_TYPE(right.as_ptr()) } == class
        && let Some(fields) = crate::interop::exact_relative_fields(&left)?
    {
        let delta = unsafe { right.cast_unchecked::<Delta>() };
        return unsafe {
            new_delta(
                py,
                delta.get().with_relative_fields(fields, SUBTRACT, true)?,
                class,
            )
        };
    }
    let result = if unsafe { ffi::PyObject_TypeCheck(left.as_ptr(), class) } != 0 {
        let value = unsafe { left.cast_unchecked::<Delta>() };
        if SUBTRACT {
            value.get().__sub__(&right)
        } else {
            value.get().__add__(&right)
        }
    } else if unsafe { ffi::PyObject_TypeCheck(right.as_ptr(), class) } != 0 {
        let value = unsafe { right.cast_unchecked::<Delta>() };
        let types = match crate::numpy_scalar::ExactTypes::cached(py) {
            Some(types) => Some(types),
            None => crate::numpy_scalar::ExactTypes::for_value(&left)?,
        };
        if let Some(source) = types
            .map(|types| types.delta_scalar(&left, true))
            .transpose()?
            .flatten()
        {
            if matches!(
                source,
                crate::numpy_scalar::DeltaScalar::Duration {
                    calendar_unit: true,
                    ..
                }
            ) {
                return Ok(py.NotImplemented().into_ptr());
            }
            return value
                .get()
                .apply_numpy(py, source, SUBTRACT, true, true)
                .map(Bound::into_ptr);
        }
        if SUBTRACT {
            value.get().__rsub__(&left)
        } else {
            value.get().__radd__(&left)
        }
    } else {
        Ok(py.NotImplemented().into_bound(py))
    }?;
    Ok(result.into_ptr())
}
/// Delegate the numeric addition slot to the checked binary dispatcher.
///
/// # Safety
/// Inherits binary's live-operand and attached-thread requirements.
unsafe extern "C" fn number_add(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    unsafe { binary::<false>(left, right) }
}
/// Delegate the numeric subtraction slot to the checked binary dispatcher.
///
/// # Safety
/// Inherits binary's live-operand and attached-thread requirements.
unsafe extern "C" fn number_sub(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    unsafe { binary::<true>(left, right) }
}

/// Apply a native unary operation without repeating Python descriptor checks.
///
/// # Safety
/// CPython's inherited numeric slot supplies a live Delta or Delta subclass
/// under the GIL. The native value remains borrowed only during the callback;
/// the result is a new owned base Delta. Errors and panics never cross the ABI.
#[inline(always)]
unsafe fn unary<const ABSOLUTE: bool>(receiver: *mut ffi::PyObject) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let receiver = unsafe { Borrowed::from_ptr(py, receiver).cast_unchecked::<Delta>() };
        let value = if ABSOLUTE {
            receiver.get().__abs__()?
        } else {
            receiver.get().__neg__()?
        };
        let class = EXACT_ALLOC_TYPE.load(Ordering::Relaxed);
        if !class.is_null() && unsafe { ffi::Py_TYPE(receiver.as_ptr()) } == class {
            unsafe { new_delta(py, value, class) }
        } else {
            Bound::new(py, value).map(Bound::into_ptr)
        }
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            let input = unsafe { Borrowed::from_ptr(py, receiver) };
            crate::error_context::argument(
                py,
                error,
                if ABSOLUTE {
                    "Delta.__abs__"
                } else {
                    "Delta.__neg__"
                },
                "value",
                &input,
            )
            .restore(py);
            ptr::null_mut()
        }
        Err(_) => {
            crate::error_context::runtime("Rust panic while applying a unary Delta operation")
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
    unsafe { unary::<false>(receiver) }
}

/// Delegate the numeric absolute-value slot to checked grouped-sign behavior.
///
/// # Safety
/// Inherits unary's live-Delta and attached-thread requirements.
unsafe extern "C" fn number_absolute(receiver: *mut ffi::PyObject) -> *mut ffi::PyObject {
    unsafe { unary::<true>(receiver) }
}

// type_call invokes tp_init with an instance of this type, a live argument
// tuple, and either a live dictionary or NULL. No borrowed value escapes.
/// Preserve an already initialized immutable Delta in CPython's tp_init slot.
///
/// # Safety
/// The method descriptor validates a live Delta subtype receiver. Arguments
/// are caller-owned FASTCALL slots; they are never read or retained.
unsafe extern "C" fn initialize_direct(
    _receiver: *mut ffi::PyObject,
    _args: *const *mut ffi::PyObject,
    _count: ffi::Py_ssize_t,
    _keywords: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    // Construction has already installed the value. A direct repeated call
    // accepts the same arguments and cannot overwrite immutable fields.
    unsafe { ffi::Py_NewRef(ffi::Py_None()) }
}
struct Initializer(ffi::PyMethodDef);
// CPython only reads this process-lifetime descriptor definition.
unsafe impl Sync for Initializer {}
static INITIALIZER: Initializer = Initializer(ffi::PyMethodDef {
    ml_name: c"__init__".as_ptr(),
    ml_meth: ffi::PyMethodDefPointer {
        PyCFunctionFastWithKeywords: initialize_direct,
    },
    ml_flags: ffi::METH_FASTCALL | ffi::METH_KEYWORDS,
    ml_doc: c"Initialization is completed when the object is created.

Repeated calls leave its value unchanged."
        .as_ptr(),
    // No instance data is retained by this definition.
});

struct Getters([ffi::PyGetSetDef; 17]);
// Static readonly names, docstrings and field-specific callback pointers.
// CPython does not mutate this table.
unsafe impl Sync for Getters {}
/// Build a readonly field descriptor with static name and documentation.
///
/// INDEX selects one of the17 validated fields at compile time.
const fn property<const INDEX: usize>(
    name: &'static std::ffi::CStr,
    doc: &'static std::ffi::CStr,
) -> ffi::PyGetSetDef {
    ffi::PyGetSetDef {
        name: name.as_ptr(),
        get: Some(getter::<INDEX>),
        set: None,
        doc: doc.as_ptr(),
        closure: ptr::null_mut(),
    }
}
static GETTERS: Getters = Getters([
    property::<0>(
        c"years",
        c"int: Normalized relative years; months are carried into this value.",
    ),
    property::<1>(
        c"months",
        c"int: Relative months after grouping years, in 0..11.",
    ),
    property::<2>(
        c"days",
        c"int: Relative days, including normalized weeks and clock carries.",
    ),
    property::<3>(c"hours", c"int: Normalized relative hours, in 0..23."),
    property::<4>(c"minutes", c"int: Normalized relative minutes, in 0..59."),
    property::<5>(c"seconds", c"int: Normalized relative seconds, in 0..59."),
    property::<6>(
        c"microseconds",
        c"int: Normalized relative microseconds, in 0..999999.",
    ),
    property::<7>(
        c"nanoseconds",
        c"int: Normalized relative nanosecond tail, in0..999.",
    ),
    property::<8>(
        c"year",
        c"int | None: Absolute year replacement, or None when unset.",
    ),
    property::<9>(
        c"month",
        c"int | None: Absolute month replacement (1..12), or None when unset.",
    ),
    property::<10>(
        c"day",
        c"int | None: Absolute day replacement (1..31), or None when unset.",
    ),
    property::<11>(
        c"weekday",
        c"int | None: Absolute weekday replacement (Monday=0 to Sunday=6), or None.",
    ),
    property::<12>(
        c"hour",
        c"int | None: Absolute hour replacement (0..23), or None when unset.",
    ),
    property::<13>(
        c"minute",
        c"int | None: Absolute minute replacement (0..59), or None when unset.",
    ),
    property::<14>(
        c"second",
        c"int | None: Absolute second replacement (0..59), or None when unset.",
    ),
    property::<15>(
        c"microsecond",
        c"int | None: Absolute microsecond replacement (0..999999), or None.",
    ),
    property::<16>(
        c"nanosecond",
        c"int | None: Absolute nanosecond tail in0..999, or None.",
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
    // A transiently enabled GIL in a free-threaded build cannot protect these
    // process caches later. Unknown build metadata selects the standard path.
    let build_setting = py
        .import("sysconfig")
        .and_then(|module| {
            module
                .call_method1("get_config_var", ("Py_GIL_DISABLED",))
                .map_err(crate::error_context::external)
        })
        .and_then(|value| value.extract::<i64>());
    let conventional_gil_build = match build_setting {
        Ok(value) => value == 0,
        Err(error) => {
            if crate::error_context::critical(py, &error)? {
                return Err(error);
            }
            false
        }
    };
    if eligible
        && conventional_gil_build
        && py
            .import("sys")?
            .getattr("_is_gil_enabled")
            .map_err(crate::error_context::external)?
            .call0()
            .map_err(crate::error_context::external)?
            .extract::<bool>()?
        && let Some(original) = unsafe { (*class_ptr).tp_alloc }
    {
        // A byte budget bounds retained dead blocks and their pointer table;
        // it is independent of benchmark case sizes and user input lengths.
        let limit = (2 * 1024 * 1024)
            / (unsafe { (*class_ptr).tp_basicsize as usize }
                + std::mem::size_of::<ptr::NonNull<c_void>>());
        let cache = unsafe { &mut *ALLOCATION_CACHE.0.get() };
        cache
            .blocks
            .try_reserve_exact(limit)
            .map_err(|_| pyo3::exceptions::PyMemoryError::new_err("cannot allocate Delta cache"))?;
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
    let original = unsafe { (*class_ptr).tp_new }
        .ok_or_else(|| crate::error_context::runtime("Delta allocator is missing"))?;
    let _ = ORIGINAL_NEW.set(original);
    // Full CPython ABI: class is a live, ready PyTypeObject owned by `class`.
    // Its tp_dict remains owned by that type. Descriptors and selected slots
    // stay attached to our own type; PyType_Modified invalidates caches.
    let dictionary = unsafe { Bound::from_borrowed_ptr(py, (*class_ptr).tp_dict) };
    let dictionary = dictionary.cast::<PyDict>()?;
    install_factory(py, &class, dictionary)?;
    install_simple_method(py, &class, dictionary, "to_timedelta", &SPAN, fixed_span)?;
    install_simple_method(py, &class, dictionary, "apply_many", &MANY, apply_many)?;
    let initializer = unsafe {
        Bound::from_owned_ptr_or_err(
            py,
            ffi::PyDescr_NewMethod(class_ptr, ptr::addr_of!(INITIALIZER.0).cast_mut()),
        )
    }?;
    dictionary.set_item("__init__", initializer)?;
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
        return Err(crate::error_context::runtime(
            "Delta numeric slots are missing",
        ));
    }
    unsafe {
        (*numbers).nb_bool = Some(truth);
        (*numbers).nb_add = Some(number_add);
        (*numbers).nb_subtract = Some(number_sub);
        (*numbers).nb_negative = Some(number_negative);
        (*numbers).nb_absolute = Some(number_absolute);
        (*class_ptr).tp_hash = Some(hash);
        // str keeps its original dynamic delegation to the current repr slot.
        (*class_ptr).tp_repr = Some(representation);
        // Base values are complete after tp_new; direct __init__ remains a no-op.
        // Python subclasses still derive their own initialization slot normally.
        (*class_ptr).tp_init = None;
        (*class_ptr).tp_new = Some(allocate);
        (*class_ptr).tp_richcompare = Some(compare)
    };
    unsafe { ffi::PyType_Modified(class_ptr) };
    Ok(())
}
