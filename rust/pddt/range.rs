//! Prepared static frequency plans and native range generation.
use super::common::{Rows, finish};
use crate::epoch::{Parsed, Unit, Zone};
use crate::range_calendar::{Business, Frequency, Kind, Plan};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDelta, PyDeltaAccess, PyDict};

type RangeOutput<'py> = (Bound<'py, PyBytes>, &'static str, Py<PyAny>, usize, usize);

fn integer(props: &Bound<'_, PyDict>, key: &str, default: i64) -> PyResult<i64> {
    props.get_item(key)?.map_or(Ok(default), |v| v.extract())
}
fn boolean(props: &Bound<'_, PyDict>, key: &str, default: bool) -> PyResult<bool> {
    props
        .get_item(key)?
        .map_or(Ok(default), |v| crate::numeric::boolean(&v))
}
fn duration(props: &Bound<'_, PyDict>) -> PyResult<i128> {
    let Some(value) = props.get_item("duration")? else {
        return Ok(0);
    };
    if let Some(ns) = crate::interop::duration_nanoseconds(&value)? {
        return Ok(ns);
    }
    let delta = value
        .cast::<PyDelta>()
        .map_err(|_| crate::error_context::type_error("frequency offset must be a timedelta"))?;
    Ok(
        (i128::from(delta.get_days()) * 86400 + i128::from(delta.get_seconds())) * 1_000_000_000
            + i128::from(delta.get_microseconds()) * 1000,
    )
}

#[pyfunction]
fn _pddt_frequency(kind: &str, n: i64, props: &Bound<'_, PyDict>) -> PyResult<Plan> {
    if n == 0 {
        return Err(crate::error_context::value_error(
            "frequency must not be zero",
        ));
    }
    let mut mask = [true, true, true, true, true, false, false];
    if let Some(value) = props.get_item("mask")? {
        let bytes = value.extract::<&[u8]>()?;
        if bytes.len() != 7 || bytes.iter().any(|v| *v > 1) || !bytes.contains(&1) {
            return Err(crate::error_context::value_error(
                "business weekmask requires seven booleans and at least one working day",
            ));
        }
        for (out, value) in mask.iter_mut().zip(bytes) {
            *out = *value != 0;
        }
    }
    let mut holidays = Vec::new();
    if let Some(value) = props.get_item("holidays")? {
        let bytes = value.extract::<&[u8]>()?;
        if bytes.len() % 8 != 0 {
            return Err(crate::error_context::runtime("invalid holiday snapshot"));
        }
        for bytes in bytes.chunks_exact(8) {
            let raw: [u8; 8] = bytes
                .try_into()
                .map_err(|_| crate::error_context::runtime("invalid holiday bytes"))?;
            let value = i64::from_ne_bytes(raw);
            if value != i64::MIN && mask[Business::weekday(i128::from(value))] {
                holidays.push(value);
            }
        }
        holidays.sort_unstable();
        holidays.dedup();
    }
    let offset = duration(props)?;
    let weekday = props
        .get_item("weekday")?
        .filter(|v| !v.is_none())
        .map_or(Ok(-1), |v| v.extract::<i64>())?;
    let kind = match kind {
        "fixed" => Kind::Fixed(
            props
                .get_item("tick")?
                .ok_or_else(|| crate::error_context::runtime("fixed frequency lacks its tick"))?
                .extract::<i128>()?,
        ),
        "duration" => Kind::Fixed(offset),
        "days" => Kind::Days,
        "week" => {
            let weekday = if props.get_item("weekday")?.is_none_or(|v| v.is_none()) {
                None
            } else {
                Some(weekday)
            };
            if weekday.is_some_and(|v| !(0..=6).contains(&v)) {
                return Err(crate::error_context::value_error(
                    "frequency weekday must be in 0..6",
                ));
            }
            Kind::Week(weekday)
        }
        "business" => Kind::Business,
        "boundary" => {
            let stride = integer(props, "stride", 1)?;
            let anchor = integer(props, "anchor", 1)?;
            if ![1, 3, 12].contains(&stride) || !(1..=12).contains(&anchor) {
                return Err(crate::error_context::value_error(
                    "invalid frequency month anchor",
                ));
            }
            Kind::Boundary {
                stride,
                anchor,
                start: boolean(props, "start", false)?,
                business: boolean(props, "business", false)?,
            }
        }
        "semi" => {
            let day = integer(props, "day", 15)?;
            if !(1..=27).contains(&day) {
                return Err(crate::error_context::value_error(
                    "semi-month day anchor must be in 1..27",
                ));
            }
            Kind::Semi {
                start: boolean(props, "start", false)?,
                day,
            }
        }
        "wom" => {
            let week = integer(props, "week", 0)?;
            if !(0..=6).contains(&weekday) || !(0..=3).contains(&week) {
                return Err(crate::error_context::value_error(
                    "invalid weekday-of-month frequency",
                ));
            }
            Kind::WeekOfMonth {
                weekday,
                week,
                last: boolean(props, "last", false)?,
            }
        }
        _ => {
            return Err(crate::error_context::runtime(
                "unknown native frequency plan",
            ));
        }
    };
    if matches!(kind, Kind::Fixed(0)) {
        return Err(crate::error_context::value_error(
            "frequency must not be zero",
        ));
    }
    Ok(Plan {
        precision: props
            .get_item("precision")?
            .map(|v| Unit::parse(v.extract::<&str>()?))
            .transpose()?
            .unwrap_or(Unit::Second),
        frequency: Frequency {
            kind,
            n,
            normalize: boolean(props, "normalize", false)?,
            offset,
            business: Business { mask, holidays },
        },
    })
}

