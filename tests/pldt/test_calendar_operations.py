"""F01-F03: independent calendar/tick answers through eager and native Expr."""
from datetime import datetime
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def ticks(value):
    return value.to_physical().to_list()


def tick(text, unit="ns"):
    return int(np.datetime64(text, unit).astype(np.int64))


def source(text="2024-01-31T12:34:56.123456789", unit="ns"):
    return Pldt([text, None], unit=unit, name="time")


def test_strict_merge_is_atomic_but_convenience_fits_only_legal_day_intent():
    x=source()
    with pytest.raises(ValueError,match="invalid|day"):
        x.pldt.replace(month=2)
    expected=[tick("2024-02-29T12:34:56.123456789"), None]
    assert ticks(x.pldt.replace(month=2,day=29))==expected
    assert ticks(x.to_date(month=2))==expected
    assert ticks(x.to_datetime(month=2))==expected
    assert ticks(x.to_time(hour=0))==[tick("2024-01-31T00:34:56.123456789"),None]
    assert ticks(x)==[tick("2024-01-31T12:34:56.123456789"),None]
    # The native whole-value replace retains its own API and return type.
    native=x.replace(datetime(2024,1,31,12,34,56,123456),datetime(2024,2,29))
    assert type(native) is pl.Series


@pytest.mark.parametrize("field,value",[("year",True),("day",1.0),("day","1"),("month",0),("month",13),("day",0),("day",32),("hour",-1),("hour",24),("minute",60),("second",60),("microsecond",1_000_000),("nanosecond",1000)])
@pytest.mark.parametrize("null_source",[False,True])
def test_every_supplied_field_is_validated_on_empty_and_missing_dates(field,value,null_source):
    x=Pldt([None] if null_source else [],unit="us")
    with pytest.raises((TypeError,ValueError)):
        x.pldt.replace(**{field:value})


def test_native_optional_null_is_none_but_float_nan_and_object_na_are_not():
    x=Pldt(["2024-01-02","2024-01-03"],unit="us",name="time")
    for days in ([None,20],pl.Series([None,20],dtype=pl.Int64)):
        assert ticks(x.pldt.replace(day=days))==[tick("2024-01-02","us"),tick("2024-01-20","us")]
    for days in ([float("nan"),20],pl.Series([None,None],dtype=pl.Float64)):
        with pytest.raises(TypeError):x.pldt.replace(day=days)
    with pytest.raises(ValueError,match="length|scalar"):x.pldt.replace(day=[20])
    with pytest.raises(ValueError,match="length|scalar"):Pldt(["2024-01-01"]).to_date(day=[1,2])
    assert ticks(x.pldt.replace(day=pl.Series([None,None],dtype=pl.Null)))==ticks(x)


def test_fraction_fields_clear_and_preserve_exact_tail_per_row():
    x=source()
    assert ticks(x.to_time(microsecond=1))==[tick("2024-01-31T12:34:56.000001000"),None]
    assert ticks(x.to_time(nanosecond=2))==[tick("2024-01-31T12:34:56.123456002"),None]
    assert ticks(x.pldt.replace(microsecond=1,nanosecond=2))==[tick("2024-01-31T12:34:56.000001002"),None]
    assert ticks(x.to_time(microsecond=[1,None],nanosecond=pl.Series([None,2],dtype=pl.Int64)))==[tick("2024-01-31T12:34:56.000001000"),None]
    negative=Pldt([-1],unit="ns")
    assert ticks(negative.to_time(nanosecond=0))==[-1000]


@pytest.mark.parametrize("call,expected",[
    (lambda x:x.to_year(1),"2025-01-31"),
    (lambda x:x.to_year(0,month="February"),"2024-02-29"),
    (lambda x:x.to_quarter(1),"2024-04-30"),
    (lambda x:x.to_quarter(1,month=2,day=31),"2024-05-31"),
    (lambda x:x.to_month(1),"2024-02-29"),
    (lambda x:x.to_weekday(0,weekday="Monday"),"2024-01-29"),
    (lambda x:x.to_weekday(1,weekday="Monday"),"2024-02-05"),
    (lambda x:x.to_weekday(-1,weekday="Friday"),"2024-01-26"),
    (lambda x:x.to_day(1),"2024-02-01"),
    (lambda x:x.to_curr_year(month=2,day=31),"2024-02-29"),
    (lambda x:x.to_prev_year(month="February",day=31),"2023-02-28"),
    (lambda x:x.to_next_year(),"2025-01-31"),
    (lambda x:x.to_curr_quarter(month=3,day=31),"2024-03-31"),
    (lambda x:x.to_prev_quarter(),"2023-10-31"),
    (lambda x:x.to_next_quarter(month=3,day=31),"2024-06-30"),
    (lambda x:x.to_curr_month(day=1),"2024-01-01"),
    (lambda x:x.to_prev_month(),"2023-12-31"),
    (lambda x:x.to_next_month(day=31),"2024-02-29"),
    (lambda x:x.to_curr_weekday(weekday="Friday"),"2024-02-02"),
    (lambda x:x.to_prev_weekday(),"2024-01-24"),
    (lambda x:x.to_next_weekday(),"2024-02-07"),
    (lambda x:x.to_monday(),"2024-01-29"),
    (lambda x:x.to_tuesday(),"2024-01-30"),
    (lambda x:x.to_wednesday(),"2024-01-31"),
    (lambda x:x.to_thursday(),"2024-02-01"),
    (lambda x:x.to_friday(),"2024-02-02"),
    (lambda x:x.to_saturday(),"2024-02-03"),
    (lambda x:x.to_sunday(),"2024-02-04"),
    (lambda x:x.to_yesterday(),"2024-01-30"),
    (lambda x:x.to_tomorrow(),"2024-02-01"),
])
def test_calendar_methods_and_aliases_have_independent_expected_date(call,expected):
    x=source()
    expected_ticks=[tick(expected+"T12:34:56.123456789"),None]
    result=call(x)
    assert isinstance(result,Pldt)
    assert result.dtype==pl.Datetime("ns") and result.name=="time"
    assert ticks(result)==expected_ticks
    df=pl.DataFrame(x)
    expr=call(pl.col("time").pldt)
    assert isinstance(expr,pl.Expr)
    assert ticks(df.lazy().select(expr).collect()["time"])==expected_ticks
    assert ticks(call(pl.Series(x).pldt))==expected_ticks


@pytest.mark.parametrize("call",[
    lambda x:x.to_year(0,month=13),lambda x:x.to_quarter(1,month=4),lambda x:x.to_quarter(1,month="January"),
    lambda x:x.to_month(0,day=32),lambda x:x.to_weekday(0,weekday=7),lambda x:x.to_weekday(0,weekday="mOnDaY"),
    lambda x:x.to_day(None),lambda x:x.to_day(True),lambda x:x.to_day(1.0),lambda x:x.to_year(1,month="unknown"),
])
def test_moves_validate_role_ranges_and_exact_saved_names(call):
    with pytest.raises((TypeError,ValueError)):
        call(Pldt([],unit="us"))


def test_single_final_month_fit_and_cancellations():
    x=source()
    assert ticks(x.to_month(2))==[tick("2024-03-31T12:34:56.123456789"),None]
    assert ticks(x.to_month(1).to_month(1))==[tick("2024-03-29T12:34:56.123456789"),None]
    assert ticks(x.add(months=1,days=-1))==[tick("2024-02-28T12:34:56.123456789"),None]
    assert ticks(x.sub(months=1,days=-1))==[tick("2024-01-01T12:34:56.123456789"),None]
    leap=Pldt(["2024-02-29T12:00"],unit="us")
    for call in [lambda x:x.add(years=1,months=-12),lambda x:x.sub(years=1,quarters=-1,months=-9),lambda x:x.add(weeks=1,days=-7),lambda x:x.add(microseconds=1,nanoseconds=-1000)]:
        assert ticks(call(leap))==[tick("2024-02-29T12:00","us")]
    assert ticks(x.add(hours=25))==[tick("2024-02-01T13:34:56.123456789"),None]


@pytest.mark.parametrize("name,amount",[("years",1),("quarters",1),("months",1),("weeks",1),("days",1),("hours",1),("minutes",1),("seconds",1),("milliseconds",1),("microseconds",1),("nanoseconds",1)])
@pytest.mark.parametrize("bad",[None,True,1.0,"1",[None]])
def test_every_relative_role_rejects_non_index_and_missing(name,amount,bad):
    with pytest.raises((TypeError,ValueError)):
        source().add(**{name:bad})
    with pytest.raises((TypeError,ValueError)):
        Pldt([],unit="us").sub(**{name:bad})


def test_current_unit_is_fixed_and_capacity_is_not_clamped():
    x=Pldt([0],unit="us")
    with pytest.raises(ValueError,match="precision|unit"):x.to_time(nanosecond=1)
    with pytest.raises(ValueError,match="precision|unit"):x.add(nanoseconds=1)
    with pytest.raises(OverflowError,match="capacity|unit|range"):Pldt([0],unit="ns").to_date(year=2500)
    assert ticks(x.to_date(year=0,month=1,day=1))==[tick("0000-01-01","us")]
    assert ticks(x.to_date(year=-1,month=1,day=1))==[tick("-001-01-01","us")]
    assert ticks(Pldt([-(1<<63)],unit="ns").add())==[-(1<<63)]
    with pytest.raises(OverflowError):Pldt([-(1<<63)],unit="ns").sub(nanoseconds=1)


def test_once_read_protocol_and_positional_nullable_names():
    class Index:
        def __init__(self,value):self.value=value;self.calls=0
        def __index__(self):self.calls+=1;return self.value
    offset=Index(1);x=Pldt(["2024-01-31","2024-04-30"],unit="us")
    assert ticks(x.to_year(offset,month=["February","March"],day=31))==[tick("2025-02-28","us"),tick("2025-03-31","us")]
    assert offset.calls==1
    assert ticks(x.to_year(0,month=pl.Series([None,"March"],dtype=pl.String)))==[tick("2024-01-31","us"),tick("2024-03-30","us")]
    def values():
        yield Index(1)
        yield Index(-1)
    assert ticks(x.to_month(values()))==[tick("2024-02-29","us"),tick("2024-03-30","us")]


def test_expr_scalar_aggregate_and_per_row_fields_are_distinct():
    x=Pldt(["2024-01-02","2024-01-03"],unit="us",name="time")
    frame=pl.DataFrame({"time":x,"new_day":[None,20],"offset":[1,2]})
    assert ticks(frame.select(pl.col("time").pldt.replace(day=pl.col("new_day")))["time"])==[tick("2024-01-02","us"),tick("2024-01-20","us")]
    assert ticks(frame.select(pl.col("time").pldt.to_day(pl.col("offset").max()))["time"])==[tick("2024-01-04","us"),tick("2024-01-05","us")]
    with pytest.raises((ValueError,pl.exceptions.ComputeError)):
        frame.select(pl.col("time").pldt.to_day(pl.col("offset").head(1)))
    native=pl.DataFrame({"number":[1,2]}).select(pl.col("number").add(2))
    assert native["number"].to_list()==[3,4]


@pytest.mark.parametrize("local,change,expected",[
    ("2024-03-09T02:30",1,"2024-03-10T07:30"),
    ("2024-03-11T02:30",-1,"2024-03-10T06:30"),
    ("2024-11-02T01:30",1,"2024-11-03T05:30"),
    ("2024-11-04T01:30",-1,"2024-11-03T06:30"),
    ("2024-03-09T12:00",1,"2024-03-10T16:00"),
])
def test_automatic_new_york_calendar_preserves_source_side(local,change,expected):
    x=Pldt([local],unit="us",tz="America/New_York",name="time")
    assert ticks(x.to_day(change))==[tick(expected,"us")]
    assert ticks(x.add(days=change))==[tick(expected,"us")]
    assert ticks(pl.DataFrame(x).select(pl.col("time").pldt.to_day(change))["time"])==[tick(expected,"us")]


def test_explicit_replace_dst_is_distinct_from_convenience_and_keeps_known_instants():
    x=Pldt(["2024-03-10T01:30"],unit="us",tz="America/New_York")
    with pytest.raises(ValueError,match="exist|gap"):x.pldt.replace(hour=2)
    assert ticks(x.pldt.replace(hour=2,nonexistent="shift_forward"))==[tick("2024-03-10T07:00","us")]
    assert ticks(x.to_time(hour=2))==[tick("2024-03-10T07:30","us")]
    y=Pldt(["2024-03-10T03:30"],unit="us",tz="America/New_York")
    assert ticks(y.to_time(hour=2))==[tick("2024-03-10T06:30","us")]
    fold=Pldt([tick("2024-11-03T06:30","us")],unit="us",tz="UTC").tz_convert("America/New_York")
    assert ticks(fold.pldt.replace())==ticks(fold)
    assert ticks(fold.to_time(hour=1))==ticks(fold)
    assert ticks(fold.pldt.replace(tzinfo=None))==[tick("2024-11-03T01:30","us")]
    assert fold.pldt.replace(tzinfo=None).dtype==pl.Datetime("us")
    naive=Pldt(["2024-01-02T12:00"],unit="us")
    assert ticks(naive.pldt.replace(tzinfo="Asia/Shanghai"))==[tick("2024-01-02T04:00","us")]


def test_real_half_hour_gap_and_missing_calendar_day():
    x=Pldt(["2024-10-05T02:15"],unit="us",tz="Australia/Lord_Howe")
    assert ticks(x.to_day(1))==[tick("2024-10-05T15:45","us")]
    apia=Pldt(["2011-12-29T12:00"],unit="us",tz="Pacific/Apia")
    with pytest.raises(ValueError,match="day|valid"):apia.to_day(1)


