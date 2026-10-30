"""K01: real optional Arrow/pandas targets, callbacks and independent validity."""
import numpy as np
import polars as pl
import pytest

pa = pytest.importorskip('pyarrow', reason='explicit Arrow/pandas export requires optional PyArrow')
pd = pytest.importorskip('pandas')
from rstimes import Pldt


@pytest.mark.parametrize('unit', ['ms', 'us', 'ns'])
def test_arrow_backed_pandas_keeps_valid_minimum_separate_from_null(unit):
    x = Pldt([-(1 << 63), None, 1], unit=unit, name='time')
    for kwargs in ({'use_pyarrow_extension_array': True}, {'types_mapper': pd.ArrowDtype}):
        out = x.to_pandas(**kwargs)
        assert type(out) is pd.Series and out.name == 'time'
        assert out.isna().tolist() == [False, True, False]
        assert pl.from_pandas(out).to_physical().to_list() == [-(1 << 63), None, 1]
    with pytest.raises(OverflowError, match='pandas|validity'):
        x.to_pandas()
    out = x.to_pandas(allow_nat_collision=np.bool_(True))
    assert out.isna().tolist() == [True, True, False]
    assert x.is_null().to_list() == [False, True, False]


def test_real_mapper_exception_identity_and_standard_kwargs():
    x = Pldt([0, None, 1], unit='ns')
    original = RuntimeError('actual mapper failure')
    calls = []
    def mapper(dtype):
        calls.append(dtype)
        raise original
    with pytest.raises(RuntimeError) as caught:
        x.to_pandas(types_mapper=mapper)
    assert caught.value is original and len(calls) == 1
    with pytest.raises(TypeError):
        x.to_pandas(unknown_keyword=True)
    with pytest.raises(TypeError):
        x.to_pandas(allow_nat_collision=1)
    result = x.to_pandas()
    assert str(result.dtype) == 'datetime64[ns]'
    assert result.isna().tolist() == [False, True, False]
    assert result.array.asi8.tolist() == [0, -(1 << 63), 1]


def test_export_validation_uses_original_owner_even_if_mapper_mutates_shell():
    x = Pldt([0, 1], unit='ns')
    calls = []
    def mapper(dtype):
        calls.append(dtype)
        x.append(Pldt([2], unit='ns'))
        return pd.ArrowDtype(dtype)
    result = x.to_pandas(types_mapper=mapper)
    assert len(calls) == 1 and len(x) == 3
    assert pl.from_pandas(result).to_physical().to_list() == [0, 1]


def test_default_deep_copy_allocates_both_data_and_validity_buffers():
    import copy
    x = Pldt([-(1 << 63), None, 1], unit='ns')
    shallow, deep = copy.copy(x), copy.deepcopy(x)
    arrays = [value.to_arrow() for value in (x, shallow, deep)]
    buffers = [array.buffers() for array in arrays]
    assert buffers[0][0].address == buffers[1][0].address
    assert buffers[0][1].address == buffers[1][1].address
    assert buffers[0][0].address != buffers[2][0].address
    assert buffers[0][1].address != buffers[2][1].address
    assert [value.to_physical().to_list() for value in (x, shallow, deep)] == [[-(1 << 63), None, 1]] * 3
