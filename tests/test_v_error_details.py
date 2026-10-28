"""Final error categories and actionable, bounded public explanations."""
from datetime import datetime, timedelta, timezone, tzinfo
from concurrent.futures import CancelledError
from pathlib import Path
import subprocess
import sys
import zoneinfo
from dateutil.parser import parserinfo
import pytest
from rstimes import Configs, Delta, Pddt, Pydt, parse, parse_str, parse_to_epoch, from_unix_ms, to_unix_ms
from rstimes import _native
from rstimes.errors import ParseError, ConfigError


@pytest.mark.parametrize('operation', ['add', 'sub'])
def test_wide_arithmetic_preserves_one_necessary_secondary_failure(operation):
    """A real wide overflow must not recreate and discard a helper's failure."""
    script = '''
from pathlib import Path
import operator
import sys
from rstimes import Delta, _native
import rstimes.errors as errors
assert Path(_native.__file__).resolve() == Path(sys.argv[2]).resolve()
marker = MemoryError('wide error construction failed')
calls = []
def fail(error):
    calls.append(error)
    raise marker
errors._own_error = fail
maximum = 2**63 - 1
# A narrow intermediate overflow that normalizes back into range is not an
# error and must not enter the Python error helper at all.
assert Delta(years=maximum) - Delta(months=-1) == Delta(years=maximum, months=1)
assert not calls
if sys.argv[1] == 'add':
    left, right, operation = Delta(years=maximum), Delta(years=1), operator.add
else:
    left, right, operation = Delta(years=-(2**63)), Delta(years=1), operator.sub
try:
    operation(left, right)
except MemoryError as error:
    assert error is marker and len(calls) == 1
    assert error.args == ('wide error construction failed',)
    assert not hasattr(error, '__notes__') and error.__cause__ is None
else:
    raise AssertionError('the real secondary failure was lost')
'''
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, operation, str(Path(_native.__file__).resolve())],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def details(error):
    return str(error)+' '.join(getattr(error,'__notes__',()))

@pytest.mark.parametrize('entry',[parse,parse_str,parse_to_epoch])
def test_required_scalar_none_is_a_type_error(entry):
    with pytest.raises(TypeError):entry(None)

@pytest.mark.parametrize('entry',[parse,parse_to_epoch,Pydt.fromseconds])
@pytest.mark.parametrize('value,kind',[(float('nan'),ValueError),(float('inf'),OverflowError),(float('-inf'),OverflowError)])
def test_nonfinite_scalar_categories(entry,value,kind):
    with pytest.raises(kind):entry(value)

@pytest.mark.parametrize('call',[
 lambda: from_unix_ms(10**30),
 lambda: to_unix_ms(datetime(1,1,1,tzinfo=timezone(timedelta(hours=1)))),
])
def test_unix_real_overflow_retains_its_category(call):
    with pytest.raises(OverflowError) as caught:call()
    assert 'unix_ms' in details(caught.value)

@pytest.mark.parametrize('text',['not a date','2024-02-30','2024-01-02 12:99'])
def test_owned_text_failure_is_parse_error(text):
    with pytest.raises(ParseError) as caught:
        parse_str(text,strict=True)
    assert caught.value.__cause__ is None


def test_unknown_timezone_is_config_error_with_real_cause():
    with pytest.raises(ConfigError) as caught:
        Configs().add_tzone('Definitely/Unknown')
    assert caught.value.__cause__ is not None
    text=details(caught.value)
    assert 'Configs.add_tzone' in text and 'data' in text

@pytest.mark.parametrize('value',[1,{},[],object()])
def test_config_unit_type_errors_are_not_domain_errors(value):
    with pytest.raises(TypeError) as caught:
        Pddt(['2024-01-02'],unit=value)
    assert type(caught.value) is TypeError
    assert 'unit' in details(caught.value)


def test_bulk_parse_reports_the_failed_data_index():
    with pytest.raises(ParseError) as caught:
        Pddt([datetime(2024,1,1),'not a date'])
    assert 'Pddt()' in str(caught.value) and 'data[1]' in str(caught.value)


def test_iterator_read_failure_has_no_claimed_element_value():
    error=RuntimeError('read failed')
    def values():
        yield datetime(2024,1,1)
        raise error
    with pytest.raises(RuntimeError) as caught:
        Pddt(values())
    assert caught.value is error
    assert len(error.__notes__)==1 and 'reading data[1]' in error.__notes__[0]


