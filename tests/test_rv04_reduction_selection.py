"""Independent copy answers protect actual reducers and the shared memo."""
import copy
import copyreg

import pytest

from rstimes import Pddt, Pldt


class Box:
    pass


VARIANTS = ("default", "reduce_only", "ex_custom", "none", "descriptor_none",
            "descriptor_absent", "descriptor_error", "dynamic", "identity", "memo", "registry")


@pytest.mark.parametrize("base", [Pddt, Pldt])
@pytest.mark.parametrize("deep", [False, True])
@pytest.mark.parametrize("variant", VARIANTS)
def test_named_and_standard_copy_select_the_actual_protocol(base, deep, variant):
    calls = []
    original = LookupError("real reducer lookup error")

    def reduced(self):
        calls.append("reduce")
        if variant == "memo":
            return Box, (), {"first": self.shared, "second": self.shared, "peer": self}
        return str, ("chosen reduction",)

    def extended(self, protocol):
        calls.append("ex:" + str(protocol))
        return "identity" if variant == "identity" else (str, ("chosen reduction",))

    class Descriptor:
        def __get__(self, obj, owner):
            calls.append("lookup")
            if variant == "descriptor_none":
                return None
            if variant == "descriptor_absent":
                raise AttributeError("reducer unavailable")
            raise original

    def dynamic(self, name):
        if name == "__reduce_ex__":
            calls.append("dynamic lookup")
            def reducer(protocol):
                calls.append("dynamic:" + str(protocol))
                return str, ("dynamic reduction",)
            return reducer
        return object.__getattribute__(self, name)

    attrs = {} if variant == "default" else {"__copy__": None, "__deepcopy__": None}
    if variant in ("reduce_only", "none", "descriptor_none", "descriptor_absent", "descriptor_error", "memo"):
        attrs["__reduce__"] = reduced
    if variant in ("none", "memo"):
        attrs["__reduce_ex__"] = None
    elif variant.startswith("descriptor"):
        attrs["__reduce_ex__"] = Descriptor()
    elif variant in ("ex_custom", "identity"):
        attrs["__reduce_ex__"] = extended
    elif variant == "dynamic":
        attrs["__getattribute__"] = dynamic
    cls = type("Business", (base,), attrs)
    source = cls([1, None], unit="ns", name="dates")
    source.shared = []

    def registered(value):
        calls.append("registered")
        assert value is source
        return str, ("registered reduction",)

    if variant == "registry":
        copyreg.pickle(cls, registered)
    try:
        for action in ((lambda: copy.deepcopy(source)) if deep else (lambda: copy.copy(source)),
                       lambda: source.copy(deep=deep)):
            calls.clear()
            if variant == "descriptor_error":
                with pytest.raises(LookupError) as caught:
                    action()
                assert caught.value is original and calls == ["lookup"]
                continue
            result = action()
            if variant == "default":
                assert type(result) is cls and result is not source
                ticks = result.asi8.tolist() if base is Pddt else result.to_physical().to_list()
                assert ticks == ([1, -(1 << 63)] if base is Pddt else [1, None])
                assert (result.shared is source.shared) is not deep
                assert calls == []
            elif variant == "identity":
                assert result is source and calls == ["ex:4"]
            elif variant == "memo":
                assert type(result) is Box and result.first is result.second
                assert (result.first is source.shared) is not deep
                assert result.peer is (result if deep else source)
                assert calls == ["reduce"]
            else:
                expected = {"dynamic": "dynamic reduction", "registry": "registered reduction"}.get(variant, "chosen reduction")
                assert type(result) is str and result == expected
                expected_calls = ["dynamic lookup", "dynamic:4"] if variant == "dynamic" else ["registered"] if variant == "registry" else ["ex:4"] if variant == "ex_custom" else ["lookup", "reduce"] if variant.startswith("descriptor") else ["reduce"]
                assert calls == expected_calls
    finally:
        if variant == "registry":
            copyreg.dispatch_table.pop(cls, None)


@pytest.mark.parametrize("base", [Pddt, Pldt])
@pytest.mark.parametrize("deep", [False, True])
@pytest.mark.parametrize("kind", ["none", "descriptor_none"])
def test_inherited_library_copy_hook_has_an_independent_fallback_answer(base, deep, kind):
    calls = []

    class Missing:
        def __get__(self, value, owner):
            calls.append("lookup")
            return None

    def reduced(self):
        calls.append("reduce")
        return str, ("chosen reduction",)

    cls = type("InheritedCopyHooks", (base,), {"__reduce_ex__": None if kind == "none" else Missing(), "__reduce__": reduced})
    source = cls([1, None], unit="ns")
    for action in ((lambda: copy.deepcopy(source)) if deep else (lambda: copy.copy(source)),
                   lambda: source.copy(deep=deep)):
        calls.clear()
        assert action() == "chosen reduction"
        assert calls == (["lookup", "reduce"] if kind == "descriptor_none" else ["reduce"])


@pytest.mark.parametrize("base", [Pddt, Pldt])
@pytest.mark.parametrize("deep", [False, True])
def test_live_replacement_of_a_base_reducer_is_not_recognized_as_library_code(base, deep, monkeypatch):
    source = base([1, None], unit="ns")
    calls = []

    def actual(self, protocol):
        calls.append(protocol)
        assert self is source
        return str, ("replacement reducer",)

    monkeypatch.setattr(base, "__reduce_ex__", actual)
    assert source.copy(deep=deep) == "replacement reducer"
    assert calls == [4]


@pytest.mark.parametrize("base", [Pddt, Pldt])
@pytest.mark.parametrize("deep", [False, True])
@pytest.mark.parametrize("returned", [None, 42])
def test_invalid_actual_recipe_keeps_standard_unpacking_errors(base, deep, returned):
    calls = []

    class InvalidRecipe(base):
        def __reduce_ex__(self, protocol):
            calls.append(protocol)
            return returned

    source = InvalidRecipe([1], unit="ns")
    for action in ((lambda: copy.deepcopy(source)) if deep else (lambda: copy.copy(source)),
                   lambda: source.copy(deep=deep)):
        calls.clear()
        with pytest.raises(TypeError, match="iterable"):
            action()
        assert calls == [4]
