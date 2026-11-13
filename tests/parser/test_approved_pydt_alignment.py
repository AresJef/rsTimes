"""Parser-wide expectations from the approved Pydt integration decisions."""
from datetime import date, datetime

import numpy as np
import pytest

from rstimes import Pydt, parse, parse_str, parse_to_epoch


@pytest.mark.parametrize("default", [date(2024, 5, 7), datetime(2024, 5, 7, 23, 59),
    "2024-05-07", 1715040000, 1715040000.0, np.datetime64("2024-05-07")])
@pytest.mark.parametrize("entry", [parse, parse_str, Pydt.parse])
def test_default_is_prepared_to_native_ymd(entry, default):
    assert entry("02-29", default=default) == datetime(2024, 2, 29)
    assert entry("01-02-00", default=default, yearfirst=False) == datetime(2000, 1, 2)


@pytest.mark.parametrize("default", ["May 7", "12:30", "not a date", object()])
def test_nonempty_default_must_independently_provide_complete_date(default):
    with pytest.raises((ValueError, TypeError)):
        parse_str("2024-05-07", default=default)


def test_object_route_does_not_parse_unused_default():
    value = datetime(2024, 5, 7)
    assert parse(value, default=object()) is value


@pytest.mark.parametrize("text", ["0000-01-02", "2024-00-02", "2024-01-00", "2024-000",
    "2024-W01-0", "2024-W00-1", "2024W010", "2024W001"])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("entry", [parse_str, parse, Pydt.parse, parse_to_epoch])
def test_explicit_invalid_lower_bounds_never_fall_back(text, strict, entry):
    if text == "0000-01-02" and entry is parse_to_epoch:
        assert entry(text, default=datetime(2024, 5, 7), strict=strict) == -62167132800000000
    else:
        with pytest.raises(ValueError):
            entry(text, default=datetime(2024, 5, 7), strict=strict)


@pytest.mark.parametrize("name", ["yearfirst", "dayfirst", "ignoretz", "isoformat", "strict"])
@pytest.mark.parametrize("text", ["False", b"0", bytearray(b"1")])
@pytest.mark.parametrize("entry", [parse, parse_str, Pydt.parse])
def test_boolean_options_do_not_silently_accept_text(name, text, entry):
    with pytest.raises(TypeError):
        entry("2024-05-07", **{name: text})


@pytest.mark.parametrize("value", ["False", b"0", bytearray(b"1")])
def test_pydt_specific_boolean_switches_reject_text(value):
    start = Pydt(2024, 5, 7)
    with pytest.raises(TypeError, match="absolute"):
        start.diff("2024-05-08", "D", absolute=value)
    with pytest.raises(TypeError, match="naive"):
        start.tz_switch("UTC", base_tz="UTC", naive=value)
