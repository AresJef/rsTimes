"""V08 keeps fixed-zone integer parsing independent of datetime capacity."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pickle
import pytest
from rstimes import Configs, parse_to_epoch, parse_str


def unix_days(year,month,day):
    y=year-1
    starts=[0,31,59,90,120,151,181,212,243,273,304,334]
    leap=year%4==0 and (year%100!=0 or year%400==0)
    return y*365+y//4-y//100+y//400+starts[month-1]+(1 if month>2 and leap else 0)+day-1-719162


@pytest.mark.parametrize('zone,offset',[('UTC',0),('Etc/GMT-8',28800),('Etc/GMT+5',-18000)])
@pytest.mark.parametrize('year',[1,2024,10000,25000])
@pytest.mark.parametrize('restore',[False,True])
def test_registered_fixed_rule_uses_native_ticks(zone,offset,year,restore):
    cfg=Configs();cfg.add_tzone(zone)
    if restore:cfg=pickle.loads(pickle.dumps(cfg))
    text=f'{year:04}-01-02 12:30:01.123456789 {zone}'
    expected=(unix_days(year,1,2)*86400+12*3600+30*60+1-offset)*10**9+123456789
    assert parse_to_epoch(text,unit='ns',cfg=cfg,ignoretz=False)==expected


@pytest.mark.parametrize('fold',[0,1])
def test_dynamic_region_keeps_its_date_and_fold_semantics(fold):
    cfg=Configs();cfg.add_tzone('America/New_York')
    default=datetime(2024,1,1,fold=fold)
    result=parse_to_epoch('2024-11-03 01:30 America/New_York',cfg=cfg,default=default,ignoretz=False)
    dt=datetime(2024,11,3,1,30,tzinfo=ZoneInfo('America/New_York'),fold=fold)
    diff=dt-datetime(1970,1,1,tzinfo=timezone.utc)
    assert result==(diff.days*86400+diff.seconds)*10**6


def test_string_output_still_uses_the_requested_zone_class():
    cfg=Configs();cfg.add_tzone('Etc/GMT-8')
    value=parse_str('2024-01-02 12:00 Etc/GMT-8',cfg=cfg,ignoretz=False)
    assert type(value.tzinfo) is ZoneInfo and value.tzinfo.key=='Etc/GMT-8'
