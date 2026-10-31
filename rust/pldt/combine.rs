//! Native date/clock pieces, exact positional shape, and one final composition.
use super::finish::{Failure, Kind, Rows, fields_nanos};
use super::zones::{Context, Policies, PolicyContext, prepare_host_zone};
use crate::batch_shape::{Column, length};
use crate::date_parts::{Piece, Reader};
use crate::epoch::{Unit, Zone as HostZone};
use crate::parser::config::NativeRules;
use crate::parser::fields::{Lenient, Nano, Precision};
use crate::parser::native;
use crate::temporal_zone::{Zone, ZoneData};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::{Deserialize, Serialize};
const NS_DAY: i128 = 86_400_000_000_000;
#[derive(Clone)]
enum SourceZone {
    Naive,
    Offset(i64),
    Region(Zone),
}
#[derive(Serialize, Deserialize)]
enum WireZone {
    Naive,
    Offset(i64),
    Region(ZoneData),
}
impl SourceZone {
    fn snapshot(&self) -> WireZone {
        match self {
            Self::Naive => WireZone::Naive,
            Self::Offset(value) => WireZone::Offset(*value),
            Self::Region(zone) => WireZone::Region(zone.snapshot()),
        }
    }
}
#[pyclass(frozen, skip_from_py_object, name = "_PldtParts")]
struct Parts {
    values: Column<Option<Piece>>,
    zones: Vec<SourceZone>,
    today: bool,
    declared: Option<usize>,
    nano: bool,
}
impl Parts {
    fn new(
        scalar: bool,
        values: Vec<Option<Piece>>,
        zones: Vec<SourceZone>,
        declared: Option<usize>,
    ) -> Result<Self, Failure> {
        let nano = values
            .iter()
            .flatten()
            .any(|value| value.value.rem_euclid(1000) != 0);
        let values = if scalar {
            if values.len() != 1 {
                return Err(Failure::new(
                    Kind::Runtime,
                    "a scalar component must contain one value",
                ));
            }
            Column::Scalar(values[0])
        } else {
            Column::Values(values)
        };
        Ok(Self {
            values,
            zones,
            today: false,
            declared,
            nano,
        })
    }
}
#[pymethods]
impl Parts {
    /// Owned clock values and zone IDs remain ordinary native Expr operands.
    fn expression<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<(PySeries, PySeries, Bound<'py, PyDict>)> {
        let (values, scalar) = match &self.values {
            Column::Scalar(value) => (std::slice::from_ref(value), true),
            Column::Values(values) => (values.as_slice(), false),
        };
        let mut clocks = Vec::with_capacity(values.len());
        let mut ids = Vec::with_capacity(values.len());
        for value in values {
            clocks.push(
                value
                    .map(|value| {
                        i64::try_from(value.value)
                            .map_err(|_| crate::error_context::overflow("clock exceeds one day"))
                    })
                    .transpose()?,
            );
            ids.push(
                value
                    .map(|value| {
                        u32::try_from(value.zone).map_err(|_| {
                            crate::error_context::overflow("too many distinct source zones")
                        })
                    })
                    .transpose()?,
            );
        }
        let snapshots = self
            .zones
            .iter()
            .map(SourceZone::snapshot)
            .collect::<Vec<_>>();
        let encoded = serde_json::to_vec(&snapshots)
            .map_err(|error| crate::error_context::runtime(error.to_string()))?;
        let declared = if let Some(declared) = self.declared {
            Some(declared)
        } else {
            let keys = self
                .zones
                .iter()
                .map(source_key)
                .collect::<Result<Vec<_>, _>>()
                .map_err(|error| error.python(py, "Pldt.combine"))?;
            let mut selected = None;
            for value in values.iter().flatten() {
                let current = keys
                    .get(value.zone)
                    .ok_or_else(|| crate::error_context::runtime("clock source zone was lost"))?;
                if selected.is_some_and(|previous: usize| keys[previous] != *current) {
                    return Err(crate::error_context::value_error(
                        "a concrete clock collection with different source timezones needs an explicit tz for Expr output",
                    ));
                }
                selected = Some(value.zone);
            }
            selected
        };
        let kwargs = PyDict::new(py);
        kwargs.set_item("zones", PyBytes::new(py, &encoded))?;
        kwargs.set_item("unit", if self.nano { "ns" } else { "us" })?;
        kwargs.set_item("scalar", scalar)?;
        kwargs.set_item("declared", declared)?;
        Ok((
            PySeries(
                Int64Chunked::from_iter_options("clock".into(), clocks.into_iter()).into_series(),
            ),
            PySeries(
                UInt32Chunked::from_iter_options("zone".into(), ids.into_iter()).into_series(),
            ),
            kwargs,
        ))
    }
}
fn source_key(zone: &SourceZone) -> Result<Option<String>, Failure> {
    match zone {
        SourceZone::Naive => Ok(None),
        SourceZone::Region(zone) => Ok(Some(zone.key().to_owned())),
        SourceZone::Offset(offset) => {
            if *offset == 0 {
                return Ok(Some("UTC".into()));
            }
            if offset % 3_600_000_000 != 0 {
                return Err(Failure::new(
                    Kind::Value,
                    "source fixed offset cannot be represented by Polars; pass explicit tz",
                ));
            }
            Ok(Some(format!(
                "Etc/GMT{}{}",
                if *offset > 0 { "-" } else { "+" },
                offset.unsigned_abs() / 3_600_000_000
            )))
        }
    }
}

