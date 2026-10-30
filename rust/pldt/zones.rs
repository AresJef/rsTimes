//! Once-prepared host policies and their Python-free native execution values.
use crate::epoch::Unit;
use crate::local_infer::Pending;
use crate::parser::Truth;
use crate::temporal_zone::{Candidates, Zone, ZoneData, ZoneError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDelta, PyDeltaAccess, PyDict, PyString};
use serde::{Deserialize, Serialize};

static HOST_RESOLVER: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// Real Python source protocols stay at the host boundary, outside workers.
pub(super) fn prepare_host_zone(value: &Bound<'_, PyAny>) -> PyResult<Zone> {
    let py = value.py();
    let resolver = crate::python_cache::get_or_prepare(&HOST_RESOLVER, py, || {
        py.import("rstimes._pldt_timezone")?
            .getattr("prepare_timezone")
            .map(Bound::unbind)
    })?;
    let context = resolver.bind(py).call1((value,))?;
    Ok(context.cast::<Context>()?.borrow().value.clone())
}

/// Explicit policy choices, never inferred from arbitrary truth values.
#[derive(Clone, Copy, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub(super) enum Ambiguous {
    Raise,
    Missing,
    Infer,
    First,
    Second,
    Mask,
}

#[derive(Clone, Copy, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
enum Nonexistent {
    Raise,
    Missing,
    Forward,
    Backward,
    Shift,
}

/// Owned rule data may be sent to a worker without its Python wrapper.
#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Policies {
    ambiguous: Ambiguous,
    nonexistent: Nonexistent,
    #[serde(deserialize_with = "crate::serde_values::byte_vector")]
    mask: Vec<u8>,
    #[serde(with = "crate::serde_values::signed_128")]
    shift_ns: i128,
}

impl Policies {
    pub(super) fn strict() -> Self {
        Self {
            ambiguous: Ambiguous::Raise,
            nonexistent: Nonexistent::Raise,
            mask: Vec::new(),
            shift_ns: 0,
        }
    }
    /// Respect the expression's logical scalar/vector role, never its length.
    pub(super) fn with_expression_mask(
        &self,
        mask: &polars::prelude::Series,
        scalar: bool,
    ) -> Result<Self, ZoneError> {
        use polars::prelude::*;
        if mask.dtype() != &DataType::Boolean || mask.null_count() != 0 {
            return Err(ZoneError::Type(
                "ambiguous requires actual booleans without null",
            ));
        }
        let values = mask
            .bool()
            .map_err(|_| ZoneError::Type("ambiguous requires a Boolean column"))?;
        if scalar {
            if mask.len() != 1 {
                return Err(ZoneError::Value(
                    "logical scalar ambiguous expression must return one boolean",
                ));
            }
            Ok(self.with_choice(
                values
                    .get(0)
                    .ok_or(ZoneError::Type("ambiguous scalar cannot be null"))?,
            ))
        } else {
            Ok(self.with_mask(
                values
                    .iter()
                    .map(|value| u8::from(value == Some(true)))
                    .collect(),
            ))
        }
    }
    /// Range endpoints use the first/last complete-sequence mask choice.
    pub(super) fn endpoint(&self, end: bool) -> Self {
        if matches!(self.ambiguous, Ambiguous::Mask) {
            let choice = if end {
                self.mask.last()
            } else {
                self.mask.first()
            };
            if let Some(choice) = choice {
                return self.with_choice(*choice != 0);
            }
            return Self {
                ambiguous: Ambiguous::Raise,
                nonexistent: self.nonexistent,
                mask: Vec::new(),
                shift_ns: self.shift_ns,
            };
        }
        self.clone()
    }
    pub(super) fn infer(&self) -> bool {
        matches!(self.ambiguous, Ambiguous::Infer)
    }
    pub(super) fn check_len(&self, len: usize) -> Result<(), ZoneError> {
        if matches!(self.ambiguous, Ambiguous::Mask) && self.mask.len() != len {
            return Err(ZoneError::Value(
                "ambiguous boolean collection must match the complete date source length",
            ));
        }
        Ok(())
    }
    pub(super) fn with_mask(&self, mask: Vec<u8>) -> Self {
        Self {
            ambiguous: Ambiguous::Mask,
            nonexistent: self.nonexistent,
            shift_ns: self.shift_ns,
            mask,
        }
    }
    pub(super) fn with_choice(&self, value: bool) -> Self {
        Self {
            ambiguous: if value {
                Ambiguous::First
            } else {
                Ambiguous::Second
            },
            nonexistent: self.nonexistent,
            mask: Vec::new(),
            shift_ns: self.shift_ns,
        }
    }
    fn choose(
        &self,
        candidates: Candidates,
        index: usize,
        zone: usize,
        pending: &mut [Option<Pending>],
    ) -> Result<Option<i128>, ZoneError> {
        match candidates {
            Candidates::One(value) => Ok(Some(value)),
            Candidates::Repeated(first, second) => match self.ambiguous {
                Ambiguous::Raise => Err(ZoneError::Value(
                    "local time occurs twice; set ambiguous to True, False, 'infer', 'NaT' or an equal-length boolean collection",
                )),
                Ambiguous::Missing => Ok(None),
                Ambiguous::First => Ok(Some(first)),
                Ambiguous::Second => Ok(Some(second)),
                Ambiguous::Mask => self
                    .mask
                    .get(index)
                    .map(|value| Some(if *value != 0 { first } else { second }))
                    .ok_or(ZoneError::Value(
                        "ambiguous boolean collection has an invalid length",
                    )),
                Ambiguous::Infer => {
                    let item = pending
                        .get_mut(index)
                        .ok_or(ZoneError::Value("invalid inference buffer length"))?;
                    *item = Some(Pending {
                        first,
                        second,
                        zone,
                    });
                    Ok(None)
                }
            },
            Candidates::Gap { .. } => Err(ZoneError::Value(
                "the requested nonexistent adjustment still lands in a missing local time",
            )),
        }
    }
    pub(super) fn localize(
        &self,
        wall: i128,
        zone: &Zone,
        unit: Unit,
        index: usize,
        zone_id: usize,
        pending: &mut [Option<Pending>],
    ) -> Result<Option<i128>, ZoneError> {
        let candidates = zone.candidates(wall)?;
        let Candidates::Gap { before, after } = candidates else {
            return self.choose(candidates, index, zone_id, pending);
        };
        let shifted = match self.nonexistent {
            Nonexistent::Raise => {
                return Err(ZoneError::Value(
                    "local time does not exist; select an existing time or set nonexistent to a supported policy",
                ));
            }
            Nonexistent::Missing => return Ok(None),
            Nonexistent::Shift => wall
                .checked_add(self.shift_ns)
                .ok_or(ZoneError::Capacity("nonexistent adjustment overflow"))?,
            Nonexistent::Forward | Nonexistent::Backward => {
                let (begin, end) = zone.gap_edges(wall, before, after)?;
                if matches!(self.nonexistent, Nonexistent::Forward) {
                    -(-end).div_euclid(unit.nanos()) * unit.nanos()
                } else {
                    (begin - 1).div_euclid(unit.nanos()) * unit.nanos()
                }
            }
        };
        self.choose(zone.candidates(shifted)?, index, zone_id, pending)
    }
    pub(super) fn complete(
        &self,
        values: &mut [Option<i128>],
        pending: &[Option<Pending>],
    ) -> Result<(), ZoneError> {
        if !self.infer() {
            return Ok(());
        }
        crate::local_infer::infer(values, pending).map_err(|error| match error {
            crate::local_infer::InferError::Data(message)
            | crate::local_infer::InferError::Internal(message) => ZoneError::Value(message),
        })
    }
}

