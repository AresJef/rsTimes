"""Independent epoch expectations for the shared nanosecond parser node."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest
from rstimes import Configs, parse, parse_str, parse_to_epoch

@pytest.mark.parametrize('unit,expected',[('s',-1),('ms',-1),('us',-1),('ns',-1)])
def test_negative_fraction_floors_once(unit,expected):
    assert parse_to_epoch('1969-12-31T23:59:59.999999999',unit)==expected

@pytest.mark.parametrize('unit,multiplier',[('s',1),('ms',1000),('us',1000000),('ns',1000000000)])
def test_numeric_input_unit_is_independent_from_output(unit,multiplier):
    assert parse_to_epoch(1,unit)==multiplier
    assert parse_to_epoch(1000,unit,input_unit='ms')==multiplier
    # P04/P17: booleans are no longer numeric epoch seconds.
    with pytest.raises(TypeError):parse_to_epoch(True,unit)

@pytest.mark.parametrize('unit',['Y','M','W','D','h','m','s','ms','us','ns'])
def test_numpy_units_use_typed_source(unit):
    value=np.datetime64('2024-01-02T12:34:56.123456789',unit)
    expected=int(value.astype('datetime64[ns]').astype('i8'))
    assert parse_to_epoch(value,'ns')==expected

@pytest.mark.parametrize('text',[
    '2024-01-02T12:34:56.123456789',
    '2024-01-02 123456.123456789',
    'Jan 2 2024 12:34:56.123456789',
    '2024-01-02T12:34:56.123456789+08:00',
    '2024-01-02T12:34:56.123456789-03:30',
])
def test_nanos_survive_both_grammars(text):
    canonical=text.replace(' 123456.',' 12:34:56.')
    expected=pd.Timestamp(canonical.replace('Jan 2 2024','2024-01-02')).value
    assert parse_to_epoch(text,'ns')==expected

@pytest.mark.parametrize('source',[date(2024,1,2),datetime(2024,1,2),datetime(2024,1,2,tzinfo=timezone(timedelta(hours=8))),datetime(2024,11,3,1,30,tzinfo=ZoneInfo('America/New_York'),fold=1)])
def test_date_datetime_and_fold(source):
    assert parse_to_epoch(source,'ns')==pd.Timestamp(source).value

def test_timestamp_keeps_nanoseconds_and_timezone():
    source=pd.Timestamp('2024-01-02 12:34:56.123456789',tz='Asia/Shanghai')
    assert parse_to_epoch(source,'ns')==source.value
    assert parse_to_epoch(source,'ns',ignoretz=True)==source.tz_localize(None).value

def test_submicro_offset_is_not_truncated():
    source=datetime(1970,1,1,tzinfo=timezone(timedelta(microseconds=123)))
    assert parse_to_epoch(source,'ns')==-123000

def test_wide_integer_return_is_not_limited_to_numpy_i64():
    assert parse_to_epoch('1000-01-01','ns')==-30610224000000000000
    assert parse_to_epoch(np.datetime64('12000-01-01','us'),'ns')==int(np.datetime64('12000-01-01','us').astype('i8'))*1000

def test_default_only_supplies_calendar():
    assert parse_to_epoch('Feb 29','us',default=datetime(2024,8,20,12,34))==1709164800000000

def test_configured_month_is_used():
    cfg=Configs();cfg.add_month('mymonth',2)
    assert parse_to_epoch('29 mymonth 2024','us',cfg=cfg)==1709164800000000

def test_existing_datetime_result_still_uses_microseconds():
    assert parse_str('2024-01-02T12:34:56.123456789').microsecond==123456
    assert parse('2024-01-02T12:34:56.123456789').microsecond==123456

def test_strict_nanosecond_duplicate_conflict():
    with pytest.raises(Exception,match='Conflicting'):
        parse_to_epoch('2024-01-02 12:34:56.123456789 56.123456788s','ns',strict=True)

@pytest.mark.parametrize('value',[None,pd.NaT,np.datetime64('NaT'),np.datetime64('NaT','M')])
def test_missing_epoch_has_no_integer(value):
    with pytest.raises(TypeError if value is None else ValueError):parse_to_epoch(value)

@pytest.mark.parametrize('value',[float('inf'),float('nan'),float('-inf')])
def test_nonfinite_number_is_an_error(value):
    with pytest.raises(ValueError if np.isnan(value) else OverflowError):parse_to_epoch(value)

@pytest.mark.parametrize('unit',['ms','us','ns'])
def test_polars_single_value_native_precision(unit):
    pl=pytest.importorskip('polars')
    value=pl.Series('time',[1704198896123456789//{'ms':1000000,'us':1000,'ns':1}[unit]],dtype=pl.Datetime(unit,'Asia/Shanghai'))
    expected=value.cast(pl.Int64)[0]*{'ms':1000000,'us':1000,'ns':1}[unit]
    assert parse_to_epoch(value,'ns')==expected

def test_polars_single_null_and_many_are_rejected():
    pl=pytest.importorskip('polars')
    for value in [pl.Series([None],dtype=pl.Datetime),pl.Series([0,1],dtype=pl.Datetime)]:
        with pytest.raises(TypeError if value is None else ValueError):parse_to_epoch(value)

@pytest.mark.parametrize('unit',['2147483647W','2147483647D'])
def test_numpy_multiplier_overflow_is_explicit(unit):
    value=np.datetime64(2**63-1,unit)
    with pytest.raises(OverflowError):parse_to_epoch(value,'ns')
    from rstimes import Pddt
    with pytest.raises(OverflowError):Pddt([value])

@pytest.mark.parametrize('sign',[-1,1])
def test_extreme_timezone_callback_is_rejected_before_narrowing(sign):
    from rstimes import Pddt
    class LargeOffset(datetime):
        def utcoffset(self):return timedelta(microseconds=sign*2**64)
    value=LargeOffset(1970,1,1,tzinfo=timezone.utc)
    with pytest.raises(ValueError,match='24'):
        parse_to_epoch(value)
    with pytest.raises(ValueError,match='24'):
        Pddt([value])


@pytest.mark.parametrize("suffix", ["", "é", "中", "😀", "\ud800"])
@pytest.mark.parametrize("fraction,nanos", [("12345678912345", 123456789), ("12", 120000000)])
def test_fraction_digit_run_keeps_precision_and_unicode_suffix(fraction, nanos, suffix):
    """Consume discarded digits and retain equivalent one/wide-byte input rules."""
    from datetime import datetime
    from rstimes import Pddt, parse_str
    text = "2024-01-02T03:04:05." + fraction + suffix
    base = (datetime(2024, 1, 2, 3, 4, 5) - datetime(1970, 1, 1)).days * 86400
    base += 3 * 3600 + 4 * 60 + 5
    expected = base * 1_000_000_000 + nanos
    assert parse_to_epoch(text, "ns") == expected
    assert parse_str(text) == datetime(2024, 1, 2, 3, 4, 5, nanos // 1000)
    assert Pddt([text], unit="ns").asi8[0] == expected
