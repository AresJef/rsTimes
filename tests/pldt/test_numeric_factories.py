"""Independent epoch answers, clock counts and static numerical Expr contracts."""
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import importlib,time
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def ticks(value):
    return value.to_physical().to_list()


def test_four_quantities_keep_clock_and_instant_distinct():
    assert ticks(Pldt.fromseconds(0,size=1,tz="Asia/Shanghai")) == [-28_800_000_000]
    assert ticks(Pldt.frommicroseconds(0,size=1,tz="Asia/Shanghai")) == [-28_800_000_000]
    assert ticks(Pldt.fromtimestamp(0,size=1,tz="Asia/Shanghai")) == [0]
    result=Pldt.utcfromtimestamp(0,size=1)
    assert result.dtype==pl.Datetime("us","UTC") and ticks(result)==[0]


@pytest.mark.parametrize("value,unit,expected", [(1.5,"ms",1500),(1e-9,"ns",1),(-1e-9,"ns",-1),(9007199254740993,"ms",9007199254740993)])
def test_fixed_input_quantities_exact_integers_and_ns(value,unit,expected):
    result=Pldt.frommicroseconds(value*1000,size=1,unit=unit) if isinstance(value,int) else Pldt.fromseconds(value,size=1,unit=unit)
    assert ticks(result)==[expected]


@pytest.mark.parametrize("value", [True,np.bool_(False),"1.5",b"1",bytearray(b"1"),datetime(2024,1,1),np.datetime64(1,"ns"),np.timedelta64(1,"ns")])
def test_numeric_roles_reject_dates_bytes_and_boolean(value):
    with pytest.raises(TypeError):
        Pldt.fromseconds(value,size=1)


@pytest.mark.parametrize("value", [1.0,1.5,np.float32(1)])
def test_integer_microseconds_reject_finite_floats(value):
    with pytest.raises(TypeError):
        Pldt.frommicroseconds(value,size=1)


def test_quantities_missing_precision_capacity_and_scalar_read_once():
    assert ticks(Pldt.fromseconds([None,float("nan"),"NaT"]))==[None,None,None]
    with pytest.raises(ValueError,match="precision|unit|loss"):
        Pldt.fromseconds(1e-9,size=1,unit="us")
    with pytest.raises(OverflowError):
        Pldt.fromseconds(float("inf"),size=1)
    calls=[]
    class Number:
        def __float__(self):
            calls.append(1)
            return 1.5
    assert ticks(Pldt.fromseconds(Number(),size=3,unit="ms"))==[1500]*3
    assert calls==[1]
    assert ticks(Pldt.fromseconds(Decimal("1.5"),size=1,unit="ms"))==[1500]


def test_optional_pandas_missing_values_keep_independent_validity():
    pd=pytest.importorskip("pandas",reason="pandas missing-singleton integration requires optional pandas")
    result=Pldt.fromseconds([pd.NaT,pd.NA,None,np.datetime64("NaT")])
    assert result.dtype==pl.Datetime("us") and ticks(result)==[None]*4


def test_zero_size_validates_but_never_loads_local_or_clock(monkeypatch):
    module=importlib.import_module("rstimes.pldt")
    def forbidden():
        raise AssertionError("empty result must not load a local zone")
    monkeypatch.setattr(module,"_local_zone",forbidden)
    for method in (Pldt.now,Pldt.today,Pldt.utcnow):
        assert len(method(0,unit="ns"))==0
    assert Pldt.utcnow(0,unit="ns").dtype==pl.Datetime("ns","UTC")
    assert len(Pldt.fromtimestamp(0,size=0))==0
    assert ticks(Pldt.fromtimestamp([None,float("nan")]))==[None,None]
    with pytest.raises(TypeError):
        Pldt.fromtimestamp(True,size=0)


def test_now_today_and_literal_preserve_current_real_ns():
    before=time.time_ns()
    result=Pldt.utcnow(3,unit="ns",name="stamp")
    after=time.time_ns()
    assert result.dtype==pl.Datetime("ns","UTC")
    tolerance=max(1_000_000,int(time.get_clock_info("time").resolution*2_000_000_000))
    assert len(set(ticks(result)))==1 and before-tolerance<=ticks(result)[0]<=after+tolerance
    query=pl.DataFrame({"id":[1,2,3]}).lazy().select(pl.lit(result))
    assert ticks(query.collect()["stamp"])==ticks(result)
    assert ticks(query.collect()["stamp"])==ticks(result)
    local=Pldt.today(2,unit="ms")
    assert local.dtype==pl.Datetime("ms") and len(set(ticks(local)))==1
    assert abs(ticks(local)[0]-int(datetime.now().timestamp()*1000))<86_400_000


