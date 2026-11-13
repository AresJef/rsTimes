"""Independent output controls for bounded structural-format reuse."""
from datetime import datetime, timedelta, tzinfo
import io
import json
import weakref

import polars as pl
import pytest

from rstimes import Pldt, Pydt, _native


@pytest.mark.parametrize('prefix', ['', '日期🌏', 'x' * 512])
def test_same_format_with_distinct_dates_and_after_eviction(prefix):
    fmt = prefix + '%Y-%m-%d %H:%M:%S%.9f'
    a = Pldt([-1, None, 123456789], unit='ns', name='stamp')
    expected = [prefix + '1969-12-31 23:59:59.999999999', None,
                prefix + '1970-01-01 00:00:00.123456789']
    assert a.strftime(fmt).to_list() == expected
    for i in range(64):
        assert Pydt(2024, 1, 2).strftime(str(i) + '%Y') == str(i) + '2024'
    assert a.strftime(fmt).to_list() == expected
    b = Pldt([0], unit='ms')
    assert b.strftime(fmt).to_list() == [prefix + '1970-01-01 00:00:00.000000000']


def test_structural_reuse_does_not_retain_format_subclass_owner():
    class Format(str):
        def __str__(self):
            raise AssertionError('format storage is read directly')
        def __hash__(self):
            raise AssertionError('no Python cache key')
        def __eq__(self, other):
            raise AssertionError('no Python cache comparison')
    fmt = Format('%Y %.9f')
    reference = weakref.ref(fmt)
    assert Pydt(2024, 1, 1, microsecond=123456).strftime(fmt) == '2024 .123456000'
    del fmt
    assert reference() is None


def test_reused_structure_reads_live_timezone_protocol_each_call():
    class Zone(tzinfo):
        label = 'first'
        def utcoffset(self, value):
            return timedelta(hours=1)
        def dst(self, value):
            return timedelta(0)
        def tzname(self, value):
            return self.label
    zone = Zone()
    date = Pydt(2024, 1, 1, microsecond=123456, tzinfo=zone)
    fmt = '%Z %z %.9f'
    assert date.strftime(fmt) == 'first +0100 .123456000'
    zone.label = 'second'
    assert date.strftime(fmt) == 'second +0100 .123456000'


def test_retained_plugin_snapshot_is_owned_and_serialization_unchanged():
    fmt = '%Y|%.9f'
    context = _native._strftime_prepare(fmt)
    before = context.plugin_data()
    for i in range(64):
        _native._strftime_prepare(str(i) + '%m')
    assert context.plugin_data() == before
    assert json.loads(before)['version'] == 1
    expr = pl.col('stamp').pldt.strftime(fmt)
    restored = pl.Expr.deserialize(io.BytesIO(expr.meta.serialize()))
    source = pl.DataFrame({'stamp': Pldt([-1, None, 0], unit='ns')})
    assert source.select(restored)['stamp'].to_list() == ['1969|.999999999', None, '1970|.000000000']


@pytest.mark.parametrize('fmt', ['%.10f', '%.f', '%.-1f', '%.3g'])
def test_invalid_fraction_remains_error_after_nearby_valid_reuse(fmt):
    date = Pydt(2024, 1, 1)
    for _ in range(2):
        assert date.strftime('%.9f') == '.000000000'
        with pytest.raises(ValueError, match='precision'):
            date.strftime(fmt)


def test_unmodified_system_format_still_matches_original_host_call():
    value = Pydt(2024, 2, 29, 12, 34, 56, 123456)
    for fmt in ['%A %B %p', '%c', '%_d', '日期 %Y', '', '%%f']:
        assert value.strftime(fmt) == datetime.strftime(value, fmt)
