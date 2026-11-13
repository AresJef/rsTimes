"""Protect the changed ISO query and NumPy constructor boundaries."""
from datetime import date, timedelta
import numpy as np
from rstimes import Pydt


def test_iso_scalar_queries_match_standard_calendar_boundaries():
    # Include century exceptions, ISO 53-week years and the datetime endpoints.
    for year in (1, 2, 4, 100, 400, 1900, 1999, 2000, 2020, 2021, 2024, 9999):
        first = date(year, 1, 1)
        last = date(year, 12, 31)
        for days in range((last - first).days + 1):
            day = first + timedelta(days=days)
            value = Pydt(day.year, day.month, day.day)
            expected = day.isocalendar()
            assert (value.isoyear(), value.isoweek()) == (expected.year, expected.week)


def test_numpy_factory_retains_the_parsers_keyword_constructor_shape():
    class Child(Pydt):
        calls = []
        def __new__(cls, *args, **kwargs):
            cls.calls.append((args, kwargs.copy()))
            return super().__new__(cls, *args, **kwargs)

    value = Child.fromdatetime64(np.datetime64('2024-05-07T12:30:45.123456789'))
    assert type(value) is Child and value.microsecond == 123456
    assert Child.calls == [((), dict(year=2024, month=5, day=7, hour=12,
        minute=30, second=45, microsecond=123456, tzinfo=None, fold=0))]


def test_local_timezone_resolves_at_first_use_and_then_stays_cached():
    import subprocess
    import sys
    code = """import os
os.environ['TZ'] = 'UTC'
import rstimes
os.environ['TZ'] = 'America/New_York'
from rstimes.pydt import _local_timezone
assert str(_local_timezone()) == 'America/New_York'
os.environ['TZ'] = 'UTC'
assert str(_local_timezone()) == 'America/New_York'
"""
    subprocess.run([sys.executable, '-P', '-c', code], check=True)
