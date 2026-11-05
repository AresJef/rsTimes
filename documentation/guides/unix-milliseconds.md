# Convert aware datetimes to Unix milliseconds

`to_unix_ms(value)` accepts an aware datetime and returns builtin integer Unix
milliseconds. A sub-millisecond remainder is floored, including before the
epoch. `from_unix_ms(value)` returns a builtin datetime with `timezone.utc`.

These helpers have a deliberately narrow interface. Use the shared parser's
integer output when you need other input types, other units, or a wider
calendar range.

```{doctest} unix-ms-round-trip
>>> from datetime import datetime, timedelta, timezone
>>> from rstimes import to_unix_ms, from_unix_ms, Pydt
>>> epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
>>> (type(to_unix_ms(epoch)) is int, to_unix_ms(epoch))
(True, 0)
>>> value = from_unix_ms(-1)
>>> (type(value) is datetime, value.tzinfo is timezone.utc, value.isoformat())
(True, True, '1969-12-31T23:59:59.999000+00:00')
>>> to_unix_ms(epoch - timedelta(microseconds=1))
-1
>>> to_unix_ms(epoch + timedelta(microseconds=1999))
1
>>> east = datetime(1970, 1, 1, 8, tzinfo=timezone(timedelta(hours=8)))
>>> to_unix_ms(east)
0
>>> to_unix_ms(Pydt(1970, 1, 1, tzinfo='UTC'))
0
```

## Integer input and datetime capacity

`from_unix_ms` accepts a Python int or a real int subclass. It rejects bool,
NumPy integers, floats, numeric strings, and an object supplying only
`__index__`. This helper does not use the broader integer protocol of calendar
field parameters. Its inclusive range is −62,135,596,800,000 through
253,402,300,799,999 milliseconds (years 1–9999 in UTC).

```{doctest} unix-ms-input-and-range
>>> import numpy as np
>>> class Count(int):
...     pass
>>> from_unix_ms(Count(0)) == epoch
True
>>> class IndexOnly:
...     def __index__(self):
...         return 0
>>> for invalid in (True, np.int64(0), 0.0, '0', IndexOnly()):
...     try:
...         from_unix_ms(invalid)
...     except TypeError:
...         continue
...     raise AssertionError(type(invalid))
>>> lower, upper = -62135596800000, 253402300799999
>>> (from_unix_ms(lower).isoformat(), from_unix_ms(upper).isoformat())
('0001-01-01T00:00:00+00:00', '9999-12-31T23:59:59.999000+00:00')
>>> for invalid in (lower - 1, upper + 1):
...     try:
...         from_unix_ms(invalid)
...     except OverflowError:
...         continue
...     raise AssertionError(invalid)
```

A naive datetime has no instant for this helper and raises `ValueError`.
An unsupported input type raises `TypeError`; real datetime/tzinfo callback
exceptions preserve their original object and cause.

```{doctest} unix-ms-errors
>>> try:
...     to_unix_ms(datetime(1970, 1, 1))
... except ValueError as error:
...     print(type(error).__name__, 'aware' in str(error))
ValueError True
>>> try:
...     to_unix_ms(0)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

See [parsing and epoch units](parsing.md) for `parse_to_epoch`, whose `unit`
selects its output resolution and whose default numeric input is seconds.
