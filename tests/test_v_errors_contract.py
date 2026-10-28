"""Approved V/E contracts; assertions use independent public expectations."""
from datetime import datetime, timedelta, tzinfo
import asyncio
from concurrent.futures import CancelledError
import pytest
import rstimes
from rstimes import Configs, Delta, Pydt, parse, parse_str
from rstimes.errors import RstimesError, ParseError, ConfigError


def test_three_domain_classes_have_unambiguous_bases():
    from rstimes import errors
    assert errors.__all__ == ['RstimesError', 'ParseError', 'ConfigError']
    assert issubclass(ParseError, RstimesError) and issubclass(ParseError, ValueError)
    assert issubclass(ConfigError, RstimesError) and issubclass(ConfigError, ValueError)
    assert not issubclass(ParseError, TypeError)
    assert not issubclass(ConfigError, TypeError)
    for name in errors.__all__:
        assert name not in rstimes.__dict__
    assert not hasattr(errors, 'InvalidRelativeDelta')


@pytest.mark.parametrize('kind', [ValueError, TypeError, OverflowError, RuntimeError, ParseError, ConfigError])
def test_numeric_callback_preserves_the_original_error(kind):
    error = kind('conversion failed')
    error.detail = object()
    detail = error.detail
    error.add_note('existing note')
    cause = LookupError('original cause')
    error.__cause__ = cause
    calls = []
    class Number:
        def __index__(self):
            calls.append('index')
            raise error
        def __repr__(self):
            pytest.fail('input repr must not run')
        def __str__(self):
            pytest.fail('input str must not run')
    with pytest.raises(kind) as caught:
        Delta(days=Number())
    assert caught.value is error
    assert error.args == ('conversion failed',)
    assert error.detail is detail and error.__cause__ is cause
    assert error.__notes__[0] == 'existing note'
    assert calls == ['index']
    assert sum('Delta()' in n for n in error.__notes__) == 1


@pytest.mark.parametrize('error', [MemoryError('stop'), KeyboardInterrupt('stop'), SystemExit(7), GeneratorExit(), asyncio.CancelledError(), CancelledError()])
def test_critical_conversion_failure_gets_no_note_or_replacement(error):
    calls=[]
    class Number:
        def __index__(self):
            calls.append(1)
            raise error
    with pytest.raises(type(error)) as caught:
        Delta(days=Number())
    assert caught.value is error and calls == [1]
    assert not hasattr(error, '__notes__')


ABSOLUTE_FIELDS = ('year', 'month', 'day', 'weekday', 'hour', 'minute', 'second', 'millisecond', 'microsecond')


class IndexTypeError(TypeError):
    pass


@pytest.mark.parametrize('field', ABSOLUTE_FIELDS)
@pytest.mark.parametrize('shape', ['keyword', 'mixed', 'positional'])
@pytest.mark.parametrize('kind', [TypeError, IndexTypeError, ValueError])
def test_absolute_index_failure_preserves_the_original_error(field, shape, kind):
    error = kind('original index failure')
    error.detail = object()
    detail = error.detail
    error.__cause__ = LookupError('original cause')
    cause = error.__cause__
    error.add_note('existing note')
    calls = []
    class Index:
        def __index__(self):
            calls.append('index')
            raise error
        def __repr__(self):
            pytest.fail('an external failure must not display its input')
    with pytest.raises(kind) as caught:
        if shape == 'keyword':
            Delta(**{field: Index()})
        elif shape == 'mixed':
            Delta(days=1, **{field: Index()})
        else:
            index = ABSOLUTE_FIELDS.index(field)
            args = [0] * 10 + [None] * (index + 1)
            args[10 + index] = Index()
            Delta(*args)
    assert caught.value is error and error.args == ('original index failure',)
    assert error.detail is detail and error.__cause__ is cause
    assert error.__notes__[0] == 'existing note'
    assert calls == ['index']


