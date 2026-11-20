//! Actual date roles and scalar/column calendar factories before final wrapping.
use super::common::{NS_DAY, Rows, finish};
use crate::epoch::{self, Parsed, Unit, Zone};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

struct NumpyDate {
    ticks: i64,
    code: i32,
    multiplier: i32,
    unit: Unit,
}

impl NumpyDate {
    fn read(value: &Bound<'_, PyAny>) -> PyResult<Option<Self>> {
        let Some((ticks, code, multiplier)) = crate::numpy_scalar::datetime_ticks(value)? else {
            return Ok(None);
        };
        let unit = crate::date_input::scalar_unit(code)?;
        Ok(Some(Self {
            ticks,
            code,
            multiplier,
            unit,
        }))
    }
}

fn role(
    value: &Bound<'_, PyAny>,
    kind: &str,
    replace: bool,
    rows: &mut Rows,
    numpy: Option<NumpyDate>,
) -> PyResult<Option<(Parsed, bool)>> {
    if kind == "iso" {
        if !value.is_instance_of::<pyo3::types::PyString>()
            && super::arguments::date_missing(value)?
        {
            return Ok(None);
        }
        let text = value.cast::<pyo3::types::PyString>().map_err(|_| {
            crate::error_context::type_error("fromisoformat requires ISO text values")
        })?;
        let view = crate::parser::text::TextView::new(text);
        if view.len() <= 3 && crate::date_input::missing_text(text)? {
            return Ok(None);
        }
        return crate::parser::iso_factory::read(&view).map(|p| Some((p, false)));
    }
    if kind == "numpy" {
        let source = if let Some(source) = numpy {
            source
        } else {
            match crate::date_input::non_numpy_date_missing(value)? {
                Some(true) => return Ok(None),
                Some(false) => None,
                None => NumpyDate::read(value)?,
            }
            .ok_or_else(|| {
                crate::error_context::type_error(
                    "requires a NumPy datetime64 value; use fromdatetime for Python datetime",
                )
            })?
        };
        if source.ticks == i64::MIN {
            rows.unit = rows.unit.max(source.unit);
            return Ok(None);
        }
        return epoch::native_datetime_ticks(source.ticks, source.code, source.multiplier)
            .map(|value| Some((value, false)));
    }
    crate::date_input::named_date(
        value,
        match kind {
            "date" => crate::date_input::DateSource::Date,
            _ => crate::date_input::DateSource::Datetime,
        },
        replace,
    )
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Once-prepared actual date factory boundary"
)]
#[pyo3(signature=(data,policy,kind,size=None,column=false,unit=None,target=None,entry="Pddt"))]
fn _pddt_date_objects<'py>(
    py: Python<'py>,
    data: &Bound<'py, PyAny>,
    policy: PyRef<'_, super::zones::Policies>,
    kind: &str,
    size: Option<usize>,
    column: bool,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let requested = unit.map(Unit::parse).transpose()?;
    let mut rows = Rows::new(Unit::Second);
    let replace = target.is_some_and(|t| !t.is_none());
    let parameter = match kind {
        "iso" => "dtstr",
        "numpy" => "dt64",
        _ => "dt",
    };
    let (numpy, missing) = if column {
        (None, false)
    } else if kind == "numpy" {
        match crate::date_input::non_numpy_date_missing(data)? {
            Some(missing) => (None, missing),
            None => (NumpyDate::read(data)?, false),
        }
    } else {
        (None, super::arguments::date_missing(data)?)
    };
    let scalar = !column
        && (missing
            || numpy.is_some()
            || data.is_instance_of::<pyo3::types::PyString>()
            || unsafe {
                ffi::PyDate_Check(data.as_ptr()) != 0 || ffi::PyIndex_Check(data.as_ptr()) != 0
            }
            || crate::numeric::supported_float(data)
            || data.is_instance_of::<pyo3::types::PyBytes>()
            || data.is_instance_of::<pyo3::types::PyByteArray>()
            || kind != "numpy" && crate::numpy_scalar::datetime_ticks(data)?.is_some());
    if scalar {
        let count = size.ok_or_else(|| {
            crate::error_context::value_error("a scalar factory input requires size")
        })?;
        let parsed = role(data, kind, replace, &mut rows, numpy)
            .map_err(|e| crate::error_context::argument(py, e, entry, parameter, data))?;
        rows.reserve(count)?;
        if let Some((parsed, instant)) = parsed {
            rows.push(py, parsed, instant)?;
        } else {
            rows.missing();
        }
        rows.empty_zone = rows.sources[0].zone;
        rows.values.resize(count, rows.values[0]);
        rows.sources.resize(count, rows.sources[0]);
    } else {
        if size.is_some() {
            return Err(crate::error_context::value_error(
                "omit size for a collection",
            ));
        }
        for (i, item) in data
            .try_iter()
            .map_err(crate::error_context::external)?
            .enumerate()
        {
            let item = item
                .map_err(crate::error_context::external)
                .map_err(|e| crate::error_context::item(py, e, entry, parameter, i, None, true))?;
            if let Some((parsed, instant)) =
                role(&item, kind, replace, &mut rows, None).map_err(|e| {
                    crate::error_context::item(py, e, entry, parameter, i, Some(&item), false)
                })?
            {
                rows.push(py, parsed, instant)?;
            } else {
                rows.missing();
            }
        }
    }
    finish(py, rows, requested, target, entry, &policy)
}

