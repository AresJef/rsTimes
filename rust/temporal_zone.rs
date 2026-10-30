//! Immutable native TZif rules and integer local/UTC candidate calculations.
//!
//! Named data comes from the pinned native IANA snapshot; host adapters may
//! also provide an owned rule snapshot. No Python object, system lookup,
//! current-time query or implicit interpreter attachment occurs here.
use jiff::{
    Timestamp,
    civil::DateTime,
    tz::{AmbiguousOffset, TimeZone},
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, OnceLock, RwLock};

const NS_SECOND: i128 = 1_000_000_000;
const NS_DAY: i128 = 86_400_000_000_000;

/// Portable rule values, owned by an expression or eager preparation.
#[derive(Clone, Deserialize, Serialize, pyo3::IntoPyObject)]
#[serde(deny_unknown_fields)]
pub(crate) struct ZoneData {
    pub(crate) key: String,
    #[serde(deserialize_with = "crate::serde_values::byte_vector")]
    pub(crate) data: Vec<u8>,
    pub(crate) fixed_seconds: Option<i32>,
}

/// Real target-capacity and local-data failures remain distinct at exits.
#[derive(Clone, Copy, Debug)]
pub(crate) enum ZoneError {
    Type(&'static str),
    Capacity(&'static str),
    Value(&'static str),
}
impl std::fmt::Display for ZoneError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Capacity(message) | Self::Value(message) | Self::Type(message) => {
                f.write_str(message)
            }
        }
    }
}

/// Native candidates, ordered by actual UTC time, never by a DST boolean.
#[derive(Clone, Copy, Debug)]
pub(crate) enum Candidates {
    One(i128),
    Repeated(i128, i128),
    Gap { before: i32, after: i32 },
}

/// The fixed variant never calls the regional backend.
#[derive(Clone)]
enum Rules {
    Fixed(i32),
    Region(TimeZone),
}

/// Cheap immutable rule handle with its explicit portable snapshot.
#[derive(Clone)]
pub(crate) struct Zone {
    key: Arc<str>,
    data: Arc<[u8]>,
    rules: Rules,
}

// Only canonical keys from the finite immutable database can enter this cache.
static NAMED: OnceLock<RwLock<HashMap<&'static str, Zone>>> = OnceLock::new();

fn timestamp(value: i128) -> Result<Timestamp, ZoneError> {
    let seconds = i64::try_from(value.div_euclid(NS_SECOND))
        .map_err(|_| ZoneError::Capacity("regional timestamp exceeds signed64 seconds"))?;
    let nanos = value.rem_euclid(NS_SECOND) as i32;
    // The pinned core's from_nanosecond omits its documented civil range.
    // Use the primary checked constructor rather than catching a later panic.
    Timestamp::new(seconds,nanos).map_err(|_|ZoneError::Capacity(
        "regional timestamp exceeds the native timezone backend range; naive, UTC and fixed offsets retain the full selected unit range"))
}

fn civil(wall: i128) -> Result<DateTime, ZoneError> {
    let ordinal = wall
        .div_euclid(NS_DAY)
        .checked_add(719_163)
        .and_then(|value| i64::try_from(value).ok())
        .ok_or(ZoneError::Capacity("regional date overflow"))?;
    let [year, month, day] = crate::calendar::from_ordinal(ordinal).map_err(ZoneError::Capacity)?;
    let year=i16::try_from(year).map_err(|_|ZoneError::Capacity("regional timezone backend supports civil years -9999 through 9999; naive, UTC and fixed offsets retain the full unit range"))?;
    let clock = wall.rem_euclid(NS_DAY);
    DateTime::new(
        year,
        month as i8,
        day as i8,
        (clock / 3_600_000_000_000) as i8,
        (clock / 60_000_000_000 % 60) as i8,
        (clock / NS_SECOND % 60) as i8,
        (clock % NS_SECOND) as i32,
    )
    .map_err(|_| {
        ZoneError::Capacity("regional timezone backend supports civil years -9999 through 9999")
    })
}