fn append(rows: &mut Rows, py: Python<'_>, value: i128, unit: Unit, instant: bool) -> PyResult<()> {
    if rows.values.len() == rows.values.capacity() {
        rows.reserve(rows.values.capacity().max(16))?;
    }
    rows.push(
        py,
        Parsed {
            nanos: value,
            unit,
            zone: Zone::Naive,
        },
        instant,
    )
}

fn endpoint_utc(
    py: Python<'_>,
    ns: i128,
    zone: &Zone,
    policy: &super::zones::Policies,
    unit: Unit,
) -> PyResult<i128> {
    let Zone::Object(value) = zone else {
        return Ok(ns);
    };
    let mut pending = if policy.infers() {
        vec![None]
    } else {
        Vec::new()
    };
    let result = super::zones::localize(ns, value.bind(py), policy, unit, 0, 0, &mut pending)?;
    let mut values = [result];
    if !pending.is_empty() {
        super::zones::infer(&mut values, &pending)?;
    }
    values[0].ok_or_else(|| {
        crate::error_context::value_error(
            "a range endpoint cannot become NaT; choose a usable localization policy",
        )
    })
}

fn validate_endpoint_unit(ns: i128, unit: Unit) -> PyResult<()> {
    if ns.rem_euclid(unit.nanos()) != 0 {
        return Err(crate::error_context::value_error(
            "endpoint cannot be preserved at the requested unit; choose a finer unit",
        ));
    }
    let tick = ns.div_euclid(unit.nanos());
    if tick <= i128::from(i64::MIN) || tick > i128::from(i64::MAX) {
        return Err(crate::error_context::overflow(
            "endpoint is outside the requested unit; choose a coarser unit",
        ));
    }
    Ok(())
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "One prepared range boundary over shared scalar decoding"
)]
#[pyo3(signature=(start,end,periods,plan,policy,unit=None,target=None,inclusive="both",normalize=false,default=None,yearfirst=None,dayfirst=None,isoformat=true,strict=false,cfg=None))]
fn _pddt_range<'py>(
    py: Python<'py>,
    start: Option<&Bound<'py, PyAny>>,
    end: Option<&Bound<'py, PyAny>>,
    periods: Option<usize>,
    plan: Option<PyRef<'_, Plan>>,
    policy: PyRef<'_, super::zones::Policies>,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    inclusive: &str,
    normalize: bool,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    strict: bool,
    cfg: Option<&Bound<'py, PyAny>>,
) -> PyResult<RangeOutput<'py>> {
    let calendar = plan
        .as_ref()
        .is_some_and(|p| !matches!(p.frequency.kind, Kind::Fixed(_)));
    let tick = plan.as_ref().and_then(|p| p.tick());
    let mut inputs = prepare_endpoints(
        py, start, end, &policy, unit, target, normalize, default, yearfirst, dayfirst, isoformat,
        strict, cfg, calendar, tick,
    )?;
    if unit.is_none() {
        if let Some(plan) = &plan {
            inputs.unit = inputs.unit.max(plan.precision);
        }
    }
    let target = (!inputs.zone.bind(py).is_none()).then(|| inputs.zone.bind(py));
    _pddt_range_sequence(
        py,
        inputs.coordinates[0],
        inputs.coordinates[1],
        periods,
        plan,
        policy,
        Some(inputs.unit.name()),
        target,
        inclusive,
        inputs.known[0],
        inputs.known[1],
    )
}

