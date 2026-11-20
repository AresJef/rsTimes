# Apply, copy, and store Delta values

Delta values normalize the relative year and month group and the relative
day and clock group. The clock remainder is non-negative. For example,
minus one nanosecond appears as minus one day and a clock remainder of
23:59:59.999999999. The fields of an existing Delta are immutable.

## Compare equivalent durations

(delta-compare-equal-fixed-values)=
```python
from rstimes import Delta

whole = Delta(microseconds=1)
same = Delta(nanoseconds=1000)
print(whole == same)
```

**Output**

```text
True
```

Equal Delta values have equal hashes. An absolute zero setting is present
and can make a Delta truthy. Use equality for value comparison. Sorting by
the Delta values themselves is unsupported.

## Apply one change to several dates

(delta-reuse-rule-across-dates)=
```python
from datetime import date

from rstimes import Delta

starts = [date(2024, 1, 31), date(2024, 5, 31)]
ends = Delta(months=1).apply_many(starts)
for end in ends:
    print(end)
```

**Output**

```text
2024-02-29
2024-06-30
```

`apply_many` returns a list in input order. It uses the same semantics
as applying `value + delta` to each item. Supported iterable inputs
include lists, tuples, and generators. If an item fails, the call raises
its error. An iterator remains consumed through the items already read.

## Copy an application rule and its labels

(delta-copy-business-data)=
```python
from copy import deepcopy

from rstimes import Delta

class Rule(Delta):
    pass

original = Rule(days=1)
original.labels = ["daily"]
trial = deepcopy(original)
trial.labels.append("trial")
print(original.labels)
print(trial.labels)
```

**Output**

```text
['daily']
['daily', 'trial']
```

Default shallow copy shares references to application values. Default deep
copy preserves aliases and cycles using the same memo. The copied Delta
keeps its precise value. A real custom copy or reduction hook can choose its
own result, and its original exception propagates.

Use ordinary `pickle` to save a Delta and load only trusted data. The
default state uses version 2 and records all 17 value fields along with
application metadata. It preserves a nanosecond tail and uses a distinct
marker for an unset absolute field. Save new values when migrating from
the old microsecond-only state. See [the Delta reference](../api/reference/rstimes/delta/index.rst)
for the value and state protocols.
