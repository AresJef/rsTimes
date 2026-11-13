"""These mistakes must be rejected without changing runtime validation."""
from rstimes import Pldt, Pydt
from rstimes._native import _integer_arg, _pldt_snapshot, _pydt_from_us

_integer_arg(1, 2, "value")
_pldt_snapshot(object(), Pldt)
_pydt_from_us(Pydt, "one", None)
_pydt_from_us(cls=Pydt, us=0, tz=None)