def test_parse_preview_is_bounded_before_escaping():
    value='\\' * 3000
    with pytest.raises(ParseError) as caught:parse_str(value)
    text=str(caught.value)
    assert 'length 3000' in text
    assert len(text)<300


def test_optional_error_attributes_are_not_overwritten():
    error=ValueError('source')
    marker=object()
    error._rstimes_entry_note=marker
    error._rstimes_failure_origin=marker
    class Number:
        def __index__(self):raise error
    with pytest.raises(ValueError) as caught:Delta(days=Number())
    assert caught.value is error
    assert error._rstimes_entry_note is marker and error._rstimes_failure_origin is marker


def test_parserinfo_source_error_preserves_identity_and_one_note():
    error=TypeError('source table failed')
    class Info(parserinfo):
        def __getattribute__(self,name):
            if name=='MONTHS':raise error
            return super().__getattribute__(name)
    source=Info.__new__(Info)
    source.yearfirst=True;source.dayfirst=False
    with pytest.raises(TypeError) as caught:Configs.from_parserinfo(source)
    assert caught.value is error and error.args==('source table failed',)
    assert len(error.__notes__)==1 and 'info.MONTHS' in error.__notes__[0]


def test_unparseable_string_can_still_negotiate_subtraction():
    class Text(str):
        def __rsub__(self,other):return 'reflected result'
    assert Pydt(2024,1,2)-Text('not a date')=='reflected result'

@pytest.mark.parametrize('kind',[ValueError,TypeError,ParseError,OverflowError,MemoryError])
def test_string_conversion_failure_is_never_not_implemented(kind):
    error=kind('string source failed')
    calls=[]
    class Text(str):
        def __str__(self):calls.append(1);raise error
        def __rsub__(self,other):pytest.fail('a real failure cannot negotiate')
    with pytest.raises(kind) as caught:Pydt(2024,1,2)-Text('2024-01-01')
    assert caught.value is error and calls==[1]


@pytest.mark.parametrize('entry',[parse_str,parse_to_epoch])
def test_final_offset_error_reports_the_actual_total(entry):
    cfg=Configs();cfg.add_tzoffset('XYZ',hours=23)
    with pytest.raises(ParseError) as caught:
        entry('2024-01-02 12:00 XYZ+02:00',cfg=cfg,ignoretz=False)
    assert '+25:00:00' in str(caught.value) and '24:00:00' in str(caught.value)


@pytest.mark.parametrize('route', ['boolean', 'float', 'index', 'pickle', 'unix', 'factory', 'zone-hash', 'offset', 'pddt-name', 'replace-index', 'comparison-offset', 'pddt-unit'])
def test_python_callback_does_not_rewrite_a_previously_owned_error(route):
    with pytest.raises(ValueError) as initial:
        Delta(hour=24)
    error=initial.value
    original=error.args
    calls=[]
    def fail():
        calls.append(1)
        raise error
    class Number:
        def __bool__(self):return fail()
        def __float__(self):return fail()
        def __index__(self):return fail()
    class Date(datetime):
        def utcoffset(self):return fail()
    class Factory(Pydt):
        @classmethod
        def fromdatetime(cls,*args,**kwargs):return fail()
    class Name(str):
        def __hash__(self):return fail()
    class Unit(str):
        def __eq__(self,other):return fail()
    class Zone(tzinfo):
        def utcoffset(self, value):return fail()
    if route=='boolean':call=lambda:Pydt(2024,1,1).diff(datetime(2024,1,2),'D',absolute=Number())
    elif route=='float':call=lambda:Pydt.fromseconds(Number())
    elif route=='index':call=lambda:Pydt(Number(),1,1)
    elif route=='pickle':call=lambda:Pydt(2024,1,1).__reduce_ex__(Number())
    elif route=='unix':call=lambda:to_unix_ms(Date(2024,1,1))
    elif route=='factory':call=Factory.utcnow
    elif route=='zone-hash':call=lambda:Pydt(2024,1,1,tzinfo=Name('UTC'))
    elif route=='pddt-name':call=lambda:Pddt(['2024-01-01'],name=Name('index'))
    elif route=='pddt-unit':call=lambda:Pddt(['2024-01-01'],unit=Unit('us'))
    elif route=='replace-index':call=lambda:Pydt(2024,1,1).replace(year=Number())
    elif route=='comparison-offset':call=lambda:Pydt(2024,1,1,tzinfo=Zone()) < datetime(2024,1,1,tzinfo=timezone.utc)
    else:call=lambda:Pydt(2024,1,1,tzinfo=Zone()).tz_convert('UTC')
    if route == "boolean":
        with pytest.raises(TypeError):
            call()
        assert calls == [] and error.args == original
        return
    with pytest.raises(ValueError) as caught:call()
    assert caught.value is error and error.args==original and calls==[1]
    assert len(error.__notes__)==1