/// No source Python tzinfo is held by this immutable native context.
#[pyclass(frozen, skip_from_py_object, name = "_PldtZoneContext")]
pub(super) struct Context {
    pub(super) value: Zone,
}
#[pymethods]
impl Context {
    #[getter]
    fn key(&self) -> &str {
        self.value.key()
    }
    #[getter]
    fn fixed_seconds(&self) -> Option<i32> {
        self.value.fixed_seconds()
    }
    fn plugin_kwargs<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        use pyo3::IntoPyObject;
        self.value.snapshot().into_pyobject(py)
    }
}

#[pyclass(frozen, skip_from_py_object, name = "_PldtPolicyContext")]
pub(super) struct PolicyContext {
    pub(super) value: Policies,
}
#[pymethods]
impl PolicyContext {
    fn plugin_kwargs<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let result = PyDict::new(py);
        result.set_item(
            "ambiguous",
            match self.value.ambiguous {
                Ambiguous::Raise => "raise",
                Ambiguous::Missing => "missing",
                Ambiguous::Infer => "infer",
                Ambiguous::First => "first",
                Ambiguous::Second => "second",
                Ambiguous::Mask => "mask",
            },
        )?;
        result.set_item(
            "nonexistent",
            match self.value.nonexistent {
                Nonexistent::Raise => "raise",
                Nonexistent::Missing => "missing",
                Nonexistent::Forward => "forward",
                Nonexistent::Backward => "backward",
                Nonexistent::Shift => "shift",
            },
        )?;
        result.set_item("mask", &self.value.mask)?;
        result.set_item(
            "shift_ns",
            (
                (self.value.shift_ns >> 64) as i64,
                self.value.shift_ns as i64,
            ),
        )?;
        Ok(result)
    }
    #[getter]
    fn infers(&self) -> bool {
        self.value.infer()
    }
}

pub(super) fn error(error: ZoneError) -> PyErr {
    match error {
        ZoneError::Type(message) => crate::error_context::type_error(message),
        ZoneError::Capacity(message) => crate::error_context::overflow(message),
        ZoneError::Value(message) => crate::error_context::value_error(message),
    }
}

#[pyfunction]
fn _pldt_zone_context(key: String, data: &[u8], fixed_seconds: Option<i32>) -> PyResult<Context> {
    Ok(Context {
        value: Zone::from_data(ZoneData {
            key,
            data: data.to_vec(),
            fixed_seconds,
        })
        .map_err(crate::error_context::value_error)?,
    })
}