pub(super) fn numpy_code(source: &str) -> PyResult<i32> {
    match source {
        "Y" => Ok(0),
        "M" => Ok(1),
        "W" => Ok(2),
        "D" => Ok(4),
        "h" => Ok(5),
        "m" => Ok(6),
        "s" => Ok(7),
        "ms" => Ok(8),
        "us" => Ok(9),
        "ns" => Ok(10),
        _ => Err(crate::error_context::value_error(
            "unsupported NumPy datetime unit; use years through nanoseconds",
        )),
    }
}

#[pyfunction]
#[expect(clippy::too_many_arguments, reason = "Native temporal column metadata")]
#[pyo3(signature=(data,policy,kind,source,multiplier=1,unit=None,source_zone=None,target=None,entry="Pddt",mask=None))]
fn _pddt_date_buffer<'py>(
    py: Python<'py>,
    data: &[u8],
    policy: PyRef<'_, super::zones::Policies>,
    kind: &str,
    source: &str,
    multiplier: i32,
    unit: Option<&str>,
    source_zone: Option<&Bound<'py, PyAny>>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
    mask: Option<&[u8]>,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    if !data.len().is_multiple_of(8) || multiplier < 1 {
        return Err(crate::error_context::runtime(
            "invalid native date metadata",
        ));
    }
    let code = numpy_code(source)?;
    let mut rows = Rows::new(super::prepare::scalar_unit(code)?);
    rows.reserve(data.len() / 8)?;
    let validity = super::validity::TemporalValidity::new(mask, data.len() / 8)?;
    let requested = unit.map(Unit::parse).transpose()?;
    let source_zone = source_zone.filter(|t| !t.is_none());
    let fixed = if let Some(zone) = source_zone {
        super::common::fixed_offset(py, &Zone::Object(zone.clone().unbind()))?
    } else {
        Some(0)
    };
    let replace = target.is_some_and(|t| !t.is_none());
    for (i, bytes) in data.as_chunks::<8>().0.iter().enumerate() {
        let raw: [u8; 8] = *bytes;
        let ticks = i64::from_ne_bytes(raw);
        if validity.missing(i, ticks) {
            rows.missing();
            continue;
        }
        let row = (|| -> PyResult<(Parsed, bool)> {
            let mut parsed = epoch::native_datetime_ticks(ticks, code, multiplier)?;
            let mut instant = false;
            if let Some(zone) = source_zone {
                if kind == "date" || replace {
                    parsed.nanos = super::zones::utc_wall(parsed.nanos, zone, fixed)?;
                } else {
                    parsed.zone = Zone::Object(zone.clone().unbind());
                    instant = true;
                }
            }
            if kind == "date" {
                parsed.nanos = parsed.nanos.div_euclid(NS_DAY) * NS_DAY;
                parsed.zone = Zone::Naive;
                instant = false;
            }
            Ok((parsed, instant))
        })()
        .map_err(|e| crate::error_context::location(py, e, entry, &format!("data[{i}]")))?;
        rows.push(py, row.0, row.1)?;
    }
    let output = if kind == "datetime" && !replace {
        source_zone
    } else {
        target
    };
    finish(py, rows, requested, output, entry, &policy)
}