impl Zone {
    /// Resolve an actual encoded schema name wholly in native code.
    pub(crate) fn named(key: &str) -> Result<Self, String> {
        let cache = NAMED.get_or_init(|| RwLock::new(HashMap::new()));
        if let Some(value) = cache
            .read()
            .map_err(|_| "native timezone cache is unavailable")?
            .get(key)
        {
            return Ok(value.clone());
        }
        let canonical = tzdb_data::TZ_NAMES
            .iter()
            .copied()
            .find(|value| *value == key)
            .ok_or_else(|| {
                format!(
                    "timezone {key:?} is not present in native TZDB {}",
                    tzdb_data::VERSION
                )
            })?;
        let raw = tzdb_data::find_raw(canonical.as_bytes())
            .ok_or("native timezone data is unavailable")?;
        let fixed = if matches!(
            canonical,
            "UTC"
                | "Etc/UTC"
                | "Etc/GMT"
                | "GMT"
                | "GMT0"
                | "Etc/GMT0"
                | "Etc/GMT+0"
                | "Etc/GMT-0"
                | "Zulu"
                | "Etc/Zulu"
                | "Universal"
                | "Etc/Universal"
                | "Greenwich"
                | "Etc/Greenwich"
        ) {
            Some(0)
        } else if let Some(value) = canonical.strip_prefix("Etc/GMT-") {
            value.parse::<i32>().ok().map(|value| value * 3600)
        } else if let Some(value) = canonical.strip_prefix("Etc/GMT+") {
            value.parse::<i32>().ok().map(|value| -value * 3600)
        } else {
            None
        };
        let rules = match fixed {
            Some(offset) => Rules::Fixed(offset),
            None => Rules::Region(
                TimeZone::tzif(canonical, raw)
                    .map_err(|e| format!("invalid bundled timezone data: {e}"))?,
            ),
        };
        let value = Self {
            key: canonical.into(),
            data: if fixed.is_some() {
                Arc::from([])
            } else {
                raw.into()
            },
            rules,
        };
        let mut write = cache
            .write()
            .map_err(|_| "native timezone cache is unavailable")?;
        Ok(write.entry(canonical).or_insert(value).clone())
    }
    /// Parse an immutable TZif snapshot or validate an explicitly encoded offset.
    pub(crate) fn from_data(value: ZoneData) -> Result<Self, String> {
        if value.key.is_empty()
            || value.key.starts_with('/')
            || value.key.split('/').any(|part| part == ".." || part == ".")
            || value.key.contains('\0')
        {
            return Err("invalid native timezone key".into());
        }
        if value.fixed_seconds.is_none()
            && (value.data.is_empty()
                || tzdb_data::find_raw(value.key.as_bytes()).is_some_and(|raw| raw == value.data))
        {
            return Self::named(&value.key);
        }
        let rules = if let Some(offset) = value.fixed_seconds {
            let expected = if offset == 0 {
                "UTC".into()
            } else {
                if offset % 3600 != 0 || !(-43_200..=50_400).contains(&offset) {
                    return Err("fixed timezone is not representable by a Polars IANA key".into());
                }
                format!(
                    "Etc/GMT{}{hours}",
                    if offset > 0 { "-" } else { "+" },
                    hours = offset.unsigned_abs() / 3600
                )
            };
            if (value.key != expected
                && !(offset == 0
                    && Self::named(&value.key).is_ok_and(|zone| zone.fixed_seconds() == Some(0))))
                || !value.data.is_empty()
            {
                return Err("fixed timezone key and offset disagree".into());
            }
            Rules::Fixed(offset)
        } else {
            Rules::Region(
                TimeZone::tzif(&value.key, &value.data)
                    .map_err(|e| format!("invalid TZif timezone data: {e}"))?,
            )
        };
        Ok(Self {
            key: value.key.into(),
            data: value.data.into(),
            rules,
        })
    }
    /// The real encoded Polars timezone name.
    pub(crate) fn key(&self) -> &str {
        &self.key
    }
    /// Re-export only owned native data; there are no process-global handles.
    pub(crate) fn snapshot(&self) -> ZoneData {
        ZoneData {
            key: self.key.to_string(),
            data: self.data.to_vec(),
            fixed_seconds: match self.rules {
                Rules::Fixed(value) => Some(value),
                Rules::Region(_) => None,
            },
        }
    }
    /// Fixed offset classification without a regional probe.
    pub(crate) fn fixed_seconds(&self) -> Option<i32> {
        match self.rules {
            Rules::Fixed(value) => Some(value),
            Rules::Region(_) => None,
        }
    }
    /// UTC to local coordinates, retaining integer precision.
    pub(crate) fn wall(&self, instant: i128) -> Result<i128, ZoneError> {
        let offset = self.offset_seconds(instant)?;
        instant
            .checked_add(i128::from(offset) * NS_SECOND)
            .ok_or(ZoneError::Capacity("timezone offset arithmetic overflow"))
    }
    pub(crate) fn offset_seconds(&self, instant: i128) -> Result<i32, ZoneError> {
        Ok(match &self.rules {
            Rules::Fixed(value) => *value,
            // TZif transitions have integral-second coordinates. Give the
            // pinned backend the containing real second: its TZif lookup
            // truncates negative fractional timestamps toward zero.
            Rules::Region(zone) => zone
                .to_offset(timestamp(instant.div_euclid(NS_SECOND) * NS_SECOND)?)
                .seconds(),
        })
    }
    pub(crate) fn is_dst(&self, instant: i128) -> Result<bool, ZoneError> {
        Ok(match &self.rules {
            Rules::Fixed(_) => false,
            Rules::Region(zone) => zone
                .to_offset_info(timestamp(instant.div_euclid(NS_SECOND) * NS_SECOND)?)
                .dst()
                .is_dst(),
        })
    }
    /// Resolve only actual local ambiguity; simple offsets never allocate dates.
    pub(crate) fn candidates(&self, wall: i128) -> Result<Candidates, ZoneError> {
        let offset = match &self.rules {
            Rules::Fixed(offset) => {
                return wall
                    .checked_sub(i128::from(*offset) * NS_SECOND)
                    .map(Candidates::One)
                    .ok_or(ZoneError::Capacity("timezone offset arithmetic overflow"));
            }
            Rules::Region(zone) => zone.to_ambiguous_timestamp(civil(wall)?).offset(),
        };
        match offset {
            AmbiguousOffset::Unambiguous { offset } => Ok(Candidates::One(
                wall - i128::from(offset.seconds()) * NS_SECOND,
            )),
            AmbiguousOffset::Fold { before, after } => {
                let first = wall - i128::from(before.seconds()) * NS_SECOND;
                let second = wall - i128::from(after.seconds()) * NS_SECOND;
                Ok(Candidates::Repeated(first.min(second), first.max(second)))
            }
            AmbiguousOffset::Gap { before, after } => Ok(Candidates::Gap {
                before: before.seconds(),
                after: after.seconds(),
            }),
        }
    }
    /// Obtain exact local gap boundaries from the mature transition iterator.
    pub(crate) fn gap_edges(
        &self,
        wall: i128,
        before: i32,
        after: i32,
    ) -> Result<(i128, i128), ZoneError> {
        let Rules::Region(zone) = &self.rules else {
            return Err(ZoneError::Value("fixed timezone has no gap"));
        };
        let left = wall - i128::from(before) * NS_SECOND;
        let right = wall - i128::from(after) * NS_SECOND;
        // TZif transition search uses whole seconds. A negative fractional
        // timestamp truncates toward zero there, potentially skipping the
        // transition immediately after it. Start at a strict earlier integral
        // second; the independently checked local bounds still decide success.
        let seed = left
            .min(right)
            .div_euclid(NS_SECOND)
            .checked_sub(1)
            .and_then(|second| second.checked_mul(NS_SECOND))
            .ok_or(ZoneError::Capacity("gap boundary overflow"))?;
        let transition = zone
            .following(timestamp(seed)?)
            .next()
            .ok_or(ZoneError::Value(
                "timezone cannot confirm the missing-time transition",
            ))?;
        let at = transition.timestamp().as_nanosecond();
        if at > left.max(right) {
            return Err(ZoneError::Value(
                "timezone transition does not bound this missing local time",
            ));
        }
        let begin = at + i128::from(before) * NS_SECOND;
        let end = at + i128::from(after) * NS_SECOND;
        if !(begin <= wall && wall < end) {
            return Err(ZoneError::Value(
                "timezone transition does not bound this missing local time",
            ));
        }
        Ok((begin, end))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn negative_epoch_gap_edges_retain_the_last_fractional_second() {
        let zone = Zone::named("Asia/Manila").unwrap();
        let begin = (i128::from(crate::calendar::ordinal(1844, 12, 31)) - 719_163) * NS_DAY;
        for wall in [begin, begin + 1, begin + NS_DAY / 2, begin + NS_DAY - 1] {
            let Candidates::Gap { before, after } = zone.candidates(wall).unwrap() else {
                panic!("the whole selected local day is missing")
            };
            assert_eq!(
                zone.gap_edges(wall, before, after).unwrap(),
                (begin, begin + NS_DAY)
            );
        }
    }

    #[test]
    fn negative_epoch_offsets_use_the_real_second_before_transition() {
        let zone = Zone::named("Asia/Manila").unwrap();
        let begin = (i128::from(crate::calendar::ordinal(1844, 12, 31)) - 719_163) * NS_DAY;
        let Candidates::Gap { before, after } = zone.candidates(begin).unwrap() else {
            panic!("the selected local day is missing")
        };
        let at = begin - i128::from(before) * NS_SECOND;
        assert_eq!(zone.wall(at - 1).unwrap(), begin - 1);
        assert_eq!(zone.wall(at).unwrap(), at + i128::from(after) * NS_SECOND);
        assert_eq!(
            zone.wall(at + 1).unwrap(),
            at + 1 + i128::from(after) * NS_SECOND
        );
    }

    #[test]
    fn bundled_names_parse_and_dublin_keeps_vanguard_dst_flags() {
        for name in tzdb_data::TZ_NAMES {
            assert!(Zone::named(name).is_ok(), "{name}");
        }
        let context = Zone::named("Europe/Dublin").unwrap();
        let Rules::Region(zone) = context.rules else {
            panic!("Dublin has real transitions")
        };
        let winter =
            timestamp((i128::from(crate::calendar::ordinal(2024, 1, 15)) - 719_163) * NS_DAY)
                .unwrap();
        let summer =
            timestamp((i128::from(crate::calendar::ordinal(2024, 7, 15)) - 719_163) * NS_DAY)
                .unwrap();
        assert!(zone.to_offset_info(winter).dst().is_dst());
        assert!(!zone.to_offset_info(summer).dst().is_dst());
    }

    #[test]
    fn regions_run_unattached_and_reject_outside_calendar_without_panic() {
        fn send_sync<T: Send + Sync>() {}
        send_sync::<Zone>();
        let zone = Zone::named("America/New_York").unwrap();
        let wide = (i128::from(crate::calendar::ordinal(12000, 1, 1)) - 719_163) * NS_DAY;
        assert!(matches!(zone.wall(wide), Err(ZoneError::Capacity(_))));
        let wall = (i128::from(crate::calendar::ordinal(2500, 7, 1)) - 719_163) * NS_DAY
            + 12 * 3_600_000_000_000;
        let result = std::thread::spawn(move || zone.candidates(wall))
            .join()
            .unwrap()
            .unwrap();
        assert!(matches!(result,Candidates::One(value) if value==wall+4*3_600_000_000_000));
    }
}
