//! Calendar boundaries and grid/Snap/fraction operations on native columns.
use super::finish::{Failure, Kind};
use crate::epoch::Unit;
use crate::period::{Period, Snap};
use crate::temporal_zone::{Candidates, Zone};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3_polars::{PySeries, derive::polars_expr};
use serde::{Deserialize, Serialize};
const DAY: i128 = 86_400_000_000_000;
impl From<crate::period::Error> for Failure {
    fn from(error: crate::period::Error) -> Self {
        match error {
            crate::period::Error::Value(message) => Self::new(Kind::Value, message),
            crate::period::Error::Capacity(message) => Self::new(Kind::Capacity, message),
            crate::period::Error::Internal(message) => Self::new(Kind::Runtime, message),
        }
    }
}
#[derive(Clone, Copy, Serialize, Deserialize)]
enum Operation {
    Boundary {
        period: Period,
        mode: u8,
        query: bool,
    },
    Round {
        #[serde(with = "crate::serde_values::signed_128")]
        step: i128,
        mode: u8,
    },
    Snap(Period),
    Fsp(i64),
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Spec {
    version: u8,
    operation: Operation,
    entry: String,
}
#[pyclass(frozen, skip_from_py_object, name = "_PldtPeriodContext")]
struct Context {
    spec: Spec,
}
#[pymethods]
impl Context {
    fn plugin_data<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let data = serde_json::to_vec(&self.spec)
            .map_err(|e| crate::error_context::runtime(e.to_string()))?;
        Ok(PyBytes::new(py, &data))
    }
}
#[pyfunction]
#[pyo3(signature=(kind,token,value,mode,query,entry))]
fn _pldt_period_prepare(
    kind: &str,
    token: Option<&str>,
    value: i128,
    mode: u8,
    query: bool,
    entry: &str,
) -> PyResult<Context> {
    let operation = match kind {
        "boundary" if mode <= 3 => Operation::Boundary {
            period: Period::parse(token.unwrap_or(""), mode >= 2)?,
            mode,
            query,
        },
        "snap" => Operation::Snap(Period::parse(token.unwrap_or(""), true)?),
        "round" if value > 0 && mode <= 2 => Operation::Round { step: value, mode },
        "fsp" if value >= 0 => Operation::Fsp(value.min(9) as i64),
        _ => {
            return Err(crate::error_context::value_error(
                "invalid period/grid or negative fractional precision",
            ));
        }
    };
    Ok(Context {
        spec: Spec {
            version: 1,
            operation,
            entry: entry.into(),
        },
    })
}
fn meta(source: &Field, spec: &Spec) -> Result<Field, Failure> {
    if spec.version != 1 {
        return Err(Failure::new(
            Kind::Value,
            "unsupported period preparation version",
        ));
    }
    let valid_period = |period, clock| match period {
        Period::NamedMonth(value) => (1..=12).contains(&value),
        Period::NamedWeekday(value) => clock && (0..=6).contains(&value),
        Period::Tick(value) => {
            clock
                && [
                    1,
                    1000,
                    1_000_000,
                    1_000_000_000,
                    60_000_000_000,
                    3_600_000_000_000,
                ]
                .contains(&value)
        }
        Period::Day => clock,
        _ => true,
    };
    let valid = match spec.operation {
        Operation::Boundary { period, mode, .. } => mode <= 3 && valid_period(period, mode >= 2),
        Operation::Snap(period) => valid_period(period, true),
        Operation::Round { step, mode } => step > 0 && mode <= 2,
        Operation::Fsp(precision) => (0..=9).contains(&precision),
    };
    if !valid {
        return Err(Failure::new(
            Kind::Value,
            "invalid prepared period/grid/fractional role",
        ));
    }
    let query = matches!(spec.operation, Operation::Boundary { query: true, .. });
    let dtype = match source.dtype() {
        DataType::Datetime(_, _) => {
            if query {
                DataType::Boolean
            } else {
                source.dtype().clone()
            }
        }
        DataType::Date if !matches!(spec.operation, Operation::Boundary { .. }) => {
            DataType::Datetime(TimeUnit::Milliseconds, None)
        }
        _ => {
            return Err(Failure::new(
                Kind::Type,
                "requires a Datetime source; use parse/fromdate first",
            ));
        }
    };
    Ok(Field::new(source.name().clone(), dtype))
}
fn aligned(value: i128, unit: Unit, end: bool) -> Result<i128, Failure> {
    crate::period::align(value, unit.nanos(), end).map_err(Failure::from)
}
fn edges(
    lower: i128,
    upper: i128,
    end: bool,
    zone: &Zone,
    unit: Unit,
) -> Result<[Option<i128>; 2], Failure> {
    let wall = if end { upper - 1 } else { lower };
    let mut candidate = zone.candidates(wall)?;
    if let Candidates::Gap { before, after } = candidate {
        let (begin, finish) = zone.gap_edges(wall, before, after)?;
        let shifted = if end { begin - 1 } else { finish };
        if !(lower..upper).contains(&shifted) {
            return Ok([None, None]);
        }
        candidate = zone.candidates(shifted)?;
    }
    let choices = match candidate {
        Candidates::One(value) => [Some(value), None],
        Candidates::Repeated(first, second) => [Some(first), Some(second)],
        Candidates::Gap { .. } => {
            return Err(Failure::new(
                Kind::Value,
                "timezone cannot confirm a valid period boundary",
            ));
        }
    };
    let mut output = [None, None];
    for (index, value) in choices.into_iter().enumerate() {
        if let Some(value) = value {
            let value = aligned(value, unit, end)?;
            if (lower..upper).contains(&zone.wall(value)?) {
                output[index] = Some(value)
            }
        }
    }
    Ok(output)
}
fn edge(
    bounds: (i128, i128),
    end: bool,
    clock: bool,
    source: (i128, i128),
    zone: Option<&Zone>,
    unit: Unit,
) -> Result<Option<i128>, Failure> {
    let (lower, upper) = bounds;
    let fixed = zone.map_or(Some(0), Zone::fixed_seconds);
    if let Some(offset) = fixed {
        let offset = i128::from(offset) * 1_000_000_000;
        let wall = if end { upper - 1 } else { lower };
        let value = aligned(wall - offset, unit, end)?;
        return Ok((lower..upper).contains(&(value + offset)).then_some(value));
    }
    let zone = zone.ok_or_else(|| Failure::new(Kind::Runtime, "missing period region"))?;
    let choices = edges(lower, upper, end, zone, unit)?;
    if clock {
        for value in choices.into_iter().flatten() {
            if zone.wall(value)? - value == source.1 - source.0 {
                return Ok(Some(value));
            }
        }
    }
    Ok(if end {
        choices.into_iter().flatten().max()
    } else {
        choices.into_iter().flatten().min()
    })
}
fn rounded(wall: i128, source: i128, step: i128, mode: u8, zone: &Zone) -> Result<i128, Failure> {
    let select = |candidate| {
        let choices = match candidate {
            Candidates::One(value) => [Some(value), None],
            Candidates::Repeated(a, b) => [Some(a), Some(b)],
            Candidates::Gap { .. } => [None, None],
        };
        choices
            .into_iter()
            .flatten()
            .filter(|value| crate::period::direction(*value, source, mode))
            .min_by_key(|value| ((*value - source).abs(), *value))
    };
    let candidate = zone.candidates(wall)?;
    let Candidates::Gap { before, after } = candidate else {
        return select(candidate).ok_or_else(|| {
            Failure::new(
                Kind::Value,
                "no rounded local occurrence preserves the requested direction",
            )
        });
    };
    let (begin, end) = zone.gap_edges(wall, before, after)?;
    let lower = (begin - 1).div_euclid(step) * step;
    let upper = (end.div_euclid(step) + i128::from(end.rem_euclid(step) != 0)) * step;
    let mut best = None;
    for wall in [lower, upper] {
        if let Some(value) = select(zone.candidates(wall)?) {
            if best.is_none_or(|previous: i128| {
                (value - source).abs() < (previous - source).abs()
                    || ((value - source).abs() == (previous - source).abs() && value > previous)
            }) {
                best = Some(value)
            }
        }
    }
    best.ok_or_else(|| {
        Failure::new(
            Kind::Value,
            "no valid rounded boundary preserves the requested direction",
        )
    })
}
#[derive(Clone, Copy)]
struct Choice {
    start: i128,
    later: bool,
    values: [Option<i128>; 2],
}
struct SnapCache {
    choices: [Option<Choice>; 2],
    next: usize,
}
impl SnapCache {
    fn get(
        &mut self,
        spec: Snap,
        start: i128,
        later: bool,
        zone: &Zone,
        unit: Unit,
    ) -> Result<[Option<i128>; 2], Failure> {
        for choice in self.choices.iter().flatten() {
            if choice.start == start && choice.later == later {
                return Ok(choice.values);
            }
        }
        let values = snap_candidates(spec, start, later, zone, unit)?;
        self.choices[self.next] = Some(Choice {
            start,
            later,
            values,
        });
        self.next ^= 1;
        Ok(values)
    }
}
fn snap_candidates(
    spec: Snap,
    mut start: i128,
    later: bool,
    zone: &Zone,
    unit: Unit,
) -> Result<[Option<i128>; 2], Failure> {
    for _ in 0..4 {
        let choices = edges(start, spec.end(start)?, false, zone, unit)?;
        if choices.iter().any(Option::is_some) {
            return Ok(choices);
        }
        if spec.months != 0 {
            start = spec.shift(start, if later { 1 } else { -1 })?;
            continue;
        }
        let Candidates::Gap { before, after } = zone.candidates(start)? else {
            return Err(Failure::new(
                Kind::Value,
                "no representable adjacent Snap period at this unit",
            ));
        };
        let (begin, end) = zone.gap_edges(start, before, after)?;
        let edge = if later { end } else { begin - 1 };
        let next = start + (edge - start).div_euclid(spec.step) * spec.step;
        start = if next == start {
            spec.shift(start, if later { 1 } else { -1 })?
        } else {
            next
        };
    }
    Err(Failure::new(
        Kind::Value,
        "timezone cannot confirm adjacent existing Snap periods",
    ))
}
fn snapped(
    period: Period,
    wall: i128,
    source: i128,
    zone: Option<&Zone>,
    unit: Unit,
    cache: &mut SnapCache,
) -> Result<i128, Failure> {
    let (spec, lower) = Snap::prepare(period, wall)?;
    let upper = spec.shift(lower, 1)?;
    if let Some(offset) = zone.map_or(Some(0), Zone::fixed_seconds) {
        let offset = i128::from(offset) * 1_000_000_000;
        let first = aligned(lower - offset, unit, false)?;
        if first == source {
            return Ok(source);
        }
        let second = aligned(upper - offset, unit, false)?;
        return Ok(if (source - first).abs() < (second - source).abs() {
            first
        } else {
            second
        });
    }
    let zone = zone.ok_or_else(|| Failure::new(Kind::Runtime, "missing Snap region"))?;
    let mut starts = vec![lower, upper];
    let mut best = None;
    let mut expanded = false;
    let mut next = 0;
    while next < starts.len() {
        let start = starts[next];
        next += 1;
        for value in cache
            .get(spec, start, start >= wall, zone, unit)?
            .into_iter()
            .flatten()
        {
            if value == source {
                return Ok(source);
            }
            if best.is_none_or(|previous: i128| {
                (value - source).abs() < (previous - source).abs()
                    || ((value - source).abs() == (previous - source).abs() && value > previous)
            }) {
                best = Some(value)
            }
        }
        if !expanded && spec.months == 0 && spec.step < DAY {
            if let Candidates::Repeated(a, b) = zone.candidates(start)? {
                expanded = true;
                for offset in [start - a, start - b] {
                    let projected = source + offset;
                    let aligned = spec.period.bounds(projected)?.0;
                    for value in [spec.shift(aligned, -1)?, aligned, spec.shift(aligned, 1)?] {
                        if !starts.contains(&value) {
                            starts.push(value)
                        }
                    }
                }
            }
        }
    }
    best.ok_or_else(|| Failure::new(Kind::Value, "no valid adjacent Snap start"))
}
fn point(
    operation: Operation,
    wall: i128,
    source: i128,
    zone: Option<&Zone>,
    unit: Unit,
    cache: &mut SnapCache,
) -> Result<Option<i128>, Failure> {
    Ok(match operation {
        Operation::Boundary {
            period,
            mode,
            query,
        } => {
            let (lower, upper) = period.bounds(wall)?;
            let end = mode % 2 == 1;
            if mode < 2 {
                let day = (if end { upper - 1 } else { lower }).div_euclid(DAY);
                let target = day * DAY + wall.rem_euclid(DAY);
                Some(if target == wall {
                    source
                } else {
                    match zone {
                        None => target,
                        Some(zone) => {
                            if let Some(offset) = zone.fixed_seconds() {
                                target - i128::from(offset) * 1_000_000_000
                            } else {
                                super::operations::automatic(target, source, wall, zone)?
                            }
                        }
                    }
                })
            } else {
                if query {
                    if !(lower..upper).contains(&wall) {
                        return Ok(None);
                    }
                    let edge_day = (if end { upper - 1 } else { lower }).div_euclid(DAY);
                    let source_day = wall.div_euclid(DAY);
                    if source_day != edge_day
                        && (zone.is_none_or(|zone| zone.fixed_seconds().is_some())
                            || (source_day - edge_day).abs() > 2)
                    {
                        return Ok(None);
                    }
                }
                edge(
                    (lower, upper),
                    end,
                    period.clock(),
                    (source, wall),
                    zone,
                    unit,
                )?
            }
        }
        Operation::Round { step, mode } => {
            let target = crate::period::rounded(wall, step, mode)?;
            Some(if target == wall {
                source
            } else {
                match zone {
                    None => target,
                    Some(zone) => {
                        if let Some(offset) = zone.fixed_seconds() {
                            target - i128::from(offset) * 1_000_000_000
                        } else {
                            rounded(target, source, step, mode, zone)?
                        }
                    }
                }
            })
        }
        Operation::Snap(period) => Some(snapped(period, wall, source, zone, unit, cache)?),
        // Every supported IANA/fixed offset is an integer number of seconds.
        // Truncating within this real second needs no civil/DST conversion.
        Operation::Fsp(precision) => {
            let step = 10i128.pow((9 - precision) as u32);
            Some(source.div_euclid(step) * step)
        }
    })
}
fn no_op(operation: Operation, unit: Unit) -> bool {
    let fine = |step| step <= unit.nanos() && unit.nanos() % step == 0 && 1_000_000_000 % step == 0;
    match operation {
        Operation::Boundary {
            period: Period::Tick(step),
            mode,
            ..
        } if mode >= 2 => fine(step),
        Operation::Snap(Period::Tick(step)) => fine(step),
        Operation::Round { step, .. } => fine(step),
        Operation::Fsp(precision) => fine(10i128.pow((9 - precision) as u32)),
        _ => false,
    }
}
fn execute(source: &Series, spec: &Spec) -> Result<Series, Failure> {
    let field = meta(
        &Field::new(source.name().clone(), source.dtype().clone()),
        spec,
    )?;
    let (unit, name) = match source.dtype() {
        DataType::Datetime(unit, zone) => (super::input::epoch_unit(*unit), zone.as_ref()),
        DataType::Date => (Unit::Millisecond, None),
        _ => return Err(Failure::new(Kind::Runtime, "validated date dtype was lost")),
    };
    let query = matches!(spec.operation, Operation::Boundary { query: true, .. });
    let unchanged = no_op(spec.operation, unit);
    if unchanged && !query && matches!(source.dtype(), DataType::Datetime(_, _)) {
        return Ok(source.clone());
    }
    let zone = if unchanged || matches!(spec.operation, Operation::Fsp(_)) {
        None
    } else {
        name.map(|key| Zone::named(key.as_str()))
            .transpose()
            .map_err(|m| Failure::new(Kind::Value, m))?
    };
    let mut dates = PrimitiveChunkedBuilder::<Int64Type>::new(
        source.name().clone(),
        if query { 0 } else { source.len() },
    );
    let mut flags =
        BooleanChunkedBuilder::new(source.name().clone(), if query { source.len() } else { 0 });
    let mut cache = SnapCache {
        choices: [None, None],
        next: 0,
    };
    let mut push = |row: usize, source: Option<i128>| -> Result<(), Failure> {
        let Some(source) = source else {
            if query {
                flags.append_value(false)
            } else {
                dates.append_null()
            }
            return Ok(());
        };
        if unchanged {
            if query {
                flags.append_value(true)
            } else {
                dates.append_value(
                    crate::precision::epoch_tick(source, unit.nanos(), false)
                        .map_err(|_| Failure::new(Kind::Capacity, "date capacity exceeded"))?,
                )
            }
            return Ok(());
        }
        let wall = zone
            .as_ref()
            .map_or(Ok(source), |zone| zone.wall(source))
            .map_err(|e| Failure::from(e).at(row))?;
        if let Operation::Boundary {
            period,
            mode,
            query: true,
        } = spec.operation
        {
            if mode < 2 {
                let (lower, upper) = period.bounds(wall)?;
                let day = (if mode % 2 == 1 { upper - 1 } else { lower }).div_euclid(DAY);
                flags.append_value(day == wall.div_euclid(DAY));
                return Ok(());
            }
        }
        let target = point(
            spec.operation,
            wall,
            source,
            zone.as_ref(),
            unit,
            &mut cache,
        )
        .map_err(|e| e.at(row))?;
        if query {
            flags.append_value(target == Some(source));
        } else {
            let target = target.ok_or_else(|| {
                Failure::new(
                    Kind::Value,
                    "the requested period has no existing representable local time",
                )
                .at(row)
            })?;
            let value =
                crate::precision::epoch_tick(target, unit.nanos(), false).map_err(|e| match e {
                    crate::precision::TickError::Precision => Failure::new(
                        Kind::Value,
                        "result precision does not fit the current unit; use as_unit explicitly",
                    )
                    .at(row),
                    crate::precision::TickError::Capacity => Failure::new(
                        Kind::Capacity,
                        "period result exceeds the current unit capacity; use as_unit explicitly",
                    )
                    .at(row),
                })?;
            dates.append_value(value);
        }
        Ok(())
    };
    match source.dtype() {
        DataType::Date => {
            for (row, value) in source
                .date()
                .map_err(|e| Failure::new(Kind::Type, e.to_string()))?
                .physical()
                .iter()
                .enumerate()
            {
                push(row, value.map(|value| i128::from(value) * DAY))?
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
                push(row, value.map(|value| i128::from(value) * unit.nanos()))?
            }
        }
    }
    if query {
        Ok(flags.finish().into_series())
    } else {
        let DataType::Datetime(resolution, zone) = field.dtype else {
            return Err(Failure::new(Kind::Runtime, "invalid period output schema"));
        };
        Ok(dates.finish().into_datetime(resolution, zone).into_series())
    }
}
#[derive(Deserialize)]
struct Options {
    #[serde(deserialize_with = "crate::serde_values::byte_vector")]
    prepared: Vec<u8>,
}
fn output_field(fields: &[Field], kwargs: Options) -> PolarsResult<Field> {
    polars_ensure!(fields.len()==1,InvalidOperation:"period operations require one source");
    let spec: Spec =
        serde_json::from_slice(&kwargs.prepared).map_err(|e| polars_err!(ComputeError:"{}",e))?;
    meta(&fields[0], &spec).map_err(|e| e.polars(&spec.entry))
}
#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_period(inputs: &[Series], kwargs: Options) -> PolarsResult<Series> {
    polars_ensure!(inputs.len()==1,InvalidOperation:"period operations require one source");
    let spec: Spec =
        serde_json::from_slice(&kwargs.prepared).map_err(|e| polars_err!(ComputeError:"{}",e))?;
    execute(&inputs[0], &spec).map_err(|e| e.polars(&spec.entry))
}
#[pyfunction]
fn _pldt_period<'py>(
    source: PySeries,
    context: PyRef<'_, Context>,
    target: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let py = target.py();
    let spec = &context.spec;
    let result = py
        .detach(|| execute(&source.0, spec))
        .map_err(|e| e.python(py, &spec.entry))?;
    super::export(py, &result, target)
}
pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pldt_period_prepare, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_period, module)?)
}