@pytest.mark.parametrize('field', ABSOLUTE_FIELDS)
@pytest.mark.parametrize('kind', [MemoryError, KeyboardInterrupt, asyncio.CancelledError])
def test_absolute_index_critical_failure_is_not_replaced_or_annotated(field, kind):
    error = kind('stop')
    calls = []
    class Index:
        def __index__(self):
            calls.append('index')
            raise error
    with pytest.raises(kind) as caught:
        Delta(**{field: Index()})
    assert caught.value is error and calls == ['index']
    assert not hasattr(error, '__notes__')


def test_absolute_index_error_is_not_stringified():
    class Message:
        def __str__(self):
            pytest.fail('external exception text must not be evaluated')
    error = TypeError(Message())
    class Index:
        def __index__(self):
            raise error
    with pytest.raises(TypeError) as caught:
        Delta(year=Index())
    assert caught.value is error


@pytest.mark.parametrize('field', ABSOLUTE_FIELDS)
@pytest.mark.parametrize('value', [9.0, object()])
def test_unsupported_absolute_values_identify_the_field(field, value):
    with pytest.raises(TypeError) as caught:
        Delta(**{field: value})
    assert field in str(caught.value) and 'integer' in str(caught.value)


def test_target_error_is_not_formatted_or_reconstructed():
    class Message:
        def __str__(self):
            pytest.fail('external exception message must not be expanded')
    error = ValueError(Message())
    class Target:
        def __new__(cls, *args, **kwargs):
            raise error
    with pytest.raises(ValueError) as caught:
        parse_str('2024-01-02', dtclass=Target)
    assert caught.value is error
    assert len(error.args) == 1 and isinstance(error.args[0], Message)


def test_standard_note_does_not_call_an_override():
    class Failure(ValueError):
        def add_note(self, text):
            pytest.fail('overridden add_note must not run')
    error = Failure('source')
    def target(*args, **kwargs):
        raise error
    with pytest.raises(Failure) as caught:
        parse_str('2024-01-02', dtclass=target)
    assert caught.value is error
    assert len(error.__notes__) == 1 and 'parse_str' in error.__notes__[0]


def test_genuine_standard_note_failure_is_not_swallowed():
    error=ValueError('source')
    error.__notes__=1
    def target(*args, **kwargs):
        raise error
    with pytest.raises(TypeError, match='__notes__'):
        parse_str('2024-01-02', dtclass=target)


def test_strict_field_creates_one_domain_exception(monkeypatch):
    from rstimes import errors
    calls=[]
    class Tracked(ParseError):
        def __new__(cls, *args):
            calls.append(args)
            return super().__new__(cls, *args)
    monkeypatch.setattr(errors, 'ParseError', Tracked)
    with pytest.raises(Tracked) as caught:
        parse_str('2024-01-02 12:99', strict=True)
    assert len(calls) == 1
    assert 'parse_str' in str(caught.value)
    assert 'minute' in str(caught.value) and '99' in str(caught.value)
    assert caught.value.__cause__ is None


def test_config_field_creates_one_domain_exception(monkeypatch):
    from rstimes import errors
    calls=[]
    class Tracked(ConfigError):
        def __new__(cls, *args):
            calls.append(args)
            return super().__new__(cls, *args)
    monkeypatch.setattr(errors,'ConfigError',Tracked)
    with pytest.raises(Tracked) as caught:
        Configs().add_month('harvest',13)
    assert len(calls)==1
    assert 'Configs.add_month' in str(caught.value)
    assert caught.value.__cause__ is None


def test_operator_not_implemented_allows_reflected_operation():
    sentinel=object()
    class Right:
        def __radd__(self, left):
            return sentinel
    assert Delta.__add__(Delta(days=1),object()) is NotImplemented
    assert Delta(days=1)+Right() is sentinel


def test_external_callback_domain_error_remains_external():
    error=ParseError('user supplied')
    def target(*args,**kwargs):
        raise error
    with pytest.raises(ParseError) as caught:
        parse_str('2024-01-02',dtclass=target)
    assert caught.value is error and error.args==('user supplied',)
    assert error.__notes__ and 'parse_str' in error.__notes__[-1]
