"""Integer calendar factories: independent dates, shape roles and native Expr."""
from datetime import date, timedelta
from decimal import Decimal
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


def ticks(value):
    return value.to_physical().to_list()


def tick(text, unit="us"):
    return int(np.datetime64(text, unit).astype(np.int64))


def test_ordinal_zero_negative_and_actual_year_zero():
    result=Pldt.fromordinal([1,0,-1,None])
    assert result.dtype==pl.Datetime("us")
    assert ticks(result)==[tick("0001-01-01"),tick("0000-12-31"),tick("0000-12-30"),None]
    assert ticks(Pldt.fromdayofyear([0,-1,12000],1,unit="ms"))==[tick("0000-01-01","ms"),tick("-001-01-01","ms"),tick("12000-01-01","ms")]


def test_iso_and_day_of_year_convenient_upper_bounds():
    assert ticks(Pldt.fromisocalendar([2020,2021],[99,99],[99,99]))==[tick("2021-01-03"),tick("2022-01-02")]
    assert ticks(Pldt.fromdayofyear([2023,2024],[999,999]))==[tick("2023-12-31"),tick("2024-12-31")]
    assert ticks(Pldt.fromdayofyear(2024,[1,60,366]))==[tick("2024-01-01"),tick("2024-02-29"),tick("2024-12-31")]
    assert ticks(Pldt.fromisocalendar(2024,1,1,size=2))==[tick("2024-01-01")]*2


@pytest.mark.parametrize("call",[
    lambda:Pldt.fromisocalendar([None],[0],1),
    lambda:Pldt.fromisocalendar(2024,1,0,size=0),
    lambda:Pldt.fromdayofyear(2024,0,size=0),
    lambda:Pldt.fromdayofyear([],0),
])
def test_missing_or_empty_does_not_hide_invalid_low_component(call):
    with pytest.raises(ValueError,match="at least 1|minimum|positive"):
        call()


@pytest.mark.parametrize("value",[True,np.bool_(False),1.0,"1",b"1"])
def test_integer_factories_do_not_truncate_or_coerce(value):
    with pytest.raises(TypeError):
        Pldt.fromordinal(value,size=1)


def test_shared_shape_does_not_broadcast_a_one_element_collection():
    with pytest.raises(ValueError,match="length|scalar"):
        Pldt.fromisocalendar([2024],[1,2],1)
    with pytest.raises(ValueError,match="size|collection"):
        Pldt.fromdayofyear([2024],1,size=1)
    with pytest.raises(ValueError,match="size"):
        Pldt.fromordinal(1)
    assert Pldt.fromordinal([]).dtype==pl.Datetime("us")
    assert Pldt.fromordinal(1,size=0).len()==0


def test_index_protocol_and_iterator_are_read_once():
    class Index:
        calls=0
        def __index__(self):
            self.calls+=1
            return date(2024,2,29).toordinal()
    value=Index()
    assert ticks(Pldt.fromordinal(value,size=4))==[tick("2024-02-29")]*4
    assert value.calls==1
    def values():
        yield value
        yield None
    assert ticks(Pldt.fromordinal(values()))==[tick("2024-02-29"),None]
    assert value.calls==2


def test_typed_integer_columns_nullable_inputs_and_ns_capacity():
    result=Pldt.fromdayofyear(np.array([2023,2024],dtype=np.int32),pl.Series([60,60]))
    assert ticks(result)==[tick("2023-03-01"),tick("2024-02-29")]
    with pytest.raises(TypeError):
        Pldt.fromordinal(np.array([1.0]))
    assert ticks(Pldt.fromordinal([float("nan"),None]))==[None,None]
    with pytest.raises(OverflowError):
        Pldt.fromdayofyear(2500,1,size=1,unit="ns")


def test_calendar_expr_static_default_and_position_pairing():
    frame=pl.DataFrame({"year":[2023,2024,None],"doy":[60,60,1]})
    expr=pl.col("year").pldt.fromdayofyear(pl.col("doy"))
    assert frame.lazy().select(expr).collect_schema()["year"]==pl.Datetime("us")
    assert ticks(frame.select(expr)["year"])==[tick("2023-03-01"),tick("2024-02-29"),None]
    assert ticks(pl.Series("year",[2023,2024]).pldt.fromdayofyear(60))==[tick("2023-03-01"),tick("2024-02-29")]
    expr=pl.col("year").max().pldt.fromdayofyear(1)
    assert ticks(frame.select(expr)["year"])==[tick("2024-01-01")]
    assert frame.select(pl.col("year"),expr.alias("max_day"))["max_day"].len()==3


