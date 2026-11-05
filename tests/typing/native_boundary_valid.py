"""Accurate private result types keep checked Python/Rust callers connected."""
from typing import assert_type
import polars as pl
from rstimes import Pldt, Pydt
from rstimes._native import (
    _integer_arg, _pldt_snapshot, _pydt_from_us, _strftime_prepare,
)

assert_type(_integer_arg(1, "typing", "value"), int)
assert_type(_pldt_snapshot(pl.Series([0]), Pldt), Pldt)
assert_type(_pydt_from_us(Pydt, 0, None), Pydt)
assert_type(_strftime_prepare("%f").plugin_data(), bytes)
