//! Once-read real temporal operands, kept native until one final result container.
use super::arguments::Column;
use super::common::{NS_DAY, pack};
use crate::delta::Delta;
use crate::epoch::{Unit, Zone};
pub(super) use crate::temporal_operand::numpy_code;
use crate::temporal_operand::{Value, column_callback, overridden, protocol_version, read, span};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDelta, PyDict};

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

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One operand preparation boundary over optional native temporal storage"
)]
#[pyo3(signature=(data,column,length,entry,subtract=false,reflected=false,buffer=None,storage=None,source=None,multiplier=1,source_zone=None,mask=None))]
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
    mask: Option<&[u8]>,
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
        let validity = super::validity::TemporalValidity::new(mask, length)?;
        let code = numpy_code(source.unwrap_or(""))?;
        unit = super::prepare::scalar_unit(code)?;
        let mut values = Vec::with_capacity(length);
        for (i, bytes) in bytes.as_chunks::<8>().0.iter().enumerate() {
            let raw: [u8; 8] = *bytes;
            let ticks = i64::from_ne_bytes(raw);
            let value = if storage == Some("M") {
                if validity.missing(i, ticks) {
                    Value::Missing(3)
                } else {
                    Value::Date(
                        crate::epoch::native_datetime_ticks(ticks, code, multiplier)?.nanos,
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

/// A scalar whole-hour calendar shift preserves every finer source tick.
/// Fixed offsets cancel in the final difference, including fractional seconds.
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared scalar calendar data and fixed-offset output boundary, without a new mode structure"
)]
fn fixed_hours<'py>(
    py: Python<'py>,
    data: &[u8],
    unit: Unit,
    offset: i64,
    fields: &crate::delta::value::DeltaValue,
    hours: i64,
    sign: i64,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, bool)> {
    let mut changed = false;
    let result = PyBytes::new_with(py, data.len(), |output| {
        for (i, (input, out)) in data
            .as_chunks::<8>()
            .0
            .iter()
            .zip(output.as_chunks_mut::<8>().0.iter_mut())
            .enumerate()
        {
            let tick = i64::from_ne_bytes(*input);
            let value = if tick == i64::MIN {
                tick
            } else {
                (|| {
                    let wall = i128::from(tick) * unit.nanos() + i128::from(offset) * 1000;
                    let source_day = wall.div_euclid(NS_DAY);
                    let ordinal = i64::try_from(source_day + 719_163)
                        .map_err(|_| crate::error_context::overflow("calendar day overflow"))?;
                    let date = crate::calendar::from_ordinal(ordinal)
                        .map_err(crate::error_context::overflow)?;
                    let hour = (wall.rem_euclid(NS_DAY) / 3_600_000_000_000) as i64;
                    let (output, _) = crate::calendar::apply_hours(
                        fields,
                        [date[0], date[1], date[2], hour, 0, 0, 0],
                        sign,
                        true,
                        hours,
                    )
                    .map_err(crate::error_context::overflow)?;
                    let day = crate::civil::ordinal(
                        i128::from(output[0]),
                        output[1] as u8,
                        output[2] as u8,
                    )
                    .map_err(crate::error_context::overflow)? - 719_163;
                    let movement = ((day - source_day) * 24 + i128::from(output[3] - hour))
                        .checked_mul(3_600_000_000_000 / unit.nanos())
                        .and_then(|delta| i128::from(tick).checked_add(delta));
                    movement
                        .and_then(|value| i64::try_from(value).ok())
                        .filter(|value| *value != i64::MIN)
                        .ok_or_else(|| {
                            crate::error_context::overflow(
                                "date is outside the requested unit; explicitly choose a coarser unit",
                            )
                        })
                })()
                .map_err(|e| {
                    crate::error_context::location(py, e, entry, &format!("result[{i}]"))
                })?
            };
            changed |= value != tick;
            out.copy_from_slice(&value.to_ne_bytes());
        }
        Ok(())
    })?;
    Ok((result, changed))
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
    if !data.len().is_multiple_of(8) {
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
    let sign = if subtract { -1 } else { 1 };
    // A scalar's canonical Delta never changes across rows. Per-row operands
    // and real callback results retain their complete generic path.
    let scalar_hours = match &operand.values {
        Column::Scalar(Value::Delta(value)) => crate::calendar::batch_hours(value),
        _ => None,
    };
    if let (Some(offset), Some(hours), Column::Scalar(Value::Delta(fields))) =
        (fixed, scalar_hours, &operand.values)
        && operand.callbacks.is_empty()
    {
        let (packed, changed) =
            fixed_hours(py, data, unit, offset, fields, hours, sign as i64, entry)?;
        return Ok((packed, unit.name(), false, changed));
    }
    let mut out = Vec::with_capacity(count);
    let mut changed = selected != unit;
    let mut callbacks = operand.callbacks.iter().peekable();
    for (i, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        let raw: [u8; 8] = *bytes;
        let ticks = i64::from_ne_bytes(raw);
        let other = operand.get(i);
        let callback = if DYNAMIC && callbacks.peek().is_some_and(|v| v.0 == i) {
            callbacks.next()
        } else {
            None
        };
        if let Value::Date(_, aware) = other
            && *aware != zone.is_some()
        {
            return Err(crate::error_context::location(
                py,
                crate::error_context::type_error(
                    "cannot subtract timezone-aware and timezone-naive dates",
                ),
                entry,
                &format!("other[{i}]"),
            ));
        }
        if ticks == i64::MIN || matches!(other, Value::Missing(_)) {
            changed |= ticks != i64::MIN;
            out.push(None);
            continue;
        }
        let source = i128::from(ticks) * unit.nanos();
        if let Some(callback) = callback
            && let Some(result) = callback_date(py, callback, ticks, unit, zone)
                .map_err(|e| crate::error_context::location(py, e, entry, &format!("other[{i}]")))?
        {
            changed |= result != Some(source);
            out.push(result);
            continue;
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
                    let civil = if let Some(hours) = scalar_hours {
                        let (output, _) = crate::calendar::apply_hours(
                            fields,
                            [
                                input[0], input[1], input[2], input[3], input[4], input[5],
                                input[6],
                            ],
                            sign as i64,
                            true,
                            hours,
                        )
                        .map_err(crate::error_context::overflow)?;
                        // Whole-hour movement preserves the exact lower clock;
                        // the source nanosecond tail remains independent of the
                        // microsecond-oriented field helper, with no projection.
                        crate::civil::CivilNs {
                            year: i128::from(output[0]),
                            month: output[1] as u8,
                            day: output[2] as u8,
                            clock_ns: ((output[3] * 3600 + output[4] * 60 + output[5])
                                * 1_000_000_000
                                + output[6] * 1000
                                + input[7]) as u64,
                        }
                    } else {
                        let civil = crate::civil::CivilNs {
                            year: i128::from(input[0]),
                            month: input[1] as u8,
                            day: input[2] as u8,
                            clock_ns: ((input[3] * 3600 + input[4] * 60 + input[5]) * 1_000_000_000
                                + input[6] * 1000
                                + input[7]) as u64,
                        };
                        crate::civil::apply(fields, civil, sign as i64)
                            .map_err(crate::error_context::overflow)?
                    };
                    let ordinal = crate::civil::ordinal(civil.year, civil.month, civil.day)
                        .map_err(crate::error_context::overflow)?;
                    let changed = (ordinal - 719_163)
                        .checked_mul(NS_DAY)
                        .and_then(|date| date.checked_add(i128::from(civil.clock_ns)))
                        .ok_or_else(|| {
                            crate::error_context::overflow("date arithmetic overflow")
                        })?;
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
