//! Boundary difference reads exact target coordinates and emits one Int64 column.
use super::finish::{Failure, Kind};
use crate::batch_shape::Column;
use crate::boundary_count::{self, BoundaryIndex, Bucket, CalendarIndex, FixedIndex, TickBucket};
use crate::epoch::{Options as ReadOptions, Unit};
use crate::parser::config::NativeRules;
use crate::parser::fields::{Lenient, Nano, Precision};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyBytes, PyString};
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;
const ENTRY: &str = "Pldt.pldt.diff";
const DAY: i128 = 86_400_000_000_000;
impl From<boundary_count::Error> for Failure {
    fn from(error: boundary_count::Error) -> Self {
        match error {
            boundary_count::Error::Value(message) => Self::new(Kind::Value, message),
            boundary_count::Error::Capacity(message) => Self::new(Kind::Capacity, message),
        }
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    unit: String,
    absolute: bool,
    inclusive: String,
    scalar: bool,
    storage: u8,
    numpy: Option<(i32, i32)>,
    aware: bool,
}
fn roles(options: &Options) -> Result<(Bucket, i128), Failure> {
    if options.version != 1 || options.storage > 2 {
        return Err(Failure::new(
            Kind::Value,
            "invalid boundary-diff preparation",
        ));
    }
    Ok((
        Bucket::parse(&options.unit)?,
        match options.inclusive.as_str() {
            "one" => 0,
            "both" => 1,
            "neither" => -1,
            _ => {
                return Err(Failure::new(
                    Kind::Value,
                    "inclusive must be 'one', 'both' or 'neither'",
                ));
            }
        },
    ))
}
fn source_meta(source: &Field) -> Result<(Unit, bool), Failure> {
    match source.dtype() {
        DataType::Datetime(unit, zone) => Ok((super::input::epoch_unit(*unit), zone.is_some())),
        DataType::Date => Ok((Unit::Millisecond, false)),
        _ => Err(Failure::new(
            Kind::Type,
            "boundary diff requires a Date or Datetime source",
        )),
    }
}
fn target_schema(field: &Field, source_aware: bool, options: &Options) -> Result<(), Failure> {
    match (options.storage, field.dtype()) {
        (2, DataType::Binary) => Ok(()),
        (1, DataType::Int64) if options.numpy.is_some() => {
            if options.aware != source_aware {
                return Err(Failure::new(
                    Kind::Type,
                    "cannot mix naive and aware date columns",
                ));
            }
            Ok(())
        }
        (0, DataType::Datetime(_, zone)) => {
            if zone.is_some() == source_aware {
                Ok(())
            } else {
                Err(Failure::new(
                    Kind::Type,
                    "cannot mix naive and aware date columns",
                ))
            }
        }
        (0, DataType::Date) => {
            if source_aware {
                Err(Failure::new(
                    Kind::Type,
                    "cannot mix naive and aware date columns",
                ))
            } else {
                Ok(())
            }
        }
        (0, DataType::String | DataType::Null | DataType::Float32 | DataType::Float64) => Ok(()),
        (0, dtype) if dtype.is_integer() => Ok(()),
        _ => Err(Failure::new(
            Kind::Type,
            "targets require dates, text or numeric seconds; Boolean/duration/binary values are not dates",
        )),
    }
}
fn read_targets(
    source: &Series,
    source_aware: bool,
    options: &Options,
) -> Result<Column<Option<i128>>, Failure> {
    target_schema(
        &Field::new(source.name().clone(), source.dtype().clone()),
        source_aware,
        options,
    )?;
    let mut values = Vec::with_capacity(source.len());
    let mut push = |value: Option<(i128, bool)>| -> Result<(), Failure> {
        if value.is_some_and(|(_, aware)| aware != source_aware) {
            return Err(Failure::new(
                Kind::Type,
                "cannot mix naive and aware date targets; prepare the target timezone explicitly",
            ));
        }
        values.push(value.map(|(nanos, _)| nanos));
        Ok(())
    };
    if options.storage == 2 {
        for (row, value) in source
            .binary()
            .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
            .iter()
            .enumerate()
        {
            let value = value
                .map(|bytes| {
                    if bytes.len() != 17 || bytes[16] > 1 {
                        return Err(Failure::new(
                            Kind::Value,
                            "invalid prepared date target record",
                        ));
                    }
                    let aware = bytes[16] != 0;
                    let bytes: [u8; 16] = bytes[..16]
                        .try_into()
                        .map_err(|_| Failure::new(Kind::Value, "invalid prepared date integer"))?;
                    Ok((i128::from_le_bytes(bytes), aware))
                })
                .transpose()
                .map_err(|e: Failure| e.at(row))?;
            push(value).map_err(|e| e.at(row))?;
        }
    } else if options.storage == 1 {
        let (code, multiplier) = options
            .numpy
            .ok_or_else(|| Failure::new(Kind::Value, "missing NumPy target unit"))?;
        crate::date_input::scalar_unit(code)
            .map_err(|e| Failure::new(Kind::Value, e.to_string()))?;
        for (row, value) in source
            .i64()
            .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
            .iter()
            .enumerate()
        {
            let value = value
                .filter(|v| *v != i64::MIN)
                .map(|value| {
                    crate::epoch::native_datetime_ticks(value, code, multiplier)
                        .map(|parsed| (parsed.nanos, options.aware))
                })
                .transpose()
                .map_err(|e| Failure::new(Kind::Capacity, e.to_string()).at(row))?;
            push(value).map_err(|e| e.at(row))?;
        }
    } else {
        match source.dtype() {
            DataType::Datetime(unit, zone) => {
                let quantum = super::input::epoch_unit(*unit).nanos();
                for value in source
                    .datetime()
                    .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                    .physical()
                    .iter()
                {
                    push(value.map(|v| (i128::from(v) * quantum, zone.is_some())))?;
                }
            }
            DataType::Date => {
                for value in source
                    .date()
                    .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                    .physical()
                    .iter()
                {
                    push(value.map(|v| (i128::from(v) * DAY, false)))?;
                }
            }
            DataType::Null => {
                for _ in 0..source.len() {
                    push(None)?;
                }
            }
            DataType::String => {
                let mut rules = NativeRules::library();
                let mut scratch = Vec::new();
                let prepared = crate::parser::native::Options {
                    default: None,
                    yearfirst: None,
                    dayfirst: None,
                    isoformat: true,
                };
                for (row, value) in source
                    .str()
                    .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                    .iter()
                    .enumerate()
                {
                    let value = value
                        .filter(|v| !super::text::missing(v))
                        .map(|value| {
                            let parsed = crate::parser::native::parse::<Nano<Lenient>>(
                                value,
                                &mut scratch,
                                &mut rules,
                                prepared,
                            )
                            .map_err(|e| Failure::new(Kind::Parse, e.to_string()))?;
                            let mut nanos = super::finish::fields_nanos(
                                parsed.completed.map(i64::from),
                                i64::from(parsed.fields.fraction.tail()),
                            )?;
                            let aware = parsed.region.is_some() || parsed.fields.is_tzoffset_set();
                            if let Some(region) = parsed.region {
                                let zone = crate::temporal_zone::Zone::named(&region.key)
                                    .map_err(|e| Failure::new(Kind::Value, e))?;
                                nanos = match zone.candidates(nanos)? {
                                    crate::temporal_zone::Candidates::One(value) => value,
                                    crate::temporal_zone::Candidates::Repeated(first, _) => first,
                                    _ => {
                                        return Err(Failure::new(
                                            Kind::Value,
                                            "date target is a nonexistent local time",
                                        ));
                                    }
                                };
                            } else if parsed.fields.is_tzoffset_set() {
                                nanos -= i128::from(parsed.fields.timezone_microseconds()) * 1000;
                            }
                            Ok((nanos, aware))
                        })
                        .transpose()
                        .map_err(|e: Failure| e.at(row))?;
                    push(value).map_err(|e| e.at(row))?;
                }
            }
            DataType::Float32 | DataType::Float64 => {
                let source = source
                    .cast(&DataType::Float64)
                    .map_err(|e| Failure::new(Kind::Type, e.to_string()))?;
                for (row, value) in source
                    .f64()
                    .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                    .iter()
                    .enumerate()
                {
                    let value = value
                        .filter(|v| !v.is_nan())
                        .map(|v| {
                            crate::precision::float_epoch_nanos(v, 1_000_000_000)
                                .map(|ns| (ns, false))
                        })
                        .transpose()
                        .map_err(|_| {
                            Failure::new(Kind::Capacity, "numeric seconds exceed native range")
                                .at(row)
                        })?;
                    push(value).map_err(|e| e.at(row))?;
                }
            }
            _ => {
                let source = source
                    .strict_cast(&DataType::Int128)
                    .map_err(|e| Failure::new(Kind::Capacity, e.to_string()))?;
                for (row, value) in source
                    .i128()
                    .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                    .iter()
                    .enumerate()
                {
                    let value = value
                        .map(|v| {
                            v.checked_mul(1_000_000_000)
                                .ok_or_else(|| {
                                    Failure::new(
                                        Kind::Capacity,
                                        "numeric seconds exceed native range",
                                    )
                                })
                                .map(|ns| (ns, false))
                        })
                        .transpose()
                        .map_err(|e| e.at(row))?;
                    push(value).map_err(|e| e.at(row))?;
                }
            }
        }
    }
    if options.scalar {
        if values.len() != 1 {
            return Err(Failure::new(
                Kind::Value,
                "scalar target must contain one value",
            ));
        }
        Ok(Column::Scalar(values[0]))
    } else {
        Ok(Column::Values(values))
    }
}
fn calculate<I: BoundaryIndex>(
    source: &Series,
    targets: &Column<Option<i128>>,
    mut index: I,
    bucket: Bucket,
    options: &Options,
    adjustment: i128,
) -> Result<Series, Failure> {
    let scalar = match targets {
        Column::Scalar(Some(nanos)) => Some(bucket.index(*nanos)?),
        _ => None,
    };
    let mut output = PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
    let mut push = |row: usize, tick: Option<i64>| -> Result<(), Failure> {
        let target = targets.get(row);
        let value = if let (Some(tick), Some(nanos)) = (tick, target) {
            let left = index
                .source(tick)
                .map_err(Failure::from)
                .map_err(|e| e.at(row))?;
            let right = if let Some(value) = scalar {
                value
            } else {
                index
                    .target(nanos)
                    .map_err(Failure::from)
                    .map_err(|e| e.at(row))?
            };
            Some(
                boundary_count::finish(left, right, options.absolute, adjustment)
                    .map_err(Failure::from)
                    .map_err(|e| e.at(row))?,
            )
        } else {
            None
        };
        output.append_option(value);
        Ok(())
    };
    if source.dtype() == &DataType::Date {
        for (row, value) in source
            .date()
            .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
            .physical()
            .iter()
            .enumerate()
        {
            push(row, value.map(|v| i64::from(v) * 86_400_000))?;
        }
    } else {
        for (row, value) in source
            .datetime()
            .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
            .physical()
            .iter()
            .enumerate()
        {
            push(row, value)?;
        }
    }
    Ok(output.finish().into_series())
}
fn execute(inputs: &[Series], options: &Options) -> Result<Series, Failure> {
    if inputs.len() != 2 {
        return Err(Failure::new(
            Kind::Value,
            "boundary diff requires source and target",
        ));
    }
    let (bucket, adjustment) = roles(options)?;
    let source = &inputs[0];
    let (unit, aware) = source_meta(&Field::new(source.name().clone(), source.dtype().clone()))?;
    if !options.scalar && inputs[1].len() != source.len() {
        return Err(Failure::new(
            Kind::Value,
            "target length must equal source length; a one-element collection is not a scalar",
        ));
    }
    let targets = read_targets(&inputs[1], aware, options)?;
    if targets.len().is_some_and(|len| len != source.len()) {
        return Err(Failure::new(
            Kind::Value,
            "target length must equal source length; a one-element collection is not a scalar",
        ));
    }
    match bucket {
        Bucket::Calendar(kind) => calculate(
            source,
            &targets,
            CalendarIndex::new(kind, unit),
            bucket,
            options,
            adjustment,
        ),
        _ => calculate(
            source,
            &targets,
            FixedIndex {
                source: TickBucket::new(bucket, unit),
                target: bucket,
            },
            bucket,
            options,
            adjustment,
        ),
    }
}
fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    polars_ensure!(fields.len()==2,InvalidOperation:"boundary diff needs source and target");
    roles(&kwargs).map_err(|e| e.polars(ENTRY))?;
    let (_, aware) = source_meta(&fields[0]).map_err(|e| e.polars(ENTRY))?;
    target_schema(&fields[1], aware, &kwargs).map_err(|e| e.polars(ENTRY))?;
    Ok(Field::new(fields[0].name().clone(), DataType::Int64))
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_diff(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    execute(inputs, &kwargs).map_err(|e| e.polars(ENTRY))
}
#[pyfunction]
#[pyo3(signature=(value,column,count=None))]
fn _pldt_diff_objects(
    value: &Bound<'_, PyAny>,
    column: bool,
    count: Option<usize>,
) -> PyResult<(PySeries, bool)> {
    let py = value.py();
    let scalar = !column
        && (crate::date_input::missing(value)
            || value.is_instance_of::<PyString>()
            || value.is_instance_of::<pyo3::types::PyDate>()
            || crate::numeric::is_bool(value)
            || crate::numeric::supported_float(value)
            || unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) != 0 }
            || crate::numpy_scalar::datetime_ticks(value)?.is_some());
    if value.is_instance_of::<PyBytes>() || value.is_instance_of::<PyByteArray>() {
        return Err(crate::error_context::type_error(
            "byte strings are not date targets",
        ));
    }
    let options = ReadOptions {
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
    let mut builder = BinaryChunkedBuilder::new("".into(), if scalar { 1 } else { 0 });
    let mut read = |item: &Bound<'_, PyAny>, row: usize| -> PyResult<()> {
        let value = crate::temporal_target::read(item, &options).map_err(|e| {
            crate::error_context::item(py, e, ENTRY, "dtobj", row, Some(item), false)
        })?;
        if let Some(value) = value {
            let mut bytes = [0; 17];
            bytes[..16].copy_from_slice(&value.nanos.to_le_bytes());
            bytes[16] = u8::from(value.aware);
            builder.append_value(bytes);
        } else {
            builder.append_null();
        }
        Ok(())
    };
    if scalar {
        read(value, 0)?;
    } else {
        let mut seen = 0;
        for (row, item) in value
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            if count.is_some_and(|count| row >= count) {
                return Err(crate::error_context::value_error(
                    "target length must equal source length",
                ));
            }
            let item = item.map_err(crate::error_context::external)?;
            read(&item, row)?;
            seen = row + 1;
        }
        if count.is_some_and(|count| count != seen) {
            return Err(crate::error_context::value_error(
                "target length must equal source length",
            ));
        }
    }
    Ok((PySeries(builder.finish().into_series()), scalar))
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One prepared native diff boundary with explicit scalar/unit/domain roles"
)]
#[pyo3(signature=(source,target,unit,absolute,inclusive,scalar,storage,numpy,aware))]
fn _pldt_diff(
    py: Python<'_>,
    source: PySeries,
    target: PySeries,
    unit: String,
    absolute: bool,
    inclusive: String,
    scalar: bool,
    storage: u8,
    numpy: Option<(i32, i32)>,
    aware: bool,
) -> PyResult<PySeries> {
    let options = Options {
        version: 1,
        unit,
        absolute,
        inclusive,
        scalar,
        storage,
        numpy,
        aware,
    };
    let inputs = [source.0, target.0];
    py.detach(|| execute(&inputs, &options))
        .map(PySeries)
        .map_err(|e| e.python(py, ENTRY))
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_diff, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_diff_objects, module)?)
}
