"""G01-G03 exact native arithmetic and real, host-only temporal protocols."""
from datetime import datetime,timedelta,date,timezone
import operator
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt,Delta


def ticks(value):return value.to_physical().to_list()
def tick(text,unit="ns"):return int(np.datetime64(text,unit).astype(np.int64))
def source(unit="ns",zone=None):return Pldt(["2024-01-31T12:34:56.123456789",None],unit=unit,tz=zone,name="time")


@pytest.mark.parametrize("delta,expected",[
    (Delta(months=1),"2024-02-29T12:34:56.123456789"),
    (Delta(days=1),"2024-02-01T12:34:56.123456789"),
    (Delta(day=1),"2024-01-01T12:34:56.123456789"),
    (Delta(hour=0),"2024-01-31T00:34:56.123456789"),
    (Delta(microseconds=1),"2024-01-31T12:34:56.123457789"),
    (Delta(microseconds=.001),"2024-01-31T12:34:56.123456790"),
    (Delta(nanoseconds=1),"2024-01-31T12:34:56.123456790"),
    (Delta(millisecond=1),"2024-01-31T12:34:56.001000000"),
    (Delta(microsecond=1),"2024-01-31T12:34:56.000001000"),
    (Delta(microsecond=0),"2024-01-31T12:34:56.000000000"),
    (Delta(nanosecond=2),"2024-01-31T12:34:56.123456002"),
    (Delta(month=2,months=1,day=31),"2024-03-31T12:34:56.123456789"),
    (Delta(weekday=0),"2024-01-29T12:34:56.123456789"),
])
def test_full_delta_fields_and_exact_ns_have_independent_answers(delta,expected):
    x=source();want=[tick(expected),None]
    for value in (x+delta,delta+x,x.pldt.add_delta(delta),pl.Series(x).pldt.add_delta(delta)):
        assert isinstance(value,Pldt)
        assert value.dtype==x.dtype and value.name=="time" and ticks(value)==want
    expr=pl.col("time").pldt.add_delta(delta)
    query=pl.DataFrame(x).lazy().select(expr)
    assert isinstance(expr,pl.Expr) and query.collect_schema()["time"]==x.dtype
    assert ticks(query.collect()["time"])==want


def test_subtract_relative_sign_but_absolute_targets_are_not_negated():
    x=source()
    assert ticks(x-Delta(months=1))==[tick("2023-12-31T12:34:56.123456789"),None]
    assert ticks(x-Delta(day=1))==[tick("2024-01-01T12:34:56.123456789"),None]
    assert ticks(x-Delta(nanoseconds=1))==[tick("2024-01-31T12:34:56.123456788"),None]
    assert ticks(pl.DataFrame(x).select(pl.col("time").pldt.sub_delta(Delta(nanoseconds=1)))["time"])==[tick("2024-01-31T12:34:56.123456788"),None]
    with pytest.raises(TypeError):Delta(months=1)-x


def test_delta_vectors_are_strict_and_snapshot_concrete_native_values():
    x=Pldt(["2024-01-31","2024-02-29"],unit="ns",name="time")
    deltas=[Delta(months=1),Delta(months=2)]
    want=[tick("2024-02-29"),tick("2024-04-29")]
    for values in [deltas,tuple(deltas),np.array(deltas,dtype=object),pl.Series("d",deltas,dtype=pl.Object),(d for d in deltas)]:
        assert ticks(x+values)==want
    expr=pl.col("time").pldt.add_delta(deltas)
    deltas[0]=Delta(days=1)
    assert ticks(pl.DataFrame(x).lazy().select(expr).collect()["time"])==want
    for values in [[Delta()],[Delta(),None],[Delta(),timedelta(1)]]:
        with pytest.raises((TypeError,ValueError)):x+values
    with pytest.raises(ValueError):Pldt(["2024-01-01"])+[Delta(),Delta()]
    with pytest.raises(TypeError):source().pldt.add_delta(pl.col("delta"))
    assert Pldt([],unit="ns").pldt.add_delta([]).dtype==pl.Datetime("ns")


