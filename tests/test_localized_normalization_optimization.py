"""Supported locale spelling and missing values survive internal name reuse."""
import pandas as pd
import pytest

from rstimes import Pddt, Pydt


@pytest.mark.parametrize("locale", ["fr-fr", "FR-fr", "fr_FR.UTF-8", "FR_fr@custom"])
def test_locale_case_separator_and_suffix_preserve_public_names(locale):
    value = Pydt(2024, 5, 7)
    assert value.month_name(locale) == "mai"
    assert value.weekday_name(locale) == "mardi"
    values = Pddt([value, None], name="calendar")
    for method, expected in (("month_name", "mai"), ("weekday_name", "mardi")):
        result = getattr(values, method)(locale)
        assert result[0] == expected and pd.isna(result[1])
        assert result.name == "calendar"


def test_locale_string_subclass_uses_its_stored_text():
    class Identifier(str):
        def lower(self):
            raise AssertionError("a real string's value needs no user normalization callback")

        def __str__(self):
            raise AssertionError("a real string's stored identifier must be used")

    assert Pydt(2024, 5, 7).month_name(Identifier("fr_FR")) == "mai"


@pytest.mark.parametrize("locale", [" fr_FR", "fr_FR ", "fr_ＦＲ"])
def test_locale_normalization_does_not_guess_new_identifiers(locale):
    with pytest.raises(ValueError, match="locale"):
        Pydt(2024, 5, 7).month_name(locale)
