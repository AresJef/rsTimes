"""Target dtypes cannot silently substitute a Python business timezone's key."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from rstimes import Pldt


class BusinessZone(ZoneInfo):
    def utcoffset(self, value):
        return timedelta(hours=2)

    def dst(self, value):
        return timedelta(0)

    def fromutc(self, value):
        return (value + timedelta(hours=2)).replace(tzinfo=self)


class PassiveZone(ZoneInfo):
    pass


ENTRIES = ("constructor", "fromdatetime", "fromisoformat", "strptime", "date_range",
           "tz_localize", "replace", "expr", "aware_source")


def operation(entry, zone):
    clock = datetime(2024, 1, 1, 12)
    plain = Pldt([clock], unit="us", name="time")
    return {
        "constructor": lambda: Pldt([clock], unit="us", tz=zone),
        "fromdatetime": lambda: Pldt.fromdatetime(clock, size=1, unit="us", tz=zone),
        "fromisoformat": lambda: Pldt.fromisoformat("2024-01-01T12:00", size=1, unit="us", tz=zone),
        "strptime": lambda: Pldt.strptime("2024-01-01 12:00", "%Y-%m-%d %H:%M", size=1, unit="us", tz=zone),
        "date_range": lambda: Pldt.date_range(clock, periods=1, freq="1h", unit="us", tz=zone),
        "tz_localize": lambda: plain.tz_localize(zone),
        "replace": lambda: plain.pldt.replace(tzinfo=zone),
        "expr": lambda: pl.DataFrame({"time": plain}).select(pl.col("time").pldt.tz_localize(zone))["time"],
        "aware_source": lambda: Pldt([clock.replace(tzinfo=zone)], unit="us", tz="UTC"),
    }[entry]


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("kind,key", [
    ("exact", "UTC"), ("passive", "UTC"), ("business", "UTC"),
    ("business", "Europe/Paris"), ("business", "America/New_York"), ("fixed", "UTC"),
])
def test_target_policy_and_real_aware_source_are_separate(entry, kind, key):
    zone = {"exact": ZoneInfo, "passive": PassiveZone, "business": BusinessZone}[kind](key) if kind != "fixed" else timezone(timedelta(hours=2))
    action = operation(entry, zone)
    if kind == "business" and entry != "aware_source":
        with pytest.raises(ValueError, match="target|encoded|represent"):
            action()
    else:
        result = action()
        expected = 1704103200000000 if kind in ("business", "fixed") else 1704110400000000
        assert result.to_physical().to_list() == [expected]
        assert result.dtype.time_unit == "us"


@pytest.mark.parametrize("values", [[], [None, None]])
@pytest.mark.parametrize("entry", ["constructor", "localize", "replace", "expr"])
def test_invalid_target_is_checked_even_without_valid_rows(values, entry):
    zone = BusinessZone("UTC")
    plain = Pldt(values, unit="ns", name="time")
    actions = {
        "constructor": lambda: Pldt(values, unit="ns", tz=zone),
        "localize": lambda: plain.tz_localize(zone),
        "replace": lambda: plain.pldt.replace(tzinfo=zone),
        "expr": lambda: pl.col("time").pldt.tz_localize(zone),
    }
    with pytest.raises(ValueError, match="target|encoded|represent"):
        actions[entry]()


def test_passive_subclass_business_state_and_ns_are_retained():
    zone = PassiveZone("Europe/Paris")
    zone.business = {"name": "allowed"}
    out = Pldt(["2024-01-01 12:00:00.000000007", None], tz=zone, unit="ns")
    assert out.to_physical().to_list() == [1704106800000000007, None]
    assert out.dtype.time_zone == "Europe/Paris"


def test_instance_override_is_not_mistaken_for_a_passive_subclass():
    zone = PassiveZone("UTC")
    zone.utcoffset = lambda value: timedelta(hours=2)
    with pytest.raises(ValueError, match="target|encoded|represent"):
        Pldt(["2024-01-01"], tz=zone, unit="us")


def test_source_callback_original_error_survives():
    original = LookupError("source offset failed")

    class BrokenZone(ZoneInfo):
        def utcoffset(self, value):
            raise original

    value = datetime(2024, 1, 1, tzinfo=BrokenZone("UTC"))
    with pytest.raises(LookupError) as caught:
        Pldt([value], tz="UTC", unit="ns")
    assert caught.value is original


def test_passive_target_is_rechecked_after_a_real_class_edit(monkeypatch):
    class LocalZone(ZoneInfo):
        pass

    zone = LocalZone("UTC")
    assert Pldt([0], unit="us", tz=zone).to_physical().to_list() == [0]
    monkeypatch.setattr(LocalZone, "utcoffset", lambda self, value: timedelta(hours=2))
    with pytest.raises(ValueError, match="target|encoded|represent"):
        Pldt([0], unit="us", tz=zone)


def test_target_capability_check_never_evaluates_a_fake_dictionary():
    calls = []

    class HiddenState(ZoneInfo):
        @property
        def __dict__(self):
            calls.append("dictionary display")
            raise RuntimeError("must not inspect a business dictionary property")

    with pytest.raises(ValueError, match="target|encoded|represent"):
        Pldt([0], unit="us", tz=HiddenState("UTC"))
    assert calls == []