#[pyclass(frozen, name = "_PddtRangeEndpoints")]
struct Endpoints {
    coordinates: [Option<i128>; 2],
    known: [Option<i128>; 2],
    unit: Unit,
    zone: Py<PyAny>,
}
impl Endpoints {
    fn carrier(&self) -> PyResult<Unit> {
        for unit in [
            Unit::Second,
            Unit::Millisecond,
            Unit::Microsecond,
            Unit::Nanosecond,
        ] {
            if unit < self.unit {
                continue;
            }
            if self.coordinates.iter().flatten().all(|ns| {
                ns.rem_euclid(unit.nanos()) == 0
                    && i64::try_from(ns.div_euclid(unit.nanos()))
                        .is_ok_and(|value| value != i64::MIN)
            }) {
                return Ok(unit);
            }
        }
        Err(crate::error_context::overflow(
            "local range endpoints exceed the supported intermediate date container",
        ))
    }

    fn tick(&self, index: usize) -> PyResult<Option<i64>> {
        let unit = self.carrier()?;
        self.coordinates[index]
            .map(|ns| {
                if ns.rem_euclid(unit.nanos()) != 0 {
                    return Err(crate::error_context::value_error(
                        "range endpoint cannot be preserved at this unit; choose a finer unit",
                    ));
                }
                i64::try_from(ns.div_euclid(unit.nanos()))
                    .ok()
                    .filter(|v| *v != i64::MIN)
                    .ok_or_else(|| {
                        crate::error_context::overflow(
                            "range endpoint is outside the selected unit",
                        )
                    })
            })
            .transpose()
    }
}
#[pymethods]
impl Endpoints {
    #[getter]
    fn carrier_unit(&self) -> PyResult<&'static str> {
        Ok(self.carrier()?.name())
    }
    #[getter]
    fn start(&self) -> PyResult<Option<i64>> {
        self.tick(0)
    }
    #[getter]
    fn end(&self) -> PyResult<Option<i64>> {
        self.tick(1)
    }
    #[getter]
    fn unit(&self) -> &'static str {
        self.unit.name()
    }
    #[getter]
    fn zone(&self, py: Python<'_>) -> Py<PyAny> {
        self.zone.clone_ref(py)
    }
}

