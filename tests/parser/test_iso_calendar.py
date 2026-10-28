"""Protect ordinal-to-month conversion at every day of common/leap years."""
from datetime import datetime, timedelta
import pytest
from rstimes import parse_str as parse

@pytest.mark.parametrize('year', [1900, 2000])
def test_all_iso_ordinal_days(year):
    first = datetime(year, 1, 1)
    last = datetime(year, 12, 31)
    for day in range(1, 367):
        expected = min(first + timedelta(days=day-1), last)
        assert parse(f'{year}-{day:03}') == expected