_CALENDAR_ENTRIES = ("fromordinal", "fromdayofyear", "fromisocalendar")
_CALENDAR_PARAMS = tuple(zip(_CALENDAR_ENTRIES, ("ordinal", "doy", "weekday"), strict=True))
_EPOCH_DATE = date(1970, 1, 1)


def _calendar_arguments(method, year, day):
    if method == "fromordinal":
        return day,
    if method == "fromdayofyear":
        return year, day
    return year, 9, day


def _calendar_entry(owner, method, args):
    return getattr(owner, method)(*args, unit="ms")


def _calendar_calls(method, day):
    years = pl.Series("year", [2024] * len(day))
    args = _calendar_arguments(method, years, day)
    frame = pl.DataFrame([years, day])
    columns = _calendar_arguments(method, pl.col("year"), pl.col("value"))
    expr = _calendar_entry(columns[0].pldt, method, columns[1:])
    eager = (
        lambda: _calendar_entry(Pldt, method, args),
        lambda: _calendar_entry(args[0].pldt, method, args[1:]),
    )
    if method == "fromordinal":
        literal = _calendar_entry(pl.lit(day).pldt, method, ())
    else:
        constants = _calendar_arguments(method, pl.col("year"), day)
        literal = lambda: _calendar_entry(constants[0].pldt, method, constants[1:])
    planned = frame.lazy().select(expr)
    return frame, planned, expr, literal, eager


def _assert_calendar_columns(method, values, expected):
    assert values.name == ("value" if method == "fromordinal" else "year")
    assert values.dtype == pl.Datetime("ms")
    assert len(values) == len(expected) and values.is_null().to_list() == [v is None for v in expected]
    assert ticks(values) == expected


@pytest.mark.parametrize("method", _CALENDAR_ENTRIES)
@pytest.mark.parametrize("dtype", [pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64, pl.UInt128, pl.Int128])
@pytest.mark.parametrize("raw", ([1, None, 2], [], [None, None]))
def test_native_calendar_column_dtypes_and_validity(method, dtype, raw):
    source = pl.Series("value", raw, dtype=dtype)
    frame, planned, expr, literal, eager = _calendar_calls(method, source)
    if method == "fromordinal":
        truth = date.fromordinal
    elif method == "fromdayofyear":
        truth = lambda day: date(2024, 1, 1) + timedelta(days=day - 1)
    else:
        truth = lambda day: date.fromisocalendar(2024, 9, day)
    expected = [None if value is None else (truth(value) - _EPOCH_DATE).days * 86_400_000 for value in raw]
    name = "value" if method == "fromordinal" else "year"
    assert planned.collect_schema() == pl.Schema({name: pl.Datetime("ms")})
    expression = literal if method == "fromordinal" else literal()
    for result in (eager[0](), eager[1](), frame.select(expr).to_series(), planned.collect().to_series(),
                   frame.lazy().select(expression).collect().to_series()):
        _assert_calendar_columns(method, result, expected)


@pytest.mark.parametrize("method,parameter", _CALENDAR_PARAMS)
@pytest.mark.parametrize("dtype", [pl.UInt128, pl.UInt64])
def test_native_wide_calendar_integer_reports_first_capacity_error(method, parameter, dtype):
    day = pl.Series("value", [1, 2**63, None], dtype=dtype)
    frame, planned, expr, literal, eager = _calendar_calls(method, day)
    assert next(iter(planned.collect_schema().values())) == pl.Datetime("ms")
    for call in eager:
        with pytest.raises(OverflowError, match=rf"{parameter}\[1\].*exceeds signed64"):
            call()
    if method != "fromordinal":
        with pytest.raises(OverflowError, match=rf"{parameter}\[1\].*exceeds signed64"):
            literal()
    for call in (lambda: frame.select(expr), planned.collect):
        with pytest.raises(pl.exceptions.ComputeError) as caught:
            call()
        message = str(caught.value)
        assert f"batch item 1: {parameter}" in message and "exceeds signed64" in message


