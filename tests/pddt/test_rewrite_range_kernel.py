"""P09 production native sequence core on already prepared integer endpoints."""
from datetime import timedelta
import numpy as np
import pandas as pd
from _fixed_pandas3 import date_range as fixed_date_range
import pytest
from rstimes._range import frequency
from rstimes._native import _pddt_range_sequence,_pddt_policies


def coordinate(value):
    return None if value is None else int(np.datetime64(value,"ns").view("i8"))


def sequence(start=None,end=None,periods=None,freq=None,unit="us",inclusive="both"):
    plan,metadata,delegate=frequency(freq)
    assert not delegate
    data,selected,zone,left,right=_pddt_range_sequence(coordinate(start),coordinate(end),periods,plan,
        _pddt_policies("raise","raise"),unit,None,inclusive)
    values=np.frombuffer(data,dtype=f"datetime64[{selected}]")
    return values[left:len(values)-right if right else None]


@pytest.mark.parametrize("freq",["s","15min","1h30min","-1h30min","D","-1D","2D","W","2W-MON","-2W-FRI","ME","MS","2ME","-1ME","-1MS","QS-FEB","QE-APR","YS-MAR","YE-JUN","B","-1B","BMS","BME","BQS-FEB","BQE-APR","BYS-MAR","BYE-JUN","SMS","SME","SMS-10","SME-20","WOM-2MON","LWOM-FRI"])
@pytest.mark.parametrize("source",["start","end"])
def test_all_static_native_families_match_fixed_pandas3(freq,source):
    args={source:"2024-02-17 12:30", "periods":5,"freq":freq}
    expected=fixed_date_range(**args,unit="us")
    actual=sequence(**args)
    assert actual.view("i8").tolist()==expected.asi8.tolist(),(freq,source)


@pytest.mark.parametrize("freq",["3h","D","-1D","W-MON","ME","B","SME","WOM-2MON"])
def test_two_endpoints_generate_only_the_directed_interval(freq):
    for start,end in [("2024-01-17 12:30","2024-05-03 13:00"),("2024-05-03 13:00","2024-01-17 12:30")]:
        expected=fixed_date_range(start=start,end=end,freq=freq,unit="us")
        assert sequence(start=start,end=end,freq=freq).view("i8").tolist()==expected.asi8.tolist()


@pytest.mark.parametrize("size",[0,1,2,5])
@pytest.mark.parametrize("inclusive",["both","left","right","neither"])
def test_fixed_small_counts_and_inclusive_match_pandas(size,inclusive):
    args=dict(start="2024-01-02",periods=size,freq="D",inclusive=inclusive)
    expected=fixed_date_range(**args,unit="us")
    assert sequence(**args).view("i8").tolist()==expected.asi8.tolist()


@pytest.mark.parametrize("start,end,expected",[(0,5,[0,1,3,5]),(5,0,[5,3,1,0])])
def test_integer_linspace_avoids_float_rounding_and_truncation(start,end,expected):
    data,unit,zone,left,right=_pddt_range_sequence(start,end,4,None,_pddt_policies("raise","raise"),"ns")
    assert np.frombuffer(data,dtype="int64").tolist()==expected


def test_static_calendar_holidays_masks_offsets_and_unanchored_week_are_complete():
    offsets=[pd.offsets.Week(),pd.offsets.BusinessDay(offset=timedelta(hours=2)),
        pd.offsets.CustomBusinessDay(weekmask="Mon Wed Fri",holidays=["2024-01-03","2024-01-08"]),
        pd.offsets.CustomBusinessMonthEnd(holidays=["2024-01-31"]),
        pd.offsets.CustomBusinessMonthBegin(weekmask="Sun Mon Tue Wed Thu"),
        pd.offsets.CustomBusinessMonthEnd(offset=timedelta(hours=2)),
        pd.offsets.BusinessDay(normalize=True),pd.offsets.MonthEnd(normalize=True)]
    for offset in offsets:
        for source in ("start","end"):
            args={source:"2024-01-10 09:15:20", "periods":4,"freq":offset}
            expected=fixed_date_range(**args,unit="us")
            assert sequence(**args).view("i8").tolist()==expected.asi8.tolist(),(offset,source)


def test_storage_vocabulary_is_3x_even_when_old_pandas_might_accept_aliases():
    for bad in ("m","M","H","T","S","L","U","N","BM","Q","A","Y","1h-30min"):
        with pytest.raises(ValueError):frequency(bad)
    for zero in ("0D","0s"):
        with pytest.raises(ValueError):frequency(zero)
    for legal in ("ME","15min","1.5h","1.0D"):
        assert frequency(legal)[2] is False


def test_duration_is_fixed_elapsed_and_genuine_custom_offsets_delegate_wholly():
    plan,metadata,delegate=frequency(timedelta(days=1))
    assert plan.tick==86400_000_000_000 and not delegate
    class Custom(pd.offsets.MonthEnd):pass
    custom=Custom(2)
    assert frequency(custom)==(None,custom,True)
    business_hour=pd.offsets.BusinessHour(start="10:00",end="15:00")
    assert frequency(business_hour)==(None,business_hour,True)
