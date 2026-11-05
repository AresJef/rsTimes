"""Appendix C/H01/L02 and B05's known external-buffer boundaries."""
import copy
from datetime import timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import pytest

from rstimes import Pldt


@pytest.mark.parametrize('zone,expected', [(None, None), ('UTC', timezone.utc),
    ('Etc/UTC', timezone.utc), ('Asia/Shanghai', ZoneInfo('Asia/Shanghai')),
    (timezone(timedelta(hours=8)), ZoneInfo('Etc/GMT-8'))])
def test_eager_timezone_metadata_works_without_rows(zone, expected):
    x = Pldt([], tz=zone)
    for target in (x, x.pldt):
        actual = target.tzinfo
        assert actual is expected if expected is None or expected is timezone.utc else actual == expected
        assert target.is_utc() is (expected is timezone.utc)


def test_timezone_available_is_native_backend_set_and_is_not_shared_mutable_state():
    x = Pldt([])
    names = x.tz_available
    assert isinstance(names, set) and {'UTC', 'Asia/Shanghai', 'America/New_York'} <= names
    assert names == x.pldt.tz_available
    from rstimes import _native
    assert names == set(_native._pldt_available_zones())
    names.clear()
    assert 'UTC' in x.tz_available


def test_metadata_queries_only_prepare_local_timezone_on_actual_request(monkeypatch):
    from rstimes import pldt
    calls = []
    def local():
        calls.append(True)
        return ZoneInfo('Asia/Shanghai')
    monkeypatch.setattr(pldt, '_local_zone', local)
    x = Pldt([], tz='UTC')
    assert x.tzinfo is timezone.utc and x.is_utc()
    assert not Pldt([]).is_local() and calls == []
    assert not x.is_local() and calls == [True]
    assert Pldt([], tz='Asia/Shanghai').is_local() and len(calls) == 2


def test_no_schema_free_expr_python_timezone_object_api():
    expression = pl.col('time').pldt
    for name in ('tzinfo', 'tz_available', 'is_local', 'is_utc'):
        assert not hasattr(expression, name)
    with pytest.raises(TypeError, match='Date|Datetime'):
        _ = pl.Series('not_dates', [1]).pldt.tzinfo


def test_public_copy_keeps_business_state_without_constructor_and_renames_core():
    class Business(Pldt):
        calls = 0
        def __new__(cls, data, **kwargs):
            cls.calls += 1
            return super().__new__(cls)
    x = Business([1, 2, 123], unit='ns', name='events')
    x.payload = ['shared']
    x.alias = x.payload
    before = Business.calls
    shallow = x.copy(name='renamed')
    deep = x.copy(deep=True)
    assert Business.calls == before
    assert type(shallow) is type(deep) is Business
    assert shallow.name == 'renamed' and x.name == deep.name == 'events'
    assert shallow.payload is x.payload
    assert deep.payload is deep.alias and deep.payload is not x.payload
    assert shallow.to_physical().to_numpy().ctypes.data == x.to_physical().to_numpy().ctypes.data
    assert deep.to_physical().to_numpy().ctypes.data != x.to_physical().to_numpy().ctypes.data


def test_public_copy_honors_real_custom_hooks_and_their_return_or_original_exception():
    result = object()
    error = RuntimeError('actual copy callback')
    class Custom(Pldt):
        def __copy__(self):
            return result
        def __deepcopy__(self, memo):
            raise error
    x = Custom([0])
    assert x.copy() is result
    with pytest.raises(RuntimeError) as caught:
        x.copy(deep=True)
    assert caught.value is error
    class SelfCopy(Pldt):
        def __copy__(self):
            return self
    x = SelfCopy([0], name='original')
    assert x.copy() is x
    with pytest.raises(ValueError, match='original|source'):
        x.copy(name='different')
    assert x.name == 'original'


@pytest.mark.parametrize('deep', [0, 1, None, 'yes'])
def test_copy_deep_is_true_boolean(deep):
    with pytest.raises(TypeError, match='deep'):
        Pldt([0]).copy(deep=deep)


@pytest.mark.parametrize('readonly', [False, True])
def test_known_numpy_input_owns_stable_ticks_even_with_a_writable_base_alias(readonly):
    original = np.array([1, 2, 3], dtype=np.int64)
    view = original.view()
    view.flags.writeable = not readonly
    x = Pldt(view, unit='ns')
    original[1] = 99
    assert x.to_physical().to_list() == [1, 2, 3]
    assert not np.shares_memory(x.to_physical().to_numpy(), original)
    assert x.add(nanoseconds=1).to_physical().to_list() == [2, 3, 4]


def test_numpy_diff_expr_literal_is_frozen_before_external_mutation():
    target = np.array(['2024-01-01', '2024-01-02'], dtype='datetime64[us]')
    expression = pl.col('time').pldt.diff(target, 'D')
    target[:] = np.datetime64('2030-01-01')
    frame = pl.DataFrame({'time': Pldt(['2024-01-03', '2024-01-04'])})
    assert frame.select(expression).to_series().to_list() == [2, 2]


def test_native_polars_copy_false_keeps_allowed_native_buffer_sharing():
    source = pl.Series('time', [1, 2, 3], dtype=pl.Int64).cast(pl.Datetime('ns'))
    x = Pldt(source, copy=False)
    assert x.to_physical().to_numpy().ctypes.data == source.to_physical().to_numpy().ctypes.data
    source.append(pl.Series('time', [3], dtype=source.dtype))
    assert len(source) == 4 and x.to_physical().to_list() == [1, 2, 3]


@pytest.mark.parametrize('receiver,method,prefix', [
    (lambda: Pldt([0]), 'to_datetime', 'Pldt.to_datetime'),
    (lambda: Pldt([0]).pldt, 'replace', 'Pldt.pldt.replace'),
    (lambda: pl.col('time').pldt, 'replace', 'Expr.pldt.replace'),
])
def test_python_argument_binding_errors_expose_public_entries(receiver, method, prefix):
    with pytest.raises(TypeError) as caught:
        getattr(receiver(), method)(unknown_argument=True)
    text = str(caught.value)
    assert prefix in text and 'unknown_argument' in text
    assert '_TransformMethods' not in text and '_SeriesNamespace' not in text and '_ExprNamespace' not in text
