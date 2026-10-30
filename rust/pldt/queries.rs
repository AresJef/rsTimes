//! Direct calendar/condition results and typed tables, without date objects.
use super::finish::{Failure, Kind};
use crate::temporal_zone::Zone;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::Deserialize;
use std::sync::OnceLock;
const DAY: i128 = 86_400_000_000_000;

impl From<crate::calendar_query::Error> for Failure {
    fn from(error: crate::calendar_query::Error) -> Self {
        match error {
            crate::calendar_query::Error::Capacity(message) => Self::new(Kind::Capacity, message),
            crate::calendar_query::Error::Internal(message) => Self::new(Kind::Runtime, message),
        }
    }
}
#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    code: u8,
    scalar: bool,
    reference: Option<(i64, i64)>,
    entry: String,
}
fn target_names(code: u8) -> u8 {
    match code {
        102 => 1,
        103 => 2,
        _ => 0,
    }
}
fn targeted(code: u8) -> bool {
    code == 11 || (100..=104).contains(&code)
}
fn temporal(source: &Field) -> Result<Option<&TimeZone>, Failure> {
    match source.dtype() {
        DataType::Date => Ok(None),
        DataType::Datetime(_, zone) => Ok(zone.as_ref()),
        _ => Err(Failure::new(
            Kind::Type,
            "requires a Date or Datetime source",
        )),
    }
}
const TIME_NAMES: [&str; 9] = [
    "tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec", "tm_wday", "tm_yday", "tm_isdst",
];
fn meta(source: &Field, options: &Options) -> Result<Field, Failure> {
    temporal(source)?;
    let dtype = match options.code {
        0..=12 | 20..=31 => DataType::Int64,
        100..=109 => DataType::Boolean,
        201 => DataType::Struct(
            ["year", "week", "day"]
                .into_iter()
                .map(|name| Field::new(name.into(), DataType::UInt32))
                .collect(),
        ),
        202 | 203 => DataType::Struct(
            TIME_NAMES
                .into_iter()
                .enumerate()
                .map(|(i, name)| {
                    Field::new(
                        name.into(),
                        match i {
                            0 => DataType::Int64,
                            7 => DataType::Int16,
                            _ => DataType::Int8,
                        },
                    )
                })
                .collect(),
        ),
        _ => return Err(Failure::new(Kind::Value, "unknown calendar query")),
    };
    if options.version != 1 {
        return Err(Failure::new(
            Kind::Value,
            "unsupported query preparation version",
        ));
    }
    Ok(Field::new(source.name().clone(), dtype))
}
/// Same mature detector and TZ override as the host local service, successful
/// native rule caching only. Invoked during naive-query preparation, never per
/// row, and never for aware comparison. No interpreter access is involved.
pub(super) fn local_rules() -> Result<Zone, Failure> {
    static LOCAL: OnceLock<Zone> = OnceLock::new();
    if let Some(zone) = LOCAL.get() {
        return Ok(zone.clone());
    }
    let key = match std::env::var("TZ") {
        Ok(name) => name.strip_prefix(':').unwrap_or(&name).to_owned(),
        Err(std::env::VarError::NotPresent) => iana_time_zone::get_timezone().map_err(|e| {
            Failure::new(Kind::Value, format!("local timezone is unavailable: {e}"))
        })?,
        Err(error) => {
            return Err(Failure::new(
                Kind::Value,
                format!("local timezone is invalid: {error}"),
            ));
        }
    };
    let zone = Zone::named(&key).map_err(|e| {
        Failure::new(
            Kind::Value,
            format!("local timezone {key:?} is unavailable: {e}"),
        )
    })?;
    let _ = LOCAL.set(zone.clone());
    Ok(LOCAL.get().cloned().unwrap_or(zone))
}
fn source_unit(source: &Series) -> Result<i128, Failure> {
    match source.dtype() {
        DataType::Date => Ok(DAY),
        DataType::Datetime(unit, _) => Ok(super::input::epoch_unit(*unit).nanos()),
        _ => Err(Failure::new(Kind::Type, "requires a temporal source")),
    }
}
fn visit(
    source: &Series,
    mut push: impl FnMut(usize, Option<i128>) -> Result<(), Failure>,
) -> Result<(), Failure> {
    let quantum = source_unit(source)?;
    if source.dtype() == &DataType::Date {
        for (row, value) in source
            .date()
            .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
            .physical()
            .iter()
            .enumerate()
        {
            push(row, value.map(|v| i128::from(v) * quantum))?;
        }
    } else {
        for (row, value) in source
            .datetime()
            .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
            .physical()
            .iter()
            .enumerate()
        {
            push(row, value.map(|v| i128::from(v) * quantum))?;
        }
    }
    Ok(())
}
fn single<const Q: u8>(inputs: &[Series], options: &Options) -> Result<Series, Failure> {
    let source = &inputs[0];
    let boolean = (100..200).contains(&Q);
    let targets = if targeted(Q) {
        let values = super::operations::query_values(&inputs[1], options.scalar, target_names(Q))?;
        if values.len().is_some_and(|len| len != source.len()) {
            return Err(Failure::new(
                Kind::Value,
                "query target length must equal source length; a one-element collection is not a scalar",
            ));
        }
        Some(values)
    } else {
        None
    };
    let zone_name = temporal(&Field::new(source.name().clone(), source.dtype().clone()))?.cloned();
    let clock = Q == 107 || Q == 108;
    let reference = if clock && source.null_count() != source.len() {
        let (high, low) = options
            .reference
            .ok_or_else(|| Failure::new(Kind::Runtime, "missing prepared query reference"))?;
        let utc = (i128::from(high) << 64) | i128::from(low as u64);
        Some(if zone_name.is_some() {
            utc
        } else {
            local_rules()?.wall(utc)?
        })
    } else {
        None
    };
    // Every supported native zone offset is an integral number of seconds.
    // Fraction fields therefore need no regional calendar/offset lookup.
    let zone = if clock || matches!(Q, 10 | 26 | 27) {
        None
    } else {
        zone_name
            .as_ref()
            .map(|key| Zone::named(key.as_str()))
            .transpose()
            .map_err(|e| Failure::new(Kind::Value, e))?
    };
    let mut integers = PrimitiveChunkedBuilder::<Int64Type>::new(
        source.name().clone(),
        if boolean { 0 } else { source.len() },
    );
    let mut flags = BooleanChunkedBuilder::new(
        source.name().clone(),
        if boolean { source.len() } else { 0 },
    );
    let mut cached = None;
    visit(source, |row, value| {
        let selected = targets.as_ref().and_then(|target| target.get(row));
        let Some(instant) = value else {
            if boolean {
                flags.append_value(false)
            } else {
                integers.append_null()
            };
            return Ok(());
        };
        let value = (|| {
            Ok::<Option<i64>, Failure>(if clock {
                let reference = reference
                    .ok_or_else(|| Failure::new(Kind::Runtime, "missing query reference"))?;
                Some(i64::from(if Q == 107 {
                    instant < reference
                } else {
                    instant > reference
                }))
            } else if Q == 12 {
                zone.as_ref()
                    .map(|zone| zone.offset_seconds(instant).map(i64::from))
                    .transpose()?
            } else if Q == 106 {
                Some(i64::from(
                    zone.as_ref()
                        .map(|zone| zone.is_dst(instant))
                        .transpose()?
                        .unwrap_or(false),
                ))
            } else {
                let wall = zone
                    .as_ref()
                    .map_or(Ok(instant), |zone| zone.wall(instant))?;
                Some(
                    crate::calendar_query::fact::<Q>(wall, selected, &mut cached)
                        .map_err(Failure::from)?,
                )
            })
        })()
        .map_err(|e| e.at(row))?;
        if boolean {
            flags.append_value(value.is_some_and(|v| v != 0));
        } else if let Some(value) = value {
            integers.append_value(value)
        } else {
            integers.append_null()
        };
        Ok(())
    })?;
    Ok(if boolean {
        flags.finish().into_series()
    } else {
        integers.finish().into_series()
    })
}
fn table(source: &Series, options: &Options) -> Result<Series, Failure> {
    let iso = options.code == 201;
    let utc = options.code == 203;
    let name = temporal(&Field::new(source.name().clone(), source.dtype().clone()))?.cloned();
    let zone = if utc {
        None
    } else {
        name.as_ref()
            .map(|key| Zone::named(key.as_str()))
            .transpose()
            .map_err(|e| Failure::new(Kind::Value, e))?
    };
    let names: Vec<&str> = if iso {
        vec!["year", "week", "day"]
    } else {
        TIME_NAMES.to_vec()
    };
    let mut builders: Vec<_> = names
        .iter()
        .map(|name| PrimitiveChunkedBuilder::<Int64Type>::new((*name).into(), source.len()))
        .collect();
    visit(source, |row, value| {
        let Some(instant) = value else {
            for builder in &mut builders {
                builder.append_null();
            }
            return Ok(());
        };
        let result = (|| {
            let wall = zone
                .as_ref()
                .map_or(Ok(instant), |zone| zone.wall(instant))?;
            let fields = crate::date_transform::fields(wall)
                .map_err(|e| Failure::from(crate::period::Error::from(e)))?;
            let ordinal = i64::try_from(wall.div_euclid(DAY) + 719_163)
                .map_err(|_| Failure::new(Kind::Capacity, "calendar day overflow"))?;
            if iso {
                let values = crate::calendar_query::iso_at(fields[0], ordinal)?;
                if !(0..=i64::from(u32::MAX)).contains(&values[0]) {
                    return Err(Failure::new(
                        Kind::Capacity,
                        "ISO year is outside the UInt32 range; use isoyear() for signed calendar years",
                    ));
                }
                for (builder, value) in builders.iter_mut().zip(values) {
                    builder.append_value(value);
                }
            } else {
                let first = crate::calendar::checked_ordinal(fields[0], 1, 1)
                    .map_err(|e| Failure::new(Kind::Capacity, e))?;
                let dst = if utc {
                    0
                } else if let Some(zone) = &zone {
                    if zone.fixed_seconds() == Some(0) {
                        -1
                    } else {
                        i64::from(zone.is_dst(instant)?)
                    }
                } else {
                    -1
                };
                let values = [
                    fields[0],
                    fields[1],
                    fields[2],
                    fields[3],
                    fields[4],
                    fields[5],
                    (ordinal - 1).rem_euclid(7),
                    ordinal - first + 1,
                    dst,
                ];
                for (builder, value) in builders.iter_mut().zip(values) {
                    builder.append_value(value);
                }
            }
            Ok(())
        })();
        result.map_err(|e: Failure| e.at(row))
    })?;
    let mut columns = Vec::with_capacity(names.len());
    for (index, builder) in builders.into_iter().enumerate() {
        let column = builder.finish().into_series();
        let dtype = if iso {
            DataType::UInt32
        } else {
            match index {
                0 => DataType::Int64,
                7 => DataType::Int16,
                _ => DataType::Int8,
            }
        };
        columns.push(
            column
                .strict_cast(&dtype)
                .map_err(|e| Failure::new(Kind::Capacity, e.to_string()))?,
        );
    }
    let validity = columns[0].chunks()[0].validity().cloned();
    Ok(
        StructChunked::from_series(source.name().clone(), source.len(), columns.iter())
            .map_err(|e| Failure::new(Kind::Runtime, e.to_string()))?
            .with_outer_validity(validity)
            .into_series(),
    )
}
fn execute(inputs: &[Series], options: &Options) -> Result<Series, Failure> {
    if inputs.len() != 1 + usize::from(targeted(options.code)) {
        return Err(Failure::new(Kind::Value, "invalid query input count"));
    }
    meta(
        &Field::new(inputs[0].name().clone(), inputs[0].dtype().clone()),
        options,
    )?;
    if options.code >= 201 {
        return table(&inputs[0], options);
    }
    macro_rules! dispatch{($($id:literal),*)=>{match options.code{$($id=>single::<$id>(inputs,options),)*_=>Err(Failure::new(Kind::Value,"unknown query code"))}};}
    dispatch!(
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
        100, 101, 102, 103, 104, 105, 106, 107, 108, 109
    )
}
fn output_field(fields: &[Field], options: Options) -> PolarsResult<Field> {
    polars_ensure!(fields.len()==1+usize::from(targeted(options.code)),InvalidOperation:"invalid query input count");
    if targeted(options.code) {
        polars_ensure!(fields[1].dtype().is_integer()||(target_names(options.code)!=0&&fields[1].dtype()==&DataType::String),InvalidOperation:"query targets require integers or supported names without missing values");
    }
    meta(&fields[0], &options).map_err(|e| e.polars(&options.entry))
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_query(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    execute(inputs, &kwargs).map_err(|e| e.polars(&kwargs.entry))
}
#[pyfunction]
fn _pldt_query_clock() -> PyResult<(i64, i64)> {
    let value = crate::clock::system_nanos(std::time::SystemTime::now())
        .map_err(crate::error_context::overflow)?;
    Ok(((value >> 64) as i64, value as i64))
}
#[pyfunction]
#[pyo3(signature=(source,code,entry,target=None,scalar=false,reference=None))]
fn _pldt_query(
    py: Python<'_>,
    source: PySeries,
    code: u8,
    entry: String,
    target: Option<PySeries>,
    scalar: bool,
    reference: Option<(i64, i64)>,
) -> PyResult<PySeries> {
    let options = Options {
        version: 1,
        code,
        scalar,
        reference,
        entry,
    };
    let mut inputs = vec![source.0];
    if let Some(target) = target {
        inputs.push(target.0);
    }
    py.detach(|| execute(&inputs, &options))
        .map(PySeries)
        .map_err(|e| e.python(py, &options.entry))
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_query, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_query_clock, module)?)
}
