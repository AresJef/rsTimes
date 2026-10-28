"""Independent expectations for the seven approved review2 repairs."""
from datetime import datetime, timedelta
import copy
import subprocess
import sys
import zoneinfo
import numpy as np
import pandas as pd
import pytest
from rstimes import Configs, Delta, Pydt, parse, parse_str, parse_to_epoch

@pytest.mark.parametrize('entry,call', [
 ('parse',lambda:parse(pd.NaT)),('Pydt.parse',lambda:Pydt.parse(pd.NaT)),
 ('Pydt.fromdate',lambda:Pydt.fromdate(pd.NaT)),('Pydt.fromdatetime',lambda:Pydt.fromdatetime(pd.NaT)),
 ('Pydt.combine',lambda:Pydt.combine(pd.NaT)),('Pydt.combine',lambda:Pydt.combine(pd.NaT,datetime.min.time())),
 ('parse_str',lambda:parse_str('12:30',default=pd.NaT)),('parse',lambda:parse('12:30',default=pd.NaT)),
 ('parse_to_epoch',lambda:parse_to_epoch('12:30',default=pd.NaT)),('parse_to_epoch',lambda:parse_to_epoch(pd.NaT))])
def test_g05_missing(entry,call):
 with pytest.raises(ValueError) as caught:call()
 assert entry in str(caught.value) and 'NaT' in str(caught.value)

@pytest.mark.parametrize('year',[10000,65537])
@pytest.mark.parametrize('unit',['s','ms','us'])
def test_g06_wide_timestamp(year,unit):
 start=pd.Timestamp(np.datetime64(f'{year}-05-07T12:30:45',unit));delta=Delta(days=1)
 assert parse(start,dtclass=pd.Timestamp) is start
 for actual in [start+delta,delta+start,delta.apply_many([start])[0]]:
  assert type(actual) is pd.Timestamp and actual==start.replace(day=8)
  assert (actual.year,actual.month,actual.day)==(year,5,8)
 assert start-delta==start.replace(day=6)
 assert delta.to_timedelta(start)==timedelta(days=1)
 for convert in [parse,Pydt.fromdatetime,Pydt.fromdate]:
  with pytest.raises((ValueError,OverflowError),match='range|year'):convert(start)
 calls=[]
 def build(**fields):calls.append(fields)
 assert parse(start,dtclass=build) is None and calls[-1]['year']==year

@pytest.mark.parametrize('days',[999999999,1000000000,2147483649,-1000000000])
@pytest.mark.parametrize('unit',['s','ms'])
def test_g06_wide_duration(days,unit):
 span=pd.Timedelta(np.timedelta64(days*86400*(1000 if unit=='ms' else 1),unit));delta=Delta(hours=1)
 assert (delta+span).days==days and (span+delta).days==days
 assert (delta-span).days==-days and (span-Delta()).days==days
 assert delta.apply_many([span])[0]==delta+span
 with pytest.raises(OverflowError):Pydt(2024,1,1)+span
 with pytest.raises(OverflowError):Pydt(2024,1,1)-span
 class Start(datetime):
  def __sub__(self,other):return span
 if abs(days)>999999999:
  with pytest.raises(OverflowError):delta.to_timedelta(Start(2024,1,1))
 else:assert delta.to_timedelta(Start(2024,1,1))==timedelta(days=days)

@pytest.mark.parametrize('year',[1970,1972,2024])
@pytest.mark.parametrize('nanos',[0,123])
def test_g06_carrier_controls(year,nanos):
 start=pd.Timestamp(f'{year}-05-07 12:30:45.123456{nanos:03d}')
 assert parse(start)==datetime(year,5,7,12,30,45,123456)
 assert Pydt.fromdatetime(start).year==year and Pydt.fromdate(start)==Pydt(year,5,7)
 moved=Delta(days=1,microseconds=1)+start
 assert (moved.year,moved.day,moved.microsecond,moved.nanosecond)==(year,8,123457,nanos)
 absolute=Delta(microsecond=2)+start
 assert (absolute.microsecond,absolute.nanosecond)==(2,0)
 assert parse_to_epoch(start,unit='ns')==start.value
 for days,seconds,micros in [(0,0,0),(0,0,1),(0,1,0),(1,2,3),(-1,86399,999999)]:
  builtin=timedelta(days=days,seconds=seconds,microseconds=micros);span=pd.Timedelta(builtin)
  assert Delta(hours=1)+span==Delta(hours=1)+builtin
  assert Pydt(2024,1,1)+span==Pydt(2024,1,1)+builtin

@pytest.mark.parametrize('nanos',[-2501,-2500,-2499,-1501,-1500,-1499,-501,-500,-499,499,500,501,1499,1500,1501,2499,2500,2501])
def test_g01_round_once(nanos):
 class Span(pd.Timedelta):pass
 class Start(datetime):
  def __sub__(self,other):return Span(nanoseconds=nanos)
 actual=Delta(hours=1).to_timedelta(Start(2024,1,1));q,r=divmod(nanos,1000)
 assert type(actual) is timedelta and actual==timedelta(microseconds=q+(r>500 or (r==500 and q%2!=0)))

