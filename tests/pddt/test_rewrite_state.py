import copy
import pickle
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt

_BUILDS=[]
class Business(Pddt):
    __slots__=('slot','me')
    def __new__(cls,data,*,required=None,**kwargs):
        if required!='ok':raise RuntimeError('business constructor needs explicit credentials')
        _BUILDS.append('new')
        return super().__new__(cls,data,**kwargs)
    def __init__(self,data,*,required=None,**kwargs):
        _BUILDS.append('init')

class CustomState(Pddt):
    def __getstate__(self):return {'chosen':self.info}
    def __setstate__(self,state):self.accepted=state


def chosen_result():return Pddt(['2001-01-01'])
class CustomReduce(Pddt):
    def __reduce__(self):return chosen_result,()

class CustomReduceEx(Pddt):
    def __reduce_ex__(self,protocol):return chosen_result,()


def example():
    x=Business(['2024-01-01 00:00:00.000000001',None],required='ok',tz='UTC',name='dates')
    x.info=[];x.left=x.info;x.right=x.info;x._business='keep';x.slot=x.info;x.me=x
    x._cache['not_business']=lambda:None
    return x


def check_date(result,source):
    assert type(result) is Business and result is not source
    assert result.asi8.tolist()==source.asi8.tolist()
    assert result.unit=='ns' and result.tz is source.tz and result.name==source.name
    assert result._business=='keep'


def test_shallow_copies_preserve_references_slots_and_safe_date_storage():
    x=example();_BUILDS.clear()
    for y in [copy.copy(x),x.copy(),x.copy(deep=False)]:
        check_date(y,x)
        assert y.info is x.info and y.slot is x.info and y.me is x
        assert np.shares_memory(x.asi8,y.asi8)
    assert _BUILDS==[]


def test_deepcopy_one_memo_keeps_aliases_cycles_and_independent_buffer():
    x=example();_BUILDS.clear()
    for y in [copy.deepcopy(x),x.copy(deep=True)]:
        check_date(y,x)
        assert y.info is not x.info and y.left is y.right is y.slot is y.info
        assert y.me is y and not np.shares_memory(x.asi8,y.asi8)
    outer=copy.deepcopy([x,x.info]);assert outer[0].info is outer[1]
    assert _BUILDS==[]


@pytest.mark.parametrize('protocol',range(pickle.HIGHEST_PROTOCOL+1))
def test_pickle_versioned_core_and_business_state_keep_aliases_and_cycles(protocol):
    x=example();_BUILDS.clear()
    y=pickle.loads(pickle.dumps(x,protocol=protocol))
    check_date(y,x)
    assert y.info is not x.info and y.left is y.right is y.slot is y.info
    assert y.me is y and _BUILDS==[]
    assert 'not_business' not in y._cache


def test_explicit_state_hooks_are_not_replaced_by_default_metadata():
    x=CustomState(['2024-01-01']);x.info=[];x.unselected='must not leak'
    for y in [copy.copy(x),copy.deepcopy(x),pickle.loads(pickle.dumps(x))]:
        assert y.accepted=={'chosen':[]}
        assert not hasattr(y,'unselected') and not hasattr(y,'info')
    assert copy.copy(x).accepted['chosen'] is x.info
    assert copy.deepcopy(x).accepted['chosen'] is not x.info


@pytest.mark.parametrize('cls',[CustomReduce,CustomReduceEx])
def test_actual_reduction_override_is_honored_in_copy_and_pickle(cls):
    x=cls(['2024-01-01'])
    for y in [copy.copy(x),copy.deepcopy(x),pickle.loads(pickle.dumps(x))]:
        assert type(y) is Pddt and y.year.tolist()==[2001]


def test_copy_hook_original_exceptions_and_business_state_failures_are_retained():
    error=RuntimeError('original state failure')
    class Broken(Pddt):
        def __getstate__(self):raise error
    x=Broken(['2024-01-01'])
    for action in [lambda:copy.copy(x),lambda:copy.deepcopy(x),lambda:pickle.dumps(x)]:
        with pytest.raises(RuntimeError) as caught:action()
        assert caught.value is error
    class Hooks(Pddt):
        def __copy__(self):return 'selected shallow'
        def __deepcopy__(self,memo):return 'selected deep'
    x=Hooks(['2024-01-01'])
    assert copy.copy(x)=='selected shallow' and copy.deepcopy(x)=='selected deep'
    assert x.copy()=='selected shallow' and x.copy(deep=True)=='selected deep'


def test_name_frequency_and_default_state_shapes():
    x=Pddt(['2024-01-01','2024-01-02'],freq='D',name='before')
    assert x.__getstate__() is None
    y=x.copy(name='after',deep=True)
    assert y.name=='after' and x.name=='before' and y.freq==x.freq
    assert y.unit==x.unit
    with pytest.raises(TypeError):x.copy(deep=1)
    assert Pddt([]).copy().empty


def test_restore_rejects_bad_version_core_and_internal_state_overwrites():
    from rstimes.pddt import _restore_pddt
    args=[Pddt,'rstimes.pddt',1,bytes(8),'us',None,None,None]
    for index,value,kind in [(1,'legacy',ValueError),(2,True,TypeError),(2,0,ValueError),(3,bytearray(8),TypeError),(3,b'bad',ValueError),(4,'D',ValueError),(0,object,TypeError)]:
        bad=args.copy();bad[index]=value
        with pytest.raises(kind):_restore_pddt(*bad)
    x=Pddt(['2024-01-01']);before=x.asi8.copy()
    for state in [{'_data':'bad'},(None,{'_name':'bad'})]:
        with pytest.raises(ValueError):x.__setstate__(state)
    assert np.array_equal(x.asi8,before)


def test_live_copy_hook_and_reduce_changes_are_not_frozen_in_a_cache():
    class Child(Pddt):pass
    x=Child(["2024-01-01"])
    assert isinstance(copy.copy(x),Child)
    Child.__copy__=lambda self:"new hook"
    assert copy.copy(x)=="new hook" and x.copy()=="new hook"
    del Child.__copy__
    Child.__reduce__=lambda self:(chosen_result,())
    assert copy.copy(x).year.tolist()==[2001]
    del Child.__reduce__
    assert type(copy.copy(x)) is Child
