//! Shared host date/clock protocols; container policies and final assembly stay separate.
use crate::date_input::date_missing;
use crate::epoch::{self, Options, Unit, Zone};
use crate::parser::fields::{Lenient, Nano};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyString, PyTime, PyTimeAccess};
const NS_DAY: i128 = 86_400_000_000_000;
#[derive(Clone, Copy)]
pub(crate) struct Piece {
    pub(crate) value: i128,
    pub(crate) zone: usize,
}

pub(crate) struct Reader<'a, 'py> {
    clock: bool,
    pub(crate) zones: Vec<Zone>,
    resolved: Vec<(Py<PyAny>, usize)>,
    resolver: &'a Bound<'py, PyAny>,
}
impl<'a, 'py> Reader<'a, 'py> {
    pub(crate) fn new(clock: bool, resolver: &'a Bound<'py, PyAny>) -> Self {
        Self {
            clock,
            zones: vec![Zone::Naive],
            resolved: Vec::new(),
            resolver,
        }
    }

    pub(crate) fn zone(&mut self, raw: Bound<'py, PyAny>) -> PyResult<usize> {
        if raw.is_none() {
            return Ok(0);
        }
        if let Some((_, id)) = self
            .resolved
            .iter()
            .find(|(source, _)| source.bind(raw.py()).is(&raw))
        {
            return Ok(*id);
        }
        let zone = self
            .resolver
            .call1((&raw,))
            .map_err(crate::error_context::external)?
            .unbind();
        let id = self.zones.len();
        self.zones.push(Zone::Object(zone));
        self.resolved.push((raw.unbind(), id));
        Ok(id)
    }
    pub(crate) fn read(&mut self, value: &Bound<'py, PyAny>) -> PyResult<Option<Piece>> {
        if !value.is_instance_of::<PyString>() && date_missing(value)? {
            return Ok(None);
        }
        if crate::numeric::is_bool(value) {
            return Err(crate::error_context::type_error(
                "boolean values are not date or clock fields",
            ));
        }
        if let Ok(clock) = value.cast::<PyTime>() {
            if !self.clock {
                return Err(crate::error_context::type_error(
                    "a time supplies clock fields, not a date",
                ));
            }
            let nanos = ((i128::from(clock.get_hour()) * 60 + i128::from(clock.get_minute())) * 60
                + i128::from(clock.get_second()))
                * 1_000_000_000
                + i128::from(clock.get_microsecond()) * 1000;
            // SAFETY: the validated live time retains its actual stored timezone.
            let zone = unsafe {
                Bound::from_borrowed_ptr(
                    value.py(),
                    ffi::PyDateTime_TIME_GET_TZINFO(value.as_ptr()),
                )
            };
            return Ok(Some(Piece {
                value: nanos,
                zone: self.zone(zone)?,
            }));
        }
        let opts = Options {
            default: None,
            yearfirst: None,
            dayfirst: None,
            ignoretz: true,
            isoformat: true,
            strict: false,
            iso_only: false,
            cfg: None,
            input_unit: Unit::Second,
        };
        let mut parsed = if let Ok(text) = value.cast::<PyString>() {
            let converted;
            let text = if value.is_exact_instance_of::<PyString>() {
                text
            } else {
                converted = value.str().map_err(crate::error_context::external)?;
                &converted
            };
            if matches!(
                text.to_str()?,
                "" | "NaT" | "NAT" | "nat" | "NaN" | "NAN" | "nan"
            ) {
                return Ok(None);
            }
            let mut text_opts = opts;
            text_opts.ignoretz = !self.clock;
            crate::date_input::text_fields::<Nano<Lenient>>(
                value.py(),
                text,
                if self.clock { Some([1970, 1, 1]) } else { None },
                &text_opts,
            )?
        } else {
            epoch::read(value, &opts)?
        };
        if !self.clock {
            return Ok(Some(Piece {
                value: parsed.nanos.div_euclid(NS_DAY),
                zone: 0,
            }));
        }
        let zone = if unsafe { ffi::PyDateTime_Check(value.as_ptr()) != 0 } {
            // SAFETY: actual datetime ancestry proves this timezone payload.
            self.zone(unsafe {
                Bound::from_borrowed_ptr(
                    value.py(),
                    ffi::PyDateTime_DATE_GET_TZINFO(value.as_ptr()),
                )
            })?
        } else if matches!(parsed.zone, Zone::Naive) {
            0
        } else {
            let id = self.zones.len();
            self.zones
                .push(std::mem::replace(&mut parsed.zone, Zone::Naive));
            id
        };
        Ok(Some(Piece {
            value: parsed.nanos.rem_euclid(NS_DAY),
            zone,
        }))
    }
}
