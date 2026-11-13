"""Standalone numeric utilities have complete, precise public signatures."""
from rstimes import parse_to_float, parse_to_integer
import numpy as np

integer: int = parse_to_integer("123")
floating: float = parse_to_float("1,234.56", allow_grouping=True)
wide: int = parse_to_integer("170141183460469231731687303715884105727")
loose: float = parse_to_float("price 1.234,56 EUR", strict=np.bool_(False), allow_grouping=np.bool_(True))
