"""Native target rules require provenance; aware sources retain actual values."""
from datetime import datetime, time, timedelta, timezone
from io import BytesIO
import struct
import gc
import weakref
from zoneinfo import ZoneInfo

from importlib.util import find_spec
import numpy as np
import polars as pl
import pytest

from rstimes import Pldt

if find_spec("pandas") is not None:
    import pandas as pd
else:
    pd = None


class PassiveZone(ZoneInfo):
    pass


def file_zone(kind=ZoneInfo, key="UTC"):
    # Frozen valid TZif v1: no transitions, one +02:00 type and its abbreviation.
    data = (b"TZif\0" + bytes(15) + struct.pack(">6l", 0, 0, 0, 0, 1, 4)
            + struct.pack(">lbb", 7200, 0, 0) + b"X+2\0")
    return kind.from_file(BytesIO(data), key=key)


def test_fixture_has_real_offset_independent_of_display_key():
    value = datetime(2024, 1, 1, 12, tzinfo=file_zone())
    assert value.utcoffset() == timedelta(hours=2)
    assert value.astimezone(timezone.utc) == datetime(2024, 1, 1, 10, tzinfo=timezone.utc)


@pytest.mark.parametrize("kind", [ZoneInfo, PassiveZone])
@pytest.mark.parametrize("key", ["UTC", "Europe/Paris", "Etc/GMT-2", None])
@pytest.mark.parametrize("values", [[datetime(2024, 1, 1, 12)], [], [None]])
@pytest.mark.parametrize("entry", ["constructor", "parse", "fromdatetime", "iso", "strptime", "range",
                                         "localize", "convert", "switch", "replace", "expr", "now"])
def test_file_target_rules_are_rejected_before_alias_or_empty_shortcuts(kind, key, values, entry):
    zone = file_zone(kind, key)
    plain = Pldt(values, unit="us", name="time")
    actions = {
        "constructor": lambda: Pldt(values, tz=zone, unit="us"),
        "parse": lambda: Pldt.parse(values, tz=zone, unit="us"),
        "fromdatetime": lambda: Pldt.fromdatetime(values, tz=zone, unit="us"),
        "iso": lambda: Pldt.fromisoformat([], tz=zone, unit="us"),
        "strptime": lambda: Pldt.strptime([], "%Y-%m-%d", tz=zone, unit="us"),
        "range": lambda: Pldt.date_range("2024-01-01", periods=0, tz=zone, unit="us"),
        "localize": lambda: plain.tz_localize(zone),
        "convert": lambda: plain.tz_localize("UTC").tz_convert(zone),
        "switch": lambda: plain.tz_switch(zone, base_tz="UTC"),
        "replace": lambda: plain.pldt.replace(tzinfo=zone),
        "expr": lambda: pl.col("time").pldt.tz_localize(zone),
        "now": lambda: Pldt.now(0, tz=zone, unit="us"),
    }
    with pytest.raises(ValueError, match="file|origin"):
        actions[entry]()


@pytest.mark.parametrize("mode", ["exact", "no_cache", "passive", "passive_no_cache"])
@pytest.mark.parametrize("key,tick", [("UTC", 1704110400000000007), ("Europe/Paris", 1704106800000000007),
                                      ("America/New_York", 1704128400000000007)])
def test_standard_named_rules_keep_ns_and_null(mode, key, tick):
    kind = PassiveZone if mode.startswith("passive") else ZoneInfo
    zone = kind.no_cache(key) if mode.endswith("no_cache") else kind(key)
    out = Pldt(["2024-01-01 12:00:00.000000007", None], tz=zone, unit="ns")
    assert out.to_physical().to_list() == [tick, None]


@pytest.mark.parametrize("kind", [ZoneInfo, PassiveZone])
@pytest.mark.parametrize("carrier", ["python", "timestamp", "index", "array", "series"])
@pytest.mark.skipif(pd is None, reason="pandas-aware source integration requires optional pandas")
def test_real_file_aware_source_converts_actual_instant(kind, carrier):
    value = datetime(2024, 1, 1, 12, tzinfo=file_zone(kind))
    stamp = pd.Timestamp(year=2024, month=1, day=1, hour=12, nanosecond=7, tzinfo=value.tzinfo)
    values = {
        "python": [value, None], "timestamp": [stamp, None],
        "index": pd.DatetimeIndex([stamp, pd.NaT]),
        "array": pd.DatetimeIndex([stamp, pd.NaT]).array,
        "series": pd.Series([stamp, pd.NaT]),
    }
    result = Pldt(values[carrier], tz="UTC", unit="ns")
    assert result.to_physical().to_list() == [1704103200000000000 + (0 if carrier == "python" else 7), None]


