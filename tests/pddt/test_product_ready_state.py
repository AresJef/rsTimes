"""Default business state uses actual containers and actual tuple protocols."""
import pytest

from rstimes import Pddt


class Passive(dict):
    pass


class TupleDisplay(dict):
    @property
    def __class__(self):
        return tuple


class RaisingDisplay(dict):
    @property
    def __class__(self):
        raise RuntimeError("display identity must not be read")


@pytest.mark.parametrize("factory", [dict, Passive, TupleDisplay, RaisingDisplay])
@pytest.mark.parametrize("wrapped", [False, True])
def test_default_restore_uses_real_dictionary_storage(factory, wrapped):
    payload = []
    state = factory(payload=payload)
    value = Pddt([1, None], unit="ns", name="stamp")
    before = value.asi8.tolist()
    value.__setstate__((state, None) if wrapped else state)
    assert value.payload is payload
    assert value.asi8.tolist() == before and value.unit == "ns" and value.name == "stamp"


def test_real_tuple_subclass_retains_its_unpacking_protocol():
    calls = []

    class State(tuple):
        def __iter__(self):
            calls.append("iter")
            return iter(({"payload": "from protocol"}, None))

    value = Pddt([1], unit="ns")
    value.__setstate__(State(({"payload": "stored"}, None)))
    assert value.payload == "from protocol" and calls == ["iter"]