@pytest.mark.parametrize("name,forward,backward",[
    ("years","2025-01-31T12:34:56.123456789","2023-01-31T12:34:56.123456789"),
    ("quarters","2024-04-30T12:34:56.123456789","2023-10-31T12:34:56.123456789"),
    ("months","2024-02-29T12:34:56.123456789","2023-12-31T12:34:56.123456789"),
    ("weeks","2024-02-07T12:34:56.123456789","2024-01-24T12:34:56.123456789"),
    ("days","2024-02-01T12:34:56.123456789","2024-01-30T12:34:56.123456789"),
    ("hours","2024-01-31T13:34:56.123456789","2024-01-31T11:34:56.123456789"),
    ("minutes","2024-01-31T12:35:56.123456789","2024-01-31T12:33:56.123456789"),
    ("seconds","2024-01-31T12:34:57.123456789","2024-01-31T12:34:55.123456789"),
    ("milliseconds","2024-01-31T12:34:56.124456789","2024-01-31T12:34:56.122456789"),
    ("microseconds","2024-01-31T12:34:56.123457789","2024-01-31T12:34:56.123455789"),
    ("nanoseconds","2024-01-31T12:34:56.123456790","2024-01-31T12:34:56.123456788"),
])
def test_all_relative_roles_in_both_directions_keep_full_ns(name,forward,backward):
    x=source()
    for method,expected in [("add",forward),("sub",backward)]:
        assert ticks(getattr(x,method)(**{name:1}))==[tick(expected),None]
        expr=getattr(pl.col("time").pldt,method)(**{name:1})
        assert ticks(pl.DataFrame(x).select(expr)["time"])==[tick(expected),None]


def test_replace_explicit_dst_mask_infer_and_expression_policies():
    x=Pldt(["2024-11-02T01:30"]*2,unit="us",tz="America/New_York",name="time")
    expected=[tick("2024-11-03T05:30","us"),tick("2024-11-03T06:30","us")]
    assert ticks(x.pldt.replace(day=3,ambiguous=[True,False]))==expected
    df=pl.DataFrame({"time":x,"choice":[True,False]})
    assert ticks(df.lazy().select(pl.col("time").pldt.replace(day=3,ambiguous=pl.col("choice"))).collect()["time"])==expected
    assert ticks(x.pldt.replace(day=3,ambiguous="NaT"))==[None,None]
    with pytest.raises(ValueError,match="length"):
        x.pldt.replace(ambiguous=[True])
    ordered=Pldt(["2024-11-02T01:00","2024-11-02T01:30"]*2,unit="us",tz="America/New_York")
    assert ticks(ordered.pldt.replace(day=3,ambiguous="infer"))==[tick(t,"us") for t in ["2024-11-03T05:00","2024-11-03T05:30","2024-11-03T06:00","2024-11-03T06:30"]]


def test_literal_buffers_are_frozen_and_source_calendar_is_not_implicitly_parsed():
    x=Pldt(["2024-01-02","2024-01-03"],unit="us",name="time")
    values=np.array([10,20],dtype=np.int64)
    expr=pl.col("time").pldt.replace(day=values)
    values[:]=1
    assert ticks(pl.DataFrame(x).select(expr)["time"])==[tick("2024-01-10","us"),tick("2024-01-20","us")]
    for data in (pl.Series("time",[1],dtype=pl.Int64),pl.Series("time",["2024-01-01"])):
        with pytest.raises(TypeError):data.pldt.to_day(1)


def test_external_field_protocol_error_preserves_identity():
    sentinel=RuntimeError("external index failed")
    class BadIndex:
        def __index__(self):raise sentinel
    with pytest.raises(RuntimeError) as info:
        source().to_day(BadIndex())
    assert info.value is sentinel


def test_shared_calendar_positional_parameters_match_pddt_and_pydt():
    x=source()
    assert ticks(x.to_year(0,2,29))==[tick("2024-02-29T12:34:56.123456789"),None]
    assert ticks(x.to_date(None,2,29))==[tick("2024-02-29T12:34:56.123456789"),None]
    assert ticks(x.pldt.replace(None,2,29))==[tick("2024-02-29T12:34:56.123456789"),None]
    assert ticks(x.add(0,0,1))==[tick("2024-02-29T12:34:56.123456789"),None]


def test_date_calendar_moves_promote_once_but_strict_field_contract_requires_datetime():
    value=pl.Series("time",[datetime(2024,1,31).date(),None],dtype=pl.Date)
    for call,expected in [(lambda x:x.to_month(1),"2024-02-29"),(lambda x:x.to_day(1),"2024-02-01"),(lambda x:x.add(months=1),"2024-02-29")]:
        result=call(value.pldt)
        assert result.dtype==pl.Datetime("ms")
        assert ticks(result)==[tick(expected,"ms"),None]
        expr=call(pl.col("time").pldt)
        query=pl.DataFrame(value).lazy().select(expr)
        assert query.collect_schema()["time"]==pl.Datetime("ms")
        assert ticks(query.collect()["time"])==[tick(expected,"ms"),None]
    with pytest.raises(TypeError):value.pldt.replace(day=1)
    with pytest.raises(TypeError):value.pldt.to_date(day=1)
