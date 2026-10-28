//! Native parser rules with independent Python configuration snapshots.
use super::fields::{ParseResult, Rule, RuleLookup};
use super::text::{TextView, ascii_letter, digit, space, tokenize};
use super::zones::{self, RegisteredZone, ZoneMap};

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyInt, PySet, PyString, PyTuple};
use std::collections::HashMap;
use std::ops::{Deref, DerefMut};
use std::sync::Arc;
type Token = Vec<u32>;
#[derive(Default, Clone)]
struct Rules {
    base: HashMap<Token, i32>,
    ext: HashMap<Token, i32>,
    base_order: Vec<Token>,
    ext_order: Vec<Token>,
    generation: u64,
}

// Copies share immutable rules until an edit detaches the changed namespace.
// No Python callback or mutable owner participates in native token lookup.
#[derive(Default, Clone)]
struct Namespace(Arc<Rules>);

impl Deref for Namespace {
    type Target = Rules;

    fn deref(&self) -> &Rules {
        &self.0
    }
}

impl DerefMut for Namespace {
    fn deref_mut(&mut self) -> &mut Rules {
        Arc::make_mut(&mut self.0)
    }
}

impl Namespace {
    fn put_base(&mut self, key: Token, value: i32) {
        if !self.base.contains_key(&key) {
            self.base_order.push(key.clone());
        }
        self.base.insert(key, value);
    }
    fn put_ext(&mut self, key: Token, value: i32) {
        if !self.ext.contains_key(&key) {
            self.ext_order.push(key.clone());
        }
        self.ext.insert(key, value);
    }
    fn base_entries(&self) -> Vec<(Token, i32)> {
        self.base_order
            .iter()
            .filter_map(|k| self.base.get(k).map(|v| (k.clone(), *v)))
            .collect()
    }
}
type Owner = Namespace;
/// Rust-only shared view of all recognition namespaces.
#[derive(Clone)]
pub(crate) struct NativeView<'a> {
    owners: &'a [Owner; 8],
}

/// Cheap immutable rule ownership for one formatted batch; edits detach normally.
pub(crate) struct FormatRules {
    owners: [Owner; 8],
    zones: Arc<ZoneMap>,
}
impl FormatRules {
    /// Capture one effective set without copying any complete vocabulary table.
    pub(crate) fn prepare(value: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        if let Some(value) = value.filter(|v| !v.is_none()) {
            let cfg = value
                .cast::<Configs>()
                .map_err(|_| {
                    crate::error_context::type_error("cfg must be a Configs instance or None")
                })?
                .borrow();
            Ok(Self {
                owners: cfg.owners.clone(),
                zones: cfg.zones.clone(),
            })
        } else {
            Ok(Self {
                owners: defaults().clone(),
                zones: Arc::new(ZoneMap::new()),
            })
        }
    }
    /// Longest registered word at the current formatted input position.
    pub(crate) fn word(&self, rule: Rule, input: &[u32]) -> Option<(i32, usize)> {
        self.owners[rule_namespace(rule)]
            .ext
            .iter()
            .filter(|(key, _)| input.starts_with(key.as_slice()))
            .max_by_key(|(key, _)| key.len())
            .map(|(key, value)| (*value, key.len()))
    }
    /// Longest explicit IANA region; never infer an operating-system abbreviation.
    pub(crate) fn region(&self, input: &[u32]) -> Option<(Arc<RegisteredZone>, usize)> {
        self.zones
            .iter()
            .filter(|(key, _)| input.starts_with(key.as_slice()))
            .max_by_key(|(key, _)| key.len())
            .map(|(key, value)| (value.clone(), key.len()))
    }
}
#[inline]
fn rule_namespace(rule: Rule) -> usize {
    match rule {
        Rule::Jump => 0,
        Rule::Pertain => 1,
        Rule::Utc => 2,
        Rule::Tz => 3,
        Rule::Month => 4,
        Rule::Weekday => 5,
        Rule::Hms | Rule::HmsContains => 6,
        Rule::Ampm => 7,
    }
}
#[inline]
fn namespace_value(namespace: &Namespace, rule: Rule, token: &[u32]) -> i32 {
    if matches!(rule, Rule::HmsContains) {
        i32::from(namespace.ext.contains_key(token))
    } else {
        namespace.ext.get(token).copied().unwrap_or(match rule {
            Rule::Jump | Rule::Pertain | Rule::Utc => 0,
            Rule::Tz => -100_000,
            _ => -1,
        })
    }
}
impl NativeView<'_> {
    /// Query immutable native rules without a lock or Python container.
    pub(crate) fn get(&self, rule: Rule, token: &[u32]) -> i32 {
        namespace_value(&self.owners[rule_namespace(rule)], rule, token)
    }
}

/// Read a library-default rule directly from Rust without a Configs object.
/// User configuration mutations cannot change this immutable vocabulary.
#[inline]
pub(crate) fn default_lookup(rule: Rule, token: &[u32]) -> i32 {
    namespace_value(&defaults()[rule_namespace(rule)], rule, token)
}

/// Immutable library vocabulary, requiring no Python Configs instance.
/// User-provided configurations borrow their immutable native rule data.
pub(super) struct DefaultView;
impl RuleLookup for DefaultView {
    fn query(&mut self, rule: Rule, token: &[u32]) -> ParseResult<i32> {
        Ok(default_lookup(rule, token))
    }
}

impl RuleLookup for NativeView<'_> {
    fn query(&mut self, rule: Rule, token: &[u32]) -> ParseResult<i32> {
        Ok(self.get(rule, token))
    }
}
/// Token-recognition rules and ambiguous calendar-order preferences for parse.
/// Configs cannot be subclassed; customize its rules with add/del/set.
///
/// Configs(yearfirst=True, dayfirst=False) starts with multilingual default rules.
/// Word tokens are stored in lowercase and recognized in lowercase, uppercase,
/// and titlecase. Jump tokens may overlap other word tables. Other word-table
/// conflicts are rejected. Property containers are independent copies.
/// Register exact regional names with add_tzone; fixed offsets use tzoffset.
///
/// copy.copy, copy.deepcopy and pickle round trips produce independent rules.
/// Editing either configuration does not change the other.
#[pyclass(module = "rstimes.parser")]
pub(crate) struct Configs {
    owners: [Owner; 8],
    cache: [Option<(Owner, u64, Py<PyAny>)>; 8],
    yearfirst: bool,
    dayfirst: bool,
    zones: Arc<ZoneMap>,
}
fn empty_owners() -> [Owner; 8] {
    std::array::from_fn(|_| Namespace::default())
}
fn encode(s: &Bound<'_, PyAny>) -> PyResult<Token> {
    let s = s.cast::<PyString>()?;
    let view = TextView::new(s)?;
    Ok(view.range(0, view.len()))
}
fn validate_token_type(token: &Bound<'_, PyAny>) -> PyResult<()> {
    if !token.is_exact_instance_of::<PyString>() {
        return Err(crate::error_context::type_error(format!(
            "Argument 'token' has incorrect type (expected str, got {})",
            crate::error_context::preview(token)?
        )));
    }
    Ok(())
}
fn variants(low: &Bound<'_, PyAny>, key: &Token) -> PyResult<[Token; 3]> {
    if low.is_exact_instance_of::<PyString>() && key.iter().all(|c| *c < 128) {
        let lower = key
            .iter()
            .map(|c| if (65..=90).contains(c) { *c + 32 } else { *c })
            .collect();
        let upper = key
            .iter()
            .map(|c| if (97..=122).contains(c) { *c - 32 } else { *c })
            .collect();
        let mut cased = false;
        let title = key
            .iter()
            .map(|c| {
                let letter = (65..=90).contains(c) || (97..=122).contains(c);
                let out = if letter && !cased {
                    if (97..=122).contains(c) { *c - 32 } else { *c }
                } else if letter {
                    if (65..=90).contains(c) { *c + 32 } else { *c }
                } else {
                    *c
                };
                cased = letter;
                out
            })
            .collect();
        return Ok([lower, upper, title]);
    }
    Ok([
        encode(
            &low.call_method0("lower")
                .map_err(crate::error_context::external)?,
        )?,
        encode(
            &low.call_method0("upper")
                .map_err(crate::error_context::external)?,
        )?,
        encode(
            &low.call_method0("title")
                .map_err(crate::error_context::external)?,
        )?,
    ])
}

/// Reject aliases that the existing lexer cannot consume as this rule.
/// This runs only when editing or restoring configuration, never while parsing.
fn validate_recognized_form(
    receiver: &Bound<'_, Configs>,
    namespace: usize,
    variant: &[u32],
    value: i32,
) -> PyResult<()> {
    if namespace == 0 && variant.len() == 1 && space(variant[0]) {
        return Ok(());
    }
    let text = decode(receiver.py(), variant)?;
    let view = TextView::new(text.cast::<PyString>()?)?;
    let tokens = tokenize(&view, 0);
    let one_token = tokens.len() == 1 && tokens.get(0) == Some(variant);
    let usable = one_token
        && variant.first().is_some_and(|&ch| !digit(ch) && !space(ch))
        && (namespace != 3 || variant.iter().all(|&ch| ascii_letter(ch)));
    if usable && variant == [58] && ((namespace == 6 && value != 0) || namespace == 7) {
        return Err(config_error(
            receiver,
            "ConfigError",
            format!(
                "Token ':' is an hour separator and cannot be a {} alias with value {}; choose another word",
                NAMES[namespace], value,
            ),
        ));
    }
    if usable {
        return Ok(());
    }
    Err(config_error(
        receiver,
        "ConfigError",
        format!(
            "Token {} for {} cannot be read as one {} alias; use a single word{}",
            crate::error_context::preview(&text)?,
            NAMES[namespace],
            NAMES[namespace],
            if namespace == 3 {
                " containing ASCII letters"
            } else {
                " without numeric or split punctuation parts"
            },
        ),
    ))
}
fn copy_display<'py>(
    py: Python<'py>,
    value: &Bound<'py, PyAny>,
    i: usize,
) -> PyResult<Bound<'py, PyAny>> {
    if i < 3 {
        // SAFETY: value is a live set; PySet_New returns an owned independent copy.
        unsafe { Bound::from_owned_ptr_or_err(py, ffi::PySet_New(value.as_ptr())) }
    } else {
        Ok(value.cast::<PyDict>()?.copy()?.into_any())
    }
}

fn decode<'py>(py: Python<'py>, s: &[u32]) -> PyResult<Bound<'py, PyAny>> {
    // SAFETY: input is valid Python code points and the slice remains alive during copying.
    unsafe {
        Bound::from_owned_ptr_or_err(
            py,
            ffi::PyUnicode_FromKindAndData(
                ffi::PyUnicode_4BYTE_KIND as i32,
                s.as_ptr().cast(),
                s.len() as isize,
            ),
        )
    }
}
const NAMES: [&str; 8] = [
    "jump", "pertain", "utc", "tzoffset", "month", "weekday", "hms", "ampm",
];
fn config_error(receiver: &Bound<'_, Configs>, kind: &str, msg: String) -> PyErr {
    crate::error_context::domain(receiver.py(), kind, msg)
}
/// Label a configuration edit while preserving its useful domain category.
fn edit_error(receiver: &Bound<'_, Configs>, entry: &str, error: PyErr) -> PyErr {
    crate::error_context::argument(receiver.py(), error, entry, "arguments", receiver.as_any())
}
fn ensure_token(
    _receiver: &Bound<'_, Configs>,
    i: usize,
    token: &Bound<'_, PyAny>,
) -> PyResult<()> {
    if token.is_instance_of::<PyString>() && !token.is_exact_instance_of::<PyString>() {
        return Err(crate::error_context::type_error(format!(
            "Expected str, got {}",
            crate::error_context::preview(token)?
        )));
    }
    if !token.is_instance_of::<PyString>() {
        return Err(crate::error_context::type_error(format!(
            "token for {} must be an exact str; got {}",
            NAMES[i],
            crate::error_context::preview(token)?
        )));
    }
    Ok(())
}
fn normalize<'py>(
    receiver: &Bound<'_, Configs>,
    i: usize,
    token: &Bound<'py, PyAny>,
    ensure: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let ns = NAMES[i];
    if !token.is_exact_instance_of::<PyString>() {
        if ensure {
            return Err(crate::error_context::type_error(format!(
                "token for {ns} must be an exact str; got {}",
                crate::error_context::preview(token)?
            )));
        }
        return Err(crate::error_context::type_error(format!(
            "Argument 'token' has incorrect type (expected str, got {})",
            crate::error_context::preview(token)?
        )));
    }
    if TextView::new(token.cast::<PyString>()?)?.len() == 0 {
        return Err(config_error(
            receiver,
            "ConfigError",
            format!("Token for 'Configs.{ns}' cannot be an empty string."),
        ));
    }
    token
        .call_method0("lower")
        .map_err(crate::error_context::external)
}

pub(super) fn c_int(value: &Bound<'_, PyAny>) -> PyResult<i32> {
    if crate::numeric::is_bool(value) {
        return Err(crate::error_context::type_error(
            "integer codes and offsets do not accept boolean values",
        ));
    }
    if value.is_instance_of::<PyString>() || value.is_none() {
        return Err(crate::error_context::type_error("an integer is required"));
    }
    // SAFETY: attached interpreter; PyNumber_Index accepts integer values without truncating floats.
    let converted = if value.is_exact_instance_of::<PyInt>() {
        value.clone()
    } else {
        unsafe { Bound::from_owned_ptr_or_err(value.py(), ffi::PyNumber_Index(value.as_ptr())) }
            .map_err(crate::error_context::external)?
    };
    let integer = converted
        .extract::<i64>()
        .map_err(crate::error_context::own)?;
    i32::try_from(integer)
        .map_err(|_| crate::error_context::overflow("value too large to convert to int"))
}
// Three signed-32-bit components fit safely in a signed-64-bit total.
// Let the configuration range check distinguish invalid values from overflow.
fn tz_seconds(hours: i32, minutes: i32, seconds: i32) -> i64 {
    i64::from(hours) * 3600 + i64::from(minutes) * 60 + i64::from(seconds)
}

/// Validate one base entry without rebuilding a partially filled word table.
fn base_entry(
    receiver: &Bound<'_, Configs>,
    i: usize,
    token: &Bound<'_, PyAny>,
    value: i64,
) -> PyResult<(Token, i32)> {
    let low = normalize(receiver, i, token, false)?;
    let key = encode(&low)?;
    let (min, max) = match i {
        3 => (-86399, 86399),
        4 => (1, 12),
        5 => (0, 6),
        6 => (0, 2),
        7 => (0, 1),
        _ => (0, 1),
    };
    if value < min || value > max {
        return Err(config_error(
            receiver,
            "ConfigError",
            format!(
                "{} must be an integer from {min} through {max}, inclusive; got {value}",
                NAMES[i]
            ),
        ));
    }
    Ok((key, value as i32))
}

/// Edit one base word and rebuild its recognized forms once.
fn add(
    receiver: &Bound<'_, Configs>,
    i: usize,
    token: &Bound<'_, PyAny>,
    value: i64,
) -> PyResult<bool> {
    let (key, value) = base_entry(receiver, i, token, value)?;
    let mut owner = receiver.borrow().owners[i].clone();
    owner.generation = owner.generation.wrapping_add(1);
    owner.put_base(key, value);
    let owner = rebuild_namespace(receiver, i, owner)?;
    set_namespace(receiver, i, owner);
    Ok(true)
}

/// Check actual recognized forms, including Unicode case expansions.
/// No live configuration borrow is retained while formatting Python errors.
fn validate_namespace(receiver: &Bound<'_, Configs>, i: usize, owner: &Owner) -> PyResult<()> {
    if i == 0 {
        return Ok(());
    }
    let owners = receiver.borrow().owners.clone();
    for key in owner.ext.keys() {
        for (j, other) in owners.iter().enumerate().skip(1) {
            if j != i && other.ext.contains_key(key) {
                return Err(config_error(
                    receiver,
                    "ConfigError",
                    format!(
                        "recognized token {} for {} conflicts with {}",
                        crate::error_context::preview(&decode(receiver.py(), key)?)?,
                        NAMES[i],
                        NAMES[j]
                    ),
                ));
            }
        }
    }
    Ok(())
}

