# Errors and exception protocols

Import domain errors from `rstimes.errors` for parsing and configuration
failures. Other operations use the builtin and callback error families below.
The concrete examples verify their own exception identities; there is a known
limitation to a universal preservation guarantee.

**Known defect RV05:** error-context preview can invoke a str-subclass hook in a
class's real type name and replace an original integer callback exception.
See the [executed counterexamples](../compatibility/known-issues.md). The normal
examples here verify their own exception identities; they do not establish a
universal exception-preservation guarantee for that defective configuration.

| Class | Meaning | Bases |
|---|---|---|
| <span id="rstimes.errors.RstimesError"></span>`RstimesError` | Base of the library's domain errors. | Exception |
| <span id="rstimes.errors.ParseError"></span>`ParseError` | Text cannot be interpreted, a strict field is invalid, or necessary date information is missing. | RstimesError and ValueError |
| <span id="rstimes.errors.ConfigError"></span>`ConfigError` | A token, mapped value, or combination of rules is unusable. | RstimesError and ValueError |

Unsupported argument types use `TypeError`. Invalid values can use `ValueError`
or the appropriate domain subclass. Real arithmetic or destination capacity
failures use `OverflowError`. Optional integrations use an explanatory
`ImportError` when absent. Catch the error that the call actually raises.

```{doctest} error-responsibilities
>>> from rstimes import Configs, parse_str
>>> from rstimes.errors import RstimesError, ParseError, ConfigError
>>> all(issubclass(kind, RstimesError) and issubclass(kind, ValueError) for kind in (ParseError, ConfigError))
True
>>> try:
...     parse_str('2024-02-30', strict=True)
... except ParseError as error:
...     print(type(error).__name__, 'parse_str' in str(error), 'day' in str(error).lower())
ParseError True True
>>> try:
...     Configs().add_month('monday', 2)
... except ConfigError as error:
...     print(type(error).__name__)
ConfigError
>>> try:
...     Configs().add_month('harvest', True)
... except TypeError as error:
...     print(type(error).__name__, isinstance(error, RstimesError))
TypeError False
```

## Preserve application failures

A callback's original exception object, arguments, and cause chain remain
available. An added entry note does not change the exception into a different
class. A callback can itself raise a domain class; that still remains its
original exception.

```{doctest} error-original-callback
>>> original = ParseError('business record failed')
>>> def build(*args, **kwargs):
...     raise original
>>> try:
...     parse_str('2024-01-02', dtclass=build)
... except ParseError as error:
...     print(error is original, error.args)
True ('business record failed',)
```

## Standard exception interface

All three classes support Python's Exception interface. In this table `E`
means one of the three public classes above. State and reconstruction methods
are ordinary Python protocols; use pickle for trusted exception persistence.

