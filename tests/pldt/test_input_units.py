"""Independent physical-integer expectations for native input and unit roles."""

from datetime import date, datetime
import gc
import numpy as np
import polars as pl
import pytest

from rstimes import Pldt


def ticks(value):
    return value.to_physical().to_list()


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_numeric_full_int64_and_independent_null(unit):
    values = [-(2**63), -1, None, 0, 2**63 - 1]
    result = Pldt(values, unit=unit, name="events")
    assert isinstance(result, Pldt)
    assert result.dtype == pl.Datetime(unit)
    assert result.name == "events"
    assert ticks(result) == values


@pytest.mark.parametrize("factory", [list, tuple, iter, lambda x: np.array(x, dtype=np.int64), lambda x: pl.Series("t", x)])
def test_one_dimensional_numeric_sources(factory):
    result = Pldt(factory([0, 1, -1]))
    assert result.dtype == pl.Datetime("ns")
    assert ticks(result) == [0, 1, -1]


@pytest.mark.parametrize("data", [[], [None, None], ["", "NaT", "nan"], pl.Series([], dtype=pl.String), pl.Series([None], dtype=pl.Null)])
def test_missing_only_without_resolution_defaults_ms(data):
    result = Pldt(data)
    assert result.dtype == pl.Datetime("ms")
    assert ticks(result) == [None] * len(data)


@pytest.mark.parametrize("data", [np.array([], dtype=np.float64), np.array([np.nan]), pl.Series([], dtype=pl.Int64)])
def test_declared_numeric_empty_and_nan_keep_ns(data):
    result = Pldt(data)
    assert result.dtype == pl.Datetime("ns")
    assert ticks(result) == [None] * len(data)


@pytest.mark.parametrize("source,unit,expected", [
    (np.array([1, -1, -(2**63)], dtype="datetime64[s]"), "ms", [1000, -1000, None]),
    (np.array([1, -1, -(2**63)], dtype="datetime64[us]"), "us", [1, -1, None]),
    (np.array([0, 1], dtype="datetime64[D]"), "ms", [0, 86400000]),
    (np.array([0, 1], dtype="datetime64[M]"), "ms", [0, 2678400000]),
    (pl.Series("d", [date(1970, 1, 1), None], dtype=pl.Date), "ms", [0, None]),
    ([datetime(1970, 1, 1, microsecond=1)], "us", [1]),
    ([date(1970, 1, 2)], "ms", [86400000]),
    ([None, np.datetime64("NaT", "ns")], "ns", [None, None]),
])
def test_native_source_precision(source, unit, expected):
    result = Pldt(source)
    assert result.dtype == pl.Datetime(unit)
    assert ticks(result) == expected


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_typed_empty_and_null_datetime_keep_metadata(unit):
    for values in ([], [None, None]):
        source = pl.Series("events", values, dtype=pl.Datetime(unit, "Asia/Shanghai"))
        result = Pldt(source)
        assert result.dtype == source.dtype
        assert result.name == source.name
        assert ticks(result) == values


