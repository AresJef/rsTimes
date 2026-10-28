//! Shared formatted date fields; only final target builders create Python dates.
use super::{config::FormatRules, fields::Rule, text::TextView};
use crate::epoch::{Parsed, Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyString};
use std::collections::HashMap;

#[derive(Clone)]
enum Step {
    Literal(Vec<u32>),
    Space,
    Field {
        code: char,
        system: bool,
        tail: usize,
    },
    Composite(char),
}

/// Cached pure format structure, independent of live Configs and locale state.
#[pyclass(frozen, name = "_StrptimeFormat")]
pub(crate) struct Format {
    steps: Vec<Step>,
    label: String,
    locale: bool,
    system_words: HashMap<char, Vec<(Vec<u32>, usize, i32)>>,
}

#[pymethods]
impl Format {
    #[getter]
    fn needs_locale(&self) -> bool {
        self.locale
    }
}

fn compile(
    text: &str,
    steps: &mut Vec<Step>,
    seen: &mut std::collections::HashSet<char>,
    templates: Option<&HashMap<String, String>>,
    system: bool,
    depth: usize,
) -> PyResult<()> {
    if depth > 8 {
        return Err(crate::error_context::value_error(
            "LC_TIME templates contain a recursive format",
        ));
    }
    let mut chars = text.chars();
    while let Some(c) = chars.next() {
        if c.is_whitespace() {
            if !matches!(steps.last(), Some(Step::Space)) {
                steps.push(Step::Space);
            }
        } else if c != '%' {
            if let Some(Step::Literal(value)) = steps.last_mut() {
                value.push(u32::from(c));
            } else {
                steps.push(Step::Literal(vec![u32::from(c)]));
            }
        } else {
            let mut code = chars.next().ok_or_else(|| {
                crate::error_context::value_error("format ends with an incomplete '%' directive")
            })?;
            if code == ':' {
                code = chars.next().ok_or_else(|| {
                    crate::error_context::value_error("incomplete timezone directive")
                })?;
                if code != 'z' {
                    return Err(crate::error_context::value_error(
                        "':' is supported only with %z",
                    ));
                }
            }
            let expansion = match code {
                'D' => Some("%m/%d/%y"),
                'F' => Some("%Y-%m-%d"),
                'R' => Some("%H:%M"),
                'T' => Some("%H:%M:%S"),
                'h' => Some("%b"),
                _ => None,
            };
            if let Some(value) = expansion {
                compile(value, steps, seen, templates, system, depth + 1)?;
                continue;
            }
            if matches!(code, 'c' | 'x' | 'X' | 'r') {
                if let Some(templates) = templates {
                    let template = templates.get(&code.to_string()).ok_or_else(|| {
                        crate::error_context::value_error(format!(
                            "LC_TIME does not provide a %{code} template"
                        ))
                    })?;
                    if template.is_empty() {
                        return Err(crate::error_context::value_error(format!(
                            "LC_TIME provides an empty %{code} template"
                        )));
                    }
                    compile(template, steps, seen, Some(templates), true, depth + 1)?;
                } else {
                    steps.push(Step::Composite(code));
                }
                continue;
            }
            if code == '%' {
                steps.push(Step::Literal(vec![37]));
                continue;
            }
            if matches!(code, 'n' | 't') {
                steps.push(Step::Space);
                continue;
            }
            if !matches!(
                code,
                'Y' | 'y'
                    | 'm'
                    | 'd'
                    | 'e'
                    | 'H'
                    | 'I'
                    | 'k'
                    | 'l'
                    | 'M'
                    | 'S'
                    | 'f'
                    | 'b'
                    | 'B'
                    | 'a'
                    | 'A'
                    | 'p'
                    | 'j'
                    | 'G'
                    | 'V'
                    | 'u'
                    | 'w'
                    | 'U'
                    | 'W'
                    | 'z'
                    | 'Z'
            ) {
                return Err(crate::error_context::value_error(format!(
                    "unsupported strptime directive %{code}"
                )));
            }
            if !seen.insert(code) {
                return Err(crate::error_context::value_error(format!(
                    "format repeats %{code}; each directive must identify one field"
                )));
            }
            steps.push(Step::Field {
                code,
                system,
                tail: 0,
            });
        }
    }
    Ok(())
}

