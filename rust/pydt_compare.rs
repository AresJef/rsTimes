//! Datetime comparison slots with a cold, true-value pandas boundary.
//!
//! The private base adds no instance storage. Ordinary comparisons retain
//! datetime's stored-field rules; Python subclasses keep normal dispatch.

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBool, PyDateAccess, PyDateTime, PyDict, PyTimeAccess, PyTuple, PyType};
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::OnceLock;
use std::sync::atomic::{AtomicPtr, Ordering};

static COMPARE: OnceLock<ffi::richcmpfunc> = OnceLock::new();
static SUBTRACT: OnceLock<ffi::binaryfunc> = OnceLock::new();
// The existing PyOnceLock owns the type reference. This is only a pointer-
// equality shortcut, never an independently dereferenced foreign type pointer.
static TIMESTAMP: AtomicPtr<ffi::PyTypeObject> = AtomicPtr::new(std::ptr::null_mut());

/// Own the public native descriptor; no pandas instance layout is assumed.
struct TimestampAccess {
    _descriptor: Py<PyAny>,
    getter: ffi::getter,
    closure: usize,
    comparator: ffi::richcmpfunc,
    zero: Py<PyAny>,
}
static TIMESTAMP_ACCESS: PyOnceLock<Option<TimestampAccess>> = PyOnceLock::new();

/// Cache only a type whose own instances have datetime storage.
fn cache_timestamp_type(py: Python<'_>) {
    if let Some(kind) = crate::interop::timestamp_type(py) {
        // SAFETY: the retained class and imported datetime type are live.
        if unsafe { ffi::PyType_IsSubtype(kind, (*ffi::PyDateTimeAPI()).DateTimeType) != 0 } {
            TIMESTAMP.store(kind, Ordering::Relaxed);
        }
    }
}

/// Resolve pandas' original native property and comparison wrappers once.
fn prepare_timestamp_access(value: &Bound<'_, PyAny>) -> PyResult<()> {
    let py = value.py();
    crate::python_cache::get_or_prepare(&TIMESTAMP_ACCESS, py, || -> PyResult<_> {
        let Some(kind) = crate::interop::timestamp_type(py) else {
            return Ok(None);
        };
        // SAFETY: the shared type cache owns this proven Timestamp base type.
        let class =
            unsafe { Bound::<PyAny>::from_borrowed_ptr(py, kind.cast()) }.cast_into::<PyType>()?;
        let descriptor = class
            .getattr("nanosecond")
            .map_err(crate::error_context::external)?;
        // A Python replacement property must stay on the general protocol path.
        if unsafe {
            ffi::Py_TYPE(descriptor.as_ptr()) != std::ptr::addr_of_mut!(ffi::PyGetSetDescr_Type)
        } {
            return Ok(None);
        }
        // SAFETY: the exact descriptor type proves both public C structures.
        let definition = unsafe { &*(descriptor.as_ptr() as *const ffi::PyGetSetDescrObject) };
        if definition.d_getset.is_null() {
            return Ok(None);
        }
        let owner = definition.d_common.d_type;
        // A borrowed descriptor can belong to an unrelated extension type.
        // Prove the cached class layout before directly invoking its getter.
        if owner.is_null() || unsafe { ffi::PyType_IsSubtype(kind, owner) == 0 } {
            return Ok(None);
        }
        for name in ["__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"] {
            let wrapper = class
                .getattr(name)
                .map_err(crate::error_context::external)?;
            // Only the original native wrappers sharing this property owner
            // qualify; Python or borrowed-method overrides retain dispatch.
            if unsafe {
                ffi::Py_TYPE(wrapper.as_ptr()) != std::ptr::addr_of_mut!(ffi::PyWrapperDescr_Type)
                    || (*(wrapper.as_ptr() as *const ffi::PyWrapperDescrObject))
                        .d_common
                        .d_type
                        != owner
            } {
                return Ok(None);
            }
        }
        let Some(comparator) = (unsafe { (*kind).tp_richcompare }) else {
            return Ok(None);
        };
        let getset = unsafe { &*definition.d_getset };
        if getset.name.is_null() {
            return Ok(None);
        }
        let Some(getter) = getset.get else {
            return Ok(None);
        };
        // SAFETY: value has the proven descriptor owner's Timestamp layout.
        // The descriptor stays owned by the cache for the getter/closure lifetime.
        let sample = unsafe {
            Bound::<PyAny>::from_owned_ptr_or_err(py, getter(value.as_ptr(), getset.closure))?
        };
        if !sample.is_exact_instance_of::<pyo3::types::PyInt>()
            || !(0..=999).contains(&sample.extract::<i32>()?)
        {
            return Ok(None);
        }
        let zero = 0_i32.into_pyobject(py)?.into_any();
        Ok(Some(TimestampAccess {
            getter,
            closure: getset.closure as usize,
            comparator,
            zero: zero.unbind(),
            _descriptor: descriptor.unbind(),
        }))
    })?;
    Ok(())
}

