"""PR-002: integer epoch output keeps wide Gregorian intermediates."""
from datetime import date

import numpy as np
import pytest
from rstimes import Pydt, parse_to_epoch


def january_ordinal(year):
    before = year - 1
    return 365 * before + before // 4 - before // 100 + before // 400 + 1


def expected_epoch(tick, code, multiple, target):
    months = tick * multiple * (12 if code == "Y" else 1)
    year, month = 1970 + months // 12, months % 12 + 1
    lengths = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    ordinal = january_ordinal(year) + sum(lengths[:month - 1])
    nanos = (ordinal - 719163) * 86_400_000_000_000
    return nanos // {"s": 1_000_000_000, "us": 1000, "ns": 1}[target]


@pytest.mark.parametrize("code,multiple", (("Y", 1), ("M", 1), ("Y", 3), ("M", 7)))
@pytest.mark.parametrize("tick", (-2**63 + 1, -1970, -1, 0, 1, 2**63 - 1))
@pytest.mark.parametrize("unit", ("s", "us", "ns"))
def test_full_non_nat_numpy_year_month_source_to_integer(tick, code, multiple, unit):
    source = np.datetime64(tick, (str(multiple) if multiple != 1 else "") + code)
    actual = parse_to_epoch(source, unit=unit)
    assert type(actual) is int and actual == expected_epoch(tick, code, multiple, unit)


def test_maximum_month_tick_has_independent_literal_answer():
    assert parse_to_epoch(np.datetime64(2**63 - 1, "M"), unit="ns") == 24255125720430699259296000000000000


@pytest.mark.parametrize("code", ("Y", "M"))
def test_true_wide_epoch_overflow_is_still_rejected(code):
    with pytest.raises(OverflowError):
        parse_to_epoch(np.datetime64(2**63 - 1, "2147483647" + code), unit="ns")


@pytest.mark.parametrize("code", ("Y", "M", "3Y", "7M"))
def test_numpy_nat_stays_reserved_and_rejected(code):
    with pytest.raises(ValueError, match="NaT"):
        parse_to_epoch(np.datetime64("NaT", code), unit="ns")


def test_wide_integer_output_does_not_expand_pydt_capacity():
    with pytest.raises(OverflowError):
        Pydt.fromdatetime64(np.datetime64(2**63 - 1, "M"))


@pytest.mark.parametrize("year", (1, 4, 100, 400, 1900, 1970, 2000, 2024, 9999))
def test_independent_integer_reference_agrees_with_standard_calendar(year):
    assert january_ordinal(year) == date(year, 1, 1).toordinal()
