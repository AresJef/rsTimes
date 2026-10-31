"""D01.O1/O2: native String execution keeps the adopted Pddt contracts."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from rstimes import Configs, Pddt


def _iteration_counter(monkeypatch):
    original = pl.Series.__iter__
    calls = []

    def observed(self):
        calls.append(self.name)
        return original(self)

    monkeypatch.setattr(pl.Series, "__iter__", observed)
    return calls


@pytest.mark.parametrize("chunked", [False, True])
def test_native_text_does_not_materialize_python_rows(monkeypatch, chunked):
    values = ["2024-01-02T12:34:56.123456789", None, "NaT", "2024-01-03"]
    source = pl.Series("source", values, dtype=pl.String)
    if chunked:
        source = pl.concat([source.slice(0, 2), source.slice(2)], rechunk=False)
    calls = _iteration_counter(monkeypatch)
    result = Pddt(source)
    assert calls == []
    assert result.name == "source" and result.unit == "ns"
    assert result.asi8.tolist() == [1704198896123456789, -(2**63), -(2**63), 1704240000000000000]
    assert result.isna().tolist() == [False, True, True, False]
    assert source.to_list() == values


@pytest.mark.parametrize("empty", [[], [None], ["", "NaT", "nan", None]])
def test_native_empty_and_missing_keep_unit_and_lazy_default(empty):
    source = pl.Series("missing", empty, dtype=pl.String)
    result = Pddt(source, default="not an independent date", tz="UTC")
    assert result.unit == Pddt(empty).unit
    assert result.name == "missing" and result.tz == timezone.utc
    assert result.isna().tolist() == [True] * len(empty)


@pytest.mark.parametrize("reference", [date(2024, 1, 2), datetime(2024, 1, 2), "2024-01-02"])
def test_native_independent_builtin_default(reference):
    result = Pddt(pl.Series("time", ["12:30", "18:45"]), default=reference)
    assert result.unit == "us"
    assert result.asi8.tolist() == [1704198600000000, 1704221100000000]


def test_native_custom_vocabulary_remains_live_between_calls(monkeypatch):
    cfg = Configs()
    cfg.add_month("harvést", 5)
    source = pl.Series("text", ["7 harvést 2024"] * 4)
    calls = _iteration_counter(monkeypatch)
    first = Pddt(source, cfg=cfg)
    cfg.set_month({"harvést": 6})
    second = Pddt(source, cfg=cfg)
    assert calls == []
    assert first.asi8.tolist() == [1715040000000000] * 4
    assert second.asi8.tolist() == [1717718400000000] * 4


@pytest.mark.parametrize("key, text, expected", [
    ("UTC", "2024-01-02 12:30 UTC", 1704198600000000),
    ("Asia/Shanghai", "2024-01-02 12:30 Asia/Shanghai", 1704169800000000),
])
def test_native_registered_zone_preserves_original_zoneinfo(key, text, expected):
    cfg = Configs()
    cfg.add_tzone(key)
    result = Pddt(pl.Series("zone", [text]), cfg=cfg)
    assert result.asi8.tolist() == [expected]
    assert isinstance(result.tz, ZoneInfo) and result.tz is ZoneInfo(key)


def test_native_dst_uses_existing_pddt_policy_and_complete_positions():
    cfg = Configs()
    cfg.add_tzone("America/New_York")
    source = pl.Series("zone", [None, "2024-11-03 01:30 America/New_York"])
    result = Pddt(source, cfg=cfg, ambiguous=[False, False])
    assert result.isna().tolist() == [True, False]
    assert result.asi8.tolist()[1] == 1730615400000000
    gap = pl.Series("zone", ["2024-03-10 02:30 America/New_York"])
    with pytest.raises(ValueError):
        Pddt(gap, cfg=cfg)
    assert Pddt(gap, cfg=cfg, nonexistent="NaT").isna().tolist() == [True]


@pytest.mark.parametrize("strict", [False, True])
def test_native_strict_and_explicit_unit_have_independent_answers(strict):
    source = pl.Series("text", ["2024-02-30"])
    if strict:
        with pytest.raises(ValueError, match="day|date"):
            Pddt(source, strict=True)
    else:
        assert Pddt(source).asi8.tolist() == [1709164800000000]
    with pytest.raises(ValueError, match="precision|loss|preserv"):
        Pddt(pl.Series(["2024-01-02T12:34:56.123456789"]), unit="us")
    zero = Pddt(pl.Series(["0000-01-01"]), unit="us")
    assert zero.year.tolist() == [0]


def test_native_error_keeps_real_index_and_bounded_input():
    text = "not a date " * 10000
    with pytest.raises(ValueError) as caught:
        Pddt(pl.Series("text", [None, text]))
    message = str(caught.value)
    assert "Pddt" in message and "data[1]" in message
    assert "not a date" in message and len(message) < 1500
    assert str(len(text)) in message


def test_callback_default_uses_original_once_only_live_path():
    cfg = Configs()
    calls = []

    class Reference(str):
        def __str__(self):
            calls.append("default")
            cfg.set_month({"jan": 2})
            return "14 Jan 2024"

    result = Pddt(pl.Series("text", ["12:30", "18:45"]),
                  cfg=cfg, default=Reference("reference"))
    assert calls == ["default"] and result.month.tolist() == [2, 2]
    assert result.day.tolist() == [14, 14]


def test_series_subclass_retains_its_real_iterator_and_live_cfg():
    cfg = Configs()
    calls = []

    class Source(pl.Series):
        def __iter__(self):
            calls.append("iterator")
            yield "14 Jan 2024"
            cfg.set_month({"jan": 2})
            yield "14 Jan 2024"

    result = Pddt(Source("source", ["ignored", "ignored"]), cfg=cfg)
    assert calls == ["iterator"] and result.month.tolist() == [1, 2]


@pytest.mark.parametrize("cfg", [0, object()])
def test_native_empty_still_validates_cfg(cfg):
    with pytest.raises(TypeError, match="cfg|Configs"):
        Pddt(pl.Series([], dtype=pl.String), cfg=cfg)


@pytest.mark.parametrize("container", [list, tuple])
@pytest.mark.parametrize("suffix", ["", " 🚀", " \ud800"])
def test_plain_text_collection_keeps_borrowed_unicode_and_missing(container, suffix):
    result = Pddt(container(["2024-01-02" + suffix, None, "NaT"]), unit="us")
    assert result.asi8.tolist() == [1704153600000000, -(2**63), -(2**63)]


@pytest.mark.parametrize("container", [list, tuple])
def test_plain_text_configuration_snapshot_is_per_call(container):
    cfg = Configs(dayfirst=True)
    source = container([None, "07/05/2024", "7 harvést 2024"])
    cfg.add_month("harvést", 5)
    first = Pddt(source, cfg=cfg)
    cfg.set_month({"harvést": 6})
    second = Pddt(source, cfg=cfg)
    assert first.asi8.tolist() == [-(2**63), 1715040000000000, 1715040000000000]
    assert second.asi8.tolist() == [-(2**63), 1715040000000000, 1717718400000000]


def test_default_callback_may_change_plain_list_before_real_row_iteration():
    cfg = Configs()
    calls = []

    class Row(str):
        def __str__(self):
            calls.append("row")
            cfg.set_month({"jan": 3})
            return "14 Jan 2024"

    source = ["14 Jan 2024", "14 Jan 2024"]

    class Reference(str):
        def __str__(self):
            calls.append("default")
            cfg.set_month({"jan": 2})
            source[1] = Row("second")
            return "2024-01-01"

    result = Pddt(source, cfg=cfg, default=Reference("reference"))
    assert calls == ["default", "row"] and result.month.tolist() == [2, 3]
