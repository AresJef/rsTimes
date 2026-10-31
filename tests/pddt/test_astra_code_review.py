"""Contract regressions for the independent CR01/02/03/06/07 review.

Expected values come from explicit callbacks, UTC integer arithmetic and the
approved metadata/type/error contract, not from another rstimes entry point.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from rstimes import Delta, Pddt


@pytest.mark.parametrize("base", [Delta, timedelta, pd.Timedelta],
                         ids=["Delta", "timedelta", "pandas-Timedelta"])
@pytest.mark.parametrize("direction", ["add", "sub", "radd"])
@pytest.mark.parametrize("container", [list, tuple, lambda x: np.array(x, dtype=object), iter],
                         ids=["list", "tuple", "ndarray", "iterator"])
@pytest.mark.parametrize("mixed", [False, True], ids=["dynamic", "mixed"])
def test_cr02_column_obeys_real_operand_protocol(base, direction, container, mixed):
    events = []

    class Business(base):
        def __radd__(self, value):
            events.append("radd")
            return value + timedelta(days=2)

        def __rsub__(self, value):
            events.append("rsub")
            return value - timedelta(days=2)

        def __add__(self, value):
            events.append("add")
            return value + timedelta(days=2)

    source = Pddt(["2024-01-01", "2024-01-03"], unit="s", name="dates")
    values = [base(days=1) if mixed else Business(days=1), Business(days=1)]
    other = container(values)
    result = source + other if direction == "add" else source - other if direction == "sub" else other + source
    sign = -1 if direction == "sub" else 1
    expected = [1704067200 + sign * (1 if mixed else 2) * 86400,
                1704240000 + sign * 2 * 86400]
    assert result.asi8.tolist() == expected
    assert result.unit == "s" and result.name == "dates"
    assert events == [{"add": "radd", "sub": "rsub", "radd": "add"}[direction]] * (1 if mixed else 2)


def test_cr02_column_preserves_original_failure_and_stops_callbacks():
    marker = RuntimeError("the business rule refuses this date")
    events = []

    class Refusing(Delta):
        def __radd__(self, value):
            events.append(value.day)
            raise marker

    source = Pddt(["2024-01-01", "2024-01-03"])
    with pytest.raises(RuntimeError) as caught:
        source + iter([Refusing(days=1), Refusing(days=1)])
    assert caught.value is marker and events == [1]


def test_cr02_dynamic_rows_preserve_nanoseconds_and_native_neighbors():
    events = []

    class Business(Delta):
        def __radd__(self, value):
            events.append(value.nanosecond)
            return value + pd.Timedelta(2, "ns")

    source = Pddt(np.array([1, 3, -2**63], dtype="i8").view("datetime64[ns]"), name="fine")
    result = source + [Delta(), Business(days=1), Delta()]
    assert result.asi8.tolist() == [1, 5, -2**63]
    assert result.name == "fine" and result.unit == "ns" and events == [3]


@pytest.mark.parametrize("direction", ["add", "sub", "radd"])
def test_cr02_pandas_duration_subclass_keeps_its_protocol_and_nanoseconds(direction):
    events = []

    class Fine(pd.Timedelta):
        def __radd__(self, value):
            events.append("radd")
            return value + pd.Timedelta(2, unit="ns")

        def __rsub__(self, value):
            events.append("rsub")
            return value - pd.Timedelta(2, unit="ns")

        def __add__(self, value):
            events.append("add")
            return value + pd.Timedelta(2, unit="ns")

    source = Pddt(np.array([10, 20], dtype="i8").view("datetime64[ns]"))
    operand = [pd.Timedelta(1, unit="ns"), Fine(1, unit="ns")]
    result = source + operand if direction == "add" else source - operand if direction == "sub" else operand + source
    assert result.asi8.tolist() == ([9, 18] if direction == "sub" else [11, 22])
    assert result.unit == "ns"
    assert events == [{"add": "radd", "sub": "rsub", "radd": "add"}[direction]]


@pytest.mark.parametrize("reflected", [False, True])
def test_cr02_notimplemented_keeps_the_corresponding_direction(reflected):
    events = []

    class Business(Delta):
        def __add__(self, other):
            events.append("add")
            return NotImplemented

        def __radd__(self, other):
            events.append("radd")
            return NotImplemented

    source = Pddt(["2024-01-01"], unit="s")
    if reflected:
        result = [Business(days=1)] + source
        assert result.asi8.tolist() == [1704153600] and events == ["add"]
    else:
        with pytest.raises(TypeError, match="NotImplemented"):
            source + [Business(days=1)]
        assert events == ["radd"]


def test_cr02_special_descriptor_bypasses_instance_display_aliases():
    events = []

    class Rule:
        def __get__(self, instance, owner):
            def run(value):
                events.append(value.day)
                return value + timedelta(days=2)
            return run

    class Business(Delta):
        __radd__ = Rule()

        def __getattribute__(self, name):
            if name == "__radd__":
                raise AssertionError("special arithmetic must not use instance lookup")
            return super().__getattribute__(name)

    source = Pddt(["2024-01-01"], unit="s")
    assert (source + [Business(days=1)]).asi8.tolist() == [1704240000]
    assert events == [1]


def test_cr02_dynamic_result_cannot_silently_change_storage_unit():
    class Business(Delta):
        def __radd__(self, value):
            return value + pd.Timedelta(1, "ns")

    source = Pddt(["2024-01-01"], unit="us")
    with pytest.raises(ValueError, match="unit"):
        source + [Business()]


def test_cr02_per_call_qualification_observes_a_live_class_edit():
    events = []

    class Child(Delta):
        pass

    def updated(self, value):
        events.append(value.day)
        return value + timedelta(days=2)

    def operands():
        yield Child(days=1)
        Child.__radd__ = updated
        yield Child(days=1)

    source = Pddt(["2024-01-01", "2024-01-03"], unit="s")
    result = source + operands()
    assert result.asi8[-1] == 1704412800 and events == [3]


@pytest.mark.parametrize("factory", ["fromdatetime", "fromisoformat", "strptime", "combine"])
@pytest.mark.parametrize("count", [0, 1])
@pytest.mark.parametrize("hours", [0, 8])
def test_cr07_scalar_factory_keeps_source_zone_even_when_empty(factory, count, hours):
    zone = timezone(timedelta(hours=hours))
    source = datetime(2024, 1, 1, 12, tzinfo=zone)
    kwargs = dict(size=count, unit="us", name="dates")
    if factory == "fromdatetime":
        result = Pddt.fromdatetime(source, **kwargs)
    elif factory == "fromisoformat":
        result = Pddt.fromisoformat(source.isoformat(), **kwargs)
    elif factory == "strptime":
        result = Pddt.strptime(source.strftime("%Y-%m-%dT%H:%M:%S%z"), "%Y-%m-%dT%H:%M:%S%z", **kwargs)
    else:
        result = Pddt.combine(source.date(), time(12, tzinfo=zone), **kwargs)
    assert len(result) == count and result.tz == zone
    assert result.unit == "us" and result.name == "dates"


@pytest.mark.parametrize("count", [0, 1])
@pytest.mark.parametrize("factory", ["fromdatetime", "combine"])
def test_cr07_region_source_and_explicit_target_priority(factory, count):
    source = datetime(2024, 1, 1, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    if factory == "fromdatetime":
        result = Pddt.fromdatetime(source, size=count)
        override = Pddt.fromdatetime(source, size=count, tz=timezone.utc)
    else:
        result = Pddt.combine(source.date(), source.timetz(), size=count)
        override = Pddt.combine(source.date(), source.timetz(), size=count, tz=timezone.utc)
    assert result.tz == source.tzinfo and override.tz == timezone.utc


@pytest.mark.parametrize("frequency", ["D", pd.DateOffset(days=1), pd.offsets.BusinessHour()],
                         ids=["native", "delegated-offset", "delegated-business"])
@pytest.mark.parametrize("unit,factor", [("s", 1), ("ms", 1000), ("us", 1000000), ("ns", 1000000000)])
def test_cr01_local_coordinate_can_be_finer_than_final_utc_unit(frequency, unit, factor):
    zone = timezone(timedelta(microseconds=1))
    source = datetime(2024, 1, 1, 9, 0, 0, 1, tzinfo=zone)
    result = Pddt.date_range(source, periods=2, freq=frequency, unit=unit)
    step = 3600 if type(frequency) is pd.offsets.BusinessHour else 86400
    assert result.asi8.tolist() == [1704099600 * factor, (1704099600 + step) * factor]
    assert result.unit == unit and result.tz == zone


@pytest.mark.parametrize("normalize", [False, True])
@pytest.mark.parametrize("frequency", ["D", pd.DateOffset(days=1)])
def test_cr01_real_inexact_utc_endpoint_still_rejected(frequency, normalize):
    source = datetime(2024, 1, 1, 9, 0, 0, 2, tzinfo=timezone(timedelta(microseconds=1)))
    with pytest.raises(ValueError, match="unit"):
        Pddt.date_range(source, periods=0, freq=frequency, unit="s", normalize=normalize)


@pytest.mark.parametrize("location", [0, 1, 2])
@pytest.mark.parametrize("case", ["parse", "bool", "days", "ordinal"])
def test_cr03_bulk_failure_keeps_known_public_position(case, location):
    source = Pddt(["2024-01-01"] * 3)
    if case in ("parse", "bool"):
        values = ["2024-01-01"] * 3
        values[location] = "bad" if case == "parse" else True
        run = lambda: source.diff(values, "D")
        field = "dtobj"
        error = ValueError if case == "parse" else TypeError
    else:
        values = np.array([1, 1, 1], dtype="u8")
        values[location] = 2**63
        run = (lambda: source.add(days=values)) if case == "days" else (lambda: Pddt.fromordinal(values))
        field = case
        error = OverflowError
    with pytest.raises(error) as caught:
        run()
    text = str(caught.value) + " ".join(getattr(caught.value, "__notes__", []))
    assert f"{field}[{location}]" in text


def test_cr03_iterator_read_error_keeps_identity_and_unread_position():
    marker = RuntimeError("the input reader failed")

    def targets():
        yield "2024-01-01"
        raise marker

    with pytest.raises(RuntimeError) as caught:
        Pddt(["2024-01-01"] * 2).diff(targets(), "D")
    assert caught.value is marker
    text = str(marker) + " ".join(getattr(marker, "__notes__", []))
    assert "reading dtobj[1]" in text


def test_cr03_scalar_read_error_keeps_identity_and_parameter():
    marker = RuntimeError("the numeric source refused conversion")

    class Source:
        def __index__(self):
            raise marker

    with pytest.raises(RuntimeError) as caught:
        Pddt(["2024-01-01"]).diff(Source(), "D")
    assert caught.value is marker
    assert "dtobj" in " ".join(getattr(marker, "__notes__", []))


@pytest.mark.parametrize("displayed", [str, pd.DatetimeIndex])
def test_cr06_display_class_does_not_replace_actual_iterable_type(displayed):
    class Dates:
        @property
        def __class__(self):
            return displayed

        def __iter__(self):
            yield "2024-01-01"

    assert Pddt(Dates(), unit="s").asi8.tolist() == [1704067200]


def test_cr06_dispatch_does_not_execute_display_class_property():
    class Dates:
        @property
        def __class__(self):
            raise AssertionError("display class must not be queried")

        def __iter__(self):
            yield "2024-01-01"

    assert Pddt(Dates(), unit="s").asi8.tolist() == [1704067200]


def test_cr07_empty_combine_retains_real_scalar_nanosecond_resolution():
    clock = pd.Timestamp("2024-01-01 12:00:00.000000001", tz="UTC")
    result = Pddt.combine(clock.date(), clock, size=0)
    assert result.unit == "ns" and result.tz == timezone.utc and len(result) == 0


@pytest.mark.parametrize("operation", ["to_day", "replace", "add", "parse", "ordinal", "strptime", "range"])
def test_cr06_new_date_result_requires_actual_subclass(operation):
    class Child(Pddt):
        wrong = False

        def __new__(cls, *args, **kwargs):
            return Facade() if cls.wrong else super().__new__(cls, *args, **kwargs)

    class Facade:
        @property
        def __class__(self):
            return Child

    source = Child(["2024-01-01"])
    Child.wrong = True
    calls = {"to_day": lambda: source.to_day(1), "replace": lambda: source.pddt.replace(day=2),
             "add": lambda: source + timedelta(days=1), "parse": lambda: Child.parse(["2024-01-02"]),
             "ordinal": lambda: Child.fromordinal(738887, size=1),
             "strptime": lambda: Child.strptime("2024-01-02", "%Y-%m-%d", size=1),
             "range": lambda: Child.date_range("2024-01-01", periods=2)}
    with pytest.raises(TypeError, match="subclass"):
        calls[operation]()
