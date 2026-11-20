"""PR-030: read an actual temporal sequence once, including __getitem__ fallback."""
from datetime import datetime, timedelta

import pytest
from rstimes import Delta, Pddt


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
    source = Pddt(DATES, unit="us")
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
    assert result.asi8.tolist() == expected
    assert events == ([0, 1, 2] if mode == "sequence" else ["iter"] if mode == "iterable" else [])
    assert source.asi8.tolist() == [EPOCH_DAYS * DAY, (EPOCH_DAYS + 1) * DAY]


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
        Pddt(DATES, unit="us") + other
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
        Pddt(DATES, unit="us") + other
    assert events == ([] if mode == "disabled" else ["iter"])


@pytest.mark.parametrize("values", ([Delta()], [Delta(), Delta(), Delta()]))
def test_sequence_lengths_remain_strict(values):
    with pytest.raises(ValueError):
        Pddt(DATES, unit="us") + SequenceOnly(values, [])


def test_sequence_first_invalid_element_keeps_location():
    with pytest.raises(TypeError, match=r"other\[1\]"):
        Pddt(DATES, unit="us") + SequenceOnly([Delta(), "one day"], [])
