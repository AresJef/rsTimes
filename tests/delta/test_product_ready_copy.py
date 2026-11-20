"""PR-008: inherited native copying honors live business reconstruction."""
import copy
import copyreg

import pytest
from rstimes import Delta

OPERATIONS = (copy.copy, copy.deepcopy)
FIELDS = ("years", "months", "days", "hours", "minutes", "seconds", "microseconds",
          "nanoseconds", "year", "month", "day", "weekday", "hour", "minute", "second",
          "microsecond", "nanosecond")


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("protocol", ("state", "reduce", "reduce_ex", "registered"))
def test_inherited_copy_uses_selected_business_recipe(operation, protocol, monkeypatch):
    calls = []

    class Business(Delta):
        pass

    if protocol == "state":
        def getstate(self):
            calls.append("getstate")
            return {"selected": self.selected}
        def setstate(self, state):
            calls.append("setstate")
            self.selected = state["selected"]
        Business.__getstate__ = getstate
        Business.__setstate__ = setstate
    elif protocol == "reduce":
        def reduce(self):
            calls.append("reduce")
            return str, ("selected result",)
        Business.__reduce__ = reduce
    elif protocol == "reduce_ex":
        def reduce_ex(self, protocol):
            calls.append(("reduce_ex", protocol))
            return str, ("selected result",)
        Business.__reduce_ex__ = reduce_ex
    else:
        def registered(value):
            calls.append("registered")
            return str, ("selected result",)
        monkeypatch.setitem(copyreg.dispatch_table, Business, registered)
    source = Business(days=2, nanoseconds=17, nanosecond=0)
    source.selected = ["kept"]
    source.omitted = "must not be copied by custom state"
    result = operation(source)
    if protocol == "state":
        assert type(result) is Business and result is not source
        assert result.selected == ["kept"] and not hasattr(result, "omitted")
        assert result.nanoseconds == 17 and result.nanosecond == 0 and result.days == 2
        assert (result.selected is source.selected) is (operation is copy.copy)
        assert calls == ["getstate", "setstate"]
    else:
        assert type(result) is str and result == "selected result"
        assert calls == [("reduce_ex", 4)] if protocol == "reduce_ex" else calls == [protocol]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_exact_delta_registration_is_live_and_does_not_replace_explicit_copy_hooks(operation, monkeypatch):
    source = Delta(nanoseconds=7, nanosecond=0)
    calls = []
    def registered(value):
        assert value is source
        calls.append("registered")
        return str, ("registered exact base",)
    with monkeypatch.context() as patch:
        patch.setitem(copyreg.dispatch_table, Delta, registered)
        assert operation(source) == "registered exact base"
        assert calls == ["registered"]
    result = operation(source)
    assert type(result) is Delta and result is not source
    assert result.nanoseconds == 7 and result.nanosecond == 0


@pytest.mark.parametrize("operation", OPERATIONS)
def test_plain_native_and_passive_copies_preserve_all_fields_and_default_memo(operation):
    class Passive(Delta):
        __slots__ = ("slot", "unset", "__dict__")
    expected = (2, 3, -4, 5, 6, 7, 8, 9, 2024, 2, 29, 0, 10, 11, 12, 123456, 789)
    source = Passive(**dict(zip(FIELDS, expected)))
    source.payload = []
    source.alias = source.slot = source.payload
    source.self = source
    memo = {}
    result = copy.deepcopy(source, memo) if operation is copy.deepcopy else operation(source)
    assert type(result) is Passive and result is not source
    assert tuple(getattr(result, name) for name in FIELDS) == expected
    assert result.payload is result.alias is result.slot
    assert (result.payload is source.payload) is (operation is copy.copy)
    assert result.self is (source if operation is copy.copy else result)
    assert not hasattr(result, "unset") and hash(result) == hash(source)
    if operation is copy.deepcopy:
        assert memo[id(source)] is result and memo[id(source.payload)] is result.payload


