"""Independent exact-value and target-projection contracts for the ns upgrade."""

from datetime import date, datetime, timedelta
from fractions import Fraction
import ast
import pickle

import numpy as np
import pytest

from rstimes import Delta, Pydt

NS_DAY = 86_400_000_000_000


def assert_fixed(value, expected):
    """Compare all canonical fixed fields to independent integer division."""
    days, clock = divmod(expected, NS_DAY)
    assert (value.days, value.hours, value.minutes, value.seconds,
            value.microseconds, value.nanoseconds) == (
        days, clock // 3_600_000_000_000, clock // 60_000_000_000 % 60,
        clock // 1_000_000_000 % 60, clock // 1000 % 1_000_000, clock % 1000,
    )


@pytest.mark.parametrize("amount", [0, 1, -1, 499, -499, 500, -500, 501, -501,
    999, -999, 1000, -1000, 1001, -1001, 1500, -1500, 2**53+1])
def test_value_exact_integer_nanoseconds(amount):
    assert_fixed(Delta(nanoseconds=amount), amount)


@pytest.mark.parametrize("arguments", [
    {"nanoseconds": 0.5}, {"nanoseconds": 1.5}, {"nanoseconds": -1.5},
    {"seconds": 1e-9}, {"microseconds": 0.001},
    {"microseconds": 1, "nanoseconds": -1000},
    {"microseconds": 0.0005, "nanoseconds": 0.5},
    {"seconds": 0.1, "microseconds": -100000.0, "nanoseconds": 0.75},
    {"weeks": 0.5, "days": -3.5, "nanoseconds": 1},
    {"nanoseconds": np.float32(0.6), "microseconds": np.float16(0.1)},
])
def test_preparation_float_rounds_complete_binary_sum_once(arguments):
    coefficients = {"weeks":604800000000000,"days":NS_DAY,"hours":3600000000000,
        "minutes":60000000000,"seconds":1000000000,"milliseconds":1000000,
        "microseconds":1000,"nanoseconds":1}
    total = sum((Fraction.from_float(float(number)) if isinstance(number,(float,np.floating))
                 else Fraction(number)) * coefficients[name]
                for name,number in arguments.items())
    assert_fixed(Delta(**arguments), round(total))


def test_value_independent_absolute_field_merge_and_zero_presence():
    tail = Delta(nanosecond=2)
    micros = Delta(microsecond=1)
    for result in (tail+micros, micros+tail):
        assert result.microsecond == 1
        assert result.nanosecond == 2
    assert (Delta(nanosecond=0)+tail).nanosecond == 2
    assert (Delta(nanosecond=0)-tail).nanosecond == 0
    assert micros.nanosecond is None
    assert bool(Delta(nanosecond=0))
    assert not bool(Delta(nanoseconds=0))
    assert "nanosecond=0" in repr(Delta(nanosecond=0))


def test_value_equal_units_have_equal_hashes_and_dictionary_keys():
    left, right = Delta(nanoseconds=1000), Delta(microseconds=1)
    assert left == right
    assert hash(left) == hash(right)
    assert {left:"value"}[right] == "value"
    assert Delta(nanoseconds=1) != Delta()


def test_value_negation_recovers_after_day_borrow():
    value = Delta(days=-(2**63), nanoseconds=1)
    opposite = -value
    assert opposite.days == 2**63-1
    assert opposite.nanoseconds == 999
    assert abs(value) == opposite
    with pytest.raises(OverflowError):
        -Delta(days=-(2**63))


@pytest.mark.parametrize("value", [True,False,np.bool_(True),1.0,"1",None])
def test_preparation_absolute_ns_rejects_wrong_numeric_role(value):
    if value is None:
        assert Delta(nanosecond=value).nanosecond is None
    else:
        with pytest.raises(TypeError):
            Delta(nanosecond=value)


@pytest.mark.parametrize("value", [-1,1000])
def test_preparation_absolute_ns_has_its_own_range(value):
    with pytest.raises(ValueError):
        Delta(nanosecond=value)