/// Reverse relational operands while leaving equality operations unchanged.
#[inline(always)]
fn swapped(operation: i32) -> i32 {
    match operation {
        ffi::Py_LT => ffi::Py_GT,
        ffi::Py_LE => ffi::Py_GE,
        ffi::Py_GT => ffi::Py_LT,
        ffi::Py_GE => ffi::Py_LE,
        _ => operation,
    }
}

/// Read exact epoch ticks only after proving the foreign Timestamp type.
fn ticks(value: &Bound<'_, PyAny>, wall_clock: bool) -> PyResult<(i128, bool)> {
    crate::interop::datetime_operation_ticks(value.cast::<PyDateTime>()?, wall_clock)
}

/// Check PEP 495's equality exception only after actual UTC values match.
/// The base replacement descriptor avoids invoking an unrelated user replace.
fn fold_dependent(value: &Bound<'_, PyAny>, original: i128, aware: bool) -> PyResult<bool> {
    let py = value.py();
    let timestamp = crate::interop::is_timestamp(value)?;
    let stored = value.cast::<PyDateTime>()?;
    if (!timestamp || !matches!(stored.get_year(), 1970 | 1972))
        && let Some(answer) = crate::pydt::standard_fold_dependent(stored)?
    {
        return Ok(answer);
    }
    let class = if timestamp {
        let kind = crate::interop::timestamp_type(py)
            .ok_or_else(|| crate::error_context::runtime("Timestamp type is unavailable"))?;
        // SAFETY: the interpreter-owned cache keeps this real base type alive.
        unsafe { Bound::<PyAny>::from_borrowed_ptr(py, kind.cast()) }.cast_into::<PyType>()?
    } else {
        py.get_type::<PyDateTime>()
    };
    let replace = crate::protocol::method_definition(&class, "replace")?
        .ok_or_else(|| crate::error_context::runtime("datetime replacement is unavailable"))?;
    let kwargs = PyDict::new(py);
    kwargs.set_item("fold", i32::from(!value.cast::<PyDateTime>()?.get_fold()))?;
    let alternate = replace
        .call((value,), Some(&kwargs))
        .map_err(crate::error_context::external)?;
    let (alternate, alternate_aware) = ticks(&alternate, false)?;
    Ok(alternate != original || alternate_aware != aware)
}

/// Compare actual Timestamp ticks without losing sub-microsecond precision.
#[cold]
fn foreign_compare(
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
    operation: i32,
) -> PyResult<Option<bool>> {
    if crate::interop::is_nat(right)? {
        return Ok(Some(operation == ffi::Py_NE));
    }
    if !crate::interop::is_timestamp(right)? {
        return Ok(None);
    }
    cache_timestamp_type(right.py());
    // Match datetime: identical timezone objects compare local fields, ignoring
    // fold. Different timezone objects compare their represented UTC instants.
    // SAFETY: the C slot proves the receiver layout and the check above proves
    // real Timestamp ancestry for the right operand.
    let wall_clock = unsafe {
        ffi::PyDateTime_DATE_GET_TZINFO(left.as_ptr())
            == ffi::PyDateTime_DATE_GET_TZINFO(right.as_ptr())
    };
    let (left_ticks, left_aware) = ticks(left, wall_clock)?;
    let (right_ticks, right_aware) = ticks(right, wall_clock)?;
    if left_aware != right_aware {
        return match operation {
            ffi::Py_EQ => Ok(Some(false)),
            ffi::Py_NE => Ok(Some(true)),
            _ => Err(crate::error_context::type_error(
                "cannot compare offset-naive and offset-aware dates",
            )),
        };
    }
    if !wall_clock
        && left_aware
        && left_ticks == right_ticks
        && matches!(operation, ffi::Py_EQ | ffi::Py_NE)
        && (fold_dependent(left, left_ticks, left_aware)?
            || fold_dependent(right, right_ticks, right_aware)?)
    {
        return Ok(Some(operation == ffi::Py_NE));
    }
    Ok(Some(match operation {
        ffi::Py_EQ => left_ticks == right_ticks,
        ffi::Py_NE => left_ticks != right_ticks,
        ffi::Py_LT => left_ticks < right_ticks,
        ffi::Py_LE => left_ticks <= right_ticks,
        ffi::Py_GT => left_ticks > right_ticks,
        ffi::Py_GE => left_ticks >= right_ticks,
        _ => {
            return Err(crate::error_context::type_error(
                "invalid datetime comparison operation",
            ));
        }
    }))
}

