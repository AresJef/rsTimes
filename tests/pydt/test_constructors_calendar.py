"""Public constructors and calendar facts under the approved Pydt contract."""
from datetime import datetime,date,time,timedelta,timezone
from zoneinfo import ZoneInfo
import numpy as np
import pytest
from rstimes import Pydt,Configs
from cytimes import Pydt as Official

@pytest.mark.parametrize('factory,args,expected',[
 ('fromordinal',(738886,),datetime(2024,1,1)),
 ('fromseconds',(-.000001,),datetime(1969,12,31,23,59,59,999999)),
 ('frommicroseconds',(-1,),datetime(1969,12,31,23,59,59,999999)),
 ('utcfromtimestamp',(0,),datetime(1970,1,1,tzinfo=timezone.utc)),
 ('fromisoformat',('2024-01-02T03:04:05.123456+00:00:30.5',),datetime(2024,1,2,3,4,5,123456,tzinfo=timezone(timedelta(seconds=30.5)))),
 ('fromisocalendar',(2020,53,7),datetime(2021,1,3)),
 ('fromdayofyear',(2024,999),datetime(2024,12,31)),
 ('fromdate',(date(2024,1,2),),datetime(2024,1,2)),
 ('fromdatetime',(datetime(2024,1,2,3),),datetime(2024,1,2,3)),
 ('strptime',('2024/01/02','%Y/%m/%d'),datetime(2024,1,2)),
 ('combine',(date(2024,1,2),time(3,4,5,fold=1)),datetime(2024,1,2,3,4,5,fold=1)),
 ('combine',('2024-01-02','03:04:05'),datetime(2024,1,2,3,4,5)),
])
def test_constructor_value_and_type(factory,args,expected):
 value=getattr(Pydt,factory)(*args)
 assert value==expected and type(value) is Pydt and value.fold==expected.fold

@pytest.mark.parametrize('unit',['Y','M','W','D','h','m','s','ms','us','ns'])
def test_numpy_units_share_parser_decoder(unit):
 value=np.datetime64('2024-05-07T15:30:01.123456789',unit)
 from rstimes import parse
 assert Pydt.fromdatetime64(value)==parse(value)
 assert type(Pydt.fromdatetime64(value)) is Pydt

@pytest.mark.parametrize('obj',['2024-05-07',date(2024,5,7),datetime(2024,5,7),1715040000,np.datetime64('2024-05-07')])
def test_parse_uses_current_native_entry(obj):
 from rstimes import parse
 assert Pydt.parse(obj)==parse(obj)
 assert type(Pydt.parse(obj)) is Pydt

def test_parse_new_rules_and_configs():
 assert Pydt.parse('2024-02-30')==datetime(2024,2,29)
 with pytest.raises(ValueError): Pydt.parse('2024-02-30',strict=True)
 cfg=Configs();cfg.add_month('mymonth',5)
 assert Pydt.parse('7 mymonth 2024',cfg=cfg)==datetime(2024,5,7)
 assert Pydt.parse('05-07-24',default=date(2026,1,1),yearfirst=False).year==2024

@pytest.mark.parametrize('method,args', [('fromisocalendar',(2024,0,0)),('fromdate',(object(),)),('fromdatetime',(date(2024,1,1),)),('fromdatetime64',(np.datetime64('NaT','us'),)),('frommicroseconds',(1<<100,))])
def test_constructor_rejects_invalid(method,args):
 with pytest.raises((ValueError,TypeError,OverflowError)): getattr(Pydt,method)(*args)

def test_standard_contract():
 p=Pydt(2024,1,31)
 assert p.weekday()==2
 assert p.isocalendar()==datetime.isocalendar(p)
 with pytest.raises(ValueError): p.replace(month=2)
 with pytest.raises(ValueError): Pydt(fold=2)
 assert Pydt.utcnow().tzinfo is timezone.utc
 assert Pydt.now(timezone.utc).tzinfo is timezone.utc

