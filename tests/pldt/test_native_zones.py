"""Native timezone candidates use independent UTC answers and real TZif data."""

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import hashlib
import numpy as np
import polars as pl
import pytest

from rstimes import _native


def wall(text):
    return int(np.datetime64(text, "us").astype(np.int64)) * 1000


def zone(key):
    from rstimes._pldt_timezone import prepare_timezone
    return prepare_timezone(key)


def probe(texts, key, ambiguous="raise", nonexistent="raise", unit="us"):
    values = [None if value is None else wall(value) for value in texts]
    policy = _native._pldt_policies(ambiguous, nonexistent)
    return _native._pldt_zone_probe(values, zone(key), policy, unit)


@pytest.mark.parametrize("key,text,utc", [
    ("America/New_York", "2024-01-01T12:00", "2024-01-01T17:00"),
    ("America/New_York", "2024-07-01T12:00", "2024-07-01T16:00"),
    ("America/New_York", "2500-07-01T12:00", "2500-07-01T16:00"),
    ("Asia/Shanghai", "2024-01-01T12:00", "2024-01-01T04:00"),
    ("Europe/Dublin", "2024-01-01T12:00", "2024-01-01T12:00"),
    ("Europe/Dublin", "2024-07-01T12:00", "2024-07-01T11:00"),
])
def test_ordinary_and_future_region_offsets(key, text, utc):
    assert probe([text, None], key) == [wall(utc), None]


@pytest.mark.parametrize("choice,utc", [(True, "2024-11-03T05:30"), (False, "2024-11-03T06:30")])
def test_repeated_candidates_are_real_utc_order(choice, utc):
    assert probe(["2024-11-03T01:30"], "America/New_York", ambiguous=choice) == [wall(utc)]


@pytest.mark.parametrize("key,text,first,second", [
    ("Europe/Warsaw", "1915-08-04T23:50", "1915-08-04T22:26", "1915-08-04T22:50"),
    ("Europe/Kyiv", "1990-07-01T01:30", "1990-06-30T21:30", "1990-06-30T22:30"),
])
def test_non_simple_dst_candidates_do_not_classify_dst_boolean(key, text, first, second):
    assert probe([text, text], key, ambiguous=[True, False]) == [wall(first), wall(second)]


@pytest.mark.parametrize("unit,step", [("ms", 1000000), ("us", 1000), ("ns", 1)])
def test_gap_nearest_boundaries_at_the_actual_unit(unit, step):
    assert probe(["2024-03-10T02:30"], "America/New_York", nonexistent="shift_forward", unit=unit) == [wall("2024-03-10T07:00")]
    assert probe(["2024-03-10T02:30"], "America/New_York", nonexistent="shift_backward", unit=unit) == [wall("2024-03-10T07:00") - step]


@pytest.mark.parametrize("key,text,boundary", [
    ("Australia/Lord_Howe", "2024-10-06T02:15", "2024-10-05T15:30"),
    ("Pacific/Apia", "2011-12-30T12:00", "2011-12-30T10:00"),
])
def test_non_hour_and_full_day_gaps(key, text, boundary):
    assert probe([text], key, nonexistent="shift_forward") == [wall(boundary)]
    assert probe([text], key, nonexistent="shift_backward") == [wall(boundary) - 1000]


def test_explicit_shift_and_missing_strategies_are_separate():
    assert probe(["2024-03-10T02:30"], "America/New_York", nonexistent=timedelta(hours=1)) == [wall("2024-03-10T07:30")]
    assert probe(["2024-03-10T02:30"], "America/New_York", nonexistent="NaT") == [None]
    assert probe(["2024-11-03T01:30"], "America/New_York", ambiguous="NaT") == [None]
    with pytest.raises(ValueError, match="missing|exist"):
        probe(["2024-03-10T02:30"], "America/New_York", nonexistent=timedelta(minutes=5))
    with pytest.raises(ValueError, match="twice|ambiguous"):
        probe(["2024-11-03T01:30"], "America/New_York")


def test_infer_uses_original_order_and_requires_one_reversal():
    source = ["2024-11-03T01:00", "2024-11-03T01:30", "2024-11-03T01:00", "2024-11-03T01:30"]
    assert probe(source, "America/New_York", ambiguous="infer") == [wall(value) for value in ("2024-11-03T05:00", "2024-11-03T05:30", "2024-11-03T06:00", "2024-11-03T06:30")]
    with pytest.raises(ValueError, match="infer"):
        probe(source[:2], "America/New_York", ambiguous="infer")
    with pytest.raises(ValueError, match="infer"):
        probe(source + source, "America/New_York", ambiguous="infer")


@pytest.mark.parametrize("value", [1, 0, None, [True, 1], [None], np.array([1], dtype=np.int64)])
def test_ambiguous_true_boolean_roles(value):
    with pytest.raises(TypeError):
        _native._pldt_policies(value, "raise")


def test_mask_checks_full_source_including_null_and_simple_zones():
    with pytest.raises(ValueError, match="length"):
        probe(["2024-01-01", None], "UTC", ambiguous=[True])
    assert probe(["2024-01-01", None], "UTC", ambiguous=[True, False]) == [wall("2024-01-01"), None]


def test_simple_contexts_are_fixed_and_canonical():
    assert zone(None) is None
    assert zone("UTC") is zone(ZoneInfo("UTC"))
    assert zone("UTC").fixed_seconds == 0
    fixed = zone(timezone(timedelta(hours=8)))
    assert fixed.key == "Etc/GMT-8" and fixed.fixed_seconds == 28800
    assert fixed.plugin_kwargs()["data"] == b""
    with pytest.raises(ValueError, match="fixed|represent"):
        zone(timezone(timedelta(hours=5, minutes=30)))
    with pytest.raises(ValueError):
        zone(timezone(timedelta(hours=23)))


def test_rule_snapshot_is_native_bytes_and_versioned_by_real_data():
    context = zone(ZoneInfo("America/New_York"))
    data = context.plugin_kwargs()
    assert data["key"] == "America/New_York"
    assert type(data["data"]) is bytes and data["data"].startswith(b"TZif")
    assert len(hashlib.sha256(data["data"]).digest()) == 32
    assert data["fixed_seconds"] is None


def test_native_database_does_not_require_python_resource_lookup(monkeypatch):
    from rstimes import _pldt_timezone
    fresh = ZoneInfo.no_cache("America/New_York")
    monkeypatch.setattr(_pldt_timezone.zoneinfo, "TZPATH", ())
    context = _pldt_timezone.prepare_timezone(fresh)
    policy = _native._pldt_policies("raise", "raise")
    assert _native._pldt_zone_probe([wall("2024-07-01T12:00")], context, policy, "us") == [wall("2024-07-01T16:00")]


def test_region_capacity_does_not_limit_fixed_offsets():
    wide = wall("12000-01-01")
    assert _native._pldt_zone_probe([wide], zone("UTC"), _native._pldt_policies("raise", "raise"), "ms") == [wide]
    with pytest.raises(OverflowError, match="regional|range|9999"):
        _native._pldt_zone_probe([wide], zone("America/New_York"), _native._pldt_policies("raise", "raise"), "ms")
