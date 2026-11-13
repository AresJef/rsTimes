"""Clock conversion overflow must fail without changing date heuristics."""
from datetime import datetime

import pytest

from rstimes.errors import ParseError
from rstimes.parser import parse_str as parse


DEFAULT = datetime(2001, 2, 3)


@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("prefix", ["", "2024-01-02 "])
@pytest.mark.parametrize("clock", [
    "1:2147483648",
    "1:4294967296",
    "1:4294967297",
    "1:00:4294967297",
])
def test_clock_integral_overflow_has_explicit_cause(clock, prefix, isoformat):
    with pytest.raises(OverflowError) as observed:
        parse(prefix + clock, default=DEFAULT, isoformat=isoformat)
    assert observed.value.__cause__ is None


@pytest.mark.parametrize("isoformat", [False, True])
def test_explicit_large_minute_clamps_without_calendar_reinterpretation(isoformat):
    assert parse('1:2147483647', default=DEFAULT, isoformat=isoformat) == datetime(2001, 2, 3, 1, 59)


@pytest.mark.parametrize('unit', ['h', 'm', 's'])
@pytest.mark.parametrize('isoformat', [False, True])
def test_explicit_clock_overflow_is_not_a_compact_calendar(unit, isoformat):
    with pytest.raises(OverflowError) as observed:
        parse('4294967297' + unit, default=DEFAULT, isoformat=isoformat)
    assert observed.value.__cause__ is None


@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("clock", ["1:02:03", "1h02m03s"])
def test_normal_clock_conversion_survives(clock, isoformat):
    assert parse(clock, default=DEFAULT, isoformat=isoformat) == datetime(2001, 2, 3, 1, 2, 3)