#[pyfunction]
fn _pldt_named_zone_context(key: &str) -> PyResult<Context> {
    Ok(Context {
        value: Zone::named(key).map_err(crate::error_context::value_error)?,
    })
}

#[pyfunction]
fn _pldt_tzdb_info() -> (&'static str, &'static str, usize) {
    (
        tzdb_data::VERSION,
        tzdb_data::VERSION_HASH,
        tzdb_data::TZ_NAMES.len(),
    )
}

#[pyfunction]
#[pyo3(signature=(ambiguous,nonexistent,expression_mask=Truth(false)))]
fn _pldt_policies(
    ambiguous: &Bound<'_, PyAny>,
    nonexistent: &Bound<'_, PyAny>,
    expression_mask: Truth,
) -> PyResult<PolicyContext> {
    let py = ambiguous.py();
    let mut mask = Vec::new();
    let choice = (|| -> PyResult<Ambiguous> {
        Ok(if expression_mask.0 {
        Ambiguous::Mask
    } else if crate::numeric::is_bool(ambiguous) {
        if crate::numeric::boolean(ambiguous)? {
            Ambiguous::First
        } else {
            Ambiguous::Second
        }
    } else if let Ok(text) = ambiguous.cast::<PyString>() {
        match text.to_str()? {
            "raise" => Ambiguous::Raise,
            "NaT" => Ambiguous::Missing,
            "infer" => Ambiguous::Infer,
            _ => {
                return Err(crate::error_context::value_error(
                    "ambiguous must be 'raise', 'NaT', 'infer', a true boolean or an equal-length boolean collection",
                ));
            }
        }
    } else {
        for (row, item) in ambiguous
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let item = item.map_err(crate::error_context::external)?;
            mask.push(u8::from(crate::numeric::boolean(&item).map_err(
                |error| {
                    crate::error_context::item(
                        py,
                        error,
                        "Pldt",
                        "ambiguous",
                        row,
                        Some(&item),
                        false,
                    )
                },
            )?));
        }
        Ambiguous::Mask
        })
    })().map_err(|error| crate::error_context::argument(py, error, "Pldt", "ambiguous", ambiguous))?;
    let mut shift_ns = 0;
    let missing = (|| -> PyResult<Nonexistent> {
        Ok(if let Ok(text) = nonexistent.cast::<PyString>() {
        match text.to_str()? {
            "raise" => Nonexistent::Raise,
            "NaT" => Nonexistent::Missing,
            "shift_forward" => Nonexistent::Forward,
            "shift_backward" => Nonexistent::Backward,
            _ => {
                return Err(crate::error_context::value_error(
                    "nonexistent must be 'raise', 'NaT', 'shift_forward', 'shift_backward' or one timedelta",
                ));
            }
        }
    } else {
        let delta = nonexistent.cast::<PyDelta>().map_err(|_| {
            crate::error_context::type_error(
                "nonexistent requires a supported policy string or one timedelta",
            )
        })?;
        shift_ns = if let Some(value) = crate::interop::duration_nanoseconds(nonexistent)? {
            value
        } else {
            (i128::from(delta.get_days()) * 86400 + i128::from(delta.get_seconds())) * 1_000_000_000
                + i128::from(delta.get_microseconds()) * 1000
        };
        Nonexistent::Shift
        })
    })().map_err(|error| crate::error_context::argument(py, error, "Pldt", "nonexistent", nonexistent))?;
    Ok(PolicyContext {
        value: Policies {
            ambiguous: choice,
            nonexistent: missing,
            mask,
            shift_ns,
        },
    })
}

/// Minimal private candidate proof path; public column wiring shares this data.
#[pyfunction]
fn _pldt_zone_probe(
    walls: Vec<Option<i128>>,
    zone: PyRef<'_, Context>,
    policy: PyRef<'_, PolicyContext>,
    unit: &str,
) -> PyResult<Vec<Option<i128>>> {
    let unit = Unit::parse(unit)?;
    policy.value.check_len(walls.len()).map_err(error)?;
    let mut pending = if policy.value.infer() && zone.value.fixed_seconds().is_none() {
        vec![None; walls.len()]
    } else {
        Vec::new()
    };
    let mut values = Vec::with_capacity(walls.len());
    for (row, value) in walls.into_iter().enumerate() {
        values.push(
            value
                .map(|wall| {
                    policy
                        .value
                        .localize(wall, &zone.value, unit, row, 0, &mut pending)
                })
                .transpose()
                .map_err(error)?
                .flatten(),
        );
    }
    policy
        .value
        .complete(&mut values, &pending)
        .map_err(error)?;
    Ok(values)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<Context>()?;
    module.add_class::<PolicyContext>()?;
    module.add_function(wrap_pyfunction!(_pldt_zone_context, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_named_zone_context, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_tzdb_info, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_policies, module)?)?;
    module.add_function(wrap_pyfunction!(_pldt_zone_probe, module)?)
}
