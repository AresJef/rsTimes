"""Calendar unit roles are the same for Pldt and both native namespaces."""
from typing import assert_type
import polars as pl
from rstimes import Pldt
from rstimes.pldt import _SeriesNamespace, _ExprNamespace


def calendar_units(series: _SeriesNamespace[Pldt], expr: _ExprNamespace) -> None:
    assert_type(Pldt.fromordinal([1], unit="ms"), Pldt)
    assert_type(Pldt.fromisocalendar([2024], 1, 1, unit="us"), Pldt)
    assert_type(Pldt.fromdayofyear([2024], 1, unit="ns"), Pldt)
    assert_type(series.fromordinal(unit="ns"), Pldt)
    assert_type(series.fromisocalendar(1, 1, unit="ms"), Pldt)
    assert_type(series.fromdayofyear(1, unit="us"), Pldt)
    assert_type(expr.fromordinal(unit="us"), pl.Expr)
    assert_type(expr.fromisocalendar(1, 1, unit="ns"), pl.Expr)
    assert_type(expr.fromdayofyear(1, unit="ms"), pl.Expr)
