//! Named factories share native calendar fields and a single final byte buffer.
use crate::epoch::{Unit, Zone};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::time::{SystemTime, UNIX_EPOCH};

pub(super) fn system_nanos(time: SystemTime) -> PyResult<i128> {
    match time.duration_since(UNIX_EPOCH) {
        Ok(value) => i128::try_from(value.as_nanos()),
        Err(value) => i128::try_from(value.duration().as_nanos()).map(|n| -n),
    }
    .map_err(|_| crate::error_context::overflow("system clock exceeds native integer range"))
}

/// Read one integer clock value after all parameters and empty-size are known.
#[pyfunction]
fn _pddt_now<'py>(
    py: Python<'py>,
    count: usize,
    unit: &str,
    zone: Option<&Bound<'py, PyAny>>,
    naive: bool,
) -> PyResult<Bound<'py, PyBytes>> {
    let unit = Unit::parse(unit)?;
    let size = count
        .checked_mul(8)
        .filter(|size| *size <= isize::MAX as usize)
        .ok_or_else(|| crate::error_context::overflow("size is too large"))?;
    if count == 0 {
        return Ok(PyBytes::new(py, &[]));
    }
    let mut ns = system_nanos(SystemTime::now())?;
    if naive {
        let zone = zone.filter(|z| !z.is_none()).ok_or_else(|| {
            crate::error_context::runtime("local clock needs a prepared timezone")
        })?;
        let object = Zone::Object(zone.clone().unbind());
        ns = super::zones::utc_wall(ns, zone, super::common::fixed_offset(py, &object)?)?;
    }
    let tick = i64::try_from(ns.div_euclid(unit.nanos()))
        .ok()
        .filter(|v| *v != i64::MIN)
        .ok_or_else(|| crate::error_context::overflow("clock exceeds the requested unit"))?
        .to_ne_bytes();
    PyBytes::new_with(py, size, |out| {
        for row in out.chunks_exact_mut(8) {
            row.copy_from_slice(&tick);
        }
        Ok(())
    })
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_now, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_numbers, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_number_buffer, module)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn system_clock_integer_sign_and_subsecond_precision() {
        let delta = std::time::Duration::new(1, 123456789);
        assert_eq!(system_nanos(UNIX_EPOCH + delta).unwrap(), 1123456789);
        assert_eq!(system_nanos(UNIX_EPOCH - delta).unwrap(), -1123456789);
    }
}

/// Numeric factories keep their fixed input unit, independently of output unit.
#[derive(Clone, Copy)]
enum Numeric {
    Seconds,
    Micros,
    Timestamp,
    LocalTimestamp,
}
impl Numeric {
    fn parse(value: &str) -> PyResult<Self> {
        match value {
            "seconds" => Ok(Self::Seconds),
            "us" => Ok(Self::Micros),
            "timestamp" => Ok(Self::Timestamp),
            "local_timestamp" => Ok(Self::LocalTimestamp),
            _ => Err(crate::error_context::runtime("unknown numeric factory")),
        }
    }
    fn instant(self) -> bool {
        matches!(self, Self::Timestamp)
    }
}

fn number_missing(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    if super::prepare::missing(value) {
        return Ok(true);
    }
    if let Ok(text) = value.cast::<pyo3::types::PyString>() {
        return super::prepare::missing_text(text);
    }
    if let Some((ticks, code, _)) = crate::numpy_scalar::datetime_ticks(value)? {
        super::prepare::scalar_unit(code)?;
        return Ok(ticks == i64::MIN);
    }
    Ok(false)
}