@pytest.mark.parametrize("carrier", ["python", "timestamp", "index", "array", "series"])
@pytest.mark.skipif(pd is None, reason="pandas-aware source integration requires optional pandas")
def test_fromdatetime_replaces_real_source_wall_zone(carrier):
    value = datetime(2024, 1, 1, 12, tzinfo=file_zone())
    stamp = pd.Timestamp(year=2024, month=1, day=1, hour=12, nanosecond=7, tzinfo=value.tzinfo)
    values = {"python": [value, None], "timestamp": [stamp, None],
              "index": pd.DatetimeIndex([stamp, pd.NaT]),
              "array": pd.DatetimeIndex([stamp, pd.NaT]).array, "series": pd.Series([stamp, pd.NaT])}
    result = Pldt.fromdatetime(values[carrier], tz="UTC", unit="ns")
    assert result.to_physical().to_list() == [1704110400000000000 + (0 if carrier == "python" else 7), None]


@pytest.mark.parametrize("carrier", ["index", "array", "series"])
@pytest.mark.skipif(pd is None, reason="pandas-aware source integration requires optional pandas")
def test_combine_reads_actual_file_source_clock_without_retaining_rules(carrier):
    stamp = pd.Timestamp(year=2024, month=1, day=1, hour=12, nanosecond=7, tzinfo=file_zone())
    index = pd.DatetimeIndex([stamp, pd.NaT])
    clock = {"index": index, "array": index.array, "series": pd.Series(index)}[carrier]
    result = Pldt.combine([datetime(2024, 1, 2), None], clock, tz="UTC", unit="ns")
    assert result.to_physical().to_list() == [1704196800000000007, None]


@pytest.mark.parametrize("expression", [False, True])
@pytest.mark.parametrize("role", ["tzinfo", "targ_tz", "base_tz", "tz"])
@pytest.mark.parametrize("bad", ["file", "business", "name", "type"])
def test_errors_identify_actual_public_timezone_role(expression, role, bad):
    class Business(ZoneInfo):
        def utcoffset(self, value):
            return timedelta(hours=2)

    zone = {"file": lambda: file_zone(), "business": lambda: Business("UTC"),
            "name": lambda: "Not/A_Real_Zone", "type": lambda: 42}[bad]()
    source = pl.col("time").pldt if expression else Pldt([0], unit="us").pldt
    actions = {"tzinfo": lambda: source.replace(tzinfo=zone),
               "targ_tz": lambda: source.tz_switch(zone, base_tz="UTC"),
               "base_tz": lambda: source.tz_switch("UTC", base_tz=zone),
               "tz": lambda: source.tz_localize(zone)}
    with pytest.raises(TypeError if bad == "type" else ValueError) as caught:
        actions[role]()
    assert f"{role}=" in str(caught.value)


def test_source_error_and_implicit_file_output_are_distinct():
    value = datetime(2024, 1, 1, 12, tzinfo=file_zone())
    with pytest.raises(ValueError, match="file|origin") as caught:
        Pldt([value], unit="us")
    assert "data" in str(caught.value)
    assert "tz=None" not in str(caught.value)


def test_file_aware_python_source_needs_no_pandas_to_preserve_instant():
    value = datetime(2024, 1, 1, 12, tzinfo=file_zone())
    out = Pldt([value, None], unit="ns", tz="UTC")
    assert out.to_physical().to_list() == [1704103200000000000, None]


@pytest.mark.skipif(pd is None, reason="pandas source metadata requires optional pandas")
@pytest.mark.parametrize("entry", ["constructor", "fromdatetime"])
def test_implicit_file_source_output_is_not_accepted_by_display_key(entry):
    stamp = pd.Timestamp(year=2024, month=1, day=1, hour=12, nanosecond=7, tzinfo=file_zone())
    source = pd.DatetimeIndex([stamp, pd.NaT])
    actions = {"constructor": lambda: Pldt(source, unit="ns"),
               "fromdatetime": lambda: Pldt.fromdatetime(source, unit="ns")}
    with pytest.raises(ValueError, match="file|origin") as caught:
        actions[entry]()
    assert "data" in str(caught.value)


