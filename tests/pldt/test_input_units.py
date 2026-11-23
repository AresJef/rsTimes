"""Independent physical-integer expectations for native input and unit roles."""

from array import array
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


@pytest.mark.parametrize("dtype,bad", [
    (pl.UInt64, 2**63), (pl.UInt128, 2**63 + 1),
    (pl.Int128, -(2**63) - 1), (pl.Int128, 2**63),
])
def test_wide_native_integer_rejects_first_bad_tick_with_position(dtype, bad):
    source = pl.concat([
        pl.Series("raw", [None, 1], dtype=dtype),
        pl.Series("raw", [bad, None, bad], dtype=dtype),
    ], rechunk=False)
    assert source.n_chunks() == 2
    for data, row in ((source, 2), (source.slice(2), 0)):
        with pytest.raises(OverflowError, match=rf"^Pldt\(\): data\[{row}\]: numeric date tick exceeds signed64$"):
            Pldt(data, unit="ns")
    assert source.to_list() == [None, 1, bad, None, bad]


@pytest.mark.parametrize("dtype,first", [(pl.UInt64, 0), (pl.UInt128, 0), (pl.Int128, -(2**63)), (pl.Int16, -1)])
@pytest.mark.parametrize("copy", [False, True])
def test_wide_and_narrow_native_integer_keep_endpoints_and_nulls(dtype, first, copy):
    last = 2**15 - 1 if dtype == pl.Int16 else 2**63 - 1
    source = pl.concat([
        pl.Series("event", [first, None], dtype=dtype),
        pl.Series("event", [last], dtype=dtype),
    ], rechunk=False)
    result = Pldt(source, unit="ns", copy=copy)
    assert (result.name, result.dtype, ticks(result)) == ("event", pl.Datetime("ns"), [first, None, last])
    assert result.is_null().to_list() == [False, True, False]


def test_wide_unsigned_owned_ticks_do_not_alias_numpy_input():
    raw = np.array([1, 2, 2**63 - 1], dtype=np.uint64)
    source = pl.Series("event", raw)
    assert np.shares_memory(source.to_numpy(allow_copy=False), raw)
    copied = Pldt(source, unit="ns", copy=True)
    raw[0] = 5
    assert source[0] == 5
    assert (copied.name, ticks(copied)) == ("event", [1, 2, 2**63 - 1])


@pytest.mark.parametrize("dtype,type_code", [
    (pl.Int8, "b"), (pl.Int16, "h"), (pl.Int32, "i"), (pl.UInt64, "Q"),
])
@pytest.mark.parametrize("layout", ["unsliced", "bit_offset", "two_chunks"])
def test_owned_integer_ticks_keep_the_validity_used_during_conversion(layout, dtype, type_code):
    pa = pytest.importorskip("pyarrow")
    bitmap = bytearray([0b1101])
    values = array(type_code, [81, 17, 53, 24])
    arrow = pa.Array.from_buffers(
        pa.type_for_alias(str(dtype).lower()), 4, [pa.py_buffer(bitmap), pa.py_buffer(values)], null_count=1
    )
    raw = pl.from_arrow(arrow, rechunk=False).rename("raw")
    source = raw
    before = [81, None, 53, 24]
    after = [81, 97, None, 24]
    if layout == "bit_offset":
        source = raw.slice(1, 3)
        before, after = before[1:], after[1:]
    elif layout == "two_chunks":
        prefix = [99, None]
        source = pl.concat([pl.Series("raw", prefix, dtype=dtype), raw], rechunk=False)
        assert source.n_chunks() == 2
        before, after = prefix + before, prefix + after

    frame = source.to_frame()
    expr = pl.col("raw").pldt.parse(unit="ns")
    lazy = frame.lazy().select(expr)
    assert lazy.collect_schema()["raw"] == pl.Datetime("ns")
    results = {
        "constructor": Pldt(source, unit="ns"),
        "copy_false": Pldt(source, unit="ns", copy=False),
        "copy_true": Pldt(source, unit="ns", copy=True),
        "factory": Pldt.parse(source, unit="ns"),
        "accessor": source.pldt.parse(unit="ns"),
        "select": frame.select(expr)["raw"],
        "collect": lazy.collect()["raw"],
    }
    assert source.to_list() == before
    assert all(ticks(result) == before for result in results.values())

    values[1] = 97
    assert source.to_list() == before
    assert all(ticks(result) == before for result in results.values())

    bitmap[0] = 0b1011
    assert source.to_list() == after
    assert ticks(Pldt(source, unit="ns")) == after
    for entry, result in results.items():
        assert (result.name, result.dtype) == ("raw", pl.Datetime("ns")), entry
        assert ticks(result) == before, entry
        assert result.is_null().to_list() == [value is None for value in before], entry


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


