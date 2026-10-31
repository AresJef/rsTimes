"""K03: independently specified common fraction grammar and native format roles."""
from datetime import datetime

import numpy as np
import polars as pl
import pytest

from rstimes import Pldt, Pydt
from rstimes._optional import PANDAS as pd

CASES = [('pydt', 'us'), ('pldt', 'ms'), ('pldt', 'us'), ('pldt', 'ns'),
         ('pddt', 's'), ('pddt', 'ms'), ('pddt', 'us'), ('pddt', 'ns')]


def source(kind, unit):
    if kind == 'pydt':
        return Pydt(2024, 2, 29, 12, 34, 56, 123456)
    fraction = {'s': '', 'ms': '.123', 'us': '.123456', 'ns': '.123456789'}[unit]
    values = ['2024-02-29T12:34:56' + fraction, None]
    if kind == 'pldt':
        return Pldt(values, unit=unit, name='time')
    if pd is None:
        pytest.skip('Pddt requires optional pandas')
    from rstimes import Pddt
    return Pddt(values, unit=unit, name='time')


def first(result, kind):
    if kind == 'pydt':
        assert type(result) is str
        return result
    if kind == 'pldt':
        assert type(result) is pl.Series and result.dtype == pl.String
        assert result.to_list()[1] is None
    else:
        assert isinstance(result, pd.Index) and pd.isna(result[1])
    assert result.name == 'time'
    return result[0]


@pytest.mark.parametrize('kind,unit', CASES)
@pytest.mark.parametrize('precision', range(10))
def test_exact_common_fraction_grammar_for_all_unit_and_precision(kind, unit, precision):
    x = source(kind, unit)
    nanos = {'s': '000000000', 'ms': '123000000', 'us': '123456000', 'ns': '123456789'}[unit]
    fmt = '%H:%M:%S%.' + str(precision) + 'f'
    expected = '12:34:56' + ('.' + nanos[:precision] if precision else '')
    assert first(x.strftime(fmt), kind) == expected
    if kind == 'pldt':
        assert pl.Series(x).pldt.strftime(fmt).to_list() == [expected, None]
        expr = pl.col('time').pldt.strftime(fmt)
        lf = pl.DataFrame({'time': pl.Series(x)}).lazy().select(expr)
        assert lf.collect_schema()['time'] == pl.String
        assert lf.collect()['time'].to_list() == [expected, None]


@pytest.mark.parametrize('kind,unit', CASES)
def test_default_fraction_escaped_directives_and_dot_elimination(kind, unit):
    x = source(kind, unit)
    expected = {'s': '000000', 'ms': '123000', 'us': '123456', 'ns': '123456789'}[unit]
    assert first(x.strftime('%f'), kind) == expected
    assert first(x.strftime('%%f %%.3f .%.0f %.0f'), kind) == '%f %.3f . '
    assert first(x.strftime('%.0f'), kind) == ''
    assert first(x.strftime(''), kind) == ''


@pytest.mark.parametrize('kind,unit', CASES)
@pytest.mark.parametrize('invalid', ['%.10f', '%.-1f', '%.f', '%.3g'])
def test_invalid_own_fraction_syntax_is_not_system_fallback(kind, unit, invalid):
    with pytest.raises(ValueError, match='precision'):
        source(kind, unit).strftime(invalid)


@pytest.mark.parametrize('kind,unit', CASES)
def test_mixed_system_locale_formats_keep_native_fraction(kind, unit):
    x = source(kind, unit)
    fraction = {'s': '.000000000', 'ms': '.123000000', 'us': '.123456000', 'ns': '.123456789'}[unit]
    expected = datetime(2024, 2, 29, 12, 34, 56).strftime('%A %b %p %H:%M:%S') + fraction
    assert first(x.strftime('%A %b %p %H:%M:%S%.9f'), kind) == expected
    if kind == 'pldt':
        with pytest.raises(ValueError, match='eager'):
            pl.col('time').pldt.strftime('%A %H:%M:%S%.9f')