fn host_zone(py: Python<'_>, zone: &HostZone) -> PyResult<SourceZone> {
    if matches!(zone, HostZone::Naive) {
        return Ok(SourceZone::Naive);
    }
    if let Some(offset) = crate::date_input::fixed_offset(py, zone)? {
        return Ok(SourceZone::Offset(offset));
    }
    match zone {
        HostZone::Naive => Ok(SourceZone::Naive),
        HostZone::Offset(value) => Ok(SourceZone::Offset(*value)),
        HostZone::Object(value) => prepare_host_zone(value.bind(py)).map(SourceZone::Region),
    }
}
#[pyfunction]
#[pyo3(signature=(data,resolver,clock,column,keep_zone))]
fn _pldt_parts_objects(
    data: &Bound<'_, PyAny>,
    resolver: &Bound<'_, PyAny>,
    clock: bool,
    column: bool,
    keep_zone: bool,
) -> PyResult<Parts> {
    let py = data.py();
    let parameter = if clock { "time" } else { "date" };
    let scalar = !column
        && (crate::numeric_epoch::scalar(data)? || data.is_instance_of::<pyo3::types::PyTime>());
    let mut reader = Reader::new(clock, resolver);
    let today = scalar && data.is_none() && !clock;
    let mut values = Vec::new();
    if scalar {
        values.push(if data.is_none() {
            Some(Piece { value: 0, zone: 0 })
        } else {
            reader.read(data).map_err(|error| {
                crate::error_context::argument(py, error, "Pldt.combine", parameter, data)
            })?
        });
    } else {
        for (row, value) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let value = value
                .map_err(crate::error_context::external)
                .map_err(|error| {
                    crate::error_context::item(
                        py,
                        error,
                        "Pldt.combine",
                        parameter,
                        row,
                        None,
                        true,
                    )
                })?;
            values.push(reader.read(&value).map_err(|error| {
                crate::error_context::item(
                    py,
                    error,
                    "Pldt.combine",
                    parameter,
                    row,
                    Some(&value),
                    false,
                )
            })?);
        }
    }
    let declared = if clock && scalar {
        values[0].map(|value| value.zone)
    } else {
        None
    };
    let zones = if clock && keep_zone {
        reader
            .zones
            .iter()
            .map(|zone| host_zone(py, zone))
            .collect::<PyResult<Vec<_>>>()?
    } else {
        for value in values.iter_mut().flatten() {
            value.zone = 0;
        }
        vec![SourceZone::Naive]
    };
    let mut result = Parts::new(
        scalar,
        values,
        zones,
        if keep_zone { declared } else { None },
    )
    .map_err(|error| error.python(py, "Pldt.combine"))?;
    result.today = today;
    Ok(result)
}
fn part_dtype(dtype: &DataType, clock: bool) -> bool {
    matches!(
        dtype,
        DataType::Date
            | DataType::Datetime(_, _)
            | DataType::Null
            | DataType::String
            | DataType::Float32
            | DataType::Float64
    ) || dtype.is_integer()
        || (clock && dtype == &DataType::Time)
}
fn native_parts(
    source: &Series,
    clock: bool,
    scalar: bool,
    keep_zone: bool,
) -> Result<Parts, Failure> {
    if !part_dtype(source.dtype(), clock) {
        return Err(Failure::new(
            Kind::Type,
            "unsupported date/clock dtype; Time is only a clock, Boolean/Duration are not dates",
        ));
    }
    let mut zones = vec![SourceZone::Naive];
    let mut declared = None;
    let native_zone = match source.dtype() {
        DataType::Datetime(_, Some(key)) => {
            Some(Zone::named(key.as_str()).map_err(|message| Failure::new(Kind::Value, message))?)
        }
        _ => None,
    };
    if clock
        && keep_zone
        && let Some(zone) = &native_zone
    {
        zones.push(SourceZone::Region(zone.clone()));
        declared = Some(1);
    }
    let source_id = declared.unwrap_or(0);
    let mut values = Vec::with_capacity(source.len());
    let mut add = |ns: Option<i128>, zone: usize| {
        values.push(ns.map(|value| Piece {
            value: if clock {
                value.rem_euclid(NS_DAY)
            } else {
                value.div_euclid(NS_DAY)
            },
            zone: if clock && keep_zone { zone } else { 0 },
        }));
    };
    match source.dtype() {
        DataType::Null => values.resize(source.len(), None),
        DataType::Date => {
            for value in source
                .date()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .physical()
                .iter()
            {
                add(value.map(|value| i128::from(value) * NS_DAY), 0);
            }
        }
        DataType::Datetime(unit, _) => {
            let scale = super::input::epoch_unit(*unit).nanos();
            for (row, value) in source
                .datetime()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                let wall = value
                    .map(|value| {
                        let value = i128::from(value) * scale;
                        if let Some(zone) = &native_zone {
                            zone.wall(value)
                                .map_err(|error| Failure::from(error).at(row))
                        } else {
                            Ok(value)
                        }
                    })
                    .transpose()?;
                add(wall, source_id);
            }
        }
        DataType::Time => {
            return Err(Failure::new(
                Kind::Runtime,
                "Time input requires its original physical clock buffer before SDK normalization",
            ));
        }
        DataType::String => {
            let mut rules = NativeRules::library();
            let mut scratch = Vec::new();
            let mut offsets = std::collections::HashMap::new();
            let mut regions = std::collections::HashMap::new();
            for (row, value) in source
                .str()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                let Some(value) = value.filter(|value| !super::text::missing(value)) else {
                    values.push(None);
                    continue;
                };
                let parsed = native::parse::<Nano<Lenient>>(
                    value,
                    &mut scratch,
                    &mut rules,
                    native::Options {
                        default: clock.then_some([1970, 1, 1]),
                        yearfirst: None,
                        dayfirst: None,
                        isoformat: true,
                    },
                )
                .map_err(|error| Failure::new(Kind::Parse, error.to_string()).at(row))?;
                let ns = fields_nanos(
                    parsed.completed.map(i64::from),
                    i64::from(parsed.fields.fraction.tail()),
                )
                .map_err(|error| error.at(row))?;
                let zone = if clock && keep_zone {
                    if let Some(region) = parsed.region {
                        if !region.available {
                            return Err(Failure::new(
                                Kind::Value,
                                "registered source region is unavailable",
                            )
                            .at(row));
                        }
                        if let Some(offset) = region.fixed_offset_us {
                            *offsets.entry(offset).or_insert_with(|| {
                                zones.push(SourceZone::Offset(offset));
                                zones.len() - 1
                            })
                        } else if let Some(&index) = regions.get(region.key.as_str()) {
                            index
                        } else {
                            let zone = Zone::named(&region.key)
                                .map_err(|message| Failure::new(Kind::Value, message).at(row))?;
                            zones.push(SourceZone::Region(zone));
                            let index = zones.len() - 1;
                            regions.insert(region.key.clone(), index);
                            index
                        }
                    } else if parsed.fields.is_tzoffset_set() {
                        let offset = parsed.fields.timezone_microseconds();
                        *offsets.entry(offset).or_insert_with(|| {
                            zones.push(SourceZone::Offset(offset));
                            zones.len() - 1
                        })
                    } else {
                        0
                    }
                } else {
                    0
                };
                values.push(Some(Piece {
                    value: if clock {
                        ns.rem_euclid(NS_DAY)
                    } else {
                        ns.div_euclid(NS_DAY)
                    },
                    zone,
                }));
            }
        }
        dtype if dtype.is_integer() => {
            let cast = source
                .strict_cast(&DataType::Int128)
                .map_err(|error| Failure::new(Kind::Capacity, error.to_string()))?;
            for (row, value) in cast
                .i128()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                add(
                    value
                        .map(|value| {
                            value.checked_mul(1_000_000_000).ok_or_else(|| {
                                Failure::new(Kind::Capacity, "numeric seconds exceed native range")
                                    .at(row)
                            })
                        })
                        .transpose()?,
                    0,
                );
            }
        }
        DataType::Float32 | DataType::Float64 => {
            let cast = source
                .strict_cast(&DataType::Float64)
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?;
            for (row, value) in cast
                .f64()
                .map_err(|error| Failure::new(Kind::Type, error.to_string()))?
                .iter()
                .enumerate()
            {
                let ns = value
                    .map(|value| {
                        crate::numeric_epoch::float_number(
                            value,
                            crate::numeric_epoch::Quantity::Seconds,
                        )
                        .map_err(|_| {
                            Failure::new(Kind::Capacity, "numeric seconds exceed native range")
                                .at(row)
                        })
                    })
                    .transpose()?
                    .flatten();
                add(ns, 0);
            }
        }
        _ => {
            return Err(Failure::new(
                Kind::Runtime,
                "validated date/clock dtype was lost",
            ));
        }
    }
    Parts::new(scalar, values, zones, declared)
}
fn time_parts(source: &Series, scalar: bool) -> Result<Parts, Failure> {
    let values = source
        .i64()
        .map_err(|error| Failure::new(Kind::Type, error.to_string()))?;
    let mut output = Vec::with_capacity(values.len());
    for (row, value) in values.iter().enumerate() {
        if value.is_some_and(|value| !(0..NS_DAY).contains(&i128::from(value))) {
            return Err(
                Failure::new(Kind::Value, "a native Time clock must be within one day").at(row),
            );
        }
        output.push(value.map(|value| Piece {
            value: i128::from(value),
            zone: 0,
        }));
    }
    Parts::new(scalar, output, vec![SourceZone::Naive], None)
}
#[pyfunction]
fn _pldt_parts_time(py: Python<'_>, physical: PySeries) -> PyResult<Parts> {
    time_parts(&physical.0, false).map_err(|error| error.python(py, "Pldt.combine"))
}

