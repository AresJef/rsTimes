//! Exact Delta, elapsed-duration and date arithmetic with host-only callbacks.
use super::finish::{Failure, Kind};
use crate::delta::Delta;
use crate::delta::value::DeltaValue;
use crate::epoch::Unit;
use crate::temporal_operand::{self, Value};
use crate::temporal_zone::Zone;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDelta};
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::{Deserialize, Serialize};
const DAY: i128 = 86_400_000_000_000;
#[derive(Serialize, Deserialize)]
enum Wire {
    Delta([i64; 17]),
    Span(#[serde(with = "crate::serde_values::signed_128")] i128),
    Date(
        #[serde(with = "crate::serde_values::signed_128")] i128,
        bool,
    ),
    Missing(u8),
}
impl Wire {
    fn native(&self) -> Result<Value, Failure> {
        Ok(match self {
            Self::Delta(value) => Value::Delta(DeltaValue::from_core17(*value).map_err(|_| {
                Failure::new(Kind::Value, "invalid prepared Delta canonical fields")
            })?),
            Self::Span(value) => Value::Span(*value),
            Self::Date(value, aware) => Value::Date(*value, *aware),
            Self::Missing(kind) => Value::Missing(*kind),
        })
    }
    fn from_native(value: Value) -> Self {
        match value {
            Value::Delta(value) => Self::Delta(value.core17()),
            Value::Span(value) => Self::Span(value),
            Value::Date(value, aware) => Self::Date(value, aware),
            Value::Missing(kind) => Self::Missing(kind),
        }
    }
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Data {
    version: u8,
    kind: u8,
    unit: String,
    scalar: bool,
    domain: Option<bool>,
    values: Vec<Wire>,
}
#[pyclass(frozen, skip_from_py_object, name = "_PldtOperand")]
struct Operand {
    data: Data,
    callbacks: Vec<(usize, Py<PyAny>, &'static str)>,
}
#[pymethods]
impl Operand {
    #[getter]
    fn kind(&self) -> u8 {
        self.data.kind
    }
    #[getter]
    fn scalar_dynamic(&self) -> bool {
        self.data.scalar && !self.callbacks.is_empty()
    }
    #[getter]
    fn dynamic(&self) -> bool {
        !self.callbacks.is_empty()
    }
    fn plugin_column(&self) -> PyResult<PySeries> {
        if self.data.scalar || !self.callbacks.is_empty() {
            return Err(crate::error_context::type_error(
                "requires a concrete ordinary Delta collection",
            ));
        }
        let mut output = BinaryChunkedBuilder::new("delta".into(), self.data.values.len());
        for value in &self.data.values {
            let Wire::Delta(fields) = value else {
                return Err(crate::error_context::type_error(
                    "requires nonmissing Delta values",
                ));
            };
            let mut bytes = [0u8; 136];
            for (chunk, value) in bytes.chunks_exact_mut(8).zip(fields) {
                chunk.copy_from_slice(&value.to_le_bytes());
            }
            output.append_value(bytes);
        }
        Ok(PySeries(output.finish().into_series()))
    }
    #[getter]
    fn scalar(&self) -> bool {
        self.data.scalar
    }
    fn plugin_data<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        if !self.callbacks.is_empty() {
            return Err(crate::error_context::type_error(
                "dynamic Python arithmetic is not supported by native Expr; use ordinary Delta values or integer named add/sub",
            ));
        }
        let bytes = serde_json::to_vec(&self.data)
            .map_err(|e| crate::error_context::runtime(e.to_string()))?;
        Ok(PyBytes::new(py, &bytes))
    }
}
fn kind(value: &Value) -> u8 {
    match value {
        Value::Delta(_) => 1,
        Value::Span(_) => 2,
        Value::Date(_, _) => 3,
        Value::Missing(kind) => *kind,
    }
}
fn selected(unit: &str) -> Result<Unit, Failure> {
    match unit {
        "s" => Ok(Unit::Second),
        "ms" => Ok(Unit::Millisecond),
        "us" => Ok(Unit::Microsecond),
        "ns" => Ok(Unit::Nanosecond),
        _ => Err(Failure::new(
            Kind::Value,
            "invalid prepared temporal resolution",
        )),
    }
}
fn prepare(
    data: &Bound<'_, PyAny>,
    column: bool,
    subtract: bool,
    reflected: bool,
    named: bool,
    entry: &str,
) -> PyResult<Option<Operand>> {
    let py = data.py();
    let mut unit = Unit::Second;
    let mut values = Vec::new();
    let mut callbacks = Vec::new();
    let mut selected = 0;
    let bases = (
        py.get_type::<Delta>(),
        py.get_type::<PyDelta>(),
        crate::interop::timedelta_type(py),
    );
    let scalar_value = if !column && !data.is_none() {
        temporal_operand::read(data, &mut unit)?
    } else {
        None
    };
    let scalar = scalar_value.is_some();
    let mut push = |row: usize,
                    item: &Bound<'_, PyAny>,
                    value: Value,
                    scalar: bool|
     -> PyResult<()> {
        let current = kind(&value);
        if current != 0 {
            if selected != 0 && selected != current {
                return Err(crate::error_context::type_error(
                    "do not mix Delta, fixed-duration and date values in one arithmetic collection",
                ));
            }
            selected = current;
        }
        if !(scalar && reflected) {
            if let Some(name) =
                temporal_operand::column_callback(item, &value, subtract, reflected, &bases)?
            {
                callbacks.push((row, item.clone().unbind(), name));
            }
        }
        values.push(Wire::from_native(value));
        Ok(())
    };
    if let Some(value) = scalar_value {
        push(0, data, value, true)?;
    } else {
        if !column
            && (data.is_none()
                || data.is_instance_of::<pyo3::types::PyString>()
                || data.is_instance_of::<pyo3::types::PyBytes>()
                || data.is_instance_of::<pyo3::types::PyByteArray>())
        {
            return Ok(None);
        }
        if !column
            && !data
                .hasattr("__iter__")
                .map_err(crate::error_context::external)?
        {
            return Ok(None);
        }
        for (row, item) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let item = item
                .map_err(crate::error_context::external)
                .map_err(|e| crate::error_context::item(py, e, entry, "other", row, None, true))?;
            let value=temporal_operand::read(&item,&mut unit).map_err(|e|crate::error_context::item(py,e,entry,"other",row,Some(&item),false))?.ok_or_else(||crate::error_context::item(py,crate::error_context::type_error("requires actual Delta, fixed-duration or date values; strings and numeric guesses are not operands"),entry,"other",row,Some(&item),false))?;
            push(row, &item, value, false).map_err(|e| {
                crate::error_context::item(py, e, entry, "other", row, Some(&item), false)
            })?;
        }
    }
    if named && values.iter().any(|value| !matches!(value, Wire::Delta(_))) {
        return Err(crate::error_context::type_error(
            "add_delta/sub_delta require actual nonmissing Delta values",
        ));
    }
    if named {
        selected = 1
    }
    if selected == 0 {
        if scalar {
            selected = if subtract { 3 } else { 2 }
        } else if subtract {
            selected = 3
        } else {
            return Err(crate::error_context::type_error(
                "an increment collection cannot consist only of missing values; use Delta() for no adjustment",
            ));
        }
    }
    if selected == 1 && values.iter().any(|value| matches!(value, Wire::Missing(_))) {
        return Err(crate::error_context::type_error(
            "Delta increments cannot be missing; use Delta()",
        ));
    }
    Ok(Some(Operand {
        data: Data {
            version: 1,
            kind: selected,
            unit: unit.name().into(),
            scalar,
            domain: None,
            values,
        },
        callbacks,
    }))
}
#[pyfunction]
#[pyo3(signature=(data,column,subtract,reflected,named,entry))]
fn _pldt_operand_objects(
    data: &Bound<'_, PyAny>,
    column: bool,
    subtract: bool,
    reflected: bool,
    named: bool,
    entry: &str,
) -> PyResult<Option<Operand>> {
    prepare(data, column, subtract, reflected, named, entry)
}
fn column_values(source: &Series) -> Result<Data, Failure> {
    let (unit, kind, domain) = match source.dtype() {
        DataType::Datetime(unit, zone) => {
            (super::input::epoch_unit(*unit), 3, Some(zone.is_some()))
        }
        DataType::Date => (Unit::Millisecond, 3, Some(false)),
        DataType::Duration(unit) => (super::input::epoch_unit(*unit), 2, None),
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "arithmetic columns require Date/Datetime/Duration or actual Object Delta values",
            ));
        }
    };
    let mut values = Vec::with_capacity(source.len());
    match source.dtype() {
        DataType::Date => {
            for value in source
                .date()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
            {
                values.push(
                    value.map_or(Wire::Missing(3), |v| Wire::Date(i128::from(v) * DAY, false)),
                )
            }
        }
        DataType::Datetime(_, _) => {
            for value in source
                .datetime()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
            {
                values.push(value.map_or(Wire::Missing(3), |v| {
                    Wire::Date(i128::from(v) * unit.nanos(), domain == Some(true))
                }))
            }
        }
        DataType::Duration(_) => {
            for value in source
                .duration()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
            {
                values.push(value.map_or(Wire::Missing(2), |v| {
                    Wire::Span(i128::from(v) * unit.nanos())
                }))
            }
        }
        _ => {
            return Err(Failure::new(
                Kind::Runtime,
                "validated temporal column dtype was lost",
            ));
        }
    }
    Ok(Data {
        version: 1,
        kind,
        unit: unit.name().into(),
        scalar: false,
        domain,
        values,
    })
}
#[pyfunction]
fn _pldt_operand_column(py: Python<'_>, source: PySeries) -> PyResult<Operand> {
    column_values(&source.0)
        .map(|data| Operand {
            data,
            callbacks: Vec::new(),
        })
        .map_err(|e| e.python(py, "Pldt arithmetic"))
}
#[pyfunction]
#[pyo3(signature=(source,storage,code,multiplier,aware,sentinel))]
fn _pldt_operand_ticks(
    source: PySeries,
    storage: &str,
    code: i32,
    multiplier: i32,
    aware: bool,
    sentinel: bool,
) -> PyResult<Operand> {
    let unit = crate::date_input::scalar_unit(code)?;
    let mut values = Vec::with_capacity(source.0.len());
    let kind = if storage == "M" { 3 } else { 2 };
    for value in source.0.i64().map_err(super::eager_error)?.iter() {
        values.push(match value {
            None => Wire::Missing(kind),
            Some(i64::MIN) if sentinel => Wire::Missing(kind),
            Some(value) if kind == 3 => Wire::Date(
                crate::epoch::native_datetime_ticks(value, code, multiplier)?.nanos,
                aware,
            ),
            Some(value) => Wire::from_native(temporal_operand::span(value, code, multiplier)?),
        });
    }
    Ok(Operand {
        data: Data {
            version: 1,
            kind,
            unit: unit.name().into(),
            scalar: false,
            domain: if kind == 3 { Some(aware) } else { None },
            values,
        },
        callbacks: Vec::new(),
    })
}
fn date_meta(source: &DataType) -> Result<(Unit, Option<&TimeZone>), Failure> {
    match source {
        DataType::Datetime(unit, zone) => Ok((super::input::epoch_unit(*unit), zone.as_ref())),
        DataType::Date => Ok((Unit::Millisecond, None)),
        _ => Err(Failure::new(Kind::Type, "requires a Date/Datetime source")),
    }
}
fn result_meta(
    source: &DataType,
    data: &Data,
    subtract: bool,
    return_only: bool,
) -> Result<(Unit, DataType), Failure> {
    if data.version != 1 || !matches!(data.kind, 1..=3) || (data.scalar && data.values.len() != 1) {
        return Err(Failure::new(
            Kind::Runtime,
            "invalid temporal operand preparation",
        ));
    }
    let (unit, zone) = date_meta(source)?;
    if data.kind == 3 {
        if !subtract && !return_only {
            return Err(Failure::new(
                Kind::Type,
                "adding two dates has no date meaning",
            ));
        }
        if data.domain.is_some_and(|aware| aware != zone.is_some()) {
            return Err(Failure::new(
                Kind::Type,
                "date domains must have matching timezone awareness",
            ));
        }
        let chosen = if return_only {
            unit
        } else {
            unit.max(selected(&data.unit)?)
        };
        Ok((
            chosen,
            if return_only {
                DataType::Datetime(super::input::resolution(unit), zone.cloned())
            } else {
                DataType::Duration(super::input::resolution(chosen))
            },
        ))
    } else {
        Ok((
            unit,
            DataType::Datetime(super::input::resolution(unit), zone.cloned()),
        ))
    }
}
fn civil_apply(value: &DeltaValue, wall: i128, sign: i64) -> Result<i128, Failure> {
    let (year, month, day) = crate::civil::from_ordinal(wall.div_euclid(DAY) + 719_163)
        .map_err(|m| Failure::new(Kind::Capacity, m))?;
    let result = crate::civil::apply(
        value,
        crate::civil::CivilNs {
            year,
            month,
            day,
            clock_ns: wall.rem_euclid(DAY) as u64,
        },
        sign,
    )
    .map_err(|m| Failure::new(Kind::Capacity, m))?;
    let ordinal = crate::civil::ordinal(result.year, result.month, result.day)
        .map_err(|m| Failure::new(Kind::Capacity, m))?;
    ordinal
        .checked_sub(719_163)
        .and_then(|value| value.checked_mul(DAY))
        .and_then(|value| value.checked_add(i128::from(result.clock_ns)))
        .ok_or_else(|| Failure::new(Kind::Capacity, "Delta result exceeds native calendar range"))
}
fn one(
    source: i128,
    value: &Value,
    zone: Option<&Zone>,
    subtract: bool,
    return_only: bool,
) -> Result<Option<i128>, Failure> {
    let sign = if subtract { -1 } else { 1 };
    Ok(match value {
        Value::Missing(_) => None,
        Value::Date(value, aware) => {
            if *aware != zone.is_some() {
                return Err(Failure::new(
                    Kind::Type,
                    "date result and source must have matching timezone awareness",
                ));
            }
            Some(if return_only {
                *value
            } else {
                source.checked_sub(*value).ok_or_else(|| {
                    Failure::new(Kind::Capacity, "date difference exceeds native range")
                })?
            })
        }
        Value::Span(value) => Some(
            value
                .checked_mul(i128::from(sign))
                .and_then(|amount| source.checked_add(amount))
                .ok_or_else(|| {
                    Failure::new(
                        Kind::Capacity,
                        "elapsed duration arithmetic exceeds native range",
                    )
                })?,
        ),
        Value::Delta(value) => {
            let wall = zone.map_or(Ok(source), |zone| zone.wall(source))?;
            let changed = civil_apply(value, wall, sign)?;
            Some(if changed == wall {
                source
            } else {
                match zone {
                    None => changed,
                    Some(zone) => {
                        if let Some(offset) = zone.fixed_seconds() {
                            changed - i128::from(offset) * 1_000_000_000
                        } else {
                            super::operations::automatic(changed, source, wall, zone)?
                        }
                    }
                }
            })
        }
    })
}
fn project(value: i128, unit: Unit, row: usize) -> Result<i64, Failure> {
    crate::precision::epoch_tick(value, unit.nanos(), false).map_err(|error| match error {
        crate::precision::TickError::Precision => Failure::new(
            Kind::Value,
            "result precision does not fit the current unit; use as_unit explicitly",
        )
        .at(row),
        crate::precision::TickError::Capacity => Failure::new(
            Kind::Capacity,
            "result exceeds int64 capacity at the chosen unit; use as_unit explicitly",
        )
        .at(row),
    })
}
fn for_source(
    source: &Series,
    mut visit: impl FnMut(usize, Option<i128>) -> Result<(), Failure>,
) -> Result<(), Failure> {
    let (unit, _) = date_meta(source.dtype())?;
    match source.dtype() {
        DataType::Date => {
            for (row, value) in source
                .date()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                visit(row, value.map(|value| i128::from(value) * DAY))?
            }
        }
        _ => {
            for (row, value) in source
                .datetime()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                visit(row, value.map(|value| i128::from(value) * unit.nanos()))?
            }
        }
    }
    Ok(())
}

