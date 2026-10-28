"""P08 shared formatted grammar, current rules and final precision boundaries."""
from datetime import datetime,timezone,timedelta
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt,Configs


@pytest.mark.parametrize("text,fmt",[
    ("2024-05-07","%Y-%m-%d"),("2024-5-7","%Y-%m-%d"),
    ("07/05/2024 12:30","%d/%m/%Y %H:%M"),("２０２４-05-07","%Y-%m-%d"),
    ("20240102","%Y%m%d"),("2024131","%Y%m%d"),("2024111","%Y%m%d"),
    ("1234","%H%M%S"),("2024-W01-2","%G-W%V-%u"),
    ("2023-366","%Y-%j"),("2024-001","%Y-%j"),
    ("2024 00 0","%Y %U %w"),("2024 01 0","%Y %U %w"),
    ("2024 00 7","%Y %W %u"),("2024 01 1","%Y %W %u"),
    ("68-01-02","%y-%m-%d"),("69-01-02","%y-%m-%d"),
    ("12 AM","%I %p"),("12 PM","%I %p"),("1 pm","%I %p"),
    ("Feb 29 2024","%b %d %Y"),("February 29 2024","%B %d %Y"),
    ("Mon 2024-01-02","%a %Y-%m-%d"),("Tuesday 2024-W01","%A %G-W%V"),
    ("2024\t05 07","%Y %m %d"),("2024-01-02 12:30+08:00","%Y-%m-%d %H:%M%z"),
    ("2024-01-02 12:30-083012.5","%Y-%m-%d %H:%M%z"),
])
def test_standard_numeric_word_and_week_formats(text,fmt):
    expected=datetime.strptime(text,fmt)
    result=Pddt.strptime(text,fmt,size=2)
    if expected.tzinfo:
        delta=expected.astimezone(timezone.utc).replace(tzinfo=None)-datetime(1970,1,1)
    else:delta=expected-datetime(1970,1,1)
    ticks=delta.days*86400000000+delta.seconds*1000000+delta.microseconds
    assert result.unit=="us" and result.asi8.tolist()==[ticks,ticks]
    assert result.tzinfo is None if expected.tzinfo is None else result.tzinfo.utcoffset(None)==expected.utcoffset()


@pytest.mark.parametrize("text,fmt", [
    ("2024001", "%Y0%m"),
    ("2024105", "%Y1%m"),
    ("202400101", "%Y0%m%d"),
    ("202401", "%Y01"),
    ("2024001a02", "%Y001a%d"),
    ("20240012", "%G0%V%u"),
    ("2024٠01", "%Y٠%m"),
    ("111", "%m1%d"),
])
def test_numeric_literals_leave_each_directive_its_own_digits(text, fmt):
    """A digit in the format is a literal, not part of the preceding year."""
    from rstimes import Pydt

    expected = datetime.strptime(text, fmt)
    scalar = Pydt.strptime(text, fmt)
    assert scalar == expected and isinstance(scalar, Pydt)
    result = Pddt.strptime([text, text], fmt)
    tick = np.datetime64(expected, "us").view("i8")
    assert result.unit == "us" and result.asi8.tolist() == [tick, tick]


@pytest.mark.parametrize("text,fmt", [
    ("2024201", "%Y0%m"),
    ("20240", "%Y0%m"),
    ("2024001x", "%Y0%m"),
    ("20240000", "%G0%V%u"),
])
def test_numeric_literal_formats_reject_mismatch_missing_fields_and_garbage(text, fmt):
    from rstimes import Pydt

    with pytest.raises(ValueError):
        datetime.strptime(text, fmt)
    with pytest.raises(ValueError):
        Pydt.strptime(text, fmt)
    with pytest.raises(ValueError):
        Pddt.strptime([text], fmt)


@pytest.mark.parametrize("year",[-400,-1,0,1,9999,10000,25000])
def test_explicitly_delimited_wide_year_is_native_until_output_capacity(year):
    spelling=("-" if year<0 else "")+str(abs(year)).zfill(4)
    result=Pddt.strptime([spelling+"-01-02"],"%Y-%m-%d")
    assert result.year.tolist()==[year] and result.day.tolist()==[2]
    assert result.asi8[0]==np.datetime64(spelling+"-01-02","us").view("i8")


