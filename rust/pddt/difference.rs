//! Exact boundary counts, with once-prepared native scalar or positional targets.
use super::arguments::Column;
use super::common::{NS_DAY, missing_mask, vector};
use crate::epoch::{Options, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyFloat, PyString};

#[derive(Clone, Copy)]
struct Date {
    nanos: i128,
    aware: bool,
}
#[derive(Clone, Copy)]
enum Bucket {
    Calendar(u8),
    Week,
    Fixed(i128),
}
impl Bucket {
    fn parse(unit: &str) -> PyResult<Self> {
        Ok(match unit {
            "Y" => Self::Calendar(0),
            "Q" => Self::Calendar(1),
            "M" => Self::Calendar(2),
            "W" => Self::Week,
            "D" => Self::Fixed(NS_DAY),
            "h" => Self::Fixed(3_600_000_000_000),
            "m" | "min" => Self::Fixed(60_000_000_000),
            "s" => Self::Fixed(1_000_000_000),
            "ms" => Self::Fixed(1_000_000),
            "us" => Self::Fixed(1000),
            "ns" => Self::Fixed(1),
            _ => {
                return Err(crate::error_context::value_error(
                    "unit must be Y, Q, M, W, D, h, m, min, s, ms, us or ns",
                ));
            }
        })
    }
    fn index(self, value: i128) -> PyResult<i128> {
        match self {
            Self::Fixed(step) => Ok(value.div_euclid(step)),
            Self::Week => Ok((value.div_euclid(NS_DAY) + 3).div_euclid(7)),
            Self::Calendar(kind) => calendar_index(kind, calendar_ordinal(value)?),
        }
    }
}

fn calendar_ordinal(value: i128) -> PyResult<i64> {
    i64::try_from(value.div_euclid(NS_DAY) + 719_163)
        .map_err(|_| crate::error_context::overflow("calendar day exceeds the native range"))
}

fn calendar_index(kind: u8, ordinal: i64) -> PyResult<i128> {
    let [year, month, _] =
        crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)?;
    let year = i128::from(year) - 1970;
    Ok(match kind {
        0 => year,
        1 => year * 4 + i128::from((month - 1) / 3),
        _ => year * 12 + i128::from(month - 1),
    })
}

/// One operation owns its calendar kind and last completed day result.
/// Target reads and errors still occur before this pure integer lookup.
#[derive(Clone, Copy)]
struct CalendarMemo {
    kind: u8,
    last: Option<(i64, i128)>,
}
impl CalendarMemo {
    fn new(kind: u8) -> Self {
        Self { kind, last: None }
    }
    fn index(&mut self, ordinal: i64) -> PyResult<i128> {
        if let Some((previous, index)) = self.last {
            if previous == ordinal {
                return Ok(index);
            }
        }
        let index = calendar_index(self.kind, ordinal)?;
        self.last = Some((ordinal, index));
        Ok(index)
    }
}

/// A fixed boundary can be counted in storage ticks without a wide division per row.
#[derive(Clone, Copy)]
enum TickBucket {
    Scale(i128),
    Divide(i64),
    Calendar(Bucket, Unit),
}
impl TickBucket {
    fn new(bucket: Bucket, unit: Unit) -> Self {
        // Supported fixed steps and storage units divide exactly; the largest
        // quotient is one day in nanoseconds, comfortably inside i64.
        match bucket {
            Bucket::Fixed(step) if unit.nanos() >= step => Self::Scale(unit.nanos() / step),
            Bucket::Fixed(step) => Self::Divide((step / unit.nanos()) as i64),
            _ => Self::Calendar(bucket, unit),
        }
    }
    fn index(self, tick: i64) -> PyResult<i128> {
        match self {
            Self::Scale(factor) => Ok(i128::from(tick) * factor),
            Self::Divide(divisor) => Ok(i128::from(tick.div_euclid(divisor))),
            Self::Calendar(bucket, unit) => bucket.index(i128::from(tick) * unit.nanos()),
        }
    }
}

/// These two native plans are chosen once, keeping calendar state out of the
/// fixed-unit loop. Static dispatch preserves one shared result/error writer.
trait BoundaryIndex {
    fn source(&mut self, tick: i64) -> PyResult<i128>;
    fn target(&mut self, nanos: i128) -> PyResult<i128>;
}

struct FixedIndex {
    source: TickBucket,
    target: Bucket,
}
impl BoundaryIndex for FixedIndex {
    #[inline]
    fn source(&mut self, tick: i64) -> PyResult<i128> {
        self.source.index(tick)
    }
    #[inline]
    fn target(&mut self, nanos: i128) -> PyResult<i128> {
        self.target.index(nanos)
    }
}