#[pyfunction]
fn _pldt_parts_column(
    py: Python<'_>,
    source: PySeries,
    clock: bool,
    keep_zone: bool,
) -> PyResult<Parts> {
    native_parts(&source.0, clock, false, keep_zone)
        .map_err(|error| error.python(py, "Pldt.combine"))
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Real sentinel date buffer with local source metadata"
)]
fn _pldt_parts_buffer(
    py: Python<'_>,
    source: PySeries,
    clock: bool,
    code: i32,
    multiplier: i32,
    source_zone: Option<PyRef<'_, Context>>,
    offset_us: Option<i64>,
    keep_zone: bool,
) -> PyResult<Parts> {
    let mut zones = vec![SourceZone::Naive];
    let id = if clock && keep_zone {
        if let Some(zone) = source_zone.as_ref() {
            zones.push(SourceZone::Region(zone.value.clone()));
            1
        } else if let Some(offset) = offset_us {
            zones.push(SourceZone::Offset(offset));
            1
        } else {
            0
        }
    } else {
        0
    };
    let mut values = Vec::with_capacity(source.0.len());
    for (row, value) in source
        .0
        .i64()
        .map_err(|error| crate::error_context::type_error(error.to_string()))?
        .iter()
        .enumerate()
    {
        let Some(value) = value.filter(|value| *value != i64::MIN) else {
            values.push(None);
            continue;
        };
        let mut ns = crate::epoch::native_datetime_ticks(value, code, multiplier)?.nanos;
        ns = if let Some(zone) = source_zone.as_ref() {
            zone.value
                .wall(ns)
                .map_err(|error| Failure::from(error).at(row).python(py, "Pldt.combine"))?
        } else {
            ns + i128::from(offset_us.unwrap_or(0)) * 1000
        };
        values.push(Some(Piece {
            value: if clock {
                ns.rem_euclid(NS_DAY)
            } else {
                ns.div_euclid(NS_DAY)
            },
            zone: id,
        }));
    }
    Parts::new(false, values, zones, (id != 0).then_some(id))
        .map_err(|error| error.python(py, "Pldt.combine"))
}