fn read_number(value: &Bound<'_, PyAny>, kind: Numeric) -> PyResult<Option<i128>> {
    if number_missing(value)? {
        return Ok(None);
    }
    if crate::numeric::is_bool(value) {
        return Err(crate::error_context::type_error(
            "boolean values are not numeric dates",
        ));
    }
    if matches!(kind, Numeric::Micros) {
        // Real floating NaN is still a date-missing value, not a fractional integer.
        if crate::numeric::supported_float(value) {
            let number = if value.is_instance_of::<pyo3::types::PyFloat>() {
                value.extract::<f64>()?
            } else {
                crate::numeric::float_value(value)?
            };
            if number.is_nan() {
                return Ok(None);
            }
        }
        return crate::numeric::index_i128(value)?
            .checked_mul(1000)
            .map(Some)
            .ok_or_else(|| crate::error_context::overflow("microseconds exceed native range"));
    }
    if unsafe { pyo3::ffi::PyIndex_Check(value.as_ptr()) != 0 } {
        return crate::numeric::index_i128(value)?
            .checked_mul(1_000_000_000)
            .map(Some)
            .ok_or_else(|| crate::error_context::overflow("seconds exceed native range"));
    }
    if value.is_instance_of::<pyo3::types::PyString>()
        || value.is_instance_of::<pyo3::types::PyBytes>()
        || value.is_instance_of::<pyo3::types::PyByteArray>()
    {
        return Err(crate::error_context::type_error(
            "seconds must be numeric, not text or byte strings",
        ));
    }
    // SAFETY: PyNumber_Float reads the original numeric protocol once; unlike
    // Python float(text), it does not add a textual number parser.
    let number = unsafe {
        Bound::from_owned_ptr_or_err(value.py(), pyo3::ffi::PyNumber_Float(value.as_ptr()))
    }
    .map_err(crate::error_context::external)?
    .extract::<f64>()?;
    float_number(number, kind)
}

fn float_number(value: f64, kind: Numeric) -> PyResult<Option<i128>> {
    if value.is_nan() {
        return Ok(None);
    }
    if matches!(kind, Numeric::Micros) {
        return Err(crate::error_context::type_error(
            "microseconds require integer index values, not floats",
        ));
    }
    crate::epoch::float_nanos(value, Unit::Second).map(Some)
}

/// A local timestamp discovers its system zone only upon the first valid value.
struct NumericRows<'a, 'py> {
    rows: super::common::Rows,
    kind: Numeric,
    local: Option<&'a Bound<'py, PyAny>>,
    prepared: Option<(Py<PyAny>, Option<i64>)>,
}
impl<'a, 'py> NumericRows<'a, 'py> {
    fn new(kind: Numeric, local: Option<&'a Bound<'py, PyAny>>) -> Self {
        Self {
            rows: super::common::Rows::new(Unit::Microsecond),
            kind,
            local,
            prepared: None,
        }
    }
    fn push(&mut self, py: Python<'py>, value: Option<i128>) -> PyResult<()> {
        let Some(mut nanos) = value else {
            self.rows.missing();
            return Ok(());
        };
        if matches!(self.kind, Numeric::LocalTimestamp) {
            if self.prepared.is_none() {
                let loader = self.local.ok_or_else(|| {
                    crate::error_context::runtime("local timestamp has no zone loader")
                })?;
                let zone = loader.call0().map_err(crate::error_context::external)?;
                let object = Zone::Object(zone.clone().unbind());
                let offset = super::common::fixed_offset(py, &object)?;
                self.prepared = Some((zone.unbind(), offset));
            }
            let (zone, offset) = self
                .prepared
                .as_ref()
                .ok_or_else(|| crate::error_context::runtime("local zone is unavailable"))?;
            nanos = super::zones::utc_wall(nanos, zone.bind(py), *offset)?;
        }
        let unit = if nanos.rem_euclid(1000) == 0 {
            Unit::Microsecond
        } else {
            Unit::Nanosecond
        };
        self.rows.push(
            py,
            crate::epoch::Parsed {
                nanos,
                unit,
                zone: Zone::Naive,
            },
            self.kind.instant(),
        )
    }
}

