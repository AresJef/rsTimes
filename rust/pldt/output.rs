//! Native numeric/date/time/name/ISO outputs, independent of Python row objects.
use super::finish::{Failure, Kind};
use crate::epoch::Unit;
use crate::parser::Truth;
use crate::temporal_zone::{Candidates, Zone};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBytes, PyList, PyString, PyTime, PyTzInfo};
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::{Deserialize, Serialize};
const DAY: i128 = 86_400_000_000_000;
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    code: u8,
    utc: bool,
    group: usize,
    sep: String,
    precision: u8,
    entry: String,
}
#[pyclass(frozen, skip_from_py_object, name = "_PldtOutputContext")]
struct Context {
    options: Options,
}
#[pymethods]
impl Context {
    fn plugin_data<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let value = serde_json::to_vec(&self.options)
            .map_err(|e| crate::error_context::runtime(e.to_string()))?;
        Ok(PyBytes::new(py, &value))
    }
}
#[pyfunction]
#[pyo3(signature=(code,utc,sep,timespec,locale,entry))]
fn _pldt_output_prepare(
    code: u8,
    utc: Truth,
    sep: &Bound<'_, PyAny>,
    timespec: &Bound<'_, PyAny>,
    locale: Option<&Bound<'_, PyAny>>,
    entry: String,
) -> PyResult<Context> {
    let py = sep.py();
    let (sep, precision) = if code == 10 {
        let sep = sep
            .cast::<PyString>()
            .map_err(|_| crate::error_context::type_error("sep must be one Unicode character"))?
            .to_str()?
            .to_owned();
        if sep.chars().count() != 1 {
            return Err(crate::error_context::value_error(
                "sep must be one Unicode character",
            ));
        }
        let spec = timespec
            .cast::<PyString>()
            .map_err(|_| crate::error_context::type_error("timespec must be a string"))?
            .to_str()?;
        let precision = match spec {
            "auto" => 0,
            "hours" | "h" => 1,
            "minutes" | "m" | "min" => 2,
            "seconds" | "s" => 3,
            "milliseconds" | "ms" => 4,
            "microseconds" | "us" => 5,
            "nanoseconds" | "ns" => 6,
            _ => {
                return Err(crate::error_context::value_error(
                    "timespec must be auto/hours/minutes/seconds/milliseconds/microseconds/nanoseconds or h/m/min/s/ms/us/ns",
                ));
            }
        };
        (sep, precision)
    } else {
        ("T".into(), 0)
    };
    let group = if code == 12 || code == 13 {
        crate::localization::name_group(py, locale)?
    } else {
        0
    };
    Ok(Context {
        options: Options {
            version: 1,
            code,
            utc: utc.0,
            group,
            sep,
            precision,
            entry,
        },
    })
}
fn meta(source: &Field, options: &Options) -> Result<Field, Failure> {
    if options.version != 1 {
        return Err(Failure::new(
            Kind::Value,
            "invalid output preparation version",
        ));
    }
    let unit = match source.dtype() {
        DataType::Datetime(unit, _) => *unit,
        DataType::Date => TimeUnit::Milliseconds,
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "requires a Date or Datetime source",
            ));
        }
    };
    let dtype = match options.code {
        0 | 3 => DataType::Float64,
        1 | 2 => DataType::Int64,
        4 => DataType::Datetime(unit, None),
        5 => DataType::Date,
        6 => DataType::Time,
        10..=14 => DataType::String,
        _ => return Err(Failure::new(Kind::Value, "unknown temporal output")),
    };
    if options.code == 10 && (options.sep.chars().count() != 1 || options.precision > 6) {
        return Err(Failure::new(Kind::Value, "invalid ISO output options"));
    }
    if matches!(options.code, 12 | 13)
        && crate::localization::native_name(options.group, 0).is_none()
    {
        return Err(Failure::new(Kind::Value, "invalid compiled locale group"));
    }
    Ok(Field::new(source.name().clone(), dtype))
}
fn execute<const K: u8>(source: &Series, options: &Options) -> Result<Series, Failure> {
    let field = meta(
        &Field::new(source.name().clone(), source.dtype().clone()),
        options,
    )?;
    let (unit, key) = match source.dtype() {
        DataType::Datetime(unit, key) => (super::input::epoch_unit(*unit), key.as_ref()),
        _ => (Unit::Millisecond, None),
    };
    let aware = key.is_some();
    let utc = K == 3 || (K == 0 || K == 1) && options.utc;
    let zone = if utc {
        None
    } else {
        key.map(|key| Zone::named(key.as_str()))
            .transpose()
            .map_err(|e| Failure::new(Kind::Value, e))?
    };
    let local = if K == 3 && !aware && source.len() != source.null_count() {
        Some(super::queries::local_rules()?)
    } else {
        None
    };
    // No wall shift is requested on these native integer exports. Keep the
    // original unit/null buffers or divide signed ns directly; every ns tick
    // has a representable us result, including the complete signed64 domain.
    if K == 1
        && (utc
            || !aware
            || zone
                .as_ref()
                .is_some_and(|zone| zone.fixed_seconds() == Some(0)))
        && let Ok(dates) = source.datetime()
    {
        match unit {
            Unit::Microsecond => return Ok(dates.physical().clone().into_series()),
            Unit::Nanosecond => {
                return Ok(dates
                    .physical()
                    .apply_values(|tick| tick.div_euclid(1000))
                    .into_series());
            }
            _ => {}
        }
    }
    let mut floats = PrimitiveChunkedBuilder::<Float64Type>::new(
        source.name().clone(),
        if K == 0 || K == 3 { source.len() } else { 0 },
    );
    let mut integers = PrimitiveChunkedBuilder::<Int64Type>::new(
        source.name().clone(),
        if matches!(K, 1 | 2 | 4 | 6) {
            source.len()
        } else {
            0
        },
    );
    let mut days = PrimitiveChunkedBuilder::<Int32Type>::new(
        source.name().clone(),
        if K == 5 { source.len() } else { 0 },
    );
    let mut strings = StringChunkedBuilder::new(
        source.name().clone(),
        if K >= 10 { source.len() } else { 0 },
    );
    let mut cached = None;
    super::input::visit_nanos(source, |row, value| {
        let result = (|| {
            let Some(instant) = value else {
                match K {
                    0 | 3 => floats.append_null(),
                    1 | 2 | 4 | 6 => integers.append_null(),
                    5 => days.append_null(),
                    _ => strings.append_null(),
                };
                return Ok(());
            };
            if K == 14 {
                if let Some(zone) = &zone {
                    strings.append_value(zone.abbreviation(instant)?);
                } else {
                    strings.append_null();
                }
                return Ok(());
            }
            let wall = zone
                .as_ref()
                .map_or(Ok(instant), |zone| zone.wall(instant))?;
            let value = if let Some(local) = &local {
                match local.candidates(wall)? {
                    Candidates::One(value) => value,
                    Candidates::Repeated(..) => {
                        return Err(Failure::new(
                            Kind::Value,
                            "local time occurs twice; call tz_localize with an explicit ambiguous policy before timestamp()",
                        ));
                    }
                    Candidates::Gap { .. } => {
                        return Err(Failure::new(
                            Kind::Value,
                            "local time is nonexistent; call tz_localize with an explicit nonexistent policy before timestamp()",
                        ));
                    }
                }
            } else {
                wall
            };
            match K {
                0|3=>floats.append_value(crate::temporal_output::seconds_float(value,1_000_000_000)),
                1=>integers.append_value(i64::try_from(value.div_euclid(1000)).map_err(|_|Failure::new(Kind::Capacity,"microseconds exceed int64 output capacity"))?),
                2=>integers.append_value(i64::try_from(wall.div_euclid(DAY)+719_163).map_err(|_|Failure::new(Kind::Capacity,"ordinal exceeds int64 output capacity"))?),
                4=>integers.append_value(crate::precision::epoch_tick(wall,unit.nanos(),false).map_err(|_|Failure::new(Kind::Capacity,"local wall coordinates exceed current unit capacity; use as_unit explicitly"))?),
                5=>days.append_value(i32::try_from(wall.div_euclid(DAY)).map_err(|_|Failure::new(Kind::Capacity,"local date exceeds the native Date signed32-day capacity"))?),
                6=>integers.append_value(wall.rem_euclid(DAY)as i64),
                12|13=>{
                    let position=if K==12{crate::calendar_query::fact::<21>(wall,None,&mut cached)?-1}else{12+crate::calendar_query::fact::<28>(wall,None,&mut cached)?};
                    strings.append_value(crate::localization::native_name(options.group,position as usize).ok_or_else(||Failure::new(Kind::Value,"invalid compiled date name position"))?);
                },
                10|11=>{
                    let f=crate::date_transform::fields(wall).map_err(|e|Failure::from(crate::period::Error::from(e)))?;
                    if K==10{let offset=zone.as_ref().map(|zone|zone.offset_seconds(instant).map(|v|i64::from(v)*1_000_000)).transpose()?;strings.append_value(crate::temporal_output::iso_text(f,&options.sep,options.precision,offset));}
                    else{let day=crate::calendar_query::fact::<28>(wall,None,&mut cached)? as usize;const DAYS:[&str;7]=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];const MONTHS:[&str;12]=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];strings.append_value(format!("{} {} {:2} {:02}:{:02}:{:02} {:04}",DAYS[day],MONTHS[(f[1]-1)as usize],f[2],f[3],f[4],f[5],f[0]));}
                },
                _=>return Err(Failure::new(Kind::Runtime,"unknown output code")),
            }
            Ok(())
        })();
        result.map_err(|e: Failure| e.at(row))
    })?;
    Ok(match K {
        0 | 3 => floats.finish().into_series(),
        1 | 2 => integers.finish().into_series(),
        4 => {
            let DataType::Datetime(unit, _) = field.dtype else {
                return Err(Failure::new(Kind::Runtime, "invalid wall output dtype"));
            };
            integers.finish().into_datetime(unit, None).into_series()
        }
        5 => days.finish().into_date().into_series(),
        6 => integers.finish().into_time().into_series(),
        _ => strings.finish().into_series(),
    })
}
fn dispatch(source: &Series, options: &Options) -> Result<Series, Failure> {
    macro_rules! codes{($($code:literal),*)=>{match options.code{$($code=>execute::<$code>(source,options),)*_=>Err(Failure::new(Kind::Value,"unknown output code"))}};}
    codes!(0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14)
}
#[derive(Deserialize)]
struct Kwargs {
    #[serde(deserialize_with = "crate::serde_values::byte_vector")]
    prepared: Vec<u8>,
}
fn output_field(fields: &[Field], kwargs: Kwargs) -> PolarsResult<Field> {
    polars_ensure!(fields.len()==1,InvalidOperation:"output needs one temporal source");
    let options: Options =
        serde_json::from_slice(&kwargs.prepared).map_err(|e| polars_err!(ComputeError:"{}",e))?;
    meta(&fields[0], &options).map_err(|e| e.polars(&options.entry))
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_output(inputs: &[Series], kwargs: Kwargs) -> PolarsResult<Series> {
    polars_ensure!(inputs.len()==1,InvalidOperation:"output needs one temporal source");
    let options: Options =
        serde_json::from_slice(&kwargs.prepared).map_err(|e| polars_err!(ComputeError:"{}",e))?;
    dispatch(&inputs[0], &options).map_err(|e| e.polars(&options.entry))
}
#[pyfunction]
fn _pldt_output<'py>(
    source: PySeries,
    context: PyRef<'_, Context>,
    target: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let options = &context.options;
    let result = py
        .detach(|| dispatch(&source.0, options))
        .map_err(|e| e.python(py, &options.entry))?;
    super::export(py, &result, target)
}
#[pyfunction]
fn _pldt_nat_collision(py: Python<'_>, source: PySeries) -> PyResult<Option<usize>> {
    if source.0.dtype() == &DataType::Date {
        return Ok(None);
    }
    let dates = source.0.datetime().map_err(super::eager_error)?;
    Ok(py.detach(|| {
        dates
            .physical()
            .iter()
            .position(|value| value == Some(i64::MIN))
    }))
}
/// Explicit host-only outputs. Dynamic timezone carriers preserve the actual
/// UTC instant against the host's timezone database; workers never use them.
#[pyfunction]
fn _pldt_python_output<'py>(
    py: Python<'py>,
    source: PySeries,
    class: &Bound<'py, PyAny>,
    zone: &Bound<'py, PyAny>,
    clock: bool,
) -> PyResult<Bound<'py, PyList>> {
    let key = match source.0.dtype() {
        DataType::Datetime(_, key) => key.as_ref(),
        DataType::Date => None,
        _ => {
            return Err(crate::error_context::type_error(
                "Python output requires Date or Datetime",
            ));
        }
    };
    let native_zone = key
        .map(|key| Zone::named(key.as_str()))
        .transpose()
        .map_err(|e| Failure::new(Kind::Value, e).python(py, "Pldt.datetime"))?;
    let fixed = native_zone.as_ref().map_or(Some(0), Zone::fixed_seconds);
    let quantum = match source.0.dtype() {
        DataType::Date => DAY,
        DataType::Datetime(unit, _) => super::input::epoch_unit(*unit).nanos(),
        _ => unreachable!(),
    };
    if source.0.dtype() == &DataType::Date {
        python_objects(
            py,
            source
                .0
                .date()
                .map_err(super::eager_error)?
                .physical()
                .iter()
                .map(|v| v.map(|v| i128::from(v) * quantum)),
            class,
            zone,
            fixed,
            clock,
        )
    } else {
        python_objects(
            py,
            source
                .0
                .datetime()
                .map_err(super::eager_error)?
                .physical()
                .iter()
                .map(|v| v.map(|v| i128::from(v) * quantum)),
            class,
            zone,
            fixed,
            clock,
        )
    }
}
fn python_objects<'py>(
    py: Python<'py>,
    values: impl Iterator<Item = Option<i128>>,
    class: &Bound<'py, PyAny>,
    zone: &Bound<'py, PyAny>,
    fixed: Option<i32>,
    clock: bool,
) -> PyResult<Bound<'py, PyList>> {
    let output = PyList::empty(py);
    let entry = if clock {
        "Pldt.timetz"
    } else {
        "Pldt.datetime"
    };
    for (row, value) in values.enumerate() {
        let result = (|| -> PyResult<()> {
            let Some(instant) = value else {
                output.append(py.None())?;
                return Ok(());
            };
            let carrier = if fixed.is_none() {
                Some(crate::host_zone::utc_local(instant, zone)?.0)
            } else {
                None
            };
            if clock {
                if let Some(carrier) = carrier {
                    output.append(carrier.call_method0("timetz")?)?;
                } else {
                    let wall = instant + i128::from(fixed.unwrap_or(0)) * 1_000_000_000;
                    let time = wall.rem_euclid(DAY);
                    output.append(PyTime::new_with_fold(
                        py,
                        (time / 3_600_000_000_000) as u8,
                        (time / 60_000_000_000 % 60) as u8,
                        (time / 1_000_000_000 % 60) as u8,
                        (time / 1000 % 1_000_000) as u32,
                        if zone.is_none() {
                            None
                        } else {
                            Some(zone.cast::<PyTzInfo>()?)
                        },
                        false,
                    )?)?;
                }
            } else if let Some(carrier) = carrier {
                output.append(crate::pydt::_pydt_from_instant(&carrier)?)?;
            } else {
                let wall = instant + i128::from(fixed.unwrap_or(0)) * 1_000_000_000;
                let f = crate::parser::objects::wide_microsecond_fields(wall.div_euclid(1000))?;
                if !(1..=9999).contains(&f[0]) {
                    return Err(crate::error_context::overflow(
                        "Python datetime output requires years 1 through 9999",
                    ));
                }
                let value = crate::pydt::try_from_fields(class, f, zone, 0)?.ok_or_else(|| {
                    crate::error_context::runtime("Pydt output type is unavailable")
                })?;
                output.append(value)?;
            }
            Ok(())
        })();
        result
            .map_err(|e| crate::error_context::location(py, e, entry, &format!("data[{row}]")))?;
    }
    Ok(output)
}
fn check_numpy_date_match(
    source: Option<i128>,
    target: Option<i128>,
    row: usize,
) -> Result<(), Failure> {
    if source == target {
        Ok(())
    } else {
        Err(Failure::new(
            if target.is_none() && source.is_some() {
                Kind::Capacity
            } else {
                Kind::Value
            },
            "requested NumPy dtype cannot preserve the date value, precision or missing position",
        )
        .at(row))
    }
}

