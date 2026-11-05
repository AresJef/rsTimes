"""Default-name adaptation preserves saved spelling and stored date fields."""

from datetime import datetime

import pytest

from rstimes import Configs, Pydt


@pytest.mark.parametrize("word,month", [("May", 5), ("五月", 5), ("haziran", 6)])
def test_default_calendar_view_preserves_literal_language_meanings(word, month):
    assert Pydt(2024, month, 7).is_month(word) is True
    assert Pydt(2024, month % 12 + 1, 7).is_month(word) is False


@pytest.mark.parametrize("word", ["monday", "Monday", "MONDAY"])
def test_default_weekday_view_preserves_saved_spellings(word):
    assert Pydt(2024, 5, 6).is_weekday(word) is True
    assert Pydt(2024, 5, 7).is_weekday(word) is False


def test_individual_configs_cannot_extend_default_calendar_queries():
    cfg = Configs()
    cfg.add_month("certainlycustommonth", 5)
    assert cfg.month["certainlycustommonth"] == 5
    with pytest.raises(ValueError, match="Pydt.is_month"):
        Pydt(2024, 5, 7).is_month("certainlycustommonth")


def test_real_unicode_subclass_does_not_use_its_displayed_class():
    class Name(str):
        @property
        def __class__(self):
            return int

        def __str__(self):
            raise AssertionError("a real saved name must not be stringified")

    assert Pydt(2024, 5, 7).is_month(Name("May")) is True
    assert Pydt(2024, 6, 7).is_month(Name("May")) is False


def test_false_unicode_display_keeps_the_real_integer_protocol():
    class Number:
        @property
        def __class__(self):
            return str

        def __index__(self):
            return 5

    assert Pydt(2024, 5, 7).is_month(Number()) is True


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


@pytest.mark.parametrize("year", [1900, 2000, 2024, 2100])
@pytest.mark.parametrize("month", range(1, 13))
def test_direct_year_position_matches_the_standard_library(year, month):
    source = datetime(year, month, 1)
    assert Pydt(year, month, 1).day_of_year == source.timetuple().tm_yday


@pytest.mark.parametrize("locale", ["fr", "fr_FR", "fr-fr", "FR_fr", "fr_FR.UTF-8", "fr_FR@calendar=gregorian"])
def test_locale_stack_key_preserves_existing_alias_encoding_and_modifier_rules(locale):
    value = Pydt(2024, 5, 7)
    assert value.month_name(locale) == "mai"
    assert value.weekday_name(locale) == "mardi"


@pytest.mark.parametrize("locale", ["", "FR" * 40, "fŕ_FR", "fr_FR_invalid"])
def test_unknown_locale_is_not_accepted_by_a_short_key(locale):
    with pytest.raises(ValueError, match="Pydt.month_name"):
        Pydt(2024, 5, 7).month_name(locale)