fn finish(source: &Series, values: Vec<Option<i64>>, dtype: DataType) -> Result<Series, Failure> {
    let physical = Int64Chunked::from_iter_options(source.name().clone(), values.into_iter());
    match dtype {
        DataType::Datetime(unit, zone) => Ok(physical.into_datetime(unit, zone).into_series()),
        DataType::Duration(unit) => Ok(physical.into_duration(unit).into_series()),
        _ => Err(Failure::new(
            Kind::Runtime,
            "invalid native arithmetic result dtype",
        )),
    }
}

fn calculate(
    source: &Series,
    data: &Data,
    subtract: bool,
    return_only: bool,
) -> Result<Series, Failure> {
    let (unit, dtype) = result_meta(source.dtype(), data, subtract, return_only)?;
    if !data.scalar && data.values.len() != source.len() {
        return Err(Failure::new(
            Kind::Value,
            "arithmetic operand collection must equal the complete source length; length-one collections are not scalar",
        ));
    }
    let values = data
        .values
        .iter()
        .map(Wire::native)
        .collect::<Result<Vec<_>, _>>()?;
    let zone = date_meta(source.dtype())?
        .1
        .map(|key| Zone::named(key.as_str()))
        .transpose()
        .map_err(|m| Failure::new(Kind::Value, m))?;
    let mut output = Vec::with_capacity(source.len());
    for_source(source, |row, value| {
        let other = &values[if data.scalar { 0 } else { row }];
        if let Value::Date(_, aware) = other {
            if *aware != zone.is_some() {
                return Err(Failure::new(
                    Kind::Type,
                    "date domains must have matching timezone awareness",
                )
                .at(row));
            }
        }
        output.push(
            value
                .map(|source| one(source, other, zone.as_ref(), subtract, return_only))
                .transpose()?
                .flatten()
                .map(|value| project(value, unit, row))
                .transpose()?,
        );
        Ok(())
    })?;
    finish(source, output, dtype)
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    #[serde(deserialize_with = "crate::serde_values::byte_vector")]
    prepared: Vec<u8>,
    subtract: bool,
    entry: String,
    scalar: bool,
}
fn prepared_delta(kwargs: &Options, source: Option<&Series>) -> Result<Data, Failure> {
    if kwargs.version != 1 {
        return Err(Failure::new(
            Kind::Value,
            "unsupported Delta plugin preparation version",
        ));
    }
    if kwargs.scalar {
        let data: Data = serde_json::from_slice(&kwargs.prepared)
            .map_err(|e| Failure::new(Kind::Value, e.to_string()))?;
        if data.kind != 1 || !data.scalar || data.values.len() != 1 {
            return Err(Failure::new(
                Kind::Value,
                "requires one ordinary Delta snapshot",
            ));
        }
        return Ok(data);
    }
    let mut values = Vec::new();
    if let Some(source) = source {
        let bytes = source.binary().map_err(|_| {
            Failure::new(Kind::Type, "prepared Delta companion requires Binary dtype")
        })?;
        values.reserve(source.len());
        for (row, value) in bytes.iter().enumerate() {
            let value = value.ok_or_else(|| {
                Failure::new(Kind::Type, "Delta increments cannot be missing").at(row)
            })?;
            if value.len() != 136 {
                return Err(
                    Failure::new(Kind::Value, "invalid canonical Delta record length").at(row),
                );
            }
            let mut fields = [0i64; 17];
            for (field, bytes) in fields.iter_mut().zip(value.chunks_exact(8)) {
                *field = i64::from_le_bytes(
                    bytes
                        .try_into()
                        .map_err(|_| Failure::new(Kind::Runtime, "invalid Delta record"))?,
                )
            }
            values.push(Wire::Delta(fields));
        }
    }
    Ok(Data {
        version: 1,
        kind: 1,
        unit: "s".into(),
        scalar: false,
        domain: None,
        values,
    })
}
fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    polars_ensure!(fields.len()==if kwargs.scalar{1}else{2},InvalidOperation:"invalid Delta plugin input count");
    if !kwargs.scalar {
        polars_ensure!(fields[1].dtype()==&DataType::Binary,InvalidOperation:"Delta companion requires native Binary dtype")
    }
    let data = prepared_delta(&kwargs, None).map_err(|e| e.polars(&kwargs.entry))?;
    let (_, dtype) = result_meta(fields[0].dtype(), &data, kwargs.subtract, false)
        .map_err(|e| e.polars(&kwargs.entry))?;
    Ok(Field::new(fields[0].name().clone(), dtype))
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_delta(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    polars_ensure!(inputs.len()==if kwargs.scalar{1}else{2},InvalidOperation:"invalid Delta plugin input count");
    let data = prepared_delta(&kwargs, inputs.get(1)).map_err(|e| e.polars(&kwargs.entry))?;
    calculate(&inputs[0], &data, kwargs.subtract, false).map_err(|e| e.polars(&kwargs.entry))
}

