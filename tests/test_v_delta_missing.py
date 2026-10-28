"""Missing dates and callback failures retain one consistent Delta contract."""
from datetime import datetime
import pytest
import pandas as pd
from rstimes import Delta, parse_str

@pytest.mark.parametrize('delta', [Delta(), Delta(days=1), Delta(hour=0)])
@pytest.mark.parametrize('method', ['__add__', '__radd__', '__sub__', '__rsub__'])
def test_nat_direct_arithmetic_is_explicitly_missing(delta, method):
    with pytest.raises(ValueError, match='missing|NaT') as caught:
        getattr(delta, method)(pd.NaT)
    assert method in str(caught.value)

@pytest.mark.parametrize('delta', [Delta(), Delta(days=1), Delta(hour=0)])
@pytest.mark.parametrize('container', [list, tuple, iter])
def test_nat_bulk_stops_with_true_position(delta, container):
    with pytest.raises(ValueError, match='missing|NaT') as caught:
        delta.apply_many(container([datetime(2024, 1, 2), pd.NaT]))
    text = str(caught.value) + ' '.join(getattr(caught.value, '__notes__', []))
    assert 'Delta.apply_many' in text and 'values[1]' in text

@pytest.mark.parametrize('delta', [Delta(), Delta(days=1)])
def test_nat_anchor_is_not_a_duration_conversion_failure(delta):
    with pytest.raises(ValueError, match='missing|NaT') as caught:
        delta.to_timedelta(pd.NaT)
    assert 'start' in str(caught.value)

@pytest.mark.parametrize('kind', [ValueError, RuntimeError, MemoryError, KeyboardInterrupt])
def test_date_subclass_constructor_error_is_original(kind):
    error = kind('constructor failed')
    calls=[]
    class Date(datetime):
        def __new__(cls, *args, **kwargs):
            calls.append(1)
            if len(calls)>1:
                raise error
            return super().__new__(cls, *args, **kwargs)
    value=Date(2024,1,2)
    with pytest.raises(kind) as caught:
        Delta(days=1) + value
    assert caught.value is error and calls == [1,1]
    assert error.args == ('constructor failed',)
    notes=getattr(error,'__notes__',[])
    assert len(notes)==(0 if kind in (MemoryError,KeyboardInterrupt) else 1)


def test_batch_callback_can_remove_the_failed_input():
    values=[]
    error=ValueError('removed input')
    class Item:
        def __add__(self, other):
            values.clear()
            raise error
        def __repr__(self):
            pytest.fail('a callback input is not displayed')
    values.append(Item())
    with pytest.raises(ValueError) as caught:
        Delta(days=1).apply_many(values)
    assert caught.value is error and values == []
    assert len(error.__notes__)==1 and 'values[0]' in error.__notes__[0]


def test_callback_can_raise_a_previously_caught_library_error():
    try:
        parse_str('not a date')
    except ValueError as saved:
        error=saved
    original=error.args
    def target(*args, **kwargs):
        raise error
    with pytest.raises(type(error)) as caught:
        parse_str('2024-01-02', dtclass=target)
    assert caught.value is error
    assert error.args==original
    assert len(error.__notes__)==1
