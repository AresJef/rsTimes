"""Exercise the runtime obligations behind the public typing corrections."""
from datetime import timedelta
from importlib.util import find_spec
import pickle
import sys
from typing import get_type_hints

import numpy as np
import pytest

from rstimes import Pydt


def test_reduce_ex_keyword_and_calendar_year_are_runtime_contracts():
    value = Pydt(2021, 1, 1)
    assert value.__reduce_ex__(protocol=4) == value.__reduce_ex__(4)
    restored = pickle.loads(pickle.dumps(value, protocol=4))
    assert restored == value and type(restored) is Pydt
    assert not restored.is_long_year() and restored.isocalendar().year == 2020
    assert Pydt(2020, 1, 1).is_long_year()
    assert "local calendar year" in Pydt.is_long_year.__doc__
    with pytest.raises(TypeError):
        value.__reduce_ex__()


@pytest.mark.parametrize("method, fine, four, coarse", (
    ("floor", [3, 6, None], [4, 6, None], [0, 0, None]),
    ("ceil", [6, 9, None], [6, 8, None], [3000, 3000, None]),
    ("round", [6, 6, None], [4, 8, None], [0, 0, None]),
))
def test_rounding_complete_eager_and_expression(method, fine, four, coarse):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt
    from rstimes.pldt import _ExprNamespace, _SeriesNamespace

    no_pandas = find_spec("pandas") is None
    if no_pandas:
        assert "pandas" not in sys.modules
    subject = Pldt([5, 7, None], unit="ns", name="stamp")
    expr = pl.col("stamp").pldt

    def check(freq, expected):
        result = getattr(subject.pldt, method)(freq)
        computed = subject.to_frame().lazy().select(getattr(expr, method)(freq)).collect()["stamp"]
        for column in (result, computed):
            assert column.name == "stamp" and column.dtype == pl.Datetime("ns")
            assert column.to_physical().to_list() == expected

    check("3ns", fine)
    check("2ns", four)
    check(timedelta(microseconds=3), coarse)
    assert get_type_hints(getattr(_SeriesNamespace, method))["freq"] == get_type_hints(
        getattr(_ExprNamespace, method)
    )["freq"]
    if no_pandas:
        assert "pandas" not in sys.modules
        return

    import pandas as pd

    check(pd.Timedelta(3, "ns"), fine)
    check(pd.offsets.Nano(3), fine)
    for cls, step in ((pd.offsets.Micro, 1000), (pd.offsets.Milli, 1_000_000),
                      (pd.offsets.Second, 1_000_000_000), (pd.offsets.Minute, 60_000_000_000),
                      (pd.offsets.Hour, 3_600_000_000_000), (pd.offsets.Day, 86_400_000_000_000)):
        check(cls(), [step if method == "ceil" else 0] * 2 + [None])

    class Custom(pd.offsets.Second):
        pass

    for freq in (pd.offsets.Tick(), Custom(), pd.offsets.MonthEnd(),
                 "0ns", "-3ns", timedelta(0), pd.offsets.Day(-1)):
        for owner in (subject.pldt, expr):
            with pytest.raises(ValueError):
                getattr(owner, method)(freq)
    for freq in (3, np.timedelta64(3, "ns")):
        for owner in (subject.pldt, expr):
            with pytest.raises(TypeError):
                getattr(owner, method)(freq)


def test_array_direct_and_numpy_option_preparation():
    pytest.importorskip("polars")
    from rstimes import Pldt

    value = Pldt([1, 2], unit="ns", name="stamp")
    raw = value.__array__(copy=None)
    independent = value.__array__(copy=True)
    assert np.array_equal(raw, independent) and not np.shares_memory(raw, independent)
    assert np.array_equal(value.__array__(copy=False), raw)
    for invalid in (np.bool_(True), 1):
        with pytest.raises(TypeError):
            value.__array__(copy=invalid)
    assert np.array_equal(np.array(value, copy=np.bool_(True)), raw)
    with pytest.raises(RuntimeError, match="copy not allowed"):
        Pldt([1, None], unit="ns").__array__(copy=False)
