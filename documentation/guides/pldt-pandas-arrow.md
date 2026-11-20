# Exchange Polars timestamps with pandas and Arrow

Pandas is optional. A pandas Series, DatetimeIndex or DatetimeArray
provides its unit, timezone and validity. Dates are read in row order.
Seconds become milliseconds. A NumPy-backed date source uses a
reserved NaT tick. Arrow can publish validity independently.

## Convert an aware pandas column to UTC

(pldt-read-index-utc-instants)=
```python
import pandas as pd
from rstimes import Pldt

source = pd.Series(pd.DatetimeIndex(["1970-01-01 08:00", None], tz="Asia/Shanghai"))
events = Pldt(source, unit="us", tz="UTC")
print(events.isoformat().to_list())
```

**Output**

```text
['1970-01-01T00:00:00+00:00', None]
```

(pldt-pandas-source-role)=
## Choose how to interpret a source date

A target on the ordinary constructor converts source instants.
`fromdatetime` with an explicit target interprets source clock
fields in that zone. `fromdate` uses the local date at midnight.
Select the factory by the intended operation.

## Round-trip the valid minimum tick

(pldt-arrow-valid-endpoint-roundtrip)=
```python
from rstimes import Pldt

events = Pldt([-(2**63), None], unit="ns", tz="UTC", name="event")
backed = events.to_pandas(use_pyarrow_extension_array=True)
restored = Pldt(backed)
print(restored.to_physical().to_list())
print(restored.is_null().to_list())
```

**Output**

```text
[-9223372036854775808, None]
[False, True]
```

Install pandas and PyArrow for the Arrow-backed pandas route. For an
Arrow Array or ChunkedArray, use Polars `from_arrow` before
construction. `to_pandas()` returns a pandas Series and checks
whether a valid tick would collide with the destination's NaT.
Selecting a NumPy-backed pandas output with
`allow_nat_collision=True` explicitly permits that loss.
Use a destination with independent validity to preserve the tick.
