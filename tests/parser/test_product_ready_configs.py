"""Canonical Configs state and public edits retain their separate value roles."""
import pytest

from rstimes import Configs, parse_str


def state_with_month(mapping):
    namespaces = (set(), set(), set(), {}, mapping, {}, {}, {})
    return ("rstimes.Configs", 2, True, False, namespaces, set())


def test_canonical_restore_rejects_index_object_without_calling_it():
    calls = []

    class Number:
        def __index__(self):
            calls.append("index")
            return 2

    cfg = Configs()
    before = cfg.__getstate__()
    with pytest.raises(TypeError, match="state.month"):
        cfg.__setstate__(state_with_month({"rolemonth": Number()}))
    assert calls == [] and cfg.__getstate__() == before


def test_public_month_edit_still_calls_real_index_once():
    calls = []

    class Number:
        def __index__(self):
            calls.append("index")
            return 2

    cfg = Configs()
    assert cfg.set_month({"rolemonth": Number()}) is True
    assert calls == ["index"]
    assert parse_str("1 rolemonth 2024", cfg=cfg).month == 2


def test_each_namespace_finishes_before_later_namespace_errors():
    cfg = Configs()
    before = cfg.__getstate__()
    state = list(state_with_month({"rolemonth": object()}))
    parts = list(state[4])
    parts[0] = {"bad word"}
    state[4] = tuple(parts)
    with pytest.raises(ValueError) as observed:
        cfg.__setstate__(tuple(state))
    assert not isinstance(observed.value, TypeError)
    assert cfg.__getstate__() == before


def test_restored_namespace_is_independent_of_source_dictionary():
    source = {"rolemonth": 2}
    cfg = Configs()
    cfg.__setstate__(state_with_month(source))
    source["rolemonth"] = 3
    assert parse_str("1 rolemonth 2024", cfg=cfg).month == 2


def test_public_set_edit_preserves_real_iterator_error_once():
    calls = []
    marker = LookupError("business set iterator")

    class Tokens(set):
        def __iter__(self):
            calls.append("iter")
            raise marker

    cfg = Configs()
    before = cfg.__getstate__()
    with pytest.raises(LookupError) as observed:
        cfg.set_jump(Tokens({"roleword"}))
    assert observed.value is marker and calls == ["iter"]
    assert cfg.__getstate__() == before
