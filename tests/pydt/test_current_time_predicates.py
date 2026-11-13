"""Past/future queries use independent instants, not same-zone wall ordering."""

from datetime import datetime, timedelta, timezone, tzinfo
from itertools import product
from pathlib import Path
import json

import pytest

import rstimes.pydt as implementation
from rstimes import Pydt
from zoneinfo import ZoneInfo

UTC = timezone.utc
REGIONAL_ANCHORS = (
    ("America/New_York", datetime(2024, 11, 3, 5, tzinfo=UTC)),
    ("Europe/London", datetime(2024, 10, 27, 0, tzinfo=UTC)),
    ("Europe/Berlin", datetime(2024, 10, 27, 0, tzinfo=UTC)),
    ("Australia/Lord_Howe", datetime(2024, 4, 6, 14, 30, tzinfo=UTC)),
    ("UTC", datetime(2024, 11, 3, 5, tzinfo=UTC)),
)
MINUTES = (0, 15, 30, 45, 59, 60, 105)
MATRIX = [(zone, anchor + timedelta(minutes=now), anchor + timedelta(minutes=value))
          for (zone, anchor), now, value in product(REGIONAL_ANCHORS, MINUTES, MINUTES)]


def freeze_clock(monkeypatch, instant, local=None):
    """Supply one exact clock reading and record the requested timezone."""
    calls = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(tz)
            return (instant.replace(tzinfo=None) if local is None else local) if tz is None else instant.astimezone(tz)

    monkeypatch.setattr(implementation, "datetime", Clock)
    return calls


@pytest.mark.parametrize("zone,now,value", MATRIX)
@pytest.mark.parametrize("query", ("is_past", "is_future"))
def test_regional_timeline_uses_utc_oracle(monkeypatch, zone, now, value, query):
    local = value.astimezone(ZoneInfo(zone))
    target = Pydt.fromdatetime(local)
    calls = freeze_clock(monkeypatch, now)
    expected = value < now if query == "is_past" else value > now
    assert getattr(target, query)() is expected
    assert len(calls) == 1


SAVED_FAILURES = json.loads((Path(__file__).parent /
    "data/current-time-regressions.json").read_text(encoding='utf-8'))["cases"]


@pytest.mark.parametrize("case", SAVED_FAILURES, ids=lambda c: c["zone"] + ":" + c["now"] + ":" + c["value"])
def test_each_saved_wrong_pair_is_repaired(monkeypatch, case):
    zone = ZoneInfo(case["zone"])
    now = datetime.fromisoformat(case["now"])
    value = datetime.fromisoformat(case["value"])
    target = Pydt(*value.timetuple()[:6], value.microsecond, tzinfo=zone, fold=case["fold"])
    calls = freeze_clock(monkeypatch, now)
    assert [target.is_past(), target.is_future()] == case["expected"]
    assert len(calls) == 2


class OffsetOnly(tzinfo):
    """A legal offset provider whose fromutc is deliberately unavailable."""
    def __init__(self, offset):
        self.offset = offset
        self.seen = []

    def utcoffset(self, dt):
        self.seen.append(dt)
        return self.offset

    def dst(self, dt):
        return None

    def fromutc(self, dt):
        raise AssertionError("queries must not need fromutc")


@pytest.mark.parametrize("offset", (None, timedelta(0), timedelta(hours=8), timedelta(hours=-7), timedelta(seconds=2, microseconds=1)))
@pytest.mark.parametrize("delta", (-1, 0, 1))
@pytest.mark.parametrize("query", ("is_past", "is_future"))
def test_one_offset_and_clock_without_fromutc(monkeypatch, offset, delta, query):
    now = datetime(2024, 5, 7, 12, tzinfo=UTC)
    fields = now.replace(tzinfo=None) + (offset or timedelta(0)) + timedelta(microseconds=delta)
    zone = OffsetOnly(offset)
    target = Pydt(*fields.timetuple()[:6], fields.microsecond, tzinfo=zone)
    zone.seen.clear()
    calls = freeze_clock(monkeypatch, now)
    assert getattr(target, query)() is (delta < 0 if query == "is_past" else delta > 0)
    assert zone.seen == [target]
    assert calls == [None if offset is None else UTC]


