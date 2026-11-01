"""Default-name adaptation preserves saved spelling and stored date fields."""

from datetime import datetime

import pytest

from rstimes import Pydt


@pytest.mark.parametrize("token", ["may", "May", "MAY"])
def test_ascii_month_name_uses_the_complete_default_rule(token):
    assert Pydt(2024, 5, 7).is_month(token) is True
    assert Pydt(2024, 6, 7).is_month(token) is False


@pytest.mark.parametrize("token", ["mAy", "", "unknown", "M" * 100])
def test_unknown_and_unsaved_spellings_do_not_gain_an_ascii_exception(token):
    with pytest.raises(ValueError, match="Pydt.is_month"):
        Pydt(2024, 5, 7).is_month(token)


@pytest.mark.parametrize("year,expected", [(1900, 28), (2000, 29), (2024, 29), (2100, 28)])
def test_month_property_reads_real_stored_calendar_fields(year, expected):
    class Child(Pydt):
        year = property(lambda self: 2000)
        month = property(lambda self: 1)

    value = Child(year, 2, 1)
    assert value.days_in_month == expected
    assert Pydt.days_in_month.fget(datetime(year, 2, 1)) == expected
