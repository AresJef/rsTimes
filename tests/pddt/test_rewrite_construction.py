"""P02/P03/P05/P06: independent Pddt construction contract."""
from collections import deque
from datetime import date, datetime, timedelta, timezone
import array

import numpy as np
import pandas as pd
import pytest

from rstimes import Configs, Pddt


@pytest.mark.parametrize("make", [list, tuple, deque, iter,
    lambda x:np.array(x,dtype=object),lambda x:pd.Series(x),
    lambda x:pd.Index(x),lambda x:pd.array(x,dtype=object),
    lambda x:dict.fromkeys(x)])
def test_supported_outer_collections_use_values_once_in_order(make):
    values = ["2024-05-07", "2024-05-08"]
    result = Pddt(make(values))
    assert result.unit == "us"
    assert result.year.tolist() == [2024, 2024]
    assert result.day.tolist() == [7, 8]


@pytest.mark.parametrize("value", [np.zeros((1, 2),dtype="datetime64[us]"), np.array(0)])
def test_numpy_shape_is_not_flattened(value):
    with pytest.raises(ValueError,match="one-dimensional"):
        Pddt(value)


@pytest.mark.parametrize("value", ["2024-05-07", b"2024", None, datetime(2024,5,7),
    1, pd.DataFrame({"x":[1]}), pd.MultiIndex.from_tuples([(2024,5,7)]), [["2024-05-07"]]])
def test_unsupported_scalar_table_and_nested_inputs_are_rejected(value):
    with pytest.raises(TypeError):
        Pddt(value)


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_native_dates_and_numeric_ticks_have_explicit_unit_meanings(unit):
    values=np.array([0,1,-1,np.iinfo("i8").min],dtype="i8")
    native=values.view(f"datetime64[{unit}]")
    assert Pddt(native).unit == unit
    assert Pddt(native).asi8.tolist() == values.tolist()
    assert Pddt(values,unit=unit).asi8.tolist() == values.tolist()
    assert Pddt([1.0],unit=unit).asi8.tolist() == [1]


@pytest.mark.parametrize("unit,expected", [("Y",31536000),("M",2678400),("W",604800),("D",86400),("h",3600),("m",60),("s",1),("ms",1),("us",1),("ns",1)])
def test_all_ten_numpy_source_units_are_decoded_not_relabelled(unit,expected):
    values=np.array([1],dtype=f"datetime64[{unit}]")
    result=Pddt(values)
    assert result.unit == (unit if unit in {"s","ms","us","ns"} else "s")
    assert result.asi8.tolist() == [expected]


@pytest.mark.parametrize("value,unit", [([],"s"),([None,pd.NA,pd.NaT,float("nan")],"s"),
    (np.array([],dtype="f8"),"ns"),(np.array([np.nan],dtype="f8"),"ns"),
    (np.array([],dtype="datetime64[ms]"),"ms"),([date(2024,5,7)],"s"),
    ([datetime(2024,5,7)],"us"),(["2024-05-07 12:30:00.000000000"],"ns")])
def test_initial_unit_comes_from_actual_sources(value,unit):
    assert Pddt(value).unit == unit


@pytest.mark.parametrize("token", ["","NaT","NAT","nat","NaN","NAN","nan"])
@pytest.mark.parametrize("strict", [False,True])
def test_exact_missing_text_tokens_only(token,strict):
    result=Pddt([token],strict=strict)
    assert len(result)==1 and result.isna().tolist()==[True]


@pytest.mark.parametrize("token", [" ","None","null","nAt","nAn"," NaT","NaT "])
def test_near_missing_tokens_remain_bad_text(token):
    with pytest.raises(ValueError):Pddt([token])


@pytest.mark.parametrize("bad,error", [(1.5,ValueError),(True,TypeError),(np.bool_(False),TypeError),
    (np.inf,OverflowError),(2**63,OverflowError),(b"2024",TypeError),
    (np.timedelta64("NaT","s"),TypeError)])
def test_bad_date_values_are_not_coerced_or_truncated(bad,error):
    with pytest.raises(error):Pddt([bad])


def test_default_is_prepared_once_only_when_actual_text_needs_it():
    reads=[]
    class Text(str):
        def __str__(self):
            reads.append(1)
            return "2024-05-07"
    result=Pddt(["12:30","18:45"],default=Text("ignored"))
    assert reads==[1] and result.day.tolist()==[7,7]
    assert result.hour.tolist()==[12,18]
    Pddt([datetime(2024,5,7)],default=object())
    Pddt([],default=object())
    with pytest.raises(ValueError):Pddt(["12:30"],default="May 7")
    with pytest.raises(TypeError):Pddt(["2024-05-07"],default=True)
    assert Pddt(["12:30"],default=-1e-9).day.tolist()==[1]


