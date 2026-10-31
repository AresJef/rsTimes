"""Integer calendar factories: independent dates, shape roles and native Expr."""
from datetime import date
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