fn source_id(rows: &mut Rows, zone: &SourceZone) -> Result<usize, Failure> {
    match zone {
        SourceZone::Naive => Ok(0),
        SourceZone::Offset(value) => rows.offset(*value),
        SourceZone::Region(zone) => rows.zone(zone.clone()),
    }
}
#[expect(
    clippy::too_many_arguments,
    reason = "Independent date/clock roles and lazy local day before one final output"
)]
fn calculate(
    date: &Parts,
    time: &Parts,
    size: Option<usize>,
    name: PlSmallStr,
    requested: Option<Unit>,
    target: Option<&Zone>,
    policy: &Policies,
    mut local_day: impl FnMut() -> Result<i128, Failure>,
) -> Result<Series, Failure> {
    let len = length([date.values.len(), time.values.len()], size)
        .map_err(|message| Failure::new(Kind::Value, message))?;
    policy.check_len(len)?;
    let mut rows = Rows::new(if time.nano {
        Unit::Nanosecond
    } else {
        Unit::Microsecond
    });
    let ids = if target.is_some() {
        vec![0; time.zones.len()]
    } else {
        time.zones
            .iter()
            .map(|zone| source_id(&mut rows, zone))
            .collect::<Result<Vec<_>, _>>()?
    };
    if let Some(zone) = time.declared {
        rows.inherit_zone(
            *ids.get(zone)
                .ok_or_else(|| Failure::new(Kind::Runtime, "invalid declared clock zone"))?,
        );
    }
    let mut today = None;
    let repeat =
        matches!(date.values, Column::Scalar(_)) && matches!(time.values, Column::Scalar(_));
    let iterations = if repeat && len != 0 { 1 } else { len };
    for row in 0..iterations {
        let (Some(day), Some(clock)) = (date.values.get(row), time.values.get(row)) else {
            rows.missing();
            continue;
        };
        let day = if date.today {
            if let Some(day) = today {
                day
            } else {
                let day = local_day()?;
                today = Some(day);
                day
            }
        } else {
            day.value
        };
        let ns = day
            .checked_mul(NS_DAY)
            .and_then(|value| value.checked_add(clock.value))
            .ok_or_else(|| {
                Failure::new(Kind::Capacity, "combined date exceeds native range").at(row)
            })?;
        let zone = *ids
            .get(clock.zone)
            .ok_or_else(|| Failure::new(Kind::Runtime, "clock source zone was lost").at(row))?;
        rows.push(
            ns,
            zone,
            false,
            if clock.value.rem_euclid(1000) != 0 {
                Unit::Nanosecond
            } else {
                Unit::Microsecond
            },
        );
    }
    if repeat && len != 0 {
        rows.repeat(len)?;
    }
    rows.finish(name, requested, target, policy, false)
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared date/clock pieces, lazy local date and final schema"
)]
#[pyo3(signature=(date,time,target,local,size,unit,tz,policy,name))]
fn _pldt_combine<'py>(
    py: Python<'py>,
    date: PyRef<'_, Parts>,
    time: PyRef<'_, Parts>,
    target: &Bound<'py, PyAny>,
    local: &Bound<'py, PyAny>,
    size: Option<usize>,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    policy: PyRef<'_, PolicyContext>,
    name: &str,
) -> PyResult<Bound<'py, PyAny>> {
    let mut external = None;
    let result = calculate(
        &date,
        &time,
        size,
        name.into(),
        super::input::selected(unit)?,
        tz.as_ref().map(|zone| &zone.value),
        &policy.value,
        || {
            (|| -> PyResult<i128> {
                let raw = local.call0().map_err(crate::error_context::external)?;
                let zone = prepare_host_zone(&raw)?;
                let instant = crate::clock::system_nanos(std::time::SystemTime::now())
                    .map_err(crate::error_context::overflow)?;
                zone.wall(instant)
                    .map(|value| value.div_euclid(NS_DAY))
                    .map_err(|error| Failure::from(error).python(py, "Pldt.combine"))
            })()
            .map_err(|error| {
                external = Some(error);
                Failure::new(Kind::Runtime, "local date preparation failed")
            })
        },
    );
    if let Some(error) = external {
        return Err(error);
    }
    let result = result.map_err(|error| error.python(py, "Pldt.combine"))?;
    super::export(py, &result, target)
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Prepared {
    #[serde(deserialize_with = "crate::serde_values::byte_vector")]
    zones: Vec<u8>,
    unit: String,
    scalar: bool,
    declared: Option<usize>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    unit: Option<String>,
    target: Option<ZoneData>,
    policy: Policies,
    date_scalar: bool,
    clock_scalar: bool,
    mask_scalar: bool,
    prepared: Option<Prepared>,
}
fn chosen(
    unit: Option<&str>,
    clock: &DataType,
    prepared: Option<&Prepared>,
) -> Result<Unit, Failure> {
    if let Some(unit) = unit {
        return match unit {
            "ms" => Ok(Unit::Millisecond),
            "us" => Ok(Unit::Microsecond),
            "ns" => Ok(Unit::Nanosecond),
            _ => Err(Failure::new(Kind::Value, "unit must be ms/us/ns")),
        };
    }
    if let Some(prepared) = prepared {
        return Ok(if prepared.unit == "ns" {
            Unit::Nanosecond
        } else {
            Unit::Microsecond
        });
    }
    match clock {
        DataType::Datetime(TimeUnit::Milliseconds | TimeUnit::Microseconds, _)
        | DataType::Date
        | DataType::Null => Ok(Unit::Microsecond),
        dtype if dtype.is_integer() => Ok(Unit::Microsecond),
        _ => Err(Failure::new(
            Kind::Value,
            "a Time/Datetime(ns)/String/floating clock Expr requires an explicit unit to determine output precision",
        )),
    }
}
fn declared_key(prepared: &Prepared) -> Result<Option<String>, Failure> {
    let zones: Vec<WireZone> = serde_json::from_slice(&prepared.zones)
        .map_err(|error| Failure::new(Kind::Runtime, error.to_string()))?;
    let Some(index) = prepared.declared else {
        return Ok(None);
    };
    match zones.get(index) {
        Some(WireZone::Naive) => Ok(None),
        Some(WireZone::Region(zone)) => Ok(Some(zone.key.clone())),
        Some(WireZone::Offset(offset)) => {
            if *offset == 0 {
                return Ok(Some("UTC".into()));
            }
            if offset % 3_600_000_000 != 0 {
                return Err(Failure::new(
                    Kind::Value,
                    "source fixed offset cannot be represented by Polars; pass explicit tz",
                ));
            }
            Ok(Some(format!(
                "Etc/GMT{}{}",
                if *offset > 0 { "-" } else { "+" },
                offset.unsigned_abs() / 3_600_000_000
            )))
        }
        None => Err(Failure::new(
            Kind::Runtime,
            "invalid prepared clock metadata",
        )),
    }
}
fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    let count = 3;
    polars_ensure!(kwargs.version==1&&(fields.len()==count||fields.len()==count+1),InvalidOperation:"Pldt.combine: invalid prepared inputs");
    polars_ensure!(part_dtype(fields[0].dtype(),false),InvalidOperation:"Pldt.combine: unsupported date dtype");
    if kwargs.prepared.is_none() {
        polars_ensure!(part_dtype(fields[1].dtype(),true),InvalidOperation:"Pldt.combine: unsupported clock dtype");
    }
    if let Some(mask) = fields.get(count) {
        polars_ensure!(mask.dtype()==&DataType::Boolean,InvalidOperation:"ambiguous Expr requires Boolean");
    }
    let unit = chosen(
        kwargs.unit.as_deref(),
        fields[1].dtype(),
        kwargs.prepared.as_ref(),
    )
    .map_err(|error| error.polars("Pldt.combine"))?;
    let zone = if let Some(zone) = kwargs.target {
        Some(zone.key)
    } else if let Some(prepared) = kwargs.prepared {
        declared_key(&prepared).map_err(|error| error.polars("Pldt.combine"))?
    } else {
        match fields[1].dtype() {
            DataType::Datetime(_, zone) => zone.as_ref().map(|zone| zone.to_string()),
            _ => None,
        }
    };
    Ok(Field::new(
        fields[0].name().clone(),
        DataType::Datetime(super::input::resolution(unit), TimeZone::opt_try_new(zone)?),
    ))
}
fn prepared_parts(
    source: &Series,
    indices: &Series,
    prepared: &Prepared,
) -> Result<Parts, Failure> {
    if source.len() != indices.len() {
        return Err(Failure::new(
            Kind::Value,
            "prepared clock and zone lengths differ",
        ));
    }
    let zones: Vec<WireZone> = serde_json::from_slice(&prepared.zones)
        .map_err(|error| Failure::new(Kind::Runtime, error.to_string()))?;
    let zones = zones
        .into_iter()
        .map(|zone| match zone {
            WireZone::Naive => Ok(SourceZone::Naive),
            WireZone::Offset(value) => Ok(SourceZone::Offset(value)),
            WireZone::Region(zone) => Zone::from_data(zone)
                .map(SourceZone::Region)
                .map_err(|message| Failure::new(Kind::Value, message)),
        })
        .collect::<Result<Vec<_>, _>>()?;
    let source = source
        .i64()
        .map_err(|error| Failure::new(Kind::Type, error.to_string()))?;
    let indices = indices
        .u32()
        .map_err(|error| Failure::new(Kind::Type, error.to_string()))?;
    let mut values = Vec::with_capacity(source.len());
    for (row, (value, zone)) in source.iter().zip(indices.iter()).enumerate() {
        values.push(match (value, zone) {
            (Some(value), Some(zone)) => {
                if !(0..NS_DAY).contains(&i128::from(value)) || zone as usize >= zones.len() {
                    return Err(Failure::new(
                        Kind::Runtime,
                        "prepared clock value/zone is invalid",
                    )
                    .at(row));
                }
                Some(Piece {
                    value: i128::from(value),
                    zone: zone as usize,
                })
            }
            (None, None) => None,
            _ => {
                return Err(
                    Failure::new(Kind::Runtime, "prepared clock validity is inconsistent").at(row),
                );
            }
        });
    }
    Parts::new(prepared.scalar, values, zones, prepared.declared)
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_combine(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    let count = 3;
    polars_ensure!(kwargs.version==1&&(inputs.len()==count||inputs.len()==count+1),InvalidOperation:"Pldt.combine: invalid native inputs");
    let unit = chosen(
        kwargs.unit.as_deref(),
        inputs[1].dtype(),
        kwargs.prepared.as_ref(),
    )
    .map_err(|error| error.polars("Pldt.combine"))?;
    let target = kwargs
        .target
        .map(Zone::from_data)
        .transpose()
        .map_err(|message| polars_err!(ComputeError:"Pldt.combine: {}",message))?;
    let policy = if let Some(mask) = inputs.get(count) {
        kwargs
            .policy
            .with_expression_mask(mask, kwargs.mask_scalar)
            .map_err(|error| polars_err!(ComputeError:"Pldt.combine: {}",error))?
    } else {
        kwargs.policy
    };
    let date = native_parts(&inputs[0], false, kwargs.date_scalar, false)
        .map_err(|error| error.polars("Pldt.combine"))?;
    let clock = if let Some(prepared) = kwargs.prepared {
        prepared_parts(&inputs[1], &inputs[2], &prepared)
    } else if inputs[1].dtype() == &DataType::Time {
        time_parts(&inputs[2], kwargs.clock_scalar)
    } else {
        native_parts(&inputs[1], true, kwargs.clock_scalar, target.is_none())
    }
    .map_err(|error| error.polars("Pldt.combine"))?;
    if target.is_none() && inputs[1].dtype() == &DataType::String && clock.zones.len() > 1 {
        polars_bail!(ComputeError:"Pldt.combine: String clock Expr containing a source timezone requires an explicit tz");
    }
    let size = (kwargs.date_scalar && kwargs.clock_scalar).then_some(1);
    calculate(
        &date,
        &clock,
        size,
        inputs[0].name().clone(),
        Some(unit),
        target.as_ref(),
        &policy,
        || {
            Err(Failure::new(
                Kind::Runtime,
                "Expr date is explicit and cannot query today",
            ))
        },
    )
    .map_err(|error| error.polars("Pldt.combine"))
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_parts_objects, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_parts_column, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_parts_time, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_parts_buffer, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_combine, module)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn invalid_native_time_is_rejected_before_missing_dates_can_hide_it() {
        let source = Int64Chunked::from_vec("clock".into(), vec![-1]).into_series();
        let error = match time_parts(&source, false) {
            Ok(_) => panic!("invalid clock was accepted"),
            Err(error) => error,
        };
        assert!(matches!(error.kind, Kind::Value));
        assert_eq!(error.row, Some(0));
    }
    #[test]
    fn empty_and_missing_clocks_do_not_request_a_local_day() {
        let mut date = Parts::new(
            true,
            vec![Some(Piece { value: 0, zone: 0 })],
            vec![SourceZone::Naive],
            None,
        )
        .unwrap_or_else(|error| panic!("{}", error.message));
        date.today = true;
        let clock = Parts::new(false, vec![None, None], vec![SourceZone::Naive], None)
            .unwrap_or_else(|error| panic!("{}", error.message));
        let policy = Policies::strict();
        let result = calculate(
            &date,
            &clock,
            None,
            "time".into(),
            None,
            None,
            &policy,
            || panic!("missing clock queried today"),
        );
        assert_eq!(
            result
                .unwrap_or_else(|error| panic!("{}", error.message))
                .null_count(),
            2
        );
        let clock = Parts::new(false, Vec::new(), vec![SourceZone::Naive], None)
            .unwrap_or_else(|error| panic!("{}", error.message));
        assert_eq!(
            calculate(
                &date,
                &clock,
                None,
                "time".into(),
                None,
                None,
                &policy,
                || panic!("empty clock queried today")
            )
            .unwrap_or_else(|error| panic!("{}", error.message))
            .len(),
            0
        );
    }
}