def test_preparation_preserves_nineteen_positions_and_adds_only_keywords():
    # The extension publishes its constructor signature directly. CPython's
    # inspect descriptor probe does not support its immutable tp_init shortcut.
    signature = ast.parse("def constructor" + Delta.__text_signature__ + ": pass").body[0].args
    assert [item.arg for item in signature.kwonlyargs] == ["nanoseconds", "nanosecond"]
    assert len(signature.args) == 19
    with pytest.raises(TypeError):
        Delta(*([0]*20))


@pytest.mark.parametrize("microseconds,ns,want", [(0,500,0),(1,500,2),(1,1500,2),(0,1500,2)])
def test_datetime_target_rounds_final_coordinate(microseconds,ns,want):
    source = datetime(2024,1,1,microsecond=microseconds)
    assert source+Delta(nanoseconds=ns) == source.replace(microsecond=want)
    source = Pydt(2024,1,1,microsecond=microseconds)
    result = source+Delta(nanoseconds=ns)
    assert isinstance(result,Pydt)
    assert result.microsecond == want


def test_date_target_uses_containing_day_and_datetime_can_round_back():
    delta=Delta(nanoseconds=-1)
    assert date(2024,1,1)+delta == date(2023,12,31)
    assert datetime(2024,1,1)+delta == datetime(2024,1,1)
    assert datetime.min+delta == datetime.min


def test_state_v2_has_no_cache_and_round_trips_nanoseconds():
    source=Delta(nanoseconds=1500,nanosecond=0)
    state=source.__getstate__()
    assert len(state)==4 and state[:2]==("rstimes.delta",2)
    assert len(state[2])==17
    assert state[2][6:8]==(1,500)
    assert state[2][16]==0
    for protocol in range(pickle.HIGHEST_PROTOCOL+1):
        assert pickle.loads(pickle.dumps(source,protocol))==source
    with pytest.raises(ValueError):
        source.__setstate__(("rstimes.delta",1,tuple([0]*15),-1,None))


@pytest.mark.parametrize("ns,want", [(500,0),(1500,2),(-1500,-2)])
def test_timedelta_exit_rounds_once(ns,want):
    assert Delta(nanoseconds=ns).to_timedelta()==timedelta(microseconds=want)
    assert Delta(nanoseconds=500).to_timedelta(datetime(2024,1,1,microsecond=1))==timedelta(microseconds=1)


@pytest.mark.parametrize("field",["years","quarters","months","weeks","days","hours","minutes","seconds",
    "milliseconds","microseconds","nanoseconds","year","month","day","weekday","hour","minute","second","millisecond","microsecond","nanosecond"])
@pytest.mark.parametrize("number",[-(2**63),-1,0,1,2**63-1])
def test_single_primitive_specialization_keeps_the_complete_protocol_role(field,number):
    class Index:
        calls=0
        def __index__(self):
            self.calls+=1
            return number
    source=Index()
    try:
        expected=Delta(**{field:source})
    except (ValueError,OverflowError,TypeError) as failure:
        assert source.calls==1
        with pytest.raises(type(failure)):
            Delta(**{field:number})
    else:
        assert source.calls==1
        assert Delta(**{field:number})==expected


@pytest.mark.parametrize("field",["weeks","days","hours","minutes","seconds","milliseconds","microseconds","nanoseconds"])
@pytest.mark.parametrize("number",[0.,-0.,.1,-.5,1.5,1e-310,1e-9])
def test_single_float_specialization_agrees_with_independent_exact_sum(field,number):
    factors={"weeks":604800000000000,"days":NS_DAY,"hours":3600000000000,"minutes":60000000000,
             "seconds":1000000000,"milliseconds":1000000,"microseconds":1000,"nanoseconds":1}
    expected=round(Fraction.from_float(number)*factors[field])
    assert_fixed(Delta(**{field:number}),expected)
    assert_fixed(Delta(years=0,**{field:number}),expected)
