"""P04/P14/P15/P17: public numeric roles and wide native calendar buckets."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from rstimes import Pydt


class Index:
    def __init__(self, value):
        self.value = value
        self.reads = 0

    def __index__(self):
        self.reads += 1
        return self.value


@pytest.mark.parametrize("name", ["year", "month", "day", "hour", "minute", "second", "microsecond"])
@pytest.mark.parametrize("bad", [True, np.bool_(False), 1.0, np.float64(1.0)])
def test_public_calendar_fields_are_integer_only(name, bad):
    with pytest.raises(TypeError):
        Pydt(**{name: bad})
    with pytest.raises(TypeError):
        Pydt(2024, 5, 7).replace(**{name: bad})


@pytest.mark.parametrize("name,value", [("year", 2024), ("month", 5), ("day", 7), ("hour", 12), ("minute", 30), ("second", 1), ("microsecond", 100)])
def test_constructor_reads_index_once(name, value):
    value = Index(value)
    result = Pydt(**{name: value})
    assert value.reads == 1
    assert getattr(result, name) == value.value


@pytest.mark.parametrize("call", [
    lambda v: Pydt.frommicroseconds(v), lambda v: Pydt.fromordinal(v),
    lambda v: Pydt.fromdayofyear(2024, v), lambda v: Pydt.fromdayofyear(v, 1),
    lambda v: Pydt.fromisocalendar(2024, v, 1),
    lambda v: Pydt.fromisocalendar(v, 1, 1),
    lambda v: Pydt.fromisocalendar(2024, 1, v),
    lambda v: Pydt(2024, 5, 7).fsp(v),
    lambda v: Pydt(2024, 5, 7).to_month(v),
    lambda v: Pydt(2024, 5, 7).leap_bt_year(v),
    lambda v: Pydt(2024, 5, 7).is_year(v),
    lambda v: Pydt(2024, 5, 7).to_curr_year(month=v),
    lambda v: Pydt(2024, 5, 7).to_curr_weekday(weekday=v),
])
@pytest.mark.parametrize("bad", [1.0, np.float32(1.0), True, np.bool_(False)])
def test_integer_factory_and_selector_roles_reject_coercion(call, bad):
    with pytest.raises(TypeError):
        call(bad)


@pytest.mark.parametrize("name", ["years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds", "milliseconds", "microseconds"])
@pytest.mark.parametrize("bad", [1.0, True, np.bool_(False)])
def test_named_relative_fields_are_integer_only(name, bad):
    value = Pydt(2024, 5, 7)
    for operation in (value.add, value.sub):
        with pytest.raises(TypeError):
            operation(**{name: bad})


def test_accepted_index_and_float_duration_roles_remain_distinct():
    from rstimes import Delta
    number = Index(1)
    assert Pydt(2024, 5, 7).add(days=number) == datetime(2024, 5, 8)
    assert number.reads == 1
    assert Pydt(2024, 5, 7) + Delta(hours=1.5) == datetime(2024, 5, 7, 1, 30)


@pytest.mark.parametrize("fold", [0, 1, False, True, np.bool_(True), np.int64(1)])
def test_fold_is_the_explicit_boolean_exception(fold):
    value = Pydt(2024, 11, 3, 1, 30, tzinfo="America/New_York", fold=fold)
    assert value.fold == int(fold)
    assert value.replace(fold=fold).fold == int(fold)


@pytest.mark.parametrize("fold,error", [(None, TypeError), (1.0, TypeError), (2, ValueError)])
def test_invalid_constructor_fold(fold, error):
    with pytest.raises(error):
        Pydt(2024, 5, 7, fold=fold)


def test_properties_are_readonly_and_weekday_remains_standard_method():
    value = Pydt(2024, 2, 29)
    assert value.is_leap_year is True
    assert value.day_of_year == 60
    assert value.days_in_month == 29
    assert value.weekday() == 3
    for name in ("is_leap_year", "day_of_year", "days_in_month"):
        with pytest.raises(AttributeError):
            setattr(value, name, 1)
        with pytest.raises(TypeError):
            getattr(value, name)()


@pytest.mark.parametrize("unit", ["Y", "Q", "M"])
def test_calendar_diff_can_use_utc_year_zero_and_ten_thousand(unit):
    early = Pydt(1, 1, 1, tzinfo=timezone(timedelta(hours=14)))
    late = Pydt(9999, 12, 31, 23, tzinfo=timezone(-timedelta(hours=14)))
    assert early.diff(early, unit) == 0
    assert late.diff(late, unit) == 0
    assert early.diff(Pydt(1, 1, 1, tzinfo=timezone.utc), unit) == -1
    assert late.diff(Pydt(9999, 12, 31, 23, tzinfo=timezone.utc), unit) == 1


def test_narrow_date_output_and_gap_checks_remain_real():
    with pytest.raises(OverflowError):
        Pydt(1, 1, 1).sub(days=1)
    with pytest.raises(ValueError):
        Pydt(2024, 3, 10, 2, 30, tzinfo=ZoneInfo("America/New_York"))
    value = Pydt(2024, 3, 10, 1, 30, tzinfo="America/New_York")
    with pytest.raises(ValueError):
        value.replace(hour=2)


def test_callback_error_identity_and_subclass_construction_are_retained():
    error = RuntimeError("index sentinel")
    class Broken:
        def __index__(self):
            raise error
    with pytest.raises(RuntimeError) as caught:
        Pydt(2024, month=Broken())
    assert caught.value is error
    events = []
    class Child(Pydt):
        def __new__(cls, *args, **kwargs):
            events.append("new")
            return super().__new__(cls, *args, **kwargs)
        def __init__(self, *args, **kwargs):
            self.tag = "child"
            events.append("init")
    number = Index(2024)
    value = Child(number, 5, 7)
    assert type(value) is Child and value.tag == "child"
    assert number.reads == 1 and events == ["new", "init"]


def test_error_context_names_actual_numeric_and_reflected_entries():
    with pytest.raises(ValueError) as caught:
        Pydt.fromseconds(float("nan"))
    assert "fromseconds" in str(caught.value) and "fromdatetime64" not in str(caught.value)
    with pytest.raises(OverflowError) as caught:
        Pydt(9999, 12, 31).__radd__(timedelta.max)
    assert "__radd__" in str(caught.value)
    with pytest.raises(ValueError) as caught:
        Pydt(2024, 5, 7).diff(Pydt(2024, 5, 7), "ns")
    assert " or ns" not in str(caught.value)


def test_unknown_numeric_text_uses_the_selector_name_error():
    value = Pydt(2024, 5, 7)
    with pytest.raises(ValueError, match="unknown month"):
        value.to_curr_year(month="1")
    with pytest.raises(ValueError, match="unknown weekday"):
        value.to_curr_weekday(weekday="1")


@pytest.mark.parametrize("call", [Pydt.fromseconds, Pydt.fromtimestamp, Pydt.utcfromtimestamp])
@pytest.mark.parametrize("bad", [True, np.bool_(False)])
def test_boolean_is_not_epoch_seconds(call, bad):
    with pytest.raises(TypeError):
        call(bad)
