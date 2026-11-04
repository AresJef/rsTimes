"""DCR02: named copy uses the same hook binding as Python's copy module."""
import copy

import pytest

from rstimes import Pddt, Pldt


def hooked_type(base, deep, style, result, visits, failure=None):
    class Business(base):
        pass

    def completed(value=None, memo=None):
        visits.append(("call", value, memo))
        if failure is not None:
            raise failure
        return result

    if deep:
        def plain(self, memo):
            return completed(self, memo)

        def static(memo):
            return completed(memo=memo)

        def class_hook(cls, memo):
            return completed(cls, memo)
    else:
        def plain(self):
            return completed(self)

        def static(value):
            return completed(value)

        def class_hook(cls, value):
            assert cls is Business
            return completed(value)

    class Descriptor:
        def __get__(self, instance, owner):
            visits.append(("bind", instance, owner))
            return static

    def property_hook(self):
        visits.append(("property", self))
        return static

    hook = {
        "plain": plain,
        "static": staticmethod(static),
        "class": classmethod(class_hook),
        "descriptor": Descriptor(),
        "property": property(property_hook),
    }[style]
    setattr(Business, "__deepcopy__" if deep else "__copy__", hook)
    return Business


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("deep", (False, True))
@pytest.mark.parametrize("style", ("plain", "static", "class", "descriptor", "property"))
@pytest.mark.parametrize("returned", ("business result", None, NotImplemented))
def test_named_copy_matches_stdlib_binding_and_callback_return(base, deep, style, returned):
    visits = []
    business = hooked_type(base, deep, style, returned, visits)
    value = business(["2024-01-01"])
    standard = copy.deepcopy if deep else copy.copy
    if style == "property" and not deep:
        # Python shallow copy deliberately looks up the class, so a property
        # object is not an instance-bound callable in either entry.
        with pytest.raises(TypeError):
            standard(value)
        assert visits == []
        with pytest.raises(TypeError):
            value.copy(deep=False)
        assert visits == []
        return

    assert standard(value) is returned
    standard_visits = visits.copy()
    visits.clear()
    assert value.copy(deep=deep) is returned
    assert [item[0] for item in visits] == [item[0] for item in standard_visits]
    call = next(item for item in visits if item[0] == "call")
    assert sum(item[0] == "call" for item in visits) == 1
    if deep:
        assert type(call[2]) is dict
    else:
        assert call[1] is value
    if style == "descriptor":
        assert visits[0] == ("bind", value if deep else None, business)
    if style == "property":
        assert visits[0] == ("property", value)


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("deep,style", (
    (False, "plain"), (False, "static"), (False, "class"), (False, "descriptor"),
    (True, "plain"), (True, "static"), (True, "class"), (True, "descriptor"),
    (True, "property"),
))
def test_named_copy_keeps_the_actual_hook_exception_and_calls_once(base, deep, style):
    original = LookupError("actual business copy failure")
    visits = []
    business = hooked_type(base, deep, style, None, visits, original)
    value = business(["2024-01-01"])
    with pytest.raises(LookupError) as caught:
        value.copy(deep=deep)
    assert caught.value is original and caught.value.args == ("actual business copy failure",)
    assert sum(item[0] == "call" for item in visits) == 1


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("deep", (False, True))
@pytest.mark.parametrize("disabled", (False, True), ids=("inherited", "None"))
def test_absent_or_disabled_copy_hook_uses_the_real_reduction(base, deep, disabled):
    visits = []

    class Business(base):
        def __reduce__(self):
            visits.append("reduce")
            return str, ("reduction result",)

    if disabled:
        setattr(Business, "__deepcopy__" if deep else "__copy__", None)
    value = Business(["2024-01-01"])
    assert (copy.deepcopy(value) if deep else copy.copy(value)) == "reduction result"
    assert visits == ["reduce"]
    visits.clear()
    assert value.copy(deep=deep) == "reduction result"
    assert visits == ["reduce"]


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("deep", (False, True))
@pytest.mark.parametrize("same_object", (False, True))
def test_optional_name_does_not_change_source_returned_by_a_hook(base, deep, same_object):
    calls = []

    class Business(base):
        def __copy__(self):
            calls.append("copy")
            return self if same_object else base(["2024-01-01"], name="callback")

        def __deepcopy__(self, memo):
            assert type(memo) is dict
            calls.append("deepcopy")
            return self if same_object else base(["2024-01-01"], name="callback")

    value = Business(["2024-01-01"], name="source")
    if same_object:
        with pytest.raises(ValueError, match="original object"):
            value.copy(name="requested", deep=deep)
    else:
        result = value.copy(name="requested", deep=deep)
        assert type(result) is base and result.name == "requested"
    assert value.name == "source" and calls == ["deepcopy" if deep else "copy"]


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("deep", (False, True))
@pytest.mark.parametrize("disabled", ("None", "AttributeError"))
def test_bound_descriptor_can_disable_a_copy_hook_like_stdlib(base, deep, disabled):
    calls = []

    class Descriptor:
        def __get__(self, instance, owner):
            calls.append("bind")
            if disabled == "AttributeError":
                raise AttributeError("hook unavailable")
            return None

    class Business(base):
        def __reduce__(self):
            calls.append("reduce")
            return str, ("fallback reduction",)

    setattr(Business, "__deepcopy__" if deep else "__copy__", Descriptor())
    value = Business(["2024-01-01"])
    assert (copy.deepcopy(value) if deep else copy.copy(value)) == "fallback reduction"
    expected = calls.copy()
    calls.clear()
    assert value.copy(deep=deep) == "fallback reduction"
    assert calls == expected == ["bind", "reduce"]


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("deep", (False, True))
def test_real_dynamic_hook_lookup_matches_stdlib_without_static_capability_cache(base, deep):
    calls = []

    class Meta(type(base)):
        def __getattribute__(cls, name):
            if name == "__copy__":
                def shallow(value):
                    calls.append("shallow")
                    return "dynamic shallow"
                return shallow
            return super().__getattribute__(name)

    class Business(base, metaclass=Meta):
        def __getattribute__(self, name):
            if name == "__deepcopy__":
                def deep_copy(memo):
                    assert type(memo) is dict
                    calls.append("deep")
                    return "dynamic deep"
                return deep_copy
            return super().__getattribute__(name)

    value = Business(["2024-01-01"])
    expected = "dynamic deep" if deep else "dynamic shallow"
    assert (copy.deepcopy(value) if deep else copy.copy(value)) == expected
    calls.clear()
    result = value.copy(deep=deep)
    assert type(result) is str and result == expected
    assert calls == ["deep" if deep else "shallow"]
