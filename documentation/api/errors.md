# Errors and exception protocols

## Catch a strict parsing error

(ref-parse-field-error)=
```python
from rstimes import parse_str
from rstimes.errors import ParseError

try:
    parse_str("2024-02-30", strict=True)
except ParseError as error:
    print(type(error).__name__)
```

**Output**

```text
ParseError
```

Import domain errors from `rstimes.errors` for parsing and configuration
failures. Other operations use the builtin and callback error families below.
For input handling and practical recovery, see the
[troubleshooting guide](../troubleshooting.md).

| Class | Meaning | Bases |
|---|---|---|
| <span id="rstimes.errors.RstimesError"></span>`RstimesError` | Base of the library's domain errors. | Exception |
| <span id="rstimes.errors.ParseError"></span>`ParseError` | Text cannot be interpreted, a strict field is invalid, or necessary date information is missing. | RstimesError and ValueError |
| <span id="rstimes.errors.ConfigError"></span>`ConfigError` | A token, mapped value, or combination of rules is unusable. | RstimesError and ValueError |

Unsupported argument types use `TypeError`. Invalid values can use `ValueError`
or the appropriate domain subclass. Real arithmetic or destination capacity
failures use `OverflowError`. Optional integrations use an explanatory
`ImportError` when absent. Catch the error that the call actually raises.

## Preserve application failures

A callback's original exception object, arguments, and cause chain remain
available. An added entry note does not change the exception into a different
class. A callback can itself raise a domain class; that still remains its
original exception.

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

See Python's [exception reference](https://docs.python.org/3/library/exceptions.html)
and [data model](https://docs.python.org/3/reference/datamodel.html) for the full
standard protocols. Batch errors identify a reliable row or argument when
available. Inputs are not returned partly transformed after a failed library
operation; external iterator consumption or callback side effects are separate.

## Exception chains and notes

These attributes are Python exception protocols on the three rsTimes domain
classes. They describe an error and do not carry a date value, unit or timezone.

| Entry on each domain exception | Value and role |
|---|---|
| <span id="rstimes.errors.RstimesError.__cause__"></span><span id="rstimes.errors.ParseError.__cause__"></span><span id="rstimes.errors.ConfigError.__cause__"></span>`E.__cause__` | Explicit exception cause, or None; `raise error from cause` also suppresses implicit context display. |
| <span id="rstimes.errors.RstimesError.__context__"></span><span id="rstimes.errors.ParseError.__context__"></span><span id="rstimes.errors.ConfigError.__context__"></span>`E.__context__` | Previous exception active when this one was raised, or None. |
| <span id="rstimes.errors.RstimesError.__suppress_context__"></span><span id="rstimes.errors.ParseError.__suppress_context__"></span><span id="rstimes.errors.ConfigError.__suppress_context__"></span>`E.__suppress_context__` | Boolean controlling implicit context display; it does not erase the context object. |
| <span id="rstimes.errors.RstimesError.__traceback__"></span><span id="rstimes.errors.ParseError.__traceback__"></span><span id="rstimes.errors.ConfigError.__traceback__"></span>`E.__traceback__` | Traceback object after a raise, or None; `with_traceback` returns the same exception. |
| <span id="rstimes.errors.RstimesError.__notes__"></span><span id="rstimes.errors.ParseError.__notes__"></span><span id="rstimes.errors.ConfigError.__notes__"></span>`E.__notes__` | List of strings created by `add_note`; absent on a new instance until a note is added. |