fn numeric_scalar(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    if number_missing(value)?
        || value.is_instance_of::<pyo3::types::PyString>()
        || value.is_instance_of::<pyo3::types::PyBytes>()
        || value.is_instance_of::<pyo3::types::PyByteArray>()
    {
        return Ok(true);
    }
    // Actual scalar protocol slots classify without executing a conversion.
    Ok(unsafe {
        pyo3::ffi::PyDate_Check(value.as_ptr()) != 0
            || pyo3::ffi::PyIndex_Check(value.as_ptr()) != 0
            || !pyo3::ffi::PyType_GetSlot(
                pyo3::ffi::Py_TYPE(value.as_ptr()),
                pyo3::ffi::Py_nb_float,
            )
            .is_null()
    })
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared numeric factory boundary"
)]
#[pyo3(signature=(data,policy,kind,size=None,column=false,unit=None,target=None,local=None,entry="Pddt",parameter="data"))]
fn _pddt_numbers<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    policy: PyRef<'_, super::zones::Policies>,
    kind: &str,
    size: Option<usize>,
    column: bool,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    local: Option<&Bound<'py, PyAny>>,
    entry: &str,
    parameter: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let kind = Numeric::parse(kind)?;
    let requested = unit.map(Unit::parse).transpose()?;
    let mut output = NumericRows::new(kind, local);
    if !column && numeric_scalar(data)? {
        let count = size.ok_or_else(|| {
            crate::error_context::value_error(
                "a scalar factory input requires size; use [value] for one date",
            )
        })?;
        let value = read_number(data, kind)
            .map_err(|e| crate::error_context::argument(py, e, entry, parameter, data))?;
        // Normalize a scalar once, including its possible local-zone protocol.
        output.rows.reserve(count)?;
        if count != 0 {
            output.push(py, value)?;
            let first = output.rows.values[0];
            let source = output.rows.sources[0];
            output.rows.values.resize(count, first);
            output.rows.sources.resize(count, source);
        }
    } else {
        if size.is_some() {
            return Err(crate::error_context::value_error(
                "size must be omitted for a collection input",
            ));
        }
        let iter = data.try_iter().map_err(crate::error_context::external)?;
        for (i, value) in iter.enumerate() {
            let value = value
                .map_err(crate::error_context::external)
                .map_err(|e| crate::error_context::item(py, e, entry, parameter, i, None, true))?;
            let number = read_number(&value, kind).map_err(|e| {
                crate::error_context::item(py, e, entry, parameter, i, Some(&value), false)
            })?;
            output.push(py, number)?;
        }
    }
    super::common::finish(py, output.rows, requested, target, entry, &policy)
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Homogeneous numeric buffer and ownership metadata"
)]
#[pyo3(signature=(data,storage,mask,policy,kind,unit=None,target=None,local=None,entry="Pddt"))]
fn _pddt_number_buffer<'py>(
    py: Python<'py>,
    data: &[u8],
    storage: &str,
    mask: Option<&[u8]>,
    policy: PyRef<'_, super::zones::Policies>,
    kind: &str,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    local: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    if data.len() % 8 != 0 || mask.is_some_and(|m| m.len() != data.len() / 8) {
        return Err(crate::error_context::value_error(
            "invalid numeric buffer or missing mask",
        ));
    }
    let kind = Numeric::parse(kind)?;
    let requested = unit.map(Unit::parse).transpose()?;
    let mut output = NumericRows::new(kind, local);
    let mut raw = [0; 8];
    for (index, bytes) in data.chunks_exact(8).enumerate() {
        if mask.is_some_and(|m| m[index] != 0) {
            output.push(py, None)?;
            continue;
        }
        raw.copy_from_slice(bytes);
        let value = match storage {
            "i" => i128::from(i64::from_ne_bytes(raw)),
            "u" => i128::from(u64::from_ne_bytes(raw)),
            "f" => {
                output.push(py, float_number(f64::from_ne_bytes(raw), kind)?)?;
                continue;
            }
            _ => return Err(crate::error_context::runtime("unknown numeric buffer type")),
        };
        let scale = if matches!(kind, Numeric::Micros) {
            1000
        } else {
            1_000_000_000
        };
        let nanos = value.checked_mul(scale).ok_or_else(|| {
            crate::error_context::overflow("numeric factory value exceeds native range")
        })?;
        output.push(py, Some(nanos))?;
    }
    super::common::finish(py, output.rows, requested, target, entry, &policy)
}
