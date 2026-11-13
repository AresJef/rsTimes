"""P07: one system clock, fixed numeric input units and exact output capacity."""
from datetime import datetime, timedelta, timezone
import time
import sys
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    _precise_clock = ctypes.WinDLL("kernel32").GetSystemTimePreciseAsFileTime
    _precise_clock.argtypes = [ctypes.POINTER(wintypes.FILETIME)]
    _precise_clock.restype = None

    def system_time_ns():
        """Use Rust's precise OS clock; Python3.12 time_ns is coarser on Windows."""
        stamp = wintypes.FILETIME()
        _precise_clock(ctypes.byref(stamp))
        ticks = (stamp.dwHighDateTime << 32) | stamp.dwLowDateTime
        return (ticks - 116444736000000000) * 100
else:
    system_time_ns = time.time_ns


@pytest.mark.parametrize("factory", [Pddt.now,Pddt.today,Pddt.utcnow])
@pytest.mark.parametrize("unit", ["s","ms","us","ns"])
def test_clock_units_repeat_one_value_and_empty_calls_do_not_discover_local(factory,unit,monkeypatch):
    import rstimes.pddt as module
    def forbidden():raise AssertionError("empty factory must not load local timezone")
    monkeypatch.setattr(module,"_local_timezone",forbidden)
    empty=factory(0,unit=unit)
    assert empty.empty and empty.unit==unit
    if factory.__name__=="utcnow":assert empty.tzinfo is timezone.utc


@pytest.mark.parametrize("unit", ["s","ms","us","ns"])
def test_utc_clock_is_bounded_by_integer_system_reads_and_preserves_unit(unit):
    before=system_time_ns()
    result=Pddt.utcnow(8,unit=unit)
    after=system_time_ns()
    scale={"s":10**9,"ms":10**6,"us":1000,"ns":1}[unit]
    assert result.unit==unit and result.tzinfo is timezone.utc
    assert len(set(result.asi8.tolist()))==1
    assert before//scale<=result.asi8[0]<=after//scale


def test_now_and_today_keep_local_clock_and_prepare_zone_once(monkeypatch):
    import rstimes.pddt as module
    calls=[]
    def local():calls.append(1);return timezone(timedelta(hours=8))
    monkeypatch.setattr(module,"_local_timezone",local)
    for factory in (Pddt.now,Pddt.today):
        before=system_time_ns()+8*3600*10**9
        result=factory(4,unit="ns")
        after=system_time_ns()+8*3600*10**9
        assert result.tzinfo is None and len(set(result.asi8))==1
        assert before<=result.asi8[0]<=after
    assert calls==[1,1]


@pytest.mark.parametrize("bad", [True,np.bool_(False),1.0,-1])
def test_size_is_nonnegative_integer_only(bad):
    for call in (Pddt.now,Pddt.today,Pddt.utcnow):
        with pytest.raises(ValueError if bad==-1 and type(bad)is int else TypeError):call(bad)


def test_numeric_factory_roles_do_not_mix_clocks_and_actual_instants(monkeypatch):
    import rstimes.pddt as module
    monkeypatch.setattr(module,"_local_timezone",lambda:timezone(timedelta(hours=8)))
    assert Pddt.fromseconds(0,size=1,tz="Asia/Shanghai").hour.tolist()==[0]
    assert Pddt.frommicroseconds(0,size=1,tz="Asia/Shanghai").hour.tolist()==[0]
    assert Pddt.fromtimestamp(0,size=1,tz="Asia/Shanghai").hour.tolist()==[8]
    assert Pddt.fromtimestamp(0,size=1).hour.tolist()==[8]
    assert Pddt.utcfromtimestamp(0,size=1).hour.tolist()==[0]
    assert Pddt.utcfromtimestamp(0,size=1).tzinfo is timezone.utc
    assert Pddt.fromseconds(0,size=1).asi8.tolist()==[0]


