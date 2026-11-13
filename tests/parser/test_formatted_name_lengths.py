"""Independent formatted longest-name answers and live configuration lifecycle."""
import copy
from datetime import datetime, timedelta, timezone
import pickle
import polars as pl
import pytest
from rstimes import Configs, Pddt, Pldt, Pydt
from rstimes.errors import ConfigError

FMT = "%d %B %Y"


def _ticks(month):
    delta = datetime(2024, month, 14) - datetime(1970, 1, 1)
    return delta.days * 86_400_000_000_000


def _read(entry, text, cfg, fmt=FMT):
    if entry == "Pydt":
        return Pydt.strptime(text, fmt, cfg=cfg)
    if entry == "Pddt":
        return Pddt.strptime([text, None], fmt, unit="ns", cfg=cfg).asi8.tolist()
    if entry == "Pldt":
        return Pldt.strptime([text, None], fmt, unit="ns", cfg=cfg).to_physical().to_list()
    frame = pl.DataFrame({"text": [text, None]})
    options = {"tz": "UTC"} if "%Z" in fmt or "%z" in fmt else {}
    expr = pl.col("text").pldt.strptime(fmt, unit="ns", cfg=cfg, **options)
    return frame.select(expr).to_series().cast(pl.Int64).to_list()


@pytest.mark.parametrize("entry", ["Pydt", "Pddt", "Pldt", "Expr"])
@pytest.mark.parametrize("word,month", [("har", 2), ("harvest", 3), ("harvester", 4)])
def test_longest_registered_prefix_keeps_its_own_month(entry, word, month):
    cfg = Configs()
    cfg.set_month({"harvest": 3, "har": 2, "harvester": 4})
    actual = _read(entry, "14 " + word + " 2024", cfg)
    if entry == "Pydt":
        assert actual == Pydt(2024, month, 14)
    elif entry == "Pddt":
        assert actual == [_ticks(month), -(1 << 63)]
    else:
        assert actual == [_ticks(month), None]


@pytest.mark.parametrize("word", ["字", "éé", "𐐀𐐀", "a" * 128, "b" * 512])
def test_codepoint_lengths_and_long_aliases_preserve_answers(word):
    cfg = Configs()
    cfg.set_month({word: 10})
    assert Pydt.strptime("14 " + word + " 2024", FMT, cfg=cfg) == Pydt(2024, 10, 14)
    assert _read("Expr", "14 " + word + " 2024", cfg) == [_ticks(10), None]


@pytest.mark.parametrize("restore", [copy.copy, copy.deepcopy, lambda cfg: pickle.loads(pickle.dumps(cfg))])
def test_edits_and_copy_keep_old_expression_values(restore):
    cfg = Configs(yearfirst=False, dayfirst=True)
    cfg.set_month({"harvest": 10})
    saved = restore(cfg)
    old = pl.col("text").pldt.strptime(FMT, unit="ns", cfg=cfg)
    assert cfg.add_month("harvest", 11)
    new = pl.col("text").pldt.strptime(FMT, unit="ns", cfg=cfg)
    frame = pl.DataFrame({"text": ["14 harvest 2024", None]})
    assert frame.select(old).to_series().cast(pl.Int64).to_list() == [_ticks(10), None]
    assert frame.select(new).to_series().cast(pl.Int64).to_list() == [_ticks(11), None]
    assert Pydt.strptime("14 harvest 2024", FMT, cfg=saved) == Pydt(2024, 10, 14)
    assert not saved.yearfirst and saved.dayfirst


def test_delete_empty_default_and_reset_have_distinct_roles():
    cfg = Configs(yearfirst=False, dayfirst=True)
    cfg.set_month({"har": 2, "harvest": 10})
    assert cfg.del_month("harvest")
    assert Pydt.strptime("14 har 2024", FMT, cfg=cfg) == Pydt(2024, 2, 14)
    with pytest.raises(ValueError):
        Pydt.strptime("14 harvest 2024", FMT, cfg=cfg)
    cfg.set_month({})
    with pytest.raises(ValueError):
        Pydt.strptime("14 May 2024", FMT, cfg=cfg)
    cfg.set_month(None)
    assert Pydt.strptime("14 May 2024", FMT, cfg=cfg) == Pydt(2024, 5, 14)
    cfg.set_month({"harvest": 10})
    cfg.reset_settings()
    assert Pydt.strptime("14 May 2024", FMT, cfg=cfg) == Pydt(2024, 5, 14)
    assert not cfg.yearfirst and cfg.dayfirst


def test_invalid_edit_and_repeated_init_preserve_published_rules():
    cfg = Configs()
    cfg.set_month({"harvest": 10})
    before = pickle.dumps(cfg)
    with pytest.raises(ConfigError):
        cfg.add_month("2bad", 4)
    cfg.__init__()
    assert pickle.dumps(cfg) == before
    assert Pydt.strptime("14 harvest 2024", FMT, cfg=cfg) == Pydt(2024, 10, 14)


@pytest.mark.parametrize("entry", ["Pydt", "Pddt", "Pldt", "Expr"])
@pytest.mark.parametrize("namespace", ["utc", "tzoffset", "ampm", "weekday"])
def test_each_formatted_name_namespace_keeps_its_own_value(entry, namespace):
    cfg = Configs()
    cfg.set_month({"harvest": 10})
    expected = datetime(2024, 10, 14)
    if namespace == "utc":
        cfg.add_utc("zuluword")
        text, fmt = "14 harvest 2024 zuluword", "%d %B %Y %Z"
        expected = expected.replace(tzinfo=timezone.utc)
    elif namespace == "tzoffset":
        cfg.add_tzoffset("xst", hours=1)
        text, fmt = "14 harvest 2024 xst", "%d %B %Y %Z"
        expected = expected.replace(tzinfo=timezone(timedelta(hours=1)))
    elif namespace == "ampm":
        cfg.add_ampm("darkness", 1)
        text, fmt = "14 harvest 2024 03 darkness", "%d %B %Y %I %p"
        expected = expected.replace(hour=15)
    else:
        cfg.add_weekday("workday", 0)
        text, fmt = "workday 14 harvest 2024", "%A %d %B %Y"
    actual = _read(entry, text, cfg, fmt)
    if entry == "Pydt":
        assert actual == expected
    else:
        origin = datetime(1970, 1, 1, tzinfo=timezone.utc if expected.tzinfo else None)
        delta = expected - origin
        tick = (delta.days * 86_400 + delta.seconds) * 1_000_000_000
        assert actual == [tick, -(1 << 63) if entry == "Pddt" else None]


@pytest.mark.parametrize("count", [10, 11])
@pytest.mark.parametrize("entry", ["Pydt", "Pddt", "Pldt", "Expr"])
def test_long_name_table_boundary_keeps_every_complete_prefix(entry, count):
    cfg = Configs()
    words = ["a" * 128 + chr(97 + i) for i in range(count)]
    cfg.set_month({word: 10 for word in words})
    actual = _read(entry, "14 " + words[-1] + " 2024", cfg)
    if entry == "Pydt":
        assert actual == Pydt(2024, 10, 14)
    else:
        assert actual == [_ticks(10), -(1 << 63) if entry == "Pddt" else None]
