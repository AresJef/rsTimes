//! Shared final column assembly: local fields and known instants stay distinct.
use super::zones::Policies;
use crate::epoch::Unit;
use crate::temporal_zone::{Zone, ZoneError};
use polars::prelude::*;
use pyo3::prelude::*;
use std::collections::HashMap;

#[derive(Clone, Copy)]
pub(super) enum Kind {
    Type,
    Value,
    Capacity,
    Runtime,
    Parse,
    Memory,
}

pub(super) struct Failure {
    pub(super) kind: Kind,
    pub(super) message: String,
    pub(super) row: Option<usize>,
}
impl Failure {
    pub(super) fn new(kind: Kind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
            row: None,
        }
    }
    pub(super) fn at(mut self, row: usize) -> Self {
        self.row = Some(row);
        self
    }
    pub(super) fn python(self, py: Python<'_>, entry: &str) -> PyErr {
        let error = match self.kind {
            Kind::Type => crate::error_context::type_error(self.message),
            Kind::Value => crate::error_context::value_error(self.message),
            Kind::Capacity => crate::error_context::overflow(self.message),
            Kind::Runtime => crate::error_context::runtime(self.message),
            Kind::Parse => crate::error_context::domain(py, "ParseError", self.message),
            Kind::Memory => pyo3::exceptions::PyMemoryError::new_err(self.message),
        };
        crate::error_context::location(
            py,
            error,
            entry,
            &self
                .row
                .map_or_else(|| "arguments".into(), |row| format!("data[{row}]")),
        )
    }
    pub(super) fn polars(self, entry: &str) -> PolarsError {
        let location = self
            .row
            .map_or_else(String::new, |row| format!("batch item {row}: "));
        polars_err!(ComputeError:"{}: {}{}",entry,location,self.message)
    }
}
impl From<ZoneError> for Failure {
    fn from(value: ZoneError) -> Self {
        let kind = match value {
            ZoneError::Type(_) => Kind::Type,
            ZoneError::Value(_) => Kind::Value,
            ZoneError::Capacity(_) => Kind::Capacity,
        };
        Self::new(kind, value.to_string())
    }
}

enum SourceZone {
    Naive,
    Offset(i64),
    Region(Zone),
}
#[derive(Clone, Copy)]
struct Source {
    zone: usize,
    instant: bool,
}

