"""F21: CLDR names use real fields; local-zone discovery is lazy and retryable."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from rstimes import Pydt


def test_all_preexisting_locale_names_match_frozen_supported_values():
    reference = json.loads((Path(__file__).parent / "data/localization-baseline-final07.json").read_text())
    months = [Pydt(2024, month, 1) for month in range(1, 13)]
    weekdays = [Pydt(2024, 1, day) for day in range(1, 8)]
    for locale, expected in reference.items():
        actual = [value.month_name(locale) for value in months]
        actual += [value.weekday_name(locale) for value in weekdays]
        assert actual == expected, locale


@pytest.mark.parametrize("locale, month, weekday", [(None, "May", "Tuesday"),
                                                  ("en_US", "May", "Tuesday"),
                                                  ("zh_CN", "五月", "星期二"),
                                                  ("tr_TR", "Mayıs", "Salı")])
def test_names_use_real_fields_without_overridden_date_or_properties(locale, month, weekday):
    class Child(Pydt):
        month = property(lambda self: 12)
        def date(self):
            raise AssertionError("names must not construct a date through this method")
        def weekday(self):
            return 6
    value = Child(2024, 5, 7)
    assert value.month_name(locale) == month
    assert value.weekday_name(locale) == weekday


@pytest.mark.parametrize("locale", ["", "unknown_locale", "en_UNKNOWN_REGION"])
def test_unknown_locale_is_an_explicit_value_error(locale):
    with pytest.raises(ValueError, match="locale"):
        Pydt(2024, 1, 1).month_name(locale)


@pytest.mark.parametrize("locale", [1, False, object(), [], {}])
def test_locale_accepts_strings_or_none_only(locale):
    with pytest.raises(TypeError, match="locale"):
        Pydt(2024, 1, 1).weekday_name(locale)


def test_no_babel_import_and_local_first_success_is_cached():
    code = r'''
import builtins, os, sys
original = builtins.__import__
def checked(name, *args, **kwargs):
    if name == "babel" or name.startswith("babel."):
        raise AssertionError("Babel must not be imported")
    return original(name, *args, **kwargs)
builtins.__import__ = checked
os.environ["TZ"] = "Unknown/Unavailable"
import rstimes
from rstimes._localization import local_timezone
assert rstimes.Pydt(2024, 5, 7).month_name("zh_CN") == "五月"
rstimes.Pydt(2024, 1, 1, tzinfo="Asia/Shanghai")
try:
    local_timezone()
except ValueError:
    pass
else:
    raise AssertionError("invalid explicit TZ must fail")
os.environ["TZ"] = "Asia/Shanghai"
first = local_timezone()
assert first.key == "Asia/Shanghai"
os.environ["TZ"] = "America/New_York"
assert local_timezone() is first
assert not any(name == "babel" or name.startswith("babel.") for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr

