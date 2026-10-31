"""Independent integer coordinates protect narrow and wide scalar exits."""

import pytest

from rstimes import parse_to_epoch


@pytest.mark.parametrize("unit,scale", [("s", 10**9), ("ms", 10**6),
                                       ("us", 1000), ("ns", 1)])
@pytest.mark.parametrize("text,nanos", [
    ("1969-12-31T23:59:59.999999999", -1),
    ("1970-01-01T00:00:00.000000001", 1),
    ("0000-01-01T00:00:00", -62_167_219_200_000_000_000),
    ("9999-12-31T23:59:59.123456789", 253_402_300_799_123_456_789),
])
def test_public_epoch_projection_has_no_early_precision_or_calendar_capacity(text, nanos, unit, scale):
    result = parse_to_epoch(text, unit=unit)
    assert type(result) is int
    assert result == nanos // scale


@pytest.mark.parametrize("unit,scale", [("s", 10**9), ("ms", 10**6),
                                       ("us", 1000), ("ns", 1)])
@pytest.mark.parametrize("seconds", [
    -(2**80), -(2**63), -(2**31), -1, 0, 1, 1_500_000_000,
    2**31 - 1, 2**31, 2**63 - 1, 2**63, 2**80,
])
def test_integer_epoch_exit_preserves_type_and_values_across_i64_boundary(seconds, unit, scale):
    result = parse_to_epoch(seconds, unit=unit)
    assert type(result) is int
    assert result == seconds * 10**9 // scale
