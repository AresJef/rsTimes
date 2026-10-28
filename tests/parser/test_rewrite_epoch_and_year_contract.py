"""P05/P06/P17: shared precision, year fields and once-prepared options."""
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from rstimes import Configs, Pydt, parse, parse_str, parse_to_epoch


@pytest.mark.parametrize("value,expected", [
    (1e-9, 1), (-1e-9, -1), (0.5e-9, 0), (-0.5e-9, -1),
    (float(2**40), 2**40 * 10**9), (2**60, 2**60 * 10**9),
])
def test_epoch_numeric_precision_is_selected_before_microseconds(value, expected):
    assert parse_to_epoch(value, unit="ns") == expected


def test_numeric_default_keeps_its_existing_microsecond_role():
    assert parse_str("12:30", default=-1e-9) == datetime(1970, 1, 1, 12, 30)
    assert parse_to_epoch("12:30", default=-1e-9, unit="s") == 45000


@pytest.mark.parametrize("isoformat", [True, False])
@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("text", ["0000-01-01", "0000-02-29", "Jan 1 0000"])
def test_both_text_paths_deliver_zero_year_to_the_target(text, isoformat, strict):
    seen = []

    class Target(datetime):
        def __new__(cls, year, month, day, *clock, **kwargs):
            seen.append((year, month, day))
            return datetime.__new__(cls, 2000, month, day, *clock, **kwargs)

    parse_str(text, isoformat=isoformat, strict=strict, dtclass=Target)
    assert seen == [(0, 2, 29) if "02-29" in text else (0, 1, 1)]


@pytest.mark.parametrize("isoformat", [True, False])
def test_zero_year_integer_output_and_target_capacity_are_distinct(isoformat):
    assert parse_to_epoch("0000-01-01", unit="us", isoformat=isoformat) == -62167219200000000
    with pytest.raises(ValueError):
        parse_str("0000-01-01", isoformat=isoformat)
    with pytest.raises(ValueError):
        Pydt.parse("0000-01-01", isoformat=isoformat)


@pytest.mark.parametrize("call", [parse, parse_to_epoch, Pydt.parse])
@pytest.mark.parametrize("bad", [True, np.bool_(False)])
def test_boolean_is_not_a_date_or_numeric_epoch(call, bad):
    with pytest.raises(TypeError):
        call(bad)


@pytest.mark.parametrize("call", [parse, parse_to_epoch, Pydt.parse])
@pytest.mark.parametrize("option", ["yearfirst", "dayfirst"])
def test_unused_ordering_option_is_still_a_boolean_option(call, option):
    with pytest.raises(TypeError):
        call(datetime(2024, 5, 7), **{option: 1})


@pytest.mark.parametrize("call", [parse, parse_to_epoch])
def test_unused_default_is_not_parsed_for_native_values(call):
    assert call(datetime(2024, 5, 7), default=True) == call(datetime(2024, 5, 7))
    with pytest.raises(TypeError):
        call("2024-05-07", default=True)


def test_negative_reference_century_uses_the_approved_window():
    import pandas as pd
    reference = pd.Timestamp(np.datetime64("-0051-05-07", "s"))
    seen = []

    class Target(datetime):
        def __new__(cls, year, month, day, *clock, **kwargs):
            seen.append(year)
            return datetime.__new__(cls, 2000, month, day, *clock, **kwargs)

    parse_str("99-05-07", default=reference, dtclass=Target, isoformat=False)
    assert seen == [-101]


@pytest.mark.parametrize("fields", [
    (1,1,1,0,0,0),
    (1969,12,30,23,59,59),
    (2024,3,10,2,30,0),
    (2024,5,7,15,30,0),
    (2024,11,3,1,30,0),
])
@pytest.mark.parametrize("fold", [0,1])
@pytest.mark.parametrize("strict", [False,True])
@pytest.mark.parametrize("isoformat", [False,True])
def test_regional_epoch_uses_completed_fields_and_keeps_nanosecond_tail(fields,fold,strict,isoformat):
    cfg=Configs();cfg.add_tzone("America/New_York")
    y,m,d,h,minute,s=fields
    value=datetime(y,m,d,h,minute,s,123456,tzinfo=ZoneInfo("America/New_York"),fold=fold)
    offset=value.utcoffset()
    offset_us=(offset.days*86400+offset.seconds)*1_000_000+offset.microseconds
    seconds=(value.toordinal()-719163)*86400+h*3600+minute*60+s
    expected=seconds*1_000_000_000+123456789-offset_us*1000
    text=f"{y:04}-{m:02}-{d:02} {h:02}:{minute:02}:{s:02}.123456789 America/New_York"
    options=dict(cfg=cfg,default=datetime(2000,1,1,fold=fold),strict=strict,isoformat=isoformat,ignoretz=False)
    assert parse_to_epoch(text,unit="ns",**options)==expected
    assert parse_to_epoch(text,unit="us",**options)==expected//1000


def test_regional_epoch_keeps_the_stored_fold_of_a_real_default_subclass():
    class Default(datetime):
        @property
        def fold(self):return 1
    default=Default(2000,1,1,fold=0)
    cfg=Configs();cfg.add_tzone("America/New_York")
    text="2024-11-03 01:30 America/New_York"
    assert parse_to_epoch(text,cfg=cfg,default=default,ignoretz=False)==parse_to_epoch(
        text,cfg=cfg,default=datetime(2000,1,1,fold=0),ignoretz=False)
