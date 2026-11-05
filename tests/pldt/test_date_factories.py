"""Named real-date roles, local fields, source precision and static Expr schema."""
from datetime import date,datetime,timezone
from zoneinfo import ZoneInfo
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def ticks(value):
    return value.to_physical().to_list()


def tick(text,unit="us"):
    return int(np.datetime64(text,unit).astype(np.int64))


def test_named_datetime_replacement_differs_from_constructor_instant_conversion():
    source=datetime(2024,1,2,12,30,tzinfo=ZoneInfo("Asia/Shanghai"))
    assert ticks(Pldt.fromdatetime(source,size=1,tz="UTC"))==[tick("2024-01-02T12:30")]
    assert ticks(Pldt([source],tz="UTC"))==[tick("2024-01-02T04:30")]
    result=Pldt.fromdatetime(source,size=1)
    assert result.dtype==pl.Datetime("us","Asia/Shanghai") and ticks(result)==[tick("2024-01-02T04:30")]


def test_fromdate_uses_local_day_and_clears_clock_and_source_zone():
    source=datetime(2024,1,2,0,30,45,123456,tzinfo=ZoneInfo("Asia/Shanghai"))
    result=Pldt.fromdate(source,size=2)
    assert result.dtype==pl.Datetime("us") and ticks(result)==[tick("2024-01-02")]*2
    result=Pldt.fromdate([date(2024,1,2),None])
    assert result.dtype==pl.Datetime("ms") and ticks(result)==[tick("2024-01-02","ms"),None]


def test_native_datetime_ns_source_and_date_midnight_keep_declared_unit():
    source=pl.Series("time",[tick("2024-01-02T04:30:45.123456789","ns"),None],dtype=pl.Datetime("ns","Asia/Shanghai"))
    result=source.pldt.fromdate()
    assert result.dtype==pl.Datetime("ns") and ticks(result)==[tick("2024-01-02","ns"),None]
    result=source.pldt.fromdatetime(tz="UTC")
    assert result.dtype==pl.Datetime("ns","UTC") and ticks(result)==[tick("2024-01-02T12:30:45.123456789","ns"),None]
    with pytest.raises(ValueError,match="precision|loss"):
        Pldt.fromdatetime(source,unit="us")
    assert ticks(Pldt.fromdate(source,unit="ms"))==[tick("2024-01-02","ms"),None]


def test_aware_fold_preserved_without_target_but_replacement_uses_column_policy():
    source=datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=1)
    assert ticks(Pldt.fromdatetime(source,size=1))==[tick("2024-11-03T06:30")]
    with pytest.raises(ValueError,match="twice|ambiguous"):
        Pldt.fromdatetime(source,size=1,tz="America/New_York")
    assert ticks(Pldt.fromdatetime(source,size=1,tz="America/New_York",ambiguous=True))==[tick("2024-11-03T05:30")]


@pytest.mark.parametrize("method,source",[("fromdate","2024-01-02"),("fromdate",np.datetime64("2024-01-02")),("fromdatetime",date(2024,1,2)),("fromdatetime64",datetime(2024,1,2)),("fromdatetime64",pl.Series([0],dtype=pl.Datetime("us")))])
def test_named_factories_do_not_widen_to_parse(method,source):
    with pytest.raises(TypeError):
        getattr(Pldt,method)(source,size=1)


@pytest.mark.parametrize("unit",["Y","M","W","D","h","m","s","ms","us","ns"])
def test_numpy_date_units_are_decoded_as_dates_without_python_datetime(unit):
    source=np.array([np.datetime64("2024-01-02T12:34:56.123456789",unit),np.datetime64("NaT",unit)])
    chosen={"ms":"ms","us":"us","ns":"ns"}.get(unit,"ms")
    expected=int(source[0].astype(f"datetime64[{chosen}]").astype(np.int64))
    result=Pldt.fromdatetime64(source)
    assert result.dtype==pl.Datetime(chosen) and ticks(result)==[expected,None]


