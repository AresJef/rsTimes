"""A final-storage-only switch is not exhaustive for local carriers."""
from typing import assert_never
from rstimes._native import _PldtRangeEndpoints


def missing_second(value: _PldtRangeEndpoints) -> int:
    unit = value.carrier()[2]
    if unit == "ms":
        return 1000
    if unit == "us":
        return 1000000
    if unit == "ns":
        return 1000000000
    return assert_never(unit)