def test_static_numeric_expr_defaults_and_float_requires_unit():
    frame=pl.DataFrame({"seconds":[0,2,None]})
    query=frame.lazy().select(pl.col("seconds").pldt.fromseconds())
    assert query.collect_schema()["seconds"]==pl.Datetime("us")
    assert ticks(query.collect()["seconds"])==[0,2_000_000,None]
    frame=pl.DataFrame({"seconds":[1.5,1e-9,None]})
    with pytest.raises(pl.exceptions.ComputeError,match="unit"):
        frame.lazy().select(pl.col("seconds").pldt.fromseconds()).collect_schema()
    result=frame.select(pl.col("seconds").pldt.utcfromtimestamp(unit="ns"))["seconds"]
    assert result.dtype==pl.Datetime("ns","UTC")
    assert ticks(result)==[1_500_000_000,1,None]


def test_numeric_aggregate_scalar_naturally_broadcasts_and_keeps_group_scalar():
    frame=pl.DataFrame({"id":[1,2,3],"group":[1,1,2],"seconds":[1,2,3]})
    expr=pl.col("seconds").max().pldt.fromseconds()
    result=frame.select("id",expr)
    assert ticks(result["seconds"])==[3_000_000]*3
    result=frame.group_by("group",maintain_order=True).agg(expr)
    assert result.schema["seconds"]==pl.Datetime("us")
    assert ticks(result["seconds"])==[2_000_000,3_000_000]


def test_microsecond_float_nan_and_finite_are_distinct_in_expr():
    frame=pl.DataFrame({"us":[float("nan"),None]})
    expr=pl.col("us").pldt.frommicroseconds()
    assert frame.lazy().select(expr).collect_schema()["us"]==pl.Datetime("us")
    assert ticks(frame.select(expr)["us"])==[None,None]
    with pytest.raises(pl.exceptions.ComputeError,match="integer|float"):
        pl.DataFrame({"us":[1.0]}).select(expr)


def test_numeric_series_nulls_and_current_unit_full_minimum():
    source=pl.Series("seconds",[0.0,1.5,None])
    assert ticks(source.pldt.fromseconds(unit="ms",tz="UTC"))==[0,1500,None]
    value=2**63+192
    assert ticks(Pldt.frommicroseconds(np.array([value],dtype=np.uint64),unit="ms"))==[value//1000]
    result=Pldt.frommicroseconds([-(2**63)],unit="us")
    assert ticks(result)==[-(2**63)] and result.null_count()==0


def test_local_timestamp_expr_snapshots_zone_but_eager_loads_on_first_value(monkeypatch):
    module=importlib.import_module("rstimes.pldt")
    calls=[]
    def local():
        calls.append(1)
        return timezone(timedelta(hours=8))
    monkeypatch.setattr(module,"_local_zone",local)
    assert ticks(Pldt.fromtimestamp([None,0,1]))==[None,28_800_000_000,28_801_000_000]
    assert calls==[1]
    expr=pl.col("seconds").pldt.fromtimestamp()
    assert calls==[1,1]
    monkeypatch.setattr(module,"_local_zone",lambda:timezone.utc)
    frame=pl.DataFrame({"seconds":[0,1]})
    assert ticks(frame.select(expr)["seconds"])==[28_800_000_000,28_801_000_000]
    assert ticks(frame.select(expr)["seconds"])==[28_800_000_000,28_801_000_000]


def test_eager_generator_prepares_local_at_first_real_value_before_next_callback(monkeypatch):
    module=importlib.import_module("rstimes.pldt")
    calls=[]
    def local():
        calls.append("local")
        return timezone(timedelta(hours=8))
    def source():
        yield None
        assert calls==[]
        yield 0
        assert calls==["local"]
        yield 1
    monkeypatch.setattr(module,"_local_zone",local)
    assert ticks(Pldt.fromtimestamp(source()))==[None,28_800_000_000,28_801_000_000]