/// Compare actual date bits without repeating the target dtype/unit dispatch.
/// Calendar units retain their scalar decoder; linear units prepare it once.
fn check_numpy_date_values(
    source: &Series,
    code: i32,
    multiplier: i32,
    mut raw_at: impl FnMut(usize) -> Result<i64, Failure>,
) -> Result<(), Failure> {
    if (-3..=-1).contains(&code) {
        let denominator = 10_i128.pow((-code * 3) as u32);
        return super::input::visit_nanos(source, |row, value| {
            let raw = raw_at(row)?;
            let equal = match value {
                None => raw == i64::MIN,
                Some(nanos) => {
                    raw != i64::MIN
                        && i128::from(raw) * i128::from(multiplier) == nanos * denominator
                }
            };
            if equal {
                Ok(())
            } else {
                Err(Failure::new(
                    Kind::Capacity,
                    "requested subnanosecond NumPy dtype cannot preserve the date within int64 capacity",
                )
                .at(row))
            }
        });
    }
    let scale = if multiplier > 0 && matches!(code, 2 | 4..=10) {
        Some(
            crate::epoch::native_datetime_ticks(1, code, multiplier)
                .map_err(|e| Failure::new(Kind::Capacity, e.to_string()))?
                .nanos,
        )
    } else {
        None
    };
    if let Some(scale) = scale.and_then(|value| i64::try_from(value).ok()) {
        return super::input::visit_nanos(source, |row, value| {
            let raw = raw_at(row)?;
            // The product of two signed64 values always fits signed128.
            // Widen both operands first; no per-row overflow check is needed.
            let target = (raw != i64::MIN).then(|| i128::from(raw) * i128::from(scale));
            check_numpy_date_match(value, target, row)
        });
    }
    super::input::visit_nanos(source, |row, value| {
        let raw = raw_at(row)?;
        let target = if raw == i64::MIN {
            None
        } else if let Some(nanos) = scale.and_then(|scale| i128::from(raw).checked_mul(scale)) {
            Some(nanos)
        } else {
            // This is also the cold linear-overflow path, preserving the
            // scalar decoder's exact error rather than inventing a new one.
            Some(
                crate::epoch::native_datetime_ticks(raw, code, multiplier)
                    .map_err(|e| Failure::new(Kind::Capacity, e.to_string()))?
                    .nanos,
            )
        };
        check_numpy_date_match(value, target, row)
    })
}

