"""Configurable date/time parsing implemented by the Rust extension.

Use parse_str for text and parse for supported date/time objects or text.
Configs provides vocabulary and date ordering for string parsing.
"""
from ._optional import POLARS as pl, HAS_POLARS, POLARS_SERIES
from ._native import Configs, parse_str, parse, parse_to_epoch, _restore_configs
from .errors import _own_error, _external_error

__all__ = ["Configs", "parse_str", "parse", "parse_to_epoch"]


def _polars_epoch_value(value, ignoretz):
    """Export one Polars datetime through its integer-backed NumPy adapter."""
    if not HAS_POLARS:
        raise _own_error(ImportError("Polars support requires polars; install rstimes[polars]."))
    if not issubclass(type(value), POLARS_SERIES):
        raise _own_error(TypeError("must be a Polars Datetime Series"), "dtobj", value)
    try:
        dtype = value.dtype
        temporal = dtype.base_type() == pl.Datetime
    except Exception as error:
        raise _external_error(error)
    if not temporal:
        raise _own_error(TypeError("must be a Polars Datetime Series"), "dtobj", value)
    try:
        size = len(value)
    except Exception as error:
        raise _external_error(error)
    if size != 1:
        raise _own_error(ValueError("requires one value; pass a longer Series to Pddt"), "dtobj", value)
    try:
        nulls = value.null_count()
    except Exception as error:
        raise _external_error(error)
    if nulls:
        raise _own_error(ValueError("a null value has no epoch value"), "dtobj", value)
    try:
        if ignoretz and dtype.time_zone is not None:
            value = value.dt.replace_time_zone(None)
        return value.to_numpy()[0]
    except Exception as error:
        raise _external_error(error)