#[expect(
    clippy::too_many_arguments,
    reason = "Shared endpoint decoding for native and explicitly delegated rules"
)]
fn prepare_endpoints<'py>(
    py: Python<'py>,
    start: Option<&Bound<'py, PyAny>>,
    end: Option<&Bound<'py, PyAny>>,
    policy: &super::zones::Policies,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    normalize: bool,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    strict: bool,
    cfg: Option<&Bound<'py, PyAny>>,
    calendar: bool,
    tick: Option<i128>,
) -> PyResult<Endpoints> {
    let requested = unit.map(Unit::parse).transpose()?;
    let options = crate::epoch::Options {
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
    let mut reader = super::prepare::Reader::new(options, Unit::Second);
    let mut rows = Rows::new(Unit::Second);
    for (value, name) in [(start, "start"), (end, "end")] {
        if let Some(value) = value {
            let parsed = reader
                .read(value, "Pddt.date_range")
                .map_err(|e| crate::error_context::argument(py, e, "Pddt.date_range", name, value))?
                .ok_or_else(|| {
                    crate::error_context::argument(
                        py,
                        crate::error_context::value_error(
                            "range endpoint must not be NaT or another missing value",
                        ),
                        "Pddt.date_range",
                        name,
                        value,
                    )
                })?;
            rows.push(py, parsed.0, parsed.1)?;
        } else {
            rows.missing();
        }
    }
    let selected = if let Some(target) = target {
        Zone::Object(target.clone().unbind())
    } else {
        let mut selected = 0;
        for source in &rows.sources {
            if source.zone == 0 {
                continue;
            }
            if selected != 0 && selected != source.zone {
                return Err(crate::error_context::value_error(
                    "range endpoints have different timezones; pass an explicit target tz",
                ));
            }
            selected = source.zone;
        }
        match &rows.zones[selected] {
            Zone::Naive => Zone::Naive,
            Zone::Offset(v) => Zone::Offset(*v),
            Zone::Object(v) => Zone::Object(v.clone_ref(py)),
        }
    };
    let selected_object = super::common::zone_object(py, &selected)?;
    let selected_fixed = super::common::fixed_offset(py, &selected)?;
    let finest = tick
        .map(crate::precision::quantum_unit)
        .unwrap_or(Unit::Second);
    let selected_unit = requested.unwrap_or(reader.unit.max(finest));
    let mut coordinates = [None, None];
    let mut known = [None, None];
    for (i, (input, name)) in [(start, "start"), (end, "end")].into_iter().enumerate() {
        let Some(input) = input else {
            continue;
        };
        let Some(ns) = rows.values[i] else {
            continue;
        };
        let source = &rows.sources[i];
        let source_zone = &rows.zones[source.zone];
        let same = super::common::same_zone(py, source_zone, &selected)?;
        let endpoint_policy = policy.endpoint(i == 1);
        let fresh_local = !source.instant && (source.zone == 0 || same);
        let mut utc = None;
        let mut wall = if fresh_local {
            ns
        } else {
            let value = if source.instant {
                ns
            } else if let Some(offset) = super::common::fixed_offset(py, source_zone)? {
                ns.checked_sub(i128::from(offset) * 1000)
                    .ok_or_else(|| crate::error_context::overflow("range source offset overflow"))?
            } else {
                endpoint_utc(py, ns, source_zone, &endpoint_policy, selected_unit)?
            };
            utc = Some(value);
            if let Some(offset) = selected_fixed {
                value
                    .checked_add(i128::from(offset) * 1000)
                    .ok_or_else(|| crate::error_context::overflow("range target offset overflow"))?
            } else {
                super::zones::utc_wall(value, selected_object.bind(py), None)?
            }
        };
        if normalize {
            wall = wall.div_euclid(super::common::NS_DAY) * super::common::NS_DAY;
            utc = None;
        }
        let coordinate = if calendar {
            wall
        } else if let Some(utc) = utc {
            utc
        } else if let Some(offset) = selected_fixed {
            wall.checked_sub(i128::from(offset) * 1000)
                .ok_or_else(|| crate::error_context::overflow("range offset overflow"))?
        } else {
            endpoint_utc(py, wall, &selected, &endpoint_policy, selected_unit)?
        };
        if let Some(unit) = requested {
            // Validate every supplied endpoint, even if rolling, inclusive or
            // an empty range omits it. Calendar generation retains wall fields;
            // unit precision belongs to the stored instant after localization.
            let stored = if calendar {
                if let Some(utc) = utc {
                    utc
                } else if let Some(offset) = selected_fixed {
                    wall.checked_sub(i128::from(offset) * 1000)
                        .ok_or_else(|| crate::error_context::overflow("range offset overflow"))?
                } else {
                    let value = endpoint_utc(py, wall, &selected, &endpoint_policy, unit)?;
                    utc = Some(value);
                    value
                }
            } else {
                coordinate
            };
            validate_endpoint_unit(stored, unit).map_err(|error| {
                crate::error_context::argument(py, error, "Pddt.date_range", name, input)
            })?;
        }
        coordinates[i] = Some(coordinate);
        if calendar {
            known[i] = utc;
        }
    }
    Ok(Endpoints {
        coordinates,
        known,
        unit: selected_unit,
        zone: selected_object,
    })
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared endpoint coordinates, frequency and final array policy"
)]
#[pyo3(signature=(start,end,periods,plan,policy,unit=None,target=None,inclusive="both",known_start=None,known_end=None))]
fn _pddt_range_sequence<'py>(
    py: Python<'py>,
    start: Option<i128>,
    end: Option<i128>,
    periods: Option<usize>,
    plan: Option<PyRef<'_, Plan>>,
    policy: PyRef<'_, super::zones::Policies>,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    inclusive: &str,
    known_start: Option<i128>,
    known_end: Option<i128>,
) -> PyResult<RangeOutput<'py>> {
    let (left, right) = match inclusive {
        "both" => (true, true),
        "left" => (true, false),
        "right" => (false, true),
        "neither" => (false, false),
        _ => {
            return Err(crate::error_context::value_error(
                "inclusive must be 'both', 'left', 'right' or 'neither'",
            ));
        }
    };
    crate::range_generate::arity(
        start.is_some(),
        end.is_some(),
        periods.is_some(),
        plan.is_some(),
    )?;
    let finest = if start
        .into_iter()
        .chain(end)
        .any(|v| v.rem_euclid(1000) != 0)
        || plan
            .as_ref()
            .is_some_and(|p| matches!(p.frequency.kind,Kind::Fixed(v)if v.rem_euclid(1000)!=0))
    {
        Unit::Nanosecond
    } else {
        Unit::Microsecond
    };
    let unit = unit.map(Unit::parse).transpose()?.unwrap_or(finest);
    let mut rows = Rows::new(unit);
    if let Some(length) = periods {
        rows.reserve(length)?;
    }
    let trim = crate::range_generate::generate(
        crate::range_generate::Input {
            start,
            end,
            periods,
            frequency: plan.as_ref().map(|plan| &plan.frequency),
            unit,
            inclusive: (left, right),
            known_start,
            known_end,
        },
        |value, instant| append(&mut rows, py, value, unit, instant),
    )?;
    let (data, unit, zone) = finish(py, rows, Some(unit), target, "Pddt.date_range", &policy)?;
    Ok((data, unit, zone, trim.left, trim.right))
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared public range parameters, without another text parser"
)]
#[pyo3(signature=(start,end,policy,unit=None,target=None,normalize=false,default=None,yearfirst=None,dayfirst=None,isoformat=true,strict=false,cfg=None))]
fn _pddt_range_endpoints<'py>(
    py: Python<'py>,
    start: Option<&Bound<'py, PyAny>>,
    end: Option<&Bound<'py, PyAny>>,
    policy: PyRef<'_, super::zones::Policies>,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    normalize: bool,
    default: Option<&Bound<'py, PyAny>>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    isoformat: bool,
    strict: bool,
    cfg: Option<&Bound<'py, PyAny>>,
) -> PyResult<Endpoints> {
    prepare_endpoints(
        py, start, end, &policy, unit, target, normalize, default, yearfirst, dayfirst, isoformat,
        strict, cfg, true, None,
    )
}

