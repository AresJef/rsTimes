//! Python-free text parsing entry used by native column and expression adapters.
use super::config::{NativeRegion, NativeRules};
use super::fields::{Fields, ParseError, ParseResult, Policy};
use super::text::Utf8View;
use super::{completion, core};
use std::sync::Arc;

/// One native invocation/worker owns its reusable character and token storage.
/// Neither vector retains an input borrow or any Python object between rows.
#[derive(Default)]
pub(crate) struct Scratch {
    pub(super) points: Vec<u32>,
    pub(super) tokens: super::text::Tokens,
}
impl Scratch {
    /// Share the character arena with adjacent native format/key recognition.
    pub(crate) fn codepoints(&mut self) -> &mut Vec<u32> {
        &mut self.points
    }
}

/// Prepared scalar options. Default has already been independently resolved;
/// no Python source or callable is retained in this native context.
#[derive(Clone, Copy, Debug, serde::Serialize, serde::Deserialize, pyo3::IntoPyObject)]
pub(crate) struct Options {
    pub(crate) default: Option<[i32; 3]>,
    pub(crate) yearfirst: Option<bool>,
    pub(crate) dayfirst: Option<bool>,
    pub(crate) isoformat: bool,
}

pub(crate) struct Parsed<P: Policy> {
    pub(crate) fields: Fields<P>,
    pub(crate) region: Option<Arc<NativeRegion>>,
    pub(crate) completed: [i32; 7],
}