def test_units_are_fixed_cancellation_is_final_and_minimum_is_a_valid_date():
    for unit in ["ms","us"]:
        x=Pldt([0],unit=unit)
        with pytest.raises(ValueError,match="precision|unit"):x+Delta(nanoseconds=1)
        assert ticks(x+Delta(microseconds=1,nanoseconds=-1000))==[0]
    x=Pldt([-(1<<63),None],unit="ns")
    assert ticks(x+Delta())==[-(1<<63),None]
    assert ticks(x+Delta(nanoseconds=1))==[-(1<<63)+1,None]
    with pytest.raises(OverflowError):x-Delta(nanoseconds=1)
    with pytest.raises(OverflowError):source()+Delta(years=500)
    wide=Pldt.fromisoformat(["0000-01-31","12000-01-31"],unit="ms")
    assert ticks(wide+Delta(months=1))==[tick("0000-02-29","ms"),tick("12000-02-29","ms")]


def test_delta_calendar_day_and_elapsed_duration_have_distinct_dst_meaning():
    x=Pldt(["2024-03-09T12:00"],unit="us",tz="America/New_York",name="time")
    assert ticks(x+Delta(days=1))==[tick("2024-03-10T16:00","us")]
    assert ticks(x+timedelta(days=1))==[tick("2024-03-10T17:00","us")]
    assert ticks(timedelta(days=1)+x)==[tick("2024-03-10T17:00","us")]
    assert ticks(x-timedelta(days=1))==[tick("2024-03-08T17:00","us")]
    gap=Pldt(["2024-03-09T02:30"],unit="us",tz="America/New_York")
    assert ticks(gap+Delta(days=1))==[tick("2024-03-10T07:30","us")]
    apia=Pldt(["2011-12-29T12:00"],unit="us",tz="Pacific/Apia")
    with pytest.raises(ValueError,match="day|valid"):apia+Delta(days=1)


@pytest.mark.parametrize("unit,scale",[("W",7*86400*10**9),("D",86400*10**9),("h",3600*10**9),("m",60*10**9),("s",10**9),("ms",10**6),("us",1000),("ns",1)])
def test_numpy_scalar_and_array_durations_retain_their_actual_units(unit,scale):
    x=Pldt([0,None],unit="ns")
    assert ticks(x+np.timedelta64(1,unit))==[scale,None]
    assert ticks(np.timedelta64(1,unit)+x)==[scale,None]
    assert ticks(x+np.array([1,2],dtype="timedelta64["+unit+"]"))==[scale,None]
    assert ticks(x-np.timedelta64(1,unit))==[-scale,None]


def test_native_duration_validity_is_independent_of_minimum_integer():
    x=Pldt([0,0,None],unit="ns")
    durations=pl.Series("d",[-(1<<63),None,1],dtype=pl.Duration("ns"))
    assert ticks(x+durations)==[-(1<<63),None,None]
    assert ticks(x+np.timedelta64("NaT","ns"))==[None,None,None]
    with pytest.raises(TypeError):x+[Delta(),None,Delta()]
    for value in [1,1.0,True,"1",None]:
        with pytest.raises(TypeError):x+value


def test_date_difference_returns_native_duration_with_common_precision_and_domain():
    x=Pldt([1001,None],unit="us",name="time")
    other=pl.Series("other",[1,None],dtype=pl.Datetime("ns"))
    result=x-other
    assert type(result) is pl.Series and result.dtype==pl.Duration("ns")
    assert result.name=="time" and ticks(result)==[1_000_999,None]
    assert ticks(x-[None,None])==[None,None]
    assert (x-[None,None]).dtype==pl.Duration("us")
    with pytest.raises(OverflowError):Pldt([(1<<63)-1],unit="ns")-pl.Series([-(1<<63)],dtype=pl.Datetime("ns"))
    aware=Pldt(["2024-01-01"],unit="us",tz="UTC")
    equivalent=Pldt(["2024-01-01T08:00"],unit="ns",tz="Asia/Shanghai")
    assert ticks(aware-equivalent)==[0]
    with pytest.raises(TypeError,match="awareness|aware"):aware-pl.Series([0],dtype=pl.Datetime("us"))
    with pytest.raises(TypeError,match="awareness|aware"):Pldt([],unit="us",tz="UTC")-pl.Series([],dtype=pl.Datetime("us"))
    with pytest.raises(TypeError):aware+equivalent