#[pyfunction]
#[pyo3(signature=(fmt,templates=None,words=None))]
fn _strptime_compile(
    fmt: &Bound<'_, PyString>,
    templates: Option<&Bound<'_, PyDict>>,
    words: Option<&Bound<'_, PyDict>>,
) -> PyResult<Format> {
    let label = fmt.to_str()?.to_owned();
    let mut steps = Vec::new();
    let templates = templates
        .map(|v| v.extract::<HashMap<String, String>>())
        .transpose()?;
    compile(
        &label,
        &mut steps,
        &mut std::collections::HashSet::new(),
        templates.as_ref(),
        false,
        0,
    )?;
    // Only format structure determines these widths. Cache them in each step
    // instead of rescanning the remaining format for every input value.
    for i in 0..steps.len() {
        let tail = minimum_numeric_tail(&steps[i + 1..]);
        if let Step::Field { tail: stored, .. } = &mut steps[i] {
            *stored = tail;
        }
    }
    let locale = steps.iter().any(|s| matches!(s, Step::Composite(_)));
    let mut system_words = HashMap::new();
    if let Some(words) = words {
        for (key, values) in words.iter() {
            let key = key.extract::<String>()?;
            let code = key
                .chars()
                .next()
                .ok_or_else(|| crate::error_context::runtime("empty system word namespace"))?;
            let values = values.extract::<Vec<(String, i32)>>()?;
            system_words.insert(
                code,
                values
                    .into_iter()
                    .filter(|(v, _)| !v.is_empty())
                    .map(|(word, value)| {
                        let width = word.chars().count();
                        let lowered = word
                            .chars()
                            .flat_map(char::to_lowercase)
                            .map(|c| if c == 'ς' { 'σ' as u32 } else { c as u32 })
                            .collect();
                        (lowered, width, value)
                    })
                    .collect(),
            );
        }
    }
    Ok(Format {
        steps,
        label,
        locale,
        system_words,
    })
}

fn system_word(format: &Format, code: char, input: &[u32]) -> Option<(i32, usize)> {
    let words = format.system_words.get(&code)?;
    if words.is_empty() && code == 'p' {
        return Some((0, 0));
    }
    words
        .iter()
        .filter(|(word, width, _)| {
            input.len() >= *width
                && input[..*width]
                    .iter()
                    .filter_map(|v| char::from_u32(*v))
                    .flat_map(char::to_lowercase)
                    .map(|c| if c == 'ς' { 'σ' as u32 } else { c as u32 })
                    .eq(word.iter().copied())
        })
        .max_by_key(|(_, width, _)| *width)
        .map(|(_, width, value)| (*value, *width))
}

fn decimal(c: u32) -> Option<i64> {
    if (48..=57).contains(&c) {
        return Some(i64::from(c - 48));
    }
    if c < 128 {
        return None;
    }
    // SAFETY: CPython's public Unicode decimal macro accepts a code point and
    // allocates no Python object. It preserves strptime's actual Unicode digits.
    let digit = unsafe { pyo3::ffi::Py_UNICODE_TODECIMAL(c) };
    (digit >= 0).then_some(i64::from(digit))
}

fn numeric(code: char) -> bool {
    matches!(
        code,
        'Y' | 'y'
            | 'm'
            | 'd'
            | 'e'
            | 'H'
            | 'I'
            | 'k'
            | 'l'
            | 'M'
            | 'S'
            | 'f'
            | 'j'
            | 'G'
            | 'V'
            | 'u'
            | 'w'
            | 'U'
            | 'W'
    )
}

fn minimum(code: char) -> usize {
    match code {
        'Y' | 'G' => 4,
        'y' => 2,
        _ => 1,
    }
}