| Entry | Parameters, result, and behavior |
|---|---|
| <span id="rstimes.errors.RstimesError.__new__"></span><span id="rstimes.errors.ParseError.__new__"></span><span id="rstimes.errors.ConfigError.__new__"></span>`E(*args)` / `E.__new__(E, *args)` | Allocate an exception; positional details are stored as its `args` tuple. |
| <span id="rstimes.errors.RstimesError.__init__"></span><span id="rstimes.errors.ParseError.__init__"></span><span id="rstimes.errors.ConfigError.__init__"></span>`E.__init__(*args)` | Initialize or replace the positional details; returns None. |
| <span id="rstimes.errors.RstimesError.args"></span><span id="rstimes.errors.ParseError.args"></span><span id="rstimes.errors.ConfigError.args"></span>`E.args` | Read or set the positional argument tuple. |
| <span id="rstimes.errors.RstimesError.add_note"></span><span id="rstimes.errors.ParseError.add_note"></span><span id="rstimes.errors.ConfigError.add_note"></span>`E.add_note(note)` | Add a string note and return None; a non-string raises TypeError. |
| <span id="rstimes.errors.RstimesError.with_traceback"></span><span id="rstimes.errors.ParseError.with_traceback"></span><span id="rstimes.errors.ConfigError.with_traceback"></span>`E.with_traceback(tb)` | Attach a traceback or None and return the same exception. |
| <span id="rstimes.errors.RstimesError.__str__"></span><span id="rstimes.errors.ParseError.__str__"></span><span id="rstimes.errors.ConfigError.__str__"></span><span id="rstimes.errors.RstimesError.__repr__"></span><span id="rstimes.errors.ParseError.__repr__"></span><span id="rstimes.errors.ConfigError.__repr__"></span>`E.__str__()` / `E.__repr__()` | Return a string message or representation. |
| <span id="rstimes.errors.RstimesError.__format__"></span><span id="rstimes.errors.ParseError.__format__"></span><span id="rstimes.errors.ConfigError.__format__"></span>`E.__format__(spec)` | Empty spec returns the string message; unsupported nonempty spec raises TypeError. |
| <span id="rstimes.errors.RstimesError.__eq__"></span><span id="rstimes.errors.ParseError.__eq__"></span><span id="rstimes.errors.ConfigError.__eq__"></span><span id="rstimes.errors.RstimesError.__ne__"></span><span id="rstimes.errors.ParseError.__ne__"></span><span id="rstimes.errors.ConfigError.__ne__"></span>`E.__eq__(other)` / `E.__ne__(other)` | Identity comparison with normal reflected negotiation. |
| <span id="rstimes.errors.RstimesError.__lt__"></span><span id="rstimes.errors.ParseError.__lt__"></span><span id="rstimes.errors.ConfigError.__lt__"></span><span id="rstimes.errors.RstimesError.__le__"></span><span id="rstimes.errors.ParseError.__le__"></span><span id="rstimes.errors.ConfigError.__le__"></span><span id="rstimes.errors.RstimesError.__gt__"></span><span id="rstimes.errors.ParseError.__gt__"></span><span id="rstimes.errors.ConfigError.__gt__"></span><span id="rstimes.errors.RstimesError.__ge__"></span><span id="rstimes.errors.ParseError.__ge__"></span><span id="rstimes.errors.ConfigError.__ge__"></span>`E.__lt__` / `E.__le__` / `E.__gt__` / `E.__ge__` | Direct ordinary exception comparisons decline with NotImplemented; no value ordering. |
| <span id="rstimes.errors.RstimesError.__hash__"></span><span id="rstimes.errors.ParseError.__hash__"></span><span id="rstimes.errors.ConfigError.__hash__"></span>`E.__hash__()` | Return the object's integer hash. |
| <span id="rstimes.errors.RstimesError.__getstate__"></span><span id="rstimes.errors.ParseError.__getstate__"></span><span id="rstimes.errors.ConfigError.__getstate__"></span><span id="rstimes.errors.RstimesError.__setstate__"></span><span id="rstimes.errors.ParseError.__setstate__"></span><span id="rstimes.errors.ConfigError.__setstate__"></span>`E.__getstate__()` / `E.__setstate__(state)` | Read or apply ordinary exception metadata; this is not a date-value format. |
| <span id="rstimes.errors.RstimesError.__reduce__"></span><span id="rstimes.errors.ParseError.__reduce__"></span><span id="rstimes.errors.ConfigError.__reduce__"></span><span id="rstimes.errors.RstimesError.__reduce_ex__"></span><span id="rstimes.errors.ParseError.__reduce_ex__"></span><span id="rstimes.errors.ConfigError.__reduce_ex__"></span>`E.__reduce__()` / `E.__reduce_ex__(protocol)` | Return reconstruction information used by pickle. |

```{doctest} error-public-protocols
>>> import pickle
>>> kinds = (RstimesError, ParseError, ConfigError)
>>> for kind in kinds:
...     value = kind.__new__(kind, 'created')
...     assert value.__init__('detail', 3) is None
...     assert type(value) is kind and value.args == ('detail', 3)
...     value.args = ('clean',)
...     assert value.__str__() == 'clean' and value.__format__('') == 'clean'
...     assert value.__repr__().startswith(kind.__name__ + '(')
...     assert type(value.__hash__()) is int
...     assert value.__eq__(value) is True and value.__ne__(value) is False
...     assert value.__eq__(kind('clean')) is NotImplemented
...     for method in ('__lt__', '__le__', '__gt__', '__ge__'):
...         assert getattr(value, method)(kind()) is NotImplemented
...     assert value.add_note('check source row') is None
...     assert value.__notes__ == ['check source row']
...     assert value.with_traceback(None) is value and value.__traceback__ is None
...     value.field = 'record'
...     assert value.__getstate__()['field'] == 'record'
...     other = kind('other')
...     assert other.__setstate__({'field': 'input'}) is None and other.field == 'input'
...     for recipe in (value.__reduce__(), value.__reduce_ex__(pickle.HIGHEST_PROTOCOL)):
...         assert type(recipe) is tuple and callable(recipe[0])
...         assert type(recipe[0](*recipe[1])) is kind
...     restored = pickle.loads(pickle.dumps(value))
...     assert type(restored) is kind and restored.args == ('clean',)
...     assert restored.field == 'record' and restored.__notes__ == ['check source row']
...     try:
...         value.add_note(1)
...     except TypeError:
...         pass
...     else:
...         raise AssertionError('non-string note accepted')
...     try:
...         value.__format__('.2f')
...     except TypeError:
...         pass
...     else:
...         raise AssertionError('numeric exception format accepted')
```

See Python's [exception reference](https://docs.python.org/3/library/exceptions.html)
and [data model](https://docs.python.org/3/reference/datamodel.html) for the full
standard protocols. Batch errors identify a reliable row or argument when
available. Inputs are not returned partly transformed after a failed library
operation; external iterator consumption or callback side effects are separate.