@pytest.mark.skipif(pd is None, reason="pandas clock integration requires optional pandas")
def test_combine_can_retain_a_proven_actual_fixed_source_offset():
    # A real constant offset can already be encoded honestly, without the key.
    stamp = pd.Timestamp(year=2024, month=1, day=1, hour=12, nanosecond=7, tzinfo=file_zone())
    out = Pldt.combine([datetime(2024, 1, 2), None], pd.DatetimeIndex([stamp, pd.NaT]), unit="ns")
    assert out.to_physical().to_list() == [1704189600000000007, None]
    assert out.dtype.time_zone == "Etc/GMT-2"


@pytest.mark.skipif(pd is None, reason="pandas source metadata requires optional pandas")
@pytest.mark.parametrize("kind", [ZoneInfo, PassiveZone])
@pytest.mark.parametrize("values", [[], [None, None]])
@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("factory", ["fromdate", "fromdatetime"])
def test_empty_special_source_default_unit_is_preserved(kind, values, unit, factory):
    source = pd.DatetimeIndex(values, dtype=pd.DatetimeTZDtype(unit=unit, tz=file_zone(kind)))
    result = getattr(Pldt, factory)(source, tz="UTC")
    assert result.dtype == pl.Datetime("ms" if unit == "s" else unit, "UTC")
    assert result.to_physical().to_list() == [None] * len(values)


@pytest.mark.skipif(pd is None, reason="pandas source metadata requires optional pandas")
@pytest.mark.parametrize("kind", [ZoneInfo, PassiveZone])
@pytest.mark.parametrize("values", [[], [None]])
def test_empty_implicit_file_output_is_rejected_before_reading_rows(kind, values):
    source = pd.DatetimeIndex(values, dtype=pd.DatetimeTZDtype(unit="ns", tz=file_zone(kind)))
    with pytest.raises(ValueError, match="file|origin"):
        Pldt.fromdatetime(source)


@pytest.mark.skipif(pd is None, reason="pandas clock metadata requires optional pandas")
@pytest.mark.parametrize("values", [[], [None]])
def test_empty_proven_fixed_clock_metadata_survives(values):
    source = pd.DatetimeIndex(values, dtype=pd.DatetimeTZDtype(unit="ns", tz=file_zone()))
    out = Pldt.combine([None] * len(values), source, unit="ns")
    assert out.dtype == pl.Datetime("ns", "Etc/GMT-2")
    assert out.to_physical().to_list() == [None] * len(values)


@pytest.mark.skipif(pd is None, reason="pandas source metadata requires optional pandas")
def test_source_date_fields_use_real_zone_across_midnight():
    stamp = pd.Timestamp(year=2024, month=1, day=2, hour=1, nanosecond=7, tzinfo=file_zone())
    result = Pldt.fromdate(pd.DatetimeIndex([stamp]), tz="UTC", unit="ns")
    assert result.to_physical().to_list() == [1704153600000000000]


@pytest.mark.skipif(pd is None, reason="pandas real source protocol requires optional pandas")
@pytest.mark.parametrize("entry", ["fromdate", "fromdatetime", "combine"])
def test_real_source_fromutc_error_is_not_replaced(entry, monkeypatch):
    class SourceZone(ZoneInfo):
        pass

    zone = SourceZone("UTC")
    source = pd.DatetimeIndex([pd.Timestamp(year=2024, month=1, day=1, hour=12, tzinfo=zone)])
    original = LookupError("actual source fromutc failed")
    original.add_note("business source note")

    def broken(self, value):
        raise original

    monkeypatch.setattr(SourceZone, "fromutc", broken)
    # A known instant needs no wall reconstruction when converted to UTC.
    assert Pldt(source, tz="UTC", unit="us").to_physical().to_list() == [1704110400000000]
    actions = {"fromdate": lambda: Pldt.fromdate(source, tz="UTC", unit="us"),
               "fromdatetime": lambda: Pldt.fromdatetime(source, tz="UTC", unit="us"),
               "combine": lambda: Pldt.combine([datetime(2024, 1, 2)], source, tz="UTC", unit="us")}
    with pytest.raises(LookupError) as caught:
        actions[entry]()
    assert caught.value is original
    assert caught.value.args == ("actual source fromutc failed",)
    assert "business source note" in caught.value.__notes__