@pytest.mark.parametrize("dtype,values,expected", [
    (pl.Datetime("ns", "UTC"), [1500, -1500, None], [1, -2, None]),
    (pl.Datetime("ns", "UTC"), [-(2**63), -1500, 2**63 - 1],
     [-(2**63) // 1000, -2, (2**63 - 1) // 1000]),
    (pl.Date, [date(1969, 12, 31), None], [-86_400_000_000, None]),
])
def test_as_unit_expr_schema_and_no_dst_reinterpretation(dtype, values, expected):
    source = pl.Series("t", values, dtype=dtype)
    frame = source.to_frame()
    expr = pl.col("t").pldt.as_unit("us")
    zone = "UTC" if dtype == pl.Datetime("ns", "UTC") else None
    target = pl.Datetime("us", zone)
    query = frame.lazy().select(expr)
    assert query.collect_schema()["t"] == target
    for result in (frame.select(expr)["t"], query.collect()["t"]):
        assert (result.dtype, result.name, ticks(result)) == (target, "t", expected)


@pytest.mark.parametrize("entry", ["Pldt.as_unit", "Series.pldt.as_unit", "Expr.pldt.as_unit"])
def test_as_unit_reports_the_public_round_ok_argument(entry):
    source = pl.Series("event", [1000, -1500, None], dtype=pl.Datetime("ns"))
    convert = {
        "Pldt.as_unit": Pldt(source).as_unit,
        "Series.pldt.as_unit": source.pldt.as_unit,
        "Expr.pldt.as_unit": pl.col("event").pldt.as_unit,
    }[entry]

    with pytest.raises(TypeError) as error:
        convert("us", round_ok=1)  # type: ignore[arg-type]
    message = str(error.value)
    assert message.startswith(f"{entry}()")
    assert "round_ok" in message

    for round_ok in (True, np.bool_(True)):
        result = convert("us", round_ok=round_ok)
        if isinstance(result, pl.Expr):
            frame = source.to_frame()
            assert ticks(frame.select(result)["event"]) == [1, -2, None]
            query = frame.lazy().select(result)
            assert query.collect_schema()["event"] == pl.Datetime("us")
            result = query.collect()["event"]
        assert (result.name, result.dtype, ticks(result)) == (
            "event", pl.Datetime("us"), [1, -2, None],
        )


@pytest.mark.parametrize("zone", [None, "UTC"])
@pytest.mark.parametrize(("via_namespace", "entry"), [
    (False, "Pldt.as_unit"),
    (True, "Series.pldt.as_unit"),
])
def test_as_unit_eager_reports_the_operation_and_rescale_failure(zone, via_namespace, entry):
    def convert(source, unit, *, round_ok):
        owner = source.pldt if via_namespace else Pldt(source)
        return owner.as_unit(unit, round_ok=round_ok)

    fine = pl.Series("event", [1000, -1500, None], dtype=pl.Datetime("ns", zone))
    with pytest.raises(ValueError) as precision:
        convert(fine, "us", round_ok=False)
    message = str(precision.value)
    assert message.startswith(f"{entry}(): data[1]:")
    assert "'us'" in message and "precision" in message and "round_ok=True" in message
    rounded = convert(fine, "us", round_ok=True)
    assert type(rounded) is Pldt
    assert (rounded.name, rounded.dtype, ticks(rounded)) == (
        "event", pl.Datetime("us", zone), [1, -2, None],
    )
    exact = pl.Series("event", [1000, -2000, None], dtype=fine.dtype)
    assert ticks(convert(exact, "us", round_ok=False)) == [1, -2, None]
    assert (fine.name, fine.dtype, ticks(fine)) == ("event", exact.dtype, [1000, -1500, None])

    limit = (2**63 - 1) // 1000
    coarse = pl.Series("event", [1, None, limit + 1], dtype=pl.Datetime("us", zone))
    for round_ok in (False, True):
        with pytest.raises(OverflowError) as capacity:
            convert(coarse, "ns", round_ok=round_ok)
        message = str(capacity.value)
        assert message.startswith(f"{entry}(): data[2]:")
        assert "'ns'" in message and "capacity" in message and "coarser" in message
        assert "round_ok=True" not in message
    assert ticks(convert(coarse, "us", round_ok=False)) == [1, None, limit + 1]
    within = pl.Series("event", [1, None, limit], dtype=coarse.dtype)
    assert ticks(convert(within, "ns", round_ok=False)) == [1000, None, limit * 1000]

    with pytest.raises(ValueError, match=r"^Pldt\(\): data\[1\].*explicitly use as_unit"):
        Pldt(fine, unit="us")
    with pytest.raises(OverflowError, match=r"^Pldt\(\): data\[2\].*capacity"):
        Pldt(coarse, unit="ns")


def test_as_unit_role_is_preserved_for_both_entrances_on_one_pldt():
    source = Pldt([1000, -1500, None], unit="ns")
    for owner, entry in ((source, "Pldt.as_unit"), (source.pldt, "Series.pldt.as_unit")):
        with pytest.raises(ValueError) as captured:
            owner.as_unit("us", round_ok=False)
        assert str(captured.value).startswith(f"{entry}(): data[1]:")


def test_native_as_unit_keeps_minimum_tick_distinct_from_null_across_chunks():
    minimum = -(2**63)
    dtype = pl.Datetime("ns")
    source = pl.concat([
        pl.Series("event", [1000, -2000, None], dtype=dtype),
        pl.Series("event", [minimum], dtype=dtype),
    ], rechunk=False)
    assert source.n_chunks() == 2
    for owner, entry in ((Pldt(source), "Pldt.as_unit"), (source.pldt, "Series.pldt.as_unit")):
        result = owner.as_unit("us")
        assert (result.name, result.dtype, ticks(result)) == (
            "event", pl.Datetime("us"), [1, -2, None, minimum // 1000],
        )
        with pytest.raises(ValueError) as captured:
            owner.as_unit("us", round_ok=False)
        assert str(captured.value).startswith(f"{entry}(): data[3]:")
    empty = source.slice(0, 0).pldt.as_unit("us", round_ok=False)
    assert (empty.name, empty.dtype, ticks(empty)) == ("event", pl.Datetime("us"), [])
    assert ticks(source) == [1000, -2000, None, minimum]


def test_native_cross_unit_constructor_interprets_naive_ticks_in_the_requested_zone():
    source = pl.Series("event", [0, None], dtype=pl.Datetime("ns"))
    result = Pldt(source, tz="Asia/Tokyo", unit="us")
    assert (result.name, result.dtype, ticks(result)) == (
        "event", pl.Datetime("us", "Asia/Tokyo"), [-32_400_000_000, None],
    )
    with pytest.raises(ValueError, match="length"):
        Pldt(source, unit="us", ambiguous=[True])


@pytest.mark.parametrize("zone", [None, "UTC"])
def test_dense_eager_as_unit_preserves_rounding_and_first_error_across_chunks(zone):
    source = pl.concat([
        pl.Series("event", [-1000, 1000], dtype=pl.Datetime("ns", zone)),
        pl.Series("event", [-1500], dtype=pl.Datetime("ns", zone)),
    ], rechunk=False)
    assert source.n_chunks() == 2
    result = source.pldt.as_unit("us")
    assert (result.name, result.dtype, ticks(result)) == (
        "event", pl.Datetime("us", zone), [-1, 1, -2],
    )
    with pytest.raises(ValueError, match=r"Series\.pldt\.as_unit\(\): data\[2\]:"):
        source.pldt.as_unit("us", round_ok=False)
    coarse = pl.Series("event", [0, 2**63 // 1000 + 1], dtype=pl.Datetime("us", zone))
    with pytest.raises(OverflowError, match=r"Pldt\.as_unit\(\): data\[1\]:"):
        Pldt(coarse).as_unit("ns")


def test_as_unit_preserves_original_business_constructor_exception():
    marker = ValueError("business constructor refused")
    marker.add_note("application note")
    cause = RuntimeError("application cause")

    class Business(Pldt):
        refuse = False

        def __init__(self, *args, **kwargs):
            if self.refuse:
                raise marker from cause
            super().__init__(*args, **kwargs)

    source = Business([1000, None], unit="ns")
    Business.refuse = True
    for owner in (source, source.pldt):
        with pytest.raises(ValueError) as captured:
            owner.as_unit("us", round_ok=False)
        assert captured.value is marker
        assert marker.args == ("business constructor refused",)
        assert marker.__cause__ is cause
        assert marker.__notes__ == ["application note"]


def test_as_unit_expr_error_keeps_the_verified_batch_local_position():
    source = pl.Series("event", [1000, -1500, None], dtype=pl.Datetime("ns", "UTC"))
    frame = pl.DataFrame([source.slice(1, 1)])
    expr = pl.col("event").pldt.as_unit("us", round_ok=False)
    lazy = frame.lazy().select(expr)
    assert lazy.collect_schema()["event"] == pl.Datetime("us", "UTC")
    for execute in (lambda: frame.select(expr), lazy.collect):
        with pytest.raises(pl.exceptions.ComputeError, match=r"batch item 0.*round_ok=True"):
            execute()


def test_as_unit_expr_capacity_error_keeps_the_verified_batch_local_position():
    source = pl.Series("event", [(2**63 - 1) // 1000 + 1], dtype=pl.Datetime("us"))
    frame = source.to_frame()
    expr = pl.col("event").pldt.as_unit("ns")
    lazy = frame.lazy().select(expr)
    assert lazy.collect_schema()["event"] == pl.Datetime("ns")
    for execute in (lambda: frame.select(expr), lazy.collect):
        with pytest.raises(pl.exceptions.ComputeError, match=r"batch item 0 exceeds target capacity"):
            execute()


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
