# Use a pandas date index with other containers

## Select a DataFrame row by its date

(pddt-use-index-in-dataframe)=
```python
import pandas as pd
from rstimes import Pddt

events = Pddt(
    ["2024-02-28", "2024-02-29"],
    unit="us", name="day",
)
sales = pd.DataFrame({"count": [3, 8]}, index=events)
print(sales.loc["2024-02-29", "count"])
```

**Output**

```text
8
```

The DataFrame uses its date index for label-based selection. Use
pandas indexing and selection methods as usual. For a date
transformation, call the Pddt methods on the date index.

## Exchange one timestamp with Arrow

(pddt-export-arrow-native-ticks)=
```python
import pyarrow as pa
from rstimes import Pddt

events = Pddt([123, None], unit="ns", tz="UTC")
column = pa.array(events)
print(column.cast(pa.int64()).to_pylist())
```

**Output**

```text
[123, None]
```

Install PyArrow for this exchange. The Arrow timestamp retains ns
precision, the zone, and the validity of each row. To import a raw
Arrow timestamp array, wrap it in a pandas Series with its Arrow
timestamp dtype and pass that Series to `Pddt`.

## Choose the right source dtype

Native pandas and one-dimensional NumPy dates retain their supported
unit and relevant timezone metadata. Pass `copy=True` when the
result must be independent of a mutable source array.
A one-dimensional noncontiguous slice retains its row order.

Supported Polars Date and Datetime Series can supply dates. A Time
Series supplies clock values for `combine(time=...)`. A Duration
Series can supply a time operand to arithmetic. `Pddt` can represent
pandas NaT and rejects an unrepresentable Polars tick that would
collide with the pandas sentinel. See
[storage units and missing values](../concepts/units-and-missing.md).

For a calendar change from dateutil, convert a supported rule to a
[Delta](delta-interop.md) and apply it. Use pandas offset behavior
where the date-range or inherited method explicitly delegates it.
