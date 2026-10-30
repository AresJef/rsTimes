//! One native grammar orchestration for borrowed Python and worker UTF8 views.
use super::fields::{Fields, ParseError, ParseResult, Policy, RuleLookup};
use super::text::{self, CharacterRead};
use super::{resolve, scan};

/// Recognition owns or borrows native tables. The associated region type lets
/// Python retain its existing object while workers carry only native metadata.
pub(super) trait Recognition: RuleLookup {
    type Region: Clone;
    fn flags(&self) -> (bool, bool);
    fn has_regions(&self) -> bool;
    fn region(&self, token: &[u32]) -> Option<Self::Region>;
    fn region_key(region: &Self::Region) -> &str;
}

pub(super) struct Parsed<P: Policy, R> {
    pub(super) fields: Fields<P>,
    pub(super) region: Option<R>,
}

/// Peel only complete trailing registered region names, preserving the shared
/// numeric-offset and strict conflict rules. No Python error is allocated here.
fn suffix<T: CharacterRead, R: Recognition>(
    input: &mut T,
    rules: &R,
    ignore: bool,
    strict: bool,
) -> ParseResult<Option<R::Region>> {
    let mut end = input.len();
    let mut selected = None;
    let mut buffer = [0u32; 64];
    loop {
        let mut last = end;
        while last > 0 && text::space(input.get(last - 1)) {
            last -= 1;
        }
        if last == 0 {
            break;
        }
        let bracket = input.get(last - 1) == 93;
        let key_end = last - usize::from(bracket);
        let mut first = key_end;
        while first > 0 && !text::space(input.get(first - 1)) && input.get(first - 1) != 91 {
            first -= 1;
        }
        if bracket && (first == 0 || input.get(first - 1) != 91) {
            break;
        }
        if first == key_end {
            break;
        }
        let region_form = bracket
            || (text::ascii_letter(input.get(first))
                && (first..key_end.saturating_sub(1))
                    .any(|i| input.get(i) == 47 && text::ascii_letter(input.get(i + 1))));
        if !region_form && !rules.has_regions() {
            break;
        }
        let owned;
        let name = if key_end - first <= buffer.len() {
            let name = &mut buffer[..key_end - first];
            for (offset, slot) in name.iter_mut().enumerate() {
                *slot = input.get(first + offset);
            }
            &*name
        } else {
            owned = input.range(first, key_end);
            &owned
        };
        let registered = rules.region(name);
        if registered.is_none() && !region_form {
            break;
        }
        if !ignore {
            let zone = registered.ok_or_else(|| ParseError::UnknownRegion(name.to_vec()))?;
            if let Some(previous) = &selected {
                if strict && R::region_key(previous) != R::region_key(&zone) {
                    return Err(ParseError::ConflictingRegions(
                        R::region_key(&zone).into(),
                        R::region_key(previous).into(),
                    ));
                }
            } else {
                selected = Some(zone);
            }
        }
        end = first - usize::from(bracket);
    }
    input.truncate(end);
    Ok(selected)
}

/// Scan, tokenize and resolve once using the caller's static reader and rules.
/// Completion and output capacity are separate, so NoMatch stays distinct from
/// malformed or overflowing fields. Callers control public error construction.
#[inline(always)]
pub(super) fn read<P: Policy, T: CharacterRead, R: Recognition>(
    input: &mut T,
    rules: &mut R,
    default: Option<[i32; 3]>,
    yearfirst: Option<bool>,
    dayfirst: Option<bool>,
    ignoretz: bool,
    isoformat: bool,
) -> ParseResult<Option<Parsed<P, R::Region>>> {
    let mut fields = Fields::<P>::new();
    let mut region = None;
    let (start, _) = scan::prefix(input, &mut fields, ignoretz, isoformat)?;
    if start != input.len() {
        if P::ISO_ONLY {
            return Err(ParseError::Value(
                "expected a complete ISO date/time string".into(),
            ));
        }
        let configured = rules.has_regions();
        let mut tokens = if configured {
            None
        } else {
            Some(text::tokenize(input, start))
        };
        if configured || tokens.as_ref().is_some_and(|value| value.region_candidate) {
            region = suffix(input, rules, ignoretz, fields.strict())?;
            tokens = Some(text::tokenize(input, start));
        }
        let tokens =
            tokens.ok_or_else(|| ParseError::Assertion("missing parser token view".into()))?;
        scan::process_tokens(
            &tokens,
            &mut fields,
            rules,
            ignoretz || region.is_some(),
            default.map(|date| date[0]),
        )?;
    }
    let (configured_year, configured_day) = if yearfirst.is_none() || dayfirst.is_none() {
        rules.flags()
    } else {
        (true, false)
    };
    let reference = if fields.idx >= 0 && !fields.century_specified && !fields.strict() {
        default.map(|date| date[0])
    } else {
        None
    };
    let resolved = fields.resolved
        || resolve::resolve(
            &mut fields,
            yearfirst.unwrap_or(configured_year),
            dayfirst.unwrap_or(configured_day),
            reference,
        )?;
    Ok(resolved.then_some(Parsed { fields, region }))
}