/// Validate an explicitly requested NumPy dtype against real source values.
/// Native dtype conversion has already run; this does not replace its protocol.
#[pyfunction]
fn _pldt_check_numpy(
    py: Python<'_>,
    source: PySeries,
    target: PySeries,
    numpy: Option<(i32, i32)>,
) -> PyResult<()> {
    if source.0.len() != target.0.len() {
        return Err(crate::error_context::value_error(
            "NumPy output changed the date column length",
        ));
    }
    let quantum = match source.0.dtype() {
        DataType::Date => DAY,
        DataType::Datetime(unit, _) => super::input::epoch_unit(*unit).nanos(),
        _ => {
            return Err(crate::error_context::type_error(
                "expected a temporal source",
            ));
        }
    };
    if source.0.is_empty() {
        return Ok(());
    }
    py.detach(|| {
        if let Some((code, multiplier)) = numpy {
            if let Ok(values) = target.0.i64() {
                if values.null_count() == 0 {
                    let mut values = values.into_no_null_iter();
                    return check_numpy_date_values(&source.0, code, multiplier, |_| {
                        // Equal lengths and native chunk iterators prove a
                        // value for every source row, without a random lookup.
                        Ok(values.next().unwrap_or(i64::MIN))
                    });
                }
                let mut values = values.iter();
                return check_numpy_date_values(&source.0, code, multiplier, |_| {
                    Ok(values.next().flatten().unwrap_or(i64::MIN))
                });
            }
            // Preserve the prior Null/invalid-target and lazy error behavior
            // for private callers outside the real int64 NumPy output path.
            return check_numpy_date_values(&source.0, code, multiplier, |row| {
                match target.0.get(row).map_err(|e| Failure::new(Kind::Value, e.to_string()))? {
                    AnyValue::Int64(value) => Ok(value),
                    AnyValue::Null => Ok(i64::MIN),
                    _ => Err(Failure::new(Kind::Type, "expected actual NumPy datetime64 bits")),
                }
            });
        }
        super::input::visit_nanos(&source.0, |row, value| {
            let actual=target.0.get(row).map_err(|e|Failure::new(Kind::Value,e.to_string()))?;
            let Some(nanos)=value else{return Err(Failure::new(Kind::Value,"requested numeric NumPy dtype cannot preserve a missing date; keep datetime64 or use an explicit object output").at(row));};
            let expected=nanos/quantum;
            let equal=match actual{
                AnyValue::Int8(v)=>i128::from(v)==expected,AnyValue::Int16(v)=>i128::from(v)==expected,AnyValue::Int32(v)=>i128::from(v)==expected,AnyValue::Int64(v)=>i128::from(v)==expected,
                AnyValue::UInt8(v)=>i128::from(v)==expected,AnyValue::UInt16(v)=>i128::from(v)==expected,AnyValue::UInt32(v)=>i128::from(v)==expected,AnyValue::UInt64(v)=>i128::from(v)==expected,
                AnyValue::Float32(v)=>v.is_finite()&&v.fract()==0.0&&(v as i128)==expected,
                AnyValue::Float64(v)=>v.is_finite()&&v.fract()==0.0&&(v as i128)==expected,
                _=>false,
            };
            if !equal{return Err(Failure::new(Kind::Value,"requested NumPy dtype cannot preserve the complete date tick").at(row));}
            Ok(())
        })
    }).map_err(|e|e.python(py,"Pldt.__array__"))
}
/// Validate actual Arrow/pandas temporal metadata and its independent validity.
#[pyfunction]
fn _pldt_check_temporal(
    py: Python<'_>,
    source: PySeries,
    target: PySeries,
    allow: Truth,
) -> PyResult<()> {
    if source.0.len() != target.0.len() {
        return Err(crate::error_context::value_error(
            "pandas output changed the date column length",
        ));
    }
    let quantum = match target.0.dtype() {
        DataType::Date => DAY,
        DataType::Datetime(unit, _) => super::input::epoch_unit(*unit).nanos(),
        _ => {
            return Err(crate::error_context::type_error(
                "actual pandas result does not have a supported temporal representation",
            ));
        }
    };
    // The actual pandas result may expose ordinary writable storage. Read that
    // host-owned representation while attached, then detach only with our own
    // complete values/validity snapshot. Ownership alone does not freeze aliases.
    let mut values = Vec::with_capacity(target.0.len());
    super::input::visit_nanos(&target.0, |_, value| {
        values.push(value);
        Ok(())
    })
    .map_err(|e| e.python(py, "Pldt.to_pandas"))?;
    py.detach(||{
        super::input::visit_nanos(&source.0,|row,value|{
            let actual=values[row];
            if value==actual||allow.0&&actual.is_none()&&value==Some(i128::from(i64::MIN)*quantum){return Ok(());}
            let error=if actual.is_none()&&value.is_some(){Kind::Capacity}else{Kind::Value};
            Err(Failure::new(error,"actual pandas output cannot preserve the date value, precision or validity; use an Arrow-backed datetime representation").at(row))
        })
    }).map_err(|e|e.python(py,"Pldt.to_pandas"))
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_output_prepare, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_output, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_nat_collision, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_check_numpy, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_check_temporal, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_python_output, module)?)
}