fn dynamic<'py>(
    py: Python<'py>,
    source: &Series,
    operand: &Operand,
    subtract: bool,
    entry: &str,
    carrier: &Bound<'py, PyAny>,
    reader: &Bound<'py, PyAny>,
) -> PyResult<Series> {
    let (source_unit, _) = date_meta(source.dtype()).map_err(|e| e.python(py, entry))?;
    let (unit, dtype) = result_meta(source.dtype(), &operand.data, subtract, false)
        .map_err(|e| e.python(py, entry))?;
    if !operand.data.scalar && operand.data.values.len() != source.len() {
        return Err(crate::error_context::value_error(
            "operand collection length must equal the complete source length",
        ));
    }
    let values = operand
        .data
        .values
        .iter()
        .map(Wire::native)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.python(py, entry))?;
    let zone = date_meta(source.dtype())
        .map_err(|e| e.python(py, entry))?
        .1
        .map(|key| Zone::named(key.as_str()))
        .transpose()
        .map_err(crate::error_context::value_error)?;
    let mut output = Vec::with_capacity(source.len());
    let mut callbacks = operand.callbacks.iter().peekable();
    // Holding only immutable native inputs/owners across an actual external call
    // allows reentrancy; no mutable PyClass borrow or native cache lock survives it.
    for row in 0..source.len() {
        let value = match source.dtype() {
            DataType::Date => source
                .date()
                .map_err(super::eager_error)?
                .physical()
                .get(row)
                .map(|value| i128::from(value) * DAY),
            DataType::Datetime(_, _) => source
                .datetime()
                .map_err(super::eager_error)?
                .physical()
                .get(row)
                .map(|value| i128::from(value) * source_unit.nanos()),
            _ => return Err(crate::error_context::type_error("requires a date source")),
        };
        let callback = if callbacks.peek().is_some_and(|value| value.0 == row) {
            callbacks.next()
        } else {
            None
        };
        let other = &values[if operand.data.scalar { 0 } else { row }];
        let Some(value) = value else {
            output.push(None);
            continue;
        };
        let mut result = None;
        if let Some((_, object, name)) = callback {
            let mut single = source.slice(row as i64, 1);
            if single.dtype() == &DataType::Date {
                single = single
                    .cast(&DataType::Datetime(TimeUnit::Milliseconds, None))
                    .map_err(super::eager_error)?;
            }
            let single = super::export(py, &single, carrier)?;
            let returned = crate::protocol::call_special(object.bind(py), name, &single)
                .map_err(|e| crate::error_context::item(py, e, entry, "other", row, None, true))?;
            if returned.is(py.NotImplemented()) {
                if *name != "__add__" {
                    return Err(crate::error_context::location(
                        py,
                        crate::error_context::type_error(
                            "the actual reflected arithmetic callback returned NotImplemented",
                        ),
                        entry,
                        &format!("other[{row}]"),
                    ));
                }
            } else if crate::date_input::missing(&returned) {
                result = Some(None)
            } else {
                let prepared = reader
                    .call1((&returned, entry))
                    .map_err(crate::error_context::external)?;
                let prepared = prepared
                    .cast::<Operand>()
                    .map_err(|_| {
                        crate::error_context::type_error(
                            "an arithmetic callback must return one date or one date row",
                        )
                    })?
                    .borrow();
                if prepared.data.kind != 3
                    || prepared.data.values.len() != 1
                    || !prepared.callbacks.is_empty()
                {
                    return Err(crate::error_context::type_error(
                        "an arithmetic callback must return exactly one date row, not text/numbers/duration or another length",
                    ));
                }
                if prepared
                    .data
                    .domain
                    .is_some_and(|aware| aware != zone.is_some())
                {
                    return Err(crate::error_context::type_error(
                        "callback date and source must have matching timezone awareness",
                    ));
                }
                let returned = prepared.data.values[0]
                    .native()
                    .map_err(|e| e.python(py, entry))?;
                result = Some(
                    one(value, &returned, zone.as_ref(), false, true)
                        .map_err(|e| e.at(row).python(py, entry))?,
                );
            }
        }
        let result = match result {
            Some(value) => value,
            None => one(value, other, zone.as_ref(), subtract, false)
                .map_err(|e| e.at(row).python(py, entry))?,
        };
        output.push(
            result
                .map(|value| project(value, unit, row))
                .transpose()
                .map_err(|e| e.python(py, entry))?,
        );
    }
    finish(source, output, dtype).map_err(|e| e.python(py, entry))
}

