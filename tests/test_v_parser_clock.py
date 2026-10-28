"""V01-V03: complete tokens and explicit seconds across native policies."""
from datetime import date, datetime, timedelta, timezone
import pytest
from rstimes import Configs, Pydt, parse, parse_str, parse_to_epoch
from rstimes.errors import ParseError

ENTRIES=[parse_str,parse,Pydt.parse,parse_to_epoch]


def expected_result(entry, value):
    if entry is not parse_to_epoch:
        return value
    zero=datetime(1970,1,1,tzinfo=value.tzinfo) if value.tzinfo is None else datetime(1970,1,1,tzinfo=timezone.utc)
    delta=value-zero
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds


@pytest.mark.parametrize('entry',ENTRIES)
@pytest.mark.parametrize('strict',[False,True])
@pytest.mark.parametrize('isoformat',[False,True])
@pytest.mark.parametrize('hour',['1','000001'])
def test_colon_takes_priority_over_compact_length(entry,strict,isoformat,hour):
    expected=datetime(2024,1,2,1,2)
    assert entry('2024-01-02 '+hour+':02',strict=strict,isoformat=isoformat)==expected_result(entry,expected)


@pytest.mark.parametrize('entry',ENTRIES)
@pytest.mark.parametrize('isoformat',[False,True])
def test_long_explicit_hour_clamps_or_reports_hour(entry,isoformat):
    text='2024-01-02 12345678:02'
    assert entry(text,strict=False,isoformat=isoformat)==expected_result(entry,datetime(2024,1,2,23,2))
    with pytest.raises(ParseError,match='hour'):
        entry(text,strict=True,isoformat=isoformat)


@pytest.mark.parametrize('entry',ENTRIES)
@pytest.mark.parametrize('isoformat',[False,True])
@pytest.mark.parametrize('clock,us',[
    ('12:30:00.1 123000',0),
    ('12:30:00 123000.1',100000),
    ('12:30:00.1 123000.1',100000),
])
def test_explicit_second_replaces_its_whole_fraction(entry,isoformat,clock,us):
    assert entry('2024-01-02 '+clock,isoformat=isoformat)==expected_result(entry,datetime(2024,1,2,12,30,0,us))


@pytest.mark.parametrize('entry',ENTRIES)
@pytest.mark.parametrize('isoformat',[False,True])
@pytest.mark.parametrize('clock',['12:30:00.1 123000','12:30:00 123000.1'])
def test_strict_seconds_compare_the_whole_fraction(entry,isoformat,clock):
    with pytest.raises(ParseError,match='[Cc]onflict'):
        entry('2024-01-02 '+clock,isoformat=isoformat,strict=True)


@pytest.mark.parametrize('isoformat',[False,True])
def test_epoch_strict_seconds_include_the_nanosecond_tail(isoformat):
    with pytest.raises(ParseError,match='nanosecond'):
        parse_to_epoch('2024-01-02 12:30:00 123000.000000001',unit='ns',strict=True,isoformat=isoformat)
    assert parse_to_epoch('2024-01-02 12:30:00 123000.000000001',unit='ns',isoformat=isoformat)%1000==1


@pytest.mark.parametrize('entry',ENTRIES)
@pytest.mark.parametrize('isoformat',[False,True])
def test_an_hour_minute_only_does_not_clear_an_earlier_second(entry,isoformat):
    result=datetime(2024,1,2,12,30,45,100000)
    assert entry('2024-01-02 12:30:45.1 12:30',isoformat=isoformat)==expected_result(entry,result)


@pytest.mark.parametrize('entry',[parse_str,parse_to_epoch])
@pytest.mark.parametrize('strict',[False,True])
@pytest.mark.parametrize('isoformat',[False,True])
@pytest.mark.parametrize('sign',[1,-1])
@pytest.mark.parametrize('offset,seconds',[('00:00:012',12),('00:00:010.5',10.5),('00:00:1.5',1.5)])
def test_offset_seconds_are_read_completely(entry,strict,isoformat,sign,offset,seconds):
    zone=timezone(timedelta(seconds=seconds*sign))
    text='2024-01-02 12:00'+('+' if sign==1 else '-')+offset
    assert entry(text,strict=strict,isoformat=isoformat,ignoretz=False)==expected_result(entry,datetime(2024,1,2,12,tzinfo=zone))