#[cfg(test)]
mod numpy_guard_tests {
    use super::*;

    fn dates(values: &[Option<i64>]) -> Series {
        Int64Chunked::from_slice_options("time".into(), values)
            .into_datetime(TimeUnit::Nanoseconds, None)
            .into_series()
    }

    #[test]
    fn linear_target_keeps_negative_ticks_nulls_and_multiplier() {
        let source = dates(&[Some(-2000), None, Some(0), Some(2000)]);
        let raw = [-1, i64::MIN, 0, 1];
        assert!(check_numpy_date_values(&source, 9, 2, |row| Ok(raw[row])).is_ok());
    }

    #[test]
    fn linear_target_rejects_fractional_ticks_at_the_first_row() {
        let source = dates(&[Some(0), Some(-1001), Some(2001)]);
        let raw = [0, -2, 2];
        let error = check_numpy_date_values(&source, 9, 1, |row| Ok(raw[row])).unwrap_err();
        assert!(matches!(error.kind, Kind::Value));
        assert_eq!(error.row, Some(1));
    }

    #[test]
    fn valid_date_cannot_become_the_numpy_nat_tick() {
        let source = dates(&[Some(0)]);
        let error = check_numpy_date_values(&source, 9, 1, |_| Ok(i64::MIN)).unwrap_err();
        assert!(matches!(error.kind, Kind::Capacity));
        assert_eq!(error.row, Some(0));
    }

    #[test]
    fn all_nulls_keep_lazy_invalid_unit_decoder_behavior() {
        let source = dates(&[None, None]);
        assert!(check_numpy_date_values(&source, 9, 0, |_| Ok(i64::MIN)).is_ok());
    }

    #[test]
    fn subnanosecond_target_preserves_exact_values_and_missing_positions() {
        let source = dates(&[Some(-1), None, Some(1)]);
        let raw = [-1000, i64::MIN, 1000];
        assert!(check_numpy_date_values(&source, -1, 1, |row| Ok(raw[row])).is_ok());
    }
}
