"""Shared optional dependencies, resolved once when their adapter is loaded."""

try:
    import pandas as PANDAS
except ModuleNotFoundError as error:
    if error.name != "pandas":
        raise
    PANDAS = None

try:
    import polars as POLARS
except ModuleNotFoundError as error:
    if error.name != "polars":
        raise
    POLARS = None

HAS_POLARS = POLARS is not None
HAS_PANDAS = PANDAS is not None
PANDAS_TIMESTAMP = PANDAS.Timestamp if HAS_PANDAS else None
PANDAS_TIMEDELTA = PANDAS.Timedelta if HAS_PANDAS else None
PANDAS_NAT_TYPE = type(PANDAS.NaT) if HAS_PANDAS else None
POLARS_SERIES = POLARS.Series if HAS_POLARS else None

# Retain the same type objects on both sides of the Python/Rust boundary.
# This extension has finished initialization before the shared adapter is loaded.
from ._native import _configure_optional

_configure_optional(PANDAS_TIMESTAMP, PANDAS_TIMEDELTA, PANDAS_NAT_TYPE, POLARS_SERIES)
