# Query, round, or count boundaries in a date index

## Find rows in a calendar month

(pddt-query-month-with-missing-date)=
```python
from rstimes import Pddt

events = Pddt(["2024-02-29", None], unit="us")
print(events.is_month("February").tolist())
```

**Output**

```text
[True, False]
```

A missing source date is false for this boolean query. A missing query
target raises `TypeError`. An unknown month name raises `ValueError`.
Integer calendar queries can return nullable integers when dates are
missing. Inherited pandas fields retain their pandas result contracts.

## Read the year a week belongs to

(pddt-iso-week-year)=
```python
from rstimes import Pddt

dates = Pddt(["0000-01-01", None], unit="us", name="event")
print(dates.isocalendar()["year"].tolist())
```

**Output**

```text
[-1, <NA>]
```

January 1 of year 0 falls in week 52 of ISO year −1, on Saturday.
The table keeps your date index and its name. The `year` column uses
nullable `Int64`. The `week` and `day` columns use nullable `UInt32`.
A missing date leaves all three cells missing. Use `isoyear()` when
you only need the year.

## Round to a fixed frequency

`floor(freq)` chooses the earlier boundary or the same value.
`ceil(freq)` chooses the later boundary or the same value.
`round(freq)` selects the nearest tick with ties to even. Use `snap(unit)`
for the closest valid beginning of the named period. Snap chooses the
later of two equally close starts.

`to_first_of` and `to_last_of` select dates within the requested period
and retain the clock. `to_start_of` and `to_end_of` select its first
or last valid tick. `fsp(precision)` truncates the fractional decimal
places. All these date results keep the receiver's supported unit.

## Count crossed day boundaries and retain missing rows

(pddt-count-midnights-with-missing-date)=
```python
from rstimes import Pddt

events = Pddt(["2024-02-01", None], unit="us")
counts = events.diff("2024-01-31 23:59:59", "D")
print(counts.tolist())
```

**Output**

```text
[1, <NA>]
```

The first interval crosses one midnight and lasts one second. The
second has no date. The result is a pandas Index of nullable integers
when there are missing rows. A whole result with no missing rows uses
an ordinary integer dtype.

`diff` compares calendar or fixed-unit buckets. Aware values use UTC
coordinates. Numeric targets are epoch seconds. For per-row targets,
supply a column with the same length. `inclusive` can adjust the boundary
count, and `absolute=True` changes its sign handling. See
[calendar boundaries and inclusive counting](pydt-boundaries.md).

## Compare a month’s calendar days and exact boundaries

(reader-pddt-month-boundaries)=
```python
from rstimes import Pddt

source = Pddt(['2024-03-15 14:30'], unit='us')
first = source.to_first_of('M')
start = source.to_start_of('M')
last = source.to_last_of('M')
end = source.to_end_of('M')
print(first.strftime('%Y-%m-%d %H:%M:%S.%f').tolist()[0])
print(start.strftime('%Y-%m-%d %H:%M:%S.%f').tolist()[0])
print(last.strftime('%Y-%m-%d %H:%M:%S.%f').tolist()[0])
print(end.strftime('%Y-%m-%d %H:%M:%S.%f').tolist()[0])
print(first.is_first_of('M')[0], first.is_start_of('M')[0])
```

**Output**

```text
2024-03-01 14:30:00.000000
2024-03-01 00:00:00.000000
2024-03-31 14:30:00.000000
2024-03-31 23:59:59.999999
True False
```

First and last choose calendar days. Start and end choose the first and last valid instants.


## Round to seconds or keep three decimal places

(reader-pddt-second-grid)=
```python
from rstimes import Pddt

source = Pddt(['2024-02-29 12:00:01.567891'], unit='us')
rounded = source.round('s')
ceiling = source.ceil('s')
below = source.floor('s')
shortened = source.fsp(3)
print(rounded.strftime('%H:%M:%S.%f').tolist()[0])
print(ceiling.strftime('%H:%M:%S.%f').tolist()[0])
print(below.strftime('%H:%M:%S.%f').tolist()[0])
print(shortened.strftime('%H:%M:%S.%f').tolist()[0])
```

**Output**

```text
12:00:02.000000
12:00:02.000000
12:00:01.000000
12:00:01.567000
```

These calls preserve the storage unit. Rounding changes the clock value and fsp discards trailing fractional digits.


## Snap to the later midnight at an exact tie

(reader-pddt-snap-tie)=
```python
from rstimes import Pddt

dates = Pddt(['1970-01-01 12:00'], unit='us')
print(dates.snap('D').isoformat().tolist())
```

**Output**

```text
['1970-01-02T00:00:00']
```
