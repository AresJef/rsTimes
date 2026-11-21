# Run rsTimes with the GIL disabled

Choose a wheel that matches your free-threaded CPython 3.14t or
3.15t interpreter and platform. Ordinary CPython and free-threaded
ABIs use distinct wheels. See [platform support](platforms.md)
for the exact interpreter and dependency matrix.

## Use compatible native dependencies

NumPy is required. The pandas qualification for free-threaded
Pddt uses pandas 3.0.6. For Pldt, use an upstream Polars runtime
compatible with your platform and interpreter. The documented
qualification uses Polars 2.1.0 from the fixed official source
revision `7f902bd3ffd27ff82d14278a09a295ff2f7aed92`.
Obtain compatible builds from upstream.
Free-threaded Intel macOS and the NumPy-dependent ARM64 Python
3.14 and 3.15 profiles require macOS 14 or newer.

## Verify state after a real date calculation

(free-threaded-check-after-query)=
```python
import sys
import sysconfig

if sysconfig.get_config_var("Py_GIL_DISABLED") != 1:
    raise SystemExit("Run this example with a free-threaded CPython 3.14t or 3.15t interpreter.")
before = sys._is_gil_enabled()

import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([123, None], dtype=pl.Datetime("ns")),
})
expr = pl.col("event").pldt.add(nanoseconds=1)
selected = frame.select(expr)["event"]
events = frame.lazy().select(expr).collect()["event"]
assert selected.equals(events)
print(events.to_physical().to_list())
print(before, sys._is_gil_enabled())
```

**Output**

```text
[124, None]
False False
```

The output above is from a fresh free-threaded interpreter with the
GIL disabled throughout. To run the same calculation with the GIL
enabled, start that interpreter with `-X gil=1`. The same date ticks
then precede `True True`. An imported extension can enable the GIL.
Check before imports and after the calculations your application uses.

## Share a completed month vocabulary

(free-threaded-read-shared-month)=
```python
from concurrent.futures import ThreadPoolExecutor

from rstimes import Configs, parse_str

config = Configs()
config.add_month("harvest", 10)

def read_month(text):
    return parse_str(text, cfg=config).month

with ThreadPoolExecutor(max_workers=2) as pool:
    print(list(pool.map(read_month, ["7 harvest 2024", "8 harvest 2024"])))
```

**Output**

```text
[10, 10]
```

Finish application edits before sharing a configuration for reads.
Different instances can be edited independently. Synchronize
overlapping read and edit operations on one instance, which can
raise `RuntimeError`. Shared native input buffers and application
callbacks retain their normal ownership and synchronization roles.
