"""Caching copy preparation must preserve each live deepcopy helper lookup."""
import copy

import pytest

from rstimes import Delta


class Child(Delta):
    pass


def test_child_copy_reads_the_current_deepcopy_helper(monkeypatch):
    value = Child(days=1)
    value.items = [1, 2]
    value.__deepcopy__({})
    original = copy.deepcopy
    seen = []

    def current(obj, *args, **kwargs):
        seen.append(type(obj))
        return original(obj, *args, **kwargs)

    monkeypatch.setattr(copy, "deepcopy", current)
    result = value.__deepcopy__({})
    assert seen
    assert type(result) is Child and result.days == 1
    assert result.items == [1, 2] and result.items is not value.items


def test_child_copy_keeps_the_current_helper_error_and_memo(monkeypatch):
    value = Child(days=1)
    value.label = "kept"
    value.__deepcopy__({})
    marker = RuntimeError("current deepcopy helper failed")
    memo = {}

    def current(obj, passed_memo):
        assert passed_memo is memo
        assert id(value) in memo and type(memo[id(value)]) is Child
        raise marker

    monkeypatch.setattr(copy, "deepcopy", current)
    with pytest.raises(RuntimeError) as error:
        value.__deepcopy__(memo)
    assert error.value is marker
