"""Independent binary64 answers for a validated short-decimal digit fold."""
import struct

import pytest

from rstimes import parse_to_float


class StoredText(str):
    def __str__(self):
        raise AssertionError("read the stored string")

    def __len__(self):
        raise AssertionError("read the stored length")

    def __getitem__(self, key):
        raise AssertionError("read the stored characters")


CASES = [
    ("1234,56789", True, False, "1234.56789"),
    ("£1234.56789 EUR", False, False, "1234.56789"),
    ("价 -0,00000元", False, False, "-0.0"),
    ("😀 +.125 items", False, False, "0.125"),
    ("qty -123456789012345 items", False, False, "-123456789012345"),
    ("qty 0.12345678901234 items", False, False, "0.12345678901234"),
    ("qty 999999999999999 items", False, False, "999999999999999"),
    ("1234,", True, False, "1234"),
    ("price -1234,500 EUR", False, True, "-1234.5"),
    ("price 1.234,500 EUR", False, True, "1234.5"),
    ("price 1.2345e2 EUR", False, False, "123.45"),
    ("price 9999999999999999.0 EUR", False, False, "9999999999999999.0"),
]


@pytest.mark.parametrize("carrier", [str, StoredText])
@pytest.mark.parametrize("text,strict,grouping,expected", CASES)
def test_short_decimal_and_adjacent_fallbacks_keep_independent_float_bits(
    carrier, text, strict, grouping, expected
):
    result = parse_to_float(carrier(text), strict=strict, allow_grouping=grouping)
    assert type(result) is float
    assert struct.pack("!d", result) == struct.pack("!d", float(expected))
