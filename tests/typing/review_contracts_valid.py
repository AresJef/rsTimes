"""Round/floor/ceil and direct protocols agree with their runtime inputs."""
from datetime import timedelta

import pandas as pd
from pandas.tseries.offsets import Day, Hour, Micro, Milli, Minute, Nano, Second
import polars as pl

from rstimes import Pldt, Pydt
from rstimes.pldt import _ExprNamespace

source = Pldt([5, 7, None], name="stamp", unit="ns")
expr = _ExprNamespace(pl.col("stamp"))
freqs: tuple[str | timedelta | Day | Hour | Micro | Milli | Minute | Nano | Second, ...] = (
    "3ns", timedelta(microseconds=3), pd.Timedelta(3, unit="ns"),
    Day(), Hour(), Micro(), Milli(), Minute(), Nano(3), Second(),
)
for frequency in freqs:
    source.pldt.floor(frequency)
    source.pldt.ceil(frequency)
    source.pldt.round(frequency)
    expr.floor(frequency)
    expr.ceil(frequency)
    expr.round(frequency)
source.__array__(copy=True)
source.__array__(copy=False)
source.__array__(copy=None)
value = Pydt(2024, 1, 1)
value.__reduce_ex__(4)
value.__reduce_ex__(protocol=4)
