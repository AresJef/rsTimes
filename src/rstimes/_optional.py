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
PANDAS_TIMESTAMP = PANDAS.Timestamp if PANDAS is not None else None
PANDAS_TIMEDELTA = PANDAS.Timedelta if PANDAS is not None else None
PANDAS_NAT_TYPE = type(PANDAS.NaT) if PANDAS is not None else None
POLARS_SERIES = POLARS.Series if POLARS is not None else None
# Prepare this upstream compatibility fact once, alongside the real type objects.
PANDAS_REPLACE_NEEDS_TAIL = PANDAS is not None and PANDAS.__version__.split(".", 1)[0] == "2"

# Retain the same type objects on both sides of the Python/Rust boundary.
# This extension has finished initialization before the shared adapter is loaded.
from ._native import _configure_optional

_configure_optional(
    PANDAS_TIMESTAMP, PANDAS_TIMEDELTA, PANDAS_NAT_TYPE, POLARS_SERIES,
    PANDAS_REPLACE_NEEDS_TAIL,
)
