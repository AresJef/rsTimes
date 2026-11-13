"""Arithmetic, saved immutable values, and normal Python subclass state."""
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
from copy import copy,deepcopy
import pickle
import numpy as np
from dateutil.relativedelta import relativedelta,MO
import pytest
from rstimes import Pydt,Delta
from cytimes import Pydt as Official

@pytest.mark.parametrize('amount',[{'years':1,'months':2,'days':3},{'months':-13,'hours':-25,'microseconds':-1},{'quarters':3,'weeks':2,'minutes':70},{'days':1.9},{'years':0}])
@pytest.mark.parametrize('method',['add','sub'])
def test_relative_arithmetic_equal_official(amount,method):
 p=Pydt(2024,1,31,15,30,1,123456);o=Official(2024,1,31,15,30,1,123456,fold=0)
 if any(isinstance(v,float) for v in amount.values()):
  with pytest.raises(TypeError):getattr(p,method)(**amount)
 else:
  assert getattr(p,method)(**amount)==getattr(o,method)(**amount)

@pytest.mark.parametrize('unit',['Y','Q','M','W','D','h','m','min','s','ms','us'])
@pytest.mark.parametrize('inclusive',['one','both','neither'])
@pytest.mark.parametrize('absolute',[False,True])
def test_boundary_difference_equal_official(unit,inclusive,absolute):
 p=Pydt(2024,5,7,12,30);o=Official(2024,5,7,12,30,fold=0)
 for other in (datetime(2024,5,7,12,30),datetime(2023,12,31,23,59,59,999999),datetime(2025,1,1)):
  assert p.diff(other,unit,absolute,inclusive)==o.diff(other,unit,absolute,inclusive)

@pytest.mark.parametrize('unit',['Y','M','W','D','h','m','s','ms','us','ns'])
def test_numpy_duration_and_date_adapters(unit):
 p=Pydt(2024,5,7,12);o=Official(2024,5,7,12,fold=0)
 for ticks in (-1,1):
  delta=np.timedelta64(ticks,unit)
  assert p+delta==o+delta
  assert p-delta==o-delta
  try: expected_reverse=delta+o
  except TypeError:
   with pytest.raises(TypeError): delta+p
  else: assert delta+p==expected_reverse
 value=np.datetime64('2024-05-07T12:00:00',unit)
 assert p-value==o-value


def test_operand_dispatch_and_safety():
 p=Pydt(2024,5,7,12)
 assert p-date(2024,5,7)==timedelta(hours=12)
 assert p-'2024-05-07 12:00'==timedelta(0)
 assert p+relativedelta(weekday=MO(2))==datetime(2024,5,20,12)
 assert p+relativedelta(years=1,leapdays=1)==datetime(2025,5,7,12)
 assert p+Delta(months=1)==datetime(2024,6,7,12)
 assert p.__sub__('not a date') is NotImplemented
 assert p.__add__(object()) is NotImplemented
 for missing in (np.datetime64('NaT','us'),np.timedelta64('NaT','us')):
  with pytest.raises(ValueError): p-missing
 with pytest.raises(OverflowError): p.add(years=2147483647)
 with pytest.raises(OverflowError): p.sub(days=-2147483648)
 with pytest.raises(OverflowError): Pydt(9999,12,31,23,59).ceil('D')

class Child(Pydt):
 __slots__=('tag',)
class Grandchild(Child):
 __slots__=('__private',)
 def set_private(self,value): self.__private=value
 def get_private(self): return self.__private

@pytest.mark.parametrize('protocol',[0,1,2,3,4,5])
@pytest.mark.parametrize('cls',[Pydt,Child,Grandchild])
def test_pickle_fields_metadata_and_cycles(protocol,cls):
 p=cls(2024,11,3,1,20,30,123456,tzinfo=ZoneInfo('America/New_York'),fold=1)
 p.payload=[1,2];p.me=p
 if isinstance(p,Child): p.tag={'slot':[3]}
 if isinstance(p,Grandchild): p.set_private('private')
 result=pickle.loads(pickle.dumps(p,protocol=protocol))
 assert type(result) is cls and result==p and result.fold==1
 assert result.me is result and result.payload==[1,2]
 if isinstance(p,Child): assert result.tag==p.tag
 if isinstance(p,Grandchild): assert result.get_private()=='private'

@pytest.mark.parametrize('cls',[Pydt,Child,Grandchild])
def test_copy_and_deepcopy(cls):
 p=cls(2024,5,7);p.payload=[];p.me=p
 if isinstance(p,Child): p.tag=[]
 if isinstance(p,Grandchild): p.set_private([3])
 shallow=copy(p);deep=deepcopy(p)
 assert type(shallow) is type(deep) is cls
 assert shallow is not p and deep is not p and shallow==deep==p
 assert shallow.payload is p.payload and shallow.me is p
 assert deep.payload is not p.payload and deep.me is deep
 if isinstance(p,Child):
  assert shallow.tag is p.tag and deep.tag is not p.tag
 if isinstance(p,Grandchild): assert deep.get_private()==[3] and deep.get_private() is not p.get_private()

class StateHook(Pydt):
 def __getstate__(self): return ('custom',self.payload,17)
 def __setstate__(self,state): self.payload=state[1];self.seen=state[0]

def test_custom_state_and_constructor_hooks():
 p=StateHook(2024,5,7);p.payload=[3]
 for result in (copy(p),deepcopy(p),pickle.loads(pickle.dumps(p))):
  assert result.payload==[3] and result.seen=='custom'
 class Customized(Pydt):
  def __new__(cls,*args,**kwargs):
   value=super().__new__(cls,*args,**kwargs);value.created=True;return value
 child=Customized(2024,1,31).to_month(1)
 assert type(child) is Customized and child.created


def test_new_state_rejects_wrong_version_and_does_not_change_value():
 from rstimes.pydt import _restore_pydt
 p=Pydt(2024,1,1)
 for version in (0,2,True):
  with pytest.raises(ValueError if type(version) is int else TypeError): _restore_pydt(Pydt,version,(2024,1,1,0,0,0,0),None,0)
 p.__setstate__({'label':'value'})
 assert p.label=='value' and p==datetime(2024,1,1)
 with pytest.raises((AttributeError,TypeError)): p.__setstate__((None,{'year':2000}))
 assert p.year==2024


class ReduceOnly(Pydt):
 def __reduce__(self):
  constructor,args,state=super().__reduce__()
  return constructor,args,{'hook':True}

class StateMapping(dict): pass
class MappingHook(Pydt):
 def __getstate__(self):
  state=StateMapping(value=17);state['me']=state;state.extra='extra'
  return state
 def __setstate__(self,state): self.saved=state

def test_explicit_reduce_and_state_container_hooks():
 for result in (copy(ReduceOnly(2024,1,1)),deepcopy(ReduceOnly(2024,1,1)),pickle.loads(pickle.dumps(ReduceOnly(2024,1,1)))):
  assert result.hook is True
 p=MappingHook(2024,1,1)
 for result in (copy(p),deepcopy(p),pickle.loads(pickle.dumps(p))):
  assert type(result.saved) is StateMapping
  assert result.saved['me'] is result.saved and result.saved.extra=='extra'