/// Rebuild only an edited namespace; parsing continues to borrow native maps.
fn rebuild_namespace(receiver: &Bound<'_, Configs>, i: usize, mut owner: Owner) -> PyResult<Owner> {
    let entries = owner.base_entries();
    owner.ext.clear();
    owner.ext_order.clear();
    for (key, value) in entries {
        let low = decode(receiver.py(), &key)?;
        for variant in variants(&low, &key)? {
            validate_recognized_form(receiver, i, &variant, value)?;
            if owner
                .ext
                .get(&variant)
                .is_some_and(|previous| *previous != value)
            {
                return Err(config_error(
                    receiver,
                    "ConfigError",
                    format!(
                        "recognized token {} has conflicting values in {}",
                        crate::error_context::preview(&decode(receiver.py(), &variant)?)?,
                        NAMES[i]
                    ),
                ));
            }
            owner.put_ext(variant, value);
        }
    }
    validate_namespace(receiver, i, &owner)?;
    Ok(owner)
}

fn remove(receiver: &Bound<'_, Configs>, i: usize, token: &Bound<'_, PyAny>) -> PyResult<bool> {
    let low = normalize(receiver, i, token, false)?;
    let key = encode(&low)?;
    let mut owner = receiver.borrow().owners[i].clone();
    if owner.base.remove(&key).is_none() {
        return Ok(false);
    }
    owner.base_order.retain(|v| v != &key);
    owner.generation = owner.generation.wrapping_add(1);
    let owner = rebuild_namespace(receiver, i, owner)?;
    set_namespace(receiver, i, owner);
    Ok(true)
}
fn display<'py>(receiver: &Bound<'py, Configs>, i: usize) -> PyResult<Bound<'py, PyAny>> {
    let py = receiver.py();
    let cached = {
        let cfg = receiver.borrow();
        let owner = &cfg.owners[i];
        let generation = owner.generation;
        cfg.cache[i]
            .as_ref()
            .filter(|(o, g, _)| Arc::ptr_eq(&o.0, &owner.0) && *g == generation)
            .map(|(_, _, v)| v.clone_ref(py))
    };
    if let Some(cached) = cached {
        return copy_display(py, cached.bind(py), i);
    }
    let owner = receiver.borrow().owners[i].clone();
    let generation = owner.generation;
    let entries = owner.base_entries();
    let out = if i < 3 {
        let out = PySet::empty(py)?;
        for (k, _) in &entries {
            out.add(decode(py, k)?)?;
        }
        out.into_any()
    } else {
        let out = PyDict::new(py);
        for (k, v) in entries {
            out.set_item(decode(py, &k)?, v)?;
        }
        out.into_any()
    };
    receiver.borrow_mut().cache[i] = Some((owner, generation, out.clone().unbind()));
    copy_display(py, &out, i)
}
// Drop cached Python containers only after releasing the mutable borrow.
fn set_namespace(receiver: &Bound<'_, Configs>, i: usize, owner: Owner) {
    let retired = {
        let mut cfg = receiver.borrow_mut();
        (
            std::mem::replace(&mut cfg.owners[i], owner),
            cfg.cache[i].take(),
        )
    };
    drop(retired);
}
fn detach_namespace(receiver: &Bound<'_, Configs>, i: usize) -> PyResult<()> {
    set_namespace(receiver, i, Namespace::default());
    Ok(())
}
fn replace(
    receiver: &Bound<'_, Configs>,
    i: usize,
    input: Option<&Bound<'_, PyAny>>,
) -> PyResult<bool> {
    let Some(input) = input.filter(|v| !v.is_none()) else {
        let owner = defaults()[i].clone();
        validate_namespace(receiver, i, &owner)?;
        set_namespace(receiver, i, owner);
        return Ok(true);
    };
    if !(if i < 3 {
        input.is_instance_of::<PySet>()
    } else {
        input.is_instance_of::<PyDict>()
    }) {
        return Err(crate::error_context::type_error(format!(
            "Argument '{}' has incorrect type (expected {}, got {})",
            if i < 3 { "tokens" } else { "mapping" },
            if i < 3 { "set" } else { "dict" },
            crate::error_context::preview(input)?
        )));
    }
    // Retain all inputs before conversions can call Python or mutate the source.
    let entries: Vec<(Py<PyAny>, Option<Py<PyAny>>)> = if i < 3 {
        input
            .cast::<PySet>()?
            .iter()
            .map(|key| (key.unbind(), None))
            .collect()
    } else {
        input
            .cast::<PyDict>()?
            .iter()
            .map(|(key, value)| (key.unbind(), Some(value.unbind())))
            .collect()
    };
    let temporary = Py::new(receiver.py(), receiver.borrow().independent())?;
    let temporary = temporary.bind(receiver.py());
    let mut owner = Namespace::default();
    for (token, value) in entries {
        let token = token.bind(receiver.py());
        ensure_token(temporary, i, token)?;
        let number = match value {
            Some(value) => i64::from(c_int(value.bind(receiver.py()))?),
            None => 1,
        };
        let (key, number) = base_entry(temporary, i, token, number)?;
        owner.put_base(key, number);
    }
    let owner = rebuild_namespace(temporary, i, owner)?;
    // A numeric callback may have changed another live namespace. Recheck at
    // commit, without replacing any unrelated changes made by that callback.
    validate_namespace(receiver, i, &owner)?;
    set_namespace(receiver, i, owner);
    Ok(true)
}

const STATE_TAG: &str = "rstimes.Configs";
fn snapshot_state(slf: &Bound<'_, Configs>) -> PyResult<Py<PyAny>> {
    let py = slf.py();
    let (flags, all) = {
        let cfg = slf.borrow();
        (
            cfg.flags(),
            cfg.owners
                .iter()
                .map(|o| o.base_entries())
                .collect::<Vec<_>>(),
        )
    };
    let mut containers = Vec::with_capacity(8);
    for (i, entries) in all.into_iter().enumerate() {
        if i < 3 {
            let out = PySet::empty(py)?;
            for (key, _) in entries {
                out.add(decode(py, &key)?)?;
            }
            containers.push(out.into_any());
        } else {
            let out = PyDict::new(py);
            for (key, value) in entries {
                out.set_item(decode(py, &key)?, value)?;
            }
            containers.push(out.into_any());
        }
    }
    let namespaces = PyTuple::new(py, containers)?;
    let regions = zones::names(py, &slf.borrow().zones)?;
    Ok((STATE_TAG, 2, flags.0, flags.1, namespaces, regions)
        .into_pyobject(py)?
        .into_any()
        .unbind())
}
fn reduction(slf: &Bound<'_, Configs>) -> PyResult<Py<PyAny>> {
    let restore = slf
        .py()
        .import("rstimes.parser")?
        .getattr("_restore_configs")
        .map_err(crate::error_context::external)?;
    Ok((restore, (), snapshot_state(slf)?)
        .into_pyobject(slf.py())?
        .into_any()
        .unbind())
}

/// Allocate the fixed configuration type for the versioned pickle protocol.
#[pyfunction]
#[pyo3(signature=(*args))]
fn _restore_configs(args: &Bound<'_, PyTuple>) -> PyResult<Configs> {
    if !args.is_empty() {
        return Err(crate::error_context::value_error(
            "Unsupported legacy Configs pickle format",
        ));
    }
    Ok(Configs::empty())
}

impl Configs {
    fn empty() -> Self {
        Self {
            owners: empty_owners(),
            cache: std::array::from_fn(|_| None),
            yearfirst: false,
            dayfirst: false,
            zones: Arc::new(ZoneMap::new()),
        }
    }
    /// Share immutable rules; subsequent edits detach only the changed namespace.
    fn independent(&self) -> Self {
        Self {
            owners: self.owners.clone(),
            cache: std::array::from_fn(|_| None),
            yearfirst: self.yearfirst,
            dayfirst: self.dayfirst,
            zones: self.zones.clone(),
        }
    }
    /// Return ordering flags independently of overridden Python attributes.
    pub(crate) fn flags(&self) -> (bool, bool) {
        (self.yearfirst, self.dayfirst)
    }
    /// Obtain ordinary native recognition storage.
    pub(crate) fn native_view(&self) -> NativeView<'_> {
        NativeView {
            owners: &self.owners,
        }
    }
    pub(super) fn zone(&self, token: &[u32]) -> Option<Arc<RegisteredZone>> {
        self.zones.get(token).cloned()
    }
    pub(super) fn has_zones(&self) -> bool {
        !self.zones.is_empty()
    }
}
#[pymethods]
impl Configs {
    #[new]
    #[pyo3(signature=(*_args,**_kwargs))]
    fn new(_args: &Bound<'_, PyTuple>, _kwargs: Option<&Bound<'_, PyDict>>) -> Self {
        Self::empty()
    }
    /// Return a configuration whose later edits do not affect the source.
    fn __copy__(&self) -> Self {
        self.independent()
    }
    /// Return independent token namespaces and record the copy in memo.
    fn __deepcopy__(slf: &Bound<'_, Self>, memo: &Bound<'_, PyDict>) -> PyResult<Py<Self>> {
        let out = slf.borrow().independent();
        let out = Py::new(slf.py(), out)?;
        memo.set_item(slf.as_ptr() as usize, &out)?;
        Ok(out)
    }
    /// Return reconstruction information with an independent versioned snapshot.
    fn __reduce__(slf: &Bound<'_, Self>) -> PyResult<Py<PyAny>> {
        reduction(slf)
    }
    /// Return reconstruction information for the requested pickle protocol.
    fn __reduce_ex__(slf: &Bound<'_, Self>, protocol: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let _ = protocol;
        reduction(slf)
    }
    /// Restore a versioned snapshot after validating every namespace.
    ///
    /// Invalid states leave this configuration unchanged. Legacy state layouts
    /// are rejected. Restored rules do not share the input containers.
    fn __setstate__(slf: &Bound<'_, Self>, state: &Bound<'_, PyAny>) -> PyResult<()> {
        (|| {
            let state = state.cast_exact::<PyTuple>().map_err(|_| {
                crate::error_context::expected_type(state, "", "state", "an exact tuple")
            })?;
            if !matches!(state.len(), 5 | 6) {
                return Err(crate::error_context::value_error(
                    "Configs restore: unsupported state format",
                ));
            }
            let tag = state.get_item(0)?;
            let version = state.get_item(1)?;
            if !tag.is_exact_instance_of::<PyString>() {
                return Err(crate::error_context::expected_type(
                    &tag,
                    "",
                    "state.tag",
                    "an exact str",
                ));
            }
            if !version.is_exact_instance_of::<PyInt>() {
                return Err(crate::error_context::expected_type(
                    &version,
                    "",
                    "state.version",
                    "an exact int",
                ));
            }
            if tag.extract::<String>()? != STATE_TAG {
                return Err(crate::error_context::argument(
                    slf.py(),
                    crate::error_context::value_error("unsupported configuration state tag"),
                    "",
                    "state.tag",
                    &tag,
                ));
            }
            if !((state.len() == 5 && version.eq(1)?) || (state.len() == 6 && version.eq(2)?)) {
                return Err(crate::error_context::argument(slf.py(), crate::error_context::value_error(
                    "unsupported version for this state layout; use a snapshot produced by this package"), "", "state.version", &version));
            }
            let year = state.get_item(2)?;
            let year = year
                .cast_exact::<PyBool>()
                .map_err(|_| {
                    crate::error_context::expected_type(
                        &year,
                        "",
                        "state.yearfirst",
                        "an exact bool",
                    )
                })?
                .is_true();
            let day = state.get_item(3)?;
            let day = day
                .cast_exact::<PyBool>()
                .map_err(|_| {
                    crate::error_context::expected_type(&day, "", "state.dayfirst", "an exact bool")
                })?
                .is_true();
            let values = state.get_item(4)?;
            let values = values.cast_exact::<PyTuple>().map_err(|_| {
                crate::error_context::expected_type(
                    &values,
                    "",
                    "state.namespaces",
                    "an exact tuple",
                )
            })?;
            if values.len() != 8 {
                return Err(crate::error_context::value_error(
                    "Configs state requires eight namespaces",
                ));
            }
            let temporary = Py::new(slf.py(), Self::empty())?;
            let temporary = temporary.bind(slf.py());
            for (i, namespace) in NAMES.iter().enumerate() {
                let value = values.get_item(i)?;
                if i < 3 {
                    let tokens = value.cast_exact::<PySet>().map_err(|_| {
                        crate::error_context::expected_type(
                            &value,
                            "",
                            &format!("state.{namespace}"),
                            "an exact set",
                        )
                    })?;
                    for token in tokens.iter() {
                        if !token.is_exact_instance_of::<PyString>() {
                            return Err(crate::error_context::expected_type(
                                &token,
                                "",
                                &format!("state.{namespace} token"),
                                "an exact str",
                            ));
                        }
                    }
                } else {
                    let mapping = value.cast_exact::<PyDict>().map_err(|_| {
                        crate::error_context::expected_type(
                            &value,
                            "",
                            &format!("state.{namespace}"),
                            "an exact dict",
                        )
                    })?;
                    for (token, number) in mapping.iter() {
                        if !token.is_exact_instance_of::<PyString>() {
                            return Err(crate::error_context::expected_type(
                                &token,
                                "",
                                &format!("state.{namespace} key"),
                                "an exact str",
                            ));
                        }
                        if !number.is_exact_instance_of::<PyInt>() {
                            return Err(crate::error_context::expected_type(
                                &number,
                                "",
                                &format!("state.{namespace} value"),
                                "an exact int",
                            ));
                        }
                    }
                }
                replace(temporary, i, Some(&value))?;
            }
            let regions = if state.len() == 6 {
                let keys = state.get_item(5)?;
                // Snapshot containers must have the advertised shape even when
                // the local machine cannot load any named timezone.
                keys.cast_exact::<PySet>().map_err(|_| {
                    crate::error_context::expected_type(&keys, "", "state.tzone", "an exact set")
                })?;
                zones::from_set(Some(&keys), true)?
            } else {
                ZoneMap::new()
            };
            let mut unavailable: Vec<_> = regions
                .values()
                .filter(|zone| zone.object.is_none())
                .map(|zone| zone.key.as_str())
                .collect();
            if !unavailable.is_empty() {
                unavailable.sort_unstable();
                let shown = unavailable.iter().map(|key| {
                    crate::error_context::text_preview(slf.py(), key)
                }).collect::<PyResult<Vec<_>>>()?;
                let message = format!(
                    "Configs was restored, but these time zones are unavailable: {}. \
                     Parsing with these zones and ignoretz=False will fail. \
                     Restore the configuration again after making the time zone data available.",
                    shown.join(", ")
                );
                // Emit before committing: warnings configured as errors must not
                // leave an existing configuration partly restored.
                slf.py()
                    .import("warnings")?
                    .getattr("warn")
                    .map_err(crate::error_context::external)?
                    .call1((
                        message,
                        slf.py().get_type::<pyo3::exceptions::PyRuntimeWarning>(),
                    ))
                    .map_err(crate::error_context::external)?;
            }
            let incoming = temporary.borrow().owners.clone();
            let retired = {
                let mut cfg = slf.borrow_mut();
                cfg.yearfirst = year;
                cfg.dayfirst = day;
                (
                    std::mem::replace(&mut cfg.owners, incoming),
                    std::mem::replace(&mut cfg.cache, std::array::from_fn(|_| None)),
                    std::mem::replace(&mut cfg.zones, Arc::new(regions)),
                )
            };
            drop(retired);
            Ok(())
        })()
        .map_err(|error| {
            crate::error_context::argument(slf.py(), error, "Configs.__setstate__", "state", state)
        })
    }
    /// Clear all token namespaces and return True.
    ///
    /// The yearfirst and dayfirst flags are preserved. Each cleared namespace becomes
    /// independent of all existing copies.
    fn clear_settings(slf: &Bound<'_, Self>) -> PyResult<bool> {
        for i in 0..8 {
            detach_namespace(slf, i)?;
        }
        let retired = std::mem::replace(&mut slf.borrow_mut().zones, Arc::new(ZoneMap::new()));
        drop(retired);
        Ok(true)
    }
    /// Restore all default token rules and return True.
    ///
    /// The yearfirst and dayfirst flags are preserved. Resetting detaches the token
    /// namespaces from existing shallow copies.
    fn reset_settings(slf: &Bound<'_, Self>) -> PyResult<bool> {
        let incoming = std::array::from_fn(|i| defaults()[i].clone());
        let retired = {
            let mut cfg = slf.borrow_mut();
            (
                std::mem::replace(&mut cfg.owners, incoming),
                std::mem::replace(&mut cfg.cache, std::array::from_fn(|_| None)),
            )
        };
        drop(retired);
        let retired = std::mem::replace(&mut slf.borrow_mut().zones, Arc::new(ZoneMap::new()));
        drop(retired);
        Ok(true)
    }

