"""Inherited equality is not cancelled by unrelated hash/ne declarations."""
from datetime import timedelta
import pytest
from rstimes import Delta


class Unhashable(Delta):
    __hash__ = None


class OnlyNe(Delta):
    def __ne__(self, other):
        return "business inequality"


@pytest.mark.parametrize("base", (Delta, Unhashable, OnlyNe))
@pytest.mark.parametrize("same", (False, True))
def test_inherited_equality_uses_fields_in_both_directions(base, same: bool) -> None:
    left = Delta(days=1, nanoseconds=3)
    right = base(days=1, nanoseconds=3 if same else 4)
    assert (left == right) is same
    assert (right == left) is same
    assert Delta.__eq__(left, right) is same
    assert Delta.__eq__(right, left) is same


def test_unhashable_value_keeps_inequality_but_stays_unhashable() -> None:
    value = Unhashable(days=1)
    assert (value != Delta(days=1)) is False
    assert (Delta(days=2) != value) is True
    assert Delta.__ne__(value, Delta(days=1)) is False
    with pytest.raises(TypeError):
        hash(value)


def test_real_ne_override_keeps_its_nonboolean_return() -> None:
    value = OnlyNe(days=1)
    assert (value != Delta(days=1)) == "business inequality"
    assert (Delta(days=1) != value) == "business inequality"
    assert Delta.__ne__(Delta(days=1), value) is NotImplemented


def test_custom_hash_retains_conservative_explicit_comparison_boundary() -> None:
    class CustomHash(Delta):
        def __hash__(self):
            return 17
    value = CustomHash(days=1)
    assert Delta.__eq__(Delta(days=1), value) is NotImplemented
    assert Delta.__ne__(Delta(days=1), value) is NotImplemented
    assert hash(value) == 17


def test_real_equality_return_and_original_error_are_preserved() -> None:
    answer = object()
    original = LookupError("business equality")

    class Business(Delta):
        def __eq__(self, other):
            return answer

    value = Business(days=1)
    assert (Delta(days=1) == value) is answer
    assert Delta.__eq__(value, Delta(days=1)) is NotImplemented

    class Broken(Delta):
        def __eq__(self, other):
            raise original

    with pytest.raises(LookupError) as caught:
        Delta(days=1) == Broken(days=1)
    assert caught.value is original


@pytest.mark.parametrize("absolute", (None, 10))
def test_bulk_absolute_and_relative_fields_are_still_combined(absolute) -> None:
    addition = Delta(days=2, nanoseconds=5, day=absolute)
    values = [Delta(days=1, nanoseconds=2), timedelta(days=3, microseconds=1), Delta(year=2024)]
    results = addition.apply_many(values)
    assert len(results) == 3 and all(type(result) is Delta for result in results)
    assert [(result.days, result.microseconds, result.nanoseconds, result.day) for result in results] == [
        (3, 0, 7, absolute), (5, 1, 5, absolute), (2, 0, 5, absolute)]
    assert results[2].year == 2024