def test_fraction_complete_consumption_last_truncation_and_negative_epoch():
    fmt="%Y-%m-%d %H:%M:%S.%f"
    text="1970-01-01 00:00:00.123456789012345678901234"
    assert Pddt.strptime(text,fmt,size=1).asi8.tolist()==[123456789]
    for unit,expected in (("s",0),("ms",123),("us",123456),("ns",123456789)):
        assert Pddt.strptime(text,fmt,size=1,unit=unit).asi8.tolist()==[expected]
    assert Pddt.strptime("1969-12-31 23:59:59.999999999",fmt,size=1,unit="us").asi8.tolist()==[-1]
    assert Pddt.strptime("1970-01-01 00:00:00.123456000",fmt,size=1).unit=="us"
    assert Pddt.strptime("1970-01-01 00:00:00.1234560001",fmt,size=1).unit=="us"


def test_effective_configs_and_pure_format_cache_never_freeze_word_meanings():
    cfg=Configs();cfg.add_month("mymonth",2)
    assert Pddt.strptime("2024 mymonth 03","%Y %B %d",size=1,cfg=cfg).month.tolist()==[2]
    cfg.set_month({"mymonth":3})
    assert Pddt.strptime("2024 mymonth 03","%Y %B %d",size=1,cfg=cfg).month.tolist()==[3]
    with pytest.raises(ValueError):Pddt.strptime("2024 February 03","%Y %B %d",size=1,cfg=cfg)
    assert Pddt.strptime("2024 février 03","%Y %B %d",size=1).month.tolist()==[2]


def test_one_batch_uses_one_current_rules_snapshot():
    cfg=Configs();cfg.add_month("mymonth",2)
    def data():
        yield "2024 mymonth 03"
        cfg.set_month({"mymonth":3})
        yield "2024 mymonth 04"
    result=Pddt.strptime(data(),"%Y %B %d",cfg=cfg)
    assert result.month.tolist()==[2,2]
    assert Pddt.strptime("2024 mymonth 03","%Y %B %d",size=1,cfg=cfg).month.tolist()==[3]


def test_explicit_timezone_names_keep_zone_and_unknown_names_explain_configuration():
    cfg=Configs();cfg.add_tzoffset("CST",hours=8);cfg.add_tzone("America/New_York")
    fmt="%Y-%m-%d %H:%M %Z"
    result=Pddt.strptime("2024-01-02 12:00 CST",fmt,size=1,cfg=cfg)
    assert result.hour.tolist()==[12] and result.tzinfo.utcoffset(None)==timedelta(hours=8)
    ny=Pddt.strptime("2024-01-02 12:00 America/New_York",fmt,size=1,cfg=cfg)
    assert ny.hour.tolist()==[12] and ny.tzinfo.key=="America/New_York"
    with pytest.raises(ValueError,match="Configs"):
        Pddt.strptime("2024-01-02 12:00 CST",fmt,size=1)
    with pytest.raises(ValueError):Pddt.strptime("2024-01-02 12:00 +0800",fmt,size=1,cfg=cfg)


def test_region_wins_over_numeric_offset_in_both_field_orders():
    cfg=Configs();cfg.add_tzone("America/New_York")
    for text,fmt in [("2024-01-02 12:00 +0800 America/New_York","%Y-%m-%d %H:%M %z %Z"),("2024-01-02 12:00 America/New_York +0800","%Y-%m-%d %H:%M %Z %z")]:
        result=Pddt.strptime(text,fmt,size=1,cfg=cfg)
        assert result.tzinfo.key=="America/New_York" and result.hour.tolist()==[12]


@pytest.mark.parametrize("bad,fmt",[("2024-02-30","%Y-%m-%d"),("2021-W53-1","%G-W%V-%u"),("24-01-02","%Y-%m-%d"),("2024-05-07x","%Y-%m-%d"),("2024 00","%G %V"),("2024 01","%Y %V"),("2024-01-02 12:60","%Y-%m-%d %H:%M")])
def test_invalid_text_is_not_reparsed_or_clamped(bad,fmt):
    with pytest.raises(ValueError):Pddt.strptime(bad,fmt,size=1)


