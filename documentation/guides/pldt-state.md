# Copy or store a Pldt date column

## Shallow-copy a column with application state

(pldt-copy-business-column)=
```python
from rstimes import Pldt

class EventDates(Pldt):
    pass

events = EventDates([5, None], unit="ns", name="event")
events.labels = ["audit"]
copied = events.copy()
print(type(copied).__name__, copied.to_physical().to_list())
print(copied.labels is events.labels)
```

**Output**

```text
EventDates [5, None]
True
```

A default shallow copy holds an independent column object. It can
share date buffers safely and preserves references to application
state. Use `copy(deep=True)` or `copy.deepcopy` for a deep copy.
Deep copy preserves cycles and aliases using one memo. A real
custom copy or state method supplies its own result and errors.

## Store a date column with its validity

(pldt-pickle-min-tick)=
```python
import pickle
from rstimes import Pldt

events = Pldt([-(2**63), None], unit="ns", tz="UTC", name="event")
restored = pickle.loads(pickle.dumps(events))
print(restored.name, restored.to_physical().to_list())
```

**Output**

```text
event [-9223372036854775808, None]
```

Pickle preserves the unit, zone, name and the independent validity
bitmap. Load data from trusted sources. Normal Series methods and
`pl.Series(events)` supply the ordinary Polars container behavior.

An eager date transformation that produces a new subclass result
calls its normal constructor on the whole column. Use constructor
parameters compatible with that call. An ordinary Series namespace
returns Pldt date results. Expr operations produce native Expr,
with the [execution and serialization boundaries](expressions-execution.md)
of the query.
