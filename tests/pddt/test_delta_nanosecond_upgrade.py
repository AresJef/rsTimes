"""Pddt's fixed-unit exits consume the exact Delta value without us carriers."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from rstimes import Delta, Pddt


@pytest.mark.parametrize("unit,scale", [("s",1_000_000_000),("ms",1_000_000),("us",1000),("ns",1)])
def test_delta_complete_precision_and_fixed_unit_in_three_directions(unit,scale):
    source=Pddt(np.array([0,1,-1],dtype="i8").view(f"datetime64[{unit}]"),unit=unit,name="time")
    delta=Delta(nanoseconds=scale)
    for result in (source+delta,delta+source):
        assert type(result) is Pddt
        assert result.unit==unit and result.name=="time"
        assert result.asi8.tolist()==[1,2,0]
    result=source-delta
    assert result.unit==unit and result.asi8.tolist()==[-1,0,-2]
    if unit != "ns":
        for operation in (lambda:source+Delta(nanoseconds=1),lambda:Delta(nanoseconds=1)+source,
                          lambda:source-Delta(nanoseconds=1)):
            with pytest.raises(ValueError):
                operation()
    assert source+Delta(microseconds=1,nanoseconds=-1000) is source
    assert source.asi8.tolist()==[0,1,-1]


def test_delta_submicrosecond_replacement_and_merge_preserve_presence():
    source=Pddt(["2024-01-01 00:00:00.123456789"],unit="ns")
    for delta,want in [(Delta(nanosecond=2),123456002),
                       (Delta(microsecond=1),1000),
                       (Delta(microsecond=1,nanosecond=2),1002),
                       (Delta(nanosecond=2)+Delta(microsecond=1),1002),
                       (Delta(nanosecond=0),123456000)]:
        assert (source+delta).asi8[0]%1_000_000_000 == want
    assert source.asi8[0]%1_000_000_000==123456789


def test_delta_columns_pair_exactly_and_reject_missing_even_on_source_nat():
    source=Pddt(["2024-01-01",None,"2024-01-03"],unit="ns")
    result=source+[Delta(nanoseconds=1),Delta(nanoseconds=7),Delta(nanoseconds=-1)]
    assert result.asi8[[0,2]].tolist()==[source.asi8[0]+1,source.asi8[2]-1]
    assert pd.isna(result[1])
    with pytest.raises(TypeError):
        source+[Delta(),None,Delta()]
    with pytest.raises(ValueError):
        source+[Delta(nanoseconds=1)]


@pytest.mark.parametrize("zone", [None,timezone.utc,timezone(timedelta(hours=8)),"America/New_York"])
def test_delta_ns_local_calendar_keeps_zone_name_and_nat(zone):
    source=Pddt([datetime(2024,3,9,12),None],unit="ns",tz=zone,name="events")
    result=source+Delta(days=1,nanoseconds=789)
    assert result.name=="events" and result.unit=="ns" and result.tz==source.tz
    assert result[0].day==10 and result[0].hour==12 and result[0].nanosecond==789
    assert pd.isna(result[1])
    if zone=="America/New_York":
        assert result.asi8[0]-source.asi8[0]==23*3600*1_000_000_000+789
    else:
        assert result.asi8[0]-source.asi8[0]==24*3600*1_000_000_000+789


@pytest.mark.parametrize("year", [-12024,0,12024])
def test_delta_ns_kernel_retains_wide_calendar_until_the_fixed_unit_exit(year):
    source=Pddt(np.array([f"{year:04d}-01-31"],dtype="datetime64[us]"),unit="us")
    result=source+Delta(months=1,nanoseconds=1000)
    assert result[0].year==year and result[0].month==2 and result[0].day==29
    assert result[0].microsecond==1 and result.unit=="us"

