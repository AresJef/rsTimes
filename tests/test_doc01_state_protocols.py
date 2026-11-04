"""DCR03: reconstruction follows real class definitions, not display metadata."""
import copy
import pickle

import pytest

from rstimes import Pddt, Pldt
from rstimes._class_protocol import definition


BASES = (Pddt, Pldt)
OPERATIONS = (
    ("copy", copy.copy),
    ("deepcopy", copy.deepcopy),
    ("named_copy", lambda value: value.copy()),
    ("named_deepcopy", lambda value: value.copy(deep=True)),
    ("reduce_ex4", lambda value: value.__reduce_ex__(4)),
    ("reduce_ex5", lambda value: value.__reduce_ex__(5)),
    ("pickle", lambda value: pickle.loads(pickle.dumps(value))),
)


def business_type(base, mode, visits, calls):
    enabled = False

    class Meta(type(base)):
        @property
        def __mro__(cls):
            visits.append("mro")
            if mode == "mro_raises":
                raise RuntimeError("display MRO must not run")
            if mode == "mro_hides_child":
                return type.__dict__["__mro__"].__get__(base)
            return type.__dict__["__mro__"].__get__(cls)

        @property
        def __dict__(cls):
            if not enabled:
                # ABCMeta is allowed to read its new class during creation.
                # Only library protocol discovery is under test here.
                return type.__dict__["__dict__"].__get__(cls)
            visits.append("dict")
            if mode == "dict_raises":
                raise RuntimeError("display dictionary must not run")
            if mode == "dict_hides_hook":
                return {"application_metadata": True}
            return type.__dict__["__dict__"].__get__(cls)

    class Business(base, metaclass=Meta):
        def __reduce__(self):
            calls.append("actual_reduce")
            return str, ("chosen business result",)

    enabled = True
    return Business


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("mode", (
    "display_control", "mro_raises", "mro_hides_child",
    "dict_raises", "dict_hides_hook",
))
@pytest.mark.parametrize("label,operation", OPERATIONS, ids=[item[0] for item in OPERATIONS])
def test_real_reduction_cannot_be_replaced_by_metaclass_display(base, mode, label, operation):
    visits, calls = [], []
    business = business_type(base, mode, visits, calls)
    value = business(["2024-01-01"])
    visits.clear()
    result = operation(value)
    expected = (str, ("chosen business result",)) if label.startswith("reduce_ex") else "chosen business result"
    assert result == expected
    assert calls == ["actual_reduce"]
    assert visits == []


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("mode", ("mro_raises", "dict_hides_hook"))
def test_definition_reads_live_class_changes_without_a_metadata_cache(base, mode):
    visits, calls = [], []
    business = business_type(base, mode, visits, calls)
    original = type.__dict__["__dict__"].__get__(business)["__reduce__"]
    visits.clear()
    assert definition(business, "__reduce__") is original

    def replacement(self):
        calls.append("replacement")
        return str, ("live replacement",)

    business.__reduce__ = replacement
    assert definition(business, "__reduce__") is replacement
    value = business(["2024-01-01"])
    assert copy.copy(value) == "live replacement"
    assert calls == ["replacement"] and visits == []


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("deep", (False, True))
def test_default_state_copy_preserves_business_aliases(base, deep):
    class Business(base):
        __slots__ = ("business_slot",)

    value = Business(["2024-01-01", None], name="dates")
    shared = [value]
    value.business_slot = shared
    value.business = shared
    result = value.copy(deep=deep)
    assert type(result) is Business and result is not value
    assert result.name == "dates"
    assert result.business is result.business_slot
    assert (result.business is shared) is (not deep)
    assert result.business[0] is (result if deep else value)


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("deep", (False, True))
def test_actual_object_state_protocol_failure_is_preserved(base, deep):
    original = LookupError("copyreg actual slot discovery failure")

    class Meta(type(base)):
        @property
        def __mro__(cls):
            raise original

    class Business(base, metaclass=Meta):
        __slots__ = ("business_slot",)

    value = Business(["2024-01-01"])
    value.business_slot = "value"
    # object.__getstate__ delegates slot discovery to copyreg._slotnames.
    # Its real external exception is not a failed static-definition lookup.
    with pytest.raises(LookupError) as caught:
        value.copy(deep=deep)
    assert caught.value is original


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("deep", (False, True))
def test_real_state_descriptors_remain_bound_normally(base, deep):
    visits, calls = [], []

    class Meta(type(base)):
        @property
        def __mro__(cls):
            visits.append("display_mro")
            raise AssertionError("display MRO must not run")

    class Business(base, metaclass=Meta):
        @property
        def __getstate__(self):
            def get():
                calls.append("get")
                return {"application": self.application}
            return get

        @property
        def __setstate__(self):
            def set_state(state):
                calls.append("set")
                self.application = state["application"]
            return set_state

    value = Business(["2024-01-01"])
    value.application = ["business"]
    result = value.copy(deep=deep)
    assert type(result) is Business and calls == ["get", "set"]
    assert result.application == ["business"] and visits == []
    assert (result.application is value.application) is (not deep)


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("hook", ("__getstate__", "__setstate__"))
@pytest.mark.parametrize("deep", (False, True))
def test_actual_state_descriptor_failure_keeps_its_exception(base, hook, deep):
    original = LookupError("actual state failure")
    calls = []

    class Business(base):
        pass

    def descriptor(self):
        def fail(*args):
            calls.append(hook)
            raise original
        return fail

    setattr(Business, hook, property(descriptor))
    value = Business(["2024-01-01"])
    value.application = ["business"]
    with pytest.raises(LookupError) as caught:
        value.copy(deep=deep)
    assert caught.value is original and calls == [hook]