def test_g01_cold_child_first():
 code='from datetime import datetime,timedelta\nimport pandas as pd\nfrom rstimes import Delta\nclass Span(pd.Timedelta):pass\nclass Start(datetime):\n def __sub__(self,other):return Span(nanoseconds=1500)\nassert Delta(hours=1).to_timedelta(Start(2024,1,1))==timedelta(microseconds=2)'
 result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
 assert result.returncode==0,result.stdout+result.stderr

def test_g02_snapshot_and_cycles():
 class Marker:
  slots=None
  def __deepcopy__(self,memo):
   self.slots=next(v for v in tuple(memo.values()) if type(v) is dict);return self
 class Child(Delta):
  __slots__=('first','second')
  def __setattr__(self,name,value):
   if name=='first' and value.slots is not None:value.slots.clear()
   object.__setattr__(self,name,value)
 original=Child(days=1);original.first=Marker();original.second=2
 cloned=copy.deepcopy(original)
 assert cloned.days==1 and cloned.second==2 and cloned.first is original.first
 # Reset the deliberately mutating callback before an ordinary shallow-copy control.
 original.first.slots=None
 shallow=copy.copy(original)
 assert shallow.first is original.first
 class Cycle(Delta):pass
 cyclic=Cycle(days=1);cyclic.cycle=cyclic
 assert copy.deepcopy(cyclic).cycle.cycle is not cyclic

def test_g02_error_propagation():
 class Child(Delta):
  __slots__=('label','__dict__')
  def __setattr__(self,name,value):
   if getattr(self,'fail',False):raise RuntimeError('user setter failed')
   object.__setattr__(self,name,value)
 original=Child(days=1);original.label='x';original.fail=True
 with pytest.raises(RuntimeError,match='user setter failed'):copy.deepcopy(original)

@pytest.mark.parametrize('fail',[False,True])
def test_g08_snapshot_and_commit(monkeypatch,fail):
 cfg=Configs();cfg.add_tzone('UTC');before=cfg.tzone;keys={'Asia/Shanghai','Europe/London'};expected=set(keys)
 original=zoneinfo.ZoneInfo;loaded=[]
 def loader(key):
  loaded.append(key);keys.clear()
  if fail and len(loaded)==2:raise RuntimeError('zone load failed')
  return original(key)
 monkeypatch.setattr(zoneinfo,'ZoneInfo',loader)
 if fail:
  with pytest.raises(RuntimeError,match='zone load failed'):cfg.set_tzone(keys)
  assert cfg.tzone==before
 else:
  cfg.set_tzone(keys);assert cfg.tzone==expected and set(loaded)==expected

def test_g08_validate_before_load(monkeypatch):
 def loader(key):pytest.fail('loader ran before complete validation')
 monkeypatch.setattr(zoneinfo,'ZoneInfo',loader)
 with pytest.raises(TypeError):Configs().set_tzone({'Asia/Shanghai',42})

@pytest.mark.parametrize('answer',[False,True,[],[1]])
def test_g04_custom_eq(answer):
 class Child(Delta):
  def __eq__(self,other):return answer
 child=Child(days=1);expected=not bool(answer)
 assert (child!=child) is expected and Child.__ne__(child,child) is expected and Delta.__ne__(child,child) is expected

def test_g04_protocols():
 class Unknown(Delta):
  def __eq__(self,other):return NotImplemented
 assert Delta.__ne__(Unknown(),object()) is NotImplemented
 class Explicit(Delta):
  def __eq__(self,other):return True
  def __ne__(self,other):return True
 value=Explicit();assert value!=value
 class Failure(Delta):
  def __eq__(self,other):raise RuntimeError('equality failed')
 with pytest.raises(RuntimeError,match='equality failed'):Failure()!=Failure()
 class TruthFailure:
  def __bool__(self):raise RuntimeError('truth failed')
 class Dynamic(Delta):
  def __eq__(self,other):return TruthFailure()
 with pytest.raises(RuntimeError,match='truth failed'):Dynamic()!=Dynamic()
 assert Delta.__eq__(Delta(days=1),timedelta(days=1)) is NotImplemented
 assert Delta.__ne__(Delta(days=1),timedelta(days=1)) is NotImplemented

@pytest.mark.parametrize('year,seconds',[(2024,1704067200),(10000,253402300800)])
def test_g07_inputs_and_defaults(year,seconds):
 inputs=[f'{year}-01-01',seconds,float(seconds),np.datetime64(f'{year}-01-01','s')]
 expected=dict(year=year,month=1,day=1,hour=0,minute=0,second=0,microsecond=0,tzinfo=None,fold=0)
 for value in inputs:
  calls=[]
  def build(**fields):calls.append(fields)
  assert parse(value,dtclass=build) is None and calls[-1]==expected
  assert parse_str('12:30',default=value,dtclass=build) is None and calls[-1]==dict(expected,hour=12,minute=30)
  assert parse_to_epoch('12:30',default=value,unit='s')==seconds+45000
  if year>=10000:
   with pytest.raises((ValueError,OverflowError)):parse(value)
 assert parse_str('2024-01-01',dtclass=lambda **fields:None) is None


