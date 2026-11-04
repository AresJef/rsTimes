"""DCR01: a completed whole-column callback owns its returned validity."""
from datetime import datetime, timedelta

import polars as pl
import pytest

from rstimes import Delta, Pldt


METHODS = ("add_delta", "sub_delta")


def ticks(value):
    return value.to_physical().to_list()


def callback_result(result, calls):
    class Whole(Delta):
        def __radd__(self, value):
            calls.append(("add", type(value), len(value)))
            return result

        def __rsub__(self, value):
            calls.append(("sub", type(value), len(value)))
            return result

    return Whole()


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("host", (Pldt, pl.Series), ids=("Pldt", "Series"))
@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
@pytest.mark.parametrize("zone", (None, "UTC", "Asia/Shanghai"))
@pytest.mark.parametrize("source_values,returned_values", [
    ([None, 0], [7, None]),
    ([None], [7]),
    ([], []),
    ([0, None], [None, None]),
    ([None, None], [None, None]),
    ([None, 0, -1], [-(1 << 63), None, (1 << 63) - 1]),
])
def test_whole_result_values_and_validity_are_authoritative(
    method, host, unit, zone, source_values, returned_values
):
    original = Pldt(source_values, unit=unit, tz=zone, name="source")
    source = original if host is Pldt else pl.Series(original)
    returned = Pldt(returned_values, unit=unit, tz=zone, name="callback")
    calls = []
    result = getattr(source.pldt, method)(callback_result(returned, calls))
    assert type(result) is Pldt
    assert ticks(result) == returned_values
    assert result.dtype == source.dtype and result.name == "source"
    assert ticks(source) == source_values and ticks(returned) == returned_values
    assert calls == [("sub" if method == "sub_delta" else "add", host, len(source))]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("source_values", ([None], [0]))
@pytest.mark.parametrize("unit", ("ms", "us"))
@pytest.mark.parametrize("value", (-1, 1))
def test_whole_result_checks_precision_even_where_source_was_missing(
    method, source_values, unit, value
):
    source = Pldt(source_values, unit=unit)
    returned = Pldt([value], unit="ns")
    calls = []
    with pytest.raises(ValueError, match="precision|unit"):
        getattr(source.pldt, method)(callback_result(returned, calls))
    assert len(calls) == 1 and ticks(source) == source_values


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("source_values", ([None], [0]))
@pytest.mark.parametrize("value", (-(1 << 63), (1 << 63) - 1))
def test_whole_result_checks_final_capacity_even_where_source_was_missing(
    method, source_values, value
):
    source = Pldt(source_values, unit="ns")
    returned = Pldt([value], unit="ms")
    with pytest.raises(OverflowError):
        getattr(source.pldt, method)(callback_result(returned, []))
    assert ticks(source) == source_values


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("source_values", ([None], []))
@pytest.mark.parametrize("source_zone,returned_zone", ((None, "UTC"), ("UTC", None)))
def test_awareness_stays_checked_for_missing_and_empty_sources(
    method, source_values, source_zone, returned_zone
):
    source = Pldt(source_values, unit="us", tz=source_zone)
    returned = Pldt([None] * len(source), unit="us", tz=returned_zone)
    with pytest.raises(TypeError, match="awareness|aware"):
        getattr(source.pldt, method)(callback_result(returned, []))


@pytest.mark.parametrize("method", METHODS)
def test_aware_return_is_an_instant_in_source_zone_and_unit(method):
    source = Pldt([None, 0], unit="us", tz="Asia/Shanghai", name="source")
    returned = Pldt([7000, None], unit="ns", tz="UTC", name="callback")
    result = getattr(source.pldt, method)(callback_result(returned, []))
    assert ticks(result) == [7, None]
    assert result.dtype == source.dtype and result.name == "source"


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("returned", [
    datetime(2024, 1, 1), "2024-01-01", 1, timedelta(1), NotImplemented,
])
def test_named_whole_callback_does_not_parse_or_broadcast_business_return(method, returned):
    source = Pldt([0, None], unit="us")
    with pytest.raises((TypeError, ValueError)):
        getattr(source.pldt, method)(callback_result(returned, []))


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("returned_values", ([1], [1, 2, 3]))
def test_whole_date_collection_must_match_complete_source_length(method, returned_values):
    source = Pldt([None, 0], unit="us")
    with pytest.raises(ValueError, match="length"):
        getattr(source.pldt, method)(callback_result(Pldt(returned_values, unit="us"), []))


@pytest.mark.parametrize("method", METHODS)
def test_per_row_callback_still_skips_only_missing_source_rows(method):
    calls = []

    class Row(Delta):
        def __radd__(self, value):
            calls.append(ticks(value))
            return Pldt([7], unit="us")

        def __rsub__(self, value):
            calls.append(ticks(value))
            return Pldt([7], unit="us")

    source = Pldt([None, 0], unit="us")
    result = getattr(source.pldt, method)([Row(), Row()])
    assert ticks(result) == [None, 7] and calls == [[0]]
    assert ticks(source) == [None, 0]


@pytest.mark.parametrize("method", METHODS)
def test_external_whole_callback_failure_retains_exception_identity(method):
    original = RuntimeError("actual business failure")
    calls = []

    class Broken(Delta):
        def __radd__(self, value):
            calls.append("add")
            raise original

        def __rsub__(self, value):
            calls.append("sub")
            raise original

    source = Pldt([None], unit="us")
    with pytest.raises(RuntimeError) as caught:
        getattr(source.pldt, method)(Broken())
    assert caught.value is original and len(calls) == 1


@pytest.mark.parametrize("method", METHODS)
def test_named_return_constructs_business_subclass_once(method):
    calls = []

    class Business(Pldt):
        def __new__(cls, values, **kwargs):
            calls.append("new")
            return super().__new__(cls)

        def __init__(self, values, **kwargs):
            calls.append("init")
            super().__init__(values, **kwargs)

    source = Business([None, 0], unit="us", name="source")
    returned = Pldt([7, None], unit="us")
    calls.clear()
    result = getattr(source.pldt, method)(callback_result(returned, []))
    assert type(result) is Business and calls == ["new", "init"]
    assert ticks(result) == [7, None] and result.name == "source"