#[pyfunction]
#[pyo3(signature=(source,operand,target,subtract,entry,return_only=false,carrier=None,reader=None))]
#[expect(
    clippy::too_many_arguments,
    reason = "One native arithmetic exit, with optional host-only actual callback adapters"
)]
fn _pldt_binary<'py>(
    source: PySeries,
    operand: PyRef<'_, Operand>,
    target: &Bound<'py, PyAny>,
    subtract: bool,
    entry: &str,
    return_only: bool,
    carrier: Option<&Bound<'py, PyAny>>,
    reader: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    if return_only && (operand.data.kind != 3 || operand.data.scalar) {
        return Err(crate::error_context::type_error(
            "a whole-column callback must return an equal-length date collection",
        ));
    }
    let result = if operand.callbacks.is_empty() {
        let data = &operand.data;
        py.detach(|| calculate(&source.0, data, subtract, return_only))
            .map_err(|e| e.python(py, entry))?
    } else {
        if operand.data.scalar {
            return Err(crate::error_context::type_error(
                "scalar callback belongs to normal whole-column Python negotiation",
            ));
        }
        dynamic(
            py,
            &source.0,
            &operand,
            subtract,
            entry,
            carrier.ok_or_else(|| {
                crate::error_context::runtime("missing actual Series callback carrier")
            })?,
            reader.ok_or_else(|| crate::error_context::runtime("missing callback date reader"))?,
        )?
    };
    super::export(py, &result, target)
}
#[pyfunction]
fn _pldt_scalar_callback<'py>(
    operand: PyRef<'_, Operand>,
    source: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let Some((_, value, name)) = operand.callbacks.first() else {
        return Err(crate::error_context::runtime(
            "missing actual arithmetic callback",
        ));
    };
    if !operand.data.scalar {
        return Err(crate::error_context::runtime(
            "expected one scalar arithmetic callback",
        ));
    }
    crate::protocol::call_special(value.bind(source.py()), name, source)
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_operand_objects, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_operand_column, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_operand_ticks, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_binary, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_scalar_callback, module)?)
}

