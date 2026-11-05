# Parse text and epoch values

Use `parse_str` for one text value, `parse` for supported date-like objects or
text, and `parse_to_epoch` for an integer result. Numeric input to the parser is
in seconds by default. Its `unit` selects the **output** resolution.

```{doctest} parser-epoch-units
>>> from datetime import datetime
>>> from rstimes import parse_str, parse_to_epoch
>>> value = parse_str('2024-05-07 12:30')
>>> (type(value) is datetime, value.isoformat())
(True, '2024-05-07T12:30:00')
>>> ticks = parse_to_epoch(1, unit='ms')
>>> (type(ticks) is int, ticks)
(True, 1000)
>>> parse_to_epoch('1970-01-01T00:00:00.000000123', unit='ns')
123
```

`Pddt([1], unit='ms')` uses a different input contract: its numeric value is
already one millisecond tick. See [pandas dates](pddt.md). Choose explicit units
at each boundary.

## Choose a parser and a result

| Call | Input | Result and precision |
|---|---|---|
| `parse_str(text, ...)` | A builtin string | Standard datetime by default; microsecond destination. |
| `parse(value, ...)` | Supported text/date/datetime, numeric epoch seconds, or NumPy datetime64 | Standard datetime by default; native input conversion follows its source role. |
| `parse_to_epoch(value, unit='us', input_unit='s', ...)` | A supported single date/time value | A Python integer in s/ms/us/ns; source nanoseconds can survive. |

`dtclass` chooses the object constructor for `parse_str` and `parse`. It does
not change `parse_to_epoch`, which returns an integer directly. Exact standard
datetime input is reused by `parse`; a datetime subtype normally becomes a
standard datetime unless the requested target is its actual type.

```{doctest} parser-object-inputs
>>> from datetime import date, timedelta, timezone
>>> import numpy as np
>>> from rstimes import parse, Pydt
>>> existing = datetime(2024, 5, 7, 12, tzinfo=timezone.utc, fold=1)
>>> (parse(existing) is existing, parse(existing).fold, parse(existing).tzinfo is timezone.utc)
(True, 1, True)
>>> parsed_date = parse(date(2024, 5, 7))
>>> (type(parsed_date) is datetime, parsed_date.isoformat())
(True, '2024-05-07T00:00:00')
>>> subclass_value = Pydt(2024, 5, 7)
>>> (type(parse(subclass_value)) is datetime, parse(subclass_value, dtclass=Pydt) is subclass_value)
(True, True)
>>> (type(parse_str('2024-05-07', dtclass=Pydt)) is Pydt, parse(1.1).isoformat())
(True, '1970-01-01T00:00:01.100000')
>>> parse(np.datetime64(1, '10D')).isoformat()
'1970-01-11T00:00:00'
>>> parse(np.datetime64(-1, 'ns')).isoformat()
'1969-12-31T23:59:59.999999'
```

NumPy nanoseconds are floored at the microsecond datetime destination, including
negative values. Numeric seconds use the parser's existing float conversion
(round to seven decimal places, then select microseconds). This is different
from Delta's final ties-to-even projection. Numeric inputs are epoch-based;
they do not consult the host's local timezone.

A string subclass belongs in `parse`, which invokes its real string conversion.
`parse_str` requires an exact builtin string.

