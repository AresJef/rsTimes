"""Native and Python target preparation retain their distinct first errors."""
import polars as pl
import pytest

from rstimes import Pldt
from rstimes.errors import ParseError


@pytest.mark.parametrize('expression', [False, True])
@pytest.mark.parametrize('native', [False, True])
def test_length_and_parse_double_fault_preserves_real_preparation_order(expression, native):
    source = Pldt(['2024-01-01', '2024-01-02'], name='time')
    target = pl.Series('target', ['bad-date']) if native else ['bad-date']
    exception = (pl.exceptions.ComputeError if expression else ValueError) if native else ParseError
    match = 'length' if native else 'no date/time fields'
    with pytest.raises(exception, match=match):
        if expression:
            expr = pl.col('time').pldt.diff(target, 'D')
            pl.DataFrame({'time': pl.Series(source)}).lazy().select(expr).collect()
        else:
            source.pldt.diff(target, 'D')
    valid = pl.Series('target', ['2024-01-01', None]) if native else ['2024-01-01', None]
    expected = [0, None]
    if expression:
        expr = pl.col('time').pldt.diff(valid, 'D')
        assert pl.DataFrame({'time': pl.Series(source)}).select(expr).to_series().to_list() == expected
    else:
        assert source.pldt.diff(valid, 'D').to_list() == expected
