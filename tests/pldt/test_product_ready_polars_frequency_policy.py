"""PR-026/028: native Polars frequency/mask paths and actual lazy execution."""
from datetime import timedelta
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt


@pytest.mark.parametrize("operation", ("range","round","ceil","floor"))
@pytest.mark.parametrize("mode", ("plain","passive","display"))
def test_polars_real_duration_frequency_uses_actual_type(operation,mode):
    events=[]
    class Passive(timedelta):pass
    class Display(timedelta):
        @property
        def __class__(self):events.append("display");return str
    freq=timedelta(minutes=1) if mode=="plain" else (Passive if mode=="passive" else Display)(minutes=1)
    if operation=="range":
        result=Pldt.date_range("2024-01-01",periods=3,freq=freq,unit="us")
        expected=[1704067200000000,1704067260000000,1704067320000000]
    else:
        source=Pldt(["2024-01-01T00:00:31",None],unit="us")
        result=getattr(source.pldt,operation)(freq)
        expected=[1704067200000000 if operation=="floor" else 1704067260000000,None]
        expr=getattr(pl.col("clock").pldt,operation)(freq)
        actual=pl.DataFrame({"clock":source}).lazy().select(expr).collect().to_series()
        assert actual.to_physical().to_list()==expected
    assert result.to_physical().to_list()==expected and result.dtype==pl.Datetime("us")
    assert events==[]


@pytest.mark.parametrize("expression", (False,True))
@pytest.mark.parametrize("mode", ("plain","passive","display"))
def test_polars_native_mask_prepared_once_and_expr_snapshot_preserved(expression,mode):
    events=[]
    class Passive(np.ndarray):pass
    class Display(np.ndarray):
        @property
        def __class__(self):events.append("display");return pl.DataFrame
        def __iter__(self):events.append("iterate");return super().__iter__()
    base=np.array([True,False]);mask=base if mode=="plain" else base.view(Passive if mode=="passive" else Display)
    texts=["2024-11-03T01:30"]*2
    if expression:
        expr=pl.col("text").pldt.parse(unit="us",tz="America/New_York",ambiguous=mask)
        base[:]=False
        result=pl.DataFrame({"text":texts}).lazy().select(expr).collect().to_series()
    else:result=Pldt(texts,unit="us",tz="America/New_York",ambiguous=mask)
    assert result.to_physical().to_list()==[1730611800000000,1730615400000000]
    assert events==(["iterate"] if mode=="display" else [])


@pytest.mark.parametrize("expression", (False,True))
@pytest.mark.parametrize("values,nonexistent,error,role", [
    ([1,0],"raise",TypeError,"ambiguous"), ([[True,False]],"raise",ValueError,"ambiguous"),
    ([True],"raise",ValueError,"ambiguous"), ([True,False],"invalid",ValueError,"nonexistent"),
    ([True],"invalid",ValueError,"nonexistent"), ([1,0],"invalid",TypeError,"ambiguous"),
    ([True,False],"raise",TypeError,"ambiguous")])
def test_polars_mask_domain_shape_first_error_and_actual_collect(expression,values,nonexistent,error,role):
    dtype=object if values==[True,False] and nonexistent=="raise" else None
    mask=np.asarray(values,dtype=dtype)
    expected=pl.exceptions.ComputeError if expression and values==[True] and nonexistent=="raise" else error
    with pytest.raises(expected,match=role):
        if expression:
            expr=pl.col("text").pldt.parse(unit="us",tz="America/New_York",ambiguous=mask,nonexistent=nonexistent)
            pl.DataFrame({"text":["2024-11-03T01:30"]*2}).lazy().select(expr).collect()
        else:Pldt(["2024-11-03T01:30"]*2,unit="us",tz="America/New_York",ambiguous=mask,nonexistent=nonexistent)
