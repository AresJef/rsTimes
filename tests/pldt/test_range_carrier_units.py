"""DCR07: mature local carriers can use seconds without changing storage."""
import pytest

from rstimes._native import (
    _pldt_named_zone_context, _pldt_policies, _pldt_range_endpoints,
)


def prepare(start, end, unit, zone=None):
    return _pldt_range_endpoints(
        start, end, _pldt_policies("raise", "raise"), None, unit,
        _pldt_named_zone_context(zone) if zone is not None else None,
        False, None, None, None, True, False, None, True,
    )


def test_exact_second_carrier_does_not_add_second_storage_to_pldt():
    value = 9223372036854775000
    result = prepare(value, None, "ms", "Etc/GMT-1")
    assert result.unit == "ms"
    assert result.carrier() == (9223372036858375, None, "s")


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
@pytest.mark.parametrize("start,end", ((0, 1000), (0, None), (None, 1000), (None, None)))
def test_ordinary_carrier_units_and_missing_endpoints_keep_their_values(unit, start, end):
    result = prepare(start, end, unit)
    assert result.unit == unit and result.carrier() == (start, end, unit)