@pytest.mark.parametrize('ymd',[(1,1,1),(1900,3,1),(2000,2,29),(2024,5,7),(9999,12,31)])
def test_calendar_facts_match_official(ymd):
 p=Pydt(*ymd);o=Official(*ymd,fold=0)
 methods=['is_leap_year','is_long_year','days_in_year','days_bf_year','day_of_year','days_in_quarter','days_bf_quarter','day_of_quarter','days_in_month','days_bf_month','day_of_month','isoyear','isoweek','isoweekday','timedict','utctimedict']
 for method in methods:
  actual=getattr(p,method) if method in {"is_leap_year","days_in_month","day_of_year"} else getattr(p,method)()
  assert actual==getattr(o,method)(),method
 for name in ('year','month','day','hour','minute','second','microsecond','tzinfo','fold','quarter','millisecond','weekday'):
  assert (p.weekday() if name == 'weekday' else getattr(p, name)) == getattr(o, 'access_' + name)(), name
  assert not hasattr(Pydt, 'access_' + name)
 for year in (1900,2000,2024,9999): assert p.leap_bt_year(year)==o.leap_bt_year(year)

@pytest.mark.parametrize('zone',[None,timezone.utc,ZoneInfo('America/New_York'),timezone(timedelta(seconds=30,microseconds=500000))])
def test_exact_epoch_and_fold_outputs(zone):
 p=Pydt(2024,11,3,1,20,30,123456,tzinfo=zone,fold=1)
 assert p.time().fold==p.timetz().fold==1
 epoch=datetime(1970,1,1)
 naive=datetime.replace(p,tzinfo=None)
 difference=naive-epoch
 expected=(difference.days*86400+difference.seconds)*1000000+difference.microseconds
 assert p.tomicroseconds()==expected
 offset=p.utcoffset()
 if offset is not None: expected-=(offset.days*86400+offset.seconds)*1000000+offset.microseconds
 assert p.tomicroseconds(utc=True)==expected
 restored=datetime.fromisoformat(p.isoformat())
 assert restored.replace(tzinfo=None)==p.replace(tzinfo=None)
 assert restored.utcoffset()==p.utcoffset()

@pytest.mark.parametrize('locale',[None,'en_US','de_DE','fr_FR','tr_TR','zh_CN'])
def test_names_use_original_babel_context(locale):
 p=Pydt(2024,5,7);o=Official(2024,5,7,fold=0)
 assert p.month_name(locale)==o.month_name(locale)
 assert p.weekday_name(locale)==o.weekday_name(locale)

def test_remaining_constructor_and_predicate_types():
 p=Pydt(2024,5,7,12,30)
 assert Pydt.today().date()==date.today()
 assert Pydt.combine().date()==date.today() and Pydt.combine().hour==0
 assert Pydt.fromtimestamp(0,'UTC')==datetime(1970,1,1,tzinfo=timezone.utc)
 assert Pydt.fromseconds(0,'Asia/Shanghai').hour==0
 assert Pydt.fromtimestamp(0,'Asia/Shanghai').hour==8
 assert Pydt.fromdatetime64(np.datetime64('2024-05-07'),tz='UTC').tzinfo is timezone.utc
 assert type(p.is_leap_year) is type(p.is_long_year()) is bool
 for name,number in [('is_year',2024.9),('is_quarter',2.9),('is_day',7.9),('is_month',5.0),('is_weekday',1.0)]:
  with pytest.raises(TypeError): getattr(p,name)(number)
 assert p.is_month('May') and p.is_weekday('Tuesday')
 for name,word in [('is_month','mAy'),('is_weekday','tUe')]:
  with pytest.raises(ValueError): getattr(p,name)(word)
 assert p.astimezone().is_local()
 with pytest.raises(TypeError): p.__format__(None)
 assert p.toseconds()==Official(2024,5,7,12,30,fold=0).toseconds()
