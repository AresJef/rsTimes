"""Exact integral products and mixed fractions use one mathematical contract."""
from fractions import Fraction

import numpy as np
import pytest

from rstimes import Delta

FACTORS = {"weeks": 604_800_000_000_000, "days": 86_400_000_000_000,
           "hours": 3_600_000_000_000, "minutes": 60_000_000_000,
           "seconds": 1_000_000_000, "milliseconds": 1_000_000,
           "microseconds": 1000, "nanoseconds": 1}


def quantity(value):
    return (value.days * FACTORS["days"] + value.hours * FACTORS["hours"]
            + value.minutes * FACTORS["minutes"] + value.seconds * FACTORS["seconds"]
            + value.microseconds * 1000 + value.nanoseconds)


@pytest.mark.parametrize("field,factor", FACTORS.items())
@pytest.mark.parametrize("number", [0.5, -0.125, 0.1, np.nextafter(0.5, 1.0), 1e-310, np.float16(0.1), np.float32(0.6), 2.25])
def test_fractional_unit_product_matches_independent_binary_rational(field, factor, number):
    expected = round(Fraction.from_float(float(number)) * factor)
    assert quantity(Delta(**{field: number})) == expected


@pytest.mark.parametrize("fields,expected", [
    ({"seconds": 0.1, "nanoseconds": 0.5}, 100_000_001),
    ({"seconds": 0.1, "nanoseconds": -99_999_999.5}, 1),
    ({"seconds": -0.1, "nanoseconds": 99_999_999.5}, -1),
    ({"days": 1.5, "seconds": 2.25}, 129_602_250_000_000),
])
def test_rounded_looking_products_cannot_be_mistaken_for_integral_terms(fields, expected):
    assert quantity(Delta(**fields)) == expected


@pytest.mark.parametrize("fields", [
    {"weeks": 0.1, "days": 0.5, "seconds": 1e-310},
    {"days": 0.5, "seconds": 0.1, "nanoseconds": 0.5},
    {"hours": -0.25, "seconds": -1e-310, "microseconds": 0.5},
])
def test_integral_and_nonintegral_terms_share_compact_and_wide_accumulation(fields):
    expected = round(sum((Fraction.from_float(number)*FACTORS[field]
                          for field, number in fields.items()), Fraction()))
    assert quantity(Delta(**fields)) == expected
