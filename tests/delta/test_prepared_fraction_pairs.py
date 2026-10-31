"""Independent complete-value guards for two prepared fixed-duration fractions."""
from fractions import Fraction

import numpy as np
import pytest

from rstimes import Delta

_FACTORS = {"weeks": 604_800_000_000_000, "days": 86_400_000_000_000,
            "hours": 3_600_000_000_000, "minutes": 60_000_000_000,
            "seconds": 1_000_000_000, "milliseconds": 1_000_000,
            "microseconds": 1_000, "nanoseconds": 1}
_PAIRS = [("weeks", "days"), ("days", "seconds"), ("hours", "minutes"),
          ("minutes", "milliseconds"), ("seconds", "microseconds"),
          ("milliseconds", "nanoseconds"), ("microseconds", "weeks"),
          ("nanoseconds", "days")]
_AMOUNTS = [(1.5, 2.25), (0.1, -0.1), (-0.5, 0.5),
            (np.float32(0.6), np.float16(0.1)),
            (float.fromhex("0x0.0000000000001p-1022"), -1e-310)]


@pytest.mark.parametrize("left,right", _PAIRS)
@pytest.mark.parametrize("a,b", _AMOUNTS)
def test_two_source_fractions_keep_the_exact_binary_sum(left, right, a, b):
    total = (Fraction.from_float(float(a)) * _FACTORS[left]
             + Fraction.from_float(float(b)) * _FACTORS[right])
    days, clock = divmod(round(total), _FACTORS["days"])
    value = Delta(**{left: a, right: b})
    assert (value.days, value.hours, value.minutes, value.seconds,
            value.microseconds, value.nanoseconds) == (
        days, clock // _FACTORS["hours"], clock // _FACTORS["minutes"] % 60,
        clock // _FACTORS["seconds"] % 60, clock // 1000 % 1_000_000,
        clock % 1000,
    )