@pytest.mark.parametrize("method", _CALENDAR_ENTRIES)
@pytest.mark.parametrize("dtype", [pl.Float16, pl.Float32, pl.Float64])
@pytest.mark.parametrize("raw", ([], [None, None], [float("nan"), None]))
def test_native_calendar_float_dtype_accepts_only_missing_values(method, dtype, raw):
    source = pl.Series("value", raw, dtype=dtype)
    frame, planned, expr, literal, eager = _calendar_calls(method, source)
    assert next(iter(planned.collect_schema().values())) == pl.Datetime("ms")
    expression = literal if method == "fromordinal" else literal()
    for result in (eager[0](), eager[1](), frame.select(expr).to_series(),
                   planned.collect().to_series(), frame.select(expression).to_series()):
        _assert_calendar_columns(method, result, [None] * len(raw))


@pytest.mark.parametrize("method,parameter", _CALENDAR_PARAMS)
@pytest.mark.parametrize("present", [1.0, float("inf"), float("-inf")])
def test_native_calendar_float16_fails_at_first_present_value(method, parameter, present):
    source = pl.Series("value", [None, float("nan"), present], dtype=pl.Float16)
    frame, planned, expr, literal, eager = _calendar_calls(method, source)
    assert next(iter(planned.collect_schema().values())) == pl.Datetime("ms")
    for call in eager:
        with pytest.raises(TypeError, match=rf"{parameter}\[2\].*not floats"):
            call()
    if method != "fromordinal":
        with pytest.raises(TypeError, match=rf"{parameter}\[2\].*not floats"):
            literal()
    for call in (lambda: frame.select(expr), planned.collect):
        with pytest.raises(pl.exceptions.ComputeError, match=rf"batch item 2: {parameter}.*not floats"):
            call()


@pytest.mark.parametrize("method,parameter", _CALENDAR_PARAMS)
@pytest.mark.parametrize("value,dtype", [(Decimal(1), pl.Decimal(scale=0)), (True, pl.Boolean)])
def test_unsupported_calendar_dtype_is_rejected_by_actual_parameter(method, parameter, value, dtype):
    source = pl.Series("value", [None, value], dtype=dtype)
    frame, planned, expr, literal, eager = _calendar_calls(method, source)
    for call in eager:
        with pytest.raises(TypeError, match=rf"{parameter}: calendar components require integers"):
            call()
    if method != "fromordinal":
        with pytest.raises(TypeError, match=rf"{parameter}: calendar components require integers"):
            literal()
    for call in (planned.collect_schema, lambda: frame.select(expr), planned.collect):
        with pytest.raises(pl.exceptions.ComputeError) as error:
            call()
        assert f"{parameter} requires integer dtype" in str(error.value)
        assert "batch item" not in str(error.value) and f"{parameter}[" not in str(error.value)


@pytest.mark.parametrize("dtype", ["uint8", "uint16", "uint32", "int64"])
def test_calendar_preparation_keeps_native_values_before_later_callbacks(dtype):
    years = np.array([20, 21], dtype=dtype)
    source = pl.Series("year", years)
    assert np.shares_memory(source.to_numpy(allow_copy=False), years)
    calls = []

    def change_years():
        calls.append("doy")
        years[:] = 30
        yield from (60, 60)

    positions = [date(20, 2, 29), date(21, 3, 1)]
    result = Pldt.fromdayofyear(source, change_years(), unit="ms")
    expected = [(value - _EPOCH_DATE).days * 86_400_000 for value in positions]
    _assert_calendar_columns("fromdayofyear", result, expected)
    assert calls == ["doy"] and years.tolist() == [30, 30]
    days = np.array([60, 61], dtype=dtype)
    literal = pl.Series("doy", days)
    assert np.shares_memory(literal.to_numpy(allow_copy=False), days)
    expr = pl.col("year").pldt.fromdayofyear(literal, unit="ms")
    days[:] = 1
    lazy = pl.LazyFrame({"year": [20, 21]}).select(expr)
    _assert_calendar_columns("fromdayofyear", lazy.collect().to_series(), [expected[0], expected[1] + 86_400_000])


def test_wide_capacity_precedes_shape_and_low_fields_without_consuming_later_input():
    called = []

    def weekday():
        called.append("weekday")
        yield 1

    wide = pl.Series("week", [0, 2**63, None], dtype=pl.UInt128)
    with pytest.raises(OverflowError, match=r"week\[1\].*exceeds signed64"):
        Pldt.fromisocalendar([2024, 2024], wide, weekday())
    assert not called
    with pytest.raises(ValueError, match="length"):
        Pldt.fromisocalendar([2024, 2024], pl.Series("week", [0, 1, 2], dtype=pl.UInt128), 1)
