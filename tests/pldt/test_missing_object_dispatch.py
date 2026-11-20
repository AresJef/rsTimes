"""Missing object rows retain lazy defaults, iteration and argument validation."""
import polars as pl
import pytest

from rstimes import Pldt


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_missing_object_rows_do_not_read_an_irrelevant_default(unit):
    values = [None, None, None]
    result = Pldt.parse(iter(values), unit=unit, name="events", default="May 7")
    assert result.dtype == pl.Datetime(unit)
    assert result.name == "events"
    assert result.to_physical().to_list() == values
    assert values == [None, None, None]


def test_iterator_failure_after_missing_rows_keeps_identity_and_order():
    error = RuntimeError("missing-input iterator sentinel")
    events = []

    def values():
        for index in range(3):
            events.append(index)
            yield None
        events.append("failure")
        raise error

    with pytest.raises(RuntimeError) as caught:
        Pldt.parse(values(), unit="ns")
    assert caught.value is error
    assert events == [0, 1, 2, "failure"]


def test_invalid_configs_are_checked_before_missing_iterator_rows():
    events = []

    def values():
        events.append("read")
        yield None

    with pytest.raises(TypeError, match="cfg"):
        Pldt.parse(values(), cfg=object())
    assert events == []
