"""Independent regression expectations for third-review repairs H01--H08."""

import copy
import gc
import operator
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Configs, Pydt, parse, parse_str, parse_to_epoch


@pytest.mark.parametrize("operation,expected", [
    (operator.eq, False), (operator.ne, True), (operator.lt, True),
    (operator.le, True), (operator.gt, False), (operator.ge, False),
])
def test_h01_timestamp_nanosecond_comparison(operation, expected):
    value = Pydt(2024, 1, 1)
    stamp = pd.Timestamp("2024-01-01 00:00:00.000000123")
    assert operation(value, stamp) is expected


def test_h01_wide_timestamp_and_hash():
    stamp = pd.Timestamp(np.datetime64("10000-01-01", "s"))
    value = Pydt(2024, 1, 1)
    assert value < stamp and value != stamp and not value > stamp
    assert Pydt(1972, 1, 1) != stamp
    assert value - stamp == timedelta(days=-2913174)
    exact = pd.Timestamp("2024-01-01")
    assert value == exact and exact == value
    assert hash(value) == hash(exact)
    assert {value: "saved"}[exact] == "saved"


@pytest.mark.parametrize("nanos,micros", [
    (-1500, -2), (-877, -1), (-500, 0), (-123, 0),
    (123, 0), (500, 0), (877, 1), (1500, 2),
])
def test_h01_round_duration_once(nanos, micros):
    stamp = pd.Timestamp("2024-01-01") - pd.Timedelta(nanos, unit="ns")
    result = Pydt(2024, 1, 1) - stamp
    assert type(result) is timedelta
    assert result == timedelta(microseconds=micros)


def test_h01_normal_protocols_and_missing():
    value = Pydt(2024, 1, 1)
    assert value == datetime(2024, 1, 1)
    assert value - datetime(2024, 1, 2) == timedelta(days=-1)
    assert Pydt(1, 1, 1) != pd.NaT
    assert not Pydt(1, 1, 1) == pd.NaT
    with pytest.raises(ValueError, match="NaT"):
        value - pd.NaT
    class Child(Pydt):
        def __eq__(self, other):
            return "custom"
    assert Child(2024, 1, 1) == value
    assert Child.__eq__(Child(2024, 1, 1), value) == "custom"


def test_h01_aware_fold_and_direct_comparison_methods():
    zone = ZoneInfo("America/New_York")
    for fold in (0, 1):
        value = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=fold)
        stamp = pd.Timestamp(datetime(2024, 11, 3, 1, 30, tzinfo=zone, fold=fold))
        assert value == stamp and stamp == value and hash(value) == hash(stamp)
        assert value - stamp == timedelta(0)
    left = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=0)
    right = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=1)
    assert left == right and left - right == timedelta(0)
    stamp = pd.Timestamp("2024-01-01 00:00:00.000000123")
    value = Pydt(2024, 1, 1)
    assert Pydt.__eq__(value, stamp) is False
    assert Pydt.__lt__(value, stamp) is True
    with pytest.raises(TypeError):
        value - pd.Timestamp("2024-01-01", tz="UTC")
    with pytest.raises(OverflowError):
        value - pd.Timestamp(np.datetime64("100000000-01-01", "s"))


@pytest.mark.parametrize("left_fold,right_fold", [(0, 1), (1, 0)])
@pytest.mark.parametrize("tail,expected_us", [(0, 0), (123, 0), (877, -1), (1500, -2)])
def test_h01_same_timezone_timestamp_preserves_wall_difference(left_fold, right_fold, tail, expected_us):
    zone = ZoneInfo("America/New_York")
    value = Pydt(2024, 11, 3, 1, 30, tzinfo=zone, fold=left_fold)
    stamp = pd.Timestamp(datetime(2024, 11, 3, 1, 30, tzinfo=zone, fold=right_fold)) + pd.Timedelta(tail, unit="ns")
    assert value - stamp == timedelta(microseconds=expected_us)
    assert (value == stamp) is (tail == 0)
    assert (value < stamp) is (tail != 0)
    assert (value != stamp) is (tail != 0)


