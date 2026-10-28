"""P10: explicit localization consumes actual candidates, not DST labels."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt, Pydt, Configs, parse_str


@pytest.mark.parametrize("key,text", [("America/New_York","2024-11-03 01:30"),
    ("Europe/Warsaw","1915-08-04 23:50"),("Europe/Kyiv","1990-07-01 01:30"),
    ("Europe/Dublin","2024-10-27 01:30")])
@pytest.mark.parametrize("choice", [True,False,np.bool_(True),np.bool_(False)])
def test_boolean_selects_the_actual_pandas_candidate(key,text,choice):
    expected=pd.Timestamp(text).tz_localize(ZoneInfo(key),ambiguous=bool(choice)).as_unit("us")
    result=Pddt([text],tz=key,ambiguous=choice)
    assert result.unit=="us" and result.asi8.tolist()==[int(expected.asm8.view("i8"))]
    assert result[0].fold==expected.fold


@pytest.mark.parametrize("strict", [False,True])
def test_default_raise_and_explicit_nat_are_distinct_from_strict(strict):
    with pytest.raises(ValueError,match="occurs twice"):
        Pddt(["2024-11-03 01:30"],tz="America/New_York",strict=strict)
    assert Pddt(["2024-11-03 01:30"],tz="America/New_York",strict=strict,ambiguous="NaT").isna().tolist()==[True]
    with pytest.raises(ValueError,match="does not exist"):
        Pddt(["2024-03-10 02:30"],tz="America/New_York",strict=strict)


@pytest.mark.parametrize("unit", ["s","ms","us","ns"])
@pytest.mark.parametrize("policy", ["shift_forward","shift_backward",timedelta(hours=1),timedelta(hours=-1),"NaT"])
def test_gap_adjustment_has_correct_boundary_and_current_precision(unit,policy):
    text="2024-03-10 02:30"
    result=Pddt([text],unit=unit,tz="America/New_York",nonexistent=policy)
    if policy=="NaT":
        assert result.isna().tolist()==[True]
        return
    scale={"s":10**9,"ms":10**6,"us":1000,"ns":1}[unit]
    if policy=="shift_backward":
        expected=int(pd.Timestamp("2024-03-10 07:00Z").as_unit(unit).asm8.view("i8"))-1
    elif policy=="shift_forward":
        expected=int(pd.Timestamp("2024-03-10 07:00Z").as_unit(unit).asm8.view("i8"))
    else:
        local=datetime.fromisoformat(text)+policy
        expected=int(pd.Timestamp(local).tz_localize(ZoneInfo("America/New_York")).as_unit(unit).asm8.view("i8"))
    assert result.unit==unit and result.asi8.tolist()==[expected]


def test_non_hour_and_whole_day_gaps_use_real_boundaries():
    # Independent rule: the first/last actually valid boundary. pandas3 currently
    # shifts Lord Howe 02:15 to03:00, which is later than the confirmed02:30 edge.
    cases=[("Australia/Lord_Howe","2024-10-06 02:15",
            "2024-10-06 02:30","2024-10-06 01:59:59.999999"),
           ("Pacific/Apia","2011-12-30 12:30",
            "2011-12-31 00:00","2011-12-29 23:59:59.999999")]
    for key,text,forward,backward in cases:
        for policy,target in (("shift_forward",forward),("shift_backward",backward)):
            expected=pd.Timestamp(target).tz_localize(ZoneInfo(key)).as_unit("us")
            result=Pddt([text],tz=key,nonexistent=policy,unit="us")
            assert result.asi8.tolist()==[int(expected.asm8.view("i8"))]


def test_a_timedelta_that_still_lands_in_the_gap_is_rejected():
    with pytest.raises(ValueError,match="still lands"):
        Pddt(["2024-03-10 02:30"],tz="America/New_York",nonexistent=timedelta(minutes=1))


def test_mask_uses_full_original_positions_not_labels_or_ambiguous_subset():
    values=[None,"2024-11-03 01:30","2024-11-03 02:30","2024-11-03 01:30"]
    mask=pd.Series([True,False,True,True],index=[9,7,3,1],dtype="boolean")
    result=Pddt(values,tz="America/New_York",ambiguous=mask)
    assert result.isna().tolist()==[True,False,False,False]
    assert result[1].fold==1 and result[3].fold==0
    with pytest.raises(ValueError,match="mask length"):
        Pddt(values,tz="America/New_York",ambiguous=[False,True])
    with pytest.raises(ValueError,match="mask length"):
        Pddt([],ambiguous=[True])
    assert Pddt([],ambiguous=[]).empty


@pytest.mark.parametrize("bad,error", [(1,TypeError),(0,TypeError),(None,TypeError),
    ("unknown",ValueError),([1],TypeError),(np.array([[True]]),ValueError)])
def test_bad_ambiguous_policy_rejected_even_on_empty_or_native_inputs(bad,error):
    for data in ([],np.array([],dtype="datetime64[us]")):
        with pytest.raises(error):Pddt(data,ambiguous=bad)


@pytest.mark.parametrize("bad,error", [(True,TypeError),(None,TypeError),(0,TypeError),
    (["NaT"],TypeError),(np.timedelta64(1,"h"),TypeError),("unknown",ValueError)])
def test_bad_nonexistent_policy_rejected_even_for_empty_data(bad,error):
    with pytest.raises(error):Pddt([],nonexistent=bad)


def test_rust_infer_matches_frozen_pandas3_order_cases():
    fixture=Path(__file__).with_name("data")/"pandas3-infer-meaning.json"
    for case in json.loads(fixture.read_text(encoding='utf-8')):
        if "error" in case:
            with pytest.raises(ValueError):
                Pddt(case["values"],tz="America/New_York",ambiguous="infer")
        else:
            result=Pddt(case["values"],tz="America/New_York",ambiguous="infer")
            assert result.asi8.tolist()==case["ticks"]


def test_region_text_is_interpreted_at_its_registered_source_before_target_conversion():
    cfg=Configs();cfg.add_tzone("America/New_York")
    text="2024-11-03 01:30:00.123456789 America/New_York"
    result=Pddt([text],cfg=cfg,tz="UTC",ambiguous=False)
    expected=pd.Timestamp("2024-11-03 06:30:00.123456789Z")
    assert result.unit=="ns" and result.asi8.tolist()==[int(expected.asm8.view("i8"))]
    with pytest.raises(ValueError,match="register"):
        Pddt([text],tz="UTC",ambiguous=False)


def test_array_strategies_ignore_default_fold_and_parser_does_not_validate_existence():
    cfg=Configs();cfg.add_tzone("America/New_York")
    text="2024-11-03 01:30 America/New_York"
    default=datetime(2024,1,1,fold=1)
    assert Pddt([text],cfg=cfg,default=default,ambiguous=True)[0].fold==0
    gap="2024-03-10 02:30 America/New_York"
    assert parse_str(gap,cfg=cfg,ignoretz=False).hour==2
    with pytest.raises(ValueError):Pydt.parse(gap,cfg=cfg,ignoretz=False)
    assert Pddt([gap],cfg=cfg,nonexistent="shift_forward")[0].hour==3


def test_known_instants_and_native_timezone_columns_do_not_need_new_fold_selection():
    first=datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=0)
    second=first.replace(fold=1)
    result=Pddt([first,second])
    assert result[0].fold==0 and result[1].fold==1
    native=pd.DatetimeIndex([first,second]).as_unit("us")
    result=Pddt(native,tz="UTC")
    assert result.asi8.tolist()==native.asi8.tolist()
    assert result.hour.tolist()==[5,6]


def test_ns_tail_and_source_values_are_not_changed_by_localization():
    values=np.array(["2024-11-03T01:30:00.123456789"],dtype="datetime64[ns]")
    before=values.copy()
    result=Pddt(values,tz="America/New_York",ambiguous=False)
    assert result.asi8[0]%1000==789 and np.array_equal(values,before)


def test_timezone_methods_preserve_instants_or_local_clocks_as_named():
    base=Pddt(["2024-05-07 12:30:00.123456789",None],name="events")
    source=base.tz_localize("Asia/Shanghai")
    assert source.tzinfo.key=="Asia/Shanghai" and source.name=="events"
    assert source.tz_convert("UTC").hour.tolist()[0]==4
    assert source.tz_localize(None).asi8.tolist()==base.asi8.tolist()
    utc_naive=source.tz_convert(None)
    assert utc_naive.tzinfo is None and utc_naive.asi8.tolist()==source.asi8.tolist()
    assert source.tz_switch(None).asi8.tolist()==base.asi8.tolist()
    switched=base.tz_switch("UTC",base_tz="Asia/Shanghai",naive=True)
    assert switched.tzinfo is None and switched.asi8.tolist()==source.asi8.tolist()
    assert source.as_unit("us").unit=="us" and source.as_unit("us").tzinfo is source.tzinfo
    with pytest.raises(TypeError):base.tz_convert("UTC")
    with pytest.raises(TypeError):source.tz_localize("UTC")
    with pytest.raises(ValueError,match="base_tz"):base.tz_switch("UTC")


def test_astimezone_naive_source_uses_local_and_keeps_target_clock_on_strip(monkeypatch):
    import rstimes.pddt as module
    local=ZoneInfo("Asia/Shanghai")
    calls=[]
    def local_zone():calls.append(1);return local
    monkeypatch.setattr(module,"_local_timezone",local_zone)
    source=Pddt(["1970-01-01 08:00"])
    result=source.astimezone("UTC")
    assert result.asi8.tolist()==[0] and result.is_utc()
    assert calls==[1]
    aware=Pddt([0],unit="s",tz="UTC")
    assert aware.astimezone("Asia/Shanghai").hour.tolist()==[8]
    assert calls==[1]
    assert aware.tz_switch("Asia/Shanghai",naive=True).hour.tolist()==[8]


def test_batch_does_not_construct_pydt_intermediates_and_accepts_empty_zone(monkeypatch):
    import rstimes.pddt as module
    def forbidden(*args,**kwargs):raise AssertionError("Pydt construction is not a batch intermediate")
    monkeypatch.setattr(Pydt,"__new__",forbidden)
    for zone in (None,timezone.utc,timezone(timedelta(hours=8)),ZoneInfo("UTC")):
        result=Pddt(["2024-05-07 12:30"],tz=zone)
        if zone is not None:
            assert result.tz_localize(None).hour.tolist()==[12]
    assert Pddt([],tz="America/New_York").empty


def test_new_subclass_dates_receive_one_normal_whole_column_construction():
    events=[]
    class Child(Pddt):
        def __new__(cls,*args,**kwargs):
            events.append("new")
            return super().__new__(cls,*args,**kwargs)
        def __init__(self,*args,**kwargs):
            events.append("init")
            self.tag="business"
    source=Child(["2024-11-03 01:30"],name="events")
    events.clear()
    result=source.tz_localize("America/New_York",ambiguous=False)
    assert type(result) is Child and result.tag=="business" and result[0].fold==1
    assert events==["new","init"] and result.name=="events"


def test_unit_cannot_silently_change_during_zone_removal():
    # A fractional fixed offset can add finer clock fields without changing
    # the stored UTC instant; removing the zone must not silently lose them.
    source=Pddt([0],unit="s",tz=timezone(timedelta(microseconds=1)))
    with pytest.raises(ValueError):source.tz_localize(None)
    result=source.as_unit("us").tz_localize(None)
    assert result.asi8.tolist()==[1]
def test_genuine_pytz_source_is_normalized_once_without_changing_instant():
    import pytest
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import pandas as pd
    from rstimes import Pddt
    pytz=pytest.importorskip("pytz")
    value=pytz.timezone("America/New_York").localize(datetime(2024,5,7,12,30))
    expected=pd.Timestamp(value).as_unit("us").asm8.view("i8")
    for result in (Pddt([value]),Pddt.fromdatetime(value,size=1)):
        assert type(result.tzinfo)is ZoneInfo and result.tzinfo.key=="America/New_York"
        assert result.asi8.tolist()==[expected] and result.hour.tolist()==[12]
    bad=datetime(2024,5,7,tzinfo=pytz.FixedOffset(60))
    with pytest.raises(ValueError):Pddt([bad])



def test_pytz_seasonal_instances_share_a_region_and_validate_even_with_target():
    pytz = pytest.importorskip("pytz")
    from datetime import datetime
    zone = pytz.timezone("America/New_York")
    sources = [zone.localize(datetime(2024, 1, 1)), zone.localize(datetime(2024, 7, 1))]
    result = Pddt(sources)
    assert result.tz.key == "America/New_York"
    assert result.asi8.tolist() == [int(x.timestamp()) * 1_000_000 for x in sources]
    with pytest.raises(ValueError, match="pytz"):
        Pddt([datetime(2024, 1, 1, tzinfo=pytz.FixedOffset(60))], tz="UTC")