/// Compact row coordinates, one distinct zone value and an independent validity.
pub(super) struct Rows {
    values: Vec<Option<i128>>,
    sources: Vec<Source>,
    zones: Vec<SourceZone>,
    names: HashMap<String, usize>,
    unit: Unit,
    common: Option<usize>,
    conflict: Option<usize>,
}
impl Rows {
    pub(super) fn new(unit: Unit) -> Self {
        Self {
            values: Vec::new(),
            sources: Vec::new(),
            zones: vec![SourceZone::Naive],
            names: HashMap::new(),
            unit,
            common: None,
            conflict: None,
        }
    }
    pub(super) fn include_unit(&mut self, unit: Unit) {
        self.unit = self.unit.max(unit);
    }
    /// Typed source metadata survives empty/all-missing input without a scan.
    pub(super) fn inherit_zone(&mut self, zone: usize) {
        self.common = Some(zone);
    }
    pub(super) fn repeat(&mut self, size: usize) -> Result<(), Failure> {
        if self.values.len() != 1 {
            return Err(Failure::new(
                Kind::Runtime,
                "a scalar factory requires exactly one prepared row",
            ));
        }
        if size
            .checked_mul(std::mem::size_of::<Option<i128>>())
            .is_none_or(|bytes| bytes > isize::MAX as usize)
        {
            return Err(Failure::new(
                Kind::Capacity,
                "requested size exceeds the native column allocation range",
            ));
        }
        self.values
            .try_reserve(size.saturating_sub(1))
            .map_err(|_| Failure::new(Kind::Memory, "cannot reserve the requested date column"))?;
        self.sources
            .try_reserve(size.saturating_sub(1))
            .map_err(|_| {
                Failure::new(
                    Kind::Memory,
                    "cannot reserve the requested date source metadata",
                )
            })?;
        self.values.resize(size, self.values[0]);
        self.sources.resize(size, self.sources[0]);
        Ok(())
    }
    pub(super) fn offset(&mut self, offset_us: i64) -> Result<usize, Failure> {
        if !(-86_400_000_000..86_400_000_000).contains(&offset_us) || offset_us == -86_400_000_000 {
            return Err(Failure::new(
                Kind::Value,
                "source timezone offset must be strictly between -24 and +24 hours",
            ));
        }
        if let Some(index) = self
            .zones
            .iter()
            .position(|zone| matches!(zone,SourceZone::Offset(value) if *value==offset_us))
        {
            return Ok(index);
        }
        let index = self.zones.len();
        self.zones.push(SourceZone::Offset(offset_us));
        Ok(index)
    }
    pub(super) fn region(&mut self, key: &str) -> Result<usize, Failure> {
        if let Some(&index) = self.names.get(key) {
            return Ok(index);
        }
        let zone = Zone::named(key).map_err(|message| Failure::new(Kind::Value, message))?;
        self.zone(zone)
    }
    pub(super) fn zone(&mut self, zone: Zone) -> Result<usize, Failure> {
        if let Some(offset) = zone.fixed_seconds() {
            return self.offset(i64::from(offset) * 1_000_000);
        }
        if let Some(&index) = self.names.get(zone.key()) {
            return Ok(index);
        }
        let index = self.zones.len();
        self.names.insert(zone.key().to_owned(), index);
        self.zones.push(SourceZone::Region(zone));
        Ok(index)
    }
    pub(super) fn missing(&mut self) {
        self.values.push(None);
        self.sources.push(Source {
            zone: 0,
            instant: false,
        });
    }
    pub(super) fn push(&mut self, value: i128, zone: usize, instant: bool, unit: Unit) {
        let row = self.values.len();
        if let Some(common) = self.common {
            if common != zone && self.conflict.is_none() {
                self.conflict = Some(row)
            }
        } else {
            self.common = Some(zone)
        }
        self.unit = self.unit.max(unit);
        self.values.push(Some(value));
        self.sources.push(Source { zone, instant });
    }
    pub(super) fn finish(
        mut self,
        name: PlSmallStr,
        requested: Option<Unit>,
        target: Option<&Zone>,
        policy: &Policies,
        truncated: bool,
    ) -> Result<Series, Failure> {
        let unit = requested.unwrap_or(self.unit.max(Unit::Millisecond));
        policy.check_len(self.values.len())?;
        let output_zone = if let Some(target) = target {
            Some(target.key().to_owned())
        } else {
            if let Some(row) = self.conflict {
                return Err(Failure::new(
                    Kind::Value,
                    "valid source timezones differ; pass an explicit common tz target",
                )
                .at(row));
            }
            match self.common.map(|index| &self.zones[index]) {
                None | Some(SourceZone::Naive) => None,
                Some(SourceZone::Region(zone)) => Some(zone.key().to_owned()),
                Some(SourceZone::Offset(offset)) => {
                    if *offset == 0 {
                        Some("UTC".into())
                    } else {
                        if offset % 3_600_000_000 != 0 {
                            return Err(Failure::new(
                                Kind::Value,
                                "this source fixed offset cannot be represented by a Polars timezone; pass tz='UTC' or another supported target",
                            ));
                        }
                        let key = format!(
                            "Etc/GMT{}{}",
                            if *offset > 0 { "-" } else { "+" },
                            offset.unsigned_abs() / 3_600_000_000
                        );
                        Zone::named(&key).map_err(|message| Failure::new(Kind::Value, message))?;
                        Some(key)
                    }
                }
            }
        };
        let needs_infer = policy.infer()
            && self.sources.iter().any(|source| {
                !source.instant
                    && match &self.zones[source.zone] {
                        SourceZone::Region(_) => true,
                        SourceZone::Naive => {
                            target.is_some_and(|zone| zone.fixed_seconds().is_none())
                        }
                        SourceZone::Offset(_) => false,
                    }
            });
        let mut pending = if needs_infer {
            vec![None; self.values.len()]
        } else {
            Vec::new()
        };
        for (row, (value, source)) in self.values.iter_mut().zip(&self.sources).enumerate() {
            let Some(wall) = *value else { continue };
            if source.instant {
                continue;
            }
            *value = match &self.zones[source.zone] {
                SourceZone::Naive => match target {
                    None => Some(wall),
                    Some(zone) => policy
                        .localize(wall, zone, unit, row, self.zones.len(), &mut pending)
                        .map_err(|error| Failure::from(error).at(row))?,
                },
                SourceZone::Offset(offset) => Some(wall - i128::from(*offset) * 1000),
                SourceZone::Region(zone) => policy
                    .localize(wall, zone, unit, row, source.zone, &mut pending)
                    .map_err(|error| Failure::from(error).at(row))?,
            };
        }
        policy.complete(&mut self.values, &pending)?;
        let mut output = PrimitiveChunkedBuilder::<Int64Type>::new(name, self.values.len());
        for (row, value) in self.values.into_iter().enumerate() {
            let tick=value.map(|value|crate::precision::epoch_tick(value,unit.nanos(),truncated).map_err(|error|match error{
                crate::precision::TickError::Precision=>Failure::new(Kind::Value,"source precision cannot fit the selected unit without loss; choose a finer unit or explicitly use as_unit").at(row),
                crate::precision::TickError::Capacity=>Failure::new(Kind::Capacity,"date exceeds the selected unit capacity; explicitly select a coarser supported unit").at(row),
            })).transpose()?;
            output.append_option(tick);
        }
        Ok(output
            .finish()
            .into_datetime(
                super::input::resolution(unit),
                TimeZone::opt_try_new(output_zone)
                    .map_err(|error| Failure::new(Kind::Value, error.to_string()))?,
            )
            .into_series())
    }
}

/// Already completed and validated civil fields; no temporary Python date.
pub(super) fn fields_nanos(fields: [i64; 7], tail: i64) -> Result<i128, Failure> {
    let [year, month, day, hour, minute, second, microsecond] = fields;
    let ordinal = crate::calendar::checked_ordinal(year, month, day)
        .map_err(|message| Failure::new(Kind::Capacity, message))?;
    Ok((i128::from(ordinal) - 719_163) * 86_400_000_000_000
        + ((i128::from(hour) * 60 + i128::from(minute)) * 60 + i128::from(second)) * 1_000_000_000
        + i128::from(microsecond) * 1000
        + i128::from(tail))
}
