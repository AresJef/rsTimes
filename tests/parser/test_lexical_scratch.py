"""Shared lexical storage must not leak a prior row into later parsing."""
import polars as pl
import pytest

from rstimes import Configs, Pddt, Pldt


def _inputs():
    cfg = Configs()
    cfg.add_tzone("UTC")
    cfg.add_month("harvést", 5)
    values = [
        "14 février 2024" + " " * 4096 + "UTC",
        "2024-01-02T12:34:56.123456789",
        None,
        "NaT",
        "7 harvést 2024",
        "15 March 2024 [UTC]",
    ]
    expected = [1707868800000000000, 1704198896123456789, None, None,
                1715040000000000000, 1710460800000000000]
    return cfg, values, expected


@pytest.mark.parametrize("cls", [Pddt, Pldt])
@pytest.mark.parametrize("container", [list, tuple, pl.Series])
def test_calendar_and_ns_survive_long_unicode_regions_and_missing_rows(cls, container):
    cfg, values, expected = _inputs()
    result = cls(container(values), unit="ns", tz="UTC", cfg=cfg)
    if cls is Pddt:
        assert result.asi8.tolist() == [-(2**63) if value is None else value
                                      for value in expected]
    else:
        assert result.to_physical().to_list() == expected


@pytest.mark.parametrize("engine", ["auto", "streaming"])
def test_native_expr_reuses_grammar_without_retaining_previous_region(engine):
    cfg, values, expected = _inputs()
    source = pl.concat([pl.Series("text", values[:3]),
                        pl.Series("text", values[3:])], rechunk=False)
    frame = pl.DataFrame(source).lazy().select(
        pl.col("text").pldt.parse(unit="ns", tz="UTC", cfg=cfg))
    result = frame.collect(engine=engine)["text"]
    assert result.to_physical().to_list() == expected