def test_missing_values_and_invalid_formats_are_checked_for_empty_columns():
    assert Pddt.strptime([None,pd.NA,pd.NaT,"NaT"],"%Y-%m-%d").isna().all()
    assert Pddt.strptime([],"%Y-%m-%d").unit=="us"
    with pytest.raises(ValueError):Pddt.strptime([],"%N")
    with pytest.raises(TypeError):Pddt.strptime([],"%Y",cfg=object())
    with pytest.raises(TypeError):Pddt.strptime([2024],"%Y")


def test_configured_zone_localizes_with_array_policy_and_final_precision_is_last():
    cfg=Configs();cfg.add_tzone("America/New_York")
    fmt="%Y-%m-%d %H:%M %Z"
    text="2024-11-03 01:30 America/New_York"
    with pytest.raises(ValueError):Pddt.strptime(text,fmt,size=1,cfg=cfg)
    early=Pddt.strptime(text,fmt,size=1,cfg=cfg,ambiguous=True)
    late=Pddt.strptime(text,fmt,size=1,cfg=cfg,ambiguous=False)
    assert late.asi8[0]-early.asi8[0]==3600*1_000_000
    result=Pddt.strptime("1970-01-01 00:00:00.000999999+00:00:00.000500",
        "%Y-%m-%d %H:%M:%S.%f%z",size=1,unit="ms")
    assert result.asi8.tolist()==[0]


def test_scalar_pydt_uses_same_grammar_and_last_microsecond_precision():
    from rstimes import Pydt
    cfg=Configs();cfg.add_month("mymonth",2);cfg.add_tzoffset("CST",hours=8)
    result=Pydt.strptime("2024 mymonth 29 12:30:00.123456789 CST","%Y %B %d %H:%M:%S.%f %Z",cfg=cfg)
    assert (result.month,result.day,result.microsecond)==(2,29,123456)
    assert result.utcoffset()==timedelta(hours=8)
    for year in (0,-1,10000):
        spelling=("-" if year<0 else "")+str(abs(year)).zfill(4)
        with pytest.raises(ValueError,match="out of range"):Pydt.strptime(spelling+"-01-01","%Y-%m-%d")
    with pytest.raises(ValueError):Pydt.strptime("00 AM","%I %p")


def test_numeric_formats_never_query_lc_time(monkeypatch):
    import rstimes._formatting as module
    def forbidden(*a,**kw):raise AssertionError("numeric format must not probe LC_TIME")
    monkeypatch.setattr(module._locale,"setlocale",forbidden)
    assert Pddt.strptime("2024-05-07","%Y-%m-%d",size=1).day.tolist()==[7]


@pytest.mark.parametrize("fmt",["%c","%x","%X"])
def test_system_composite_uses_real_templates_and_its_own_word_data(fmt):
    import locale
    from rstimes import Pydt
    value=datetime(2024,5,7,13,14,15)
    text=value.strftime(fmt)
    expected=datetime.strptime(text,fmt)
    cfg=Configs();cfg.set_month({});cfg.set_weekday({});cfg.set_ampm({})
    result=Pddt.strptime(text,fmt,size=1,cfg=cfg)[0]
    assert result.to_pydatetime()==expected
    assert Pydt.strptime(text,fmt,cfg=cfg)==expected
    with pytest.raises(ValueError):Pddt.strptime("May 2024","%b %Y",size=1,cfg=cfg)


def test_locale_change_does_not_reuse_stale_composite_templates():
    import locale
    from rstimes import Pydt
    original=locale.setlocale(locale.LC_TIME)
    checked=[]
    try:
        for name in ("C","en_US.UTF-8","fr_FR.UTF-8"):
            try:locale.setlocale(locale.LC_TIME,name)
            except locale.Error:continue
            value=datetime(2024,5,7,13,14,15)
            for fmt in ("%c","%x","%X"):
                text=value.strftime(fmt)
                expected=datetime.strptime(text,fmt)
                assert Pydt.strptime(text,fmt)==expected
                assert Pddt.strptime(text,fmt,size=1)[0].to_pydatetime()==expected
            checked.append(locale.setlocale(locale.LC_TIME))
    finally:locale.setlocale(locale.LC_TIME,original)
    assert "C" in checked
