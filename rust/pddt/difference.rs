//! Exact boundary counts, with once-prepared native scalar or positional targets.
use super::arguments::Column;
use super::common::{missing_mask, vector};
use crate::epoch::{Options, Unit};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};

use crate::boundary_count::{BoundaryIndex, Bucket, CalendarIndex, FixedIndex, TickBucket};
use crate::temporal_target::{Date, domain, read};
impl From<crate::boundary_count::Error> for PyErr {
    fn from(error: crate::boundary_count::Error) -> Self {
        match error {
            crate::boundary_count::Error::Value(message) => {
                crate::error_context::value_error(message)
            }
            crate::boundary_count::Error::Capacity(message) => {
                crate::error_context::overflow(message)
            }
        }
    }
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One fused diff boundary over explicit source and target metadata"
)]
#[pyo3(signature=(data,source_unit,aware,target,column,unit,absolute,inclusive,buffer=None,storage=None,date_unit=None,multiplier=1,target_zone=None,target_mask=None))]
fn _pddt_diff<'py>(
    py: Python<'py>,
    data: &[u8],
    source_unit: &str,
    aware: bool,
    target: &Bound<'py, PyAny>,
    column: bool,
    unit: &str,
    absolute: bool,
    inclusive: &str,
    buffer: Option<&[u8]>,
    storage: Option<&str>,
    date_unit: Option<&str>,
    multiplier: i32,
    target_zone: Option<&Bound<'py, PyAny>>,
    target_mask: Option<&[u8]>,
) -> PyResult<(Bound<'py, PyBytes>, Option<Bound<'py, PyBytes>>)> {
    const ENTRY: &str = "Pddt.diff";
    if !data.len().is_multiple_of(8) {
        return Err(crate::error_context::runtime("invalid source date buffer"));
    }
    let source_unit = Unit::parse(source_unit)?;
    let plan = Bucket::parse(unit).map_err(|e| {
        crate::error_context::argument(
            py,
            PyErr::from(e),
            ENTRY,
            "unit",
            PyString::new(py, unit).as_any(),
        )
    })?;
    let adjustment = match inclusive {
        "one" => 0,
        "both" => 1,
        "neither" => -1,
        _ => {
            return Err(crate::error_context::argument(
                py,
                crate::error_context::value_error("inclusive must be 'one', 'both' or 'neither'"),
                ENTRY,
                "inclusive",
                PyString::new(py, inclusive).as_any(),
            ));
        }
    };
    if target.is_instance_of::<PyBytes>() || target.is_instance_of::<pyo3::types::PyByteArray>() {
        return Err(crate::error_context::type_error(
            "byte strings are not date targets",
        ));
    }
    let count = data.len() / 8;
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
    let targets = if let Some(bytes) = buffer {
        if bytes.len() % 8 != 0
            || bytes.len() / 8 != count
            || target_mask
                .is_some_and(|m| m.len() != count && !(storage == Some("M") && m.is_empty()))
        {
            return Err(crate::error_context::value_error(
                "target column length must equal source length",
            ));
        }
        let storage = storage.unwrap_or("");
        if !matches!(storage, "M" | "i" | "u" | "f") {
            return Err(crate::error_context::runtime("invalid target storage"));
        }
        let target_aware = target_zone.is_some_and(|z| !z.is_none());
        let code = if storage == "M" {
            if target_aware != aware {
                return Err(crate::error_context::type_error(
                    "cannot mix naive and aware date columns",
                ));
            }
            Some(super::operands::numpy_code(date_unit.unwrap_or(""))?)
        } else {
            None
        };
        let validity = super::validity::TemporalValidity::new(
            if storage == "M" { target_mask } else { None },
            count,
        )?;
        let mut values = vector(count)?;
        for (i, bytes) in bytes.as_chunks::<8>().0.iter().enumerate() {
            if storage != "M" && target_mask.is_some_and(|m| m[i] != 0) {
                values.push(None);
                continue;
            }
            let raw: [u8; 8] = *bytes;
            let value = (|| {
                let nanos = match storage {
                    "M" => {
                        let tick = i64::from_ne_bytes(raw);
                        if validity.missing(i, tick) {
                            return Ok(None);
                        }
                        crate::epoch::native_datetime_ticks(
                            tick,
                            code.ok_or_else(|| {
                                crate::error_context::runtime("missing target unit")
                            })?,
                            multiplier,
                        )?
                        .nanos
                    }
                    "i" => i128::from(i64::from_ne_bytes(raw)) * 1_000_000_000,
                    "u" => i128::from(u64::from_ne_bytes(raw)) * 1_000_000_000,
                    _ => {
                        let f = f64::from_ne_bytes(raw);
                        if f.is_nan() {
                            return Ok(None);
                        }
                        crate::epoch::float_nanos(f, Unit::Second)?
                    }
                };
                domain(
                    Some(Date {
                        nanos,
                        aware: target_aware,
                    }),
                    aware,
                )
            })()
            .map_err(|e| crate::error_context::location(py, e, ENTRY, &format!("dtobj[{i}]")))?;
            values.push(value);
        }
        Column::Values(values)
    } else if !column
        && (super::prepare::missing(target)
            || target.is_instance_of::<PyString>()
            || target.is_instance_of::<pyo3::types::PyDate>()
            || crate::numeric::is_bool(target)
            || crate::numeric::supported_float(target)
            || unsafe { pyo3::ffi::PyIndex_Check(target.as_ptr()) != 0 }
            || crate::numpy_scalar::datetime_ticks(target)?.is_some())
    {
        Column::Scalar(
            read(target, &opts)
                .and_then(|value| domain(value, aware))
                .map_err(|e| crate::error_context::argument(py, e, ENTRY, "dtobj", target))?,
        )
    } else {
        let iterator = target.try_iter().map_err(crate::error_context::external)?;
        let mut values = vector(count)?;
        for (i, item) in iterator.enumerate() {
            let item = item
                .map_err(crate::error_context::external)
                .map_err(|error| {
                    crate::error_context::item(py, error, ENTRY, "dtobj", i, None, true)
                })?;
            if i == count {
                return Err(crate::error_context::value_error(
                    "target column length must equal source length",
                ));
            }
            values.push(
                read(&item, &opts)
                    .and_then(|value| domain(value, aware))
                    .map_err(|e| {
                        crate::error_context::item(py, e, ENTRY, "dtobj", i, Some(&item), false)
                    })?,
            );
        }
        if values.len() != count {
            return Err(crate::error_context::value_error(
                "target column length must equal source length",
            ));
        }
        Column::Values(values)
    };
    let scalar_bucket = match &targets {
        Column::Scalar(Some(d)) => Some(plan.index(d.nanos)?),
        _ => None,
    };
    match plan {
        Bucket::Calendar(kind) => pack_diff(
            py,
            data,
            &targets,
            CalendarIndex::new(kind, source_unit),
            scalar_bucket,
            absolute,
            adjustment,
        ),
        _ => pack_diff(
            py,
            data,
            &targets,
            FixedIndex {
                source: TickBucket::new(plan, source_unit),
                target: plan,
            },
            scalar_bucket,
            absolute,
            adjustment,
        ),
    }
}

