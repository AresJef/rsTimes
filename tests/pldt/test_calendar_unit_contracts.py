"""DCR06: nine calendar factories require a real unit; omission still means us."""
from datetime import date
import inspect

import polars as pl
import pytest

from rstimes import Pldt
from rstimes.pldt import _ExprNamespace, _SeriesNamespace


OMITTED = object()
METHODS = ("fromordinal", "fromisocalendar", "fromdayofyear")


def invoke(host, method, option):
    first = [date(2024, 1, 1).toordinal(), None] if method == "fromordinal" else [2024, None]
    remaining = () if method == "fromordinal" else (1, 1) if method == "fromisocalendar" else (1,)
    options = {} if option is OMITTED else {"unit": option}
    if host == "class":
        return getattr(Pldt, method)(first, *remaining, **options)
    if host == "series":
        return getattr(pl.Series("value", first).pldt, method)(*remaining, **options)
    expr = getattr(pl.col("value").pldt, method)(*remaining, **options)
    assert isinstance(expr, pl.Expr)
    return pl.DataFrame({"value": first}).lazy().select(expr).collect().to_series()


@pytest.mark.parametrize("host", ("class", "series", "expr"))
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("option", (OMITTED, "ms", "us", "ns", None, "s", "unknown"),
                         ids=("omitted", "ms", "us", "ns", "None", "s", "unknown"))
def test_all_calendar_factory_unit_roles(host, method, option):
    if option is None:
        with pytest.raises(TypeError, match="unit"):
            invoke(host, method, option)
    elif option in ("s", "unknown"):
        with pytest.raises(ValueError, match="unit"):
            invoke(host, method, option)
    else:
        unit = "us" if option is OMITTED else option
        result = invoke(host, method, option)
        assert type(result) is (pl.Series if host == "expr" else Pldt)
        factor = {"ms": 1000, "us": 1000000, "ns": 1000000000}[unit]
        assert result.dtype == pl.Datetime(unit)
        assert result.to_physical().to_list() == [19723 * 86400 * factor, None]


@pytest.mark.parametrize("owner", (Pldt, _SeriesNamespace, _ExprNamespace))
@pytest.mark.parametrize("method", METHODS)
def test_calendar_annotation_and_docstring_agree_with_none_rejection(owner, method):
    function = getattr(owner, method)
    parameter = inspect.signature(function).parameters["unit"]
    assert parameter.default == "us" and "None" not in str(parameter.annotation)
    assert "Explicit None is not accepted" in inspect.getdoc(function)


def test_constructor_none_keeps_its_distinct_initial_selection_role():
    source = pl.Series([0]).cast(pl.Datetime("ms"))
    value = Pldt(source, unit=None)
    assert value.dtype == pl.Datetime("ms")