def test_custom_state_deepcopy_reuses_one_memo_for_aliases_and_self_cycle():
    calls = []
    class Business(Delta):
        def __getstate__(self):
            calls.append("getstate")
            return {"one": self.one, "two": self.one, "self": self}
        def __setstate__(self, state):
            calls.append("setstate")
            self.__dict__.update(state)
    source = Business(nanoseconds=999)
    source.one = []
    source.excluded = 42
    memo = {}
    result = copy.deepcopy([source, source], memo)
    value = result[0]
    assert value is result[1] is memo[id(source)] and value.self is value
    assert value.one is value.two is memo[id(source.one)] and value.one is not source.one
    assert value.nanoseconds == 999 and not hasattr(value, "excluded")
    assert calls == ["getstate", "setstate"]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_custom_setstate_alone_receives_default_selected_metadata(operation):
    calls = []
    class Business(Delta):
        def __setstate__(self, state):
            calls.append(state)
            self.selected = state["raw"]
    source = Business(nanoseconds=19)
    source.raw = ["business"]
    result = operation(source)
    assert type(result) is Business and result.nanoseconds == 19
    assert result.selected == ["business"] and not hasattr(result, "raw")
    assert len(calls) == 1 and calls[0] == {"raw": ["business"]}


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("selection", ("descriptor", "dynamic", "none_then_basic"))
def test_reducer_lookup_uses_actual_binding_once(operation, selection):
    calls = []
    def chosen(protocol=None):
        calls.append(("call", protocol))
        return str, ("chosen dynamically",)
    class Business(Delta):
        pass
    if selection == "descriptor":
        class Descriptor:
            def __get__(self, instance, owner):
                if instance is None:
                    return self
                calls.append("bind")
                return chosen
        Business.__reduce_ex__ = Descriptor()
        expected = ["bind", ("call", 4)]
    elif selection == "dynamic":
        def lookup(self, name):
            if name == "__reduce_ex__":
                calls.append("lookup")
                return chosen
            return object.__getattribute__(self, name)
        Business.__getattribute__ = lookup
        expected = ["lookup", ("call", 4)]
    else:
        Business.__reduce_ex__ = None
        def basic(self):
            return chosen()
        Business.__reduce__ = basic
        expected = [("call", None)]
    assert operation(Business(days=1)) == "chosen dynamically"
    assert calls == expected


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("kind", ("lookup", "reduce", "state", "setter"))
def test_real_protocol_exceptions_keep_original_identity(operation, kind):
    marker = LookupError("business " + kind)
    calls = []
    class Business(Delta):
        pass
    def fail(*args):
        calls.append(kind)
        raise marker
    if kind == "lookup":
        class Descriptor:
            def __get__(self, instance, owner):
                return self if instance is None else fail()
        Business.__reduce_ex__ = Descriptor()
    elif kind == "reduce":
        Business.__reduce_ex__ = fail
    elif kind == "state":
        Business.__getstate__ = fail
    else:
        Business.__getstate__ = lambda self: {"selected": 1}
        Business.__setstate__ = fail
    with pytest.raises(LookupError) as observed:
        operation(Business(days=1))
    assert observed.value is marker and calls == [kind]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_missing_or_false_basic_reducer_keeps_mode_specific_error(operation):
    class Business(Delta):
        __reduce_ex__ = None
        __reduce__ = None
    with pytest.raises(copy.Error):
        operation(Business(days=1))


@pytest.mark.parametrize("operation", OPERATIONS)
def test_false_callable_registration_uses_standard_mode_selection(operation, monkeypatch):
    calls = []
    class Registered:
        def __bool__(self):
            calls.append("bool")
            return False
        def __call__(self, value):
            calls.append("call")
            return str, ("false callable registration",)
    source = Delta(nanoseconds=11)
    monkeypatch.setitem(copyreg.dispatch_table, Delta, Registered())
    result = operation(source)
    if operation is copy.copy:
        assert result == "false callable registration" and calls == ["call"]
    else:
        assert type(result) is Delta and result.nanoseconds == 11 and calls == ["bool"]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_explicit_business_copy_hooks_still_win_over_registration(operation, monkeypatch):
    calls = []
    class Business(Delta):
        def __copy__(self):
            calls.append("copy")
            return "explicit copy"
        def __deepcopy__(self, memo):
            calls.append("deepcopy")
            return "explicit deepcopy"
    monkeypatch.setitem(copyreg.dispatch_table, Business, lambda value: (_ for _ in ()).throw(AssertionError("not selected")))
    mode = "copy" if operation is copy.copy else "deepcopy"
    assert operation(Business()) == "explicit " + mode
    assert calls == [mode]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_string_recipe_keeps_original_and_does_not_add_state(operation):
    class Business(Delta):
        def __reduce_ex__(self, protocol):
            return "global self"
    value = Business(nanoseconds=2)
    value.raw = []
    assert operation(value) is value


