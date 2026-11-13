"""Approved safety differences with explicit expected errors; no unsafe oracle calls."""
from datetime import date
import pytest
from rstimes.parser import Configs, parse_str as parse
from rstimes.errors import ParseError, ConfigError


@pytest.mark.parametrize("text", ["9"*40, "12."+"9"*40+"h"])
def test_numeric_accumulation_overflow_is_safe(text):
    with pytest.raises(OverflowError) as observed:
        parse(text, default=date(2024,1,1))
    assert observed.value.__cause__ is None


def test_timezone_representable_total_uses_config_range_error():
    with pytest.raises(ConfigError):
        Configs().add_tzoffset("large", hours=2**30)


@pytest.mark.parametrize("state,error", [((),ValueError), (None,TypeError)])
def test_malformed_state_rejects_before_indexing(state,error):
    with pytest.raises(error):
        Configs().__setstate__(state)