/// Keep callback handling off the ordinary datetime comparison stack.
///
/// # Safety
/// CPython supplies live operands and a real datetime receiver under the GIL.
/// Returns a new reference, or null with an active Python exception.
#[cold]
#[inline(never)]
unsafe fn compare_foreign(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
    operation: i32,
    standard: ffi::richcmpfunc,
) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let outcome = catch_unwind(AssertUnwindSafe(|| -> PyResult<_> {
        let left_bound = unsafe { Borrowed::from_ptr(py, left) };
        let right_bound = unsafe { Borrowed::from_ptr(py, right) };
        if crate::interop::is_timestamp(&right_bound)? {
            cache_timestamp_type(py);
            prepare_timestamp_access(&right_bound)?;
            // pandas' own comparator handles ordinary real years and nanos
            // directly, including reflected user comparisons. Its wide-year
            // datetime carrier needs the explicit integer path below instead.
            if let Some(slot) = unsafe { (*ffi::Py_TYPE(right)).tp_richcompare } {
                let standard_timestamp = TIMESTAMP_ACCESS
                    .get(py)
                    .and_then(Option::as_ref)
                    .is_some_and(|access| std::ptr::fn_addr_eq(slot, access.comparator));
                if !standard_timestamp {
                    // A custom result owns the decision. NotImplemented only
                    // declines that hook; our true-value comparison is still
                    // applicable and must not ask Python to invoke it again.
                    let answer = unsafe { slot(right, left, swapped(operation)) };
                    if answer.is_null() {
                        return Err(crate::error_context::fetch(py));
                    }
                    if answer != unsafe { ffi::Py_NotImplemented() } {
                        return Ok(answer);
                    }
                    unsafe { ffi::Py_DECREF(answer) };
                }
            }
        }
        if let Some(answer) = foreign_compare(&left_bound, &right_bound, operation)? {
            return Ok(PyBool::new(py, answer).to_owned().into_ptr());
        }
        // SAFETY: the original datetime slot accepts this live datetime receiver.
        let answer = unsafe { standard(left, right, operation) };
        if answer.is_null() {
            Err(crate::error_context::fetch(py))
        } else {
            Ok(answer)
        }
    }));
    match outcome {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            let left = unsafe { Borrowed::from_ptr(py, left) };
            let right = unsafe { Borrowed::from_ptr(py, right) };
            let entry = match operation {
                ffi::Py_LT => "Pydt.__lt__",
                ffi::Py_LE => "Pydt.__le__",
                ffi::Py_EQ => "Pydt.__eq__",
                ffi::Py_NE => "Pydt.__ne__",
                ffi::Py_GT => "Pydt.__gt__",
                _ => "Pydt.__ge__",
            };
            crate::error_context::binary(py, error, entry, &left, &right).restore(py);
            std::ptr::null_mut()
        }
        Err(_) => {
            crate::error_context::runtime("Rust panic while comparing Pydt").restore(py);
            std::ptr::null_mut()
        }
    }
}

/// Order the ten public datetime field bytes with two native integer loads.
/// Big-endian significance matches calendar ordering without a memcmp call.
#[inline(always)]
fn field_order(a: &[u8; 10], b: &[u8; 10]) -> std::cmp::Ordering {
    let first_a = u64::from_be_bytes([a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]]);
    let first_b = u64::from_be_bytes([b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]]);
    let first = first_a.cmp(&first_b);
    if first.is_eq() {
        u16::from_be_bytes([a[8], a[9]]).cmp(&u16::from_be_bytes([b[8], b[9]]))
    } else {
        first
    }
}

