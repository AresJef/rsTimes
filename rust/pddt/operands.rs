//! Once-read real temporal operands, kept native until one final result container.
use super::arguments::Column;
use super::common::{NS_DAY, pack};
use crate::delta::Delta;
use crate::epoch::{Options, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDate, PyDelta, PyDeltaAccess, PyDict};

#[derive(Clone, Copy)]
pub(super) enum Value {
    Delta([i64; 15]),
    Span(i128),
    Date(i128, bool),
    Missing(u8),
}
#[pyclass(frozen, name = "_PddtOperand")]
pub(super) struct Operand {
    values: Column<Value>,
    kind: u8,
    unit: Unit,
    date_domain: Option<bool>,
    callbacks: Vec<(usize, Py<PyAny>, &'static str)>,
}
#[pymethods]
impl Operand {
    #[getter]
    fn date(&self) -> bool {
        self.kind == 3
    }
}
impl Operand {
    fn get(&self, i: usize) -> &Value {
        match &self.values {
            Column::Scalar(v) => v,
            Column::Values(v) => &v[i],
        }
    }
}
fn kind(v: &Value) -> u8 {
    match v {
        Value::Delta(_) => 1,
        Value::Span(_) => 2,
        Value::Date(_, _) => 3,
        Value::Missing(kind) => *kind,
    }
}
pub(super) fn numpy_code(name: &str) -> PyResult<i32> {
    match name {
        "Y" => Ok(0),
        "M" => Ok(1),
        "W" => Ok(2),
        "D" => Ok(4),
        "h" => Ok(5),
        "m" => Ok(6),
        "s" => Ok(7),
        "ms" => Ok(8),
        "us" => Ok(9),
        "ns" => Ok(10),
        _ => Err(crate::error_context::type_error(
            "unsupported native temporal unit",
        )),
    }
}
fn span(ticks: i64, code: i32, multiplier: i32) -> PyResult<Value> {
    if multiplier < 1 {
        return Err(crate::error_context::value_error(
            "invalid temporal unit multiplier",
        ));
    }
    let scale = match code {
        2 => 7 * NS_DAY,
        4 => NS_DAY,
        5 => 3_600_000_000_000,
        6 => 60_000_000_000,
        7 => 1_000_000_000,
        8 => 1_000_000,
        9 => 1000,
        10 => 1,
        _ => {
            return Err(crate::error_context::type_error(
                "fixed durations support W, D, h, m, s, ms, us and ns",
            ));
        }
    };
    if ticks == i64::MIN {
        return Ok(Value::Missing(2));
    }
    i128::from(ticks)
        .checked_mul(i128::from(multiplier))
        .and_then(|v| v.checked_mul(scale))
        .map(Value::Span)
        .ok_or_else(|| crate::error_context::overflow("duration exceeds native range"))
}
fn read(value: &Bound<'_, PyAny>, unit: &mut Unit) -> PyResult<Option<Value>> {
    if super::prepare::missing(value) {
        return Ok(Some(Value::Missing(0)));
    }
    if let Ok(delta) = value.cast::<Delta>() {
        return Ok(Some(Value::Delta(delta.get().snapshot())));
    }
    if let Ok(delta) = value.cast::<PyDelta>() {
        let ns = if let Some(v) = crate::interop::duration_nanoseconds(value)? {
            v
        } else {
            (i128::from(delta.get_days()) * 86400 + i128::from(delta.get_seconds())) * 1_000_000_000
                + i128::from(delta.get_microseconds()) * 1000
        };
        return Ok(Some(Value::Span(ns)));
    }
    if let Some((ticks, code, multiplier)) = crate::numpy_scalar::duration_ticks(value)? {
        return span(ticks, code, multiplier).map(Some);
    }
    if let Some((ticks, code, multiplier)) = crate::numpy_scalar::datetime_ticks(value)? {
        *unit = (*unit).max(super::prepare::scalar_unit(code)?);
        if ticks == i64::MIN {
            return Ok(Some(Value::Missing(3)));
        }
        let parsed = crate::epoch::numpy_ticks(ticks, code, multiplier)?;
        return Ok(Some(Value::Date(parsed.nanos, false)));
    }
    if value.is_instance_of::<PyDate>() {
        let opts = Options {
            default: None,
            yearfirst: None,
            dayfirst: None,
            ignoretz: false,
            isoformat: true,
            strict: false,
            iso_only: false,
            cfg: None,
            input_unit: Unit::Second,
        };
        let parsed = crate::epoch::read(value, &opts)?;
        *unit = (*unit).max(parsed.unit);
        return Ok(Some(Value::Date(
            parsed.nanos,
            !matches!(parsed.zone, Zone::Naive),
        )));
    }
    Ok(None)
}
fn overridden(
    value: &Bound<'_, PyAny>,
    base: &Bound<'_, pyo3::types::PyType>,
    subtract: bool,
) -> PyResult<bool> {
    overrides_method(value, base, if subtract { "__rsub__" } else { "__radd__" })
}

fn overrides_method(
    value: &Bound<'_, PyAny>,
    base: &Bound<'_, pyo3::types::PyType>,
    name: &str,
) -> PyResult<bool> {
    if value.get_type().is(base) {
        return Ok(false);
    }
    let own = crate::protocol::method_definition(&value.get_type(), name)?;
    let base = crate::protocol::method_definition(base, name)?;
    Ok(match (own, base) {
        (Some(a), Some(b)) => !a.is(&b),
        (None, None) => false,
        _ => true,
    })
}

fn column_callback(
    value: &Bound<'_, PyAny>,
    parsed: &Value,
    subtract: bool,
    reflected: bool,
    bases: &(
        Bound<'_, pyo3::types::PyType>,
        Bound<'_, pyo3::types::PyType>,
        Option<Bound<'_, pyo3::types::PyType>>,
    ),
) -> PyResult<Option<&'static str>> {
    // SAFETY: actual and base types are ready and retained under the GIL. A
    // genuine inherited C arithmetic slot proves no Python override needs
    // dispatch. Slot changes are observed afresh, not cached by class name.
    let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
    if actual == bases.0.as_type_ptr() || actual == bases.1.as_type_ptr() {
        return Ok(None);
    }
    let name = if reflected {
        "__add__"
    } else if subtract {
        "__rsub__"
    } else {
        "__radd__"
    };
    let base = match parsed {
        Value::Delta(_) => &bases.0,
        Value::Span(_) if value.is_instance_of::<PyDelta>() => {
            if inherits_stdlib_span_slot(actual, bases.1.as_type_ptr(), subtract) {
                return Ok(None);
            }
            match &bases.2 {
                Some(base) if value.get_type().is_subclass(base)? => base,
                _ => &bases.1,
            }
        }
        _ => return Ok(None),
    };
    // A third-party base may itself use CPython's generic numeric slot. Its
    // subclasses can share that address while overriding the actual methods.
    // Only the known stdlib timedelta C slot above proves native inheritance.
    Ok(overrides_method(value, base, name)?.then_some(name))
}