@pytest.mark.parametrize('text,expected', [
    ('2017-01-01', '2017 17 01 01 00 12 00 00 001 0 7 01 00 2016 52'),
    ('2018-01-01', '2018 18 01 01 00 12 00 00 001 1 1 00 01 2018 01'),
    ('2016-01-01', '2016 16 01 01 00 12 00 00 001 5 5 00 00 2015 53'),
])
def test_native_numeric_calendar_directives_have_independent_week_answers(text, expected):
    fmt = '%Y %y %m %d %H %I %M %S %j %w %u %U %W %G %V'
    x = Pldt([text])
    assert x.strftime(fmt).to_list() == [expected]
    assert pl.DataFrame({'x': pl.Series(x)}).select(pl.col('x').pldt.strftime(fmt))['x'].to_list() == [expected]


@pytest.mark.parametrize('year', ['0000', '-0001', '10000'])
def test_native_wide_year_format_does_not_construct_python_datetime(year):
    x = Pldt(np.array([year + '-01-04'], dtype='datetime64[us]'))
    assert x.strftime('%Y-%m-%d').to_list() == [year + '-01-04']
    with pytest.raises(OverflowError, match='years|carrier'):
        x.strftime('%A %Y')


def test_fraction_only_format_skips_wide_regional_calendar_capacity():
    maximum = (1 << 63) - 1
    x = Pldt(pl.Series('x', [maximum, None], dtype=pl.Int64).cast(pl.Datetime('us', 'America/New_York')))
    expected = f'{(maximum * 1000) % 1000000000:09d}'
    assert x.strftime('%.9f').to_list() == ['.' + expected, None]
    assert x.strftime('%.0f literal').to_list() == [' literal', None]
    with pytest.raises(OverflowError):
        x.strftime('%Y')


def test_negative_epoch_fraction_and_real_zone_abbreviation():
    x = Pldt([-1, None], unit='ns', tz='UTC')
    assert x.strftime('%Y-%m-%d %H:%M:%S%.9f %z %Z').to_list() == ['1969-12-31 23:59:59.999999999 +0000 UTC', None]
    x = Pldt(['2024-01-01T12:00', '2024-07-01T12:00'], tz='America/New_York')
    assert x.strftime('%z %Z').to_list() == ['-0500 EST', '-0400 EDT']
    assert Pldt([0]).strftime('%z%Z').to_list() == ['']


def test_pydt_stored_fraction_and_actual_subclass_format_dispatch():
    class Business(Pydt):
        @property
        def microsecond(self):
            raise AssertionError('datetime.strftime reads its stored fraction')
    value = Business(2024, 1, 1, microsecond=123456)
    assert value.strftime('%f %.9f') == '123456 .123456000'
    calls = []
    class FormatBusiness(Pydt):
        def strftime(self, format):
            calls.append(format)
            return 'business'
    assert format(FormatBusiness(2024, 1, 1), '%.9f') == 'business'
    assert calls == ['%.9f']
    for fmt in ('%Y/%m/%d', '%A', '%_d', 'literal', '', '%%f', '%c'):
        plain = Pydt(1, 1, 1, 1, 2, 3)
        try:
            expected = datetime.strftime(plain, fmt)
        except Exception as original:
            with pytest.raises(type(original)) as caught:
                plain.strftime(fmt)
            assert caught.value.args == original.args
        else:
            assert plain.strftime(fmt) == expected


@pytest.mark.parametrize('invalid', [None, 1, True, b'%f'])
def test_format_parameter_type_checked_on_empty_source(invalid):
    with pytest.raises(TypeError):
        Pldt([]).strftime(invalid)
    with pytest.raises(TypeError):
        pl.col('x').pldt.strftime(invalid)


def test_format_plugin_has_versioned_owned_kwargs_and_rejects_unknown_version():
    import json
    from pathlib import Path
    from polars.plugins import register_plugin_function
    from rstimes import _native
    context = _native._strftime_prepare('%Y %.9f')
    payload = json.loads(context.plugin_data())
    assert payload['version'] == 1
    payload['version'] = 2
    expr = register_plugin_function(plugin_path=Path(_native.__file__), function_name='pldt_strftime',
                                    args=[pl.col('x')], kwargs={'prepared': json.dumps(payload).encode()},
                                    is_elementwise=True)
    with pytest.raises(pl.exceptions.ComputeError, match='version'):
        pl.DataFrame({'x': Pldt([0])}).lazy().select(expr).collect_schema()