@pytest.mark.parametrize("zone", (None, UTC, timezone(timedelta(hours=8)), timezone(timedelta(hours=-7)), ZoneInfo("UTC")))
@pytest.mark.parametrize("delta", (-1, 0, 1))
@pytest.mark.parametrize("query", ("is_past", "is_future"))
def test_naive_fixed_utc_and_equal_now(monkeypatch, zone, delta, query):
    now = datetime(2024, 5, 7, 12, tzinfo=UTC)
    fields = now.replace(tzinfo=None) if zone is None else now.astimezone(zone)
    fields += timedelta(microseconds=delta)
    target = Pydt(*fields.timetuple()[:6], fields.microsecond, tzinfo=zone)
    calls = freeze_clock(monkeypatch, now)
    assert getattr(target, query)() is (delta < 0 if query == "is_past" else delta > 0)
    assert len(calls) == 1


@pytest.mark.parametrize("query", ("is_past", "is_future"))
def test_offset_error_keeps_original_exception(monkeypatch, query):
    failure = RuntimeError("offset source failed")

    class Broken(OffsetOnly):
        def utcoffset(self, dt):
            raise failure

    target = datetime.__new__(Pydt, 2024, 1, 1, tzinfo=Broken(None))
    calls = freeze_clock(monkeypatch, datetime(2024, 5, 7, tzinfo=UTC))
    with pytest.raises(RuntimeError) as caught:
        getattr(target, query)()
    assert caught.value is failure
    assert not calls


@pytest.mark.parametrize("offset,error", (("+08:00", TypeError), (timedelta(days=1), ValueError)))
@pytest.mark.parametrize("query", ("is_past", "is_future"))
def test_invalid_offset_still_rejected(monkeypatch, offset, error, query):
    target = datetime.__new__(Pydt, 2024, 1, 1, tzinfo=OffsetOnly(offset))
    freeze_clock(monkeypatch, datetime(2024, 5, 7, tzinfo=UTC))
    with pytest.raises(error):
        getattr(target, query)()


def test_ordinary_same_zone_comparison_and_subtraction_unchanged(monkeypatch):
    zone = ZoneInfo("America/New_York")
    first = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=0)
    second = Pydt(2024, 11, 3, 1, 15, tzinfo=zone, fold=1)
    assert second < first
    assert second - first == timedelta(minutes=-15)
    equal_wall = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=1)
    assert first == equal_wall and hash(first) == hash(equal_wall)
    freeze_clock(monkeypatch, datetime(2024, 11, 3, 5, 30, tzinfo=UTC))
    assert second.is_future()


def test_real_fields_and_stored_timezone_take_precedence(monkeypatch):
    class Child(Pydt):
        year = 9999
        month = 12
        day = 31
        tzinfo = UTC
        fold = 0

    zone = ZoneInfo("America/New_York")
    target = Child(2024, 11, 3, 1, 15, tzinfo=zone, fold=1)
    freeze_clock(monkeypatch, datetime(2024, 11, 3, 5, 30, tzinfo=UTC))
    assert target.is_future()


@pytest.mark.parametrize("zone,value,now", (
    ("America/New_York", datetime(2024, 11, 3, 6, 15, tzinfo=UTC), datetime(2024, 10, 31, 12, tzinfo=UTC)),
    ("America/New_York", datetime(2024, 11, 3, 6, 15, tzinfo=UTC), datetime(2024, 11, 6, 12, tzinfo=UTC)),
    ("Australia/Lord_Howe", datetime(2024, 4, 6, 15, 15, tzinfo=UTC), datetime(2024, 4, 3, 12, tzinfo=UTC)),
    ("Australia/Lord_Howe", datetime(2024, 4, 6, 15, 15, tzinfo=UTC), datetime(2024, 4, 9, 12, tzinfo=UTC)),
))
def test_opposite_fold_far_apart_keeps_instant_order(monkeypatch, zone, value, now):
    """Exercise the proved wide-gap shortcut as well as nearby offset comparisons."""
    target = Pydt.fromdatetime(value.astimezone(ZoneInfo(zone)))
    assert target.fold == 1
    calls = freeze_clock(monkeypatch, now)
    assert target.is_past() is (value < now)
    assert target.is_future() is (value > now)
    assert len(calls) == 2