fn inherits_stdlib_span_slot(
    actual: *mut pyo3::ffi::PyTypeObject,
    base: *mut pyo3::ffi::PyTypeObject,
    subtract: bool,
) -> bool {
    // SAFETY: callers retain both ready types. Number tables may be absent;
    // function addresses are inspected only, never called with guessed layout.
    unsafe {
        let a = (*actual).tp_as_number;
        let b = (*base).tp_as_number;
        if a.is_null() || b.is_null() {
            return false;
        }
        let left = if subtract {
            (*a).nb_subtract
        } else {
            (*a).nb_add
        };
        let right = if subtract {
            (*b).nb_subtract
        } else {
            (*b).nb_add
        };
        left.is_some() && left.map(|f| f as usize) == right.map(|f| f as usize)
    }
}

/// A per-call eligibility cache is valid only while CPython's live type version
/// remains nonzero and unchanged. Standard descriptors can populate that version
/// without invoking user code; custom metaclasses/descriptors stay uncached.
fn protocol_version(value: &Bound<'_, PyAny>, name: &str) -> PyResult<u32> {
    let actual = value.get_type();
    // SAFETY: the owned ready type remains live and attached throughout lookup.
    let mut version = unsafe { (*actual.as_type_ptr()).tp_version_tag };
    if version == 0
        && unsafe { pyo3::ffi::Py_TYPE(actual.as_ptr()) }
            == std::ptr::addr_of_mut!(pyo3::ffi::PyType_Type)
    {
        if let Some(definition) = crate::protocol::method_definition(&actual, name)? {
            let kind = unsafe { pyo3::ffi::Py_TYPE(definition.as_ptr()) };
            if kind == std::ptr::addr_of_mut!(pyo3::ffi::PyMethodDescr_Type)
                || kind == std::ptr::addr_of_mut!(pyo3::ffi::PyWrapperDescr_Type)
                || unsafe { pyo3::ffi::PyFunction_Check(definition.as_ptr()) != 0 }
            {
                // Exact type's attribute machinery and these exact descriptor
                // types perform no Python callback. A live class edit clears
                // its version before the following input item can be read.
                let _ = actual
                    .getattr(name)
                    .map_err(crate::error_context::external)?;
                version = unsafe { (*actual.as_type_ptr()).tp_version_tag };
            }
        }
    }
    Ok(version)
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One operand preparation boundary over optional native temporal storage"
)]
#[pyo3(signature=(data,column,length,entry,subtract=false,reflected=false,buffer=None,storage=None,source=None,multiplier=1,source_zone=None))]
fn _pddt_operand(
    data: &Bound<'_, PyAny>,
    column: bool,
    length: usize,
    entry: &str,
    subtract: bool,
    reflected: bool,
    buffer: Option<&[u8]>,
    storage: Option<&str>,
    source: Option<&str>,
    multiplier: i32,
    source_zone: Option<&Bound<'_, PyAny>>,
) -> PyResult<Option<Operand>> {
    let py = data.py();
    let mut unit = Unit::Second;
    if let Some(bytes) = buffer {
        if bytes.len() % 8 != 0 {
            return Err(crate::error_context::runtime("invalid operand buffer"));
        }
        if bytes.len() / 8 != length {
            return Err(crate::error_context::value_error(
                "operand column length must equal source length",
            ));
        }
        let code = numpy_code(source.unwrap_or(""))?;
        unit = super::prepare::scalar_unit(code)?;
        let mut values = Vec::with_capacity(length);
        for (i, bytes) in bytes.chunks_exact(8).enumerate() {
            let raw: [u8; 8] = bytes
                .try_into()
                .map_err(|_| crate::error_context::runtime("invalid temporal operand tick"))?;
            let ticks = i64::from_ne_bytes(raw);
            let value = if storage == Some("M") {
                if ticks == i64::MIN {
                    Value::Missing(3)
                } else {
                    Value::Date(
                        crate::epoch::numpy_ticks(ticks, code, multiplier)?.nanos,
                        source_zone.is_some_and(|v| !v.is_none()),
                    )
                }
            } else {
                span(ticks, code, multiplier).map_err(|e| {
                    crate::error_context::location(py, e, entry, &format!("other[{i}]"))
                })?
            };
            values.push(value);
        }
        return Ok(Some(Operand {
            values: Column::Values(values),
            kind: if storage == Some("M") { 3 } else { 2 },
            unit,
            date_domain: if storage == Some("M") {
                Some(source_zone.is_some_and(|v| !v.is_none()))
            } else {
                None
            },
            callbacks: Vec::new(),
        }));
    }
    if !column {
        if data.is_none() {
            return Ok(None);
        }
        if let Some(value) = read(data, &mut unit)? {
            if matches!(value, Value::Delta(_))
                && !reflected
                && overridden(data, &py.get_type::<Delta>(), subtract)?
            {
                return Ok(None);
            }
            if matches!(value, Value::Span(_)) && !reflected {
                let base = if let Some(base) = crate::interop::timedelta_type(py) {
                    if data.get_type().is_subclass(&base)? {
                        base
                    } else {
                        py.get_type::<PyDelta>()
                    }
                } else {
                    py.get_type::<PyDelta>()
                };
                if data.is_instance_of::<PyDelta>() && overridden(data, &base, subtract)? {
                    return Ok(None);
                }
            }
            let kind = if matches!(value, Value::Missing(0)) {
                if subtract { 3 } else { 2 }
            } else {
                kind(&value)
            };
            return Ok(Some(Operand {
                values: Column::Scalar(value),
                kind,
                unit,
                date_domain: if let Value::Date(_, aware) = value {
                    Some(aware)
                } else {
                    None
                },
                callbacks: Vec::new(),
            }));
        }
        if data.is_instance_of::<pyo3::types::PyString>()
            || data.is_instance_of::<pyo3::types::PyBytes>()
            || data.is_instance_of::<pyo3::types::PyByteArray>()
        {
            return Ok(None);
        }
        // Only iterables enter a row path; scalar unsupported operands retain
        // normal Python/pandas NotImplemented negotiation.
        if !data
            .hasattr("__iter__")
            .map_err(crate::error_context::external)?
        {
            return Ok(None);
        }
    }
    let iterator = data.try_iter().map_err(crate::error_context::external)?;
    let mut values = Vec::with_capacity(length);
    let mut selected = 0;
    let mut callbacks = Vec::new();
    let bases = (
        py.get_type::<Delta>(),
        py.get_type::<PyDelta>(),
        crate::interop::timedelta_type(py),
    );
    let mut previous: Option<(Py<pyo3::types::PyType>, u32, Option<&'static str>)> = None;
    for (i, value) in iterator.enumerate() {
        let value = value
            .map_err(crate::error_context::external)
            .map_err(|e| crate::error_context::item(py, e, entry, "other", i, None, true))?;
        if i == length {
            return Err(crate::error_context::value_error(
                "operand collection is longer than source dates",
            ));
        }
        let parsed=read(&value,&mut unit).map_err(|e|crate::error_context::item(py,e,entry,"other",i,Some(&value),false))?
            .ok_or_else(||crate::error_context::item(py,crate::error_context::type_error("requires actual Delta, fixed-duration or date values; strings and numeric guesses are not arithmetic operands"),entry,"other",i,Some(&value),false))?;
        let kind = kind(&parsed);
        let actual = unsafe { pyo3::ffi::Py_TYPE(value.as_ptr()) };
        let callback = if actual == bases.0.as_type_ptr()
            || actual == bases.1.as_type_ptr()
            || bases
                .2
                .as_ref()
                .is_some_and(|base| actual == base.as_type_ptr())
        {
            None
        } else {
            let version = unsafe { (*actual).tp_version_tag };
            if let Some((class, cached_version, decision)) = &previous
                && version != 0
                && version == *cached_version
                && class.as_ptr() == actual.cast()
            {
                *decision
            } else {
                let decision = column_callback(&value, &parsed, subtract, reflected, &bases)?;
                let name = if reflected {
                    "__add__"
                } else if subtract {
                    "__rsub__"
                } else {
                    "__radd__"
                };
                let version = protocol_version(&value, name)?;
                previous = Some((value.get_type().unbind(), version, decision));
                decision
            }
        };
        if let Some(name) = callback {
            callbacks.push((i, value.clone().unbind(), name));
        }
        if kind != 0 {
            if selected != 0 && selected != kind {
                return Err(crate::error_context::type_error(
                    "do not mix date, duration and Delta values in one arithmetic operand column",
                ));
            }
            selected = kind;
        }
        values.push(parsed);
    }
    if values.len() != length {
        return Err(crate::error_context::value_error(
            "operand collection length must equal source dates",
        ));
    }
    if selected == 0 {
        if !subtract {
            return Err(crate::error_context::type_error(
                "an arithmetic increment column cannot consist only of missing values; use Delta() for no calendar adjustment",
            ));
        }
        selected = 3;
    }
    if selected == 1 && values.iter().any(|v| matches!(v, Value::Missing(_))) {
        return Err(crate::error_context::type_error(
            "Delta increments cannot be missing; use Delta() for no adjustment",
        ));
    }
    Ok(Some(Operand {
        values: Column::Values(values),
        kind: selected,
        unit,
        date_domain: None,
        callbacks,
    }))
}

type Output<'py> = (Bound<'py, PyBytes>, &'static str, bool, bool);

#[pyfunction]
fn _pddt_binary<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    operand: PyRef<'_, Operand>,
    subtract: bool,
    entry: &str,
) -> PyResult<Output<'py>> {
    if operand.callbacks.is_empty() {
        binary::<false>(py, data, unit, zone, &operand, subtract, entry)
    } else {
        binary::<true>(py, data, unit, zone, &operand, subtract, entry)
    }
}

