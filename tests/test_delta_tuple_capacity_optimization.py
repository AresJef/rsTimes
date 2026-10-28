"""Tuple bulk addition preserves live Python dispatch and owned output prefixes."""
import gc
from datetime import date, datetime, timedelta

import pytest

from rstimes import Delta


@pytest.mark.parametrize("values", [
    (), tuple(Delta(days=i) for i in range(8)),
    tuple(timedelta(days=i) for i in range(8)),
    tuple(date(2024, 5, i) for i in range(1, 9)),
    tuple(datetime(2024, 5, i) for i in range(1, 9)),
])
def test_tuple_bulk_keeps_order_types_and_values(values):
    delta = Delta(months=1, days=2, hour=0)
    actual = delta.apply_many(values)
    expected = [value + delta for value in values]
    assert actual == expected
    assert [type(value) for value in actual] == [type(value) for value in expected]


def test_tuple_callback_can_change_a_discovered_completed_output_prefix():
    first, second, third = object(), object(), object()
    calls = []

    class Item:
        def __add__(self, other):
            calls.append(len(calls))
            if len(calls) == 1:
                return first
            if len(calls) == 2:
                for value in gc.get_objects():
                    if type(value) is list and len(value) == 1 and value[0] is first:
                        value.clear()
                        value.extend(("changed", "replaced", "replaced"))
                        break
                else:
                    raise AssertionError("the completed output prefix was not visible")
                return second
            return third

    result = Delta(days=1).apply_many((Item(), Item(), Item()))
    assert calls == [0, 1, 2]
    assert result[0] == "changed" and result[1] is second and result[2] is third


def test_tuple_subclass_keeps_its_real_iteration_protocol():
    class Values(tuple):
        def __iter__(self):
            yield timedelta(days=7)
            yield timedelta(days=2)

    delta = Delta(days=1)
    assert delta.apply_many(Values((timedelta(days=99),))) == [
        delta + timedelta(days=7), delta + timedelta(days=2),
    ]
