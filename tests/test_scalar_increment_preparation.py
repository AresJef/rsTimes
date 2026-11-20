"""Scalar calendar contributions preserve cancellation and argument protocols."""
import numpy as np
import pytest


@pytest.fixture(params=["pddt", "pldt"])
def host(request):
    pytest.importorskip("pandas" if request.param == "pddt" else "polars")
    from rstimes import Pddt, Pldt
    return request.param, Pddt if request.param == "pddt" else Pldt


def ticks(value, kind):
    if kind == "pddt":
        return value.asi8.tolist()
    return [-(1 << 63) if v is None else v for v in value.to_physical()]


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("zone", [None, "UTC"])
@pytest.mark.parametrize("method", ["add", "sub"])
def test_all_scalar_roles_combine_before_calendar_move(host, unit, zone, method):
    kind, cls = host
    original = np.array(["2024-01-31T12:34:56.123456789", "NaT",
                         "2024-03-31T12:34:56.123456789"], dtype=f"datetime64[{unit}]")
    expected = np.array(
        ["2024-02-29T12:34:56.123456789", "NaT", "2024-04-30T12:34:56.123456789"]
        if method == "add" else
        ["2023-12-31T12:34:56.123456789", "NaT", "2024-02-29T12:34:56.123456789"],
        dtype=original.dtype)
    source = cls(original, tz=zone, name="events")
    before = ticks(source, kind)
    result = getattr(source, method)(years=1, quarters=2, months=-17, weeks=1,
                                    days=-7, hours=5, minutes=-300, seconds=3,
                                    milliseconds=-3000, microseconds=1, nanoseconds=-1000)
    assert ticks(result, kind) == expected.view("i8").tolist()
    assert ticks(source, kind) == before
    assert result.name == "events" and result.dtype == source.dtype


@pytest.mark.parametrize("method", ["add", "sub"])
def test_wide_scalar_components_cancel_without_intermediate_narrowing(host, method):
    kind, cls = host
    maximum = (1 << 63) - 1
    years, weeks, hours, micros = maximum // 12, maximum // 7, maximum // 60, maximum // 1000
    source = cls(["2024-02-29T12:34:56.123456789", None], unit="ns", name="events")
    result = getattr(source, method)(years=years, months=-12 * years,
                                    weeks=weeks, days=-7 * weeks,
                                    hours=hours, minutes=-60 * hours,
                                    microseconds=micros, nanoseconds=-1000 * micros)
    assert ticks(result, kind) == ticks(source, kind)
    assert result.dtype == source.dtype and result.name == "events"


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
@pytest.mark.parametrize("data", [[], [None], [None, None]])
def test_empty_and_missing_sources_do_not_evaluate_unused_calendar_results(host, unit, data):
    kind, cls = host
    source = cls(data, unit=unit, name="events")
    result = source.add(years=(1 << 63) - 1, hours=(1 << 63) - 1)
    assert ticks(result, kind) == ticks(source, kind)
    assert result.dtype == source.dtype and result.name == "events"


def test_scalar_integer_protocol_is_read_once_before_row_work(host):
    kind, cls = host

    class Once:
        calls = 0

        def __index__(self):
            self.calls += 1
            assert self.calls == 1
            return 1

    days = Once()
    source = cls(["2024-01-31", "2024-02-29"], unit="ns")
    result = source.add(days=days)
    expected = np.array(["2024-02-01", "2024-03-01"], dtype="datetime64[ns]")
    assert ticks(result, kind) == expected.view("i8").tolist()
    assert days.calls == 1