/// Compare native fields with datetime's same-timezone, fold-ignoring rule.
///
/// # Safety
/// Both arguments have already been proven to have datetime layout.
#[inline(always)]
unsafe fn same_zone_compare(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
    operation: i32,
) -> Option<*mut ffi::PyObject> {
    unsafe {
        if ffi::PyDateTime_DATE_GET_TZINFO(left) != ffi::PyDateTime_DATE_GET_TZINFO(right) {
            return None;
        }
        // The C API stores calendar/time components in big-endian significance
        // order, so byte ordering is the same as wall-clock ordering.
        let a = &(*(left as *const ffi::PyDateTime_DateTime)).data;
        let b = &(*(right as *const ffi::PyDateTime_DateTime)).data;
        let answer = match operation {
            ffi::Py_EQ => a == b,
            ffi::Py_NE => a != b,
            ffi::Py_LT => field_order(a, b).is_lt(),
            ffi::Py_LE => !field_order(a, b).is_gt(),
            ffi::Py_GT => field_order(a, b).is_gt(),
            ffi::Py_GE => !field_order(a, b).is_lt(),
            _ => false,
        };
        Some(ffi::Py_NewRef(if answer {
            ffi::Py_True()
        } else {
            ffi::Py_False()
        }))
    }
}

/// Add context only after a standard C slot has reported an actual failure.
///
/// # Safety
/// The active C operation has set an exception. Its input need not be reread.
#[cold]
#[inline(never)]
unsafe fn comparison_failed(operation: i32, location: &str) -> *mut ffi::PyObject {
    let py = unsafe { Python::assume_attached() };
    let error = crate::error_context::fetch(py);
    let entry = match operation {
        ffi::Py_LT => "Pydt.__lt__",
        ffi::Py_LE => "Pydt.__le__",
        ffi::Py_EQ => "Pydt.__eq__",
        ffi::Py_NE => "Pydt.__ne__",
        ffi::Py_GT => "Pydt.__gt__",
        _ => "Pydt.__ge__",
    };
    crate::error_context::location(py, error, entry, location).restore(py);
    std::ptr::null_mut()
}

/// Preserve standard successful comparisons without entering the error helper.
///
/// # Safety
/// CPython supplies live operands accepted by the retained standard slot.
#[cold]
#[inline(never)]
unsafe fn call_standard(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
    operation: i32,
    standard: ffi::richcmpfunc,
) -> *mut ffi::PyObject {
    let result = unsafe { standard(left, right, operation) };
    if result.is_null() {
        unsafe { comparison_failed(operation, "operands") }
    } else {
        result
    }
}

