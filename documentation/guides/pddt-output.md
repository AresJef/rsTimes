# Export or format a pandas date index

## Export UTC microseconds and retain a missing entry

(pddt-export-utc-microseconds-and-nat)=
```python
from rstimes import Pddt

events = Pddt(
    ["1970-01-01 08:00:00.000000123", None],
    unit="ns", tz="Asia/Shanghai",
)
ticks = events.tomicroseconds(utc=True)
print(ticks.tolist())
```

**Output**

```text
[0, <NA>]
```

The valid instant is 123 ns after the epoch. Exporting microseconds
selects the earlier tick. The result is a pandas Index with nullable
integer dtype. Omitting `utc=True` uses the local clock coordinate.
`toseconds` returns float seconds and uses NaN for missing results.
`timestamp()` returns Unix seconds, interpreting a naive date in the
process-local zone. Localize a repeated or nonexistent local clock
explicitly before requesting its Unix instant.

`asi8` exposes stored ticks in the index's unit; a missing date uses
the reserved signed int64 minimum. `values_naive` yields a NumPy clock
view in the index's unit, dropping the timezone after expressing the
local clock. With aware dates, the inherited `values` uses UTC
coordinates. A local value that cannot fit the unit raises an error.

## Display all nine fractional digits

(pddt-format-native-nanosecond-text)=
```python
from rstimes import Pddt

events = Pddt(
    ["2024-02-29T12:34:56.123456789"],
    unit="ns", name="event",
)
text = events.strftime("%H:%M:%S.%f")
print(text.tolist())
```

**Output**

```text
['12:34:56.123456789']
```

`strftime` returns a pandas Index of strings with the original name.
`%f` writes nine digits for ns storage and six for s, ms, or us storage.
Use `%.1f` through `%.9f` to include a decimal point and the selected
number of digits. The result is truncated or padded with zeros.
`%.0f` emits an empty string. `isoformat` selects a display precision
with `timespec`; the stored values and their precision stay the same.
`month_name` and `weekday_name` use a display locale.

## Extract local calendar fields into a table

(pddt-export-local-hours-table)=
```python
from rstimes import Pddt

events = Pddt(
    ["2024-02-29 12:30", None], unit="us"
)
calendar = events.timedf()
print(calendar["tm_hour"].tolist())
```

**Output**

```text
[12, <NA>]
```

`timedf` returns nine nullable integer columns on a positional index.
Use `utctimedf` for UTC fields. A missing date gives an entirely
missing row. The DST field is −1 when an adjustment is unspecified,
0 for zero, and 1 for a nonzero adjustment; the UTC table uses 0 for
valid dates.

Use `datetime()` to get an object array of Pydt values and pandas NaT.
This output projects to microseconds and requires years 1 through 9999.
The `date`, `time`, and `timetz` properties produce standard Python date
or time fields. The zoned time form retains its zone and fold.