fn pack_diff<'py, I: BoundaryIndex>(
    py: Python<'py>,
    data: &[u8],
    targets: &Column<Option<Date>>,
    mut indexer: I,
    scalar_bucket: Option<i128>,
    absolute: bool,
    adjustment: i128,
) -> PyResult<(Bound<'py, PyBytes>, Option<Bound<'py, PyBytes>>)> {
    const ENTRY: &str = "Pddt.diff";
    let count = data.len() / 8;
    let mut mask = None;
    let packed = PyBytes::new_with(py, data.len(), |out| {
        for (i, (bytes, out)) in data
            .as_chunks::<8>()
            .0
            .iter()
            .zip(out.as_chunks_mut::<8>().0.iter_mut())
            .enumerate()
        {
            let tick = i64::from_ne_bytes(*bytes);
            let target = targets.get(i);
            let result = if tick == i64::MIN || target.is_none() {
                missing_mask(&mut mask, count, i)?;
                0
            } else {
                let target =
                    target.ok_or_else(|| crate::error_context::runtime("missing target"))?;
                let left = indexer.source(tick)?;
                let right = if let Some(value) = scalar_bucket {
                    value
                } else {
                    indexer.target(target.nanos)?
                };
                crate::boundary_count::finish(left, right, absolute, adjustment).map_err(
                    |error| {
                        crate::error_context::location(
                            py,
                            PyErr::from(error),
                            ENTRY,
                            &format!("result[{i}]"),
                        )
                    },
                )?
            };
            out.copy_from_slice(&result.to_ne_bytes());
        }
        Ok(())
    })?;
    Ok((packed, mask.map(|m| PyBytes::new(py, &m))))
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_diff, module)?)
}
