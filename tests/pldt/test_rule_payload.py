"""Immutable library templates and explicit rule replacements cross native workers."""
from datetime import datetime, timezone
import copy
import io

import polars as pl
from polars.plugins import register_plugin_function
import pytest

from rstimes import Configs, Pldt  # Loading the public class registers .pldt.
import rstimes._native as native
from pathlib import Path


def test_unmodified_library_tables_use_versioned_values_not_expanded_copies():
    prepared = native._pldt_prepare_text(cfg=Configs()).plugin_kwargs()
    assert prepared["rules"] == {
        "version": 2, "tables": [None] * 8,
        "regions": [], "flags": (True, False),
    }


@pytest.mark.parametrize("engine", ["auto", "streaming"])
def test_flags_remain_snapshot_values_when_the_tables_are_builtin(engine):
    cfg = Configs(yearfirst=False, dayfirst=True)
    expr = pl.col("text").pldt.parse(unit="us", cfg=cfg)
    cfg.__init__(yearfirst=False, dayfirst=False)
    new = pl.col("text").pldt.parse(unit="us", cfg=cfg)
    frame = pl.LazyFrame({"text": ["07/05/2024", None]})
    assert frame.select(expr).collect(engine=engine)["text"].to_list() == [datetime(2024, 5, 7), None]
    assert frame.select(new).collect(engine=engine)["text"].to_list() == [datetime(2024, 7, 5), None]


@pytest.mark.parametrize("engine", ["auto", "streaming"])
def test_changed_table_survives_source_edits_and_native_expression_serialization(engine):
    cfg = Configs()
    cfg.add_month("harvest", 10)
    payload = native._pldt_prepare_text(cfg=cfg).plugin_kwargs()["rules"]
    assert payload["tables"][4] is not None
    assert all(value is None for i, value in enumerate(payload["tables"]) if i != 4)
    expr = pl.col("text").pldt.parse(unit="us", cfg=cfg)
    restored = pl.Expr.deserialize(io.BytesIO(expr.meta.serialize()))
    cfg.set_month({"harvest": 11})
    del cfg
    frame = pl.LazyFrame({"text": ["14 harvest 2024", None]})
    for candidate in (expr, copy.copy(expr), restored):
        assert frame.select(candidate).collect(engine=engine)["text"].to_list() == [datetime(2024, 10, 14), None]


def test_explicit_empty_table_does_not_restore_library_words():
    cfg = Configs()
    cfg.set_month({})
    payload = native._pldt_prepare_text(cfg=cfg).plugin_kwargs()["rules"]
    assert payload["tables"][4] == []
    expr = pl.col("text").pldt.parse(unit="us", cfg=cfg)
    with pytest.raises(pl.exceptions.ComputeError):
        pl.DataFrame({"text": ["14 Jan 2024"]}).select(expr)
    assert pl.DataFrame({"text": ["2024-01-14"]}).select(expr)["text"].to_list() == [datetime(2024, 1, 14)]


def test_regions_remain_explicit_values_alongside_builtin_tables():
    cfg = Configs()
    cfg.add_tzone("America/New_York")
    payload = native._pldt_prepare_text(cfg=cfg).plugin_kwargs()["rules"]
    assert payload["tables"] == [None] * 8
    assert len(payload["regions"]) == 1
    expr = pl.col("text").pldt.parse(unit="us", cfg=cfg, tz="UTC")
    cfg.del_tzone("America/New_York")
    out = pl.DataFrame({"text": ["2024-01-07 12:00 America/New_York"]}).select(expr)["text"]
    assert out.to_list() == [datetime(2024, 1, 7, 17, tzinfo=timezone.utc)]


@pytest.mark.parametrize("version", [0, 3, 77])
def test_unknown_rule_snapshot_version_is_rejected_at_the_native_boundary(version):
    prepared = native._pldt_prepare_text(cfg=Configs()).plugin_kwargs()
    prepared["rules"]["version"] = version
    expr = register_plugin_function(
        plugin_path=Path(native.__file__), function_name="pldt_parse",
        args=[pl.col("text")], kwargs={"version": 1, "unit": "us", "prepared": prepared},
        is_elementwise=True,
    )
    with pytest.raises(pl.exceptions.ComputeError, match="vocabulary snapshot version must be 2"):
        pl.DataFrame({"text": ["2024-01-02"]}).select(expr)