def test_scalar_dates_and_numpy_dates_are_not_parsed_through_text():
    x=Pldt(["2024-01-02",None],unit="ns")
    day=86400*10**9
    for other in [datetime(2024,1,1),date(2024,1,1),np.datetime64("2024-01-01","D")]:
        assert ticks(x-other)==[day,None]
    for other in [np.array(["2024-01-01","NaT"],dtype="datetime64[ms]"),pl.Series([date(2024,1,1),None],dtype=pl.Date)]:
        assert ticks(x-other)==[day,None]
    with pytest.raises(TypeError):x-["2024-01-01",None]


def test_plain_subclass_and_irrelevant_override_keep_the_native_path():
    class Plain(Delta):pass
    class Irrelevant(Delta):
        def __repr__(self):raise AssertionError("not an arithmetic protocol")
    x=source()
    for value in [Plain(nanoseconds=1),Irrelevant(nanoseconds=1)]:
        assert ticks(x+value)==[tick("2024-01-31T12:34:56.123456790"),None]
        assert ticks(pl.DataFrame(x).select(pl.col("time").pldt.add_delta(value))["time"])==[tick("2024-01-31T12:34:56.123456790"),None]


def test_scalar_external_business_result_is_normal_python_negotiation():
    calls=[]
    class Custom(Delta):
        def __radd__(self,other):calls.append(other);return "business-result"
    x=source();value=Custom(days=1)
    assert x.__add__(value) is NotImplemented and calls==[]
    assert x+value=="business-result" and calls==[x]
    with pytest.raises(TypeError,match="collection|Delta|date"):x.pldt.add_delta(value)
    with pytest.raises(TypeError,match="dynamic|Python|Expr"):pl.col("time").pldt.add_delta(value)
    with pytest.raises(TypeError,match="dynamic|Python|Expr"):pl.col("time").pldt.add_delta([Delta(),value])


def test_named_scalar_actual_callback_must_return_equal_length_dates():
    calls=[]
    class Custom(Delta):
        def __radd__(self,other):calls.append(type(other));return other.pldt.add(nanoseconds=2)
    x=source();result=x.pldt.add_delta(Custom())
    assert isinstance(result,Pldt) and ticks(result)==[tick("2024-01-31T12:34:56.123456791"),None]
    assert calls==[Pldt]


def test_vector_callbacks_receive_one_real_series_with_full_ns():
    observed=[]
    class Custom(Delta):
        def __radd__(self,other):
            observed.append((type(other),len(other),other.dtype,ticks(other)))
            return other.pldt.add(nanoseconds=2)
    x=Pldt(["2024-01-01T00:00:00.123456789"]*2,unit="ns",name="time")
    result=x+[Delta(),Custom()]
    assert ticks(result)==[tick("2024-01-01T00:00:00.123456789"),tick("2024-01-01T00:00:00.123456791")]
    assert observed==[(pl.Series,1,pl.Datetime("ns"),[tick("2024-01-01T00:00:00.123456789")])]


@pytest.mark.parametrize("returned",["text",1,timedelta(1),NotImplemented,[],[datetime(2024,1,1)]*2])
def test_bad_vector_callback_returns_are_not_reparsed(returned):
    class Custom(Delta):
        def __radd__(self,other):return returned
    with pytest.raises((TypeError,ValueError)):
        Pldt([0],unit="ns")+[Custom()]


def test_dynamic_null_source_skips_call_and_first_error_preserves_identity():
    calls=[];sentinel=RuntimeError("business failure")
    class Custom(Delta):
        def __init__(self,label):self.label=label
        def __radd__(self,other):
            calls.append(self.label)
            if self.label==1:raise sentinel
            return other
    x=Pldt([None,0,0],unit="ns")
    with pytest.raises(RuntimeError) as info:x+[Custom(0),Custom(1),Custom(2)]
    assert info.value is sentinel and calls==[1] and ticks(x)==[None,0,0]
    with pytest.raises(TypeError):x+[None,Delta(),Delta()]


def test_live_method_edits_and_inherited_descriptors_are_observed():
    class Plain(Delta):pass
    x=Pldt([0],unit="ns",name="time");value=Plain(nanoseconds=1)
    snapshot=pl.col("time").pldt.add_delta(value)
    Plain.__radd__=lambda self,other:"changed"
    assert x+value=="changed"
    with pytest.raises(TypeError):pl.col("time").pldt.add_delta(value)
    assert ticks(pl.DataFrame(x).select(snapshot)["time"])==[1]
    events=[]
    class Descriptor:
        def __get__(self,obj,cls):
            events.append("bind")
            return lambda other:other.pldt.add(nanoseconds=3)
    class Base(Delta):__radd__=Descriptor()
    class Child(Base):pass
    assert ticks(x+[Child()])==[3] and events==["bind"]


