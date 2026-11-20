"""Thin real-Series preparation; no user constructor is used to borrow a column."""
from ._optional import POLARS as pl

_BASE = None


def register(base):
    global _BASE
    _BASE = base


def plain_series(value):
    """Retain a native owner without business clone or constructor callbacks."""
    kind = type(value)
    if kind not in (pl.Series, _BASE) and issubclass(kind, pl.Series):
        # Public host methods capture _s once and return an independent base
        # shell. Unlike SDK exchange, this also preserves Object payloads.
        return pl.Series.to_frame(value).to_series()
    return pl.Series(value)
