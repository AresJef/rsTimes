# Format or export a single datetime

## Get the Unix coordinate of an aware value

(pydt-export-wall-versus-utc-microseconds)=
```python
from rstimes import Pydt

value = Pydt(1970, 1, 1, 8, tzinfo="Asia/Shanghai")
print(value.tomicroseconds())
print(value.tomicroseconds(utc=True))
```

**Output**

```text
28800000000
0
```

The default coordinate uses the local clock since the naive 1970 epoch.
`utc=True` uses the UTC coordinate for aware values. A naive input
keeps its naive coordinate. `toseconds` returns seconds as a float.
`timestamp()` returns Unix seconds and interprets naive input
through standard datetime behavior.

## Show three fractional digits

(pydt-format-three-fractional-digits)=
```python
from rstimes import Pydt

value = Pydt(2024, 1, 1, 9, 30, microsecond=123456)
text = value.strftime("%H:%M:%S%.3f")
print(text)
```

**Output**

```text
09:30:00.123
```

`%f` writes six digits without a decimal point. A directive from
`%.1f` through `%.9f` writes the point and that number of digits.
It truncates extra digits or pads on the right with zeros. `%.0f`
omits its fractional component. These directives leave the datetime
unchanged. See [changing the stored fraction](pydt-boundaries.md)
if the value itself needs lower precision.

`isoformat` produces standard datetime ISO output. You can select
its separator and standard `timespec`. `month_name` and `weekday_name` select
localized names. Their locale controls display, while `Configs`
controls parsing vocabulary.

## Show a date as English clock text

(pydt-english-ctime)=
```python
from datetime import timezone
from rstimes import Pydt

value = Pydt(2024, 2, 9, 9, 30, 0, 123456, tzinfo=timezone.utc)
text = value.ctime()
print(text)
```

**Output**

```text
Fri Feb  9 09:30:00 2024
```

Notice the space-padded day. The string omits fractional seconds and the
UTC offset.

## Choose a calendar export

| Method | What it returns |
| --- | --- |
| `date()`, `time()`, `timetz()` | Standard date and time objects. `time()` omits the zone and `timetz()` retains it. |
| `toordinal()`, `isocalendar()` | The calendar day coordinate or the ISO year, week, and weekday. |
| `timetuple()`, `utctimetuple()` | Calendar fields using the local clock or the UTC coordinate, respectively. |
| `timedict()`, `utctimedict()` | The same calendar field roles in a dictionary. |

Use the [Pydt reference](../api/reference/rstimes/pydt/index.rst)
for field names, offset metadata, and clock-relative predicates.
