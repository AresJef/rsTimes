//! Native range endpoints and one shared integer/calendar sequence generator.
use super::finish::{Failure, Kind as ErrorKind, Rows};
use super::zones::{Context, Policies, PolicyContext, prepare_host_zone};
use crate::date_input::Reader;
use crate::epoch::{Options, Unit, Zone as HostZone};
use crate::range_calendar::{Kind, Plan};
use crate::range_generate::{self, Input};
use crate::temporal_zone::Zone;
use pyo3::prelude::*;
use pyo3_polars::PySeries;
const NS_DAY: i128 = 86_400_000_000_000;
impl From<range_generate::Error> for Failure {
    fn from(error: range_generate::Error) -> Self {
        match error {
            range_generate::Error::Value(message) => Self::new(ErrorKind::Value, message),
            range_generate::Error::Capacity(message) => Self::new(ErrorKind::Capacity, message),
        }
    }
}
#[derive(Clone)]
enum Source {
    Naive,
    Offset(i64),
    Region(Zone),
}
impl Source {
    fn same(&self, other: &Self) -> bool {
        match (self, other) {
            (Self::Naive, Self::Naive) => true,
            (Self::Offset(a), Self::Offset(b)) => a == b,
            (Self::Region(a), Self::Region(b)) => a.key() == b.key(),
            (Self::Offset(a), Self::Region(b)) | (Self::Region(b), Self::Offset(a)) => b
                .fixed_seconds()
                .is_some_and(|value| i64::from(value) * 1_000_000 == *a),
            _ => false,
        }
    }
    fn target(&self) -> Result<Option<Zone>, Failure> {
        match self {
            Self::Naive => Ok(None),
            Self::Region(zone) => Ok(Some(zone.clone())),
            Self::Offset(offset) => {
                if offset % 3_600_000_000 != 0 {
                    return Err(Failure::new(
                        ErrorKind::Value,
                        "source offset cannot be represented by a Polars timezone; pass explicit tz",
                    ));
                }
                let key = if *offset == 0 {
                    "UTC".to_owned()
                } else {
                    format!(
                        "Etc/GMT{}{}",
                        if *offset > 0 { "-" } else { "+" },
                        offset.unsigned_abs() / 3_600_000_000
                    )
                };
                Zone::named(&key)
                    .map(Some)
                    .map_err(|message| Failure::new(ErrorKind::Value, message))
            }
        }
    }
}
struct Endpoint {
    ns: i128,
    zone: Source,
    instant: bool,
}
#[pyclass(frozen, skip_from_py_object, name = "_PldtRangeEndpoints")]
struct Endpoints {
    coordinates: [Option<i128>; 2],
    known: [Option<i128>; 2],
    unit: Unit,
    zone: Option<Zone>,
}
fn tick(ns: i128, unit: Unit) -> Result<i64, Failure> {
    crate::precision::epoch_tick(ns, unit.nanos(), false).map_err(|error| match error {
        crate::precision::TickError::Precision => Failure::new(
            ErrorKind::Value,
            "endpoint cannot be preserved at the requested unit; choose a finer unit",
        ),
        crate::precision::TickError::Capacity => Failure::new(
            ErrorKind::Capacity,
            "endpoint exceeds the requested unit; choose a coarser supported unit",
        ),
    })
}
fn localize(wall: i128, zone: &Zone, policy: &Policies, unit: Unit) -> Result<i128, Failure> {
    let mut pending = if policy.infer() && zone.fixed_seconds().is_none() {
        vec![None]
    } else {
        Vec::new()
    };
    let mut values = [policy.localize(wall, zone, unit, 0, 0, &mut pending)?];
    policy.complete(&mut values, &pending)?;
    values[0].ok_or_else(|| {
        Failure::new(
            ErrorKind::Value,
            "a range endpoint cannot become null; choose a usable localization policy",
        )
    })
}
fn utc(endpoint: &Endpoint, policy: &Policies, unit: Unit) -> Result<i128, Failure> {
    if endpoint.instant {
        return Ok(endpoint.ns);
    }
    match &endpoint.zone {
        Source::Naive => Ok(endpoint.ns),
        Source::Offset(offset) => endpoint
            .ns
            .checked_sub(i128::from(*offset) * 1000)
            .ok_or_else(|| Failure::new(ErrorKind::Capacity, "source offset overflow")),
        Source::Region(zone) => localize(endpoint.ns, zone, policy, unit),
    }
}
#[pymethods]
impl Endpoints {
    #[getter]
    fn unit(&self) -> &'static str {
        self.unit.name()
    }
    /// Mature engines may need a distinct, exact local carrier resolution.
    fn carrier(&self) -> PyResult<(Option<i64>, Option<i64>, &'static str)> {
        let candidates = [
            self.unit,
            Unit::Nanosecond,
            Unit::Microsecond,
            Unit::Millisecond,
            Unit::Second,
        ];
        for unit in candidates {
            let values = self.coordinates.map(|value| {
                value
                    .map(|value| crate::precision::epoch_tick(value, unit.nanos(), false))
                    .transpose()
            });
            if let [Ok(start), Ok(end)] = values {
                return Ok((start, end, unit.name()));
            }
        }
        Err(crate::error_context::overflow(
            "mature range engine cannot represent exact local endpoints at a supported carrier unit",
        ))
    }
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Actual scalar endpoints, shared parsing options and one native final context"
)]
#[pyo3(signature=(start,end,policy,plan,unit,tz,normalize,default,yearfirst,dayfirst,isoformat,strict,cfg,calendar=false))]
fn _pldt_range_endpoints<'py>(
    py: Python<'py>,
    start: Option<&Bound<'py, PyAny>>,
    end: Option<&Bound<'py, PyAny>>,
    policy: PyRef<'_, PolicyContext>,
    plan: Option<PyRef<'_, Plan>>,
    unit: Option<&str>,
    tz: Option<PyRef<'_, Context>>,
    normalize: bool,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    strict: bool,
    cfg: Option<&Bound<'py, PyAny>>,
    calendar: bool,
) -> PyResult<Endpoints> {
    let requested = super::input::selected(unit)?;
    let options = Options {
        default,
        yearfirst,
        dayfirst,
        ignoretz: false,
        isoformat,
        strict,
        iso_only: false,
        cfg,
        input_unit: requested.unwrap_or(Unit::Nanosecond),
    };
    let mut reader = Reader::<false>::new(options, Unit::Second);
    let mut endpoints = [None, None];
    for (index, (input, label)) in [(start, "start"), (end, "end")].into_iter().enumerate() {
        let Some(input) = input else {
            continue;
        };
        let (parsed, instant) = reader
            .read(input, "Pldt.date_range")
            .map_err(|error| {
                crate::error_context::argument(py, error, "Pldt.date_range", label, input)
            })?
            .ok_or_else(|| {
                crate::error_context::argument(
                    py,
                    crate::error_context::value_error(
                        "range endpoint must not be NaT or another missing value",
                    ),
                    "Pldt.date_range",
                    label,
                    input,
                )
            })?;
        let zone = if instant && tz.is_some() {
            Source::Naive
        } else {
            match parsed.zone {
                HostZone::Naive => Source::Naive,
                HostZone::Offset(value) => Source::Offset(value),
                HostZone::Object(value) => {
                    if let Some(offset) =
                        crate::date_input::fixed_offset(py, &HostZone::Object(value.clone_ref(py)))?
                    {
                        Source::Offset(offset)
                    } else {
                        Source::Region(prepare_host_zone(value.bind(py))?)
                    }
                }
            }
        };
        endpoints[index] = Some(Endpoint {
            ns: parsed.nanos,
            zone,
            instant,
        });
    }
    let selected = if let Some(target) = tz.as_ref() {
        Source::Region(target.value.clone())
    } else {
        let mut selected = Source::Naive;
        for endpoint in endpoints.iter().flatten() {
            if matches!(endpoint.zone, Source::Naive) {
                continue;
            }
            if !matches!(selected, Source::Naive) && !selected.same(&endpoint.zone) {
                return Err(crate::error_context::value_error(
                    "range endpoints have different timezones; pass explicit tz",
                ));
            }
            selected = endpoint.zone.clone();
        }
        selected
    };
    let zone = selected
        .target()
        .map_err(|error| error.python(py, "Pldt.date_range"))?;
    let unit = requested.unwrap_or(
        reader.unit.max(
            plan.as_ref()
                .map_or(Unit::Second, |plan| plan.required_unit()),
        ),
    );
    let calendar = calendar
        || plan
            .as_ref()
            .is_some_and(|plan| !matches!(plan.frequency.kind, Kind::Fixed(_)));
    let mut coordinates = [None, None];
    let mut known = [None, None];
    for (index, endpoint) in endpoints.into_iter().enumerate() {
        let Some(endpoint) = endpoint else {
            continue;
        };
        let endpoint_policy = policy.value.endpoint(index == 1);
        let fresh = !endpoint.instant
            && (matches!(endpoint.zone, Source::Naive) || endpoint.zone.same(&selected));
        let (mut wall, mut instant) = if fresh {
            (endpoint.ns, None)
        } else {
            let instant = utc(&endpoint, &endpoint_policy, unit)
                .map_err(|error| error.python(py, "Pldt.date_range"))?;
            let wall = if let Some(zone) = &zone {
                zone.wall(instant)
                    .map_err(|error| Failure::from(error).python(py, "Pldt.date_range"))?
            } else {
                instant
            };
            (wall, Some(instant))
        };
        if normalize {
            wall = wall.div_euclid(NS_DAY) * NS_DAY;
            instant = None;
        }
        let coordinate = if calendar {
            wall
        } else if let Some(instant) = instant {
            instant
        } else if let Some(zone) = &zone {
            localize(wall, zone, &endpoint_policy, unit)
                .map_err(|error| error.python(py, "Pldt.date_range"))?
        } else {
            wall
        };
        if let Some(requested) = requested {
            let stored = if calendar {
                if let Some(instant) = instant {
                    instant
                } else if let Some(zone) = &zone {
                    let value = localize(wall, zone, &endpoint_policy, requested)
                        .map_err(|error| error.python(py, "Pldt.date_range"))?;
                    instant = Some(value);
                    value
                } else {
                    wall
                }
            } else {
                coordinate
            };
            let input = if index == 0 { start } else { end }
                .ok_or_else(|| crate::error_context::runtime("endpoint input was lost"))?;
            tick(stored, requested).map_err(|error| {
                crate::error_context::argument(
                    py,
                    error.python(py, "Pldt.date_range"),
                    "Pldt.date_range",
                    if index == 0 { "start" } else { "end" },
                    input,
                )
            })?;
        }
        coordinates[index] = Some(coordinate);
        if calendar {
            known[index] = instant;
        }
    }
    Ok(Endpoints {
        coordinates,
        known,
        unit,
        zone,
    })
}
fn inclusive(value: &str) -> Result<(bool, bool), Failure> {
    match value {
        "both" => Ok((true, true)),
        "left" => Ok((true, false)),
        "right" => Ok((false, true)),
        "neither" => Ok((false, false)),
        _ => Err(Failure::new(
            ErrorKind::Value,
            "inclusive must be 'both', 'left', 'right' or 'neither'",
        )),
    }
}
#[pyfunction]
fn _pldt_range<'py>(
    target: &Bound<'py, PyAny>,
    inputs: PyRef<'_, Endpoints>,
    periods: Option<usize>,
    plan: Option<PyRef<'_, Plan>>,
    policy: PyRef<'_, PolicyContext>,
    closed: &str,
    name: &str,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let unit = inputs.unit.max(Unit::Millisecond);
    let mut rows = Rows::new(unit);
    range_generate::arity(
        inputs.coordinates[0].is_some(),
        inputs.coordinates[1].is_some(),
        periods.is_some(),
        plan.is_some(),
    )
    .map_err(|error| Failure::from(error).python(py, "Pldt.date_range"))?;
    if let Some(periods) = periods {
        rows.reserve(periods)
            .map_err(|error| error.python(py, "Pldt.date_range"))?;
    }
    let trim = range_generate::generate(
        Input {
            start: inputs.coordinates[0],
            end: inputs.coordinates[1],
            periods,
            frequency: plan.as_ref().map(|plan| &plan.frequency),
            unit,
            inclusive: inclusive(closed).map_err(|error| error.python(py, "Pldt.date_range"))?,
            known_start: inputs.known[0],
            known_end: inputs.known[1],
        },
        |value, instant| -> Result<(), Failure> {
            if instant {
                tick(value, unit)?;
            } else if let Some(zone) = &inputs.zone {
                if let Some(offset) = zone.fixed_seconds() {
                    tick(value - i128::from(offset) * 1_000_000_000, unit)?;
                }
            } else {
                tick(value, unit)?;
            }
            rows.ensure_one()?;
            rows.push(value, 0, instant, unit);
            Ok(())
        },
    )
    .map_err(|error: Failure| error.python(py, "Pldt.date_range"))?;
    let result = rows
        .finish(
            name.into(),
            Some(unit),
            inputs.zone.as_ref(),
            &policy.value,
            false,
        )
        .map_err(|error| error.python(py, "Pldt.date_range"))?;
    let length = result.len().saturating_sub(trim.left + trim.right);
    let result = result.slice(trim.left as i64, length);
    super::export(py, &result, target)
}
#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Mature raw source is localized once with independent output precision"
)]
fn _pldt_range_external<'py>(
    target: &Bound<'py, PyAny>,
    inputs: PyRef<'_, Endpoints>,
    source: PySeries,
    source_unit: &str,
    policy: PyRef<'_, PolicyContext>,
    closed: &str,
    unit: Option<&str>,
    infer: bool,
    name: &str,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let output = inclusive(closed).map_err(|error| error.python(py, "Pldt.date_range"))?;
    let source_unit = Unit::parse(source_unit)?;
    let mut selected = unit.map(Unit::parse).transpose()?.unwrap_or(source_unit);
    let mut rows = Rows::new(selected);
    let mut first = None;
    let mut last = None;
    let len = source.0.len();
    for (index, value) in source
        .0
        .i64()
        .map_err(|error| crate::error_context::type_error(error.to_string()))?
        .iter()
        .enumerate()
    {
        let Some(value) = value.filter(|value| *value != i64::MIN) else {
            rows.missing();
            continue;
        };
        let ns = i128::from(value) * source_unit.nanos();
        if infer && ns.rem_euclid(selected.nanos()) != 0 {
            selected = if ns.rem_euclid(1000) == 0 {
                Unit::Microsecond
            } else {
                Unit::Nanosecond
            };
        }
        if index == 0 {
            first = Some(ns);
        }
        if index + 1 == len {
            last = Some(ns);
        }
        let known = if index == 0 && Some(ns) == inputs.coordinates[0] {
            inputs.known[0]
        } else if index + 1 == len && Some(ns) == inputs.coordinates[1] {
            inputs.known[1]
        } else {
            None
        };
        rows.push(known.unwrap_or(ns), 0, known.is_some(), source_unit);
    }
    let (mut left, mut right) = (0, 0);
    if inputs.coordinates[0].is_some() && inputs.coordinates[0] == inputs.coordinates[1] {
        if !output.0 && !output.1 {
            left = usize::from(len > 0);
            right = usize::from(len > 1);
        }
    } else {
        if !output.0 && first == inputs.coordinates[0] {
            left = usize::from(len > 0);
        }
        if !output.1 && last == inputs.coordinates[1] {
            right = usize::from(len > left);
        }
    }
    let result = rows
        .finish(
            name.into(),
            Some(selected.max(Unit::Millisecond)),
            inputs.zone.as_ref(),
            &policy.value,
            false,
        )
        .map_err(|error| error.python(py, "Pldt.date_range"))?;
    let result = result.slice(left as i64, result.len().saturating_sub(left + right));
    super::export(py, &result, target)
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_range_endpoints, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_range, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_range_external, module)?)
}
