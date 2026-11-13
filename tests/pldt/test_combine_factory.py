"""Date/clock composition has one native final construction and strict roles."""
from datetime import date,datetime,time,timezone,timedelta
from zoneinfo import ZoneInfo
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def ticks(value):
    return value.to_physical().to_list()


def tick(text,unit="us"):
    return int(np.datetime64(text,unit).astype(np.int64))


def test_date_and_clock_roles_are_independent():
    result=Pldt.combine([date(2024,1,2),None],time(12,30))
    assert result.dtype==pl.Datetime("us") and ticks(result)==[tick("2024-01-02T12:30"),None]
    source=datetime(2000,5,7,12,34,56,123456,tzinfo=ZoneInfo("Asia/Shanghai"))
    assert ticks(Pldt.combine(date(2024,1,2),source,size=1))==[tick("2024-01-02T04:34:56.123456")]
    assert ticks(Pldt.combine(date(2024,1,2),source,size=1,tz="UTC"))==[tick("2024-01-02T12:34:56.123456")]
    assert ticks(Pldt.combine(datetime(2024,1,2,0,1,tzinfo=ZoneInfo("Asia/Shanghai")),time(12),size=1))==[tick("2024-01-02T12")]


def test_none_defaults_differ_from_missing_elements_and_all_missing():
    assert ticks(Pldt.combine([date(2024,1,2)],None))==[tick("2024-01-02")]
    assert ticks(Pldt.combine([date(2024,1,2)],[None]))==[None]
    assert ticks(Pldt.combine(None,[None,None]))==[None,None]
    assert Pldt.combine(None,[],unit="ns").dtype==pl.Datetime("ns")
    assert Pldt.combine(None,time(0),size=0).len()==0


def test_native_time_ns_real_precision_default_and_fixed_output_unit():
    dates=pl.Series("day",[date(2024,1,2),date(2024,1,3)],dtype=pl.Date)
    clocks=pl.Series("clock",[12*3600*10**9+123456789,None],dtype=pl.Time)
    result=Pldt.combine(dates,clocks)
    assert result.dtype==pl.Datetime("ns") and ticks(result)==[tick("2024-01-02T12:00:00.123456789","ns"),None]
    with pytest.raises(ValueError,match="loss|precision"):
        Pldt.combine(dates,clocks,unit="us")
    aligned=pl.Series("clock",[123456000],dtype=pl.Time)
    assert Pldt.combine(date(2024,1,2),aligned).dtype==pl.Datetime("us")


def test_native_time_rejects_invalid_clock_even_for_null_dates():
    raw=np.array([1],dtype=np.int64)
    clock=pl.Series("clock",raw).cast(pl.Time)
    raw[0]=-1
    assert clock.to_physical().to_list()==[-1]
    with pytest.raises(ValueError,match="day|clock"):
        Pldt.combine([None],clock)
    frame=pl.DataFrame({"day":[None],"clock":clock})
    with pytest.raises(pl.exceptions.ComputeError,match="day|clock"):
        frame.select(pl.col("day").pldt.combine(pl.col("clock"),unit="us"))


def test_combined_clock_not_its_source_date_drives_dst_strategy():
    source=time(1,30,tzinfo=ZoneInfo("America/New_York"),fold=1)
    with pytest.raises(ValueError,match="twice|ambiguous"):
        Pldt.combine(date(2024,11,3),source,size=1)
    assert ticks(Pldt.combine(date(2024,11,3),source,size=1,ambiguous=False))==[tick("2024-11-03T06:30")]
    with pytest.raises(ValueError,match="exist|gap"):
        Pldt.combine(date(2024,3,10),time(2,30),size=1,tz="America/New_York")
    assert ticks(Pldt.combine(date(2024,3,10),time(2,30),size=1,tz="America/New_York",nonexistent="shift_forward"))==[tick("2024-03-10T07:00")]


def test_empty_and_all_missing_typed_clock_timezone_metadata():
    source=pl.Series("clock",[],dtype=pl.Datetime("ns","UTC"))
    result=Pldt.combine(date(2024,1,2),source)
    assert result.dtype==pl.Datetime("us","UTC") and len(result)==0
    source=pl.Series("clock",[None],dtype=pl.Datetime("ns","UTC"))
    assert Pldt.combine([None],source).dtype==pl.Datetime("us","UTC")
    assert Pldt.combine([None],source,tz="Asia/Shanghai").dtype==pl.Datetime("us","Asia/Shanghai")