def test_numpy_multiplier_ns_precision_and_nat_source_metadata():
    source=np.array([1,2],dtype=np.int64).view("datetime64[3ms]")
    assert ticks(Pldt.fromdatetime64(source))==[3,6]
    source=np.datetime64("2024-01-02T12:30:45.123456789","ns")
    assert ticks(Pldt.fromdatetime64(source,size=1,tz="Asia/Shanghai"))==[tick("2024-01-02T04:30:45.123456789","ns")]
    assert Pldt.fromdatetime64(np.datetime64("NaT","ns"),size=1).dtype==pl.Datetime("ns")


def test_empty_typed_metadata_and_scalar_aware_size_zero():
    source=pl.Series("time",[],dtype=pl.Datetime("ns","UTC"))
    assert Pldt.fromdatetime(source).dtype==pl.Datetime("ns","UTC")
    assert Pldt.fromdate(source).dtype==pl.Datetime("ns")
    source=datetime(2024,1,2,tzinfo=ZoneInfo("Asia/Shanghai"))
    assert Pldt.fromdatetime(source,size=0).dtype==pl.Datetime("us","Asia/Shanghai")


def test_real_typed_date_expr_schema_and_distinct_replace_meaning():
    source=pl.Series("time",[tick("2024-01-02T04:30"),None],dtype=pl.Datetime("us","Asia/Shanghai"))
    frame=pl.DataFrame(source)
    expr=pl.col("time").pldt.fromdatetime(tz="UTC")
    assert frame.lazy().select(expr).collect_schema()["time"]==pl.Datetime("us","UTC")
    assert ticks(frame.select(expr)["time"])==[tick("2024-01-02T12:30"),None]
    assert ticks(frame.select(pl.col("time").pldt.fromdate())["time"])==[tick("2024-01-02"),None]
    with pytest.raises(pl.exceptions.ComputeError,match="Datetime|datetime"):
        pl.DataFrame({"day":pl.Series([date(2024,1,2)])}).select(pl.col("day").pldt.fromdatetime())


def test_numpy_factory_is_not_fabricated_on_polars_namespaces():
    assert not hasattr(pl.Series([0],dtype=pl.Datetime("us")).pldt,"fromdatetime64")
    assert not hasattr(pl.col("time").pldt,"fromdatetime64")


def test_pandas_native_date_roles_keep_metadata_and_final_capacity():
    pd=pytest.importorskip("pandas")
    from datetime import timedelta
    source=pd.DatetimeIndex([pd.Timestamp("2024-01-02 12:30:45.123456789",tz="Asia/Shanghai"),pd.NaT],name="time")
    assert ticks(Pldt.fromdatetime(source))==source.asi8.tolist()[:1]+[None]
    result=Pldt.fromdate(source,unit="ms")
    assert result.name=="time" and ticks(result)==[tick("2024-01-02","ms"),None]
    assert ticks(Pldt.fromdatetime(source,tz="UTC"))==[tick("2024-01-02T12:30:45.123456789","ns"),None]
    assert Pldt.fromdatetime(source[:0]).dtype==pl.Datetime("ns","Asia/Shanghai")
    assert Pldt.fromdate(source[:0]).dtype==pl.Datetime("ns")
    fixed=timezone(timedelta(hours=5,minutes=30))
    values=pd.DatetimeIndex([datetime(2024,1,2,12,30,tzinfo=fixed)])
    assert Pldt.fromdate(values).dtype==pl.Datetime(values.unit)
    assert ticks(Pldt.fromdate(values))==[tick("2024-01-02",values.unit)]
    assert ticks(Pldt.fromdatetime(values,tz="UTC"))==[tick("2024-01-02T12:30",values.unit)]
    with pytest.raises(ValueError,match="represented|supported"):
        Pldt.fromdatetime(values)


def test_native_date_midnight_does_not_overflow_a_discarded_clock():
    pd=pytest.importorskip("pandas")
    source=pd.DatetimeIndex(np.array([9_223_372_036_854_776],dtype=np.int64).view("datetime64[s]"))
    # The original second count cannot be represented as milliseconds. Its local
    # midnight can, so the fromdate role must floor before final unit narrowing.
    expected=(9_223_372_036_854_776//86400)*86400*1000
    assert expected <= (1<<63)-1
    assert ticks(Pldt.fromdate(source))==[expected]
