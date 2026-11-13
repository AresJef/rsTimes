"""Pandas ProductReady regressions preserve fixed units and missing positions."""
from fractions import Fraction

import numpy as np
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("value", ["0.5", "0.5" + "0" * 40,
                                  "0.123456789012345678901234567890",
                                  "0." + "0" * 40 + "1"])
@pytest.mark.parametrize("clock_unit,factor", [("h", 3_600_000_000_000),
                                              ("m", 60_000_000_000)])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("isoformat", [False, True])
def test_decimal_clock_matches_exact_rational_and_preserves_nat(value, clock_unit,
                                                               factor, strict, isoformat):
    text = "1970-01-01 " + value + clock_unit
    source = [text, None]
    result = Pddt(source, unit="ns", name="stamp", strict=strict, isoformat=isoformat)
    assert result.unit == "ns" and result.name == "stamp"
    assert result.asi8.tolist() == [int(Fraction(value) * factor), np.iinfo(np.int64).min]
    assert source == [text, None]