// Reserve the rest of a contiguous digit run, including literal digits. A
// nondigit literal is the explicit boundary that permits a wider year.
fn minimum_numeric_tail(steps: &[Step]) -> usize {
    let mut tail = 0_usize;
    for step in steps {
        match step {
            Step::Field { code, .. } if numeric(*code) => {
                tail = tail.saturating_add(minimum(*code));
            }
            Step::Literal(value) => {
                let digits = value.iter().take_while(|v| decimal(**v).is_some()).count();
                tail = tail.saturating_add(digits);
                if digits < value.len() {
                    break;
                }
            }
            _ => break,
        }
    }
    tail
}

fn read_number(input: &[u32], pos: &mut usize, code: char, tail: usize) -> PyResult<i64> {
    if matches!(code, 'e' | 'k' | 'l') && input.get(*pos) == Some(&32) {
        *pos += 1;
    }
    let negative = matches!(code, 'Y' | 'G') && input.get(*pos) == Some(&45);
    if negative {
        *pos += 1;
    }
    let begin = *pos;
    let run = input[begin..]
        .iter()
        .take_while(|v| decimal(**v).is_some())
        .count();
    let available = run.saturating_sub(tail);
    let max = match code {
        'Y' | 'G' if tail == 0 => available,
        'Y' | 'G' => 4,
        'j' => 3,
        'u' | 'w' => 1,
        _ => 2,
    }
    .min(available);
    let min = minimum(code);
    if max < min {
        return Err(crate::error_context::value_error(
            "numeric field does not match its strptime directive",
        ));
    }
    let bounds = match code {
        'm' => (1, 12),
        'd' | 'e' => (1, 31),
        'H' | 'k' => (0, 23),
        'I' | 'l' => (1, 12),
        'M' => (0, 59),
        'S' => (0, 61),
        'j' => (1, 366),
        'V' => (1, 53),
        'u' => (1, 7),
        'w' => (0, 6),
        'U' | 'W' => (0, 53),
        'y' => (0, 99),
        _ => (i64::MIN, i64::MAX),
    };
    for length in (min..=max).rev() {
        let mut value = 0_i64;
        for &c in &input[begin..begin + length] {
            value = value
                .checked_mul(10)
                .and_then(|v| v.checked_add(decimal(c)?))
                .ok_or_else(|| {
                    crate::error_context::overflow("formatted calendar field exceeds signed64")
                })?;
        }
        if negative {
            value = value
                .checked_neg()
                .ok_or_else(|| crate::error_context::overflow("formatted year exceeds signed64"))?;
        }
        if (bounds.0..=bounds.1).contains(&value) {
            *pos = begin + length;
            return Ok(value);
        }
    }
    Err(crate::error_context::value_error(
        "numeric field is outside the range of its strptime directive",
    ))
}

/// One call's current rules; scalar and complete column parsers share it.
pub(crate) struct Context<'a> {
    format: &'a Format,
    rules: FormatRules,
}

impl<'a> Context<'a> {
    /// Prepare shared ownership once, without caching user word meanings by identity.
    pub(crate) fn prepare(format: &'a Format, cfg: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        if format.locale {
            return Err(crate::error_context::value_error(
                "this format requires prepared LC_TIME templates",
            ));
        }
        Ok(Self {
            format,
            rules: FormatRules::prepare(cfg)?,
        })
    }
}

#[derive(Default)]
struct State {
    year: Option<i64>,
    month: Option<i64>,
    day: Option<i64>,
    hour: i64,
    minute: i64,
    second: i64,
    nanos: i64,
    hour12: bool,
    ampm: Option<i32>,
    doy: Option<i64>,
    weekday: Option<i64>,
    week: Option<(i64, bool)>,
    iso_year: Option<i64>,
    iso_week: Option<i64>,
    zone: Option<Zone>,
    numeric_offset: Option<i64>,
}