@pytest.mark.parametrize("operation", OPERATIONS)
def test_external_recipe_keeps_constructor_state_list_dict_and_one_memo(operation):
    payload = []
    calls = []
    class Box:
        def __init__(self, argument):
            calls.append("construct")
            self.argument = argument
            self.items = []
            self.mapping = {}
        def append(self, value):
            self.items.append(value)
        def __setitem__(self, key, value):
            self.mapping[key] = value
    class Business(Delta):
        def __reduce_ex__(self, protocol):
            calls.append(("reduce_ex", protocol))
            return Box, (payload,), {"selected": payload}, iter([payload]), iter([("key", payload)])
    source = Business(nanoseconds=3)
    source.omitted = "not selected"
    result = operation(source)
    assert type(result) is Box and not hasattr(result, "omitted")
    assert result.argument is result.selected is result.items[0] is result.mapping["key"]
    assert (result.selected is payload) is (operation is copy.copy)
    assert calls == [("reduce_ex", 4), "construct"]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_native_method_bound_to_another_receiver_is_not_the_default(operation):
    chosen = Delta(nanoseconds=314)
    class Business(Delta):
        __reduce_ex__ = None
        __reduce__ = chosen.__reduce__
    result = operation(Business(nanoseconds=13))
    assert type(result) is Delta and result.nanoseconds == 314


@pytest.mark.parametrize("operation", OPERATIONS)
def test_lookup_result_is_not_read_again_after_descriptor_changes_class(operation):
    calls = []
    class Business(Delta):
        pass
    def replacement(*args):
        raise AssertionError("new class definition was not selected")
    def selected(protocol):
        calls.append(("selected", protocol))
        return str, ("original binding",)
    class Descriptor:
        def __get__(self, instance, owner):
            if instance is None:
                return self
            calls.append("bind")
            owner.__reduce_ex__ = replacement
            return selected
    Business.__reduce_ex__ = Descriptor()
    assert operation(Business()) == "original binding"
    assert calls == ["bind", ("selected", 4)]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_reconstruction_failure_propagates_original_exception(operation):
    marker = LookupError("chosen constructor failure")
    calls = []
    def construct():
        calls.append("construct")
        raise marker
    class Business(Delta):
        def __reduce_ex__(self, protocol):
            return construct, ()
    with pytest.raises(LookupError) as observed:
        operation(Business())
    assert observed.value is marker and calls == ["construct"]


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("name", ("__reduce_ex__", "__getstate__"))
def test_instance_protocol_binding_is_not_hidden_by_passive_class(operation, name):
    calls = []
    class Business(Delta):
        pass
    value = Business(nanoseconds=29)
    value.omitted = 1
    if name == "__reduce_ex__":
        def chosen(protocol):
            calls.append(protocol)
            return str, ("instance reducer",)
        value.__reduce_ex__ = chosen
        assert operation(value) == "instance reducer" and calls == [4]
    else:
        def chosen_state():
            calls.append("state")
            return {"selected": [1]}
        value.__getstate__ = chosen_state
        result = operation(value)
        assert type(result) is Business and result.selected == [1]
        assert not hasattr(result, "omitted") and calls == ["state"]
        assert result.nanoseconds == 29


def test_false_subclass_registration_is_evaluated_once_then_uses_real_reducer(monkeypatch):
    calls = []
    class Business(Delta):
        def __reduce_ex__(self, protocol):
            calls.append("reduce")
            return str, ("real reducer",)
    class Registered:
        def __bool__(self):
            calls.append("bool")
            return False
        def __call__(self, value):
            raise AssertionError("false registration is not selected for deep copy")
    monkeypatch.setitem(copyreg.dispatch_table, Business, Registered())
    assert copy.deepcopy(Business()) == "real reducer" and calls == ["bool", "reduce"]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_passive_eligibility_is_not_cached_across_later_business_changes(operation):
    class Business(Delta):
        pass
    source = Business(nanoseconds=41)
    source.raw = [1]
    before = operation(source)
    assert type(before) is Business and before.raw == [1]
    def selected(self, protocol):
        return str, ("later protocol",)
    Business.__reduce_ex__ = selected
    assert operation(source) == "later protocol"
    del Business.__reduce_ex__
    after = operation(source)
    assert type(after) is Business and after.nanoseconds == 41 and after.raw == [1]


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("state", (None, {"selected": [7]}))
def test_copy_does_not_bind_source_setter_before_selected_state(operation, state):
    """A result setter has no role in selecting the source's business state."""
    events = []
    source_holder = []
    marker = LookupError("unused source setter")

    class Business(Delta):
        def __getstate__(self):
            events.append("getter")
            return state

        @property
        def __setstate__(self):
            if self is source_holder[0]:
                events.append("source setter")
                raise marker
            events.append("result setter")
            def apply(value):
                events.append("apply")
                self.selected = value["selected"]
            return apply

    expected = (2, 3, -4, 5, 6, 7, 8, 9, 2024, 2, 29, 0, 10, 11, 12, 123456, 789)
    source = Business(**dict(zip(FIELDS, expected)))
    source_holder.append(source)
    source.omitted = "not part of the selected state"
    memo = {}
    result = copy.deepcopy(source, memo) if operation is copy.deepcopy else operation(source)
    assert type(result) is Business and result is not source
    assert tuple(getattr(result, name) for name in FIELDS) == expected
    assert events[0] == "getter" and "source setter" not in events
    assert not hasattr(result, "omitted")
    if state is None:
        assert events == ["getter"] and not hasattr(result, "selected")
    else:
        assert result.selected == [7] and events[-1] == "apply"
        assert events.count("apply") == 1
        assert (result.selected is state["selected"]) is (operation is copy.copy)
    if operation is copy.deepcopy:
        assert memo[id(source)] is result
        if state is not None:
            assert memo[id(state["selected"])] is result.selected