def test_reflected_forward_callback_notimplemented_is_not_called_twice():
    calls=[]
    class Forward(Delta):
        def __add__(self,other):calls.append(type(other));return NotImplemented
    x=Pldt([0],unit="ns")
    assert ticks(Forward(nanoseconds=1)+x)==[1]
    assert calls==[Pldt]
    calls.clear()
    assert ticks([Forward(nanoseconds=1)]+x)==[1]
    assert calls==[pl.Series]


def test_concrete_delta_vectors_follow_full_domains_slices_chunks_and_streaming():
    raw=pl.concat([pl.Series("time",[0,1000],dtype=pl.Datetime("ns")),pl.Series("time",[2000,None],dtype=pl.Datetime("ns"))],rechunk=False)
    expr=pl.col("time").pldt.add_delta([Delta(nanoseconds=i) for i in [1,2,3,4]])
    q=pl.DataFrame(raw).lazy().select(expr).slice(1,2)
    assert ticks(q.collect(engine="streaming")["time"])==[1002,2003]
    with pytest.raises((ValueError,pl.exceptions.PolarsError)):
        pl.DataFrame(raw).lazy().filter(pl.col("time")>0).select(expr).collect()
    scalar=pl.col("time").pldt.add_delta(Delta(nanoseconds=1)).over("g")
    frame=pl.DataFrame({"time":raw,"g":["A","B","A","B"]})
    assert ticks(frame.select(scalar)["time"])==[1,1001,2001,None]


def test_optional_pandas_native_units_dates_and_durations_preserve_real_ns():
    pd=pytest.importorskip("pandas")
    x=Pldt([0,None],unit="ns")
    durations=pd.TimedeltaIndex([pd.Timedelta(1,unit="ns"),pd.NaT])
    assert ticks(x+durations)==[1,None]
    dates=pd.DatetimeIndex([pd.Timestamp(1,unit="ns"),pd.NaT])
    assert ticks(x-dates)==[-1,None]
    assert ticks(x+pd.Timedelta(1,unit="ns"))==[1,None]


def test_explicit_numpy_temporal_ufuncs_share_only_the_approved_directions():
    x=Pldt([0,None],unit="ns")
    assert ticks(np.add(x,np.timedelta64(1,"ns")))==[1,None]
    assert ticks(np.subtract(x,np.timedelta64(1,"ns")))==[-1,None]
    assert ticks(np.add(np.array([1,2],dtype="timedelta64[ns]"),x))==[1,None]
    assert ticks(np.subtract(x,np.datetime64(1,"ns")))==[-1,None]
    with pytest.raises(TypeError):np.subtract(np.datetime64(1,"ns"),x)
    assert np.negative(x).equals(np.negative(pl.Series(x)))


def test_subtraction_real_reverse_method_and_date_column_results_are_respected():
    class Business(Delta):
        def __rsub__(self,other):return "sub-business"
    x=Pldt([0],unit="ns")
    assert x-Business()=="sub-business"
    class DateResult(Delta):
        def __rsub__(self,other):return np.array([123456789],dtype="datetime64[ns]")
    assert ticks(x-[DateResult()])==[123456789]
    class ScalarDate(Delta):
        def __radd__(self,other):return np.datetime64(123456789,"ns")
    assert ticks(x+[ScalarDate()])==[123456789]


def test_dynamic_duration_and_live_descriptor_follow_actual_arithmetic():
    calls=[]
    class Duration(timedelta):
        def __radd__(self,other):calls.append(type(other));return other.pldt.add(nanoseconds=3)
    x=Pldt([0],unit="ns")
    assert ticks(x+Duration(days=1))==[3]
    assert calls==[Pldt]
    calls.clear()
    assert ticks(x+[Duration(days=1)])==[3]
    assert calls==[pl.Series]
    sentinel=RuntimeError("descriptor binding failure")
    class Descriptor:
        def __get__(self,obj,cls):raise sentinel
    class Broken(Delta):__radd__=Descriptor()
    with pytest.raises(RuntimeError) as info:x+[Broken()]
    assert info.value is sentinel


