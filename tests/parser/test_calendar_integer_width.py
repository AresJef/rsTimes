"""Keep integer range errors stable in complete numeric calendar triples."""
from datetime import datetime

import pytest

from rstimes import parse_str as parse
from rstimes.errors import ParseError


@pytest.mark.parametrize("text, expected", [
    ("999999999999999999/01/01", None),
    ("9223372036854775807/01/01", None),
    ("9223372036854775808/01/01", None),
    ("2024/999999999999999999/01", None),
])
def test_numeric_calendar_preserves_checked_integer_boundaries(text, expected):
    if expected is not None:
        assert parse(text, isoformat=False) == expected
    else:
        with pytest.raises(OverflowError) as observed:
            parse(text, isoformat=False)
        assert observed.value.__cause__ is None


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("text, dayfirst, expected", [
    ("0001/02/03", False, datetime(1, 2, 3)),
    ("0001/02/03", True, datetime(1, 3, 2)),
    ("02/03/0001", False, datetime(1, 2, 3)),
    ("02/03/0001", True, datetime(1, 3, 2)),
])
def test_explicit_small_year_preserves_numeric_calendar_order(text, dayfirst, expected, strict):
    assert parse(text, isoformat=False, dayfirst=dayfirst, strict=strict) == expected


@pytest.mark.parametrize("text, dayfirst, expected", [
    ("2024/13/04", False, datetime(2024, 12, 4)),
    ("2024/13/04", True, datetime(2024, 4, 13)),
    ("00/05/2024", True, None),
    ("32/05/2024", False, datetime(2024, 5, 31)),
])
def test_numeric_calendar_keeps_lenient_boundary_clamping(text, dayfirst, expected):
    if expected is None:
        with pytest.raises(ValueError): parse(text, isoformat=False, dayfirst=dayfirst)
    else:
        assert parse(text, isoformat=False, dayfirst=dayfirst) == expected