@pytest.mark.parametrize("operation", OPERATIONS)
def test_selected_getter_error_precedes_unused_source_setter(operation):
    events = []
    marker = LookupError("selected getter")

    class Business(Delta):
        def __getstate__(self):
            events.append("getter")
            raise marker

        @property
        def __setstate__(self):
            events.append("source setter")
            raise RuntimeError("not selected")

    with pytest.raises(LookupError) as observed:
        operation(Business(nanoseconds=17))
    assert observed.value is marker and events == ["getter"]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_default_empty_metadata_does_not_need_source_setter(operation):
    events = []

    class Business(Delta):
        @property
        def __setstate__(self):
            events.append("setter")
            raise AssertionError("empty default metadata has no setter application")

    source = Business(nanoseconds=23)
    assert object.__getstate__(source) is None
    result = operation(source)
    assert type(result) is Business and result is not source
    assert result.nanoseconds == 23 and not events


@pytest.mark.parametrize("operation", OPERATIONS)
def test_copy_keeps_actual_getter_binding_after_descriptor_changes_class(operation):
    calls = []

    class Business(Delta):
        def __setstate__(self, state):
            calls.append("setter")
            self.selected = state["selected"]

    def unselected(self):
        raise AssertionError("replacement getter was not selected")

    class Getter:
        def __get__(self, instance, owner):
            if instance is None:
                return self
            calls.append("bind getter")
            owner.__getstate__ = unselected
            def selected():
                calls.append("getter")
                return {"selected": [31]}
            return selected

    Business.__getstate__ = Getter()
    result = operation(Business(nanoseconds=29))
    assert type(result) is Business and result.selected == [31]
    assert result.nanoseconds == 29 and calls == ["bind getter", "getter", "setter"]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_copy_keeps_post_getter_constructor_selection(operation):
    calls = []

    def unselected_new(cls, *args, **kwargs):
        calls.append("unselected constructor")
        raise AssertionError("native reconstruction must retain the complete core")

    class Business(Delta):
        def __getstate__(self):
            calls.append("getter")
            type(self).__new__ = staticmethod(unselected_new)
            return {"selected": [41]}

        def __setstate__(self, state):
            calls.append("setter")
            self.selected = state["selected"]

    source = Business(nanoseconds=53)
    result = operation(source)
    assert type(result) is Business and result is not source
    assert result.nanoseconds == 53 and result.selected == [41]
    assert calls == ["getter", "setter"]


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("storage", ["dict", "slots", "both"])
def test_setter_only_receives_default_business_metadata_shape(operation, storage):
    states = []

    class Business(Delta):
        __slots__ = ("slot", "__dict__")

        def __setstate__(self, state):
            states.append(state)
            self.selected = state

    source = Business(nanoseconds=61)
    shared = ["business"]
    if storage in ("dict", "both"):
        source.raw = shared
    if storage in ("slots", "both"):
        source.slot = shared
    memo = {}
    result = copy.deepcopy(source, memo) if operation is copy.deepcopy else operation(source)
    assert type(result) is Business and result.nanoseconds == 61 and len(states) == 1
    if storage == "dict":
        assert type(result.selected) is dict and set(result.selected) == {"raw"}
        selected = result.selected["raw"]
    else:
        dictionary, slots = result.selected
        assert type(result.selected) is tuple and len(result.selected) == 2
        assert dictionary is None if storage == "slots" else set(dictionary) == {"raw"}
        assert set(slots) == {"slot"}
        selected = slots["slot"]
        if storage == "both":
            assert dictionary["raw"] is selected
    assert selected == ["business"]
    assert (selected is shared) is (operation is copy.copy)
    if operation is copy.deepcopy:
        assert memo[id(source)] is result and memo[id(shared)] is selected
