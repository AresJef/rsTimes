"""Actual eager/Expr timezone execution, schema, logical order and nulls."""
from datetime import timezone, timedelta
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def us(text):
    return int(np.datetime64(text, "us").astype(np.int64))


def ticks(value):
    return value.to_physical().to_list()


def naive(values):
    return pl.Series("time", [None if text is None else us(text) for text in values], dtype=pl.Datetime("us"))


def test_attach_convert_and_two_remove_meanings():
    source = Pldt(naive(["2024-01-01T12:00", None]))
    result = source.tz_localize("Asia/Shanghai")
    assert type(result) is Pldt
    assert result.dtype == pl.Datetime("us", "Asia/Shanghai")
    assert ticks(result) == [us("2024-01-01T04:00"), None]
    assert ticks(source) == [us("2024-01-01T12:00"), None]
    utc = result.tz_convert("UTC")
    assert utc.dtype == pl.Datetime("us", "UTC")
    assert ticks(utc) == ticks(result)
    assert ticks(result.tz_convert(None)) == [us("2024-01-01T04:00"), None]
    assert result.tz_convert(None).dtype == pl.Datetime("us")
    assert ticks(result.tz_localize(None)) == ticks(source)
    assert result.tz_localize(None).dtype == pl.Datetime("us")
    with pytest.raises(TypeError, match="naive"):
        source.tz_convert("UTC")
    with pytest.raises(TypeError, match="already|convert"):
        result.tz_localize("UTC")


@pytest.mark.parametrize("parameter,value,category", [
    ("ambiguous", "unknown", ValueError),
    ("nonexistent", 1, TypeError),
])
def test_policy_failures_identify_entry_parameter_and_input(parameter, value, category):
    source = Pldt(naive(["2024-01-01T12:00"]))
    with pytest.raises(category) as caught:
        source.tz_localize("UTC", **{parameter: value})
    message = str(caught.value)
    assert "Pldt.tz_localize" in message
    assert parameter in message and repr(value) in message


def test_policy_external_iterator_failure_preserves_actual_exception():
    failure = ValueError("user mask failed")

    class BrokenMask:
        def __iter__(self):
            raise failure

    source = Pldt(naive(["2024-01-01T12:00"]))
    with pytest.raises(ValueError) as caught:
        source.tz_localize("UTC", ambiguous=BrokenMask())
    assert caught.value is failure
    assert str(caught.value) == "user mask failed"


def test_switch_base_target_none_and_naive_target_clock():
    source = Pldt(naive(["2024-01-01T12:00"]))
    result = source.tz_switch("UTC", base_tz="Asia/Shanghai")
    assert ticks(result) == [us("2024-01-01T04:00")]
    result = result.tz_switch("America/New_York", base_tz="ignored bad base", naive=True)
    assert result.dtype == pl.Datetime("us")
    assert ticks(result) == [us("2023-12-31T23:00")]
    assert ticks(source.tz_switch(None, base_tz="ignored bad base")) == ticks(source)
    with pytest.raises(ValueError, match="base_tz"):
        source.tz_switch("UTC")


@pytest.mark.parametrize("unit,step", [("ms", 1), ("us", 1), ("ns", 1)])
def test_public_gap_current_unit_and_true_minimum(unit, step):
    factor = {"ms": 1000, "us": 1, "ns": 0.001}[unit]
    # Build from exact integral source ticks, avoiding float conversion.
    before = us("2024-03-10T02:30")
    raw = before // 1000 if unit == "ms" else before if unit == "us" else before * 1000
    source = Pldt(pl.Series("time", [raw, None], dtype=pl.Datetime(unit)))
    result = source.tz_localize("America/New_York", nonexistent="shift_backward")
    end = us("2024-03-10T07:00")
    expected = end // 1000 - step if unit == "ms" else end - step if unit == "us" else end * 1000 - step
    assert ticks(result) == [expected, None]
    minimum = Pldt([-(2**63), None], unit=unit).tz_localize("UTC")
    assert ticks(minimum) == [-(2**63), None]
    assert ticks(minimum.tz_convert(None)) == [-(2**63), None]


def test_actual_lazy_timezone_pipeline_schema_and_instants():
    source = naive(["2024-01-01T12:00", None])
    expr = pl.col("time").pldt.tz_localize("Asia/Shanghai").pldt.tz_convert("UTC")
    query = pl.DataFrame(source).lazy().select(expr)
    assert query.collect_schema()["time"] == pl.Datetime("us", "UTC")
    assert ticks(query.collect()["time"]) == [us("2024-01-01T04:00"), None]
    expr = pl.col("time").pldt.tz_localize("Asia/Shanghai").pldt.tz_localize(None)
    assert ticks(pl.DataFrame(source).select(expr)["time"]) == ticks(source)


def repeated():
    return naive(["2024-11-03T01:00", "2024-11-03T01:30", "2024-11-03T01:00", "2024-11-03T01:30"])


