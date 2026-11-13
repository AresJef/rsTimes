"""PR-027: a ZoneInfo label is not proof of the original transition rules."""
from datetime import datetime, timedelta, timezone
from importlib import resources
from io import BytesIO
from pathlib import Path
from zoneinfo import TZPATH, ZoneInfo

import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt

WALL = datetime(2024,1,1,12)
EPOCH = datetime(1970,1,1,tzinfo=timezone.utc)


def utc_zone_file(kind=ZoneInfo, key="Asia/Shanghai"):
    path = next((Path(root)/"UTC" for root in TZPATH if (Path(root)/"UTC").is_file()), None)
    data = path.read_bytes() if path is not None else resources.files("tzdata.zoneinfo").joinpath("UTC").read_bytes()
    return kind.from_file(BytesIO(data), key=key)


def tick(wall, zone, unit):
    delta = wall.replace(tzinfo=zone).astimezone(timezone.utc)-EPOCH
    ns = ((delta.days*86400+delta.seconds)*1000000+delta.microseconds)*1000
    return ns//{"s":1000000000,"ms":1000000,"us":1000,"ns":1}[unit]


@pytest.mark.parametrize("direction", ("file_to_named", "named_to_file"))
@pytest.mark.parametrize("unit", ("s", "ms", "us", "ns"))
def test_replace_same_key_distinct_rules_keeps_wall_and_changes_instant(direction, unit):
    file_zone, named = utc_zone_file(), ZoneInfo("Asia/Shanghai")
    source, target = (file_zone,named) if direction=="file_to_named" else (named,file_zone)
    value = Pddt([WALL.replace(tzinfo=source),None], unit=unit, name="clock")
    before = value.asi8.tolist()
    result = value.pddt.replace(tzinfo=target)
    assert result.asi8.tolist() == [tick(WALL,target,unit), -(2**63)]
    assert result is not value and result.tz is target
    assert result.unit == unit and result.name == "clock"
    assert value.asi8.tolist() == before and value.tz is source


@pytest.mark.parametrize("mode", ("empty", "all_missing"))
@pytest.mark.parametrize("direction", ("file_to_named", "named_to_file"))
def test_empty_or_missing_rows_still_replace_distinct_zone_metadata(mode, direction):
    file_zone, named = utc_zone_file(), ZoneInfo("Asia/Shanghai")
    source,target = (file_zone,named) if direction=="file_to_named" else (named,file_zone)
    value = Pddt([],tz=source,unit="ns",name="clock") if mode=="empty" else Pddt([None,None],tz=source,unit="ns",name="clock")
    result = value.pddt.replace(tzinfo=target)
    assert result.tz is target and result is not value
    assert result.unit == "ns" and result.name == "clock" and len(result) == len(value)
    assert result.isna().tolist() == value.isna().tolist() and value.tz is source


@pytest.mark.parametrize("reverse", (False,True))
def test_mixed_same_labels_different_rules_need_explicit_target(reverse):
    file_zone,named = utc_zone_file(),ZoneInfo("Asia/Shanghai")
    values=[WALL.replace(tzinfo=file_zone),WALL.replace(tzinfo=named)]
    if reverse:values.reverse()
    with pytest.raises(ValueError):
        Pddt(values,unit="us")
    result = Pddt(values,tz="UTC",unit="us",name="clock")
    assert result.asi8.tolist() == [tick(WALL,value.tzinfo,"us") for value in values]
    assert result.name == "clock" and result.unit == "us"


@pytest.mark.parametrize("mode", ("same_file", "named_no_cache", "passive_no_cache", "fixed_equal"))
def test_proven_same_rules_keep_existing_identity_shortcuts(mode):
    class Passive(ZoneInfo):pass
    if mode=="same_file":
        source=target=utc_zone_file()
    elif mode=="named_no_cache":
        source,target=ZoneInfo("Asia/Shanghai"),ZoneInfo.no_cache("Asia/Shanghai")
    elif mode=="passive_no_cache":
        source,target=Passive.no_cache("Asia/Shanghai"),ZoneInfo.no_cache("Asia/Shanghai")
    else:
        source,target=timezone(timedelta(hours=2),"first"),timezone(timedelta(hours=2),"second")
    value=Pddt([WALL.replace(tzinfo=source)],unit="us")
    result=value.pddt.replace(tzinfo=target)
    assert result is value and result.asi8.tolist()==[tick(WALL,source,"us")]


@pytest.mark.parametrize("direction", ("file_to_named", "named_to_file"))
def test_ns_tail_survives_real_timezone_replacement(direction):
    file_zone,named=utc_zone_file(),ZoneInfo("Asia/Shanghai")
    source,target=(file_zone,named) if direction=="file_to_named" else (named,file_zone)
    timestamp=pd.Timestamp("2024-01-01T12:00:00.000000123",tz=source)
    value=Pddt([timestamp],unit="ns",name="clock")
    result=value.pddt.replace(tzinfo=target)
    assert result.asi8.tolist()==[tick(WALL,target,"ns")+123]
    assert result.unit=="ns" and result.name=="clock" and result.tz is target


@pytest.mark.parametrize("direction", ("file_to_named", "named_to_file"))
def test_explicit_range_target_preserves_endpoint_instant(direction):
    file_zone,named=utc_zone_file(),ZoneInfo("Asia/Shanghai")
    source,target=(file_zone,named) if direction=="file_to_named" else (named,file_zone)
    result=Pddt.date_range(WALL.replace(tzinfo=source),periods=2,freq="D",tz=target,unit="us",name="clock")
    first=tick(WALL,source,"us")
    assert result.asi8.tolist()==[first,first+86400000000]
    assert result.tz is target and result.unit=="us" and result.name=="clock"


def test_live_business_methods_do_not_use_cached_named_eligibility():
    class Business(ZoneInfo):pass
    source=Business.no_cache("UTC")
    target=ZoneInfo("UTC")
    warm=Pddt([WALL.replace(tzinfo=source)],unit="us")
    assert warm.pddt.replace(tzinfo=target) is warm
    Business.utcoffset=lambda self,value:timedelta(hours=2)
    Business.dst=lambda self,value:timedelta(0)
    def fromutc(self,value):
        return (value.replace(tzinfo=None)+timedelta(hours=2)).replace(tzinfo=self)
    Business.fromutc=fromutc
    current=Pddt([WALL.replace(tzinfo=source)],unit="us")
    result=current.pddt.replace(tzinfo=target)
    assert result.asi8.tolist()==[tick(WALL,target,"us")]
    assert result.tz is target and result is not current


@pytest.mark.parametrize("length", (0,1))
@pytest.mark.parametrize("key", ("UTC","Asia/Shanghai"))
def test_pldt_file_target_rejection_stays_separate_from_pddt_rule_support(length,key):
    pytest.importorskip("polars")
    from rstimes import Pldt
    file_zone=utc_zone_file(key=key)
    with pytest.raises(ValueError):
        Pldt(np.arange(length),unit="us",tz=file_zone)