```{doctest} parser-string-subclasses
>>> conversions = []
>>> class Text(str):
...     def __str__(self):
...         conversions.append(1)
...         return '2024-05-07'
>>> text = Text('application token')
>>> parse(text).isoformat()
'2024-05-07T00:00:00'
>>> conversions
[1]
>>> try:
...     parse_str(text)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

## Control field order and defaults

The precedence for each ordering flag is an explicit non-`None` call argument,
then Configs, then year-first=True/day-first=False without a configuration.
An explicit `False` overrides a configured `True`. Other switches default to
`isoformat=True` and `strict=False`. ISO-first parsing can fall back to the
general grammar; it is not a strict-ISO-only switch.

`default` must be independently complete when it is needed. It fills missing
year/month/day and supplies a two-digit-year reference; its clock and timezone
do not fill the result. A datetime default also supplies its `fold` for object
construction. Native object input does not parse an irrelevant textual default.

```{doctest} parser-order-default
>>> from rstimes import Configs
>>> config = Configs(yearfirst=False, dayfirst=True)
>>> parse_str('01/02/2024', cfg=config).isoformat()
'2024-02-01T00:00:00'
>>> parse_str('01/02/2024', cfg=config, dayfirst=False).isoformat()
'2024-01-02T00:00:00'
>>> parse_str('May 7', default='2024-01-01', isoformat=False).isoformat()
'2024-05-07T00:00:00'
>>> fallback = datetime(2024, 2, 29, 23, 59, tzinfo=timezone.utc, fold=1)
>>> completed = parse_str('March 1', default=fallback)
>>> (completed.year, completed.month, completed.day, completed.hour, completed.minute, completed.tzinfo, completed.fold)
(2024, 3, 1, 0, 0, None, 1)
>>> parse(existing, default='not a complete date') is existing
True
>>> parse_str('01/02/24', default='2020-01-01', yearfirst=False, dayfirst=False).isoformat()
'2024-01-02T00:00:00'
```

## Distinguish strict fields from ISO and timezone rules

By default, invalid recognized fields are clipped to their valid boundaries
without carrying into the next field. Strict mode rejects invalid explicit
fields, conflicting repeated fields, and a weekday contradicting a complete
date. It does not turn parse failures into missing values or manage DST.
A two-digit year requires non-strict mode and an explicit complete default.

```{doctest} parser-strict-fields
>>> from rstimes.errors import ParseError
>>> parse_str('2024-02-30 12:99').isoformat()
'2024-02-29T12:59:00'
>>> for text, options in (('2024-02-30', {'strict': True}), ('Monday 2024-01-02', {'strict': True}), ('01/02/24', {'strict': True, 'default': '2020-01-01'}), ('May 7', {})):
...     try:
...         parse_str(text, **options)
...     except ParseError:
...         continue
...     raise AssertionError(text)
>>> parse_str('2024-01-02 00 PM').hour
13
>>> try:
...     parse_str('2024-01-02 00 PM', strict=True)
... except ParseError as error:
...     print(type(error).__name__)
ParseError
```

## Keep or discard recognized timezones

`parse_str` defaults to `ignoretz=True`, which retains the written clock and
discards a recognized timezone. `parse` preserves a timezone already carried
by an input datetime, even with that default. In contrast, `parse_to_epoch`
defaults to `ignoretz=False` and uses the actual instant; its `ignoretz=True`
discards the offset and interprets the wall clock against the epoch.

```{doctest} parser-timezone-responsibilities
>>> text = '1970-01-01 08:00+08:00'
>>> (parse_str(text).tzinfo, parse_str(text).hour)
(None, 8)
>>> aware = parse_str(text, ignoretz=False)
>>> (aware.utcoffset().total_seconds(), parse(aware) is aware)
(28800.0, True)
>>> (parse_to_epoch(text), parse_to_epoch(text, ignoretz=True))
(0, 28800000000)
>>> (parse_to_epoch(aware), parse_to_epoch(aware, ignoretz=True))
(0, 28800000000)
```

Register region names with `Configs.add_tzone`. The parser supplies the
recognized fields, zone, and fold to the result constructor. Standard datetime
accepts a nonexistent local time; choosing Pydt makes its strict construction
reject that time. Region rules and explicit DST policies for vector dates are
described in their respective guides.

```{doctest} parser-region-constructor
>>> regions = Configs()
>>> regions.add_tzone('Europe/Paris')
True
>>> gap = '2024-03-31 02:30 Europe/Paris'
>>> plain = parse_str(gap, cfg=regions, ignoretz=False)
>>> (type(plain) is datetime, plain.hour, plain.tzinfo.key)
(True, 2, 'Europe/Paris')
>>> try:
...     parse_str(gap, cfg=regions, ignoretz=False, dtclass=Pydt)
... except ValueError as error:
...     print(type(error).__name__)
ValueError
```

## Return integer ticks without a datetime capacity limit

`parse_to_epoch` converts directly to its requested unit. Coarser output selects
the earlier tick; it does not first round through a microsecond datetime.
`input_unit` changes only numeric input ticks. Native temporal input retains
its own unit. A Python integer result is not restricted to an int64 buffer.

```{doctest} parser-integer-precision
>>> (parse_to_epoch(1, unit='ns', input_unit='us'), parse_to_epoch(1e-9, unit='ns'))
(1000, 1)
>>> parse_to_epoch(-0.5e-9, unit='ns')
-1
>>> parse_to_epoch(np.datetime64(123, 'ns'), unit='ns')
123
>>> [parse_to_epoch(np.datetime64(-1, 'ns'), unit=unit) for unit in ('s', 'ms', 'us', 'ns')]
[-1, -1, -1, -1]
>>> parse_to_epoch('0000-01-01', unit='us')
-62167219200000000
>>> parse_to_epoch('0000-01-01', unit='ns')
-62167219200000000000
>>> try:
...     parse_str('0000-01-01')
... except ValueError as error:
...     print(type(error) is ValueError)
True
```

## Custom constructors and errors

A permitted custom result constructor can return `None`. It is called once;
its original exception is preserved when it fails. Input type failures use
`TypeError`, invalid values use `ValueError` or the specific domain error, and
real capacity failures use `OverflowError`. Unsupported boolean substitutes
are rejected without invoking an arbitrary truth conversion.

```{doctest} parser-custom-constructor-errors
>>> calls = []
>>> def optional_result(*args, **kwargs):
...     calls.append(1)
...     return None
>>> parse_str('2024-05-07', dtclass=optional_result) is None
True
>>> calls
[1]
>>> failure = RuntimeError('application constructor failed')
>>> def rejected_result(*args, **kwargs):
...     raise failure
>>> try:
...     parse_str('2024-05-07', dtclass=rejected_result)
... except RuntimeError as error:
...     print(error is failure)
True
>>> for value, expected in ((True, TypeError), (np.bool_(False), TypeError), (None, TypeError), (float('nan'), ValueError), (float('inf'), OverflowError), (np.datetime64('NaT'), ValueError)):
...     try:
...         parse(value)
...     except expected:
...         continue
...     raise AssertionError(value)
>>> for option in ('ignoretz', 'isoformat', 'strict'):
...     try:
...         parse(existing, **{option: 1})
...     except TypeError:
...         continue
...     raise AssertionError(option)
```

Continue with [editable parsing rules](configs.md) and
[native parser inputs](parser-interop.md). Complete signatures, defaults, and
exceptions are in the [parser reference](../api/reference/rstimes/parser/index.rst).
