# Move or replace fields in a pandas date index

Use Pddt's calendar selectors for date moves. Use `.pddt.replace` when
your new fields must form exact valid dates.

## Select a different month for each row

(pddt-pair-calendar-fields-positionally)=
```python
import pandas as pd
from rstimes import Pddt

events = Pddt(
    ["2024-01-31", "2024-03-31"],
    unit="us", name="event",
)
months = pd.Series([2, 4], index=["second", "first"])
moved = events.to_date(month=months)
for text in moved.strftime("%Y-%m-%d"):
    print(text)
```

**Output**

```text
2024-02-29
2024-04-30
```

The first month value applies to the first date. pandas labels play
no part in this operation. A scalar supplies the same field for all
rows. A collection must have exactly the receiver's length.

`to_date` fits a valid day selection to the target month's end.
`to_datetime` selects date and clock fields, and `to_time` selects
clock fields. A field set to `None` keeps its previous value. Use an
object collection for a field column that preserves selected values
with actual `None` entries. An integer missing marker such as `pd.NA`
is a different input.

## Replace the fractional fields exactly

(pddt-set-microsecond-and-tail)=
```python
from rstimes import Pddt

events = Pddt(
    ["2024-01-02T12:30:00.123456789"],
    unit="ns",
)
changed = events.pddt.replace(
    microsecond=1, nanosecond=2
)
print(changed.isoformat(timespec="ns")[0])
```

**Output**

```text
2024-01-02T12:30:00.000001002
```

A microsecond setting replaces the fractional field and clears the old
nanosecond tail. The explicit nanosecond setting then fills that tail.
A nanosecond setting by itself retains the existing microseconds.
The pandas whole-value replacement API keeps its own meaning.

## Choose the calendar step

`to_year`, `to_quarter`, `to_month`, `to_weekday`, and `to_day` move
by their named calendar period. Use the `to_curr_*`, `to_prev_*`, and
`to_next_*` forms for a step of zero, minus one, or one. Month and weekday
selectors accept names where listed in the reference. A quarter's month
selector is its position from 1 to 3.

Named `add` and `sub` take integer amounts. They combine year, quarter,
and month deltas before choosing the target date, then apply the
remaining relative quantities. Date results keep their current unit
and metadata. A result too fine for that unit raises `ValueError`;
choose a finer unit before the calculation. See the
[Pddt reference](../api/reference/rstimes/pddt/index.rst) for each role.
