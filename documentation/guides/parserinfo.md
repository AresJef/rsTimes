# Adapt dateutil parserinfo

`Configs.from_parserinfo(info)` imports supported vocabulary and order flags
from a real dateutil `parserinfo` instance or subclass. Install the optional
`python-dateutil` dependency before starting Python. If you add it to a running
environment, restart Python before using the integration.

The adapter copies data, not custom dateutil parsing methods or its private
caches. Subsequent changes to the source do not alter the resulting Configs.

```{doctest} parserinfo-normal
>>> from dateutil.parser import parserinfo
>>> from rstimes import Configs, parse_str
>>> info = parserinfo(yearfirst=False, dayfirst=True)
>>> config = Configs.from_parserinfo(info)
>>> (type(config) is Configs, config.yearfirst, config.dayfirst)
(True, False, True)
>>> parse_str('01/02/2024', cfg=config).isoformat()
'2024-02-01T00:00:00'
>>> info.MONTHS = [('replacementmonth',)]
>>> (config.month['jan'], 'replacementmonth' in config.month)
(1, False)
>>> class BusinessInfo(parserinfo):
...     def convertyear(self, year, century_specified=False):
...         raise RuntimeError('this dateutil method is not the shared parser')
>>> independent = Configs.from_parserinfo(BusinessInfo())
>>> parse_str('7 May 2024', cfg=independent).isoformat()
'2024-05-07T00:00:00'
```

## Table and value roles

| parserinfo attribute | Accepted non-None outer container | Configs table |
|---|---|---|
| `JUMP` | list, tuple, or set | `jump` |
| `PERTAIN` | list, tuple, or set | `pertain` |
| `UTCZONE` | list, tuple, or set | `utc` |
| `TZOFFSET` | dict, values in integer seconds | `tzoffset` |
| `MONTHS` | list or tuple of aliases | `month`, row position selects 1–12 |
| `WEEKDAYS` | list or tuple of aliases | `weekday`, row position selects Monday=0 |
| `HMS` | list or tuple of aliases | `hms`, row position selects hour/minute/second |
| `AMPM` | list or tuple of aliases | `ampm`, row position selects AM/PM |

Real subclasses of the listed containers are accepted. A string row is one
complete alias. The adapter applies the same mapped-value, case expansion, and
conflict checks as Configs edits. `None` means import no rules for that table;
it does not restore the ordinary default vocabulary.

```{doctest} parserinfo-empty-and-offset
>>> info = parserinfo()
>>> for table in ('JUMP', 'PERTAIN', 'UTCZONE', 'TZOFFSET', 'MONTHS', 'WEEKDAYS', 'HMS', 'AMPM'):
...     setattr(info, table, None)
>>> empty = Configs.from_parserinfo(info)
>>> all(not getattr(empty, name) for name in ('jump', 'pertain', 'utc', 'tzoffset', 'month', 'weekday', 'hms', 'ampm'))
True
>>> info = parserinfo()
>>> info.TZOFFSET = {'desktime': 3600}
>>> configured = Configs.from_parserinfo(info)
>>> configured.tzoffset['desktime']
3600
>>> value = parse_str('1970-01-01 01:00 desktime', cfg=configured, ignoretz=False)
>>> (value.hour, value.utcoffset().total_seconds())
(1, 3600.0)
```

## Reject unsupported outer containers and flags

An empty container of the wrong kind is still an invalid table. Generators are
not accepted for these table attributes. The two preference flags require real
Python or NumPy booleans, rather than a general truth conversion.

```{doctest} parserinfo-rejected-inputs
>>> import numpy as np
>>> for table, invalid in (('MONTHS', set()), ('HMS', {}), ('JUMP', iter(())), ('TZOFFSET', [])):
...     info = parserinfo()
...     setattr(info, table, invalid)
...     try:
...         Configs.from_parserinfo(info)
...     except TypeError as error:
...         assert table in str(error)
...         continue
...     raise AssertionError(table)
>>> for invalid in (1, None, 'yes'):
...     info = parserinfo()
...     info.dayfirst = invalid
...     try:
...         Configs.from_parserinfo(info)
...     except TypeError:
...         continue
...     raise AssertionError(invalid)
>>> info = parserinfo()
>>> info.dayfirst = np.bool_(True)
>>> Configs.from_parserinfo(info).dayfirst
True
>>> try:
...     Configs.from_parserinfo(object())
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

This integration does not make dateutil a dependency of ordinary parsing.
Its source exception and supported subclass-attribute behavior are preserved;
it does not run a dateutil parser as a fallback. For normal edits, use the
[Configs guide](configs.md).
