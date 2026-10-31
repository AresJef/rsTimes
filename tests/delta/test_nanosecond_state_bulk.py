"""GN08/GN10: complete ns values, new encodings and live Python protocols."""

import copy
from datetime import date, datetime, timedelta
import pickle
import struct

import numpy as np
import pytest

from rstimes import Delta
from rstimes._native import _restore_delta

FIELDS=("years","months","days","hours","minutes","seconds","microseconds","nanoseconds",
        "year","month","day","weekday","hour","minute","second","microsecond","nanosecond")
CORE=(2,3,-4,5,6,7,8,9,2024,2,29,0,10,11,12,123456,789)
MAGIC=b"rstDlt\0\x02"
PAYLOAD=MAGIC+struct.pack("<17q",*CORE)


def assert_core(value,expected=CORE):
    actual=tuple(-1 if getattr(value,name) is None else getattr(value,name) for name in FIELDS)
    assert actual==expected
    assert value.__getstate__()[2]==expected


def test_version_two_known_little_endian_vector_all_fields_and_getters():
    value=_restore_delta(Delta,PAYLOAD)
    assert len(PAYLOAD)==144
    assert_core(value)
    assert_core(Delta(PAYLOAD))
    assert value.__reduce_ex__(4)[1][1]==PAYLOAD
    assert value.__getstate__()==("rstimes.delta",2,CORE,None)
    for name in FIELDS:
        assert getattr(Delta,name).__get__(value,Delta)==getattr(value,name)
        with pytest.raises(TypeError):
            getattr(Delta,name).__get__(object(),Delta)
    for protocol in range(pickle.HIGHEST_PROTOCOL+1):
        result=pickle.loads(pickle.dumps(value,protocol=protocol))
        assert result is not value
        assert_core(result)


@pytest.mark.parametrize("payload", [
    b"rstDlt\0\x01"+bytes(128), bytes(136),
    b"rstDlt\0\x03"+PAYLOAD[8:], b"unknown!"+PAYLOAD[8:],
    PAYLOAD[:-1], PAYLOAD+b"\0",
])
def test_all_old_unknown_or_wrong_length_payloads_are_rejected(payload):
    with pytest.raises((ValueError,TypeError)):
        _restore_delta(Delta,payload)
    with pytest.raises((ValueError,TypeError)):
        Delta(payload)


@pytest.mark.parametrize("state", [
    ("rstimes.delta",1,tuple([0]*15),-1,None),
    ("rstimes.delta",1,CORE,None), ("rstimes.delta",3,CORE,None),
    ("rstimes.delta",2,CORE[:-1],None),
    ("rstimes.delta",2,list(CORE),None),
])
def test_old_default_states_and_noncanonical_encodings_never_migrate(state):
    value=_restore_delta(Delta,CORE)
    before=hash(value)
    with pytest.raises((ValueError,TypeError)):
        value.__setstate__(state)
    assert_core(value)
    assert hash(value)==before


@pytest.mark.parametrize("index",range(17),ids=FIELDS)
@pytest.mark.parametrize("kind",[lambda n:bool(n),lambda n:np.int64(n),lambda n:type("ChildInt",(int,),{})(n)],
                         ids=["bool","numpy-int","int-subclass"])
def test_external_core_requires_exact_builtin_integer_at_each_position(index,kind):
    core=list(CORE)
    core[index]=kind(core[index])
    with pytest.raises(TypeError):
        _restore_delta(Delta,tuple(core))


@pytest.mark.parametrize("index,invalid",[(1,12),(3,24),(4,60),(5,60),(6,1000000),(7,1000),
    (8,0),(9,0),(10,0),(11,7),(12,24),(13,60),(14,60),(15,1000000),(16,1000),(16,-2)])
def test_external_state_is_validated_without_clamping_or_normalizing(index,invalid):
    core=list(CORE); core[index]=invalid
    with pytest.raises(ValueError):
        _restore_delta(Delta,tuple(core))
    with pytest.raises(ValueError):
        Delta(MAGIC+struct.pack("<17q",*core))


class BusinessDelta(Delta):
    __slots__=("slot","unset","__dict__")
    creations=0

    def __new__(cls,token,**fields):
        return Delta.__new__(cls,**fields)

    def __init__(self,token,**fields):
        type(self).creations+=1
        self.token=token


@pytest.mark.parametrize("mode",["shallow","deep",*range(pickle.HIGHEST_PROTOCOL+1)])
def test_ns_default_business_state_keeps_slots_memo_and_bypasses_constructors(mode):
    value=BusinessDelta("account",nanoseconds=1500,nanosecond=0)
    value.payload=[]; value.alias=value.payload; value.slot=value.payload; value.self=value
    count=BusinessDelta.creations
    expected_hash=hash(value)
    repr(value)
    if mode=="shallow":
        result=copy.copy(value)
        assert result.payload is value.payload and result.self is value
    elif mode=="deep":
        result=copy.deepcopy(value)
        assert result.payload is not value.payload and result.self is result
    else:
        result=pickle.loads(pickle.dumps(value,mode))
        assert result.payload is not value.payload and result.self is result
    assert BusinessDelta.creations==count
    assert type(result) is BusinessDelta and result is not value
    assert result==value and hash(result)==expected_hash
    assert result.nanoseconds==500 and result.nanosecond==0
    assert result.token=="account" and result.alias is result.payload and result.slot is result.payload
    assert not hasattr(result,"unset")


def test_core_cannot_be_overwritten_even_after_hash_and_representation_are_cached():
    value=Delta(nanoseconds=1,nanosecond=0)
    original_hash=hash(value); original_repr=repr(value)
    state=list(value.__getstate__())
    fields=list(state[2]); fields[7]=2; state[2]=tuple(fields)
    with pytest.raises(ValueError):
        value.__setstate__(tuple(state))
    value.__init__(nanoseconds=99)
    assert value.nanoseconds==1 and value.nanosecond==0
    assert hash(value)==original_hash and repr(value)==original_repr


def test_mixed_ns_bulk_uses_the_same_independent_target_roles():
    delta=Delta(nanoseconds=-1)
    values=[date(2024,1,1),datetime(2024,1,1),timedelta(microseconds=1),
            np.datetime64("2024-01-01","D"),np.datetime64("2024-01-01T00:00:00.000001500","ns"),
            np.timedelta64(1500,"ns"),Delta(nanoseconds=2)]
    expected=[date(2023,12,31),datetime(2024,1,1),Delta(nanoseconds=999),
              date(2023,12,31),datetime(2024,1,1,microsecond=1),Delta(nanoseconds=1499),Delta(nanoseconds=1)]
    assert delta.apply_many(values)==expected
    assert delta.apply_many(iter(values))==expected


@pytest.mark.parametrize("mutation",["clear","replace","append"])
def test_ns_bulk_retains_current_reference_and_reads_live_length(mutation):
    items=[]
    class Callback:
        def __add__(self,value):
            assert value.nanoseconds==1
            if mutation=="clear": items.clear()
            elif mutation=="replace": items[0]=np.timedelta64(999,"ns")
            else: items.append(np.timedelta64(3,"ns"))
            return Delta(nanoseconds=2)
    items[:]=[Callback(),np.timedelta64(2,"ns")]
    expected=[Delta(nanoseconds=2)]
    if mutation!="clear": expected.append(Delta(nanoseconds=3))
    if mutation=="append": expected.append(Delta(nanoseconds=4))
    assert Delta(nanoseconds=1).apply_many(items)==expected

