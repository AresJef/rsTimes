"""UTC conversion, local convenience policy and dynamic timezone callbacks."""
from datetime import datetime,timedelta,timezone,tzinfo
from zoneinfo import ZoneInfo
import pytest
from rstimes import Pydt

@pytest.mark.parametrize('zone,utcfields', [('America/New_York',(2024,3,10,2,30)),('Europe/Berlin',(2024,3,31,2,30)),('Australia/Lord_Howe',(2024,10,5,15,45))])
def test_conversion_preserves_instant(zone,utcfields):
 p=Pydt(*utcfields,tzinfo=timezone.utc)
 result=p.tz_convert(zone)
 expected=datetime(*utcfields,tzinfo=timezone.utc).astimezone(ZoneInfo(zone))
 assert result==expected and result.fold==expected.fold and type(result) is Pydt
 assert result.timestamp()==p.timestamp()
 assert result.tz_convert(timezone.utc)==p

@pytest.mark.parametrize('zone,wall,expected',[
 ('America/New_York',(2024,3,10,2,30),(2024,3,10,3,30)),
 ('Europe/Berlin',(2024,3,31,2,30),(2024,3,31,3,30)),
 ('Australia/Lord_Howe',(2024,10,6,2,15),(2024,10,6,2,45)),
 ('Pacific/Apia',(2011,12,30,12,30),(2011,12,31,12,30)),
])
@pytest.mark.parametrize('fold',[0,1])
def test_localize_gap_follows_fold(zone,wall,expected,fold):
 value=Pydt(*wall,fold=fold)
 with pytest.raises(ValueError,match='exist'): value.tz_localize(zone)
 with pytest.raises(ValueError,match='exist'): Pydt(*wall,tzinfo=ZoneInfo(zone),fold=fold)

def test_convenience_and_duration_arithmetic_share_gap_policy():
 zone=ZoneInfo('America/New_York');p=Pydt(2024,3,9,2,30,tzinfo=zone)
 assert p.to_day(1).hour==p.add(days=1).hour==3
 assert (p+timedelta(days=1)).hour==3
 assert p.to_date(day=10).hour==3
 existing=Pydt(2024,3,10,3,30,1,123456,tzinfo=zone)
 assert existing.to_day(0) is existing
 assert existing.fsp(6) is existing
 trimmed=existing.fsp(3)
 assert (trimmed.hour,trimmed.minute,trimmed.microsecond,trimmed.fold)==(3,30,123000,0)

@pytest.mark.parametrize('fold',[0,1])
def test_repeat_and_round_keep_fold(fold):
 p=Pydt(2024,11,3,1,20,30,123456,tzinfo=ZoneInfo('America/New_York'),fold=fold)
 for result in (p.fsp(3),p.floor('m'),p.ceil('m'),p.round('m'),p.to_time(second=15)):
  assert result.fold==fold
 assert p.time().fold==p.timetz().fold==fold
 a=p.replace(fold=0);b=p.replace(fold=1)
 assert a==b and hash(a)==hash(b) and a-b==timedelta(0)
 assert datetime.__sub__(a,b)==a-b

def test_none_timezone_semantics():
 p=Pydt(2024,5,7,12,tzinfo='Asia/Shanghai')
 assert p.tz_localize(None)==datetime(2024,5,7,12)
 assert p.tz_convert(None)==datetime(2024,5,7,4)
 assert p.tz_switch(None)==datetime(2024,5,7,12)
 assert p.tz_switch('UTC',naive=True)==datetime(2024,5,7,4)
 n=Pydt(2024,5,7,12)
 assert n.tz_switch('UTC',base_tz='Asia/Shanghai')==datetime(2024,5,7,4,tzinfo=timezone.utc)
 with pytest.raises(ValueError): n.tz_convert('UTC')
 with pytest.raises(ValueError): n.tz_switch('UTC')
 with pytest.raises(ValueError): p.tz_localize('UTC')

class WrappedZone(tzinfo):
 """A full custom protocol, deliberately not identified through its fake key."""
 key='Europe/Berlin'
 def __init__(self): self.inner=ZoneInfo('America/New_York');self.roundtrips=0
 def utcoffset(self,dt): return self.inner.utcoffset(dt.replace(tzinfo=self.inner))
 def dst(self,dt): return self.inner.dst(dt.replace(tzinfo=self.inner))
 def tzname(self,dt): return self.inner.tzname(dt.replace(tzinfo=self.inner))
 def fromutc(self,dt):
  self.roundtrips+=1
  return self.inner.fromutc(dt.replace(tzinfo=self.inner)).replace(tzinfo=self)

@pytest.mark.parametrize('fold',[0,1])
def test_custom_timezone_gap_uses_fromutc(fold):
 zone=WrappedZone();p=Pydt(2024,3,10,2,30,fold=fold)
 with pytest.raises(ValueError,match='exist'): p.tz_localize(zone)

class NoneOffset(tzinfo):
 def utcoffset(self,dt): return None
 def dst(self,dt): return None


def test_effectively_naive_and_bad_callbacks():
 z=NoneOffset();p=Pydt(2024,1,1,tzinfo=z)
 assert p.tomicroseconds(True)==p.tomicroseconds(False)
 assert p.diff(datetime(2024,1,1),'s')==0
 with pytest.raises(ValueError): p.tz_convert('UTC')
 class Broken(tzinfo):
  def utcoffset(self,dt): raise RuntimeError('callback failure')
 b=Pydt(2024,1,1,tzinfo=Broken())
 with pytest.raises(RuntimeError,match='callback failure'): b.to_day(1)
 class BadFromUTC(tzinfo):
  def utcoffset(self,dt): return timedelta(hours=1)
  def fromutc(self,dt): return 'not a date'
 with pytest.raises(TypeError): Pydt(2024,1,1,tzinfo=BadFromUTC()).to_day(1)
 class Overridden(Pydt):
  def utcoffset(self): return timedelta(days=999999999)
 assert Overridden(2024,1,1).tomicroseconds(True)==Pydt(2024,1,1).tomicroseconds()

@pytest.mark.parametrize('alias',['UTC','utc','GMT','z','Etc/UTC','Zulu','Universal','Local'])
def test_named_timezone_aliases(alias):
 value=Pydt(2024,1,1,tzinfo=alias)
 assert value.tzinfo is not None
 if alias.lower()!='local': assert value.is_utc()
 with pytest.raises(ValueError): Pydt(tzinfo='Definitely/Unknown')