def test_clock_numeric_seconds_and_text_parser_roles():
    assert ticks(Pldt.combine("2024-01-02",3661,size=1))==[tick("2024-01-02T01:01:01")]
    assert ticks(Pldt.combine("2024-01-02","12:34:56.123456789",size=1))==[tick("2024-01-02T12:34:56.123456789","ns")]
    assert ticks(Pldt.combine("2024-01-02",np.datetime64("2000-01-01T12:34:56.123456789","ns"),size=1))==[tick("2024-01-02T12:34:56.123456789","ns")]
    with pytest.raises(TypeError):
        Pldt.combine(time(12),time(12),size=1)
    with pytest.raises(TypeError):
        Pldt.combine(date(2024,1,2),True,size=1)


def test_combine_shape_and_scalar_known_precision():
    with pytest.raises(ValueError,match="length|scalar"):
        Pldt.combine([date(2024,1,2)],[time(12),time(13)])
    pd=pytest.importorskip("pandas")
    source=pd.Timestamp("2000-01-01 12:34:56.123456789",tz="UTC")
    result=Pldt.combine([],source)
    assert result.dtype==pl.Datetime("ns","UTC")


def test_native_combine_expr_schema_and_true_scalar_broadcast():
    frame=pl.DataFrame({"day":pl.Series([date(2024,1,2),date(2024,1,3)]),"clock":pl.Series([1,None],dtype=pl.Time)})
    with pytest.raises(pl.exceptions.ComputeError,match="unit"):
        frame.lazy().select(pl.col("day").pldt.combine(pl.col("clock"))).collect_schema()
    expr=pl.col("day").pldt.combine(pl.col("clock"),unit="ns")
    assert frame.lazy().select(expr).collect_schema()["day"]==pl.Datetime("ns")
    assert ticks(frame.select(expr)["day"])==[tick("2024-01-02","ns")+1,None]
    assert ticks(frame.select(pl.col("day").pldt.combine(time(12)))["day"])==[tick("2024-01-02T12"),tick("2024-01-03T12")]
    assert ticks(frame.select(pl.col("day").pldt.combine(pl.lit(None,dtype=pl.Time),unit="us"))["day"])==[None,None]
    result=frame.select(pl.lit(date(2024,1,2)).pldt.combine(pl.col("clock"),unit="ns"))
    assert ticks(result.to_series())==[tick("2024-01-02","ns")+1,None]


def test_valid_minimum_is_not_a_missing_sentinel_and_components_can_cancel():
    value=-(1<<63)
    source=pl.Series("time",[value,None],dtype=pl.Datetime("ms"))
    result=Pldt.combine(source,source,unit="ms")
    assert ticks(result)==[value,None]


def test_today_is_looked_up_only_for_a_needed_row_and_external_errors_survive(monkeypatch):
    import rstimes.pldt as module
    calls=[]
    def local():
        calls.append(1)
        return ZoneInfo("UTC")
    monkeypatch.setattr(module,"_local_zone",local)
    assert len(Pldt.combine(None,[],unit="ns"))==0 and calls==[]
    assert ticks(Pldt.combine(None,[None,None]))==[None,None] and calls==[]
    result=Pldt.combine(None,[time(12),time(13)])
    assert len(result)==2 and calls==[1]
    error=RuntimeError("original local source failure")
    def broken():
        raise error
    monkeypatch.setattr(module,"_local_zone",broken)
    with pytest.raises(RuntimeError) as captured:
        Pldt.combine(None,time(12),size=1)
    assert captured.value is error


def test_prepared_clock_expr_snapshots_objects_and_preserves_ns_and_zones():
    pd=pytest.importorskip("pandas")
    frame=pl.DataFrame({"day":pl.Series([date(2024,1,2),date(2024,1,3)])})
    clocks=[pd.Timestamp("2000-05-07 12:34:56.123456789",tz="Asia/Shanghai"),None]
    expr=pl.col("day").pldt.combine(clocks)
    clocks[0]=time(1)
    assert frame.lazy().select(expr).collect_schema()["day"]==pl.Datetime("ns","Asia/Shanghai")
    assert ticks(frame.select(expr)["day"])==[tick("2024-01-02T04:34:56.123456789","ns"),None]
    # Concrete clock values are prepared eagerly and may supply known metadata.
    expr=pl.col("day").pldt.combine([pd.Timestamp("2000-05-07 12:34:56.123456789",tz="Asia/Shanghai"),None],tz="UTC")
    assert ticks(frame.select(expr)["day"])==[tick("2024-01-02T12:34:56.123456789","ns"),None]
