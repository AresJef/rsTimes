"""PR-026/028: real frequency and mask roles at the pandas host boundary."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt


@pytest.mark.parametrize("mode", ("plain","passive","display"))
@pytest.mark.parametrize("operation", ("range","round","ceil","floor"))
def test_real_duration_frequency_does_not_become_displayed_text(mode,operation):
    events=[]
    class Passive(timedelta):pass
    class Display(timedelta):
        @property
        def __class__(self):events.append("display");return str
    value=timedelta(minutes=1) if mode=="plain" else (Passive if mode=="passive" else Display)(minutes=1)
    if operation=="range":
        actual=Pddt.date_range("2024-01-01",periods=3,freq=value,unit="us")
        expected=[1704067200000000,1704067260000000,1704067320000000]
    else:
        source=Pddt(["2024-01-01T00:00:31",None],unit="us")
        actual=getattr(source,operation)(freq=value)
        target=1704067200000000 if operation=="floor" else 1704067260000000
        expected=[target,-2**63]
    assert actual.asi8.tolist()==expected and actual.unit=="us" and events==[]


@pytest.mark.parametrize("text", ("D","2h","15min","ME","MS"))
def test_parsed_string_frequency_uses_new_offset_type_and_stays_native(text,monkeypatch):
    from rstimes._range import frequency
    class Text(str):
        def __str__(self):raise AssertionError("must read native text")
    plan,metadata,delegated=frequency(Text(text))
    assert plan is not None and metadata is not None and delegated is False
    def forbidden(*args,**kwargs):raise AssertionError("native rule must not delegate")
    monkeypatch.setattr(pd,"date_range",forbidden)
    result=Pddt.date_range("2024-01-01",periods=2,freq=Text(text),unit="us")
    assert len(result)==2 and result.unit=="us"


def test_calendar_day_and_elapsed_day_keep_different_dst_meanings():
    zone=ZoneInfo("America/New_York")
    calendar=Pddt.date_range("2024-03-09T12:00",periods=2,freq="D",tz=zone,unit="us")
    elapsed=Pddt.date_range("2024-03-09T12:00",periods=2,freq=timedelta(days=1),tz=zone,unit="us")
    assert calendar.hour.tolist()==[12,12] and elapsed.hour.tolist()==[12,13]
    assert calendar.asi8[1]-calendar.asi8[0]==23*3600*10**6
    assert elapsed.asi8[1]-elapsed.asi8[0]==24*3600*10**6


def test_real_business_offset_stays_original_mature_operand():
    from rstimes._range import frequency
    events=[]
    class Business(pd.DateOffset):
        @property
        def __class__(self):events.append("display");return str
    offset=Business(days=1)
    plan,metadata,delegated=frequency(offset)
    assert plan is None and metadata is offset and delegated and events==[]
    # Upstream may itself read its operand's display class: preserve that engine.
    args=dict(start=datetime(2024,1,1),periods=2,freq=offset)
    try:expected=pd.date_range(**args)
    except Exception as original:
        with pytest.raises(type(original)):Pddt.date_range(**args)
    else:
        actual=Pddt.date_range(**args)
        assert actual.asi8.tolist()==expected.as_unit(actual.unit).asi8.tolist()


@pytest.mark.parametrize("mode", ("plain","passive","display"))
@pytest.mark.parametrize("dtype", (bool,object))
def test_real_bool_mask_keeps_pandas_element_domain_and_one_iteration(mode,dtype):
    events=[]
    class Passive(np.ndarray):pass
    class Display(np.ndarray):
        @property
        def __class__(self):events.append("display");return pd.DataFrame
        def __iter__(self):events.append("iterate");return super().__iter__()
    source=np.array([True,False],dtype=dtype)
    mask=source if mode=="plain" else source.view(Passive if mode=="passive" else Display)
    actual=Pddt(["2024-11-03T01:30"]*2,tz="America/New_York",unit="us",ambiguous=mask)
    assert actual.asi8.tolist()==[1730611800000000,1730615400000000]
    assert events==(["iterate"] if mode=="display" else [])


@pytest.mark.parametrize("values,nonexistent,error,role", [
    ([1,0],"raise",TypeError,"ambiguous"), ([[True,False]],"raise",ValueError,"ambiguous"),
    ([True],"raise",ValueError,"ambiguous"), ([True,False],"invalid",ValueError,"nonexistent"),
    ([True],"invalid",ValueError,"nonexistent"), ([1,0],"invalid",TypeError,"ambiguous")])
def test_policy_shape_first_error_and_no_broadcast(values,nonexistent,error,role):
    mask=np.asarray(values)
    with pytest.raises(error,match=role):
        Pddt(["2024-11-03T01:30"]*2,tz="America/New_York",ambiguous=mask,nonexistent=nonexistent)
