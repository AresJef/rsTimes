"""K01/K02/K04 native outputs, explicit Python exits and safe target formats."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import pytest

from rstimes import Pldt, Pydt


@pytest.mark.parametrize('mode', ['direct', 'namespace', 'expr'])
@pytest.mark.parametrize('method,args,dtype,expected', [
    ('toseconds', (), pl.Float64, 28800.000000999),
    ('toseconds', (True,), pl.Float64, 0.000000999),
    ('tomicroseconds', (), pl.Int64, 28800000000),
    ('tomicroseconds', (True,), pl.Int64, 0),
    ('timestamp', (), pl.Float64, 0.000000999),
    ('toordinal', (), pl.Int64, 719163),
    ('isoformat', (), pl.String, '1970-01-01T08:00:00.000000999+08:00'),
    ('ctime', (), pl.String, 'Thu Jan  1 08:00:00 1970'),
    ('month_name', (), pl.String, 'January'),
    ('weekday_name', (), pl.String, 'Thursday'),
    ('month_name', ('zh_CN',), pl.String, '一月'),
    ('tzname', (), pl.String, 'CST'),
])
def test_native_output_roles_and_independent_answers(mode, method, args, dtype, expected):
    x = Pldt(['1970-01-01T08:00:00.000000999', None], unit='ns', tz='Asia/Shanghai', name='time')
    owner = x if mode == 'direct' else pl.Series(x).pldt if mode == 'namespace' else pl.col('time').pldt
    result = getattr(owner, method)(*args)
    if mode == 'expr':
        assert isinstance(result, pl.Expr)
        df = pl.DataFrame({'time': pl.Series(x)})
        assert df.lazy().select(result).collect_schema()['time'] == dtype
        result = df.lazy().select(result).collect()['time']
    assert type(result) is pl.Series and result.name == 'time'
    assert result.dtype == dtype and result.to_list() == [expected, None]
    assert x.to_physical().to_list() == [999, None]


@pytest.mark.parametrize('mode', ['direct', 'namespace', 'expr'])
@pytest.mark.parametrize('attribute,dtype,raw', [
    ('values_naive', pl.Datetime('ns'), 28800000000999),
    ('date', pl.Date, 0), ('time', pl.Time, 28800000000999),
])
def test_temporal_outputs_have_native_dtype_and_validity(mode, attribute, dtype, raw):
    x = Pldt(['1970-01-01T08:00:00.000000999', None], unit='ns', tz='Asia/Shanghai', name='time')
    owner = x if mode == 'direct' else pl.Series(x).pldt if mode == 'namespace' else pl.col('time').pldt
    result = getattr(owner, attribute)
    if mode == 'expr':
        result = pl.DataFrame({'time': pl.Series(x)}).select(result)['time']
    assert type(result) is pl.Series and result.dtype == dtype
    assert result.to_physical().to_list() == [raw, None]


@pytest.mark.parametrize('unit', ['ms', 'us', 'ns'])
def test_explicit_numpy_boundary_guard_and_no_implicit_escape(unit):
    minimum = -(1 << 63)
    x = Pldt([minimum, None, 0], unit=unit)
    assert x.is_null().to_list() == [False, True, False]
    for invoke in (x.to_numpy, lambda: np.asarray(x), lambda: np.array(x)):
        with pytest.raises(OverflowError, match='NaT'):
            invoke()
    array = x.to_numpy(allow_nat_collision=True)
    assert array.dtype == np.dtype(f'datetime64[{unit}]')
    assert np.isnat(array).tolist() == [True, True, False]
    assert x.to_physical().to_list() == [minimum, None, 0]
    with pytest.raises(TypeError):
        x.to_numpy(allow_nat_collision=1)


def test_native_numpy_flags_and_real_business_override_protocol():
    x = Pldt([0, 1], unit='us')
    assert not x.to_numpy().flags.writeable
    assert x.to_numpy(writable=True).flags.writeable
    assert np.asarray(x, dtype='datetime64[ns]').view('i8').tolist() == [0, 1000]
    with pytest.raises(RuntimeError, match='copy'):
        x.__array__(np.dtype('datetime64[ns]'), copy=False)
    calls = []
    class Business(Pldt):
        def to_numpy(self, **kwargs):
            calls.append(kwargs)
            return np.array([7, 8])
    assert np.asarray(Business([0, 1]), dtype=float).tolist() == [7., 8.]
    assert len(calls) == 1


@pytest.mark.parametrize('dtype', ['datetime64[us]', 'datetime64[ms]', 'datetime64[D]'])
def test_explicit_numpy_coarsening_cannot_silently_drop_ns(dtype):
    x = Pldt([1], unit='ns')
    with pytest.raises(ValueError, match='precision|preserve'):
        np.asarray(x, dtype=dtype)


@pytest.mark.parametrize('dtype', ['int64', 'float64'])
def test_numeric_numpy_dtype_cannot_erase_missing_position(dtype):
    with pytest.raises(ValueError, match='missing'):
        np.asarray(Pldt([0, None], unit='us'), dtype=dtype)


def test_finer_numpy_unit_cannot_wrap_broad_date_or_round_large_tick():
    with pytest.raises((OverflowError, ValueError)):
        np.asarray(Pldt(['2500-01-01'], unit='us'), dtype='datetime64[ns]')
    with pytest.raises(ValueError, match='tick'):
        np.asarray(Pldt([(1 << 63) - 1], unit='ns'), dtype=float)
    assert np.asarray(Pldt([0, 1], unit='us'), dtype=np.int64).tolist() == [0, 1]


@pytest.mark.parametrize('namespace', [False, True])
def test_explicit_python_output_is_pydt_or_standard_time_with_real_fold(namespace):
    x = Pldt(['2024-11-03T01:30:00.123456789', None], unit='ns', tz='America/New_York', ambiguous=False)
    owner = pl.Series(x).pldt if namespace else x
    result = owner.datetime()
    assert type(result) is np.ndarray and result.dtype == object
    assert type(result[0]) is Pydt and result[1] is None
    assert result[0].fold == 1 and result[0].microsecond == 123456
    assert result[0].tzinfo == ZoneInfo('America/New_York')
    assert result[0].timestamp() == datetime(2024, 11, 3, 6, 30, 0, 123456, tzinfo=timezone.utc).timestamp()
    times = owner.timetz
    assert type(times[0]) is time and times[0].fold == 1 and times[1] is None
    assert times[0].tzinfo == ZoneInfo('America/New_York')
    assert x.nanosecond.to_list() == [789, None]


def test_python_output_utc_normalization_capacity_and_fixed_clock_shortcut():
    assert Pldt([0], tz=ZoneInfo('UTC')).datetime()[0].tzinfo is timezone.utc
    assert Pldt([0]).datetime()[0].tzinfo is None
    for tick in (-(1 << 63), (1 << 63) - 1):
        x = Pldt([tick], unit='us')
        with pytest.raises(OverflowError, match='years'):
            x.datetime()
        assert type(x.timetz[0]) is time
        assert x.time.to_physical()[0] == (tick * 1000) % 86400000000000
    assert not hasattr(pl.col('x').pldt, 'datetime')
    assert not hasattr(pl.col('x').pldt, 'timetz')


@pytest.mark.parametrize('source', [[], [None]])
def test_output_options_validate_on_empty_and_missing(source):
    x = Pldt(source)
    for utc in (None, 1, '', []):
        with pytest.raises(TypeError):
            x.toseconds(utc)
    with pytest.raises(ValueError):
        x.isoformat(sep='')
    with pytest.raises(TypeError):
        x.isoformat(timespec=None)
    with pytest.raises(ValueError):
        x.isoformat(timespec='invalid')
    with pytest.raises(ValueError):
        x.month_name('unknown-LOCALE')


@pytest.mark.parametrize('unit', ['ms', 'us', 'ns'])
def test_complete_native_domain_utc_numeric_outputs_and_date_capacity(unit):
    q = {'ms': 1000000, 'us': 1000, 'ns': 1}[unit]
    values = [-(1 << 63), None, (1 << 63) - 1]
    x = Pldt(values, unit=unit, tz='UTC')
    assert x.timestamp().to_list() == [values[0] * q / 1000000000, None, values[2] * q / 1000000000]
    assert x.tzname().to_list() == ['UTC', None, 'UTC']
    if unit == 'ns':
        assert x.tomicroseconds().to_list() == [values[0] // 1000, None, values[2] // 1000]
    elif unit == 'us':
        assert x.tomicroseconds().to_list() == values
    else:
        with pytest.raises(OverflowError):
            x.tomicroseconds()
        with pytest.raises(OverflowError, match='Date'):
            _ = x.date


@pytest.mark.parametrize('timespec,expected', [
    ('hours', '1970-01-01T00'), ('h', '1970-01-01T00'),
    ('minutes', '1970-01-01T00:00'), ('m', '1970-01-01T00:00'), ('min', '1970-01-01T00:00'),
    ('seconds', '1970-01-01T00:00:00'), ('s', '1970-01-01T00:00:00'),
    ('milliseconds', '1970-01-01T00:00:00.123'), ('ms', '1970-01-01T00:00:00.123'),
    ('microseconds', '1970-01-01T00:00:00.123456'), ('us', '1970-01-01T00:00:00.123456'),
    ('nanoseconds', '1970-01-01T00:00:00.123456789'), ('ns', '1970-01-01T00:00:00.123456789'),
])
def test_iso_exact_aliases_truncate_only_display(timespec, expected):
    x = Pldt([123456789, None], unit='ns', name='x')
    assert x.isoformat(timespec=timespec).to_list() == [expected, None]
    assert pl.DataFrame({'x': pl.Series(x)}).select(pl.col('x').pldt.isoformat(timespec=timespec))['x'].to_list() == [expected, None]
    assert x.isoformat(sep='日', timespec='s').to_list() == ['1970-01-01日00:00:00', None]


def test_local_timestamp_preparation_is_conditional_and_failed_zone_is_retryable():
    import os
    import subprocess
    import sys
    script = '''
import os
from rstimes import Pldt
os.environ['TZ'] = 'Unrecognized/Zone'
assert Pldt([0], tz='UTC').timestamp().to_list() == [0.0]
assert Pldt([None]).timestamp().to_list() == [None]
try:
    Pldt([0]).timestamp()
except ValueError:
    pass
else:
    raise AssertionError('invalid actual local zone was accepted')
os.environ['TZ'] = 'UTC'
assert Pldt([0]).timestamp().to_list() == [0.0]
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, env=os.environ.copy())
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('unit,multiplier', [('ps', 1000), ('fs', 1000000), ('as', 1000000000)])
def test_native_numpy_subnanosecond_dtype_is_preserved_when_exact(unit, multiplier):
    x = Pldt([0, 1, None], unit='ns')
    result = np.asarray(x, dtype=f'datetime64[{unit}]')
    assert result.dtype == np.dtype(f'datetime64[{unit}]')
    assert result.view('i8').tolist() == [0, multiplier, -(1 << 63)]
    with pytest.raises(OverflowError):
        np.asarray(Pldt(['2024-01-01'], unit='ns'), dtype=f'datetime64[{unit}]')


def test_extended_numpy_output_dtype_keeps_native_protocol_and_exactness():
    values = [0, 1, (1 << 63) - 1]
    x = Pldt(values, unit='ns')
    if np.finfo(np.longdouble).nmant >= 63:
        result = np.asarray(x, dtype=np.longdouble)
        assert result.dtype == np.dtype(np.longdouble)
        assert np.array_equal(result, np.array(values, dtype=np.longdouble))
    else:
        with pytest.raises(ValueError):
            np.asarray(x, dtype=np.longdouble)


def test_explicit_dynamic_python_exit_preserves_instant_across_native_host_tzdb_difference():
    text = '1844-12-31T15:56:07.999999999Z'
    x = Pldt([text], unit='ns', tz='Asia/Manila')
    result = x.datetime()[0]
    expected = datetime(1844, 12, 31, 15, 56, 7, 999999, tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Manila'))
    assert result.astimezone(timezone.utc) == expected.astimezone(timezone.utc)
    assert (result.year, result.month, result.day, result.hour, result.minute, result.second, result.microsecond, result.fold) == (expected.year, expected.month, expected.day, expected.hour, expected.minute, expected.second, expected.microsecond, expected.fold)
    assert result.tzinfo == expected.tzinfo