@pytest.mark.skipif(pd is None, reason="real pandas source exporter requires optional pandas")
@pytest.mark.parametrize("dtype", ["float64", "uint64", "bool"])
@pytest.mark.parametrize("entry", ["fromdate", "fromdatetime", "combine"])
def test_special_source_invalid_tick_export_is_not_coerced(dtype, entry):
    class BadTicks(pd.arrays.DatetimeArray):
        @property
        def asi8(self):
            return np.array([1], dtype=dtype)

    original = pd.DatetimeIndex([pd.Timestamp(year=2024, month=1, day=1, hour=12, tzinfo=file_zone())]).array
    source = BadTicks._simple_new(original._ndarray, dtype=original.dtype)
    actions = {"fromdate": lambda: Pldt.fromdate(source, tz="UTC", unit="us"),
               "fromdatetime": lambda: Pldt.fromdatetime(source, tz="UTC", unit="us"),
               "combine": lambda: Pldt.combine([datetime(2024, 1, 2)], source, tz="UTC", unit="us")}
    with pytest.raises(TypeError, match="signed int64"):
        actions[entry]()


def test_target_qualification_does_not_call_business_pickle_hooks():
    calls = []

    class OwnPickle(ZoneInfo):
        def __reduce__(self):
            calls.append("reduce")
            raise RuntimeError("business reduce")

        def __reduce_ex__(self, protocol):
            calls.append("reduce_ex")
            raise RuntimeError("business reduce_ex")

    out = Pldt([0], unit="us", tz=OwnPickle("UTC"))
    assert out.to_physical().to_list() == [0]
    assert calls == []


@pytest.mark.parametrize("instance", [False, True])
def test_qualification_never_executes_custom_unpickle_lookup(instance):
    calls = []

    class Zone(ZoneInfo):
        pass

    value = Zone("UTC")
    if instance:
        value._unpickle = lambda *args: calls.append("instance")
    else:
        Zone._unpickle = property(lambda self: calls.append("descriptor"))
    with pytest.raises(ValueError, match="target|encoded|represent"):
        Pldt([0], unit="us", tz=value)
    assert calls == []


def test_cached_file_refusal_has_fresh_actual_roles_and_errors():
    zone = file_zone()
    source = Pldt([0], unit="us")
    errors = []
    actions = (("tzinfo", lambda: source.pldt.replace(tzinfo=zone)),
               ("targ_tz", lambda: source.tz_switch(zone, base_tz="UTC")),
               ("base_tz", lambda: source.tz_switch("UTC", base_tz=zone)),
               ("tz", lambda: Pldt([0], unit="us", tz=zone)))
    for role, action in actions:
        with pytest.raises(ValueError) as caught:
            action()
        assert f"{role}=" in str(caught.value)
        errors.append(caught.value)
    assert len({id(error) for error in errors}) == 4


def test_unpickle_lookup_is_rechecked_after_a_success(monkeypatch):
    class Zone(ZoneInfo):
        pass

    zone = Zone("UTC")
    assert Pldt([0], unit="us", tz=zone).to_physical().to_list() == [0]
    calls = []
    monkeypatch.setattr(Zone, "_unpickle", property(lambda self: calls.append("business lookup")))
    with pytest.raises(ValueError, match="encoded"):
        Pldt([0], unit="us", tz=zone)
    assert calls == []


def test_origin_cache_does_not_retain_a_business_owner():
    value = PassiveZone.no_cache("UTC")
    owner = weakref.ref(value)
    for _ in range(3):
        assert Pldt([0], unit="us", tz=value).to_physical().to_list() == [0]
    del value
    gc.collect()
    assert owner() is None


def test_origin_cache_uses_identity_without_business_hash_or_equality():
    calls = []

    class IdentityOnly(ZoneInfo):
        def __hash__(self):
            calls.append("hash")
            raise RuntimeError("business hash")

        def __eq__(self, other):
            calls.append("equality")
            raise RuntimeError("business equality")

    value = IdentityOnly.no_cache("UTC")
    for _ in range(3):
        assert Pldt([0], unit="us", tz=value).to_physical().to_list() == [0]
    assert calls == []


def test_expired_origin_entries_never_substitute_a_reused_address():
    for _ in range(140):
        named = PassiveZone.no_cache("UTC")
        assert Pldt([0], unit="us", tz=named).to_physical().to_list() == [0]
        del named
        source = file_zone(PassiveZone)
        with pytest.raises(ValueError, match="file|origin"):
            Pldt([0], unit="us", tz=source)
        del source
