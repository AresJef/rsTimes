# Apply date operands or copy a pandas date index

## Apply a different Delta to each row

(pddt-apply-row-calendar-deltas)=
```python
from rstimes import Delta, Pddt

events = Pddt(
    ["2024-01-31", "2024-02-29"],
    unit="us", name="event",
)
moved = events + [Delta(days=1), Delta(months=1)]
print(moved.strftime("%Y-%m-%d").tolist())
```

**Output**

```text
['2024-02-01', '2024-03-29']
```

A scalar Delta applies to every row. A Delta collection pairs by position
and must match the date count. `Delta()` is a zero change. A missing
operand raises `TypeError`. A missing source date stays missing.

Use `timedelta` for elapsed time and `Delta(days=1)` for a local calendar
day. Subtracting a compatible date gives a pandas TimedeltaIndex.
A real external operator can supply its own result or error. In a
per-row dynamic callback, a Pddt value is supplied as a Timestamp.

## Copy the index and its application attributes

(pddt-copy-index-keeps-business-state)=
```python
from rstimes import Pddt

class Schedule(Pddt):
    pass

events = Schedule(
    ["2024-02-29"], unit="us", name="day"
)
events.labels = ["renewal"]
trial = events.copy(deep=True)
trial.labels.append("review")
print(events.labels)
print(trial.labels)
```

**Output**

```text
['renewal']
['renewal', 'review']
```

The default shallow copy creates a new shell with shared application
references. Deep copy isolates date storage and copies application
state with one memo, preserving aliases and cycles. Ordinary
`copy.copy` and `copy.deepcopy` follow their supported protocols.
The `deep` option accepts real booleans.

A changed date result from an rsTimes operation can call the subclass's
normal constructor. Copying and loading the default state restore
existing fields and application metadata without rerunning the
business initializer. Real custom copy or reduction hooks retain their
own result and exception behavior. Use ordinary pickle for trusted
records. The current date-core format is versioned; migrate older
incompatible values through their original environment.