def test_infer_spans_real_chunks_and_streaming_logical_column():
    source = pl.concat([repeated().head(2), repeated().tail(2)], rechunk=False)
    assert source.n_chunks() == 2
    expected = [us(text) for text in ("2024-11-03T05:00", "2024-11-03T05:30", "2024-11-03T06:00", "2024-11-03T06:30")]
    assert ticks(source.pldt.tz_localize("America/New_York", ambiguous="infer")) == expected
    expr = pl.col("time").pldt.tz_localize("America/New_York", ambiguous="infer")
    query = pl.DataFrame(source).lazy().select(expr)
    assert ticks(query.collect(engine="streaming")["time"]) == expected


def test_boolean_expr_and_logical_scalar_policy_roles():
    source = naive(["2024-11-03T01:30", "2024-11-03T01:30"])
    frame = pl.DataFrame({"time": source, "choice": [True, False]})
    expr = pl.col("time").pldt.tz_localize("America/New_York", ambiguous=pl.col("choice"))
    assert ticks(frame.select(expr)["time"]) == [us("2024-11-03T05:30"), us("2024-11-03T06:30")]
    expr = pl.col("time").pldt.tz_localize("America/New_York", ambiguous=pl.col("choice").any())
    assert ticks(frame.select(expr)["time"]) == [us("2024-11-03T05:30")] * 2
    expr = pl.col("time").pldt.tz_localize("America/New_York", ambiguous=pl.col("choice").head(1))
    with pytest.raises(pl.exceptions.PolarsError):
        frame.select(expr)


def test_mask_snapshot_and_native_boolean_validation():
    source = naive(["2024-11-03T01:30", "2024-11-03T01:30"])
    mask = np.array([True, False])
    expr = pl.col("time").pldt.tz_localize("America/New_York", ambiguous=mask)
    mask[:] = False
    assert ticks(pl.DataFrame(source).select(expr)["time"]) == [us("2024-11-03T05:30"), us("2024-11-03T06:30")]
    for bad in (np.array([], dtype=float), pl.Series([], dtype=pl.Int64)):
        with pytest.raises(TypeError):
            source.head(0).pldt.tz_localize("UTC", ambiguous=bad)


def test_grouped_infer_does_not_mix_groups():
    source = pl.concat([repeated(), repeated()], rechunk=False)
    frame = pl.DataFrame({"time": source, "group": ["A"] * 4 + ["B"] * 4})
    expr = pl.col("time").pldt.tz_localize("America/New_York", ambiguous="infer").over("group")
    expected = [us(text) for text in ("2024-11-03T05:00", "2024-11-03T05:30", "2024-11-03T06:00", "2024-11-03T06:30")] * 2
    assert ticks(frame.select(expr)["time"]) == expected


def test_known_instant_conversion_does_not_check_region_capacity():
    value = int(np.datetime64("12000-01-01", "ms").astype(np.int64))
    source = Pldt(pl.Series("time", [value], dtype=pl.Datetime("ms", "America/New_York")))
    assert ticks(source.tz_convert("UTC")) == [value]
    assert ticks(source.tz_convert(None)) == [value]
    with pytest.raises(OverflowError):
        source.tz_localize(None)


def test_business_timezone_result_constructs_once():
    class Business(Pldt):
        calls = 0
        def __init__(self, data, **kwargs):
            Business.calls += 1
            super().__init__(data, **kwargs)
    source = Business(naive(["2024-01-01T12:00"]))
    Business.calls = 0
    assert type(source.pldt.tz_localize("UTC")) is Business
    assert Business.calls == 1


def test_empty_and_all_null_keep_explicit_region_and_check_policies():
    for data in ([], [None, None]):
        source = pl.Series("time", data, dtype=pl.Datetime("ns"))
        result = source.pldt.tz_localize("Asia/Shanghai")
        assert result.dtype == pl.Datetime("ns", "Asia/Shanghai")
        assert ticks(result) == data
        with pytest.raises(ValueError):
            source.pldt.tz_localize("UTC", nonexistent="unknown")


@pytest.mark.parametrize("days", [200000, -200000])
def test_expr_wide_policy_integer_transport_has_no_i128_pickle_loss(days):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    shift = timedelta(days=days)
    result = (datetime(2024, 3, 10, 2, 30) + shift).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
    elapsed = result.replace(tzinfo=None) - datetime(1970, 1, 1)
    expected = (elapsed.days * 86400 + elapsed.seconds) * 1000000 + elapsed.microseconds
    source = naive(["2024-03-10T02:30"])
    expr = pl.col("time").pldt.tz_localize("America/New_York", nonexistent=shift)
    assert ticks(pl.DataFrame(source).select(expr)["time"]) == [expected]


def test_fixed_switch_checks_only_final_combined_shift():
    source = Pldt([-(2**63)], unit="ms")
    result = source.tz_switch(timezone(timedelta(hours=8)), base_tz=timezone(timedelta(hours=8)), naive=True)
    assert ticks(result) == [-(2**63)]
    assert result.dtype == pl.Datetime("ms")
