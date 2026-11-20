# Parse dates into datetimes or epoch ticks

Choose the function by the input you have and the result you need.

| Function | Input | Result |
| --- | --- | --- |
| `parse_str` | One string | Standard Python datetime by default, with microsecond precision. |
| `parse` | Supported strings, dates, datetimes, epoch seconds, or NumPy datetime64 values | Standard Python datetime by default. |
| `parse_to_epoch` | One supported date or time value | Python int in seconds, milliseconds, microseconds, or nanoseconds. |

For one timestamp in a pandas or Polars container, see
[native scalar inputs](parser-interop.md).

## Read a date and time from one string

(parse-one-date-string)=
```python
from rstimes import parse_str

value = parse_str("2024-05-07 12:30")
print(value.isoformat())
```

**Output**

```text
2024-05-07T12:30:00
```

Both `parse_str` and `parse` read the stored text of a real `str` subclass.
Call `str(value)` before parsing when you want the subclass's custom conversion.

`parse` reuses an exact standard datetime input. To choose a constructor for
a new datetime, pass `dtclass` to `parse` or `parse_str`. A supported constructor
can return `None` and its original exceptions propagate.

## Fill missing date fields with a complete default

(parse-fill-calendar-default)=
```python
from datetime import date

from rstimes import parse_str

reference = date(2024, 5, 7)
value = parse_str("12:30", default=reference)
print(value.isoformat())
```

**Output**

```text
2024-05-07T12:30:00
```

A default supplies missing year, month, and day and provides the reference
year for a two-digit year. Give it a complete date of its own. A datetime
default can supply `fold`; the time and zone come from the input. Native
date inputs bypass unused text defaults.

For ambiguous numeric dates, each explicit order flag takes precedence over
its value in `Configs`. The defaults are `yearfirst=True` and
`dayfirst=False` when there is no configuration. See
[choose a date order](configs.md).

## Require valid explicit fields

The default parser can fit recognized fields to their valid ranges.
Use `strict=True` to reject an invalid date, conflicting fields, or a
weekday that contradicts a complete date. Strict mode also rejects
two-digit years. To accept a two-digit year, use a complete `default`
with the ordinary parser.

(parse-reject-impossible-day)=
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

Use February 29 for a valid leap-day input. Invalid scalar text raises a
parsing error. To match one complete format, use `strptime`.

## Read a known fractional-second format

(parse-explicit-format-fraction)=
```python
from rstimes import Pydt

text = "2024-02-29 08:05:00.123456789"
fmt = "%Y-%m-%d %H:%M:%S.%f"
value = Pydt.strptime(text, fmt)
print(value.isoformat())
```

**Output**

```text
2024-02-29T08:05:00.123456
```

`Pydt.strptime` consumes the complete fraction and keeps microseconds.

## Read a compact ISO clock with an offset

(parse-compact-iso-clock)=
```python
from rstimes import Pydt

value = Pydt.fromisoformat(
    "2024-01-02T103000-0430"
)
print(value.isoformat())
```

**Output**

```text
2024-01-02T10:30:00-04:30
```

The compact clock encodes 10:30:00 and the offset is −04:30.
`Pydt.fromisoformat` also accepts ISO week dates such as `2024-W09-4`.
The ordinary parser's `isoformat=True` tries ISO first and can continue
with the general date grammar.

## Retain an offset written in a date string

(parse-keep-explicit-offset)=
```python
from rstimes import parse_str

value = parse_str(
    "1970-01-01 08:00+08:00", ignoretz=False
)
print(value.isoformat())
```

**Output**

```text
1970-01-01T08:00:00+08:00
```

`parse_str` and the text form of `parse` default to `ignoretz=True` and
retain the written clock without its zone. `parse_to_epoch` defaults to
`ignoretz=False` and uses the instant represented by the offset.
Register named regions in [Configs](configs.md). The output constructor
determines whether a regional wall time is valid.

## Convert numeric seconds to integer milliseconds

(parse-numeric-seconds-to-ms)=
```python
from rstimes import parse_to_epoch

milliseconds = parse_to_epoch(1, unit="ms")
print(milliseconds)
```

**Output**

```text
1000
```

`unit` selects the output resolution. Set `input_unit` if your input
numbers already represent ticks in another unit. A NumPy datetime64 uses
its own declared unit. A numeric `Pddt` constructor value, such as
`Pddt([1], unit="ms")`, is already a tick of the selected unit.

## Keep nanoseconds in an epoch value

(parse-exact-nanosecond-tick)=
```python
from rstimes import parse_to_epoch

text = "1970-01-01T00:00:00.123456789Z"
nanoseconds = parse_to_epoch(text, unit="ns")
print(nanoseconds)
```

**Output**

```text
123456789
```

Coarser epoch output selects the earlier tick, including before the epoch.
The integer result can represent dates outside the standard datetime year
range. Standard datetimes use years 1 through 9999 and microseconds.

For an aware datetime and Unix milliseconds, see
[Unix millisecond helpers](unix-milliseconds.md). For strings that contain
numbers, see [numeric text](numeric-text.md).