@pytest.mark.parametrize('entry',[parse_str,parse_to_epoch])
@pytest.mark.parametrize('isoformat',[False,True])
@pytest.mark.parametrize('sign',[1,-1])
@pytest.mark.parametrize('offset,seconds,field',[('00:00:123',59,'second'),('01:234',7140,'minute')])
def test_offset_field_role_survives_clamping(entry,isoformat,sign,offset,seconds,field):
    text='2024-01-02 12:00'+('+' if sign==1 else '-')+offset
    value=datetime(2024,1,2,12,tzinfo=timezone(timedelta(seconds=sign*seconds)))
    assert entry(text,isoformat=isoformat,ignoretz=False)==expected_result(entry,value)
    with pytest.raises(ParseError,match='timezone '+field):
        entry(text,isoformat=isoformat,ignoretz=False,strict=True)


@pytest.mark.parametrize('entry', ENTRIES)
@pytest.mark.parametrize('strict', [False, True])
@pytest.mark.parametrize('isoformat', [False, True])
@pytest.mark.parametrize('ignoretz', [False, True])
@pytest.mark.parametrize('prefix', [
    '2024-01-02 12:34:56', '2 Jan 2024 12:34:56', '2024-01-02T12:34',
])
@pytest.mark.parametrize('suffix,offset', [
    ('+01:30', timedelta(hours=1, minutes=30)),
    ('+0130', timedelta(hours=1, minutes=30)),
    ('+01:30:15', timedelta(hours=1, minutes=30, seconds=15)),
    ('+013015', timedelta(hours=1, minutes=30, seconds=15)),
    ('+0130:15', timedelta(hours=1, minutes=30, seconds=15)),
    ('+01:30:15.123456', timedelta(hours=1, minutes=30, seconds=15, microseconds=123456)),
    ('+013015.123456', timedelta(hours=1, minutes=30, seconds=15, microseconds=123456)),
    ('+0130:15.123456', timedelta(hours=1, minutes=30, seconds=15, microseconds=123456)),
    ('-00:00:30', timedelta(seconds=-30)),
    ('-000030', timedelta(seconds=-30)),
    ('-0000:30', timedelta(seconds=-30)),
])
def test_numeric_offset_is_consumed_as_one_field(
    entry, strict, isoformat, ignoretz, prefix, suffix, offset,
):
    """Ignoring an offset may remove the zone, never change the clock."""
    wall = datetime(2024, 1, 2, 12, 34, 0 if prefix.endswith('12:34') else 56)
    expected = wall if ignoretz else wall.replace(tzinfo=timezone(offset))
    options = dict(strict=strict, isoformat=isoformat, ignoretz=ignoretz)
    if entry is parse_to_epoch:
        options['unit'] = 'ns'
        elapsed = wall - datetime(1970, 1, 1)
        if not ignoretz:
            elapsed -= offset
        wanted = ((elapsed.days * 86400 + elapsed.seconds) * 1000000 + elapsed.microseconds) * 1000
        assert entry(prefix + suffix, **options) == wanted
    else:
        result = entry(prefix + suffix, **options)
        assert result.replace(tzinfo=None) == wall
        assert result.utcoffset() == expected.utcoffset()


def test_compact_offset_reaches_pydt_combine_and_date_difference():
    offset = timezone(timedelta(hours=1, minutes=30, seconds=15))
    expected = Pydt(2024, 5, 7, 12, 34, 56, tzinfo=offset)
    assert Pydt.combine(date(2024, 5, 7), '12:34:56+013015') == expected
    text = '2024-05-07 12:34:56+013015'
    assert expected.diff(text, 's') == 0
    assert expected - text == timedelta(0)


def test_registered_region_still_wins_over_complete_numeric_offset():
    cfg = Configs()
    cfg.add_tzone('Asia/Shanghai')
    value = parse_str('2024-01-02 12:34:56+013015 Asia/Shanghai', cfg=cfg, ignoretz=False)
    assert value.replace(tzinfo=None) == datetime(2024, 1, 2, 12, 34, 56)
    assert value.utcoffset() == timedelta(hours=8)