@pytest.mark.parametrize('version',[None,1.0,'1',True])
def test_pydt_restore_wrong_version_type_names_the_field(version):
    from rstimes.pydt import _restore_pydt
    with pytest.raises(TypeError) as caught:
        _restore_pydt(Pydt,version,(2024,1,1,0,0,0,0),None,0)
    assert 'state.version' in str(caught.value)


def test_pydt_restore_wrong_field_type_names_the_field():
    from rstimes.pydt import _restore_pydt
    with pytest.raises(TypeError) as caught:
        _restore_pydt(Pydt,1,(2024,1,1,0,'bad',0,0),None,0)
    assert 'state.fields.minute' in str(caught.value)


@pytest.mark.parametrize('position,value,field',[(0,1,'tag'),(1,True,'version'),(2,'yes','yearfirst'),(3,1,'dayfirst'),(4,[],'namespaces'),(5,[],'tzone')])
def test_config_restore_structural_type_errors_are_atomic_and_name_the_field(position,value,field):
    cfg=Configs(); before=cfg.__reduce__()[2]
    state=list(before);state[position]=value
    with pytest.raises(TypeError) as caught:cfg.__setstate__(tuple(state))
    assert 'state.'+field in str(caught.value)
    assert cfg.__reduce__()[2]==before


def test_error_constructor_secondary_failure_keeps_its_original_identity(monkeypatch):
    from rstimes import errors
    with pytest.raises(ValueError) as initial:Delta(hour=24)
    error=initial.value; original=error.args
    calls=[]
    class Broken(ParseError):
        def __new__(cls,*args):
            calls.append(1)
            raise error
    monkeypatch.setattr(errors,'ParseError',Broken)
    with pytest.raises(ValueError) as caught:parse_str('2024-01-02 12:99',strict=True)
    assert caught.value is error and error.args==original and calls==[1]


@pytest.mark.parametrize('kind',[MemoryError,CancelledError])
def test_critical_zone_failure_does_not_probe_the_unavailable_fallback(monkeypatch,kind):
    cfg=Configs(); before=cfg.__reduce__()[2]
    error=kind('zone source failed'); calls=[]
    def source(key):
        calls.append(key)
        raise error
    class Forbidden(type):
        def __instancecheck__(cls,value):
            pytest.fail('critical exceptions cannot enter an optional fallback')
    class MissingZone(metaclass=Forbidden):pass
    monkeypatch.setattr(zoneinfo,'ZoneInfo',source)
    monkeypatch.setattr(zoneinfo,'ZoneInfoNotFoundError',MissingZone)
    with pytest.raises(kind) as caught:cfg.add_tzone('Asia/Shanghai')
    assert caught.value is error and calls==['Asia/Shanghai']
    assert not hasattr(error,'__notes__') and cfg.__reduce__()[2]==before


@pytest.mark.parametrize('entry',[parse_str,parse])
def test_bad_target_result_reports_the_result_without_calling_its_display(entry):
    class Result:
        def __repr__(self):pytest.fail('result repr must not run')
        def __str__(self):pytest.fail('result str must not run')
    result=Result();calls=[]
    def target(*args,**kwargs):calls.append(1);return result
    with pytest.raises(TypeError) as caught:entry('2024-01-02',dtclass=target)
    assert 'dtclass result' in str(caught.value) and '<Result>' in str(caught.value)
    assert calls==[1]


def test_invalid_unicode_zone_key_is_a_configuration_error_with_real_cause():
    cfg=Configs(); before=cfg.__reduce__()[2]
    with pytest.raises(ConfigError) as caught:cfg.add_tzone('\ud800')
    assert isinstance(caught.value.__cause__,UnicodeEncodeError)
    assert 'key' in str(caught.value) and cfg.__reduce__()[2]==before


@pytest.mark.parametrize('query',['_pydt_calendar','_pydt_flag'])
def test_invalid_private_fixed_query_is_an_internal_runtime_error(query):
    from rstimes import _native
    with pytest.raises(RuntimeError):getattr(_native,query)(Pydt(2024,1,1),255)