/// Only a genuinely overridden row needs a scalar; ordinary loops stay native.
fn callback_date(
    py: Python<'_>,
    callback: &(usize, Py<PyAny>, &'static str),
    ticks: i64,
    unit: Unit,
    zone: Option<&Bound<'_, PyAny>>,
) -> PyResult<Option<Option<i128>>> {
    let kwargs = PyDict::new(py);
    kwargs.set_item("unit", unit.name())?;
    if let Some(zone) = zone {
        kwargs.set_item("tz", zone)?;
    }
    let date = crate::interop::timestamp_class(py)?
        .call((ticks,), Some(&kwargs))
        .map_err(crate::error_context::external)?;
    let result = crate::protocol::call_special(callback.1.bind(py), callback.2, &date)?;
    if result.is(py.NotImplemented()) {
        if callback.2 == "__add__" {
            // The forward method declined: the existing reflected native
            // Pddt path may still accept the actual duration/Delta value.
            return Ok(None);
        }
        return Err(crate::error_context::type_error(
            "the operand's reflected arithmetic returned NotImplemented",
        ));
    }
    let mut result_unit = unit;
    match read(&result, &mut result_unit)? {
        Some(Value::Date(ns, aware)) if aware == zone.is_some() => Ok(Some(Some(ns))),
        Some(Value::Missing(_)) => Ok(Some(None)),
        Some(Value::Date(_, _)) => Err(crate::error_context::type_error(
            "arithmetic result and source must have matching timezone awareness",
        )),
        _ => Err(crate::error_context::type_error(
            "an arithmetic operand callback must return a date value",
        )),
    }
}

fn binary<'py, const DYNAMIC: bool>(
    py: Python<'py>,
    data: &[u8],
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    operand: &Operand,
    subtract: bool,
    entry: &str,
) -> PyResult<Output<'py>> {
    if data.len() % 8 != 0 {
        return Err(crate::error_context::runtime("invalid date source buffer"));
    }
    if operand.kind == 3 && !subtract {
        return Err(crate::error_context::type_error(
            "adding two dates has no date meaning",
        ));
    }
    let unit = Unit::parse(unit)?;
    let selected = if operand.kind == 3 {
        unit.max(operand.unit)
    } else {
        unit
    };
    let zone = zone.filter(|v| !v.is_none());
    if operand.kind == 3
        && operand
            .date_domain
            .is_some_and(|aware| aware != zone.is_some())
    {
        return Err(crate::error_context::type_error(
            "cannot subtract timezone-aware and timezone-naive date domains",
        ));
    }
    let fixed = if operand.kind == 1 {
        super::common::fixed_offset(
            py,
            &zone.map_or(Zone::Naive, |v| Zone::Object(v.clone().unbind())),
        )?
    } else {
        Some(0)
    };
    let count = data.len() / 8;
    if operand.values.len().is_some_and(|n| n != count) {
        return Err(crate::error_context::value_error(
            "operand length must equal source dates",
        ));
    }
    let mut out = Vec::with_capacity(count);
    let mut changed = selected != unit;
    let sign = if subtract { -1 } else { 1 };
    let mut callbacks = operand.callbacks.iter().peekable();
    for (i, bytes) in data.chunks_exact(8).enumerate() {
        let raw: [u8; 8] = bytes
            .try_into()
            .map_err(|_| crate::error_context::runtime("invalid date tick"))?;
        let ticks = i64::from_ne_bytes(raw);
        let other = operand.get(i);
        let callback = if DYNAMIC && callbacks.peek().is_some_and(|v| v.0 == i) {
            callbacks.next()
        } else {
            None
        };
        if let Value::Date(_, aware) = other {
            if *aware != zone.is_some() {
                return Err(crate::error_context::location(
                    py,
                    crate::error_context::type_error(
                        "cannot subtract timezone-aware and timezone-naive dates",
                    ),
                    entry,
                    &format!("other[{i}]"),
                ));
            }
        }
        if ticks == i64::MIN || matches!(other, Value::Missing(_)) {
            changed |= ticks != i64::MIN;
            out.push(None);
            continue;
        }
        let source = i128::from(ticks) * unit.nanos();
        if let Some(callback) = callback {
            if let Some(result) = callback_date(py, callback, ticks, unit, zone)
                .map_err(|e| crate::error_context::location(py, e, entry, &format!("other[{i}]")))?
            {
                changed |= result != Some(source);
                out.push(result);
                continue;
            }
        }
        let value = (|| -> PyResult<i128> {
            match other {
                Value::Span(value) => source
                    .checked_add(*value * sign)
                    .ok_or_else(|| crate::error_context::overflow("duration addition overflow")),
                Value::Date(value, aware) => {
                    if *aware != zone.is_some() {
                        return Err(crate::error_context::type_error(
                            "cannot subtract timezone-aware and timezone-naive dates",
                        ));
                    }
                    source
                        .checked_sub(*value)
                        .ok_or_else(|| crate::error_context::overflow("date difference overflow"))
                }
                Value::Delta(fields) => {
                    let wall = if let Some(offset) = fixed {
                        source + i128::from(offset) * 1000
                    } else {
                        super::zones::utc_wall(
                            source,
                            zone.ok_or_else(|| {
                                crate::error_context::runtime("missing source region")
                            })?,
                            None,
                        )?
                    };
                    let input = super::operations::fields(wall)?;
                    let f = [
                        input[0], input[1], input[2], input[3], input[4], input[5], input[6],
                    ];
                    let (changed, _) = crate::calendar::apply(fields, f, sign as i64, true)
                        .map_err(crate::error_context::overflow)?;
                    let tail = if fields[14] >= 0 { 0 } else { input[7] };
                    let changed = super::operations::nanos([
                        changed[0], changed[1], changed[2], changed[3], changed[4], changed[5],
                        changed[6], tail,
                    ])?;
                    if changed == wall {
                        return Ok(source);
                    }
                    if let Some(offset) = fixed {
                        Ok(changed - i128::from(offset) * 1000)
                    } else {
                        super::operations::automatic(
                            changed,
                            source,
                            wall,
                            zone.ok_or_else(|| {
                                crate::error_context::runtime("missing source region")
                            })?,
                        )
                    }
                }
                Value::Missing(_) => {
                    Err(crate::error_context::runtime("missing arithmetic operand"))
                }
            }
        })()
        .map_err(|e| crate::error_context::location(py, e, entry, &format!("result[{i}]")))?;
        changed |= value != source;
        out.push(Some(value));
    }
    let packed = pack(py, &out, selected, true, entry)?;
    Ok((packed, selected.name(), operand.kind == 3, changed))
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_operand, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_binary, module)?)
}
