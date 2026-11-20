"""PR-030: read an actual temporal sequence once, including __getitem__ fallback."""
from datetime import datetime, timedelta

import pytest
import polars as pl
from rstimes import Delta, Pldt


DATES = [datetime(2024, 1, 1), datetime(2024, 1, 2)]
DAY = 86_400_000_000
EPOCH_DAYS = 19723


class SequenceOnly:
    def __init__(self, values, events):
        self.values = values
        self.events = events

    def __getitem__(self, index):
        self.events.append(index)
        if index >= len(self.values):
            raise IndexError(index)
        return self.values[index]


class Iterable(SequenceOnly):
    def __iter__(self):
        self.events.append("iter")
        return iter(self.values)


def operand(values, mode, events):
    if mode == "list":
        return list(values)
    if mode == "tuple":
        return tuple(values)
    if mode == "generator":
        return (value for value in values)
    return (SequenceOnly if mode == "sequence" else Iterable)(values, events)


@pytest.mark.parametrize("mode", ("list", "tuple", "generator", "sequence", "iterable"))
@pytest.mark.parametrize("operation", ("delta_add", "delta_sub", "span_add", "span_sub", "date_sub"))
def test_equal_length_actual_sequence_values_and_single_read(mode, operation):
    events = []
    source = Pldt(DATES, unit="us")
    if operation == "date_sub":
        values = DATES
        expected = [0, 0]
    else:
        factory = Delta if operation.startswith("delta") else timedelta
        values = [factory(days=1), factory(days=2)]
        sign = 1 if operation.endswith("add") else -1
        expected = [(EPOCH_DAYS + sign) * DAY, (EPOCH_DAYS + 1 + 2 * sign) * DAY]
    other = operand(values, mode, events)
    result = source + other if operation.endswith("add") else source - other
    assert result.to_physical().to_list() == expected
    assert events == ([0, 1, 2] if mode == "sequence" else ["iter"] if mode == "iterable" else [])
    assert source.to_physical().to_list() == [EPOCH_DAYS * DAY, (EPOCH_DAYS + 1) * DAY]


@pytest.mark.parametrize("error_type", (TypeError, RuntimeError, LookupError))
@pytest.mark.parametrize("protocol", ("iter", "getitem"))
def test_actual_iterator_failures_keep_original_exception_and_first_read(error_type, protocol):
    sentinel = error_type("actual temporal iterator failed")
    events = []
    class BrokenSequence(SequenceOnly):
        def __getitem__(self, index):
            events.append(index)
            if index == 1:
                raise sentinel
            return Delta(days=1)
    class BrokenIterable:
        def __iter__(self):
            events.append("iter")
            raise sentinel
    other = BrokenSequence([], events) if protocol == "getitem" else BrokenIterable()
    with pytest.raises(error_type) as caught:
        Pldt(DATES, unit="us") + other
    assert caught.value is sentinel
    assert events == ([0, 1] if protocol == "getitem" else ["iter"])


@pytest.mark.parametrize("mode", ("disabled", "noniterator"))
def test_disabled_or_malformed_iter_is_not_replaced_by_sequence_fallback(mode):
    events = []
    class Disabled(SequenceOnly):
        __iter__ = None
    class NonIterator(SequenceOnly):
        def __iter__(self):
            events.append("iter")
            return 123
    other = (Disabled if mode == "disabled" else NonIterator)([Delta(), Delta()], events)
    with pytest.raises(TypeError):
        Pldt(DATES, unit="us") + other
    assert events == ([] if mode == "disabled" else ["iter"])


@pytest.mark.parametrize("values", ([Delta()], [Delta(), Delta(), Delta()]))
def test_sequence_lengths_remain_strict(values):
    with pytest.raises(ValueError):
        Pldt(DATES, unit="us") + SequenceOnly(values, [])


def test_sequence_first_invalid_element_keeps_location():
    with pytest.raises(TypeError, match=r"other\[1\]"):
        Pldt(DATES, unit="us") + SequenceOnly([Delta(), "one day"], [])


@pytest.mark.parametrize("expression", (False, True))
@pytest.mark.parametrize("subtract", (False, True))
def test_named_delta_accepts_one_pass_sequence_and_expr_captures_values(expression, subtract):
    events = []
    values = [Delta(days=1), Delta(days=2)]
    target = SequenceOnly(values, events)
    method = "sub_delta" if subtract else "add_delta"
    sign = -1 if subtract else 1
    expected = [(EPOCH_DAYS + sign) * DAY, (EPOCH_DAYS + 1 + 2 * sign) * DAY]
    if expression:
        expr = getattr(pl.col("clock").pldt, method)(target)
        values[:] = [Delta(days=20), Delta(days=20)]
        result = pl.DataFrame({"clock": DATES}).lazy().select(expr).collect().to_series()
    else:
        result = getattr(Pldt(DATES, unit="us").pldt, method)(target)
    assert result.to_physical().to_list() == expected
    assert events == [0, 1, 2]


def test_unknown_scalar_keeps_not_implemented_negotiation():
    assert Pldt(DATES, unit="us").__add__(object()) is NotImplemented