@pytest.mark.parametrize("source", [[1.5],np.array([1.5],dtype="f8"),pd.Series([1.5]),pd.array([1.5],dtype="Float64")])
def test_seconds_and_output_unit_are_independent(source):
    assert Pddt.fromseconds(source,unit="ms").asi8.tolist()==[1500]
    with pytest.raises(ValueError):Pddt.fromseconds(source,unit="s")
    with pytest.raises(TypeError):Pddt.frommicroseconds(source)


def test_scalar_size_collection_and_once_read_protocols():
    class Number:
        reads=0
        def __float__(self):self.reads+=1;return 1.5
    number=Number()
    assert Pddt.fromseconds(number,size=4).asi8.tolist()==[1500000]*4
    assert number.reads==1
    with pytest.raises(ValueError):Pddt.fromseconds(1)
    with pytest.raises(ValueError):Pddt.fromseconds([1],size=1)
    class Integer:
        reads=0
        def __index__(self):self.reads+=1;return 1000
    integer=Integer()
    assert Pddt.frommicroseconds(integer,size=3).asi8.tolist()==[1000]*3
    assert integer.reads==1


def test_numeric_nanoseconds_keep_signed_submicrosecond_values():
    result=Pddt.fromseconds([1e-9,-1e-9])
    assert result.unit=="ns" and result.asi8.tolist()==[1,-1]
    assert Pddt.fromseconds(np.array([1e-9,-1e-9])).asi8.tolist()==[1,-1]
    with pytest.raises(ValueError):Pddt.fromseconds([1e-9],unit="us")


def test_native_unsigned_and_python_bigints_can_select_a_lossless_wider_unit():
    value=((1<<63)//1000+1)*1000
    for source in ([value],np.array([value],dtype="uint64")):
        assert Pddt.frommicroseconds(source,unit="ms").asi8.tolist()==[value//1000]
        with pytest.raises(OverflowError):Pddt.frommicroseconds(source)
    for source in ([np.iinfo("i8").min],np.array([np.iinfo("i8").min],dtype="i8")):
        with pytest.raises(OverflowError):Pddt.frommicroseconds(source)


@pytest.mark.parametrize("call", [Pddt.fromseconds,Pddt.frommicroseconds,Pddt.fromtimestamp,Pddt.utcfromtimestamp])
def test_numeric_factory_missing_values_and_invalid_types(call):
    assert call([None,pd.NA,pd.NaT,np.nan]).isna().tolist()==[True]*4
    assert call([]).unit=="us"
    for bad in (True,np.bool_(False),"1",b"1",datetime(2024,5,7)):
        with pytest.raises(TypeError):call(bad,size=1)
    for bad in (np.inf,-np.inf):
        with pytest.raises(TypeError if call.__name__=="frommicroseconds" else OverflowError):call([bad])


def test_nullable_integer_mask_does_not_swallow_a_real_minimum_integer():
    result=Pddt.frommicroseconds(pd.array([1,pd.NA],dtype="Int64"))
    assert result.asi8.tolist()==[1,np.iinfo("i8").min]
    with pytest.raises(OverflowError):
        Pddt.frommicroseconds(pd.array([np.iinfo("i8").min,pd.NA],dtype="Int64"))


def test_native_numeric_strides_endian_and_polars_do_not_change_values():
    source=np.arange(8,dtype="i8")[::2].astype(">i8")
    assert Pddt.frommicroseconds(source).asi8.tolist()==[0,2,4,6]
    pl=pytest.importorskip("polars")
    assert Pddt.fromseconds(pl.Series([1.5,None])).asi8.tolist()==[1500000,np.iinfo("i8").min]


def test_unused_local_zone_is_not_loaded_for_empty_or_all_missing_timestamps(monkeypatch):
    import rstimes.pddt as module
    def forbidden():raise AssertionError("unused local timezone")
    monkeypatch.setattr(module,"_local_timezone",forbidden)
    assert Pddt.fromtimestamp([]).empty
    assert Pddt.fromtimestamp([None,np.nan]).isna().all()
