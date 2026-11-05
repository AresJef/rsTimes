"""Explicit None is not an initial unit selector for calendar factories."""
from rstimes import Pldt
from rstimes.pldt import _SeriesNamespace, _ExprNamespace


def calendar_none(series: _SeriesNamespace[Pldt], expr: _ExprNamespace) -> None:
    Pldt.fromordinal([1], unit=None)
    Pldt.fromisocalendar([2024], 1, 1, unit=None)
    Pldt.fromdayofyear([2024], 1, unit=None)
    series.fromordinal(unit=None)
    series.fromisocalendar(1, 1, unit=None)
    series.fromdayofyear(1, unit=None)
    expr.fromordinal(unit=None)
    expr.fromisocalendar(1, 1, unit=None)
    expr.fromdayofyear(1, unit=None)
