"""Thin real-Series preparation; no user constructor is used to borrow a column."""
from ._optional import POLARS as pl
from ._native import _pldt_snapshot

_BASE = None


def register(base):
    global _BASE
    _BASE = base


def plain_series(value):
    """Keep ordinary Polars preparation fast; borrow business subclasses via SDK."""
    if isinstance(value, pl.Series) and type(value) not in (pl.Series, _BASE):
        return _pldt_snapshot(value, pl.Series)
    return pl.Series(value)
