"""Exact public integer results at signed-byte boundaries, independent of SDK."""
import pytest

from rstimes import parse_to_epoch


@pytest.mark.parametrize("bit", [64, 71, 72, 79, 80, 87, 88, 95, 96, 103, 104, 111, 112, 119, 120, 126])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_wide_python_integer_output_retains_value_and_builtin_type(bit, sign, offset):
    value = sign * (2**bit) + offset
    result = parse_to_epoch(value, unit="ns", input_unit="ns")
    assert type(result) is int
    assert result == value


@pytest.mark.parametrize("value", [-(2**127), 2**127 - 1])
def test_full_signed_integer_output_keeps_both_extremes(value):
    result = parse_to_epoch(value, unit="ns", input_unit="ns")
    assert type(result) is int and result == value
