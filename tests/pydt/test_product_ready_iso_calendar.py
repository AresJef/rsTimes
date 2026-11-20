"""ISO year/week shares native rules and matches independent stdlib dates."""
from datetime import date

import pytest

from rstimes import Pydt


def test_complete_400_year_cycle_matches_independent_stdlib_iso_answers():
    for ordinal in range(date(2000, 1, 1).toordinal(), date(2400, 1, 1).toordinal()):
        plain = date.fromordinal(ordinal)
        expected = plain.isocalendar()
        value = Pydt(plain.year, plain.month, plain.day)
        assert (value.isoyear(), value.isoweek()) == (expected.year, expected.week)


@pytest.mark.parametrize('year', [1, 4, 100, 400, 1600, 1900, 2000, 2020, 2099, 9999])
@pytest.mark.parametrize('month,day', [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5),
                                        (12, 27), (12, 28), (12, 29), (12, 30), (12, 31)])
def test_year_endpoints_and_52_or_53_week_transitions_match_stdlib(year, month, day):
    plain = date(year, month, day)
    value = Pydt(year, month, day, 23, 59, 59, 999999)
    expected = plain.isocalendar()
    assert (value.isoyear(), value.isoweek()) == (expected.year, expected.week)


def test_shared_iso_query_reads_actual_datetime_storage_without_subclass_hooks():
    class Business(Pydt):
        @property
        def year(self):
            raise AssertionError('public date hook must not be read')
        def isocalendar(self):
            raise AssertionError('business ISO hook must not be called')
    value = Business(2021, 1, 1)
    assert (value.isoyear(), value.isoweek()) == (2020, 53)
