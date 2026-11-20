# Convert between UTC instants and Unix milliseconds

Use `to_unix_ms` with an aware datetime. It returns a Python int.
`from_unix_ms` returns a standard datetime with `timezone.utc`.

## Convert an aware datetime just before the epoch

(unix-ms-floor-negative-fraction)=
```python
from datetime import datetime, timezone

from rstimes import to_unix_ms

value = datetime(
    1969, 12, 31, 23, 59, 59, 999999,
    tzinfo=timezone.utc,
)
milliseconds = to_unix_ms(value)
print(milliseconds)
```

**Output**

```text
-1
```

The input is one microsecond before the epoch. The conversion selects the
earlier millisecond tick. Offset-aware values use their actual instant.
A naive datetime raises `ValueError`; supply an aware datetime in the
zone that describes its clock time.

## Read a negative Unix millisecond

(unix-ms-restore-utc-datetime)=
```python
from rstimes import from_unix_ms

value = from_unix_ms(-1)
print(value.isoformat())
```

**Output**

```text
1969-12-31T23:59:59.999000+00:00
```

`from_unix_ms` accepts a Python int or a real int subclass. A bool, NumPy
integer, float, numeric string, or object supplying only `__index__` raises
`TypeError`. Its inclusive range is `-62135596800000` through
`253402300799999`, the millisecond ticks in years 1 to 9999 UTC. A value
outside that range raises `OverflowError`. Real timezone callback exceptions
propagate to the caller.

Use [parse_to_epoch](parsing.md#convert-numeric-seconds-to-integer-milliseconds)
for other input types, a different output unit, or a wider integer range.