/// Parse one valid UTF8 row through the exact same scanner and completion as
/// scalar Python strings. Native errors remain native until the caller's exit.
pub(crate) fn parse<P: Policy>(
    input: &str,
    scratch: &mut Scratch,
    rules: &mut NativeRules,
    options: Options,
) -> ParseResult<Parsed<P>> {
    let mut view = Utf8View::new(input, &mut scratch.points);
    let parsed = core::read::<P, _, _>(
        &mut view,
        rules,
        options.default,
        options.yearfirst,
        options.dayfirst,
        false,
        options.isoformat,
        Some(&mut scratch.tokens),
    )?
    .ok_or_else(|| {
        ParseError::Value(
            "no date/time fields could be read; provide a recognizable date or time".into(),
        )
    })?;
    let completed = completion::complete(&parsed.fields, options.default)?;
    Ok(Parsed {
        fields: parsed.fields,
        region: parsed.region,
        completed,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::fields::{Lenient, Nano, Precision, Strict};

    const OPTIONS: Options = Options {
        default: None,
        yearfirst: None,
        dayfirst: None,
        isoformat: true,
    };

    #[test]
    fn utf8_shared_grammar_preserves_full_ns_and_library_vocabulary_without_python() {
        fn assert_send_sync<T: Send + Sync>() {}
        assert_send_sync::<NativeRules>();
        let mut rules = NativeRules::library();
        let mut scratch = Scratch::default();
        for (input, want, tail) in [
            (
                "2024-01-02 12:34:56.123456789",
                [2024, 1, 2, 12, 34, 56, 123456],
                789,
            ),
            ("14 February 2024", [2024, 2, 14, 0, 0, 0, 0], 0),
            ("14 février 2024", [2024, 2, 14, 0, 0, 0, 0], 0),
            ("14 haziran 2024", [2024, 6, 14, 0, 0, 0, 0], 0),
            ("0000-01-01", [0, 1, 1, 0, 0, 0, 0], 0),
        ] {
            let result = parse::<Nano<Lenient>>(input, &mut scratch, &mut rules, OPTIONS).unwrap();
            assert_eq!(result.completed, want, "{input}");
            assert_eq!(result.fields.fraction.tail(), tail);
            assert!(result.region.is_none());
        }
    }

    #[test]
    fn utf8_shared_grammar_keeps_iso_fallback_strict_and_default_roles() {
        let mut rules = NativeRules::library();
        let mut scratch = Scratch::default();
        let options = Options {
            default: Some([2024, 1, 31]),
            ..OPTIONS
        };
        assert_eq!(
            parse::<Lenient>("February", &mut scratch, &mut rules, options)
                .unwrap()
                .completed,
            [2024, 2, 29, 0, 0, 0, 0]
        );
        assert!(matches!(
            parse::<Strict>("2024-02-30", &mut scratch, &mut rules, OPTIONS),
            Err(ParseError::Value(_))
        ));
        assert!(matches!(
            parse::<Lenient>(
                "2024-01-01 Asia/Shanghai",
                &mut scratch,
                &mut rules,
                OPTIONS
            ),
            Err(ParseError::UnknownRegion(_))
        ));
        let generic = Options {
            isoformat: false,
            ..OPTIONS
        };
        assert_eq!(
            parse::<Lenient>("0000-01-01", &mut scratch, &mut rules, generic)
                .unwrap()
                .completed[0],
            0
        );
    }
    #[test]
    fn shared_grammar_success_and_failure_run_on_an_unattached_native_thread() {
        std::thread::spawn(|| {
            let mut rules = NativeRules::library();
            let mut scratch = Scratch::default();
            let result = parse::<Nano<Lenient>>(
                "14 février 2024 12:34:56.123456789",
                &mut scratch,
                &mut rules,
                OPTIONS,
            )
            .unwrap();
            assert_eq!(result.completed, [2024, 2, 14, 12, 34, 56, 123456]);
            assert_eq!(result.fields.fraction.tail(), 789);
            assert!(parse::<Strict>("2024-02-30", &mut scratch, &mut rules, OPTIONS).is_err());
        })
        .join()
        .unwrap();
    }

    #[test]
    fn compact_rule_data_preserves_defaults_overrides_empty_tables_and_version_without_python() {
        std::thread::spawn(|| {
            let library = NativeRules::library().data();
            assert_eq!(library.version, 2);
            assert!(library.tables.iter().all(Option::is_none));
            let mut scratch = Scratch::default();
            let mut data = library.clone();
            data.flags = (false, true);
            let mut rules = NativeRules::from_data(data).unwrap();
            assert_eq!(
                parse::<Nano<Lenient>>("01/02/2024", &mut scratch, &mut rules, OPTIONS)
                    .unwrap()
                    .completed,
                [2024, 2, 1, 0, 0, 0, 0]
            );
            assert!(rules.data().tables.iter().all(Option::is_none));

            let mut custom = library.clone();
            custom.tables[4] = Some(vec![("Harvest".chars().map(u32::from).collect(), 10)]);
            let mut rules = NativeRules::from_data(custom).unwrap();
            assert_eq!(
                parse::<Nano<Lenient>>("14 Harvest 2024", &mut scratch, &mut rules, OPTIONS)
                    .unwrap()
                    .completed,
                [2024, 10, 14, 0, 0, 0, 0]
            );
            let mut empty = library.clone();
            empty.tables[4] = Some(Vec::new());
            let mut rules = NativeRules::from_data(empty).unwrap();
            assert!(rules.data().tables[4].as_ref().unwrap().is_empty());
            assert!(
                parse::<Nano<Lenient>>("14 Jan 2024", &mut scratch, &mut rules, OPTIONS).is_err()
            );

            let mut unknown = library;
            unknown.version = 77;
            assert!(matches!(
                NativeRules::from_data(unknown),
                Err(ParseError::Value(_))
            ));
        })
        .join()
        .unwrap();
    }

    #[test]
    fn reused_lexical_storage_drops_previous_tokens_regions_and_failed_row_state() {
        let mut data = NativeRules::library().data();
        data.regions.push((
            "UTC".chars().map(u32::from).collect(),
            NativeRegion {
                key: "UTC".into(),
                available: true,
                fixed_offset_us: Some(0),
            },
        ));
        let mut rules = NativeRules::from_data(data).unwrap();
        let mut scratch = Scratch::default();
        let long = format!("14 février 2024{}UTC", " ".repeat(4096));
        for (text, date, region) in [
            (long.as_str(), [2024, 2, 14], Some("UTC")),
            ("2024-01-02T12:34:56.123456789", [2024, 1, 2], None),
            ("7 May 2024", [2024, 5, 7], None),
            ("14 January 2024 [UTC]", [2024, 1, 14], Some("UTC")),
            ("15 March 2024", [2024, 3, 15], None),
        ] {
            let result = parse::<Nano<Lenient>>(text, &mut scratch, &mut rules, OPTIONS).unwrap();
            assert_eq!(result.completed[..3], date, "{text}");
            assert_eq!(result.region.as_ref().map(|zone| zone.key.as_str()), region);
        }
        assert!(parse::<Nano<Strict>>("2024-02-30", &mut scratch, &mut rules, OPTIONS).is_err());
        assert!(
            parse::<Nano<Lenient>>(
                "2024-01-02 [Missing/Zone]",
                &mut scratch,
                &mut rules,
                OPTIONS
            )
            .is_err()
        );
        let result =
            parse::<Nano<Lenient>>("15 March 2024", &mut scratch, &mut rules, OPTIONS).unwrap();
        assert_eq!(result.completed, [2024, 3, 15, 0, 0, 0, 0]);
        assert!(result.region.is_none());
    }
}