    /// Return the registered time zone names as an independent set.
    ///
    /// Names use exact ZoneInfo keys, such as "Asia/Shanghai". Editing this
    /// returned set does not change the configuration. A restored name may be
    /// unavailable on this machine; restoring warns about those names.
    #[getter]
    fn tzone<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        zones::names(py, &self.zones)
    }

    /// Register a time zone and return True.
    ///
    /// The name is loaded with ZoneInfo now and reused by parse. Names are case
    /// sensitive. Missing time zone support or data raises an error and leaves
    /// the configuration unchanged.
    fn add_tzone(slf: &Bound<'_, Self>, key: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            let zone = zones::load(key, false)?;
            let token = zone.key.chars().map(u32::from).collect();
            let retired = {
                let mut cfg = slf.borrow_mut();
                Arc::make_mut(&mut cfg.zones).insert(token, zone)
            };
            drop(retired);
            Ok(true)
        })();
        result.map_err(|error| edit_error(slf, "Configs.add_tzone", error))
    }

    /// Delete one registered time zone and return whether it existed.
    fn del_tzone(slf: &Bound<'_, Self>, key: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            let token = zones::token(key)?;
            let retired = Arc::make_mut(&mut slf.borrow_mut().zones).remove(&token);
            let existed = retired.is_some();
            drop(retired);
            Ok(existed)
        })();
        result.map_err(|error| edit_error(slf, "Configs.del_tzone", error))
    }

    /// Replace all registered time zones and return True.
    ///
    /// Pass a set of exact ZoneInfo names. None or an empty set removes all
    /// registrations. Names are fixed and validated before loading begins.
    /// The complete replacement is committed only after every load succeeds;
    /// an invalid or unavailable name leaves the old configuration unchanged.
    #[pyo3(signature=(keys=None))]
    fn set_tzone(slf: &Bound<'_, Self>, keys: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            let incoming = Arc::new(zones::from_set(keys, false)?);
            let retired = std::mem::replace(&mut slf.borrow_mut().zones, incoming);
            drop(retired);
            Ok(true)
        })();
        result.map_err(|error| edit_error(slf, "Configs.set_tzone", error))
    }

    /// Replace the jump namespace and return True on success.
    ///
    /// :param tokens: A set[str], or None to restore its default rules.
    ///     An empty set removes all rules in this namespace.
    /// Tokens must be strings.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(tokens=None))]
    fn set_jump(slf: &Bound<'_, Self>, tokens: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 0, tokens);
        result.map_err(|error| edit_error(slf, "Configs.set_jump", error))
    }
    /// Replace the pertain namespace and return True on success.
    ///
    /// :param tokens: A set[str], or None to restore its default rules.
    ///     An empty set removes all rules in this namespace.
    /// Tokens must be strings.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(tokens=None))]
    fn set_pertain(slf: &Bound<'_, Self>, tokens: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 1, tokens);
        result.map_err(|error| edit_error(slf, "Configs.set_pertain", error))
    }
    /// Replace the utc namespace and return True on success.
    ///
    /// :param tokens: A set[str], or None to restore its default rules.
    ///     An empty set removes all rules in this namespace.
    /// Tokens must be strings.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(tokens=None))]
    fn set_utc(slf: &Bound<'_, Self>, tokens: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 2, tokens);
        result.map_err(|error| edit_error(slf, "Configs.set_utc", error))
    }
    /// Replace the tzoffset namespace and return True on success.
    ///
    /// :param mapping: A dict with string keys and integer-index values, or None to restore defaults.
    ///     An empty dict removes all rules in this namespace.
    /// Values may be Python/NumPy integers or valid __index__ objects within the namespace range.
    /// Python and NumPy booleans, floats, numeric text and __int__-only objects are rejected.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(mapping=None))]
    fn set_tzoffset(slf: &Bound<'_, Self>, mapping: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 3, mapping);
        result.map_err(|error| edit_error(slf, "Configs.set_tzoffset", error))
    }
    /// Replace the month namespace and return True on success.
    ///
    /// :param mapping: A dict with string keys and integer-index values, or None to restore defaults.
    ///     An empty dict removes all rules in this namespace.
    /// Values may be Python/NumPy integers or valid __index__ objects within the namespace range.
    /// Python and NumPy booleans, floats, numeric text and __int__-only objects are rejected.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(mapping=None))]
    fn set_month(slf: &Bound<'_, Self>, mapping: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 4, mapping);
        result.map_err(|error| edit_error(slf, "Configs.set_month", error))
    }
    /// Replace the weekday namespace and return True on success.
    ///
    /// :param mapping: A dict with string keys and integer-index values, or None to restore defaults.
    ///     An empty dict removes all rules in this namespace.
    /// Values may be Python/NumPy integers or valid __index__ objects within the namespace range.
    /// Python and NumPy booleans, floats, numeric text and __int__-only objects are rejected.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(mapping=None))]
    fn set_weekday(slf: &Bound<'_, Self>, mapping: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 5, mapping);
        result.map_err(|error| edit_error(slf, "Configs.set_weekday", error))
    }
    /// Replace the hms namespace and return True on success.
    ///
    /// :param mapping: A dict with string keys and integer-index values, or None to restore defaults.
    ///     An empty dict removes all rules in this namespace.
    /// Values may be Python/NumPy integers or valid __index__ objects within the namespace range.
    /// Python and NumPy booleans, floats, numeric text and __int__-only objects are rejected.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(mapping=None))]
    fn set_hms(slf: &Bound<'_, Self>, mapping: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 6, mapping);
        result.map_err(|error| edit_error(slf, "Configs.set_hms", error))
    }
    /// Replace the ampm namespace and return True on success.
    ///
    /// :param mapping: A dict with string keys and integer-index values, or None to restore defaults.
    ///     An empty dict removes all rules in this namespace.
    /// Values may be Python/NumPy integers or valid __index__ objects within the namespace range.
    /// Python and NumPy booleans, floats, numeric text and __int__-only objects are rejected.
    /// Tokens are normalized to lowercase and recognized in lowercase, uppercase, and titlecase.
    /// Cross-namespace conflicts are rejected, except that jump tokens may overlap any namespace.
    /// If validation fails, this namespace retains its previous rules.
    /// Copied configurations remain unchanged by a successful replacement.
    #[pyo3(signature=(mapping=None))]
    fn set_ampm(slf: &Bound<'_, Self>, mapping: Option<&Bound<'_, PyAny>>) -> PyResult<bool> {
        let result: PyResult<bool> = replace(slf, 7, mapping);
        result.map_err(|error| edit_error(slf, "Configs.set_ampm", error))
    }
    /// Whether the first value of an ambiguous calendar triple is interpreted as year.
    ///
    /// This read-only flag defaults to True and takes precedence over dayfirst.
    #[getter]
    fn yearfirst(&self) -> bool {
        self.yearfirst
    }
    /// Whether the first non-year value of an ambiguous calendar triple is interpreted as day.
    ///
    /// This read-only flag defaults to False. When yearfirst is True, it selects Y/D/M.
    #[getter]
    fn dayfirst(&self) -> bool {
        self.dayfirst
    }

    // Both truth conversions may reenter Configs; acquire the mutable borrow only afterward.
    fn _flags(
        slf: &Bound<'_, Self>,
        yearfirst: &Bound<'_, PyAny>,
        dayfirst: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let y = crate::numeric::boolean(yearfirst).map_err(|error| {
            crate::error_context::argument(slf.py(), error, "", "yearfirst", yearfirst)
        })?;
        let d = crate::numeric::boolean(dayfirst).map_err(|error| {
            crate::error_context::argument(slf.py(), error, "", "dayfirst", dayfirst)
        })?;
        let mut cfg = slf.borrow_mut();
        cfg.yearfirst = y;
        cfg.dayfirst = d;
        Ok(())
    }
    /// Return the configuration class, calendar-order flags, and namespace sizes.
    fn __repr__(&self) -> String {
        let [jump, pertain, utc, tzoffset, month, weekday, hms, ampm] =
            self.owners.each_ref().map(|owner| owner.base.len());
        format!(
            "<'Configs' ({}: yearfirst={} dayfirst={} | sizes: jump={} pertain={} utc={} tzoffset={} month={} weekday={} hms={} ampm={})>",
            self.order_hint(),
            if self.yearfirst { "True" } else { "False" },
            if self.dayfirst { "True" } else { "False" },
            jump,
            pertain,
            utc,
            tzoffset,
            month,
            weekday,
            hms,
            ampm,
        )
    }

    /// Return the order used to interpret an ambiguous calendar triple.
    ///
    /// The result is "Y/D/M", "Y/M/D", "D/M/Y", or "M/D/Y", according to the
    /// current yearfirst and dayfirst flags.
    fn order_hint(&self) -> &'static str {
        match (self.yearfirst, self.dayfirst) {
            (true, true) => "Y/D/M",
            (true, false) => "Y/M/D",
            (false, true) => "D/M/Y",
            _ => "M/D/Y",
        }
    }

    /// Return an independent set of tokens the parser may skip.
    ///
    /// Keys are stored in lowercase. Mutating the returned container does not change this Configs.
    /// Use add_jump, del_jump, or set_jump to edit its rules.
    #[getter]
    fn jump<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 0)
    }
    /// Add or update a jump token and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    ///
    /// The token is recognized in lowercase, uppercase, and titlecase.
    /// Jump tokens may overlap any other namespace.
    ///
    /// Changes affect this configuration only; copied configurations remain independent.
    fn add_jump(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = add(slf, 0, token, 1);
        result.map_err(|error| edit_error(slf, "Configs.add_jump", error))
    }
    /// Remove a jump token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_jump(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 0, token);
        result.map_err(|error| edit_error(slf, "Configs.del_jump", error))
    }

    /// Return an independent set of relationship tokens such as "of".
    ///
    /// Keys are stored in lowercase. Mutating the returned container does not change this Configs.
    /// Use add_pertain, del_pertain, or set_pertain to edit its rules.
    #[getter]
    fn pertain<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 1)
    }
    /// Add or update a pertain token and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    ///
    /// The token is recognized in lowercase, uppercase, and titlecase.
    /// Conflicts between recognized case forms are rejected; overlap with jump is allowed.
    ///
    /// Changes affect this configuration only; copied configurations remain independent.
    fn add_pertain(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = add(slf, 1, token, 1);
        result.map_err(|error| edit_error(slf, "Configs.add_pertain", error))
    }
    /// Remove a pertain token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_pertain(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 1, token);
        result.map_err(|error| edit_error(slf, "Configs.del_pertain", error))
    }

    /// Return an independent set of tokens denoting UTC.
    ///
    /// Keys are stored in lowercase. Mutating the returned container does not change this Configs.
    /// Use add_utc, del_utc, or set_utc to edit its rules.
    #[getter]
    fn utc<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 2)
    }
    /// Add or update a utc token and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    ///
    /// The token is recognized in lowercase, uppercase, and titlecase.
    /// Conflicts between recognized case forms are rejected; overlap with jump is allowed.
    ///
    /// Changes affect this configuration only; copied configurations remain independent.
    fn add_utc(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = add(slf, 2, token, 1);
        result.map_err(|error| edit_error(slf, "Configs.add_utc", error))
    }
    /// Remove a utc token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_utc(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 2, token);
        result.map_err(|error| edit_error(slf, "Configs.del_utc", error))
    }

    /// Return an independent map from lowercase timezone aliases to seconds.
    /// Changes to this copy do not alter the configuration.
    #[getter]
    fn tzoffset<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 3)
    }
    /// Add or update a timezone alias and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    /// :param hours: Signed hour component of the UTC offset; defaults to 0.
    /// :param minutes: Signed minute component; defaults to 0.
    /// :param seconds: Signed second component; defaults to 0.
    /// Numeric components must be integers; floats and explicit None are not accepted. Use minutes=30 for a half hour.
    /// The total offset is hours * 3600 + minutes * 60 + seconds and must be within
    /// -86399 through 86399 seconds. Offsets outside this range raise
    /// ConfigError. Integers too large to convert raise OverflowError.
    /// The alias is recognized in lowercase, uppercase, and titlecase.
    /// Conflicts between recognized case forms are rejected; overlap with jump is allowed.
    /// Changes affect this configuration only; copied configurations remain independent.
    #[pyo3(signature=(token,*args,**kwargs),text_signature="(self, token, hours=0, minutes=0, seconds=0)")]
    fn add_tzoffset(
        slf: &Bound<'_, Self>,
        token: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            validate_token_type(token)?;
            if args.len() > 3 {
                return Err(crate::error_context::type_error(format!(
                    "add_tzoffset() takes at most 4 positional arguments ({} given)",
                    args.len() + 1
                )));
            }
            let mut values = [0_i32; 3];
            let names = ["hours", "minutes", "seconds"];
            // Retain every keyword reference before any numeric callback,
            // including callbacks in earlier positional arguments.
            let keywords: Vec<_> = kwargs.map(|kw| kw.iter().collect()).unwrap_or_default();
            for (i, value) in args.iter().enumerate() {
                values[i] = c_int(&value).map_err(|error| {
                    crate::error_context::argument(
                        slf.py(),
                        error,
                        "Configs.add_tzoffset",
                        names[i],
                        &value,
                    )
                })?;
            }
            {
                for (key, value) in keywords {
                    let name = key.extract::<String>()?;
                    let Some(i) = names.iter().position(|n| *n == name) else {
                        return Err(crate::error_context::type_error(format!(
                            "add_tzoffset() got an unexpected keyword argument '{name}'"
                        )));
                    };
                    if i < args.len() {
                        return Err(crate::error_context::type_error(format!(
                            "add_tzoffset() got multiple values for argument '{name}'"
                        )));
                    }
                    values[i] = c_int(&value).map_err(|error| {
                        crate::error_context::argument(
                            slf.py(),
                            error,
                            "Configs.add_tzoffset",
                            names[i],
                            &value,
                        )
                    })?;
                }
            }
            add(slf, 3, token, tz_seconds(values[0], values[1], values[2]))
        })();
        result.map_err(|error| edit_error(slf, "Configs.add_tzoffset", error))
    }

    /// Remove a tzoffset token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_tzoffset(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 3, token);
        result.map_err(|error| edit_error(slf, "Configs.del_tzoffset", error))
    }

    /// Return an independent dict of month aliases and numbers from 1 through 12.
    ///
    /// Keys are stored in lowercase. Mutating the returned container does not change this Configs.
    /// Use add_month, del_month, or set_month to edit its rules.
    #[getter(month)]
    fn month_property<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 4)
    }
    /// Add or update a month token and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    /// :param month: Month number from 1 (January) through 12 (December).
    /// The token is recognized in lowercase, uppercase, and titlecase.
    /// Conflicts between recognized case forms are rejected; overlap with jump is allowed.
    /// Numeric arguments must be integers; floats and out-of-range values are rejected.
    /// Changes affect this configuration only; copied configurations remain independent.
    fn add_month(
        slf: &Bound<'_, Self>,
        token: &Bound<'_, PyAny>,
        month: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            validate_token_type(token)?;
            let month = c_int(month).map_err(|error| {
                crate::error_context::argument(slf.py(), error, "Configs.add_month", "month", month)
            })?;
            add(slf, 4, token, i64::from(month))
        })();
        result.map_err(|error| edit_error(slf, "Configs.add_month", error))
    }
    /// Remove a month token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_month(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 4, token);
        result.map_err(|error| edit_error(slf, "Configs.del_month", error))
    }

    /// Return an independent dict of weekday aliases and numbers from 0 (Monday) through 6 (Sunday).
    ///
    /// Keys are stored in lowercase. Mutating the returned container does not change this Configs.
    /// Use add_weekday, del_weekday, or set_weekday to edit its rules.
    #[getter(weekday)]
    fn weekday_property<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 5)
    }
    /// Add or update a weekday token and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    /// :param weekday: Weekday number from 0 (Monday) through 6 (Sunday).
    /// The token is recognized in lowercase, uppercase, and titlecase.
    /// Conflicts between recognized case forms are rejected; overlap with jump is allowed.
    /// Numeric arguments must be integers; floats and out-of-range values are rejected.
    /// Changes affect this configuration only; copied configurations remain independent.
    fn add_weekday(
        slf: &Bound<'_, Self>,
        token: &Bound<'_, PyAny>,
        weekday: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            validate_token_type(token)?;
            let weekday = c_int(weekday).map_err(|error| {
                crate::error_context::argument(
                    slf.py(),
                    error,
                    "Configs.add_weekday",
                    "weekday",
                    weekday,
                )
            })?;
            add(slf, 5, token, i64::from(weekday))
        })();
        result.map_err(|error| edit_error(slf, "Configs.add_weekday", error))
    }
    /// Remove a weekday token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_weekday(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 5, token);
        result.map_err(|error| edit_error(slf, "Configs.del_weekday", error))
    }

    /// Return an independent dict of time-unit aliases and flags: 0 for hours, 1 for minutes, 2 for seconds.
    ///
    /// Keys are stored in lowercase. Mutating the returned container does not change this Configs.
    /// Use add_hms, del_hms, or set_hms to edit its rules.
    #[getter(hms)]
    fn hms_property<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 6)
    }
    /// Add or update a hms token and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    /// :param flag: 0 for hours, 1 for minutes, or 2 for seconds.
    /// The token is recognized in lowercase, uppercase, and titlecase.
    /// Conflicts between recognized case forms are rejected; overlap with jump is allowed.
    /// Numeric arguments must be integers; floats and out-of-range values are rejected.
    /// Changes affect this configuration only; copied configurations remain independent.
    fn add_hms(
        slf: &Bound<'_, Self>,
        token: &Bound<'_, PyAny>,
        flag: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            validate_token_type(token)?;
            let flag = c_int(flag)?;
            add(slf, 6, token, i64::from(flag))
        })();
        result.map_err(|error| edit_error(slf, "Configs.add_hms", error))
    }
    /// Remove a hms token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_hms(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 6, token);
        result.map_err(|error| edit_error(slf, "Configs.del_hms", error))
    }

    /// Return an independent dict of AM/PM aliases and flags: 0 for AM, 1 for PM.
    ///
    /// Keys are stored in lowercase. Mutating the returned container does not change this Configs.
    /// Use add_ampm, del_ampm, or set_ampm to edit its rules.
    #[getter(ampm)]
    fn ampm_property<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyAny>> {
        display(slf, 7)
    }
    /// Add or update a ampm token and return True.
    ///
    /// :param token: A nonempty str, normalized to lowercase; str subclasses are not accepted.
    /// :param flag: 0 for AM or 1 for PM.
    /// The token is recognized in lowercase, uppercase, and titlecase.
    /// Conflicts between recognized case forms are rejected; overlap with jump is allowed.
    /// Numeric arguments must be integers; floats and out-of-range values are rejected.
    /// Changes affect this configuration only; copied configurations remain independent.
    fn add_ampm(
        slf: &Bound<'_, Self>,
        token: &Bound<'_, PyAny>,
        flag: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let result: PyResult<bool> = (|| {
            validate_token_type(token)?;
            let flag = c_int(flag)?;
            add(slf, 7, token, i64::from(flag))
        })();
        result.map_err(|error| edit_error(slf, "Configs.add_ampm", error))
    }
    /// Remove a ampm token and return whether it existed.
    ///
    /// :param token: A nonempty str; removal is case-insensitive. Str subclasses are not accepted.
    /// :returns: True if the token was removed, or False if it was absent.
    /// The removal affects this configuration only.
    fn del_ampm(slf: &Bound<'_, Self>, token: &Bound<'_, PyAny>) -> PyResult<bool> {
        let result: PyResult<bool> = remove(slf, 7, token);
        result.map_err(|error| edit_error(slf, "Configs.del_ampm", error))
    }
}
/// Register Configs and the lifecycle boundary methods.
pub(crate) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<Configs>()?;
    let globals = PyDict::new(module.py());
    globals.set_item("Configs", module.py().get_type::<Configs>())?;
    globals.set_item("_bool_option", module.getattr("_bool_option")?)?;
    globals.set_item("parserinfo", crate::interop::parserinfo_type(module.py())?)?;
    globals.set_item("__name__", "rstimes.parser")?;
    let code = std::ffi::CString::new(BOUNDARY)
        .map_err(|e| crate::error_context::runtime(e.to_string()))?;
    module.py().run(&code, Some(&globals), None)?;
    module.add_function(wrap_pyfunction!(_restore_configs, module)?)?;
    Ok(())
}
const BOUNDARY: &str = r####"from rstimes import errors
class _Boundary:
    def __init__(self, yearfirst=True, dayfirst=False):
        'Create configuration with default token rules.\n\nParameters\n----------\nyearfirst : bool, default True\n    Interpret the first value of an ambiguous calendar triple as year.\ndayfirst : bool, default False\n    Interpret the first non-year value as day. Together with yearfirst,\n    this selects Y/D/M; otherwise it selects D/M/Y.\n\nFlags accept only Python bool or NumPy boolean scalars. Calling __init__ again replaces the flags\nand resets all token rules. Word tokens are normalized to lowercase\nand recognized in lowercase, uppercase, and titlecase. Jump words may overlap\nany word table; other word-table conflicts are rejected. Register regional\nZoneInfo names with add_tzone; these use exact matching and are loaded once.\nFixed-offset aliases use tzoffset.\n\nToken properties return independent containers. copy.copy, copy.deepcopy and\npickle round trips create independent configurations. Editing rules or flags\nin either configuration does not change the other. Configs cannot be subclassed; use\nits add/del/set methods to customize rules. Saved state is independent. Replacements use an entry snapshot before numeric callbacks and commit only after validation; case-expanded conflicts are rejected.'
        try:
            self._flags(yearfirst, dayfirst)
            self.reset_settings()
        except Exception as error:
            errors._raise_argument_context(error, "Configs", "arguments", None)
    @classmethod
    def from_parserinfo(cls, info):
        'Copy vocabulary and calendar-order flags from dateutil parserinfo.\n\nRequires optional python-dateutil; install rsTimes[dateutil] and restart Python.\n\nParameters\n----------\ninfo : dateutil.parser.parserinfo\n    An instance or real subclass supplying the vocabulary and ordering flags.\n    Custom parsing methods and internal parserinfo caches are not copied.\n\nReturns\n-------\nConfigs\n    An independent configuration using the imported rules.\n\nRaises\n------\nTypeError\n    The source is not a parserinfo instance or a non-None vocabulary table\n    has an unsupported outer container, or an ordering flag is not a Python\n    bool or NumPy boolean scalar. Integers such as 0 and 1, text and other\n    truth-value objects are not accepted. The message identifies the field.\nConfigError\n    A token, mapped value or cross-table combination is invalid.\nOverflowError\n    A numeric configuration value exceeds the supported integer range.\n\nNotes\n-----\nJUMP, PERTAIN and UTCZONE accept list, tuple or set; TZOFFSET accepts dict.\nMONTHS, WEEKDAYS, HMS and AMPM accept list or tuple. Real subclasses of these\ncontainers are accepted. None leaves that table empty; it does not restore\nits default vocabulary. Other outer types, including generators and empty\ncontainers of the wrong type, raise TypeError before iteration.\n\nEach source table is read once in its established order. A string row is one\ncomplete alias. Existing alias collections, value ranges, case variants and\nconflict checks apply. The imported configuration does not depend on later\nchanges to the source. TZOFFSET values are UTC offsets in seconds.\n\nExamples\n--------\n>>> from dateutil.parser import parserinfo\n>>> from rstimes import Configs\n>>> cfg = Configs.from_parserinfo(parserinfo(dayfirst=True))\n>>> cfg.dayfirst\nTrue\n'
        try:
            if parserinfo is None:
                error = ImportError(
                    "dateutil integration requires python-dateutil; install rstimes[dateutil]"
                )
                # The normal failure boundary completes args with public context.
                error.msg = None
                raise errors._own_error(error, "info", info)
            if not issubclass(type(info), parserinfo):
                raise errors._own_error(TypeError("must be a dateutil.parser.parserinfo instance"), "info", info)
            def source(name, flag=False):
                try:
                    value = getattr(info, name)
                except Exception as error:
                    raise errors._location_error(errors._external_error(error), "", "reading info." + name)
                if not flag:
                    return value
                return _bool_option(value, "Configs.from_parserinfo", "info." + name)
            cfg = cls(yearfirst=source('yearfirst', True), dayfirst=source('dayfirst', True))
            cfg.clear_settings()
            def table(name, accepted, description, destination, conversion):
                value = source(name)
                if value is None:
                    return
                if not issubclass(type(value), accepted):
                    raise errors._own_error(TypeError("must be " + description + "; got " + errors._preview(value)), "info." + name, value)
                try:
                    incoming = conversion(value)
                except Exception as error:
                    raise errors._location_error(errors._external_error(error), "", "reading info." + name)
                try:
                    getattr(cfg, destination)(incoming)
                except Exception as error:
                    errors._raise_argument_context(error, "", "info." + name, value)
            def rows(value, offset):
                return {token: i + offset for i, row in enumerate(value)
                        for token in ((row,) if issubclass(type(row), str) else row)}
            table('JUMP', (list, tuple, set), 'a list, tuple, set or None', 'set_jump', set)
            table('PERTAIN', (list, tuple, set), 'a list, tuple, set or None', 'set_pertain', set)
            table('UTCZONE', (list, tuple, set), 'a list, tuple, set or None', 'set_utc', set)
            table('TZOFFSET', (dict,), 'a dict or None', 'set_tzoffset', dict)
            table('MONTHS', (list, tuple), 'a list, tuple or None', 'set_month', lambda v: rows(v, 1))
            table('WEEKDAYS', (list, tuple), 'a list, tuple or None', 'set_weekday', lambda v: rows(v, 0))
            table('HMS', (list, tuple), 'a list, tuple or None', 'set_hms', lambda v: rows(v, 0))
            table('AMPM', (list, tuple), 'a list, tuple or None', 'set_ampm', lambda v: rows(v, 0))
            return cfg
        except Exception as error:
            errors._raise_argument_context(error, "Configs.from_parserinfo", "arguments", None)