def test_h01_subtraction_adapter_does_not_require_prior_comparison():
    code = """
from datetime import timedelta
from rstimes import Pydt
import pandas as pd
p = Pydt(2024, 1, 1)
assert p - pd.Timestamp('2024-01-02') == timedelta(days=-1)
assert p - pd.Timestamp('2024-01-01 00:00:00.000000877') == timedelta(microseconds=-1)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("year", [1000000, 1234567, 12345678])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("entry", [parse_str, parse])
def test_h02_long_year_fields(year, strict, entry):
    seen = []
    def target(**fields):
        seen.append(fields)
    entry(f"{year}-01-02", strict=strict, dtclass=target)
    assert (seen[-1]["year"], seen[-1]["month"], seen[-1]["day"]) == (year, 1, 2)


@pytest.mark.parametrize("text", ["20240102", "2024002", "2024-01-02"])
def test_h02_existing_compact_forms(text):
    assert parse_str(text) == datetime(2024, 1, 2)


def test_h02_long_year_epoch_and_target_range():
    text = "1234567-01-02"
    seconds = int(np.datetime64(text, "s").astype("int64"))
    assert parse_to_epoch(text, unit="s") == seconds
    assert parse_to_epoch(text, unit="ns") == seconds * 1000000000
    with pytest.raises((ValueError, OverflowError)):
        parse_str(text)
    with pytest.raises((ValueError, OverflowError)):
        Pydt.parse(text)


def test_h02_complete_long_year_is_checked_before_its_prefix():
    for entry in (parse, parse_str):
        assert entry("00001234-01-02") == datetime(1234, 1, 2)


@pytest.mark.parametrize("fold", [0, 1])
@pytest.mark.parametrize("unit", ["us", "ns"])
def test_h03_native_precision_is_identity(fold, unit):
    value = Pydt(2024, 11, 3, 1, 30, tzinfo="America/New_York", fold=fold)
    before = parse_to_epoch(value)
    for side in ("start", "end"):
        assert getattr(value, f"is_{side}_of")(unit) is True
        result = getattr(value, f"to_{side}_of")(unit)
        assert result is value and result.fold == fold
        assert parse_to_epoch(result) == before


def test_h03_native_precision_needs_no_timezone_callback():
    class NoCalls(tzinfo):
        def utcoffset(self, value):
            pytest.fail("native precision boundary invoked the timezone")
    value = Pydt(2024, 1, 1, tzinfo=NoCalls())
    assert value.to_start_of("us") is value and value.to_end_of("ns") is value
    assert value.is_start_of("us") and value.is_end_of("ns")


def test_h04_missing_time_and_normal_datetime():
    with pytest.raises(ValueError, match="time.*NaT|NaT.*time"):
        Pydt.combine(date(2024, 1, 2), time=pd.NaT)
    clock = datetime(2024, 5, 6, 12, 30, tzinfo=timezone.utc, fold=1)
    result = Pydt.combine(date(2024, 1, 2), time=clock)
    assert (result.year, result.month, result.day, result.hour, result.minute) == (2024, 1, 2, 12, 30)
    assert result.tzinfo is timezone.utc and result.fold == 1


def test_h05_callback_cannot_change_keyword_iteration():
    class Number:
        def __index__(self):
            for reference in gc.get_referrers(self):
                if type(reference) is dict and set(reference) == {"hours", "minutes"}:
                    reference.clear()
            return 1
    cfg = Configs()
    cfg.add_tzoffset("HVALIDCALL", hours=Number(), minutes=2)
    assert cfg.tzoffset["hvalidcall"] == 3720


def test_h05_failed_conversion_does_not_write():
    class Number:
        def __index__(self):
            raise RuntimeError("user integer failure")
    cfg = Configs()
    before = cfg.tzoffset
    with pytest.raises(RuntimeError, match="user integer failure"):
        cfg.add_tzoffset("HVALIDERROR", hours=Number())
    assert cfg.tzoffset == before


def test_h05_positional_callback_cannot_erase_later_keywords():
    class Minute:
        def __index__(self):
            return 2
    minute = Minute()
    class Hour:
        def __index__(self):
            for reference in gc.get_referrers(minute):
                if type(reference) is dict and set(reference) == {"minutes", "seconds"}:
                    reference.clear()
            return 1
    cfg = Configs()
    cfg.add_tzoffset("HVALIDPOSITION", Hour(), minutes=minute, seconds=3)
    assert cfg.tzoffset["hvalidposition"] == 3723


def test_h06_restore_slots_snapshot():
    slots = {"first": 1, "second": 2}
    class Child(Pydt):
        __slots__ = ("first", "second")
        def __setattr__(self, name, value):
            if name == "first":
                slots.clear()
            object.__setattr__(self, name, value)
    result = Child(2024, 1, 1)
    result.__setstate__((None, slots))
    assert (result.first, result.second) == (1, 2)


def test_h06_slots_are_fixed_before_instance_dictionary_lookup():
    slots = {"label": "kept"}
    class Child(Pydt):
        __slots__ = ("label",)
        def __getattribute__(self, name):
            if name == "__dict__":
                slots.clear()
            return super().__getattribute__(name)
    result = Child(2024, 1, 1)
    result.__setstate__(({"extra": 1}, slots))
    assert result.label == "kept" and result.extra == 1


def test_h06_deepcopy_callback_and_cycles():
    class Marker:
        slots = None
        def __deepcopy__(self, memo):
            self.slots = next(v for v in tuple(memo.values()) if type(v) is dict)
            return self
    class Child(Pydt):
        __slots__ = ("first", "second")
        def __setattr__(self, name, value):
            if name == "first" and value.slots is not None:
                value.slots.clear()
            object.__setattr__(self, name, value)
    value = Child(2024, 1, 1)
    value.first, value.second = Marker(), 2
    result = copy.deepcopy(value)
    assert result.second == 2 and result.first is value.first
    class Cycle(Pydt):
        pass
    original = Cycle(2024, 1, 1)
    original.owner = original
    cloned = copy.deepcopy(original)
    assert cloned.owner is cloned


@pytest.mark.parametrize("short", [10, 48, 80, 99])
def test_h07_checked_reference_window(short):
    reference = 2147483647
    expected = short + reference // 100 * 100
    if expected >= reference + 50:
        expected -= 100
    elif expected < reference - 50:
        expected += 100
    seen = []
    def target(**fields):
        seen.append(fields["year"])
    default = np.datetime64(f"{reference}-01-01", "s")
    if expected > 2147483647:
        with pytest.raises(OverflowError):
            parse_str(f"{short:02}-01-02", default=default, dtclass=target)
    else:
        parse_str(f"{short:02}-01-02", default=default, dtclass=target)
        assert seen == [expected]


@pytest.mark.parametrize("short,expected", [(0, 0), (1, 1), (99, -1)])
def test_h07_reference_year_does_not_impose_datetime_range(short, expected):
    seen = []
    def target(**fields):
        seen.append(fields["year"])
    parse_str(f"{short:02}-01-02", default=date(1, 1, 1), dtclass=target)
    assert seen == [expected]


@pytest.mark.parametrize("sign", [-1, 1])
def test_h08_real_offset_range(sign):
    class InvalidZone(tzinfo):
        def utcoffset(self, value):
            return pd.Timedelta(np.timedelta64(sign * 1000000000 * 86400, "s"))
        def dst(self, value):
            return timedelta(0)
    value = Pydt(2024, 1, 1, tzinfo=InvalidZone())
    for operation in (value.utcoffset_seconds, lambda: value.tomicroseconds(utc=True),
                      lambda: parse_to_epoch(value, "s")):
        with pytest.raises(ValueError, match="24|offset"):
            operation()


@pytest.mark.parametrize("mode", ["borrowed_descriptor", "non_datetime_alias"])
def test_h01_timestamp_alias_cannot_bypass_native_layout_guards(mode):
    code = r"""