def test_configs_order_and_shared_scanner_are_authoritative():
    cfg=Configs();cfg.set_month({"mymonth":2})
    result=Pddt(["14 Mymonth 2024"],cfg=cfg)
    assert result.month.tolist()==[2]
    assert Pddt(["03/04/2024"],yearfirst=False,dayfirst=True).day.tolist()==[3]
    assert Pddt(["03/04/2024"],yearfirst=False,dayfirst=False).day.tolist()==[4]
    with pytest.raises(ValueError):Pddt(["2024-02-30"],strict=True)
    assert Pddt(["2024-02-30"]).day.tolist()==[29]


def test_zero_wide_year_and_ns_precision_go_to_the_array_boundary():
    for iso in (False,True):
        result=Pddt(["0000-02-29"],isoformat=iso,unit="us")
        assert result.year.tolist()==[0] and result.day.tolist()==[29]
    source=pd.Timestamp("2024-05-07 12:00:00.123456789")
    result=Pddt([source])
    assert result.unit=="ns" and result.asi8[0]==source.as_unit("ns").value
    with pytest.raises(ValueError):Pddt([source],unit="us")
    with pytest.raises(OverflowError):Pddt(["2500-01-01"],unit="ns")
    assert Pddt(["2500-01-01"],unit="us").year.tolist()==[2500]


def test_native_noncontiguous_endian_multiplier_and_copy_ownership():
    values=np.arange(8,dtype="i8").view("datetime64[ms]")[::2]
    result=Pddt(values)
    assert np.shares_memory(values,result.asi8)
    assert not np.shares_memory(values,Pddt(values,copy=True).asi8)
    opposite=values.astype(values.dtype.newbyteorder(">"))
    assert Pddt(opposite).asi8.tolist()==[0,2,4,6]
    multiplied=np.array([1,2],dtype="datetime64[3D]")
    assert Pddt(multiplied).asi8.tolist()==[259200,518400]


def test_numeric_and_text_timezone_roles_and_aware_sources_are_distinct():
    zone=timezone(timedelta(hours=8))
    numeric=Pddt([0],unit="us",tz=zone)
    text=Pddt(["1970-01-01"],tz=zone)
    # A standard fixed offset needs no regional candidate or round-trip.
    assert numeric.hour.tolist()==[8] and numeric.asi8.tolist()==[0]
    assert text.hour.tolist()==[0] and text.asi8.tolist()==[-28800000000]
    result=Pddt(["1970-01-01T08:00+08:00","1970-01-01T00:00Z"],tz="UTC")
    assert result.asi8.tolist()==[0,0]
    with pytest.raises(ValueError):
        Pddt(["1970-01-01T08:00+08:00","1970-01-01T00:00Z"])
    aware=pd.DatetimeIndex([datetime(2024,5,7,tzinfo=timezone.utc)]).as_unit("ms")
    assert Pddt(aware).unit=="ms" and Pddt(aware).asi8.tolist()==aware.asi8.tolist()


def test_metadata_and_iterators_keep_original_failure_context():
    values=[]
    def source():
        values.append(1)
        yield datetime(2024,5,7)
        values.append(2)
        yield date(2024,5,8)
    result=Pddt(source(),name=("a",1))
    assert values==[1,2] and result.name==("a",1)
    assert result.unit=="us"
    error=RuntimeError("read sentinel")
    def broken():
        yield datetime(2024,5,7)
        raise error
    with pytest.raises(RuntimeError) as caught:Pddt(broken())
    assert caught.value is error and "reading data[1]" in " ".join(error.__notes__)
    with pytest.raises(ValueError,match="data\\[1\\]"):
        Pddt([datetime(2024,5,7),"bad date"])


def test_polars_date_datetime_and_string_columns():
    pl=pytest.importorskip("polars")
    dates=pl.Series("dates",[date(2024,5,7),None],dtype=pl.Date)
    out=Pddt(dates)
    assert out.unit=="s" and out.name=="dates" and out.isna().tolist()==[False,True]
    ticks=pl.Series([1,None],dtype=pl.Int64).cast(pl.Datetime("ns"))
    out=Pddt(ticks)
    assert out.unit=="ns" and out.asi8.tolist()==[1,np.iinfo("i8").min]
    assert Pddt(pl.Series(["2024-05-07"])).day.tolist()==[7]
    with pytest.raises(TypeError):Pddt(pl.DataFrame({"x":[1]}))


def test_real_region_keys_are_not_collapsed_by_equal_current_offsets():
    from zoneinfo import ZoneInfo
    same=[datetime(2024,5,7,tzinfo=ZoneInfo.no_cache("UTC")),
          datetime(2024,5,8,tzinfo=ZoneInfo.no_cache("UTC"))]
    assert Pddt(same).day.tolist()==[7,8]
    distinct=[datetime(2024,5,7,tzinfo=ZoneInfo("UTC")),
              datetime(2024,5,8,tzinfo=ZoneInfo("Etc/UTC"))]
    with pytest.raises(ValueError):Pddt(distinct)
    assert Pddt(distinct,tz="UTC").day.tolist()==[7,8]
