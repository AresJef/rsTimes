"""PR-039: independent schema/worker kwargs retain a closed clock precision."""
import copy
from datetime import date, time
import importlib
import io
import pickle

import polars as pl
import pytest

api = importlib.import_module("rstimes.pldt")
MISSING = object()


def captured_registration(monkeypatch, clock):
    records = []
    original = api.register_plugin_function
    def capture(**kwargs):
        records.append(kwargs)
        return original(**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(api, "register_plugin_function", capture)
        valid = pl.col("date").pldt.combine(clock)
    assert api.register_plugin_function is original and len(records) == 1
    return valid, original, records[0]


@pytest.mark.parametrize("prepared_unit", ("us", "ns", "unknown", "", "ms", MISSING),
                         ids=("us", "ns", "unknown", "empty", "ms", "missing"))
@pytest.mark.parametrize("output_unit", (None, "ms", "us", "ns"))
@pytest.mark.parametrize("mode", ("ordinary", "empty", "all_null"))
@pytest.mark.parametrize("phase", ("schema", "collect"))
def test_static_clock_precision_cannot_be_bypassed_by_output_unit_or_empty_rows(
        prepared_unit, output_unit, mode, phase, monkeypatch):
    _, register, base = captured_registration(monkeypatch, time(1, 2, 3, 456000))
    options = copy.deepcopy(base["kwargs"])
    options["unit"] = output_unit
    if prepared_unit is MISSING:
        del options["prepared"]["unit"]
    else:
        options["prepared"]["unit"] = prepared_unit
    expression = register(**{**base, "kwargs": options})
    values = [] if mode == "empty" else [None, None] if mode == "all_null" else [date(1970,1,1), None]
    frame = pl.DataFrame({"date": pl.Series(values, dtype=pl.Date)})
    query = frame.lazy().select(expression)
    legal = prepared_unit in ("us", "ns")
    if not legal:
        with pytest.raises(pl.exceptions.PolarsError, match="unit|variant"):
            query.collect_schema() if phase == "schema" else query.collect()
    else:
        chosen = output_unit or prepared_unit
        if phase == "schema":
            assert query.collect_schema()["date"] == pl.Datetime(chosen)
        else:
            result = query.collect()["date"]
            expected = [] if mode == "empty" else [None, None] if mode == "all_null" else [
                3723456000000 // {"ms":1000000, "us":1000, "ns":1}[chosen], None]
            assert result.dtype == pl.Datetime(chosen)
            assert result.to_physical().to_list() == expected


@pytest.mark.parametrize("variant", ("original", "clone", "pickle", "native_deserialize"))
@pytest.mark.parametrize("precision", ("us", "ns"))
def test_legal_precision_keeps_nanosecond_tail_and_expression_roundtrip(variant, precision, monkeypatch):
    pd = pytest.importorskip("pandas")
    clock = time(1,2,3,456000) if precision == "us" else pd.Timestamp("2000-01-01T01:02:03.123456789")
    expression, _, base = captured_registration(monkeypatch, clock)
    assert base["kwargs"]["prepared"]["unit"] == precision
    if variant == "clone":
        expression = copy.copy(expression)
    elif variant == "pickle":
        expression = pickle.loads(pickle.dumps(expression))
    elif variant == "native_deserialize":
        expression = pl.Expr.deserialize(io.BytesIO(expression.meta.serialize()))
    frame = pl.DataFrame({"date": pl.Series([date(1970,1,1),None], dtype=pl.Date)})
    result = frame.lazy().select(expression).collect()["date"]
    expected = 3723456000 if precision == "us" else 3723123456789
    assert result.dtype == pl.Datetime(precision)
    assert result.to_physical().to_list() == [expected,None]
