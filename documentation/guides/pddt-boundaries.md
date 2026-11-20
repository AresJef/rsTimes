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