#[pyfunction]
#[pyo3(signature=(inputs,data,source,policy,inclusive,unit=None,infer=false))]
#[expect(
    clippy::too_many_arguments,
    reason = "Final external buffer boundary separates working precision and requested output"
)]
fn _pddt_range_external<'py>(
    py: Python<'py>,
    inputs: PyRef<'_, Endpoints>,
    data: &[u8],
    source: &str,
    policy: PyRef<'_, super::zones::Policies>,
    inclusive: &str,
    unit: Option<&str>,
    infer: bool,
) -> PyResult<RangeOutput<'py>> {
    let (left, right) = match inclusive {
        "both" => (true, true),
        "left" => (true, false),
        "right" => (false, true),
        "neither" => (false, false),
        _ => {
            return Err(crate::error_context::value_error(
                "inclusive must be 'both', 'left', 'right' or 'neither'",
            ));
        }
    };
    if data.len() % 8 != 0 {
        return Err(crate::error_context::runtime(
            "invalid generated date buffer",
        ));
    }
    let source = Unit::parse(source)?;
    let count = data.len() / 8;
    let mut selected = unit.map(Unit::parse).transpose()?.unwrap_or(source);
    let mut rows = Rows::new(selected);
    rows.reserve(count)?;
    let mut first = None;
    let mut last = None;
    for (i, bytes) in data.chunks_exact(8).enumerate() {
        let raw: [u8; 8] = bytes
            .try_into()
            .map_err(|_| crate::error_context::runtime("invalid generated date item"))?;
        let value = i64::from_ne_bytes(raw);
        if value == i64::MIN {
            rows.missing();
            continue;
        }
        let ns = i128::from(value) * source.nanos();
        if infer && ns.rem_euclid(selected.nanos()) != 0 {
            selected = if ns.rem_euclid(1000) == 0 {
                Unit::Microsecond
            } else {
                Unit::Nanosecond
            };
        }
        if i == 0 {
            first = Some(ns);
        }
        if i + 1 == count {
            last = Some(ns);
        }
        let known = if i == 0 && Some(ns) == inputs.coordinates[0] {
            inputs.known[0]
        } else if i + 1 == count && Some(ns) == inputs.coordinates[1] {
            inputs.known[1]
        } else {
            None
        };
        append(&mut rows, py, known.unwrap_or(ns), source, known.is_some())?;
    }
    let (mut trim_left, mut trim_right) = (0, 0);
    if inputs.coordinates[0].is_some() && inputs.coordinates[0] == inputs.coordinates[1] {
        if !left && !right {
            trim_left = usize::from(count > 0);
            trim_right = usize::from(count > 1);
        }
    } else {
        trim_left = usize::from(!left && first.is_some() && first == inputs.coordinates[0]);
        trim_right = usize::from(
            !right && last.is_some() && last == inputs.coordinates[1] && count > trim_left,
        );
    }
    let target = (!inputs.zone.bind(py).is_none()).then(|| inputs.zone.bind(py));
    let (data, unit, zone) = finish(py, rows, Some(selected), target, "Pddt.date_range", &policy)?;
    Ok((data, unit, zone, trim_left, trim_right))
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_frequency, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_range, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_range_endpoints, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_range_external, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_range_sequence, module)?)
}

impl From<crate::range_generate::Error> for PyErr {
    fn from(error: crate::range_generate::Error) -> Self {
        match error {
            crate::range_generate::Error::Value(message) => {
                crate::error_context::value_error(message)
            }
            crate::range_generate::Error::Capacity(message) => {
                crate::error_context::overflow(message)
            }
        }
    }
}