def test_dynamic_validity_and_timezone_are_checked_before_final_projection():
    class OtherZone(Delta):
        def __radd__(self,other):return other.dt.convert_time_zone("UTC")
    x=Pldt(["2024-01-01T12:00"],unit="ns",tz="Asia/Shanghai")
    result=x+[OtherZone()]
    assert result.dtype==pl.Datetime("ns","Asia/Shanghai") and ticks(result)==[tick("2024-01-01T04:00")]
    class Naive(Delta):
        def __radd__(self,other):return other.dt.replace_time_zone(None)
    with pytest.raises(TypeError,match="awareness|aware"):x+[Naive()]
    class Missing(Delta):
        def __radd__(self,other):return None
    assert ticks(x+[Missing()])==[None]
    class TooFine(Delta):
        def __radd__(self,other):return np.datetime64(1,"ns")
    with pytest.raises(ValueError,match="precision|unit"):Pldt([0],unit="us")+[TooFine()]


def test_native_failure_stops_before_a_later_dynamic_callback():
    calls=[]
    class Later(Delta):
        def __radd__(self,other):calls.append("called");return other
    x=Pldt([0,0],unit="ns")
    with pytest.raises(OverflowError):x+[Delta(years=1000),Later()]
    assert calls==[] and ticks(x)==[0,0]


def test_scalar_named_callback_checks_full_result_shape_without_broadcasting():
    class Short(Delta):
        def __radd__(self,other):return other.head(1)
    x=Pldt([0,0],unit="ns")
    with pytest.raises(ValueError,match="length|scalar"):x.pldt.add_delta(Short())
    class Array(Delta):
        def __radd__(self,other):return np.array([1,2],dtype="datetime64[ns]")
    assert ticks(x.pldt.add_delta(Array()))==[1,2]


@pytest.mark.parametrize("unit,scale",[("ms",1000),("us",1_000_000),("ns",1_000_000_000)])
@pytest.mark.parametrize("zone",[None,"UTC","Asia/Shanghai"])
def test_every_date_arithmetic_exit_retains_unit_zone_name_and_validity(unit,scale,zone):
    x=Pldt([0,None],unit=unit,tz=zone,name="time")
    for result in [x+Delta(seconds=1),x-Delta(seconds=-1),x+timedelta(seconds=1),x-timedelta(seconds=-1)]:
        assert result.dtype==x.dtype and result.name=="time"
        assert ticks(result)==[scale,None]


def test_concrete_delta_companion_uses_logical_group_length_and_order():
    frame=pl.DataFrame({"time":pl.Series([0,1000,2000,None],dtype=pl.Datetime("ns")),"g":["A","B","A","B"]})
    deltas=[Delta(nanoseconds=1),Delta(nanoseconds=2)]
    expr=pl.col("time").pldt.add_delta(deltas).over("g")
    assert ticks(frame.lazy().select(expr).collect()["time"])==[1,1001,2002,None]
    with pytest.raises((ValueError,pl.exceptions.PolarsError)):
        frame.select(pl.col("time").pldt.add_delta([Delta()]*4).over("g"))


@pytest.mark.parametrize("unit",["Y","M","W","D","h","m","s","ms","us","ns"])
def test_numpy_date_operands_read_all_ten_supported_units(unit):
    x=Pldt([0],unit="ns")
    scalar=np.datetime64(1,unit)
    expected=-int(scalar.astype("datetime64[ns]").astype(np.int64))
    assert ticks(x-scalar)==[expected]
    assert ticks(x-np.array([scalar]))==[expected]


def test_date_difference_checks_only_the_real_final_duration_capacity():
    # The first absolute date cannot be represented in int64 microseconds,
    # yet their difference is just193us. No premature narrowing is permitted.
    x=Pldt([9223372036854776],unit="ms")
    other=pl.Series([9223372036854775807],dtype=pl.Datetime("us"))
    result=x-other
    assert result.dtype==pl.Duration("us") and ticks(result)==[193]
    minimum=pl.Series([-(1<<63)],dtype=pl.Datetime("ns"))
    assert ticks(Pldt([-1],unit="ns")-minimum)==[(1<<63)-1]
    assert ticks(Pldt([0],unit="ns")-np.array([np.datetime64("NaT")]))==[None]
