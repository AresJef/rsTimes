"""Native Polars date columns and expression namespaces.

Column calculations share a Rust kernel. Loading this module explicitly enables
the official Series/Expr namespaces; the base rsTimes import does not require
Polars. The implementation is being expanded under the approved PLDT contract.
"""

from pathlib import Path

from ._optional import POLARS as pl

if pl is None:
    raise ImportError('Pldt requires Polars; install "rstimes[polars]".')

from polars.plugins import register_plugin_function
from . import _native
from ._native import _integer_arg, _pldt_execute

_PLUGIN_PATH = Path(_native.__file__)


def _operand(value, *, expression):
    """Prepare the actual scalar/vector role once, never from result length."""
    if isinstance(value, pl.Expr):
        if not expression:
            raise TypeError("Pldt.add: eager days cannot be an Expr")
        return value, value.meta.is_scalar()
    if isinstance(value, pl.Series):
        return (pl.lit(value) if expression else value), False
    if isinstance(value, (list, tuple)):
        series = pl.Series("days", value)
        return (pl.lit(series) if expression else series), False
    value = _integer_arg(value, "Pldt.add", "days")
    return (pl.lit(value, dtype=pl.Int64) if expression else pl.Series("days", [value])), True


def _expr(source, operation, argument=0, operand=None, scalar=False):
    """Build an official plugin expression with owned, versioned kwargs."""
    args = [source] if operand is None else [source, operand]
    return register_plugin_function(
        plugin_path=_PLUGIN_PATH,
        function_name="pldt_execute",
        args=args,
        kwargs={"version": 1, "operation": operation, "argument": argument, "scalar": scalar},
        is_elementwise=operand is None,
    )


def _eager(source, operation, argument=0, operand=None, scalar=False):
    target = pl.Series if operation == "is_month" else Pldt
    return _pldt_execute(source, target, operation, argument, operand, scalar)


class Pldt(pl.Series):
    """A true Polars Datetime Series with native calendar operations.

    Args:
        data: One-dimensional date data. The initial native execution slice
            accepts a typed Polars Datetime Series.
        unit: Optional target resolution, one of ``ms``, ``us`` or ``ns``.
        name: Optional output column name; otherwise retain the source name.

    The complete constructor is delivered by the approved input-kernel stage.
    """

    def __init__(self, data, *, unit=None, name=None):
        if not isinstance(data, pl.Series) or data.dtype.base_type() != pl.Datetime:
            raise TypeError("Pldt: this native execution slice requires a Datetime Series")
        if unit is not None and unit not in ("ms", "us", "ns"):
            raise ValueError("Pldt: unit must be 'ms', 'us' or 'ns'")
        if unit is not None and unit != data.dtype.time_unit:
            raise NotImplementedError("Pldt unit conversion is supplied by the input kernel")
        super().__init__(data if name is None else data.rename(name))

    def to_next_month(self):
        """Return a Pldt moved one calendar month, fitting month-end dates."""
        return _eager(self, "next_month")

    def is_month(self, month):
        """Return a Boolean Series; missing dates are False."""
        month = _integer_arg(month, "Pldt.is_month", "month")
        return _eager(self, "is_month", month)


class _SeriesNamespace:
    def __init__(self, series):
        self._series = series

    def to_next_month(self):
        """Move a typed date column by one month, returning Pldt."""
        return _eager(self._series, "next_month")

    def is_month(self, month):
        """Return a native Boolean column without an intermediate Pldt."""
        month = _integer_arg(month, "Pldt.is_month", "month")
        return _eager(self._series, "is_month", month)

    def add(self, *, days=0):
        """Add a scalar or strictly equal-length integer days column."""
        operand, scalar = _operand(days, expression=False)
        return _eager(self._series, "add_days", operand=operand, scalar=scalar)


class _ExprNamespace:
    def __init__(self, expr):
        self._expr = expr

    def to_next_month(self):
        """Return a native Expr applying the shared calendar-month kernel."""
        return _expr(self._expr, "next_month")

    def is_month(self, month):
        """Return a Boolean Expr, preserving the source expression name."""
        month = _integer_arg(month, "Pldt.is_month", "month")
        return _expr(self._expr, "is_month", month)

    def add(self, *, days=0):
        """Add integer days, distinguishing logical scalars from vectors."""
        operand, scalar = _operand(days, expression=True)
        return _expr(self._expr, "add_days", operand=operand, scalar=scalar)


if hasattr(pl.Series, "pldt") or hasattr(pl.Expr, "pldt"):
    raise RuntimeError("Cannot register rstimes.pldt: the Polars 'pldt' namespace is already occupied")

pl.api.register_series_namespace("pldt")(_SeriesNamespace)
pl.api.register_expr_namespace("pldt")(_ExprNamespace)

__all__ = ["Pldt"]
