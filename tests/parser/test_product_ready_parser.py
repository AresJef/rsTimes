"""ProductReady regressions use independent expected values at public exits."""
from datetime import datetime, timedelta
from fractions import Fraction

import pytest

from rstimes import Pydt, parse, parse_str, parse_to_epoch


DECIMAL_CLOCK_VALUES = [
    "0.5", "0.5" + "0" * 40,
    "0.123456789012345678901234567890",
    "0." + "0" * 40 + "1", "0." + "9" * 80,
    "0." + "1234567890" * 100,
]


@pytest.mark.parametrize("value", DECIMAL_CLOCK_VALUES)
@pytest.mark.parametrize("clock_unit,factor", [("h", 3_600_000_000_000),
                                              ("m", 60_000_000_000)])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("entry", ["parse_str", "parse", "parse_to_epoch", "Pydt"])
def test_decimal_clock_length_does_not_change_exact_value(value, clock_unit, factor,
                                                         strict, isoformat, entry):
    text = "1970-01-01 " + value + clock_unit
    nanos = int(Fraction(value) * factor)
    options = {"strict": strict, "isoformat": isoformat}
    if entry == "parse_to_epoch":
        assert parse_to_epoch(text, unit="ns", **options) == nanos
    else:
        expected = datetime(1970, 1, 1) + timedelta(microseconds=nanos // 1000)
        call = {"parse_str": parse_str, "parse": parse, "Pydt": Pydt.parse}[entry]
        actual = call(text, **options)
        assert type(actual) is (Pydt if entry == "Pydt" else datetime)
        assert actual == expected


@pytest.mark.parametrize("strict", [False, True])
def test_seconds_fraction_keeps_its_existing_truncation(strict):
    text = "1970-01-01 0.123456789" + "0" * 100 + "s"
    assert parse_to_epoch(text, unit="ns", strict=strict) == 123456789
    assert parse_str(text, strict=strict).microsecond == 123456


@pytest.mark.parametrize("unit,factor", [("s", 1), ("ms", 1000),
                                       ("us", 1_000_000), ("ns", 1_000_000_000)])
def test_long_decimal_exact_value_is_representable_at_each_epoch_unit(unit, factor):
    text = "1970-01-01 0.5" + "0" * 40 + "h"
    assert parse_to_epoch(text, unit=unit) == 1800 * factor


@pytest.mark.parametrize("text", ["1970-01-01 25.5h", "1970-01-01 60.5m",
                                 "1970-01-01 0.5h 31m"])
def test_long_fraction_repair_does_not_relax_strict_clock_rules(text):
    with pytest.raises(ValueError):
        parse_str(text, strict=True)