#[pyfunction]
#[expect(
    clippy::too_many_arguments,
    reason = "Prepared calendar component columns"
)]
#[pyo3(signature=(first,policy,kind,second=None,third=None,size=None,unit=None,target=None,entry="Pddt"))]
fn _pddt_calendar<'py>(
    py: Python<'py>,
    first: PyRef<'_, super::arguments::Integers>,
    policy: PyRef<'_, super::zones::Policies>,
    kind: &str,
    second: Option<PyRef<'_, super::arguments::Integers>>,
    third: Option<PyRef<'_, super::arguments::Integers>>,
    size: Option<usize>,
    unit: Option<&str>,
    target: Option<&Bound<'py, PyAny>>,
    entry: &str,
) -> PyResult<(Bound<'py, PyBytes>, &'static str, Py<PyAny>)> {
    let length = super::arguments::length(
        [
            first.0.len(),
            second.as_ref().and_then(|c| c.0.len()),
            third.as_ref().and_then(|c| c.0.len()),
        ],
        size,
    )?;
    let mut rows = Rows::new(Unit::Microsecond);
    rows.reserve(length)?;
    let requested = unit.map(Unit::parse).transpose()?;
    for (component, label) in [
        (
            second.as_ref(),
            if kind == "doy" { "doy" } else { "ISO week" },
        ),
        (third.as_ref(), "ISO weekday"),
    ] {
        if let Some(component) = component {
            let values = match &component.0 {
                super::arguments::Column::Scalar(v) => std::slice::from_ref(v),
                super::arguments::Column::Values(v) => v.as_slice(),
            };
            if values.iter().flatten().any(|v| *v < 1) {
                return Err(crate::error_context::location(
                    py,
                    crate::error_context::value_error(format!("{label} must be at least 1")),
                    entry,
                    label,
                ));
            }
        }
    }
    for i in 0..length {
        let Some(a) = first.0.get(i) else {
            rows.missing();
            continue;
        };
        let b = second.as_ref().map_or(Some(1), |c| c.0.get(i));
        let c = third.as_ref().map_or(Some(1), |c| c.0.get(i));
        let (Some(b), Some(c)) = (b, c) else {
            rows.missing();
            continue;
        };
        let ordinal = match kind {
            "ordinal" => Ok(a),
            "doy" => {
                crate::calendar::year_day_ordinal(a, b).map_err(crate::error_context::overflow)
            }
            "iso" => crate::calendar::iso_ordinal(a, b, c).map_err(crate::error_context::overflow),
            _ => Err(crate::error_context::runtime("unknown calendar factory")),
        }
        .map_err(|e| crate::error_context::location(py, e, entry, &format!("data[{i}]")))?;
        rows.push(
            py,
            Parsed {
                nanos: (i128::from(ordinal) - 719_163) * NS_DAY,
                unit: Unit::Microsecond,
                zone: Zone::Naive,
            },
            false,
        )?;
    }
    finish(py, rows, requested, target, entry, &policy)
}

pub(super) fn configure(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(_pddt_date_objects, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_date_buffer, module)?)?;
    module.add_function(wrap_pyfunction!(_pddt_calendar, module)?)
}
