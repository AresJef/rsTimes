"""Reject unsupported frequency families and non-builtin direct copy flags."""
import numpy as np
import polars as pl
from pandas.tseries.offsets import MonthEnd
from rstimes import Pldt
from rstimes.pldt import _ExprNamespace

source = Pldt([5, 7, None], unit="ns")
expr = _ExprNamespace(pl.col("stamp"))
source.pldt.floor(MonthEnd())
source.pldt.ceil(3)
source.pldt.round(np.timedelta64(3, "ns"))
expr.floor(MonthEnd())
expr.ceil(3)
expr.round(np.timedelta64(3, "ns"))
source.__array__(copy=np.bool_(True))
source.__array__(copy=1)
