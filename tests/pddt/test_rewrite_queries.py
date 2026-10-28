"""Native local facts and strictly typed scalar/row conditions."""
from datetime import date
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Pydt

_FACTS=['isoyear','isoweek','isoweekday','days_in_year','days_bf_year','days_in_quarter','days_bf_quarter','day_of_quarter','days_bf_month','day_of_month','millisecond','is_long_year']
@pytest.mark.parametrize('method',_FACTS)
@pytest.mark.parametrize('text',['2024-02-29 12:34:56.123456','2021-01-01','2020-12-31'])
def test_shared_facts_match_current_scalar_contract(method,text):
    x=Pddt([text,None],unit='us')
    scalar=Pydt.fromdatetime(pd.Timestamp(text).to_pydatetime())
    value=getattr(x,method)
    result=value() if callable(value) else value
    reference=getattr(scalar,method)
    assert result[0]==(reference() if callable(reference) else reference)
    if method=='is_long_year':assert result.tolist()==[bool(getattr(scalar,method)()),False]
    else:assert str(result.dtype)=='Int64' and pd.isna(result[1])


def test_signed_iso_and_zero_year_are_not_clamped_to_pydt():
    x=Pddt(['0000-01-01','0000-01-03'],unit='us')
    assert x.isoyear().tolist()==[-1,0]
    assert x.isoweek().tolist()==[52,1]
    assert x.isoweekday().tolist()==[6,1]


@pytest.mark.parametrize('method,values,expected',[('is_year',[2024,2023],[True,False]),('is_quarter',[1,9],[True,False]),('is_month',['February','January'],[True,False]),('is_weekday',['Thursday','Tuesday'],[True,False]),('is_day',[29,-1],[True,False])])
def test_row_conditions_are_positional_and_allow_numeric_nonmatches(method,values,expected):
    x=Pddt(['2024-02-29','2024-02-29'])
    assert getattr(x,method)(pd.Series(values,index=[10,2])).tolist()==expected
    with pytest.raises(ValueError):getattr(x,method)([1])
    for bad in [None,True,1.0,[None,1],[1.0,1.0]]:
        with pytest.raises(TypeError):getattr(x,method)(bad)
    assert getattr(Pddt([None]),method)(1).tolist()==[False]


def test_names_and_missing_target_validation_apply_to_empty_data():
    x=Pddt([])
    for name in ['is_month','is_weekday']:
        for value in ['', 'unknown']:
            with pytest.raises(ValueError):getattr(x,name)(value)
        with pytest.raises(TypeError):getattr(x,name)(None)


def test_local_queries_do_not_use_utc_date_fields():
    x=Pddt([0,None],unit='s',tz='America/New_York')
    assert x.year.tolist()[0]==1969
    assert x.is_month(12).tolist()==[True,False]
    assert x.day_of_month().tolist()[0]==31


def test_wide_year_property_does_not_overflow_a_pandas_int32_field():
    raw=np.array([0],dtype='int64').view('datetime64[s]')
    raw[0]=np.datetime64('3000000000-01-01','s')
    x=Pddt(raw)
    assert x.year.tolist()==[3000000000]
    assert x.is_year(3000000000).tolist()==[True]
    assert str(Pddt(['2024-01-01']).year.dtype)=='int32'
    assert pd.isna(Pddt([None]).year[0])


@pytest.mark.parametrize('attribute,expected',[
    ('day_of_year',[60,60,None]),
    ('days_in_month',[29,31,None]),
    ('is_leap_year',[True,False,False]),
])
def test_standard_date_properties_keep_local_values_and_missing_positions(attribute,expected):
    x=Pddt(['2000-02-29 23:30','2100-03-01 00:30',None],tz='Asia/Shanghai')
    result=getattr(x,attribute)
    assert len(result)==len(expected)
    for actual,wanted in zip(result,expected):
        if wanted is None:
            assert pd.isna(actual)
        else:
            assert actual==wanted
    assert len(getattr(Pddt([]),attribute))==0


def test_leap_year_targets_support_scalar_and_row_values_in_both_directions():
    x=Pddt(['2024-01-01','2030-01-01',None])
    assert x.leap_bt_year([2030,2024,2024]).tolist()[:2]==[2,2]
    assert pd.isna(x.leap_bt_year(2024)[2])
    with pytest.raises(TypeError):x.leap_bt_year([2030,None,2024])


def test_standard_iso_table_has_unsigned_capacity_and_real_missing_values():
    x=Pddt(["2021-01-01",None],name="date")
    result=x.isocalendar()
    assert list(result.columns)==["year","week","day"]
    assert result.iloc[0].tolist()==[2020,53,5]
    assert result.iloc[1].isna().all()
    assert all(str(d)=="UInt32" for d in result.dtypes)
    assert result.index.equals(x) and result.index.name=="date"
    assert Pddt(["0000-01-03"]).isocalendar()["year"].tolist()==[0]
    with pytest.raises(OverflowError,match="UInt32"):
        Pddt(["0000-01-01"]).isocalendar()
    with pytest.raises(OverflowError,match="UInt32"):
        Pddt(np.array(["4294967296-01-04"],dtype="datetime64[s]")).isocalendar()
    empty=Pddt([]).isocalendar()
    assert empty.empty and all(str(d)=="UInt32" for d in empty.dtypes)


def test_dst_and_offsets_use_each_actual_occurrence_and_negative_dst():
    x=Pddt(["2024-01-01","2024-07-01",None],tz="America/New_York")
    assert x.is_dst().tolist()==[False,True,False]
    assert x.utcoffset_seconds().tolist()[:2]==[-18000,-14400]
    assert pd.isna(x.utcoffset_seconds()[2])
    dublin=Pddt(["2024-01-01","2024-07-01"],tz="Europe/Dublin")
    assert dublin.is_dst().tolist()==[bool(t.dst()) for t in dublin.to_pydatetime()]
    from datetime import tzinfo,timedelta
    class NegativeDST(tzinfo):
        def utcoffset(self,value):return timedelta(0)
        def dst(self,value):return timedelta(hours=-1)
        def tzname(self,value):return "NEG"
        def fromutc(self,value):return value
    assert Pddt(["2024-01-01"],tz=NegativeDST()).is_dst().tolist()==[True]
    naive=Pddt(["2024-01-01",None])
    assert naive.is_dst().tolist()==[False,False]
    assert naive.utcoffset_seconds().isna().all()
    from datetime import timezone,timedelta
    fixed=Pddt([0],unit="us",tz=timezone(timedelta(microseconds=-1)))
    assert fixed.utcoffset_seconds().tolist()==[-1]
    assert fixed.is_dst().tolist()==[False]


def test_current_clock_queries_are_lazy_and_prepare_the_local_clock_once(monkeypatch,request):
    import rstimes._localization as zones
    from datetime import timezone
    calls=[]
    zones.named_timezone.cache_clear()
    request.addfinalizer(zones.named_timezone.cache_clear)
    def local():calls.append(1);return timezone.utc
    monkeypatch.setattr(zones,"local_timezone",local)
    assert Pddt([None]).is_past().tolist()==[False]
    assert Pddt([]).is_future().empty
    assert calls==[]
    x=Pddt(["1900-01-01","2200-01-01",None])
    assert x.is_past().tolist()==[True,False,False]
    assert len(calls)==1
    assert x.is_future().tolist()==[False,True,False]
    assert len(calls)==1
    aware=Pddt(["1900-01-01","2200-01-01",None],tz="America/New_York")
    assert aware.is_past().tolist()==[True,False,False]
    assert aware.is_future().tolist()==[False,True,False]
    assert len(calls)==1