def test_explicit_unit_is_lossless_and_final_capacity_checked():
    source = pl.Series("t", [1000, -1000, None], dtype=pl.Datetime("ns"))
    assert ticks(Pldt(source, unit="us")) == [1, -1, None]
    with pytest.raises(ValueError, match="unit|precision|loss"):
        Pldt(pl.Series([1500], dtype=pl.Datetime("ns")), unit="us")
    with pytest.raises(OverflowError):
        Pldt(np.array([(2**63 - 1) // 1000 + 1], dtype="datetime64[s]"))
    with pytest.raises(OverflowError):
        Pldt(np.array(["2500-01-01"], dtype="datetime64[us]"), unit="ns")


@pytest.mark.parametrize("round_ok,expected", [(True, [1, -2, None]), (False, None)])
def test_as_unit_floor_and_lossless(round_ok, expected):
    source = Pldt(pl.Series("t", [1500, -1500, None], dtype=pl.Datetime("ns")))
    if expected is None:
        with pytest.raises(ValueError):
            source.as_unit("us", round_ok=round_ok)
    else:
        result = source.as_unit("us", round_ok=round_ok)
        assert result.dtype == pl.Datetime("us")
        assert ticks(result) == expected
    assert ticks(source) == [1500, -1500, None]


def test_as_unit_expr_schema_and_no_dst_reinterpretation():
    source = pl.Series("t", [1500, -1500, None], dtype=pl.Datetime("ns", "UTC"))
    query = pl.DataFrame(source).lazy().select(pl.col("t").pldt.as_unit("us"))
    assert query.collect_schema()["t"] == pl.Datetime("us", "UTC")
    assert ticks(query.collect()["t"]) == [1, -2, None]


def test_copy_isolation_and_independent_mutable_shell():
    raw = np.array([1, 2], dtype=np.int64)
    source = pl.Series("t", raw, dtype=pl.Datetime("ns"))
    result = Pldt(source, copy=True)
    raw[0] = 9
    assert ticks(result) == [1, 2]
    borrowed = Pldt(source, copy=False)
    source.append(pl.Series("t", [3], dtype=source.dtype))
    assert len(borrowed) == 2
    shell = pl.Series(borrowed)
    shell.append(pl.Series("t", [4], dtype=shell.dtype))
    assert len(borrowed) == 2
    del source, raw
    gc.collect()
    assert ticks(borrowed) == [9, 2]


def test_chunks_stride_and_byte_order():
    source = pl.concat([pl.Series("t", [1, None], dtype=pl.Datetime("ns")), pl.Series("t", [2], dtype=pl.Datetime("ns"))], rechunk=False)
    result = Pldt(source.slice(1, 2))
    assert ticks(result) == [None, 2]
    assert ticks(Pldt(np.arange(6, dtype=np.int64)[::2])) == [0, 2, 4]
    assert ticks(Pldt(np.array([1, -1], dtype=">i8"))) == [1, -1]
    assert ticks(Pldt(np.array([1, -1], dtype=">M8[us]"))) == [1, -1]


@pytest.mark.parametrize("data", [{"1970-01-01": 1}, {1, 2}, frozenset([1]), [[1]], pl.Series([[1]]), pl.DataFrame({"t": [1]}), pl.LazyFrame({"t": [1]}), pl.col("t"), "1970-01-01", datetime(1970, 1, 1), None])
def test_unsupported_outer_or_nested_is_type_error(data):
    with pytest.raises(TypeError):
        Pldt(data)


@pytest.mark.parametrize("data", [np.array(1), np.array([[1]])])
def test_numpy_dimension_is_value_error(data):
    with pytest.raises(ValueError):
        Pldt(data)


@pytest.mark.parametrize("value,error", [(True, TypeError), (np.bool_(False), TypeError), (1.5, ValueError), (float("inf"), OverflowError), (b"1970", TypeError)])
def test_numeric_and_element_roles(value, error):
    with pytest.raises(error):
        Pldt([value])


def test_index_protocol_is_read_once():
    class Index:
        calls = 0
        def __index__(self):
            self.calls += 1
            return 1
    value = Index()
    assert ticks(Pldt([value], unit="us")) == [1]
    assert value.calls == 1


def test_generator_and_actual_iterator_are_obtained_once():
    class Once:
        def __init__(self):
            self.calls = 0
            self.items = iter([0, 1])
        def __iter__(self):
            self.calls += 1
            if self.calls > 1:
                raise RuntimeError("iterator requested twice")
            return self
        def __next__(self):
            return next(self.items)
    source = Once()
    assert ticks(Pldt(source)) == [0, 1]
    assert source.calls == 1


def test_real_iterator_failure_is_preserved():
    error = TypeError("business iterator failed")
    class Broken:
        def __iter__(self):
            raise error
    with pytest.raises(TypeError) as captured:
        Pldt(Broken())
    assert captured.value is error


def test_business_result_has_one_normal_constructor():
    class Business(Pldt):
        calls = 0
        def __init__(self, data, **kwargs):
            Business.calls += 1
            super().__init__(data, **kwargs)
            self.checked = True
    source = Business([datetime(2024, 1, 31)])
    Business.calls = 0
    result = source.to_next_month()
    assert type(result) is Business and result.checked
    assert Business.calls == 1
    assert ticks(result) == [1709164800000000]
    Business.calls = 0
    result = source.pldt.as_unit("ns")
    assert type(result) is Business
    assert Business.calls == 1


def test_slice_retains_column_precision_and_native_scalar_return():
    source = Pldt([1704067200123456789, None], unit="ns")
    result = source[:1]
    assert isinstance(result, Pldt)
    assert ticks(result) == [1704067200123456789]
    assert type(source[0]) is datetime
    assert source[0].microsecond == 123456
    assert source[1] is None


@pytest.mark.parametrize("kind", [np.bool_, np.complex128, "timedelta64[us]", "S10"])
def test_unsupported_declared_empty_dtype_is_rejected(kind):
    with pytest.raises(TypeError):
        Pldt(np.array([], dtype=kind))


def test_optional_pandas_datetime_and_extension_sources():
    pd = pytest.importorskip("pandas")
    source = pd.DatetimeIndex(np.array([1, -(2**63)], dtype="datetime64[s]"), name="events").tz_localize("UTC")
    result = Pldt(source)
    assert result.dtype == pl.Datetime("ms", "UTC")
    assert result.name == "events"
    assert ticks(result) == [1000, None]
    assert Pldt(pd.Series([], dtype="Int64")).dtype == pl.Datetime("ns")


def test_naive_input_text_precision_and_independent_default():
    source = Pldt(["2024-01-01 00:00:00.123456000"])
    assert source.dtype == pl.Datetime("ns")
    assert ticks(source) == [1704067200123456000]
    result = Pldt(["12:30", "18:45"], default="2024-05-07")
    assert ticks(result) == [1715085000000000, 1715107500000000]
    assert Pldt([], default="May 7").dtype == pl.Datetime("ms")
    with pytest.raises(ValueError):
        Pldt(["2024-05-07"], default="May 7")


@pytest.mark.parametrize("factory", [list, tuple, iter, lambda x: np.array(x), lambda x: pl.Series(x)])
def test_integer_row_arguments_share_strict_shape(factory):
    source = Pldt([0, 0], unit="us")
    assert ticks(source.pldt.add(days=factory([1, 2]))) == [86400000000, 172800000000]
    with pytest.raises((ValueError, pl.exceptions.ShapeError, pl.exceptions.ComputeError)):
        source.pldt.add(days=factory([1]))


def test_index_role_precedes_iteration_for_scalar_argument():
    class Both:
        def __index__(self):
            return 1
        def __iter__(self):
            raise AssertionError("scalar index role must not iterate")
    assert ticks(Pldt([0], unit="us").pldt.add(days=Both())) == [86400000000]


def test_native_date_namespace_promotes_midnight_without_parsing():
    source = pl.Series("t", [date(2024, 1, 31), None], dtype=pl.Date)
    result = source.pldt.to_next_month()
    assert isinstance(result, Pldt)
    assert result.dtype == pl.Datetime("ms")
    assert ticks(result) == [1709164800000, None]
    query = pl.DataFrame(source).lazy().select(pl.col("t").pldt.to_next_month())
    assert query.collect_schema()["t"] == pl.Datetime("ms")
    assert ticks(query.collect()["t"]) == [1709164800000, None]


def test_valid_extreme_unit_conversion_and_capacity():
    source = Pldt([-(2**63), 2**63 - 1, None], unit="ns")
    assert ticks(source.as_unit("us")) == [-9223372036854776, 9223372036854775, None]
    with pytest.raises(OverflowError):
        Pldt([2**63 - 1], unit="us").as_unit("ns")
    with pytest.raises(OverflowError):
        Pldt(np.array([2**63], dtype=np.uint64))
    for value in (1, "yes", None):
        with pytest.raises(TypeError):
            source.as_unit("us", round_ok=value)
    assert ticks(source.as_unit("us", round_ok=np.bool_(True))) == [-9223372036854776, 9223372036854775, None]


def test_zero_negative_and_wide_year_native_sources_stay_integer():
    raw = np.array(["0000-01-01", "-0001-12-31", "12000-01-01", "1000000-01-01"], dtype="datetime64[ms]")
    source = Pldt(raw)
    assert source.dtype == pl.Datetime("ms")
    assert ticks(source) == raw.view(np.int64).tolist()
    assert isinstance(source[:1], Pldt)
    with pytest.raises(ValueError):
        source[0]


def test_pandas_empty_boolean_and_duration_are_not_missing_dates():
    pd = pytest.importorskip("pandas")
    for value in (pd.Series([], dtype="boolean"), pd.Series([], dtype="timedelta64[ns]")):
        with pytest.raises(TypeError):
            Pldt(value)


def test_legacy_sequence_integer_argument_is_not_mistaken_for_scalar():
    class Sequence:
        def __getitem__(self, index):
            return [1, 2][index]
    assert ticks(Pldt([0, 0], unit="ms").pldt.add(days=Sequence())) == [86400000, 172800000]


@pytest.mark.parametrize("code,unit,factor", [("Y", "ms", 31536000000), ("M", "ms", 2678400000), ("W", "ms", 604800000), ("D", "ms", 86400000), ("h", "ms", 3600000), ("m", "ms", 60000), ("s", "ms", 1000), ("ms", "ms", 1), ("us", "us", 1), ("ns", "ns", 1)])
def test_all_ten_numpy_date_units_and_declared_missing(code, unit, factor):
    source = np.array([0, 1, -1, -(2**63)], dtype=f"datetime64[{code}]")
    result = Pldt(source)
    assert result.dtype == pl.Datetime(unit)
    assert ticks(result) == [0, factor, -factor, None]
    assert Pldt(source[:0]).dtype == pl.Datetime(unit)


def test_numpy_multiplier_and_generic_missing():
    assert ticks(Pldt(np.array([1, -1], dtype="datetime64[3us]"))) == [3, -3]
    assert Pldt(np.array(["NaT"], dtype="datetime64")).dtype == pl.Datetime("ms")


def test_numpy_float_roles_follow_real_type_identity():
    for kind in (np.float16, np.float32, np.float64):
        assert ticks(Pldt(np.array([1.0, -1.0, np.nan], dtype=kind))) == [1, -1, None]
    if np.longdouble is np.float64:
        assert ticks(Pldt(np.array([1.0], dtype=np.longdouble))) == [1]
    else:
        for values in ([], [1.0]):
            with pytest.raises(TypeError):
                Pldt(np.array(values, dtype=np.longdouble))


@pytest.mark.parametrize("option,value,error", [("unit", "s", ValueError), ("unit", 1, TypeError), ("copy", 1, TypeError), ("strict", 1, TypeError), ("isoformat", 1, TypeError), ("name", 1, TypeError), ("cfg", object(), TypeError)])
def test_empty_still_checks_actual_options(option, value, error):
    with pytest.raises(error):
        Pldt([], **{option: value})
