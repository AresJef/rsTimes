"""Keep exact Python integer outputs across native integer widths and signs."""

import pytest

from rstimes import parse_to_epoch


@pytest.mark.parametrize("seconds", [
    1,
    2**31 - 1,
    2**31,
    2**63 - 1,
    2**63,
    2**64 - 1,
    2**64,
    2**72 - 1,
    2**72,
    (2**127 - 1) // 1_000_000_000,
])
@pytest.mark.parametrize("unit,scale", [
    ("s", 1), ("ms", 1_000), ("us", 1_000_000), ("ns", 1_000_000_000),
])
@pytest.mark.parametrize("sign", [-1, 1])
def test_integer_epoch_output_keeps_its_exact_sign_and_value(
    seconds: int, unit: str, scale: int, sign: int,
) -> None:
    """Numeric epoch seconds scale exactly, without a datetime capacity limit."""
    result = parse_to_epoch(sign * seconds, unit=unit)
    assert type(result) is int
    assert result == sign * seconds * scale