/// Finished local fields, retaining native timezone metadata and submicroseconds.
pub(crate) struct Output {
    pub(crate) fields: [i64; 7],
    pub(crate) tail: i64,
    pub(crate) zone: Zone,
}
impl Output {
    /// Convert local fields to integer coordinates before the container's policy.
    pub(crate) fn into_epoch(self) -> PyResult<Parsed> {
        let [y, m, d, h, mi, s, us] = self.fields;
        let ordinal =
            crate::calendar::checked_ordinal(y, m, d).map_err(crate::error_context::overflow)?;
        Ok(Parsed {
            nanos: (i128::from(ordinal) - 719_163) * 86_400_000_000_000
                + ((i128::from(h) * 60 + i128::from(mi)) * 60 + i128::from(s)) * 1_000_000_000
                + i128::from(us) * 1000
                + i128::from(self.tail),
            unit: if self.tail == 0 {
                Unit::Microsecond
            } else {
                Unit::Nanosecond
            },
            zone: self.zone,
        })
    }
}

fn finished(mut state: State) -> PyResult<Output> {
    let year = state.year.unwrap_or(1900);
    let mut ymd = [year, state.month.unwrap_or(1), state.day.unwrap_or(1)];
    let ordinal = if let Some(iso) = state.iso_year {
        if state.doy.is_some() {
            return Err(crate::error_context::value_error(
                "%G is incompatible with %j; use an ISO week and weekday",
            ));
        }
        let week = state.iso_week.ok_or_else(|| {
            crate::error_context::value_error("%G requires %V and a weekday directive")
        })?;
        let weekday = state.weekday.ok_or_else(|| {
            crate::error_context::value_error("%G requires %V and a weekday directive")
        })?;
        let jan1 =
            crate::calendar::checked_ordinal(iso, 1, 1).map_err(crate::error_context::overflow)?;
        let wd = (jan1 - 1).rem_euclid(7);
        let last = 52 + i64::from(wd == 3 || (wd == 2 && crate::calendar::leap(iso)));
        if week > last {
            return Err(crate::error_context::value_error(
                "invalid ISO week for this year",
            ));
        }
        Some(
            crate::calendar::iso_ordinal(iso, week, weekday + 1)
                .map_err(crate::error_context::overflow)?,
        )
    } else if state.iso_week.is_some() {
        return Err(crate::error_context::value_error(
            "%V requires %G and a weekday directive",
        ));
    } else if let Some(day) = state.doy {
        Some(
            crate::calendar::checked_ordinal(year, 1, 1)
                .map_err(crate::error_context::overflow)?
                .checked_add(day - 1)
                .ok_or_else(|| {
                    crate::error_context::overflow(
                        "formatted day-of-year exceeds calendar capacity",
                    )
                })?,
        )
    } else if let (Some((week, monday)), Some(weekday)) = (state.week, state.weekday) {
        let first =
            crate::calendar::checked_ordinal(year, 1, 1).map_err(crate::error_context::overflow)?;
        let mut first_weekday = (first - 1).rem_euclid(7);
        let mut weekday = weekday;
        if !monday {
            first_weekday = (first_weekday + 1) % 7;
            weekday = (weekday + 1) % 7;
        }
        let before = (7 - first_weekday) % 7;
        let day = if week == 0 {
            weekday - first_weekday
        } else {
            before + (week - 1) * 7 + weekday
        };
        Some(first.checked_add(day).ok_or_else(|| {
            crate::error_context::overflow("formatted week exceeds calendar capacity")
        })?)
    } else {
        None
    };
    if let Some(ordinal) = ordinal {
        ymd = crate::calendar::from_ordinal(ordinal).map_err(crate::error_context::overflow)?;
    }
    if !(1..=12).contains(&ymd[1])
        || !(1..=crate::calendar::days_in_month(ymd[0], ymd[1])).contains(&ymd[2])
    {
        return Err(crate::error_context::value_error(
            "day is out of range for month",
        ));
    }
    if state.hour12 {
        state.hour = state.hour % 12 + if state.ampm == Some(1) { 12 } else { 0 };
    }
    if state.second > 59 {
        return Err(crate::error_context::value_error("second must be in 0..59"));
    }
    Ok(Output {
        fields: [
            ymd[0],
            ymd[1],
            ymd[2],
            state.hour,
            state.minute,
            state.second,
            state.nanos / 1000,
        ],
        tail: state.nanos % 1000,
        zone: match state.zone {
            Some(region @ Zone::Object(_)) => region,
            other => state
                .numeric_offset
                .map(Zone::Offset)
                .or(other)
                .unwrap_or(Zone::Naive),
        },
    })
}