def test_g07_native_values_beyond_i64_microseconds():
 year=1000000;seconds=31494784780800
 for value in [seconds,float(seconds),np.datetime64('1000000-01-01','s')]:
  calls=[]
  def build(**fields):calls.append(fields)
  assert parse(value,dtclass=build) is None and calls[-1]['year']==year
  assert parse_str('12:30',default=value,dtclass=build) is None and calls[-1]['year']==year
  assert parse_to_epoch('12:30',default=value,unit='s')==seconds+45000


def test_g06_timestamp_beyond_i64_microseconds():
 start=pd.Timestamp(np.datetime64('1000000-05-07','s'))
 result=Delta(days=1)+start
 assert (result.year,result.month,result.day)==(1000000,5,8)
 assert Delta(days=1).to_timedelta(start)==timedelta(days=1)


def test_g07_numeric_callback_runs_once():
 calls=[]
 class Number(int):
  def __float__(self):
   calls.append(1)
   raise OverflowError('user numeric conversion failed')
 with pytest.raises(OverflowError,match='user numeric conversion failed'):parse(Number(1))
 assert len(calls)==1


@pytest.mark.parametrize('text,year',[('0000-05-07',0),('-10000-05-07',-10000)])
def test_g06_wide_lower_years(text,year):
 start=pd.Timestamp(np.datetime64(text,'s'))
 actual=Delta(days=1)+start
 assert (actual.year,actual.month,actual.day)==(year,5,8)


def test_g04_descriptor_and_metaclass_semantics():
 class Static(Delta):
  __eq__=staticmethod(lambda other:True)
 static=Static();assert (static!=static) is False
 class Class(Delta):
  __eq__=classmethod(lambda cls,other:True)
 value=Class();assert (value!=value) is False
 calls=[]
 class Meta(type):
  def __getattribute__(cls,name):
   if name=='__eq__':
    calls.append(name)
    return lambda self,other:False
   return super().__getattribute__(name)
 class Actual(Delta,metaclass=Meta):
  def __eq__(self,other):return True
 actual=Actual();calls.clear()
 assert actual==actual and (actual!=actual) is False and calls==[]


def test_g05_child_factories_and_real_date_fields():
 calls=[]
 class Child(Pydt):
  def __new__(cls,*args,**kwargs):
   calls.append((args,kwargs))
   return super().__new__(cls,*args,**kwargs)
 for factory in [Child.parse,Child.fromdate,Child.fromdatetime,lambda date:Child.combine(date,datetime.min.time())]:
  with pytest.raises(ValueError,match='NaT'):factory(pd.NaT)
 calls.clear();Child.fromdate(pd.Timestamp('1970-05-07'))
 assert calls[-1][0]==(1970,5,7) and 'tzinfo' in calls[-1][1]
 calls.clear();Child.combine(pd.Timestamp('1972-05-07'),datetime.min.time())
 assert calls[-1][0]==(1972,5,7,0,0,0,0,None) and calls[-1][1]=={'fold':0}


def test_g05_cold_ordinary_subclass_does_not_import_pandas():
 code="""from datetime import datetime
import builtins,sys
from rstimes import parse,parse_to_epoch
class NaTType(datetime):pass
original=builtins.__import__
def reject(name,*args,**kwargs):
    if name=='pandas':raise AssertionError('ordinary date imported pandas')
    return original(name,*args,**kwargs)
builtins.__import__=reject
assert parse(NaTType(1,1,1))==datetime(1,1,1)
assert parse(NaTType(1970,1,1))==datetime(1970,1,1)
assert parse_to_epoch(NaTType(1,1,1),unit='s')==-62135596800
"""
 result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
 assert result.returncode==0,result.stdout+result.stderr


def test_g05_real_nat_subclass_is_missing():
 class Missing(type(pd.NaT)):pass
 missing=Missing()
 for convert in [parse,Pydt.parse,Pydt.fromdate,Pydt.fromdatetime,Pydt.combine,parse_to_epoch]:
  with pytest.raises(ValueError,match='NaT'):convert(missing)
 with pytest.raises(ValueError,match='NaT'):parse_str('12:30',default=missing)


@pytest.mark.parametrize('year,target',[(10000,1972),(65537,1970)])
def test_g06_real_year_precedes_identity_shortcut(year,target):
 value=pd.Timestamp(np.datetime64(f'{year}-05-07','s'));delta=Delta(year=target)
 for result in [delta+value,value+delta,delta.apply_many([value])[0]]:
  assert (result.year,result.month,result.day)==(target,5,7)


@pytest.mark.parametrize('shadow_parent',[False,True])
def test_g04_explicit_base_aliases_keep_value_semantics(shadow_parent):
 class Parent(Delta):
  def __eq__(self,other):return False
 base=Parent if shadow_parent else Delta
 class Alias(base):
  __eq__=Delta.__eq__
  __ne__=Delta.__ne__
  __hash__=Delta.__hash__
 value=Alias(days=1);other=Delta(days=1)
 assert value==other and not(value!=other)
 assert Delta.__ne__(value,other) is False
 assert hash(value)==hash(other)
