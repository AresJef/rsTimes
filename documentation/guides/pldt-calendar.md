# Change dates by calendar field or offset

Date results from Pldt and native Series `.pldt` preserve unit, zone,
name and the original null positions.

## Move month-end dates to the next month

(pldt-fit-next-month-end)=
```python
import polars as pl
from rstimes import Pldt

events = Pldt(["2024-01-31T12:00:00.123456789", None], name="event")
base = pl.Series(events)
moved = base.pldt.to_next_month()
print(moved.isoformat().to_list())
```

**Output**

```text
['2024-02-29T12:00:00.123456789', None]
```

`to_year`, `to_quarter`, `to_month`, `to_weekday` and `to_day`
select a calendar period by offset. Their current, previous and next
variants select relative to the corresponding period. A requested
day is fitted to the selected month. A quarter month is a position 1–3.
Weekday selectors number Monday=0 through Sunday=6. Use
`to_monday` through `to_sunday` for weekdays in the current week.

## Replace exact fields by row

(pldt-replace-fields-positionally)=
```python
import polars as pl
from rstimes import Pldt

events = Pldt(["2024-01-05", "2024-01-06", None], tz="UTC", name="event")
days = pl.Series([10, 20, None], dtype=pl.Int64)
adjusted = events.pldt.replace(day=days)
print(adjusted.isoformat().to_list())
```

**Output**

```text
['2024-01-10T00:00:00+00:00', '2024-01-20T00:00:00+00:00', None]
```

Use `.pldt.replace` for strict date-field replacement. A scalar is
broadcast. A supplied column is paired by position and must have the
same length, including null rows. `None` retains an optional field.
A relative increment must be an integer. The Series method `replace`
has its usual value-replacement meaning.

`to_datetime`, `to_date` and `to_time` set legal field intentions.
A zero clock component is a real value. An explicit microsecond replaces
the six-digit fraction and clears an unspecified nanosecond tail.
Changing another field retains the existing fraction.

## Replace fields on a native Series

(pldt-series-replace)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series("event", ["2024-01-31", None]).str.to_datetime(time_unit="us")
adjusted = source.pldt.replace(month=2, day=28)
print(adjusted.isoformat().to_list())
```

**Output**

```text
['2024-02-28T00:00:00', None]
```

## Add one calendar month

(pldt-add-calendar-month)=
```python
from rstimes import Pldt

events = Pldt(["2024-01-31 14:30", None], unit="us")
print(events.add(months=1).isoformat().to_list())
```

**Output**

```text
['2024-02-29T14:30:00', None]
```

The original day is past the end of February. The result keeps 14:30 and
the missing row.

## Add a calendar offset at the existing unit

(pldt-add-cancelling-fine-amounts)=
```python
from rstimes import Pldt

events = Pldt(["2024-01-31 12:00", None], unit="ms")
adjusted = events.add(months=1, microseconds=1, nanoseconds=-1000)
print(adjusted.isoformat().to_list())
```

**Output**

```text
['2024-02-29T12:00:00', None]
```

`add` and `sub` combine calendar components and check the final
precision at the existing unit. Month-end fitting can lose the original
day intent. For elapsed-duration arithmetic, see [use Delta and duration](pldt-arithmetic.md).

## Apply signed increments to an existing Series

(pldt-series-add)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series("event", ["2024-01-31 14:30", None]).str.to_datetime(time_unit="us")
dates = source.pldt.add(months=1)
print(dates.isoformat().to_list())
```

**Output**

```text
['2024-02-29T14:30:00', None]
```

## Move to the next month or set calendar fields

(reader-pldt-month-and-fields)=
```python
from rstimes import Pldt

source = Pldt.parse(['2024-01-31 14:30'], unit='us')
moved = source.to_next_month()
edited = source.to_datetime(month=2, day=31, hour=9)
print(moved.strftime('%Y-%m-%d %H:%M').to_list()[0])
print(edited.strftime('%Y-%m-%d %H:%M').to_list()[0])
```

**Output**

```text
2024-02-29 14:30
2024-02-29 09:30
```


## Move to the next month or set calendar fields on a Series

(reader-series-month-and-fields)=
```python
import polars as pl
import rstimes.pldt

source = pl.Series('event', ['2024-01-31 14:30']).str.to_datetime(time_unit='us')
moved = source.pldt.to_next_month()
edited = source.pldt.to_datetime(month=2, day=31, hour=9)
print(moved.strftime('%Y-%m-%d %H:%M').to_list()[0])
print(edited.strftime('%Y-%m-%d %H:%M').to_list()[0])
```

**Output**

```text
2024-02-29 14:30
2024-02-29 09:30
```