for _name in ("__init__", "from_parserinfo"):
    setattr(Configs, _name, vars(_Boundary)[_name])
"####;

fn defaults() -> &'static [Namespace; 8] {
    static DEFAULTS: std::sync::OnceLock<[Namespace; 8]> = std::sync::OnceLock::new();
    DEFAULTS.get_or_init(|| {
        let mut all: [Namespace; 8] = std::array::from_fn(|_| Namespace::default());
        all[0].put_base("t".chars().map(u32::from).collect(), 1);
        all[0].put_ext("t".chars().map(u32::from).collect(), 1);
        all[0].put_ext("T".chars().map(u32::from).collect(), 1);
        all[0].put_base("rd".chars().map(u32::from).collect(), 1);
        all[0].put_ext("rd".chars().map(u32::from).collect(), 1);
        all[0].put_ext("RD".chars().map(u32::from).collect(), 1);
        all[0].put_ext("Rd".chars().map(u32::from).collect(), 1);
        all[0].put_base("of".chars().map(u32::from).collect(), 1);
        all[0].put_ext("of".chars().map(u32::from).collect(), 1);
        all[0].put_ext("OF".chars().map(u32::from).collect(), 1);
        all[0].put_ext("Of".chars().map(u32::from).collect(), 1);
        all[0].put_base("on".chars().map(u32::from).collect(), 1);
        all[0].put_ext("on".chars().map(u32::from).collect(), 1);
        all[0].put_ext("ON".chars().map(u32::from).collect(), 1);
        all[0].put_ext("On".chars().map(u32::from).collect(), 1);
        all[0].put_base(";".chars().map(u32::from).collect(), 1);
        all[0].put_ext(";".chars().map(u32::from).collect(), 1);
        all[0].put_base("ad".chars().map(u32::from).collect(), 1);
        all[0].put_ext("ad".chars().map(u32::from).collect(), 1);
        all[0].put_ext("AD".chars().map(u32::from).collect(), 1);
        all[0].put_ext("Ad".chars().map(u32::from).collect(), 1);
        all[0].put_base(",".chars().map(u32::from).collect(), 1);
        all[0].put_ext(",".chars().map(u32::from).collect(), 1);
        all[0].put_base("m".chars().map(u32::from).collect(), 1);
        all[0].put_ext("m".chars().map(u32::from).collect(), 1);
        all[0].put_ext("M".chars().map(u32::from).collect(), 1);
        all[0].put_base("日".chars().map(u32::from).collect(), 1);
        all[0].put_ext("日".chars().map(u32::from).collect(), 1);
        all[0].put_base("/".chars().map(u32::from).collect(), 1);
        all[0].put_ext("/".chars().map(u32::from).collect(), 1);
        all[0].put_base("nd".chars().map(u32::from).collect(), 1);
        all[0].put_ext("nd".chars().map(u32::from).collect(), 1);
        all[0].put_ext("ND".chars().map(u32::from).collect(), 1);
        all[0].put_ext("Nd".chars().map(u32::from).collect(), 1);
        all[0].put_base("月".chars().map(u32::from).collect(), 1);
        all[0].put_ext("月".chars().map(u32::from).collect(), 1);
        all[0].put_base("at".chars().map(u32::from).collect(), 1);
        all[0].put_ext("at".chars().map(u32::from).collect(), 1);
        all[0].put_ext("AT".chars().map(u32::from).collect(), 1);
        all[0].put_ext("At".chars().map(u32::from).collect(), 1);
        all[0].put_base("年".chars().map(u32::from).collect(), 1);
        all[0].put_ext("年".chars().map(u32::from).collect(), 1);
        all[0].put_base("-".chars().map(u32::from).collect(), 1);
        all[0].put_ext("-".chars().map(u32::from).collect(), 1);
        all[0].put_base("'".chars().map(u32::from).collect(), 1);
        all[0].put_ext("'".chars().map(u32::from).collect(), 1);
        all[0].put_base("and".chars().map(u32::from).collect(), 1);
        all[0].put_ext("and".chars().map(u32::from).collect(), 1);
        all[0].put_ext("AND".chars().map(u32::from).collect(), 1);
        all[0].put_ext("And".chars().map(u32::from).collect(), 1);
        all[0].put_base(" ".chars().map(u32::from).collect(), 1);
        all[0].put_ext(" ".chars().map(u32::from).collect(), 1);
        all[0].put_base("th".chars().map(u32::from).collect(), 1);
        all[0].put_ext("th".chars().map(u32::from).collect(), 1);
        all[0].put_ext("TH".chars().map(u32::from).collect(), 1);
        all[0].put_ext("Th".chars().map(u32::from).collect(), 1);
        all[0].put_base(".".chars().map(u32::from).collect(), 1);
        all[0].put_ext(".".chars().map(u32::from).collect(), 1);
        all[0].put_base("st".chars().map(u32::from).collect(), 1);
        all[0].put_ext("st".chars().map(u32::from).collect(), 1);
        all[0].put_ext("ST".chars().map(u32::from).collect(), 1);
        all[0].put_ext("St".chars().map(u32::from).collect(), 1);
        all[1].put_base("of".chars().map(u32::from).collect(), 1);
        all[1].put_ext("of".chars().map(u32::from).collect(), 1);
        all[1].put_ext("OF".chars().map(u32::from).collect(), 1);
        all[1].put_ext("Of".chars().map(u32::from).collect(), 1);
        all[2].put_base("gmt".chars().map(u32::from).collect(), 1);
        all[2].put_ext("gmt".chars().map(u32::from).collect(), 1);
        all[2].put_ext("GMT".chars().map(u32::from).collect(), 1);
        all[2].put_ext("Gmt".chars().map(u32::from).collect(), 1);
        all[2].put_base("z".chars().map(u32::from).collect(), 1);
        all[2].put_ext("z".chars().map(u32::from).collect(), 1);
        all[2].put_ext("Z".chars().map(u32::from).collect(), 1);
        all[2].put_base("utc".chars().map(u32::from).collect(), 1);
        all[2].put_ext("utc".chars().map(u32::from).collect(), 1);
        all[2].put_ext("UTC".chars().map(u32::from).collect(), 1);
        all[2].put_ext("Utc".chars().map(u32::from).collect(), 1);
        all[4].put_base("jan".chars().map(u32::from).collect(), 1);
        all[4].put_ext("jan".chars().map(u32::from).collect(), 1);
        all[4].put_ext("JAN".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Jan".chars().map(u32::from).collect(), 1);
        all[4].put_base("january".chars().map(u32::from).collect(), 1);
        all[4].put_ext("january".chars().map(u32::from).collect(), 1);
        all[4].put_ext("JANUARY".chars().map(u32::from).collect(), 1);
        all[4].put_ext("January".chars().map(u32::from).collect(), 1);
        all[4].put_base("januar".chars().map(u32::from).collect(), 1);
        all[4].put_ext("januar".chars().map(u32::from).collect(), 1);
        all[4].put_ext("JANUAR".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Januar".chars().map(u32::from).collect(), 1);
        all[4].put_base("janvier".chars().map(u32::from).collect(), 1);
        all[4].put_ext("janvier".chars().map(u32::from).collect(), 1);
        all[4].put_ext("JANVIER".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Janvier".chars().map(u32::from).collect(), 1);
        all[4].put_base("gennaio".chars().map(u32::from).collect(), 1);
        all[4].put_ext("gennaio".chars().map(u32::from).collect(), 1);
        all[4].put_ext("GENNAIO".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Gennaio".chars().map(u32::from).collect(), 1);
        all[4].put_base("enero".chars().map(u32::from).collect(), 1);
        all[4].put_ext("enero".chars().map(u32::from).collect(), 1);
        all[4].put_ext("ENERO".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Enero".chars().map(u32::from).collect(), 1);
        all[4].put_base("janeiro".chars().map(u32::from).collect(), 1);
        all[4].put_ext("janeiro".chars().map(u32::from).collect(), 1);
        all[4].put_ext("JANEIRO".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Janeiro".chars().map(u32::from).collect(), 1);
        all[4].put_base("januari".chars().map(u32::from).collect(), 1);
        all[4].put_ext("januari".chars().map(u32::from).collect(), 1);
        all[4].put_ext("JANUARI".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Januari".chars().map(u32::from).collect(), 1);
        all[4].put_base("stycznia".chars().map(u32::from).collect(), 1);
        all[4].put_ext("stycznia".chars().map(u32::from).collect(), 1);
        all[4].put_ext("STYCZNIA".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Stycznia".chars().map(u32::from).collect(), 1);
        all[4].put_base("ocak".chars().map(u32::from).collect(), 1);
        all[4].put_ext("ocak".chars().map(u32::from).collect(), 1);
        all[4].put_ext("OCAK".chars().map(u32::from).collect(), 1);
        all[4].put_ext("Ocak".chars().map(u32::from).collect(), 1);
        all[4].put_base("一月".chars().map(u32::from).collect(), 1);
        all[4].put_ext("一月".chars().map(u32::from).collect(), 1);
        all[4].put_base("feb".chars().map(u32::from).collect(), 2);
        all[4].put_ext("feb".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEB".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Feb".chars().map(u32::from).collect(), 2);
        all[4].put_base("february".chars().map(u32::from).collect(), 2);
        all[4].put_ext("february".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEBRUARY".chars().map(u32::from).collect(), 2);
        all[4].put_ext("February".chars().map(u32::from).collect(), 2);
        all[4].put_base("februar".chars().map(u32::from).collect(), 2);
        all[4].put_ext("februar".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEBRUAR".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Februar".chars().map(u32::from).collect(), 2);
        all[4].put_base("février".chars().map(u32::from).collect(), 2);
        all[4].put_ext("février".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FÉVRIER".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Février".chars().map(u32::from).collect(), 2);
        all[4].put_base("febbraio".chars().map(u32::from).collect(), 2);
        all[4].put_ext("febbraio".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEBBRAIO".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Febbraio".chars().map(u32::from).collect(), 2);
        all[4].put_base("febrero".chars().map(u32::from).collect(), 2);
        all[4].put_ext("febrero".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEBRERO".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Febrero".chars().map(u32::from).collect(), 2);
        all[4].put_base("fevereiro".chars().map(u32::from).collect(), 2);
        all[4].put_ext("fevereiro".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEVEREIRO".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Fevereiro".chars().map(u32::from).collect(), 2);
        all[4].put_base("februari".chars().map(u32::from).collect(), 2);
        all[4].put_ext("februari".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEBRUARI".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Februari".chars().map(u32::from).collect(), 2);
        all[4].put_base("lutego".chars().map(u32::from).collect(), 2);
        all[4].put_ext("lutego".chars().map(u32::from).collect(), 2);
        all[4].put_ext("LUTEGO".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Lutego".chars().map(u32::from).collect(), 2);
        all[4].put_base("şubat".chars().map(u32::from).collect(), 2);
        all[4].put_ext("şubat".chars().map(u32::from).collect(), 2);
        all[4].put_ext("ŞUBAT".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Şubat".chars().map(u32::from).collect(), 2);
        all[4].put_base("二月".chars().map(u32::from).collect(), 2);
        all[4].put_ext("二月".chars().map(u32::from).collect(), 2);
        all[4].put_base("febr".chars().map(u32::from).collect(), 2);
        all[4].put_ext("febr".chars().map(u32::from).collect(), 2);
        all[4].put_ext("FEBR".chars().map(u32::from).collect(), 2);
        all[4].put_ext("Febr".chars().map(u32::from).collect(), 2);
        all[4].put_base("mar".chars().map(u32::from).collect(), 3);
        all[4].put_ext("mar".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MAR".chars().map(u32::from).collect(), 3);
        all[4].put_ext("Mar".chars().map(u32::from).collect(), 3);
        all[4].put_base("march".chars().map(u32::from).collect(), 3);
        all[4].put_ext("march".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MARCH".chars().map(u32::from).collect(), 3);
        all[4].put_ext("March".chars().map(u32::from).collect(), 3);
        all[4].put_base("märz".chars().map(u32::from).collect(), 3);
        all[4].put_ext("märz".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MÄRZ".chars().map(u32::from).collect(), 3);
        all[4].put_ext("März".chars().map(u32::from).collect(), 3);
        all[4].put_base("mars".chars().map(u32::from).collect(), 3);
        all[4].put_ext("mars".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MARS".chars().map(u32::from).collect(), 3);
        all[4].put_ext("Mars".chars().map(u32::from).collect(), 3);
        all[4].put_base("marzo".chars().map(u32::from).collect(), 3);
        all[4].put_ext("marzo".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MARZO".chars().map(u32::from).collect(), 3);
        all[4].put_ext("Marzo".chars().map(u32::from).collect(), 3);
        all[4].put_base("março".chars().map(u32::from).collect(), 3);
        all[4].put_ext("março".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MARÇO".chars().map(u32::from).collect(), 3);
        all[4].put_ext("Março".chars().map(u32::from).collect(), 3);
        all[4].put_base("maart".chars().map(u32::from).collect(), 3);
        all[4].put_ext("maart".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MAART".chars().map(u32::from).collect(), 3);
        all[4].put_ext("Maart".chars().map(u32::from).collect(), 3);
        all[4].put_base("marca".chars().map(u32::from).collect(), 3);
        all[4].put_ext("marca".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MARCA".chars().map(u32::from).collect(), 3);
        all[4].put_ext("Marca".chars().map(u32::from).collect(), 3);
        all[4].put_base("mart".chars().map(u32::from).collect(), 3);
        all[4].put_ext("mart".chars().map(u32::from).collect(), 3);
        all[4].put_ext("MART".chars().map(u32::from).collect(), 3);
        all[4].put_ext("Mart".chars().map(u32::from).collect(), 3);
        all[4].put_base("三月".chars().map(u32::from).collect(), 3);
        all[4].put_ext("三月".chars().map(u32::from).collect(), 3);
        all[4].put_base("apr".chars().map(u32::from).collect(), 4);
        all[4].put_ext("apr".chars().map(u32::from).collect(), 4);
        all[4].put_ext("APR".chars().map(u32::from).collect(), 4);
        all[4].put_ext("Apr".chars().map(u32::from).collect(), 4);
        all[4].put_base("april".chars().map(u32::from).collect(), 4);
        all[4].put_ext("april".chars().map(u32::from).collect(), 4);
        all[4].put_ext("APRIL".chars().map(u32::from).collect(), 4);
        all[4].put_ext("April".chars().map(u32::from).collect(), 4);
        all[4].put_base("avril".chars().map(u32::from).collect(), 4);
        all[4].put_ext("avril".chars().map(u32::from).collect(), 4);
        all[4].put_ext("AVRIL".chars().map(u32::from).collect(), 4);
        all[4].put_ext("Avril".chars().map(u32::from).collect(), 4);
        all[4].put_base("aprile".chars().map(u32::from).collect(), 4);
        all[4].put_ext("aprile".chars().map(u32::from).collect(), 4);
        all[4].put_ext("APRILE".chars().map(u32::from).collect(), 4);
        all[4].put_ext("Aprile".chars().map(u32::from).collect(), 4);
        all[4].put_base("abril".chars().map(u32::from).collect(), 4);
        all[4].put_ext("abril".chars().map(u32::from).collect(), 4);
        all[4].put_ext("ABRIL".chars().map(u32::from).collect(), 4);
        all[4].put_ext("Abril".chars().map(u32::from).collect(), 4);
        all[4].put_base("kwietnia".chars().map(u32::from).collect(), 4);
        all[4].put_ext("kwietnia".chars().map(u32::from).collect(), 4);
        all[4].put_ext("KWIETNIA".chars().map(u32::from).collect(), 4);
        all[4].put_ext("Kwietnia".chars().map(u32::from).collect(), 4);
        all[4].put_base("nisan".chars().map(u32::from).collect(), 4);
        all[4].put_ext("nisan".chars().map(u32::from).collect(), 4);
        all[4].put_ext("NISAN".chars().map(u32::from).collect(), 4);
        all[4].put_ext("Nisan".chars().map(u32::from).collect(), 4);
        all[4].put_base("四月".chars().map(u32::from).collect(), 4);
        all[4].put_ext("四月".chars().map(u32::from).collect(), 4);
        all[4].put_base("may".chars().map(u32::from).collect(), 5);
        all[4].put_ext("may".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAY".chars().map(u32::from).collect(), 5);
        all[4].put_ext("May".chars().map(u32::from).collect(), 5);
        all[4].put_base("mai".chars().map(u32::from).collect(), 5);
        all[4].put_ext("mai".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAI".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Mai".chars().map(u32::from).collect(), 5);
        all[4].put_base("maggio".chars().map(u32::from).collect(), 5);
        all[4].put_ext("maggio".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAGGIO".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Maggio".chars().map(u32::from).collect(), 5);
        all[4].put_base("mayo".chars().map(u32::from).collect(), 5);
        all[4].put_ext("mayo".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAYO".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Mayo".chars().map(u32::from).collect(), 5);
        all[4].put_base("maio".chars().map(u32::from).collect(), 5);
        all[4].put_ext("maio".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAIO".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Maio".chars().map(u32::from).collect(), 5);
        all[4].put_base("mei".chars().map(u32::from).collect(), 5);
        all[4].put_ext("mei".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MEI".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Mei".chars().map(u32::from).collect(), 5);
        all[4].put_base("maj".chars().map(u32::from).collect(), 5);
        all[4].put_ext("maj".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAJ".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Maj".chars().map(u32::from).collect(), 5);
        all[4].put_base("maja".chars().map(u32::from).collect(), 5);
        all[4].put_ext("maja".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAJA".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Maja".chars().map(u32::from).collect(), 5);
        all[4].put_base("mayıs".chars().map(u32::from).collect(), 5);
        all[4].put_ext("mayıs".chars().map(u32::from).collect(), 5);
        all[4].put_ext("MAYIS".chars().map(u32::from).collect(), 5);
        all[4].put_ext("Mayıs".chars().map(u32::from).collect(), 5);
        all[4].put_base("五月".chars().map(u32::from).collect(), 5);
        all[4].put_ext("五月".chars().map(u32::from).collect(), 5);
        all[4].put_base("jun".chars().map(u32::from).collect(), 6);
        all[4].put_ext("jun".chars().map(u32::from).collect(), 6);
        all[4].put_ext("JUN".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Jun".chars().map(u32::from).collect(), 6);
        all[4].put_base("june".chars().map(u32::from).collect(), 6);
        all[4].put_ext("june".chars().map(u32::from).collect(), 6);
        all[4].put_ext("JUNE".chars().map(u32::from).collect(), 6);
        all[4].put_ext("June".chars().map(u32::from).collect(), 6);
        all[4].put_base("juni".chars().map(u32::from).collect(), 6);
        all[4].put_ext("juni".chars().map(u32::from).collect(), 6);
        all[4].put_ext("JUNI".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Juni".chars().map(u32::from).collect(), 6);
        all[4].put_base("juin".chars().map(u32::from).collect(), 6);
        all[4].put_ext("juin".chars().map(u32::from).collect(), 6);
        all[4].put_ext("JUIN".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Juin".chars().map(u32::from).collect(), 6);
        all[4].put_base("giugno".chars().map(u32::from).collect(), 6);
        all[4].put_ext("giugno".chars().map(u32::from).collect(), 6);
        all[4].put_ext("GIUGNO".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Giugno".chars().map(u32::from).collect(), 6);
        all[4].put_base("junio".chars().map(u32::from).collect(), 6);
        all[4].put_ext("junio".chars().map(u32::from).collect(), 6);
        all[4].put_ext("JUNIO".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Junio".chars().map(u32::from).collect(), 6);
        all[4].put_base("junho".chars().map(u32::from).collect(), 6);
        all[4].put_ext("junho".chars().map(u32::from).collect(), 6);
        all[4].put_ext("JUNHO".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Junho".chars().map(u32::from).collect(), 6);
        all[4].put_base("czerwca".chars().map(u32::from).collect(), 6);
        all[4].put_ext("czerwca".chars().map(u32::from).collect(), 6);
        all[4].put_ext("CZERWCA".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Czerwca".chars().map(u32::from).collect(), 6);
        all[4].put_base("haziran".chars().map(u32::from).collect(), 6);
        all[4].put_ext("haziran".chars().map(u32::from).collect(), 6);
        all[4].put_ext("HAZIRAN".chars().map(u32::from).collect(), 6);
        all[4].put_ext("Haziran".chars().map(u32::from).collect(), 6);
        all[4].put_base("六月".chars().map(u32::from).collect(), 6);
        all[4].put_ext("六月".chars().map(u32::from).collect(), 6);
        all[4].put_base("jul".chars().map(u32::from).collect(), 7);
        all[4].put_ext("jul".chars().map(u32::from).collect(), 7);
        all[4].put_ext("JUL".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Jul".chars().map(u32::from).collect(), 7);
        all[4].put_base("july".chars().map(u32::from).collect(), 7);
        all[4].put_ext("july".chars().map(u32::from).collect(), 7);
        all[4].put_ext("JULY".chars().map(u32::from).collect(), 7);
        all[4].put_ext("July".chars().map(u32::from).collect(), 7);
        all[4].put_base("juli".chars().map(u32::from).collect(), 7);
        all[4].put_ext("juli".chars().map(u32::from).collect(), 7);
        all[4].put_ext("JULI".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Juli".chars().map(u32::from).collect(), 7);
        all[4].put_base("juillet".chars().map(u32::from).collect(), 7);
        all[4].put_ext("juillet".chars().map(u32::from).collect(), 7);
        all[4].put_ext("JUILLET".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Juillet".chars().map(u32::from).collect(), 7);
        all[4].put_base("luglio".chars().map(u32::from).collect(), 7);
        all[4].put_ext("luglio".chars().map(u32::from).collect(), 7);
        all[4].put_ext("LUGLIO".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Luglio".chars().map(u32::from).collect(), 7);
        all[4].put_base("julio".chars().map(u32::from).collect(), 7);
        all[4].put_ext("julio".chars().map(u32::from).collect(), 7);
        all[4].put_ext("JULIO".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Julio".chars().map(u32::from).collect(), 7);
        all[4].put_base("julho".chars().map(u32::from).collect(), 7);
        all[4].put_ext("julho".chars().map(u32::from).collect(), 7);
        all[4].put_ext("JULHO".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Julho".chars().map(u32::from).collect(), 7);
        all[4].put_base("lipca".chars().map(u32::from).collect(), 7);
        all[4].put_ext("lipca".chars().map(u32::from).collect(), 7);
        all[4].put_ext("LIPCA".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Lipca".chars().map(u32::from).collect(), 7);
        all[4].put_base("temmuz".chars().map(u32::from).collect(), 7);
        all[4].put_ext("temmuz".chars().map(u32::from).collect(), 7);
        all[4].put_ext("TEMMUZ".chars().map(u32::from).collect(), 7);
        all[4].put_ext("Temmuz".chars().map(u32::from).collect(), 7);
        all[4].put_base("七月".chars().map(u32::from).collect(), 7);
        all[4].put_ext("七月".chars().map(u32::from).collect(), 7);
        all[4].put_base("aug".chars().map(u32::from).collect(), 8);
        all[4].put_ext("aug".chars().map(u32::from).collect(), 8);
        all[4].put_ext("AUG".chars().map(u32::from).collect(), 8);
        all[4].put_ext("Aug".chars().map(u32::from).collect(), 8);
        all[4].put_base("august".chars().map(u32::from).collect(), 8);
        all[4].put_ext("august".chars().map(u32::from).collect(), 8);
        all[4].put_ext("AUGUST".chars().map(u32::from).collect(), 8);
        all[4].put_ext("August".chars().map(u32::from).collect(), 8);
        all[4].put_base("août".chars().map(u32::from).collect(), 8);
        all[4].put_ext("août".chars().map(u32::from).collect(), 8);
        all[4].put_ext("AOÛT".chars().map(u32::from).collect(), 8);
        all[4].put_ext("Août".chars().map(u32::from).collect(), 8);
        all[4].put_base("agosto".chars().map(u32::from).collect(), 8);
        all[4].put_ext("agosto".chars().map(u32::from).collect(), 8);
        all[4].put_ext("AGOSTO".chars().map(u32::from).collect(), 8);
        all[4].put_ext("Agosto".chars().map(u32::from).collect(), 8);
        all[4].put_base("augustus".chars().map(u32::from).collect(), 8);
        all[4].put_ext("augustus".chars().map(u32::from).collect(), 8);
        all[4].put_ext("AUGUSTUS".chars().map(u32::from).collect(), 8);
        all[4].put_ext("Augustus".chars().map(u32::from).collect(), 8);
        all[4].put_base("augusti".chars().map(u32::from).collect(), 8);
        all[4].put_ext("augusti".chars().map(u32::from).collect(), 8);
        all[4].put_ext("AUGUSTI".chars().map(u32::from).collect(), 8);
        all[4].put_ext("Augusti".chars().map(u32::from).collect(), 8);
        all[4].put_base("sierpnia".chars().map(u32::from).collect(), 8);
        all[4].put_ext("sierpnia".chars().map(u32::from).collect(), 8);
        all[4].put_ext("SIERPNIA".chars().map(u32::from).collect(), 8);
        all[4].put_ext("Sierpnia".chars().map(u32::from).collect(), 8);
        all[4].put_base("ağustos".chars().map(u32::from).collect(), 8);
        all[4].put_ext("ağustos".chars().map(u32::from).collect(), 8);
        all[4].put_ext("AĞUSTOS".chars().map(u32::from).collect(), 8);
        all[4].put_ext("Ağustos".chars().map(u32::from).collect(), 8);
        all[4].put_base("八月".chars().map(u32::from).collect(), 8);
        all[4].put_ext("八月".chars().map(u32::from).collect(), 8);
        all[4].put_base("sep".chars().map(u32::from).collect(), 9);
        all[4].put_ext("sep".chars().map(u32::from).collect(), 9);
        all[4].put_ext("SEP".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Sep".chars().map(u32::from).collect(), 9);
        all[4].put_base("september".chars().map(u32::from).collect(), 9);
        all[4].put_ext("september".chars().map(u32::from).collect(), 9);
        all[4].put_ext("SEPTEMBER".chars().map(u32::from).collect(), 9);
        all[4].put_ext("September".chars().map(u32::from).collect(), 9);
        all[4].put_base("septembre".chars().map(u32::from).collect(), 9);
        all[4].put_ext("septembre".chars().map(u32::from).collect(), 9);
        all[4].put_ext("SEPTEMBRE".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Septembre".chars().map(u32::from).collect(), 9);
        all[4].put_base("settembre".chars().map(u32::from).collect(), 9);
        all[4].put_ext("settembre".chars().map(u32::from).collect(), 9);
        all[4].put_ext("SETTEMBRE".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Settembre".chars().map(u32::from).collect(), 9);
        all[4].put_base("septiembre".chars().map(u32::from).collect(), 9);
        all[4].put_ext("septiembre".chars().map(u32::from).collect(), 9);
        all[4].put_ext("SEPTIEMBRE".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Septiembre".chars().map(u32::from).collect(), 9);
        all[4].put_base("setembro".chars().map(u32::from).collect(), 9);
        all[4].put_ext("setembro".chars().map(u32::from).collect(), 9);
        all[4].put_ext("SETEMBRO".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Setembro".chars().map(u32::from).collect(), 9);
        all[4].put_base("września".chars().map(u32::from).collect(), 9);
        all[4].put_ext("września".chars().map(u32::from).collect(), 9);
        all[4].put_ext("WRZEŚNIA".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Września".chars().map(u32::from).collect(), 9);
        all[4].put_base("eylül".chars().map(u32::from).collect(), 9);
        all[4].put_ext("eylül".chars().map(u32::from).collect(), 9);
        all[4].put_ext("EYLÜL".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Eylül".chars().map(u32::from).collect(), 9);
        all[4].put_base("九月".chars().map(u32::from).collect(), 9);
        all[4].put_ext("九月".chars().map(u32::from).collect(), 9);
        all[4].put_base("sept".chars().map(u32::from).collect(), 9);
        all[4].put_ext("sept".chars().map(u32::from).collect(), 9);
        all[4].put_ext("SEPT".chars().map(u32::from).collect(), 9);
        all[4].put_ext("Sept".chars().map(u32::from).collect(), 9);
        all[4].put_base("oct".chars().map(u32::from).collect(), 10);
        all[4].put_ext("oct".chars().map(u32::from).collect(), 10);
        all[4].put_ext("OCT".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Oct".chars().map(u32::from).collect(), 10);
        all[4].put_base("october".chars().map(u32::from).collect(), 10);
        all[4].put_ext("october".chars().map(u32::from).collect(), 10);
        all[4].put_ext("OCTOBER".chars().map(u32::from).collect(), 10);
        all[4].put_ext("October".chars().map(u32::from).collect(), 10);
        all[4].put_base("oktober".chars().map(u32::from).collect(), 10);
        all[4].put_ext("oktober".chars().map(u32::from).collect(), 10);
        all[4].put_ext("OKTOBER".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Oktober".chars().map(u32::from).collect(), 10);
        all[4].put_base("octobre".chars().map(u32::from).collect(), 10);
        all[4].put_ext("octobre".chars().map(u32::from).collect(), 10);
        all[4].put_ext("OCTOBRE".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Octobre".chars().map(u32::from).collect(), 10);
        all[4].put_base("ottobre".chars().map(u32::from).collect(), 10);
        all[4].put_ext("ottobre".chars().map(u32::from).collect(), 10);
        all[4].put_ext("OTTOBRE".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Ottobre".chars().map(u32::from).collect(), 10);
        all[4].put_base("octubre".chars().map(u32::from).collect(), 10);
        all[4].put_ext("octubre".chars().map(u32::from).collect(), 10);
        all[4].put_ext("OCTUBRE".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Octubre".chars().map(u32::from).collect(), 10);
        all[4].put_base("outubro".chars().map(u32::from).collect(), 10);
        all[4].put_ext("outubro".chars().map(u32::from).collect(), 10);
        all[4].put_ext("OUTUBRO".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Outubro".chars().map(u32::from).collect(), 10);
        all[4].put_base("października".chars().map(u32::from).collect(), 10);
        all[4].put_ext("października".chars().map(u32::from).collect(), 10);
        all[4].put_ext("PAŹDZIERNIKA".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Października".chars().map(u32::from).collect(), 10);
        all[4].put_base("ekim".chars().map(u32::from).collect(), 10);
        all[4].put_ext("ekim".chars().map(u32::from).collect(), 10);
        all[4].put_ext("EKIM".chars().map(u32::from).collect(), 10);
        all[4].put_ext("Ekim".chars().map(u32::from).collect(), 10);
        all[4].put_base("十月".chars().map(u32::from).collect(), 10);
        all[4].put_ext("十月".chars().map(u32::from).collect(), 10);
        all[4].put_base("nov".chars().map(u32::from).collect(), 11);
        all[4].put_ext("nov".chars().map(u32::from).collect(), 11);
        all[4].put_ext("NOV".chars().map(u32::from).collect(), 11);
        all[4].put_ext("Nov".chars().map(u32::from).collect(), 11);
        all[4].put_base("november".chars().map(u32::from).collect(), 11);
        all[4].put_ext("november".chars().map(u32::from).collect(), 11);
        all[4].put_ext("NOVEMBER".chars().map(u32::from).collect(), 11);
        all[4].put_ext("November".chars().map(u32::from).collect(), 11);
        all[4].put_base("novembre".chars().map(u32::from).collect(), 11);
        all[4].put_ext("novembre".chars().map(u32::from).collect(), 11);
        all[4].put_ext("NOVEMBRE".chars().map(u32::from).collect(), 11);
        all[4].put_ext("Novembre".chars().map(u32::from).collect(), 11);
        all[4].put_base("noviembre".chars().map(u32::from).collect(), 11);
        all[4].put_ext("noviembre".chars().map(u32::from).collect(), 11);
        all[4].put_ext("NOVIEMBRE".chars().map(u32::from).collect(), 11);
        all[4].put_ext("Noviembre".chars().map(u32::from).collect(), 11);
        all[4].put_base("novembro".chars().map(u32::from).collect(), 11);
        all[4].put_ext("novembro".chars().map(u32::from).collect(), 11);
        all[4].put_ext("NOVEMBRO".chars().map(u32::from).collect(), 11);
        all[4].put_ext("Novembro".chars().map(u32::from).collect(), 11);
        all[4].put_base("listopada".chars().map(u32::from).collect(), 11);
        all[4].put_ext("listopada".chars().map(u32::from).collect(), 11);
        all[4].put_ext("LISTOPADA".chars().map(u32::from).collect(), 11);
        all[4].put_ext("Listopada".chars().map(u32::from).collect(), 11);
        all[4].put_base("kasım".chars().map(u32::from).collect(), 11);
        all[4].put_ext("kasım".chars().map(u32::from).collect(), 11);
        all[4].put_ext("KASIM".chars().map(u32::from).collect(), 11);
        all[4].put_ext("Kasım".chars().map(u32::from).collect(), 11);
        all[4].put_base("十一月".chars().map(u32::from).collect(), 11);
        all[4].put_ext("十一月".chars().map(u32::from).collect(), 11);
        all[4].put_base("dec".chars().map(u32::from).collect(), 12);
        all[4].put_ext("dec".chars().map(u32::from).collect(), 12);
        all[4].put_ext("DEC".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Dec".chars().map(u32::from).collect(), 12);
        all[4].put_base("december".chars().map(u32::from).collect(), 12);
        all[4].put_ext("december".chars().map(u32::from).collect(), 12);
        all[4].put_ext("DECEMBER".chars().map(u32::from).collect(), 12);
        all[4].put_ext("December".chars().map(u32::from).collect(), 12);
        all[4].put_base("dezember".chars().map(u32::from).collect(), 12);
        all[4].put_ext("dezember".chars().map(u32::from).collect(), 12);
        all[4].put_ext("DEZEMBER".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Dezember".chars().map(u32::from).collect(), 12);
        all[4].put_base("décembre".chars().map(u32::from).collect(), 12);
        all[4].put_ext("décembre".chars().map(u32::from).collect(), 12);
        all[4].put_ext("DÉCEMBRE".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Décembre".chars().map(u32::from).collect(), 12);
        all[4].put_base("dicembre".chars().map(u32::from).collect(), 12);
        all[4].put_ext("dicembre".chars().map(u32::from).collect(), 12);
        all[4].put_ext("DICEMBRE".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Dicembre".chars().map(u32::from).collect(), 12);
        all[4].put_base("diciembre".chars().map(u32::from).collect(), 12);
        all[4].put_ext("diciembre".chars().map(u32::from).collect(), 12);
        all[4].put_ext("DICIEMBRE".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Diciembre".chars().map(u32::from).collect(), 12);
        all[4].put_base("dezembro".chars().map(u32::from).collect(), 12);
        all[4].put_ext("dezembro".chars().map(u32::from).collect(), 12);
        all[4].put_ext("DEZEMBRO".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Dezembro".chars().map(u32::from).collect(), 12);
        all[4].put_base("grudnia".chars().map(u32::from).collect(), 12);
        all[4].put_ext("grudnia".chars().map(u32::from).collect(), 12);
        all[4].put_ext("GRUDNIA".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Grudnia".chars().map(u32::from).collect(), 12);
        all[4].put_base("aralık".chars().map(u32::from).collect(), 12);
        all[4].put_ext("aralık".chars().map(u32::from).collect(), 12);
        all[4].put_ext("ARALIK".chars().map(u32::from).collect(), 12);
        all[4].put_ext("Aralık".chars().map(u32::from).collect(), 12);
        all[4].put_base("十二月".chars().map(u32::from).collect(), 12);
        all[4].put_ext("十二月".chars().map(u32::from).collect(), 12);
        all[5].put_base("mon".chars().map(u32::from).collect(), 0);
        all[5].put_ext("mon".chars().map(u32::from).collect(), 0);
        all[5].put_ext("MON".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Mon".chars().map(u32::from).collect(), 0);
        all[5].put_base("monday".chars().map(u32::from).collect(), 0);
        all[5].put_ext("monday".chars().map(u32::from).collect(), 0);
        all[5].put_ext("MONDAY".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Monday".chars().map(u32::from).collect(), 0);
        all[5].put_base("montag".chars().map(u32::from).collect(), 0);
        all[5].put_ext("montag".chars().map(u32::from).collect(), 0);
        all[5].put_ext("MONTAG".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Montag".chars().map(u32::from).collect(), 0);
        all[5].put_base("lundi".chars().map(u32::from).collect(), 0);
        all[5].put_ext("lundi".chars().map(u32::from).collect(), 0);
        all[5].put_ext("LUNDI".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Lundi".chars().map(u32::from).collect(), 0);
        all[5].put_base("lunedì".chars().map(u32::from).collect(), 0);
        all[5].put_ext("lunedì".chars().map(u32::from).collect(), 0);
        all[5].put_ext("LUNEDÌ".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Lunedì".chars().map(u32::from).collect(), 0);
        all[5].put_base("lunes".chars().map(u32::from).collect(), 0);
        all[5].put_ext("lunes".chars().map(u32::from).collect(), 0);
        all[5].put_ext("LUNES".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Lunes".chars().map(u32::from).collect(), 0);
        all[5].put_base("maandag".chars().map(u32::from).collect(), 0);
        all[5].put_ext("maandag".chars().map(u32::from).collect(), 0);
        all[5].put_ext("MAANDAG".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Maandag".chars().map(u32::from).collect(), 0);
        all[5].put_base("måndag".chars().map(u32::from).collect(), 0);
        all[5].put_ext("måndag".chars().map(u32::from).collect(), 0);
        all[5].put_ext("MÅNDAG".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Måndag".chars().map(u32::from).collect(), 0);
        all[5].put_base("poniedziałek".chars().map(u32::from).collect(), 0);
        all[5].put_ext("poniedziałek".chars().map(u32::from).collect(), 0);
        all[5].put_ext("PONIEDZIAŁEK".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Poniedziałek".chars().map(u32::from).collect(), 0);
        all[5].put_base("pazartesi".chars().map(u32::from).collect(), 0);
        all[5].put_ext("pazartesi".chars().map(u32::from).collect(), 0);
        all[5].put_ext("PAZARTESI".chars().map(u32::from).collect(), 0);
        all[5].put_ext("Pazartesi".chars().map(u32::from).collect(), 0);
        all[5].put_base("星期一".chars().map(u32::from).collect(), 0);
        all[5].put_ext("星期一".chars().map(u32::from).collect(), 0);
        all[5].put_base("周一".chars().map(u32::from).collect(), 0);
        all[5].put_ext("周一".chars().map(u32::from).collect(), 0);
        all[5].put_base("tue".chars().map(u32::from).collect(), 1);
        all[5].put_ext("tue".chars().map(u32::from).collect(), 1);
        all[5].put_ext("TUE".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Tue".chars().map(u32::from).collect(), 1);
        all[5].put_base("tuesday".chars().map(u32::from).collect(), 1);
        all[5].put_ext("tuesday".chars().map(u32::from).collect(), 1);
        all[5].put_ext("TUESDAY".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Tuesday".chars().map(u32::from).collect(), 1);
        all[5].put_base("dienstag".chars().map(u32::from).collect(), 1);
        all[5].put_ext("dienstag".chars().map(u32::from).collect(), 1);
        all[5].put_ext("DIENSTAG".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Dienstag".chars().map(u32::from).collect(), 1);
        all[5].put_base("mardi".chars().map(u32::from).collect(), 1);
        all[5].put_ext("mardi".chars().map(u32::from).collect(), 1);
        all[5].put_ext("MARDI".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Mardi".chars().map(u32::from).collect(), 1);
        all[5].put_base("martedì".chars().map(u32::from).collect(), 1);
        all[5].put_ext("martedì".chars().map(u32::from).collect(), 1);
        all[5].put_ext("MARTEDÌ".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Martedì".chars().map(u32::from).collect(), 1);
        all[5].put_base("martes".chars().map(u32::from).collect(), 1);
        all[5].put_ext("martes".chars().map(u32::from).collect(), 1);
        all[5].put_ext("MARTES".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Martes".chars().map(u32::from).collect(), 1);
        all[5].put_base("dinsdag".chars().map(u32::from).collect(), 1);
        all[5].put_ext("dinsdag".chars().map(u32::from).collect(), 1);
        all[5].put_ext("DINSDAG".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Dinsdag".chars().map(u32::from).collect(), 1);
        all[5].put_base("tisdag".chars().map(u32::from).collect(), 1);
        all[5].put_ext("tisdag".chars().map(u32::from).collect(), 1);
        all[5].put_ext("TISDAG".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Tisdag".chars().map(u32::from).collect(), 1);
        all[5].put_base("wtorek".chars().map(u32::from).collect(), 1);
        all[5].put_ext("wtorek".chars().map(u32::from).collect(), 1);
        all[5].put_ext("WTOREK".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Wtorek".chars().map(u32::from).collect(), 1);
        all[5].put_base("salı".chars().map(u32::from).collect(), 1);
        all[5].put_ext("salı".chars().map(u32::from).collect(), 1);
        all[5].put_ext("SALI".chars().map(u32::from).collect(), 1);
        all[5].put_ext("Salı".chars().map(u32::from).collect(), 1);
        all[5].put_base("星期二".chars().map(u32::from).collect(), 1);
        all[5].put_ext("星期二".chars().map(u32::from).collect(), 1);
        all[5].put_base("周二".chars().map(u32::from).collect(), 1);
        all[5].put_ext("周二".chars().map(u32::from).collect(), 1);
        all[5].put_base("wed".chars().map(u32::from).collect(), 2);
        all[5].put_ext("wed".chars().map(u32::from).collect(), 2);
        all[5].put_ext("WED".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Wed".chars().map(u32::from).collect(), 2);
        all[5].put_base("wednesday".chars().map(u32::from).collect(), 2);
        all[5].put_ext("wednesday".chars().map(u32::from).collect(), 2);
        all[5].put_ext("WEDNESDAY".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Wednesday".chars().map(u32::from).collect(), 2);
        all[5].put_base("mittwoch".chars().map(u32::from).collect(), 2);
        all[5].put_ext("mittwoch".chars().map(u32::from).collect(), 2);
        all[5].put_ext("MITTWOCH".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Mittwoch".chars().map(u32::from).collect(), 2);
        all[5].put_base("mercredi".chars().map(u32::from).collect(), 2);
        all[5].put_ext("mercredi".chars().map(u32::from).collect(), 2);
        all[5].put_ext("MERCREDI".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Mercredi".chars().map(u32::from).collect(), 2);
        all[5].put_base("mercoledì".chars().map(u32::from).collect(), 2);
        all[5].put_ext("mercoledì".chars().map(u32::from).collect(), 2);
        all[5].put_ext("MERCOLEDÌ".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Mercoledì".chars().map(u32::from).collect(), 2);
        all[5].put_base("miércoles".chars().map(u32::from).collect(), 2);
        all[5].put_ext("miércoles".chars().map(u32::from).collect(), 2);
        all[5].put_ext("MIÉRCOLES".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Miércoles".chars().map(u32::from).collect(), 2);
        all[5].put_base("woensdag".chars().map(u32::from).collect(), 2);
        all[5].put_ext("woensdag".chars().map(u32::from).collect(), 2);
        all[5].put_ext("WOENSDAG".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Woensdag".chars().map(u32::from).collect(), 2);
        all[5].put_base("onsdag".chars().map(u32::from).collect(), 2);
        all[5].put_ext("onsdag".chars().map(u32::from).collect(), 2);
        all[5].put_ext("ONSDAG".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Onsdag".chars().map(u32::from).collect(), 2);
        all[5].put_base("środa".chars().map(u32::from).collect(), 2);
        all[5].put_ext("środa".chars().map(u32::from).collect(), 2);
        all[5].put_ext("ŚRODA".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Środa".chars().map(u32::from).collect(), 2);
        all[5].put_base("çarşamba".chars().map(u32::from).collect(), 2);
        all[5].put_ext("çarşamba".chars().map(u32::from).collect(), 2);
        all[5].put_ext("ÇARŞAMBA".chars().map(u32::from).collect(), 2);
        all[5].put_ext("Çarşamba".chars().map(u32::from).collect(), 2);
        all[5].put_base("星期三".chars().map(u32::from).collect(), 2);
        all[5].put_ext("星期三".chars().map(u32::from).collect(), 2);
        all[5].put_base("周三".chars().map(u32::from).collect(), 2);
        all[5].put_ext("周三".chars().map(u32::from).collect(), 2);
        all[5].put_base("thu".chars().map(u32::from).collect(), 3);
        all[5].put_ext("thu".chars().map(u32::from).collect(), 3);
        all[5].put_ext("THU".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Thu".chars().map(u32::from).collect(), 3);
        all[5].put_base("thursday".chars().map(u32::from).collect(), 3);
        all[5].put_ext("thursday".chars().map(u32::from).collect(), 3);
        all[5].put_ext("THURSDAY".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Thursday".chars().map(u32::from).collect(), 3);
        all[5].put_base("donnerstag".chars().map(u32::from).collect(), 3);
        all[5].put_ext("donnerstag".chars().map(u32::from).collect(), 3);
        all[5].put_ext("DONNERSTAG".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Donnerstag".chars().map(u32::from).collect(), 3);
        all[5].put_base("jeudi".chars().map(u32::from).collect(), 3);
        all[5].put_ext("jeudi".chars().map(u32::from).collect(), 3);
        all[5].put_ext("JEUDI".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Jeudi".chars().map(u32::from).collect(), 3);
        all[5].put_base("giovedì".chars().map(u32::from).collect(), 3);
        all[5].put_ext("giovedì".chars().map(u32::from).collect(), 3);
        all[5].put_ext("GIOVEDÌ".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Giovedì".chars().map(u32::from).collect(), 3);
        all[5].put_base("jueves".chars().map(u32::from).collect(), 3);
        all[5].put_ext("jueves".chars().map(u32::from).collect(), 3);
        all[5].put_ext("JUEVES".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Jueves".chars().map(u32::from).collect(), 3);
        all[5].put_base("donderdag".chars().map(u32::from).collect(), 3);
        all[5].put_ext("donderdag".chars().map(u32::from).collect(), 3);
        all[5].put_ext("DONDERDAG".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Donderdag".chars().map(u32::from).collect(), 3);
        all[5].put_base("torsdag".chars().map(u32::from).collect(), 3);
        all[5].put_ext("torsdag".chars().map(u32::from).collect(), 3);
        all[5].put_ext("TORSDAG".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Torsdag".chars().map(u32::from).collect(), 3);
        all[5].put_base("czwartek".chars().map(u32::from).collect(), 3);
        all[5].put_ext("czwartek".chars().map(u32::from).collect(), 3);
        all[5].put_ext("CZWARTEK".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Czwartek".chars().map(u32::from).collect(), 3);
        all[5].put_base("perşembe".chars().map(u32::from).collect(), 3);
        all[5].put_ext("perşembe".chars().map(u32::from).collect(), 3);
        all[5].put_ext("PERŞEMBE".chars().map(u32::from).collect(), 3);
        all[5].put_ext("Perşembe".chars().map(u32::from).collect(), 3);
        all[5].put_base("星期四".chars().map(u32::from).collect(), 3);
        all[5].put_ext("星期四".chars().map(u32::from).collect(), 3);
        all[5].put_base("周四".chars().map(u32::from).collect(), 3);
        all[5].put_ext("周四".chars().map(u32::from).collect(), 3);
        all[5].put_base("fri".chars().map(u32::from).collect(), 4);
        all[5].put_ext("fri".chars().map(u32::from).collect(), 4);
        all[5].put_ext("FRI".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Fri".chars().map(u32::from).collect(), 4);
        all[5].put_base("friday".chars().map(u32::from).collect(), 4);
        all[5].put_ext("friday".chars().map(u32::from).collect(), 4);
        all[5].put_ext("FRIDAY".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Friday".chars().map(u32::from).collect(), 4);
        all[5].put_base("freitag".chars().map(u32::from).collect(), 4);
        all[5].put_ext("freitag".chars().map(u32::from).collect(), 4);
        all[5].put_ext("FREITAG".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Freitag".chars().map(u32::from).collect(), 4);
        all[5].put_base("vendredi".chars().map(u32::from).collect(), 4);
        all[5].put_ext("vendredi".chars().map(u32::from).collect(), 4);
        all[5].put_ext("VENDREDI".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Vendredi".chars().map(u32::from).collect(), 4);
        all[5].put_base("venerdì".chars().map(u32::from).collect(), 4);
        all[5].put_ext("venerdì".chars().map(u32::from).collect(), 4);
        all[5].put_ext("VENERDÌ".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Venerdì".chars().map(u32::from).collect(), 4);
        all[5].put_base("viernes".chars().map(u32::from).collect(), 4);
        all[5].put_ext("viernes".chars().map(u32::from).collect(), 4);
        all[5].put_ext("VIERNES".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Viernes".chars().map(u32::from).collect(), 4);
        all[5].put_base("vrijdag".chars().map(u32::from).collect(), 4);
        all[5].put_ext("vrijdag".chars().map(u32::from).collect(), 4);
        all[5].put_ext("VRIJDAG".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Vrijdag".chars().map(u32::from).collect(), 4);
        all[5].put_base("fredag".chars().map(u32::from).collect(), 4);
        all[5].put_ext("fredag".chars().map(u32::from).collect(), 4);
        all[5].put_ext("FREDAG".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Fredag".chars().map(u32::from).collect(), 4);
        all[5].put_base("piątek".chars().map(u32::from).collect(), 4);
        all[5].put_ext("piątek".chars().map(u32::from).collect(), 4);
        all[5].put_ext("PIĄTEK".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Piątek".chars().map(u32::from).collect(), 4);
        all[5].put_base("cuma".chars().map(u32::from).collect(), 4);
        all[5].put_ext("cuma".chars().map(u32::from).collect(), 4);
        all[5].put_ext("CUMA".chars().map(u32::from).collect(), 4);
        all[5].put_ext("Cuma".chars().map(u32::from).collect(), 4);
        all[5].put_base("星期五".chars().map(u32::from).collect(), 4);
        all[5].put_ext("星期五".chars().map(u32::from).collect(), 4);
        all[5].put_base("周五".chars().map(u32::from).collect(), 4);
        all[5].put_ext("周五".chars().map(u32::from).collect(), 4);
        all[5].put_base("sat".chars().map(u32::from).collect(), 5);
        all[5].put_ext("sat".chars().map(u32::from).collect(), 5);
        all[5].put_ext("SAT".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Sat".chars().map(u32::from).collect(), 5);
        all[5].put_base("saturday".chars().map(u32::from).collect(), 5);
        all[5].put_ext("saturday".chars().map(u32::from).collect(), 5);
        all[5].put_ext("SATURDAY".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Saturday".chars().map(u32::from).collect(), 5);
        all[5].put_base("samstag".chars().map(u32::from).collect(), 5);
        all[5].put_ext("samstag".chars().map(u32::from).collect(), 5);
        all[5].put_ext("SAMSTAG".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Samstag".chars().map(u32::from).collect(), 5);
        all[5].put_base("samedi".chars().map(u32::from).collect(), 5);
        all[5].put_ext("samedi".chars().map(u32::from).collect(), 5);
        all[5].put_ext("SAMEDI".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Samedi".chars().map(u32::from).collect(), 5);
        all[5].put_base("sabato".chars().map(u32::from).collect(), 5);
        all[5].put_ext("sabato".chars().map(u32::from).collect(), 5);
        all[5].put_ext("SABATO".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Sabato".chars().map(u32::from).collect(), 5);
        all[5].put_base("sábado".chars().map(u32::from).collect(), 5);
        all[5].put_ext("sábado".chars().map(u32::from).collect(), 5);
        all[5].put_ext("SÁBADO".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Sábado".chars().map(u32::from).collect(), 5);
        all[5].put_base("zaterdag".chars().map(u32::from).collect(), 5);
        all[5].put_ext("zaterdag".chars().map(u32::from).collect(), 5);
        all[5].put_ext("ZATERDAG".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Zaterdag".chars().map(u32::from).collect(), 5);
        all[5].put_base("lördag".chars().map(u32::from).collect(), 5);
        all[5].put_ext("lördag".chars().map(u32::from).collect(), 5);
        all[5].put_ext("LÖRDAG".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Lördag".chars().map(u32::from).collect(), 5);
        all[5].put_base("sobota".chars().map(u32::from).collect(), 5);
        all[5].put_ext("sobota".chars().map(u32::from).collect(), 5);
        all[5].put_ext("SOBOTA".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Sobota".chars().map(u32::from).collect(), 5);
        all[5].put_base("cumartesi".chars().map(u32::from).collect(), 5);
        all[5].put_ext("cumartesi".chars().map(u32::from).collect(), 5);
        all[5].put_ext("CUMARTESI".chars().map(u32::from).collect(), 5);
        all[5].put_ext("Cumartesi".chars().map(u32::from).collect(), 5);
        all[5].put_base("星期六".chars().map(u32::from).collect(), 5);
        all[5].put_ext("星期六".chars().map(u32::from).collect(), 5);
        all[5].put_base("周六".chars().map(u32::from).collect(), 5);
        all[5].put_ext("周六".chars().map(u32::from).collect(), 5);
        all[5].put_base("sun".chars().map(u32::from).collect(), 6);
        all[5].put_ext("sun".chars().map(u32::from).collect(), 6);
        all[5].put_ext("SUN".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Sun".chars().map(u32::from).collect(), 6);
        all[5].put_base("sunday".chars().map(u32::from).collect(), 6);
        all[5].put_ext("sunday".chars().map(u32::from).collect(), 6);
        all[5].put_ext("SUNDAY".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Sunday".chars().map(u32::from).collect(), 6);
        all[5].put_base("sonntag".chars().map(u32::from).collect(), 6);
        all[5].put_ext("sonntag".chars().map(u32::from).collect(), 6);
        all[5].put_ext("SONNTAG".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Sonntag".chars().map(u32::from).collect(), 6);
        all[5].put_base("dimanche".chars().map(u32::from).collect(), 6);
        all[5].put_ext("dimanche".chars().map(u32::from).collect(), 6);
        all[5].put_ext("DIMANCHE".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Dimanche".chars().map(u32::from).collect(), 6);
        all[5].put_base("domenica".chars().map(u32::from).collect(), 6);
        all[5].put_ext("domenica".chars().map(u32::from).collect(), 6);
        all[5].put_ext("DOMENICA".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Domenica".chars().map(u32::from).collect(), 6);
        all[5].put_base("domingo".chars().map(u32::from).collect(), 6);
        all[5].put_ext("domingo".chars().map(u32::from).collect(), 6);
        all[5].put_ext("DOMINGO".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Domingo".chars().map(u32::from).collect(), 6);
        all[5].put_base("zondag".chars().map(u32::from).collect(), 6);
        all[5].put_ext("zondag".chars().map(u32::from).collect(), 6);
        all[5].put_ext("ZONDAG".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Zondag".chars().map(u32::from).collect(), 6);
        all[5].put_base("söndag".chars().map(u32::from).collect(), 6);
        all[5].put_ext("söndag".chars().map(u32::from).collect(), 6);
        all[5].put_ext("SÖNDAG".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Söndag".chars().map(u32::from).collect(), 6);
        all[5].put_base("niedziela".chars().map(u32::from).collect(), 6);
        all[5].put_ext("niedziela".chars().map(u32::from).collect(), 6);
        all[5].put_ext("NIEDZIELA".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Niedziela".chars().map(u32::from).collect(), 6);
        all[5].put_base("pazar".chars().map(u32::from).collect(), 6);
        all[5].put_ext("pazar".chars().map(u32::from).collect(), 6);
        all[5].put_ext("PAZAR".chars().map(u32::from).collect(), 6);
        all[5].put_ext("Pazar".chars().map(u32::from).collect(), 6);
        all[5].put_base("星期日".chars().map(u32::from).collect(), 6);
        all[5].put_ext("星期日".chars().map(u32::from).collect(), 6);
        all[5].put_base("周日".chars().map(u32::from).collect(), 6);
        all[5].put_ext("周日".chars().map(u32::from).collect(), 6);
        all[6].put_base("h".chars().map(u32::from).collect(), 0);
        all[6].put_ext("h".chars().map(u32::from).collect(), 0);
        all[6].put_ext("H".chars().map(u32::from).collect(), 0);
        all[6].put_base("hour".chars().map(u32::from).collect(), 0);
        all[6].put_ext("hour".chars().map(u32::from).collect(), 0);
        all[6].put_ext("HOUR".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Hour".chars().map(u32::from).collect(), 0);
        all[6].put_base("stunde".chars().map(u32::from).collect(), 0);
        all[6].put_ext("stunde".chars().map(u32::from).collect(), 0);
        all[6].put_ext("STUNDE".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Stunde".chars().map(u32::from).collect(), 0);
        all[6].put_base("heure".chars().map(u32::from).collect(), 0);
        all[6].put_ext("heure".chars().map(u32::from).collect(), 0);
        all[6].put_ext("HEURE".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Heure".chars().map(u32::from).collect(), 0);
        all[6].put_base("ora".chars().map(u32::from).collect(), 0);
        all[6].put_ext("ora".chars().map(u32::from).collect(), 0);
        all[6].put_ext("ORA".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Ora".chars().map(u32::from).collect(), 0);
        all[6].put_base("hora".chars().map(u32::from).collect(), 0);
        all[6].put_ext("hora".chars().map(u32::from).collect(), 0);
        all[6].put_ext("HORA".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Hora".chars().map(u32::from).collect(), 0);
        all[6].put_base("uur".chars().map(u32::from).collect(), 0);
        all[6].put_ext("uur".chars().map(u32::from).collect(), 0);
        all[6].put_ext("UUR".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Uur".chars().map(u32::from).collect(), 0);
        all[6].put_base("timme".chars().map(u32::from).collect(), 0);
        all[6].put_ext("timme".chars().map(u32::from).collect(), 0);
        all[6].put_ext("TIMME".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Timme".chars().map(u32::from).collect(), 0);
        all[6].put_base("godzina".chars().map(u32::from).collect(), 0);
        all[6].put_ext("godzina".chars().map(u32::from).collect(), 0);
        all[6].put_ext("GODZINA".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Godzina".chars().map(u32::from).collect(), 0);
        all[6].put_base("saat".chars().map(u32::from).collect(), 0);
        all[6].put_ext("saat".chars().map(u32::from).collect(), 0);
        all[6].put_ext("SAAT".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Saat".chars().map(u32::from).collect(), 0);
        all[6].put_base("时".chars().map(u32::from).collect(), 0);
        all[6].put_ext("时".chars().map(u32::from).collect(), 0);
        all[6].put_base("hr".chars().map(u32::from).collect(), 0);
        all[6].put_ext("hr".chars().map(u32::from).collect(), 0);
        all[6].put_ext("HR".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Hr".chars().map(u32::from).collect(), 0);
        all[6].put_base("hours".chars().map(u32::from).collect(), 0);
        all[6].put_ext("hours".chars().map(u32::from).collect(), 0);
        all[6].put_ext("HOURS".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Hours".chars().map(u32::from).collect(), 0);
        all[6].put_base("stunden".chars().map(u32::from).collect(), 0);
        all[6].put_ext("stunden".chars().map(u32::from).collect(), 0);
        all[6].put_ext("STUNDEN".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Stunden".chars().map(u32::from).collect(), 0);
        all[6].put_base("heures".chars().map(u32::from).collect(), 0);
        all[6].put_ext("heures".chars().map(u32::from).collect(), 0);
        all[6].put_ext("HEURES".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Heures".chars().map(u32::from).collect(), 0);
        all[6].put_base("ore".chars().map(u32::from).collect(), 0);
        all[6].put_ext("ore".chars().map(u32::from).collect(), 0);
        all[6].put_ext("ORE".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Ore".chars().map(u32::from).collect(), 0);
        all[6].put_base("horas".chars().map(u32::from).collect(), 0);
        all[6].put_ext("horas".chars().map(u32::from).collect(), 0);
        all[6].put_ext("HORAS".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Horas".chars().map(u32::from).collect(), 0);
        all[6].put_base("uren".chars().map(u32::from).collect(), 0);
        all[6].put_ext("uren".chars().map(u32::from).collect(), 0);
        all[6].put_ext("UREN".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Uren".chars().map(u32::from).collect(), 0);
        all[6].put_base("timmar".chars().map(u32::from).collect(), 0);
        all[6].put_ext("timmar".chars().map(u32::from).collect(), 0);
        all[6].put_ext("TIMMAR".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Timmar".chars().map(u32::from).collect(), 0);
        all[6].put_base("godziny".chars().map(u32::from).collect(), 0);
        all[6].put_ext("godziny".chars().map(u32::from).collect(), 0);
        all[6].put_ext("GODZINY".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Godziny".chars().map(u32::from).collect(), 0);
        all[6].put_base("saatler".chars().map(u32::from).collect(), 0);
        all[6].put_ext("saatler".chars().map(u32::from).collect(), 0);
        all[6].put_ext("SAATLER".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Saatler".chars().map(u32::from).collect(), 0);
        all[6].put_base("小时".chars().map(u32::from).collect(), 0);
        all[6].put_ext("小时".chars().map(u32::from).collect(), 0);
        all[6].put_base("m".chars().map(u32::from).collect(), 1);
        all[6].put_ext("m".chars().map(u32::from).collect(), 1);
        all[6].put_ext("M".chars().map(u32::from).collect(), 1);
        all[6].put_base("minute".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minute".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTE".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minute".chars().map(u32::from).collect(), 1);
        all[6].put_base("minuto".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minuto".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTO".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minuto".chars().map(u32::from).collect(), 1);
        all[6].put_base("minuut".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minuut".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUUT".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minuut".chars().map(u32::from).collect(), 1);
        all[6].put_base("minut".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minut".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUT".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minut".chars().map(u32::from).collect(), 1);
        all[6].put_base("minuta".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minuta".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTA".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minuta".chars().map(u32::from).collect(), 1);
        all[6].put_base("dakika".chars().map(u32::from).collect(), 1);
        all[6].put_ext("dakika".chars().map(u32::from).collect(), 1);
        all[6].put_ext("DAKIKA".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Dakika".chars().map(u32::from).collect(), 1);
        all[6].put_base("分".chars().map(u32::from).collect(), 1);
        all[6].put_ext("分".chars().map(u32::from).collect(), 1);
        all[6].put_base("min".chars().map(u32::from).collect(), 1);
        all[6].put_ext("min".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MIN".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Min".chars().map(u32::from).collect(), 1);
        all[6].put_base("minutes".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minutes".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTES".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minutes".chars().map(u32::from).collect(), 1);
        all[6].put_base("minuten".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minuten".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTEN".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minuten".chars().map(u32::from).collect(), 1);
        all[6].put_base("minuti".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minuti".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTI".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minuti".chars().map(u32::from).collect(), 1);
        all[6].put_base("minutos".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minutos".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTOS".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minutos".chars().map(u32::from).collect(), 1);
        all[6].put_base("minuter".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minuter".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTER".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minuter".chars().map(u32::from).collect(), 1);
        all[6].put_base("minuty".chars().map(u32::from).collect(), 1);
        all[6].put_ext("minuty".chars().map(u32::from).collect(), 1);
        all[6].put_ext("MINUTY".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Minuty".chars().map(u32::from).collect(), 1);
        all[6].put_base("dakikalar".chars().map(u32::from).collect(), 1);
        all[6].put_ext("dakikalar".chars().map(u32::from).collect(), 1);
        all[6].put_ext("DAKIKALAR".chars().map(u32::from).collect(), 1);
        all[6].put_ext("Dakikalar".chars().map(u32::from).collect(), 1);
        all[6].put_base("分钟".chars().map(u32::from).collect(), 1);
        all[6].put_ext("分钟".chars().map(u32::from).collect(), 1);
        all[6].put_base("s".chars().map(u32::from).collect(), 2);
        all[6].put_ext("s".chars().map(u32::from).collect(), 2);
        all[6].put_ext("S".chars().map(u32::from).collect(), 2);
        all[6].put_base("second".chars().map(u32::from).collect(), 2);
        all[6].put_ext("second".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SECOND".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Second".chars().map(u32::from).collect(), 2);
        all[6].put_base("sekunde".chars().map(u32::from).collect(), 2);
        all[6].put_ext("sekunde".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEKUNDE".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Sekunde".chars().map(u32::from).collect(), 2);
        all[6].put_base("seconde".chars().map(u32::from).collect(), 2);
        all[6].put_ext("seconde".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SECONDE".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Seconde".chars().map(u32::from).collect(), 2);
        all[6].put_base("secondo".chars().map(u32::from).collect(), 2);
        all[6].put_ext("secondo".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SECONDO".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Secondo".chars().map(u32::from).collect(), 2);
        all[6].put_base("segundo".chars().map(u32::from).collect(), 2);
        all[6].put_ext("segundo".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEGUNDO".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Segundo".chars().map(u32::from).collect(), 2);
        all[6].put_base("sekund".chars().map(u32::from).collect(), 2);
        all[6].put_ext("sekund".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEKUND".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Sekund".chars().map(u32::from).collect(), 2);
        all[6].put_base("sekunda".chars().map(u32::from).collect(), 2);
        all[6].put_ext("sekunda".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEKUNDA".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Sekunda".chars().map(u32::from).collect(), 2);
        all[6].put_base("saniye".chars().map(u32::from).collect(), 2);
        all[6].put_ext("saniye".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SANIYE".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Saniye".chars().map(u32::from).collect(), 2);
        all[6].put_base("秒".chars().map(u32::from).collect(), 2);
        all[6].put_ext("秒".chars().map(u32::from).collect(), 2);
        all[6].put_base("sec".chars().map(u32::from).collect(), 2);
        all[6].put_ext("sec".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEC".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Sec".chars().map(u32::from).collect(), 2);
        all[6].put_base("seconds".chars().map(u32::from).collect(), 2);
        all[6].put_ext("seconds".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SECONDS".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Seconds".chars().map(u32::from).collect(), 2);
        all[6].put_base("sekunden".chars().map(u32::from).collect(), 2);
        all[6].put_ext("sekunden".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEKUNDEN".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Sekunden".chars().map(u32::from).collect(), 2);
        all[6].put_base("secondes".chars().map(u32::from).collect(), 2);
        all[6].put_ext("secondes".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SECONDES".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Secondes".chars().map(u32::from).collect(), 2);
        all[6].put_base("secondi".chars().map(u32::from).collect(), 2);
        all[6].put_ext("secondi".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SECONDI".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Secondi".chars().map(u32::from).collect(), 2);
        all[6].put_base("segundos".chars().map(u32::from).collect(), 2);
        all[6].put_ext("segundos".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEGUNDOS".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Segundos".chars().map(u32::from).collect(), 2);
        all[6].put_base("seconden".chars().map(u32::from).collect(), 2);
        all[6].put_ext("seconden".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SECONDEN".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Seconden".chars().map(u32::from).collect(), 2);
        all[6].put_base("sekunder".chars().map(u32::from).collect(), 2);
        all[6].put_ext("sekunder".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEKUNDER".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Sekunder".chars().map(u32::from).collect(), 2);
        all[6].put_base("sekundy".chars().map(u32::from).collect(), 2);
        all[6].put_ext("sekundy".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SEKUNDY".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Sekundy".chars().map(u32::from).collect(), 2);
        all[6].put_base("saniyeler".chars().map(u32::from).collect(), 2);
        all[6].put_ext("saniyeler".chars().map(u32::from).collect(), 2);
        all[6].put_ext("SANIYELER".chars().map(u32::from).collect(), 2);
        all[6].put_ext("Saniyeler".chars().map(u32::from).collect(), 2);
        all[6].put_base("godzin".chars().map(u32::from).collect(), 0);
        all[6].put_ext("godzin".chars().map(u32::from).collect(), 0);
        all[6].put_ext("GODZIN".chars().map(u32::from).collect(), 0);
        all[6].put_ext("Godzin".chars().map(u32::from).collect(), 0);
        all[7].put_base("a".chars().map(u32::from).collect(), 0);
        all[7].put_ext("a".chars().map(u32::from).collect(), 0);
        all[7].put_ext("A".chars().map(u32::from).collect(), 0);
        all[7].put_base("am".chars().map(u32::from).collect(), 0);
        all[7].put_ext("am".chars().map(u32::from).collect(), 0);
        all[7].put_ext("AM".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Am".chars().map(u32::from).collect(), 0);
        all[7].put_base("morning".chars().map(u32::from).collect(), 0);
        all[7].put_ext("morning".chars().map(u32::from).collect(), 0);
        all[7].put_ext("MORNING".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Morning".chars().map(u32::from).collect(), 0);
        all[7].put_base("morgen".chars().map(u32::from).collect(), 0);
        all[7].put_ext("morgen".chars().map(u32::from).collect(), 0);
        all[7].put_ext("MORGEN".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Morgen".chars().map(u32::from).collect(), 0);
        all[7].put_base("mattina".chars().map(u32::from).collect(), 0);
        all[7].put_ext("mattina".chars().map(u32::from).collect(), 0);
        all[7].put_ext("MATTINA".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Mattina".chars().map(u32::from).collect(), 0);
        all[7].put_base("mañana".chars().map(u32::from).collect(), 0);
        all[7].put_ext("mañana".chars().map(u32::from).collect(), 0);
        all[7].put_ext("MAÑANA".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Mañana".chars().map(u32::from).collect(), 0);
        all[7].put_base("manhã".chars().map(u32::from).collect(), 0);
        all[7].put_ext("manhã".chars().map(u32::from).collect(), 0);
        all[7].put_ext("MANHÃ".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Manhã".chars().map(u32::from).collect(), 0);
        all[7].put_base("ochtend".chars().map(u32::from).collect(), 0);
        all[7].put_ext("ochtend".chars().map(u32::from).collect(), 0);
        all[7].put_ext("OCHTEND".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Ochtend".chars().map(u32::from).collect(), 0);
        all[7].put_base("morgon".chars().map(u32::from).collect(), 0);
        all[7].put_ext("morgon".chars().map(u32::from).collect(), 0);
        all[7].put_ext("MORGON".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Morgon".chars().map(u32::from).collect(), 0);
        all[7].put_base("rano".chars().map(u32::from).collect(), 0);
        all[7].put_ext("rano".chars().map(u32::from).collect(), 0);
        all[7].put_ext("RANO".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Rano".chars().map(u32::from).collect(), 0);
        all[7].put_base("sabah".chars().map(u32::from).collect(), 0);
        all[7].put_ext("sabah".chars().map(u32::from).collect(), 0);
        all[7].put_ext("SABAH".chars().map(u32::from).collect(), 0);
        all[7].put_ext("Sabah".chars().map(u32::from).collect(), 0);
        all[7].put_base("上午".chars().map(u32::from).collect(), 0);
        all[7].put_ext("上午".chars().map(u32::from).collect(), 0);
        all[7].put_base("p".chars().map(u32::from).collect(), 1);
        all[7].put_ext("p".chars().map(u32::from).collect(), 1);
        all[7].put_ext("P".chars().map(u32::from).collect(), 1);
        all[7].put_base("pm".chars().map(u32::from).collect(), 1);
        all[7].put_ext("pm".chars().map(u32::from).collect(), 1);
        all[7].put_ext("PM".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Pm".chars().map(u32::from).collect(), 1);
        all[7].put_base("afternoon".chars().map(u32::from).collect(), 1);
        all[7].put_ext("afternoon".chars().map(u32::from).collect(), 1);
        all[7].put_ext("AFTERNOON".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Afternoon".chars().map(u32::from).collect(), 1);
        all[7].put_base("nachmittag".chars().map(u32::from).collect(), 1);
        all[7].put_ext("nachmittag".chars().map(u32::from).collect(), 1);
        all[7].put_ext("NACHMITTAG".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Nachmittag".chars().map(u32::from).collect(), 1);
        all[7].put_base("pomeriggio".chars().map(u32::from).collect(), 1);
        all[7].put_ext("pomeriggio".chars().map(u32::from).collect(), 1);
        all[7].put_ext("POMERIGGIO".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Pomeriggio".chars().map(u32::from).collect(), 1);
        all[7].put_base("tarde".chars().map(u32::from).collect(), 1);
        all[7].put_ext("tarde".chars().map(u32::from).collect(), 1);
        all[7].put_ext("TARDE".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Tarde".chars().map(u32::from).collect(), 1);
        all[7].put_base("middag".chars().map(u32::from).collect(), 1);
        all[7].put_ext("middag".chars().map(u32::from).collect(), 1);
        all[7].put_ext("MIDDAG".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Middag".chars().map(u32::from).collect(), 1);
        all[7].put_base("eftermiddag".chars().map(u32::from).collect(), 1);
        all[7].put_ext("eftermiddag".chars().map(u32::from).collect(), 1);
        all[7].put_ext("EFTERMIDDAG".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Eftermiddag".chars().map(u32::from).collect(), 1);
        all[7].put_base("popołudnie".chars().map(u32::from).collect(), 1);
        all[7].put_ext("popołudnie".chars().map(u32::from).collect(), 1);
        all[7].put_ext("POPOŁUDNIE".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Popołudnie".chars().map(u32::from).collect(), 1);
        all[7].put_base("öğleden".chars().map(u32::from).collect(), 1);
        all[7].put_ext("öğleden".chars().map(u32::from).collect(), 1);
        all[7].put_ext("ÖĞLEDEN".chars().map(u32::from).collect(), 1);
        all[7].put_ext("Öğleden".chars().map(u32::from).collect(), 1);
        all[7].put_base("下午".chars().map(u32::from).collect(), 1);
        all[7].put_ext("下午".chars().map(u32::from).collect(), 1);
        all
    })
}