/// Preserve the builtin slot for exact or same-type operands.
///
/// # Safety
/// Installed only on a datetime subclass; CPython owns both live operands.
unsafe extern "C" fn compare(
    left: *mut ffi::PyObject,
    right: *mut ffi::PyObject,
    operation: i32,
) -> *mut ffi::PyObject {
    // SAFETY: registration initializes the datetime C API before this slot is
    // reachable. Type equality proves the direct cases without Python callbacks.
    unsafe {
        let kind = ffi::Py_TYPE(right);
        if kind == ffi::Py_TYPE(left)
            || kind == (*ffi::PyDateTimeAPI()).DateTimeType
            || (*kind)
                .tp_richcompare
                .is_some_and(|slot| std::ptr::fn_addr_eq(slot, compare as ffi::richcmpfunc))
        {
            if let Some(answer) = same_zone_compare(left, right, operation) {
                return answer;
            }
        } else if kind == TIMESTAMP.load(Ordering::Relaxed) {
            let year = ffi::PyDateTime_GET_YEAR(right);
            if !matches!(year, 1970 | 1972) {
                let py = Python::assume_attached();
                if let Some(Some(access)) = TIMESTAMP_ACCESS.get(py) {
                    let original = (*kind)
                        .tp_richcompare
                        .is_some_and(|slot| std::ptr::fn_addr_eq(slot, access.comparator));
                    let zone = ffi::PyDateTime_DATE_GET_TZINFO(left);
                    if original && zone == ffi::PyDateTime_DATE_GET_TZINFO(right) {
                        let a = &(*(left as *const ffi::PyDateTime_DateTime)).data;
                        let b = &(*(right as *const ffi::PyDateTime_DateTime)).data;
                        // Equality needs only two native loads; a full lexical
                        // compare may call memcmp even for this fixed size.
                        if matches!(operation, ffi::Py_EQ | ffi::Py_NE) {
                            let equal = if a == b {
                                let tail =
                                    (access.getter)(right, access.closure as *mut std::ffi::c_void);
                                if tail.is_null() {
                                    return comparison_failed(operation, "other.nanosecond");
                                }
                                let zero = tail == access.zero.as_ptr();
                                ffi::Py_DECREF(tail);
                                zero
                            } else {
                                false
                            };
                            return ffi::Py_NewRef(if equal == (operation == ffi::Py_EQ) {
                                ffi::Py_True()
                            } else {
                                ffi::Py_False()
                            });
                        }
                        let mut ordering = field_order(a, b);
                        if ordering.is_eq() {
                            // Invoke pandas' own property getter instead of
                            // guessing any private pandas field offset. Its
                            // validated integer zero is retained by the cache.
                            let tail =
                                (access.getter)(right, access.closure as *mut std::ffi::c_void);
                            if tail.is_null() {
                                return comparison_failed(operation, "other.nanosecond");
                            }
                            if tail != access.zero.as_ptr() {
                                ordering = std::cmp::Ordering::Less;
                            }
                            ffi::Py_DECREF(tail);
                        }
                        let answer = match operation {
                            ffi::Py_EQ => ordering.is_eq(),
                            ffi::Py_NE => !ordering.is_eq(),
                            ffi::Py_LT => ordering.is_lt(),
                            ffi::Py_LE => !ordering.is_gt(),
                            ffi::Py_GT => ordering.is_gt(),
                            ffi::Py_GE => !ordering.is_lt(),
                            _ => false,
                        };
                        return ffi::Py_NewRef(if answer {
                            ffi::Py_True()
                        } else {
                            ffi::Py_False()
                        });
                    }
                }
            }
        } else if ffi::PyDateTime_Check(right) != 0
            && let Some(standard) = COMPARE.get().copied()
        {
            // A normal datetime subclass inheriting the original native
            // comparator has no foreign precision to inspect. Its Python
            // subclass hooks still get CPython's normal dispatch priority.
            if (*kind)
                .tp_richcompare
                .is_some_and(|slot| std::ptr::fn_addr_eq(slot, standard))
            {
                if let Some(answer) = same_zone_compare(left, right, operation) {
                    return answer;
                }
                return call_standard(left, right, operation, standard);
            }
            return compare_foreign(left, right, operation, standard);
        }
        if let Some(standard) = COMPARE.get().copied() {
            // A cached Timestamp with a wide carrier still needs true ticks.
            if kind == TIMESTAMP.load(Ordering::Relaxed) {
                return compare_foreign(left, right, operation, standard);
            }
            return call_standard(left, right, operation, standard);
        }
        let py = Python::assume_attached();
        crate::error_context::runtime("datetime comparison is not initialized").restore(py);
        std::ptr::null_mut()
    }
}

/// Prove when the native datetime difference already retains all precision.
#[inline]
fn native_span_equivalent(
    left: &Bound<'_, PyDateTime>,
    right: &Bound<'_, PyDateTime>,
) -> PyResult<bool> {
    let py = left.py();
    // SAFETY: the arguments have real datetime layout; the exact cached
    // Timestamp type and owned native descriptor prove the getter receiver.
    let answer = unsafe {
        if ffi::Py_TYPE(right.as_ptr()) == TIMESTAMP.load(Ordering::Relaxed)
            && !matches!(right.get_year(), 1970 | 1972)
            && ffi::PyDateTime_DATE_GET_TZINFO(left.as_ptr())
                == ffi::PyDateTime_DATE_GET_TZINFO(right.as_ptr())
        {
            if let Some(Some(access)) = TIMESTAMP_ACCESS.get(py) {
                let tail = Bound::<PyAny>::from_owned_ptr_or_err(
                    py,
                    (access.getter)(right.as_ptr(), access.closure as *mut std::ffi::c_void),
                )?;
                tail.as_ptr() == access.zero.as_ptr()
            } else {
                false
            }
        } else {
            false
        }
    };
    Ok(answer)
}

/// Call datetime's unchanged subtraction slot with proven native operands.
#[inline]
fn standard_sub<'py>(
    left: &Bound<'py, PyDateTime>,
    right: &Bound<'py, PyDateTime>,
) -> PyResult<Bound<'py, PyAny>> {
    let standard = SUBTRACT
        .get()
        .ok_or_else(|| crate::error_context::runtime("datetime subtraction is not initialized"))?;
    // SAFETY: the typed operands have datetime layout. The slot retains its
    // standard reference and exception convention.
    unsafe { Bound::from_owned_ptr_or_err(left.py(), standard(left.as_ptr(), right.as_ptr())) }
        .map_err(crate::error_context::external)
}

