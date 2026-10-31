"""Dedicated ISO grammar: strict fields, complete text, original precision."""
from datetime import datetime
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def ticks(value):return value.to_physical().to_list()
def tick(text,unit="us"):return int(np.datetime64(text,unit).astype(np.int64))


@pytest.mark.parametrize("text,expected",[("2024-01-02","2024-01-02"),("20240102","2024-01-02"),("2020-W53-7","2021-01-03"),("2024-002","2024-01-02"),("2024-01-02x12:30","2024-01-02T12:30"),("2024-01-02T12:30.5","2024-01-02T12:30:00.5"),("0000-01-01","0000-01-01"),("12000-01-02","12000-01-02")])
def test_shared_iso_grammar_and_wide_calendar(text,expected):
    assert ticks(Pldt.fromisoformat(text,size=1))==[tick(expected)]


@pytest.mark.parametrize("text",["2024-02-30","2021-W53-7","2023-366","Jan 2 2024","2024-01-02 extra","-001-01-01","2024-01-02T25:00"])
def test_iso_is_strict_and_does_not_use_convenient_upper_clamps(text):
    with pytest.raises(ValueError):Pldt.fromisoformat(text,size=1)


def test_iso_fraction_width_default_and_final_explicit_precision():
    assert Pldt.fromisoformat("2024-01-02T00:00:00.123456000",size=1).dtype==pl.Datetime("ns")
    result=Pldt.fromisoformat("2024-01-02T12:30:00.1234567899999",size=1)
    assert ticks(result)==[tick("2024-01-02T12:30:00.123456789","ns")]
    with pytest.raises(ValueError,match="precision|loss"):
        Pldt.fromisoformat("2024-01-02T00:00:00.123456789",size=1,unit="us")
    assert Pldt.fromisoformat([]).dtype==pl.Datetime("ms")
    assert Pldt.fromisoformat([None,"NaT",float("nan")]).dtype==pl.Datetime("ms")


def test_iso_source_offsets_are_instants_but_naive_target_is_local():
    result=Pldt.fromisoformat(["2024-01-02T12:30+08:00","2024-01-02T04:30Z"],tz="UTC")
    assert result.dtype==pl.Datetime("us","UTC") and ticks(result)==[tick("2024-01-02T04:30")]*2
    assert ticks(Pldt.fromisoformat("2024-01-02T12:30+05:30",size=1,tz="UTC"))==[tick("2024-01-02T07:00")]
    assert ticks(Pldt.fromisoformat("2024-01-02T12:30",size=1,tz="Asia/Shanghai"))==[tick("2024-01-02T04:30")]
    with pytest.raises(ValueError,match="represented|supported"):
        Pldt.fromisoformat("2024-01-02T12:30+05:30",size=1)


def test_iso_new_target_region_uses_column_strategy():
    with pytest.raises(ValueError,match="exist|gap"):
        Pldt.fromisoformat("2024-03-10T02:30",size=1,tz="America/New_York")
    assert ticks(Pldt.fromisoformat("2024-03-10T02:30",size=1,tz="America/New_York",nonexistent="shift_forward"))==[tick("2024-03-10T07:00")]


def test_iso_only_text_and_explicit_missing_sources_and_shape():
    with pytest.raises(TypeError):Pldt.fromisoformat(datetime(2024,1,2),size=1)
    with pytest.raises(TypeError):Pldt.fromisoformat(1,size=1)
    with pytest.raises(ValueError,match="size"):Pldt.fromisoformat("2024-01-02")
    with pytest.raises(ValueError,match="size"):Pldt.fromisoformat(["2024-01-02"],size=1)
    with pytest.raises(ValueError,match="size"):Pldt.fromisoformat(pl.Series(["2024-01-02"]),size=1)
    assert Pldt.fromisoformat("2024-01-02",size=0).len()==0


def test_iso_native_series_expr_static_schema_and_no_hidden_timezone():
    frame=pl.DataFrame({"text":["2024-01-02T12:30:00.123456789",None]})
    result=frame["text"].pldt.fromisoformat()
    assert result.dtype==pl.Datetime("ns")
    expr=pl.col("text").pldt.fromisoformat(unit="ns")
    assert frame.lazy().select(expr).collect_schema()["text"]==pl.Datetime("ns")
    assert ticks(frame.select(expr)["text"])==ticks(result)
    with pytest.raises(pl.exceptions.ComputeError,match="unit"):
        frame.lazy().select(pl.col("text").pldt.fromisoformat()).collect_schema()
    with pytest.raises(pl.exceptions.ComputeError,match="tz|timezone"):
        pl.DataFrame({"text":["2024-01-02T12:30Z"]}).select(expr)