struct CalendarIndex {
    ticks_per_day: i64,
    source: CalendarMemo,
    target: CalendarMemo,
}
impl CalendarIndex {
    fn new(kind: u8, unit: Unit) -> Self {
        // All four storage resolutions divide a day exactly within i64.
        Self {
            ticks_per_day: (NS_DAY / unit.nanos()) as i64,
            source: CalendarMemo::new(kind),
            target: CalendarMemo::new(kind),
        }
    }
}
impl BoundaryIndex for CalendarIndex {
    #[inline]
    fn source(&mut self, tick: i64) -> PyResult<i128> {
        let ordinal = tick
            .div_euclid(self.ticks_per_day)
            .checked_add(719_163)
            .ok_or_else(|| {
                crate::error_context::overflow("calendar day exceeds the native range")
            })?;
        self.source.index(ordinal)
    }
    #[inline]
    fn target(&mut self, nanos: i128) -> PyResult<i128> {
        self.target.index(calendar_ordinal(nanos)?)
    }
}

fn read(value: &Bound<'_, PyAny>, opts: &Options<'_, '_>) -> PyResult<Option<Date>> {
    if super::prepare::missing(value) {
        return Ok(None);
    }
    if crate::numeric::is_bool(value) {
        return Err(crate::error_context::type_error(
            "boolean values are not date or epoch inputs",
        ));
    }
    if let Ok(text) = value.cast::<PyString>() {
        let converted;
        let text = if value.is_exact_instance_of::<PyString>() {
            text
        } else {
            converted = value.str().map_err(crate::error_context::external)?;
            &converted
        };
        if super::prepare::missing_text(text)? {
            return Ok(None);
        }
        let p = crate::epoch::read(text.as_any(), opts)?;
        return Ok(Some(Date {
            nanos: p.nanos,
            aware: !matches!(p.zone, Zone::Naive),
        }));
    }
    if let Some((tick, code, multiplier)) = crate::numpy_scalar::datetime_ticks(value)? {
        super::prepare::scalar_unit(code)?;
        if tick == i64::MIN {
            return Ok(None);
        }
        return crate::epoch::numpy_ticks(tick, code, multiplier).map(|p| {
            Some(Date {
                nanos: p.nanos,
                aware: false,
            })
        });
    }
    if value.is_instance_of::<pyo3::types::PyDelta>()
        || crate::numpy_scalar::duration_ticks(value)?.is_some()
    {
        return Err(crate::error_context::type_error(
            "a duration is not a date target",
        ));
    }
    if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) != 0 } {
        let nanos = crate::numeric::index_i128(value)?
            .checked_mul(1_000_000_000)
            .ok_or_else(|| {
                crate::error_context::overflow("numeric seconds exceed the native range")
            })?;
        return Ok(Some(Date {
            nanos,
            aware: false,
        }));
    }
    if crate::numeric::supported_float(value) {
        let number = if value.is_instance_of::<PyFloat>() {
            value.extract::<f64>()?
        } else {
            crate::numeric::float_value(value)?
        };
        if number.is_nan() {
            return Ok(None);
        }
        return crate::epoch::float_nanos(number, Unit::Second).map(|nanos| {
            Some(Date {
                nanos,
                aware: false,
            })
        });
    }
    let p = crate::epoch::read(value, opts)?;
    Ok(Some(Date {
        nanos: p.nanos,
        aware: !matches!(p.zone, Zone::Naive),
    }))
}
fn domain(value: Option<Date>, aware: bool) -> PyResult<Option<Date>> {
    if value.is_some_and(|v| v.aware != aware) {
        Err(crate::error_context::type_error(
            "cannot mix naive and aware date targets; prepare the target timezone explicitly",
        ))
    } else {
        Ok(value)
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
    if data.len() % 8 != 0 {
        return Err(crate::error_context::runtime("invalid source date buffer"));
    }
    let source_unit = Unit::parse(source_unit)?;
    let plan = Bucket::parse(unit).map_err(|e| {
        crate::error_context::argument(py, e, ENTRY, "unit", PyString::new(py, unit).as_any())
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
        for (i, bytes) in bytes.chunks_exact(8).enumerate() {
            if storage != "M" && target_mask.is_some_and(|m| m[i] != 0) {
                values.push(None);
                continue;
            }
            let raw: [u8; 8] = bytes
                .try_into()
                .map_err(|_| crate::error_context::runtime("invalid target tick"))?;
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
            .chunks_exact(8)
            .zip(out.chunks_exact_mut(8))
            .enumerate()
        {
            let tick = i64::from_ne_bytes(
                bytes
                    .try_into()
                    .map_err(|_| crate::error_context::runtime("invalid source tick"))?,
            );
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
                let mut difference = left.checked_sub(right).ok_or_else(|| {
                    crate::error_context::overflow("date difference exceeds native range")
                })?;
                if absolute {
                    difference = difference.checked_abs().ok_or_else(|| {
                        crate::error_context::overflow("absolute difference exceeds native range")
                    })?;
                }
                difference = difference
                    .checked_add(if difference < 0 {
                        -adjustment
                    } else {
                        adjustment
                    })
                    .ok_or_else(|| {
                        crate::error_context::overflow("inclusive difference exceeds native range")
                    })?;
                i64::try_from(difference).map_err(|_| {
                    crate::error_context::location(
                        py,
                        crate::error_context::overflow(
                            "difference exceeds the full int64 range; choose a coarser diff unit",
                        ),
                        ENTRY,
                        &format!("result[{i}]"),
                    )
                })?
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