/// Subtract datetimes without narrowing a Timestamp to its base-class carrier.
#[pyfunction]
pub(crate) fn _pydt_datetime_sub<'py>(
    left: &Bound<'py, PyDateTime>,
    right: &Bound<'py, PyDateTime>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = left.py();
    if native_span_equivalent(left, right)? {
        return standard_sub(left, right);
    }
    if !right.is_exact_instance_of::<PyDateTime>() && !crate::pydt::is_exact(right) {
        crate::interop::reject_nat(right, "Pydt.__sub__", "other")?;
        if crate::interop::is_timestamp(right)? {
            cache_timestamp_type(py);
            prepare_timestamp_access(right)?;
            if native_span_equivalent(left, right)? {
                return standard_sub(left, right);
            }
            // Same-timezone subtraction follows datetime's wall-clock rule;
            // keep the Timestamp tail through the final duration rounding.
            // SAFETY: both operands are typed, live datetime values.
            let wall_clock = unsafe {
                ffi::PyDateTime_DATE_GET_TZINFO(left.as_ptr())
                    == ffi::PyDateTime_DATE_GET_TZINFO(right.as_ptr())
            };
            let (left, left_aware) = ticks(left, wall_clock)?;
            let (right, right_aware) = ticks(right, wall_clock)?;
            if left_aware != right_aware {
                return Err(crate::error_context::type_error(
                    "cannot subtract offset-naive and offset-aware dates",
                ));
            }
            let span = left
                .checked_sub(right)
                .ok_or_else(|| crate::error_context::overflow("date difference overflow"))?;
            return crate::interop::span_from_nanoseconds(py, span).map(Bound::into_any);
        }
    }
    standard_sub(left, right)
}

/// Install a storage-free datetime base through CPython's public type-spec API.
///
/// The native comparison and original hash descriptors are inherited by the Python
/// Pydt class, so subclass overrides use normal CPython special-method dispatch.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    let datetime = py.get_type::<PyDateTime>();
    // SAFETY: datetime is ready and owns these slots for the process lifetime.
    // Each slot ID fixes its C signature; the pointers are non-null on datetime.
    let (comparison, subtraction, hash) = unsafe {
        (
            ffi::PyType_GetSlot(datetime.as_type_ptr(), ffi::Py_tp_richcompare),
            ffi::PyType_GetSlot(datetime.as_type_ptr(), ffi::Py_nb_subtract),
            ffi::PyType_GetSlot(datetime.as_type_ptr(), ffi::Py_tp_hash),
        )
    };
    if comparison.is_null() || subtraction.is_null() || hash.is_null() {
        return Err(crate::error_context::runtime(
            "datetime protocol slots are unavailable",
        ));
    }
    // SAFETY: signatures follow the checked slot IDs above. No instance pointer
    // or interpreter-owned object is stored in these process-global functions.
    let _ = COMPARE
        .set(unsafe { std::mem::transmute::<*mut std::ffi::c_void, ffi::richcmpfunc>(comparison) });
    let _ = SUBTRACT
        .set(unsafe { std::mem::transmute::<*mut std::ffi::c_void, ffi::binaryfunc>(subtraction) });
    let mut slots = [
        ffi::PyType_Slot {
            slot: ffi::Py_tp_richcompare,
            pfunc: compare as *mut std::ffi::c_void,
        },
        ffi::PyType_Slot {
            slot: ffi::Py_tp_hash,
            pfunc: hash,
        },
        ffi::PyType_Slot {
            slot: 0,
            pfunc: std::ptr::null_mut(),
        },
    ];
    let mut spec = ffi::PyType_Spec {
        name: c"rstimes._native._PydtBase".as_ptr(),
        basicsize: 0,
        itemsize: 0,
        flags: (ffi::Py_TPFLAGS_DEFAULT | ffi::Py_TPFLAGS_BASETYPE) as u32,
        slots: slots.as_mut_ptr(),
    };
    let bases = PyTuple::new(py, [datetime])?;
    // SAFETY: zero basicsize inherits datetime's storage unchanged. CPython
    // copies the spec/slots and owns the returned type; bases remain live here.
    let class = unsafe {
        Bound::<PyAny>::from_owned_ptr_or_err(
            py,
            ffi::PyType_FromSpecWithBases(&mut spec, bases.as_ptr()),
        )?
    };
    module.add("_PydtBase", class)?;
    module.add_function(wrap_pyfunction!(_pydt_datetime_sub, module)?)?;
    Ok(())
}
