"""PR-032: classify the returned DST duration before unit projection."""
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt, Pydt

DAY_NS = 86400 * 10**9


class FalseDuration(timedelta):
    def __bool__(self):
        raise AssertionError("DST must not use a duration truth hook")


class BusinessZone(tzinfo):
    def __init__(self, adjustment):
        self.adjustment = adjustment
        self.calls = []
        self.error = None

    def utcoffset(self, value):
        return timedelta(0)

    def dst(self, value):
        self.calls.append(value)
        if self.error is not None:
            raise self.error
        return self.adjustment

    def fromutc(self, value):
        return value

    def tzname(self, value):
        return "BUSINESS"


VALID = [(None, -1), (timedelta(0), 0), (timedelta(hours=1), 1),
         (timedelta(hours=-1), 1), (FalseDuration(0), 0), (FalseDuration(seconds=1), 1)]
VALID += [(pd.Timedelta(n, unit="ns"), int(n != 0))
          for n in (0, 1, -1, 999, -999, 1000, -1000, DAY_NS-1, -DAY_NS+1)]
ENTRIES = ("scalar_dst", "scalar_bool", "scalar_tuple", "scalar_dict", "column_bool", "column_table")


def read(entry, scalar, column):
    if entry == "scalar_dst":return scalar.dst()
    if entry == "scalar_bool":return scalar.is_dst()
    if entry == "scalar_tuple":return scalar.timetuple().tm_isdst
    if entry == "scalar_dict":return scalar.timedict()["tm_isdst"]
    if entry == "column_bool":return column.is_dst().tolist()
    return column.timedf()["tm_isdst"].tolist()


@pytest.mark.parametrize("adjustment,marker", VALID)
@pytest.mark.parametrize("entry", ENTRIES)
def test_dst_reads_true_value_once_and_preserves_duration_identity(adjustment, marker, entry):
    zone = BusinessZone(adjustment)
    scalar = Pydt(2024,1,1,12,tzinfo=zone)
    column = Pddt([datetime(2024,1,1,12,tzinfo=zone), None,
                   datetime(2024,1,2,12,tzinfo=zone)], unit="ns")
    zone.calls.clear()
    actual = read(entry, scalar, column)
    if entry == "scalar_dst":assert actual is adjustment
    elif entry == "scalar_bool":assert actual is (marker > 0)
    elif entry.startswith("scalar"):assert actual == marker
    elif entry == "column_bool":assert actual == [marker > 0, False, marker > 0]
    else:assert actual[0] == marker and pd.isna(actual[1]) and actual[2] == marker
    if entry.startswith("scalar"):
        assert len(zone.calls) == 1 and zone.calls[0] is scalar
    else:
        assert len(zone.calls) == 2
        assert [(x.year,x.month,x.day,x.hour) for x in zone.calls] == [(2024,1,1,12),(2024,1,2,12)]
        assert all(x.tzinfo is zone for x in zone.calls)


@pytest.mark.parametrize("adjustment", [timedelta(hours=24), timedelta(hours=-24),
    *(pd.Timedelta(n,unit="ns") for n in (DAY_NS, -DAY_NS, DAY_NS+1, -DAY_NS-1))])
@pytest.mark.parametrize("entry", ENTRIES)
def test_dst_rejects_actual_day_boundaries_with_one_callback(adjustment, entry):
    zone = BusinessZone(adjustment)
    scalar = Pydt(2024,1,1,tzinfo=zone)
    column = Pddt([datetime(2024,1,1,tzinfo=zone)],unit="us")
    zone.calls.clear()
    with pytest.raises(ValueError, match=r"dst\(\) must.*24"):
        read(entry, scalar, column)
    assert len(zone.calls) == 1


@pytest.mark.parametrize("entry", ENTRIES)
def test_real_dst_exception_identity_is_retained(entry):
    zone = BusinessZone(timedelta(0))
    scalar = Pydt(2024,1,1,tzinfo=zone)
    column = Pddt([datetime(2024,1,1,tzinfo=zone)],unit="us")
    error = LookupError("real DST failure")
    zone.error = error
    zone.calls.clear()
    with pytest.raises(LookupError) as failure:
        read(entry,scalar,column)
    assert failure.value is error and len(zone.calls) == 1


@pytest.mark.parametrize("values", ([], [None,None]))
def test_empty_missing_and_utc_tables_do_not_call_dst(values):
    zone = BusinessZone(pd.Timedelta(1, unit="ns"))
    column = Pddt(values,unit="us",tz=zone)
    zone.error = AssertionError("DST callback must not run")
    zone.calls.clear()
    assert column.is_dst().tolist() == [False]*len(values)
    assert column.timedf()["tm_isdst"].isna().tolist() == [True]*len(values)
    assert column.utctimedf()["tm_isdst"].isna().tolist() == [True]*len(values)
    assert zone.calls == []


def test_valid_utc_table_does_not_call_dst():
    zone = BusinessZone(timedelta(hours=24))
    column = Pddt([datetime(2024,1,1,tzinfo=zone),None],unit="us")
    zone.error = AssertionError("UTC table must not read DST")
    zone.calls.clear()
    result = column.utctimedf()["tm_isdst"]
    assert result.iloc[0] == 0 and pd.isna(result.iloc[1]) and zone.calls == []


@pytest.mark.parametrize("zone,marker", [(None,-1),(timezone.utc,-1),
    (timezone(timedelta(hours=8)),-1),(ZoneInfo("UTC"),0)])
@pytest.mark.parametrize("wide", (False,True))
def test_fixed_wide_and_ordinary_unknown_marker_is_distinct_from_zero(zone,marker,wide):
    text = "12000-01-01" if wide else "2024-01-01"
    column = Pddt([np.datetime64(text,"us"),None],unit="us",tz=zone)
    assert column.is_dst().tolist() == [False,False]
    result = column.timedf()["tm_isdst"]
    assert result.iloc[0] == marker and pd.isna(result.iloc[1])