import sys
from datetime import datetime
import pandas as pd
from rstimes import Pydt
original = pd.Timestamp
mode = sys.argv[1]
if mode == "borrowed_descriptor":
    class Alias(datetime):
        __slots__ = tuple("extra"+str(i) for i in range(24))
        nanosecond = original.nanosecond
        __eq__ = original.__eq__
        __ne__ = original.__ne__
        __lt__ = original.__lt__
        __le__ = original.__le__
        __gt__ = original.__gt__
        __ge__ = original.__ge__
    pd.Timestamp = Alias
    left, right = Pydt(2024, 1, 1), Alias(2024, 1, 1)
    for _ in range(2):
        # A mutable pandas alias must not reclassify this real datetime child.
        assert (left == right) is True
        assert (left == original("2024-01-01 00:00:00.000000001")) is False
        try:
            original.nanosecond.__get__(right)
        except TypeError:
            pass
        else:
            raise AssertionError("borrowed descriptor accepted an unrelated receiver")
else:
    class Alias:
        pass
    class Child(datetime, Alias):
        pass
    pd.Timestamp = Alias
    left = Pydt(2024, 1, 1)
    try:
        left - Child(2024, 1, 1)
    except (AttributeError, TypeError):
        pass
    for _ in range(2):
        assert (left == Alias()) is False
print("native-layout-guard-ok")
"""
    result = subprocess.run([sys.executable, "-c", code, mode], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "native-layout-guard-ok" in result.stdout