/// Read one exact format; no ordinary parser guessing, fallback or Python date.
pub(crate) fn read(context: &Context<'_>, text: &Bound<'_, PyString>) -> PyResult<Output> {
    let view = TextView::new(text)?;
    let input = view.range(0, view.len());
    let mut state = State::default();
    let mut pos = 0;
    for step in &context.format.steps {
        match step {
            Step::Literal(value) => {
                if !input[pos..].starts_with(value) {
                    return Err(mismatch(text, &context.format.label));
                }
                pos += value.len();
            }
            Step::Space => {
                let begin = pos;
                while input
                    .get(pos)
                    .is_some_and(|c| char::from_u32(*c).is_some_and(char::is_whitespace))
                {
                    pos += 1;
                }
                if begin == pos {
                    return Err(mismatch(text, &context.format.label));
                }
            }
            Step::Composite(c) => {
                return Err(crate::error_context::runtime(format!(
                    "unexpanded locale directive %{c}"
                )));
            }
            Step::Field { code, system, tail } => {
                let tail = *tail;
                if numeric(*code) && *code != 'f' {
                    let value = read_number(&input, &mut pos, *code, tail).map_err(|e| {
                        if e.is_instance_of::<pyo3::exceptions::PyOverflowError>(text.py()) {
                            e
                        } else {
                            mismatch(text, &context.format.label)
                        }
                    })?;
                    match code {
                        'Y' => state.year = Some(value),
                        'y' => state.year = Some(value + if value <= 68 { 2000 } else { 1900 }),
                        'm' => state.month = Some(value),
                        'd' | 'e' => state.day = Some(value),
                        'H' | 'k' => {
                            state.hour = value;
                            state.hour12 = false;
                        }
                        'I' | 'l' => {
                            state.hour = value;
                            state.hour12 = true;
                        }
                        'M' => state.minute = value,
                        'S' => state.second = value,
                        'j' => state.doy = Some(value),
                        'G' => state.iso_year = Some(value),
                        'V' => state.iso_week = Some(value),
                        'u' => state.weekday = Some(value - 1),
                        'w' => state.weekday = Some((value + 6) % 7),
                        'U' | 'W' => state.week = Some((value, *code == 'W')),
                        _ => {}
                    }
                } else if *code == 'f' {
                    let begin = pos;
                    let run = input[pos..]
                        .iter()
                        .take_while(|v| decimal(**v).is_some())
                        .count();
                    let count = run.saturating_sub(tail);
                    if count == 0 {
                        return Err(mismatch(text, &context.format.label));
                    }
                    let mut ns = 0;
                    for &c in &input[pos..pos + count.min(9)] {
                        ns = ns * 10 + decimal(c).unwrap_or(0);
                    }
                    ns *= 10_i64.pow((9 - count.min(9)) as u32);
                    state.nanos = ns;
                    pos = begin + count;
                } else {
                    let rule = match code {
                        'b' | 'B' => Some(Rule::Month),
                        'a' | 'A' => Some(Rule::Weekday),
                        'p' => Some(Rule::Ampm),
                        _ => None,
                    };
                    if let Some(rule) = rule {
                        let (value, count) = if *system {
                            system_word(context.format, *code, &input[pos..])
                        } else {
                            context.rules.word(rule, &input[pos..])
                        }
                        .ok_or_else(|| mismatch(text, &context.format.label))?;
                        pos += count;
                        match code {
                            'b' | 'B' => state.month = Some(i64::from(value)),
                            'a' | 'A' => state.weekday = Some(i64::from(value)),
                            'p' => state.ampm = Some(value),
                            _ => {}
                        }
                    } else if *code == 'Z' {
                        if let Some((registered, count)) = context.rules.region(&input[pos..]) {
                            state.zone=Some(Zone::Object(registered.object.as_ref().ok_or_else(||crate::error_context::value_error("registered %Z region is unavailable; restore its timezone data"))?.clone_ref(text.py())));
                            pos += count;
                        } else if let Some((_, count)) =
                            context.rules.word(Rule::Utc, &input[pos..])
                        {
                            state.zone = Some(Zone::Offset(0));
                            pos += count;
                        } else if let Some((seconds, count)) =
                            context.rules.word(Rule::Tz, &input[pos..])
                        {
                            state.zone = Some(Zone::Offset(i64::from(seconds) * 1_000_000));
                            pos += count;
                        } else {
                            return Err(crate::error_context::value_error(
                                "%Z name is unknown; register it with Configs.add_tzone/add_tzoffset, or use %z for a numeric offset",
                            ));
                        }
                    } else if *code == 'z' {
                        state.numeric_offset = Some(
                            offset(&input, &mut pos)
                                .map_err(|_| mismatch(text, &context.format.label))?,
                        );
                    }
                }
            }
        }
    }
    if pos != input.len() {
        let rest: String = input[pos..]
            .iter()
            .take(120)
            .map(|v| char::from_u32(*v).unwrap_or('\u{fffd}'))
            .collect();
        return Err(crate::error_context::value_error(format!(
            "unconverted data remains: {rest}"
        )));
    }
    finished(state)
}

