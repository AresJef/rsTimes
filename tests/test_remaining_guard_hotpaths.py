"""Independent semantics beside the confirmed remaining performance guards."""
from datetime import datetime, timedelta
from fractions import Fraction
import calendar
import itertools

import numpy as np
import pytest

from rstimes import Delta, parse_to_epoch


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("value", [0, 1, -1, 2**31-1, 2**31, -(2**31), -(2**31)-1, 2**63-1, -(2**63), 2**80, -(2**80)])
def test_identity_epoch_projection_keeps_the_actual_integer(unit, value):
    result = parse_to_epoch(value, unit=unit, input_unit=unit)
    assert type(result) is int and result == value


def test_identity_epoch_does_not_reuse_a_numeric_subclass_or_bool():
    class Integer(int):
        pass

    result = parse_to_epoch(Integer(123), unit="s")
    assert type(result) is int and result == 123
    for value in [True, False, np.bool_(True)]:
        with pytest.raises(TypeError):
            parse_to_epoch(value, unit="s")
    assert parse_to_epoch(-1, unit="s", input_unit="ms") == -1
    assert parse_to_epoch(1, unit="ms", input_unit="s") == 1000
    with pytest.raises(OverflowError):
        parse_to_epoch(2**127, unit="s")


def fixed_ns(value):
    return (((value.days*24+value.hours)*60+value.minutes)*60+value.seconds)*1_000_000_000 + value.microseconds*1000 + value.nanoseconds


def test_fraction_head_preserves_exact_complete_binary_sum():
    numbers = [0.1, -0.1, 0.5, -0.5, 0.125, float.fromhex("0x0.0000000000001p-1022")]
    for a, b, c in itertools.product(numbers, numbers, [-1.5, 0.0, 0.5]):
        expected = round(Fraction.from_float(a)*86_400_000_000_000
                         + Fraction.from_float(b)*1_000_000_000
                         + Fraction.from_float(c))
        assert fixed_ns(Delta(days=a, seconds=b, nanoseconds=c)) == expected, (a, b, c)


@pytest.mark.parametrize("start", [datetime(2000, 3, 1), datetime(1900, 3, 1),
                                  datetime(2024, 12, 31), datetime(2024, 1, 1)])
@pytest.mark.parametrize("days", [-27, -1, 0, 1, 27])
def test_zero_year_month_calendar_path_matches_standard_days(start, days):
    delta = Delta(days=days)
    assert start + delta == start + timedelta(days=days)
    assert start - delta == start - timedelta(days=days)
    assert delta.apply_many([start, start]) == [start + timedelta(days=days)]*2


def test_calendar_relative_year_month_and_ns_carry_are_not_skipped():
    assert datetime(2024, 1, 31) + Delta(months=1) == datetime(2024, 2, 29)
    assert datetime(2024, 2, 29) - Delta(years=1) == datetime(2023, 2, 28)
    assert datetime(2024, 1, 1) + Delta(nanoseconds=-1000) == datetime(2023, 12, 31, 23, 59, 59, 999999)


def pddt_class():
    pytest.importorskip("pandas")
    from rstimes import Pddt
    return Pddt


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("size", [0, 1, 8, 9])
def test_small_query_snapshot_keeps_year_dtype_missing_and_boolean(unit, size):
    Pddt = pddt_class()
    x = Pddt.frommicroseconds([123456]*size).as_unit(unit, round_ok=True)
    assert x.year.tolist() == [1970]*size
    assert str(x.year.dtype) == "int32"
    assert x.is_long_year().tolist() == [True]*size
    missing = Pddt([None], unit=unit)
    assert np.isnan(missing.year[0])
    assert missing.is_long_year().tolist() == [False]


def test_second_storage_wide_year_keeps_int64():
    Pddt = pddt_class()
    ticks = 2**63-1
    ordinal = ticks//86400 + 719163

    def first(y):
        previous = y-1
        return previous*365 + previous//4-previous//100+previous//400 + 1

    low, high = 1, 400_000_000_000
    while low+1 < high:
        middle = (low+high)//2
        if first(middle) <= ordinal:
            low = middle
        else:
            high = middle
    x = Pddt.fromseconds([ticks], unit="s")
    assert x.year.tolist() == [low]
    assert str(x.year.dtype) == "int64"


def test_subclass_query_still_reads_the_live_source_once():
    Pddt = pddt_class()

    class Changing(Pddt):
        @property
        def asi8(self):
            self.calls = getattr(self, "calls", 0)+1
            return np.array([946684800000000 if self.calls == 1 else 978307200000000], dtype="int64")

    x = Changing.frommicroseconds([0])
    x.calls = 0
    assert x.year.tolist() == [2000]
    assert x.year.tolist() == [2001]
    assert x.calls == 2


def test_prepared_batch_calendar_matches_independent_month_then_duration():
    starts = [datetime(year, month, day, hour, 19, 41, 123456)
              for year, month, day in [(1900, 1, 31), (2000, 1, 31), (2024, 2, 29), (2024, 12, 31)]
              for hour in [0, 15, 23]]
    for years, months, days, hours in itertools.product([-1, 0, 1], [-13, -1, 0, 1, 13], [-28, -3, 0, 27, 28], [-25, -2, 0, 2, 25]):
        change = Delta(years=years, months=months, days=days, hours=hours)
        expected = []
        for source in starts:
            total = (source.year+years)*12 + source.month-1 + months
            year, month0 = divmod(total, 12)
            month = month0+1
            base = source.replace(year=year, month=month, day=min(source.day, calendar.monthrange(year, month)[1]))
            expected.append(base+timedelta(days=days, hours=hours))
        assert change.apply_many(starts) == expected, (years, months, days, hours)


@pytest.mark.parametrize("source_unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("output_unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("ticks", [2**65+12345, -(2**65+12345), 2**80+3, -(2**80+3), 2**126, -(2**126)])
def test_wide_epoch_unit_projection_matches_python_integer_floor(source_unit, output_unit, ticks):
    scales = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1000, "ns": 1}
    nanos = ticks*scales[source_unit]
    if not -(2**127) <= nanos < 2**127:
        with pytest.raises(OverflowError):
            parse_to_epoch(ticks, unit=output_unit, input_unit=source_unit)
    else:
        result = parse_to_epoch(ticks, unit=output_unit, input_unit=source_unit)
        assert type(result) is int and result == nanos//scales[output_unit]
