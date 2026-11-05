"""D01/D02 native worker boundary via the official SDK, before W13 public wiring."""
from pathlib import Path
from datetime import datetime
import gc

import polars as pl
from polars.plugins import register_plugin_function
import pytest

from rstimes import Configs
import rstimes._native as native


def expression(source=None, *, unit="us", **options):
    context = native._pldt_prepare_text(**options)
    return register_plugin_function(
        plugin_path=Path(native.__file__), function_name="pldt_parse",
        args=[pl.col("text") if source is None else source],
        kwargs={"version": 1, "unit": unit, "prepared": context.plugin_kwargs()},
        is_elementwise=True,
    )


def epoch_ns(value):
    elapsed = value - datetime(1970, 1, 1)
    return (elapsed.days * 86400 + elapsed.seconds) * 10**9 + elapsed.microseconds * 1000


@pytest.mark.parametrize("engine", ["auto", "streaming"])
def test_worker_reads_utf8_multi_chunk_slices_and_full_fraction(engine, monkeypatch):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("Python parse")
        raise AssertionError("native workers must not call Python parser functions")
    for name in ("parse", "parse_str", "parse_to_epoch"):
        monkeypatch.setattr(native, name, forbidden)
    data = pl.concat([
        pl.Series("text", ["unused", "14 février 2024", "2024-01-02 12:34:56.123456789"]),
        pl.Series("text", [None, "NaT", "2024年5月7日", "unused"]),
    ], rechunk=False).slice(1, 5)
    out = pl.DataFrame(data).lazy().select(expression(unit="ns")).collect(engine=engine)["text"]
    assert out.dtype == pl.Datetime("ns")
    assert out.cast(pl.Int64).to_list() == [
        epoch_ns(datetime(2024, 2, 14)), epoch_ns(datetime(2024, 1, 2, 12, 34, 56, 123456)) + 789,
        None, None, epoch_ns(datetime(2024, 5, 7)),
    ]
    assert calls == []


def test_worker_configuration_snapshot_and_default_callbacks_are_not_replayed():
    cfg = Configs()
    calls = []
    class Reference(str):
        def __str__(self):
            calls.append("default")
            cfg.set_month({"jan": 2})
            return "14 Jan 2024"
    old = expression(default=Reference("ignored"), cfg=cfg)
    new = expression(default="14 Jan 2024", cfg=cfg)
    cfg.set_month({"jan": 8})
    del cfg
    gc.collect()
    lf = pl.LazyFrame({"text": ["12:30", None]})
    for _ in range(2):
        a = lf.select(old).collect()["text"]
        b = lf.select(new).collect()["text"]
        assert a.to_list() == [datetime(2024, 1, 14, 12, 30), None]
        assert b.to_list() == [datetime(2024, 2, 14, 12, 30), None]
    assert calls == ["default"]


def test_worker_explicit_config_changes_ordinary_grammar_and_missing_is_exact():
    cfg = Configs()
    cfg.add_month("收获月", 10)
    expr = expression(cfg=cfg)
    out = pl.DataFrame({"text": ["14 收获月 2024", "", "NAN", None]}).select(expr)["text"]
    assert out.to_list() == [datetime(2024, 10, 14), None, None, None]
    with pytest.raises(pl.exceptions.ComputeError, match="row.*NaT"):
        pl.DataFrame({"text": [" NaT "]}).select(expr)


@pytest.mark.parametrize("isoformat", [True, False])
def test_worker_zero_year_and_option_precedence_are_shared(isoformat):
    out = pl.DataFrame({"text": ["0000-01-01"]}).select(expression(isoformat=isoformat))["text"]
    assert out.cast(pl.Int64).to_list() == [-62167219200000000]


def test_worker_strict_errors_and_explicit_unit_precision_are_not_coerced():
    frame = pl.DataFrame({"text": ["2024-02-30"]})
    assert frame.select(expression())["text"].to_list() == [datetime(2024, 2, 29)]
    with pytest.raises(pl.exceptions.ComputeError, match="day.*30"):
        frame.select(expression(strict=True))
    with pytest.raises(pl.exceptions.ComputeError, match="precision"):
        pl.DataFrame({"text": ["2024-01-02 12:34:56.123456789"]}).select(expression(unit="us"))
    with pytest.raises(pl.exceptions.ComputeError, match="explicit output tz"):
        pl.DataFrame({"text": ["2024-01-02T12:34Z"]}).select(expression())
    with pytest.raises(pl.exceptions.ComputeError, match="not registered"):
        pl.DataFrame({"text": ["2024-01-02 Asia/Shanghai"]}).select(expression())


def test_worker_empty_typed_string_schema_and_expression_default_validation():
    expr = expression(unit="ns")
    lf = pl.DataFrame({"text": pl.Series([], dtype=pl.String)}).lazy().select(expr)
    assert lf.collect_schema()["text"] == pl.Datetime("ns")
    assert lf.collect()["text"].is_empty()
    with pytest.raises(ValueError):
        expression(default="May 7")