fn mismatch(text: &Bound<'_, PyString>, fmt: &str) -> PyErr {
    match crate::error_context::preview(text.as_any()) {
        Ok(value) => crate::error_context::value_error(format!(
            "time data {value} does not match format {:?}",
            fmt.chars().take(120).collect::<String>()
        )),
        Err(error) => error,
    }
}

fn offset(input: &[u32], pos: &mut usize) -> PyResult<i64> {
    if input.get(*pos) == Some(&90) {
        *pos += 1;
        return Ok(0);
    }
    let negative = match input.get(*pos) {
        Some(45) => true,
        Some(43) => false,
        _ => return Err(crate::error_context::value_error("invalid %z sign")),
    };
    *pos += 1;
    let pair = |position: &mut usize| -> PyResult<i64> {
        let a = input
            .get(*position)
            .and_then(|v| decimal(*v))
            .ok_or_else(|| crate::error_context::value_error("incomplete %z offset"))?;
        let b = input
            .get(*position + 1)
            .and_then(|v| decimal(*v))
            .ok_or_else(|| crate::error_context::value_error("incomplete %z offset"))?;
        *position += 2;
        Ok(a * 10 + b)
    };
    let h = pair(pos)?;
    let colon = input.get(*pos) == Some(&58);
    if colon {
        *pos += 1;
    }
    let m = pair(pos)?;
    let mut s = 0;
    if colon && input.get(*pos) == Some(&58) {
        *pos += 1;
        s = pair(pos)?;
    } else if !colon && input.get(*pos).is_some_and(|v| decimal(*v).is_some()) {
        s = pair(pos)?;
    }
    let mut us = 0;
    if input.get(*pos) == Some(&46) {
        *pos += 1;
        let start = *pos;
        while input.get(*pos).is_some_and(|v| decimal(*v).is_some()) && *pos - start < 6 {
            us = us * 10 + decimal(input[*pos]).unwrap_or(0);
            *pos += 1;
        }
        if *pos == start {
            return Err(crate::error_context::value_error("empty %z fraction"));
        }
        us *= 10_i64.pow((6 - (*pos - start)) as u32);
    }
    if h > 23 || m > 59 || s > 59 {
        return Err(crate::error_context::value_error(
            "%z offset outside one day",
        ));
    }
    let value = ((h * 60 + m) * 60 + s) * 1_000_000 + us;
    Ok(if negative { -value } else { value })
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_strptime_compile, module)?)
}