#[cfg(test)]
mod tests {
    #[test]
    fn exact_delta_snapshot_executes_on_an_unattached_native_thread() {
        std::thread::spawn(|| {
            use polars::prelude::*;
            let delta = crate::delta::value::DeltaValue::from_totals(
                0,
                1,
                crate::delta::value::AbsoluteFields::EMPTY,
            )
            .unwrap();
            let data = super::Data {
                version: 1,
                kind: 1,
                unit: "s".into(),
                scalar: true,
                domain: None,
                values: vec![super::Wire::Delta(delta.core17())],
            };
            let encoded = serde_json::to_vec(&data).unwrap();
            let decoded: super::Data = serde_json::from_slice(&encoded).unwrap();
            let source = Series::new("time".into(), [Some(123456789i64), Some(i64::MIN), None])
                .cast(&DataType::Datetime(TimeUnit::Nanoseconds, None))
                .unwrap();
            let result = super::calculate(&source, &decoded, false, false)
                .map_err(|error| error.message)
                .unwrap();
            assert_eq!(
                result
                    .datetime()
                    .unwrap()
                    .physical()
                    .iter()
                    .collect::<Vec<_>>(),
                [Some(123456790), Some(i64::MIN + 1), None]
            );
        })
        .join()
        .unwrap();
    }
}
