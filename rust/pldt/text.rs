//! Native String adapter for the shared Parser. Worker rows never visit Python.
use crate::parser::config::NativeRules;
use crate::parser::fields::{Lenient, Nano, Policy, Precision, Strict};
use crate::parser::native;
use crate::parser::prepared::TextData;
use polars::prelude::*;
use pyo3_polars::derive::polars_expr;
use serde::Deserialize;

#[derive(Clone, Copy, Deserialize)]
#[serde(rename_all = "lowercase")]
enum Resolution {
    Ms,
    Us,
    Ns,
}
impl Resolution {
    fn unit(self) -> TimeUnit {
        match self {
            Self::Ms => TimeUnit::Milliseconds,
            Self::Us => TimeUnit::Microseconds,
            Self::Ns => TimeUnit::Nanoseconds,
        }
    }
    fn tick(self) -> i128 {
        match self {
            Self::Ms => 1_000_000,
            Self::Us => 1_000,
            Self::Ns => 1,
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    version: u8,
    unit: Resolution,
    prepared: TextData,
}

fn validate(options: &Options) -> PolarsResult<()> {
    polars_ensure!(options.version==1,InvalidOperation:"unsupported rstimes text preparation version");
    if let Some([year, month, day]) = options.prepared.options.default {
        polars_ensure!((1..=12).contains(&month) && (1..=crate::calendar::days_in_month(i64::from(year),i64::from(month))).contains(&i64::from(day)),InvalidOperation:"Pldt.parse: invalid prepared default date");
    }
    Ok(())
}

fn output_field(fields: &[Field], options: Options) -> PolarsResult<Field> {
    validate(&options)?;
    polars_ensure!(fields.len()==1,InvalidOperation:"Pldt.parse requires one String source");
    polars_ensure!(fields[0].dtype()==&DataType::String,InvalidOperation:"Pldt.parse requires String input");
    Ok(Field::new(
        fields[0].name().clone(),
        DataType::Datetime(options.unit.unit(), None),
    ))
}

/// Exact approved missing strings; no strip, lowercase allocation or coercion.
pub(super) fn missing(value: &str) -> bool {
    matches!(value, "" | "NaT" | "NAT" | "nat" | "NaN" | "NAN" | "nan")
}

fn row_error(row: usize, input: &str, error: impl std::fmt::Display) -> PolarsError {
    let preview: String = input.chars().take(120).collect();
    polars_err!(ComputeError:"Pldt.parse: row {}, input {:?}: {}",row,preview,error)
}

fn rows<P: Policy>(
    source: &Series,
    options: &Options,
    mut rules: NativeRules,
) -> PolarsResult<Series> {
    let values = source.str()?;
    let mut output = PrimitiveChunkedBuilder::<Int64Type>::new(source.name().clone(), source.len());
    let mut scratch = Vec::new();
    for (row, value) in values.iter().enumerate() {
        let Some(value) = value.filter(|value| !missing(value)) else {
            output.append_null();
            continue;
        };
        let parsed = native::parse::<P>(value, &mut scratch, &mut rules, options.prepared.options)
            .map_err(|error| row_error(row, value, error))?;
        if parsed
            .region
            .as_ref()
            .is_some_and(|region| !region.available)
        {
            return Err(row_error(
                row,
                value,
                "the registered region is unavailable; restore timezone data and prepare the expression again",
            ));
        }
        // W12 supplies the region service and W13 adds the explicit target.
        // This already valid naive schema must never silently discard a zone.
        if parsed.region.is_some() || parsed.fields.is_tzoffset_set() {
            return Err(row_error(
                row,
                value,
                "timezone-aware text requires an explicit output tz; regional text execution is not installed yet",
            ));
        }
        let [year, month, day, hour, minute, second, microsecond] = parsed.completed;
        let ordinal =
            crate::calendar::checked_ordinal(i64::from(year), i64::from(month), i64::from(day))
                .map_err(|error| row_error(row, value, error))?;
        let nanos = (i128::from(ordinal) - 719_163) * 86_400_000_000_000
            + ((i128::from(hour) * 60 + i128::from(minute)) * 60 + i128::from(second))
                * 1_000_000_000
            + i128::from(microsecond) * 1000
            + i128::from(parsed.fields.fraction.tail());
        let tick = options.unit.tick();
        if nanos.rem_euclid(tick) != 0 {
            return Err(row_error(
                row,
                value,
                "source precision cannot fit the selected unit without loss; choose a finer unit",
            ));
        }
        let value = i64::try_from(nanos / tick).map_err(|_| {
            row_error(
                row,
                value,
                "date exceeds the selected unit capacity; choose a coarser unit",
            )
        })?;
        output.append_value(value);
    }
    Ok(output
        .finish()
        .into_datetime(options.unit.unit(), None)
        .into_series())
}

#[polars_expr(output_type_func_with_kwargs=output_field)]
fn pldt_parse(inputs: &[Series], mut kwargs: Options) -> PolarsResult<Series> {
    validate(&kwargs)?;
    polars_ensure!(inputs.len()==1,InvalidOperation:"Pldt.parse requires one String source");
    let rules = match kwargs.prepared.rules.take() {
        Some(data) => NativeRules::from_data(data)
            .map_err(|error| polars_err!(ComputeError:"Pldt.parse: {}",error))?,
        None => NativeRules::library(),
    };
    if kwargs.prepared.strict {
        rows::<Nano<Strict>>(&inputs[0], &kwargs, rules)
    } else {
        rows::<Nano<Lenient>>(&inputs[0], &kwargs, rules)
    }
}
