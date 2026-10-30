"""Approved text, source/target, snapshot and formatted column contracts."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import importlib
import numpy as np
import polars as pl
import pytest

from rstimes import Configs, Pldt


def tick(text, unit="us"):
    return int(np.datetime64(text, unit).astype(np.int64))


def ticks(value):
    return value.to_physical().to_list()


def registered():
    cfg = Configs()
    cfg.add_tzone("America/New_York")
    cfg.add_tzone("America/Toronto")
    return cfg


def test_constructor_preserves_common_region_and_true_nanoseconds():
    result = Pldt(["2024-01-01 12:00 America/New_York",
                   "2024-07-01 12:00:00.123456789 America/New_York", None], cfg=registered())
    assert result.dtype == pl.Datetime("ns", "America/New_York")
    assert ticks(result) == [tick("2024-01-01T17:00", "ns"), tick("2024-07-01T16:00:00.123456789", "ns"), None]


def test_numeric_instants_and_naive_text_have_distinct_target_meanings():
    result = Pldt([0, "1970-01-01 00:00", None], unit="us", tz="Asia/Shanghai")
    assert result.dtype == pl.Datetime("us", "Asia/Shanghai")
    assert ticks(result) == [0, -28_800_000_000, None]


def test_source_localization_precedes_explicit_target_conversion():
    result = Pldt(["2024-01-01 12:00 America/New_York", "2024-01-01 12:00"],
                  cfg=registered(), tz="UTC", unit="us")
    assert ticks(result) == [tick("2024-01-01T17:00"), tick("2024-01-01T12:00")]
    assert result.dtype == pl.Datetime("us", "UTC")


def test_future_source_region_uses_posix_rules_and_keeps_true_instants():
    result = Pldt(["2500-07-01 12:00"], tz="America/New_York")
    assert ticks(result) == [tick("2500-07-01T16:00")]
    assert ticks(result.tz_localize(None)) == [tick("2500-07-01T12:00")]
    assert ticks(result.tz_convert("UTC")) == [tick("2500-07-01T16:00")]


def test_aware_python_fold_is_a_known_instant_but_default_fold_is_not_column_policy():
    source = datetime(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    assert ticks(Pldt([source], tz="UTC")) == [tick("2024-11-03T06:30")]
    with pytest.raises(ValueError, match="ambiguous|twice"):
        Pldt(["2024-11-03 01:30"], default=source, tz="America/New_York")


@pytest.mark.parametrize("values", [
    ["2024-01-01 12:00", "2024-01-01 12:00 America/New_York"],
    ["2024-01-01 12:00 America/New_York", "2024-01-01 12:00 America/Toronto"],
])
def test_conflicting_nonmissing_source_zones_require_target(values):
    with pytest.raises(ValueError, match="tz|source|zone"):
        Pldt(values, cfg=registered())


def test_unregistered_region_is_not_activated_by_target():
    with pytest.raises(ValueError, match="registered|add_tzone"):
        Pldt(["2024-01-01 12:00 America/New_York"], tz="UTC")


def test_unencodable_source_offset_can_convert_to_explicit_target():
    source = datetime(2024, 1, 1, 12, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert ticks(Pldt([source], tz="UTC")) == [tick("2024-01-01T06:30")]
    assert ticks(Pldt(["2024-01-01 12:00+05:30"], tz="UTC")) == [tick("2024-01-01T06:30")]
    with pytest.raises(ValueError, match="fixed|represent|encode"):
        Pldt([source])


def test_native_known_instant_target_conversion_does_not_relocalize():
    source = pl.Series("time", [tick("2024-07-01T16:00"), None], dtype=pl.Datetime("us", "America/New_York"))
    result = Pldt(source, tz="UTC")
    assert result.dtype == pl.Datetime("us", "UTC")
    assert ticks(result) == ticks(source)


@pytest.mark.parametrize("raw,offset", [(9223372036854776, 8), (-9223372036854777, -8)])
@pytest.mark.parametrize("source_kind", ["polars", "numpy"])
def test_localize_before_narrowing_avoids_false_intermediate_overflow(raw, offset, source_kind):
    source = pl.Series("time", [raw], dtype=pl.Datetime("us")) if source_kind == "polars" else np.array([raw], dtype="datetime64[us]")
    result = Pldt(source, unit="ns", tz=timezone(timedelta(hours=offset)))
    assert ticks(result) == [raw * 1000 - offset * 3_600_000_000_000]
    assert result.dtype == pl.Datetime("ns", f"Etc/GMT{'-' if offset > 0 else '+'}{abs(offset)}")


@pytest.mark.parametrize("source,expected_dtype,expected", [
    (pl.Series("time", [1, None], dtype=pl.Datetime("us", "UTC")), pl.Datetime("us", "UTC"), [1, None]),
    (pl.Series("time", [0, None], dtype=pl.Date), pl.Datetime("ms"), [0, None]),
    (pl.Series("time", [1, None], dtype=pl.Int64), pl.Datetime("ns"), [1, None]),
    (pl.Series("time", [1.0, float("nan")]), pl.Datetime("ns"), [1, None]),
    (pl.Series("time", [None], dtype=pl.Null), pl.Datetime("ms"), [None]),
])
def test_native_expr_schema_selects_unit_without_text_sampling(source, expected_dtype, expected):
    query = pl.DataFrame(source).lazy().select(pl.col("time").pldt.parse())
    assert query.collect_schema()["time"] == expected_dtype
    assert ticks(query.collect()["time"]) == expected


def test_native_expr_numeric_and_naive_date_target_roles():
    source = pl.DataFrame({"time": pl.Series([0], dtype=pl.Int64)})
    result = source.select(pl.col("time").pldt.parse(unit="us", tz="Asia/Shanghai"))["time"]
    assert ticks(result) == [0]
    source = pl.DataFrame({"time": pl.Series([0], dtype=pl.Datetime("us"))})
    result = source.select(pl.col("time").pldt.parse(tz="Asia/Shanghai"))["time"]
    assert ticks(result) == [-28_800_000_000]


def test_native_string_constructor_uses_native_column_core(monkeypatch):
    module = importlib.import_module("rstimes.pldt")
    def forbidden(*args, **kwargs):
        raise AssertionError("native String data must not enter Python-object iteration")
    monkeypatch.setattr(module, "_pldt_objects", forbidden)
    result = Pldt(pl.Series("time", ["1970-01-01 00:00:00.000000001", "", None]))
    assert result.dtype == pl.Datetime("ns")
    assert ticks(result) == [1, None, None]


def test_parse_class_series_and_expr_return_native_responsible_types():
    source = pl.Series("time", ["2024-01-01", None])
    assert type(Pldt.parse(source)) is Pldt
    assert type(source.pldt.parse()) is Pldt
    expr = pl.col("time").pldt.parse(unit="us")
    assert isinstance(expr, pl.Expr)
    query = pl.DataFrame(source).lazy().select(expr)
    assert query.collect_schema()["time"] == pl.Datetime("us")
    assert type(query.collect()["time"]) is pl.Series
    assert ticks(query.collect()["time"]) == [tick("2024-01-01"), None]


def test_generic_expr_requires_static_unit_and_explicit_aware_target():
    with pytest.raises(pl.exceptions.ComputeError, match="unit"):
        pl.DataFrame({"time": ["2024-01-01"]}).lazy().select(pl.col("time").pldt.parse()).collect_schema()
    cfg = registered()
    source = pl.DataFrame({"time": ["2024-01-01 12:00 America/New_York"]})
    expr = pl.col("time").pldt.parse(unit="us", cfg=cfg)
    with pytest.raises(pl.exceptions.ComputeError, match="tz|target"):
        source.select(expr)
    expr = pl.col("time").pldt.parse(unit="us", cfg=cfg, tz="UTC")
    assert ticks(source.select(expr)["time"]) == [tick("2024-01-01T17:00")]


def test_expr_rules_are_creation_snapshot_and_eager_reads_current_rules():
    cfg = Configs()
    cfg.add_month("jan", 2)
    source = pl.DataFrame({"time": ["14 Jan 2024"]})
    expr = pl.col("time").pldt.parse(unit="us", cfg=cfg)
    cfg.add_month("jan", 3)
    assert ticks(source.select(expr)["time"]) == [tick("2024-02-14")]
    assert ticks(source.select(expr)["time"]) == [tick("2024-02-14")]
    assert ticks(source["time"].pldt.parse(cfg=cfg)) == [tick("2024-03-14")]


@pytest.mark.parametrize("expression,expected", [(False, "2024-02-14T12:30"), (True, "2024-01-14T12:30")])
def test_public_default_callback_and_configs_snapshot_order(expression, expected):
    cfg = Configs()
    calls = []

    class Reference(str):
        def __str__(self):
            calls.append("default")
            cfg.set_month({"jan": 2})
            return "14 Jan 2024"

    default = Reference("reference")
    source = pl.Series("time", ["12:30", "12:30"])
    if expression:
        expr = pl.col("time").pldt.parse(unit="us", default=default, cfg=cfg)
        cfg.set_month({"jan": 8})
        for _ in range(2):
            assert ticks(pl.DataFrame(source).select(expr)["time"]) == [tick(expected)] * 2
    else:
        assert ticks(source.pldt.parse(default=default, cfg=cfg)) == [tick(expected)] * 2
    assert calls == ["default"]


def test_native_eager_dates_ignore_unrelated_default():
    class InvalidDefault:
        pass
    source = pl.Series("time", [1], dtype=pl.Datetime("ns"))
    assert ticks(Pldt(source, default=InvalidDefault(), tz="UTC")) == [1]


def test_parse_empty_and_allmissing_do_not_read_irrelevant_eager_default():
    class InvalidDefault:
        pass
    for values in ([], ["", None]):
        result = Pldt(pl.Series("time", values, dtype=pl.String), default=InvalidDefault())
        assert result.dtype == pl.Datetime("ms")
        assert ticks(result) == [None] * len(values)
    with pytest.raises(TypeError):
        pl.col("time").pldt.parse(unit="us", default=InvalidDefault())


def test_parse_masks_span_source_nulls_and_original_chunk_order():
    source = pl.concat([pl.Series("time", ["2024-11-03 01:00", "2024-11-03 01:30"]),
                        pl.Series("time", ["2024-11-03 01:00", "2024-11-03 01:30"])], rechunk=False)
    expr = pl.col("time").pldt.parse(unit="us", tz="America/New_York", ambiguous="infer")
    assert ticks(pl.DataFrame(source).lazy().select(expr).collect(engine="streaming")["time"]) == [tick(text) for text in (
        "2024-11-03T05:00", "2024-11-03T05:30", "2024-11-03T06:00", "2024-11-03T06:30")]


def test_parse_boolean_expr_mask_preserves_aggregate_and_vector_roles():
    source = pl.DataFrame({"time": ["2024-11-03 01:30"] * 2, "choice": [True, False]})
    expr = pl.col("time").pldt.parse(unit="us", tz="America/New_York", ambiguous=pl.col("choice"))
    assert ticks(source.select(expr)["time"]) == [tick("2024-11-03T05:30"), tick("2024-11-03T06:30")]
    expr = pl.col("time").pldt.parse(unit="us", tz="America/New_York", ambiguous=pl.col("choice").any())
    assert ticks(source.select(expr)["time"]) == [tick("2024-11-03T05:30")] * 2
    expr = pl.col("time").pldt.parse(unit="us", tz="America/New_York", ambiguous=pl.col("choice").head(1))
    with pytest.raises(pl.exceptions.ComputeError, match="length"):
        source.select(expr)


@pytest.mark.parametrize("unit,expected", [("ns", 123456789), ("us", 123456), ("ms", 123)])
def test_strptime_truncates_only_at_explicit_final_output(unit, expected):
    text = "1970-01-01 00:00:00.1234567899"
    fmt = "%Y-%m-%d %H:%M:%S.%f"
    result = Pldt.strptime(text, fmt, size=2, unit=unit)
    assert type(result) is Pldt and result.dtype == pl.Datetime(unit)
    assert ticks(result) == [expected, expected]
    source = pl.DataFrame({"time": [text, None]})
    expr = pl.col("time").pldt.strptime(fmt, unit=unit)
    assert ticks(source.select(expr)["time"]) == [expected, None]


def test_strptime_negative_epoch_and_static_format_roles():
    source = pl.DataFrame({"time": ["1969-12-31 23:59:59.9999999999"]})
    fmt = "%Y-%m-%d %H:%M:%S.%f"
    assert ticks(source["time"].pldt.strptime(fmt, unit="us")) == [-1]
    with pytest.raises(ValueError, match="unit"):
        pl.col("time").pldt.strptime(fmt)
    expr = pl.col("time").pldt.strptime("%Y-%m-%d")
    assert pl.DataFrame({"time": ["0000-01-01"]}).lazy().select(expr).collect_schema()["time"] == pl.Datetime("us")


def test_strptime_registered_zone_explicit_target_and_missing_static_target():
    cfg = registered()
    fmt = "%Y-%m-%d %H:%M %Z"
    source = pl.DataFrame({"time": ["2024-01-01 12:00 America/New_York"]})
    with pytest.raises(ValueError, match="tz"):
        pl.col("time").pldt.strptime(fmt, cfg=cfg)
    expr = pl.col("time").pldt.strptime(fmt, cfg=cfg, tz="UTC")
    assert ticks(source.select(expr)["time"]) == [tick("2024-01-01T17:00")]
    assert ticks(Pldt.strptime(source["time"], fmt, cfg=cfg, tz="UTC")) == [tick("2024-01-01T17:00")]


def test_formatted_snapshot_custom_words_and_ordinary_numeric_no_locale(monkeypatch):
    module = importlib.import_module("rstimes._formatting")
    def forbidden(*args, **kwargs):
        raise AssertionError("numeric formats must not query locale")
    monkeypatch.setattr(module._locale, "setlocale", forbidden)
    assert ticks(Pldt.strptime(["0000-01-01", "-0001-01-01", "12000-01-01"], "%Y-%m-%d")) == [tick(text) for text in ("0000-01-01", "-0001-01-01", "12000-01-01")]
    cfg = Configs()
    cfg.add_month("specialmonth", 2)
    expr = pl.col("time").pldt.strptime("%d %B %Y", cfg=cfg)
    cfg.add_month("specialmonth", 3)
    source = pl.DataFrame({"time": ["14 specialmonth 2024"]})
    assert ticks(source.select(expr)["time"]) == [tick("2024-02-14")]
    assert ticks(source["time"].pldt.strptime("%d %B %Y", cfg=cfg)) == [tick("2024-03-14")]


def test_strptime_rejects_nontext_and_trailing_or_invalid_fields():
    for values in ([1], [datetime(2024, 1, 1)]):
        with pytest.raises(TypeError):
            Pldt.strptime(values, "%Y-%m-%d")
    for text in ("2024-02-30", "2024-01-01 trailing"):
        with pytest.raises(ValueError):
            Pldt.strptime([text], "%Y-%m-%d")


def test_formatted_scalar_repeat_applies_full_boolean_mask_after_parsing_once():
    calls = []

    class Text(str):
        def __str__(self):
            calls.append("text")
            return "2024-11-03 01:30"

    result = Pldt.strptime(Text("ignored"), "%Y-%m-%d %H:%M", size=2,
                          tz="America/New_York", ambiguous=[True, False])
    assert ticks(result) == [tick("2024-11-03T05:30"), tick("2024-11-03T06:30")]
    assert calls == ["text"]


def test_formatted_explicit_missing_values_propagate_without_numeric_coercion():
    result = Pldt.strptime([None, float("nan"), np.float64("nan"), np.datetime64("NaT"), "NaT"], "%Y-%m-%d")
    assert result.dtype == pl.Datetime("us")
    assert ticks(result) == [None] * 5
    with pytest.raises(TypeError):
        Pldt.strptime([True], "%Y-%m-%d")


def test_current_parser_and_pydt_outputs_are_not_changed_by_column_targets():
    from rstimes import Pydt, parse_str, parse_to_epoch
    text = "2024-01-02 12:34:56.123456789"
    assert parse_str(text).microsecond == 123456
    assert Pydt.parse(text).microsecond == 123456
    assert parse_to_epoch(text, unit="ns") == 1704198896123456789


def test_failed_parse_and_format_leave_source_and_valid_prefix_unmodified():
    source = pl.Series("time", ["2024-01-01", "invalid", None])
    for operation in (lambda: source.pldt.parse(), lambda: source.pldt.strptime("%Y-%m-%d")):
        with pytest.raises(ValueError):
            operation()
        assert source.to_list() == ["2024-01-01", "invalid", None]


def test_factory_subclass_uses_one_normal_business_constructor():
    calls = []

    class Business(Pldt):
        def __init__(self, *args, **kwargs):
            calls.append("construct")
            super().__init__(*args, **kwargs)

    result = Business.strptime("2024-01-01", "%Y-%m-%d", size=2)
    assert type(result) is Business and calls == ["construct"]
    assert ticks(result) == [tick("2024-01-01")] * 2
    calls.clear()
    parsed = result.pldt.parse()
    assert type(parsed) is Business and calls == ["construct"]
    assert ticks(parsed) == ticks(result)


@pytest.mark.parametrize("operation,entry", [
    (lambda: Pldt.parse(["invalid"]), "Pldt.parse"),
    (lambda: pl.Series("time", ["invalid"]).pldt.parse(), "Pldt.parse"),
    (lambda: Pldt.strptime(["invalid"], "%Y-%m-%d"), "Pldt.strptime"),
])
def test_own_parse_failures_include_exact_public_entry_and_known_input(operation, entry):
    with pytest.raises(ValueError) as caught:
        operation()
    message = str(caught.value)
    assert entry in message and "invalid" in message
