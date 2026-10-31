from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing_extensions import assert_type
import numpy as np
import polars as pl
from rstimes import Delta, Pldt
from rstimes.pldt import _ExprNamespace

x = Pldt(['2024-01-31', None], unit='ns', name='time')
assert_type(x.to_next_month(), Pldt)
assert_type(x.add(nanoseconds=1), Pldt)
assert_type(x.year, pl.Series)
assert_type(x.nanosecond, pl.Series)
assert_type(x.isocalendar(), pl.Series)
assert_type(x.timedf(), pl.DataFrame)
assert_type(x.tzinfo, tzinfo | None)
zone: str | None = None
assert_type(x.is_utc(), bool)
assert_type(x.is_local(), bool)
assert_type(x.tz_available, set[str])
assert_type(x.pldt.replace(day=[28, None]), Pldt)
assert_type(x.pldt.round(freq='15min'), Pldt)
assert_type(x.pldt.diff('2024-01-01', 'D'), pl.Series)
assert_type(x + Delta(nanoseconds=1), Pldt)
assert_type(x - datetime(2024, 1, 1), pl.Series)
assert_type(x.copy(deep=True), Pldt)
assert_type(x.to_numpy(), np.ndarray)
assert_type(x.datetime(), np.ndarray)
assert_type(Pldt.fromdate(date(2024, 1, 1), size=2), Pldt)
assert_type(Pldt.fromdatetime(datetime(2024, 1, 1), size=2), Pldt)
assert_type(Pldt.fromdatetime64(np.datetime64('2024-01-01'), size=2), Pldt)
assert_type(Pldt.fromseconds([1e-9], unit='ns'), Pldt)
assert_type(Pldt.fromordinal([1, None]), Pldt)
assert_type(Pldt.combine([date(2024, 1, 1)], time(12)), Pldt)
assert_type(Pldt.date_range('2024-01-01', periods=2, freq='D'), Pldt)

class Business(Pldt):
    pass

assert_type(Business([0]).to_next_month(), Business)
assert_type(Business([0]).pldt.replace(day=2), Business)
assert_type(Business.fromseconds([0]), Business)
assert_type(Business([0]).copy(), Business)

# Native Polars owns dynamic attribute discovery. The concrete namespace type
# verifies this project's Expr signatures without installing a checker plugin.
expr = _ExprNamespace(pl.col('time'))
assert_type(expr.add(nanoseconds=pl.col('ns')), pl.Expr)
assert_type(expr.year, pl.Expr)
assert_type(expr.fromisocalendar(pl.col('week'), pl.col('weekday')), pl.Expr)
assert_type(expr.diff(pl.col('target').max(), 'D'), pl.Expr)
assert_type(expr.replace(day=pl.col('day')), pl.Expr)
