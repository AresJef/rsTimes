# Run rsTimes with the GIL disabled

Choose a wheel that matches your free-threaded CPython 3.14t or
3.15t interpreter and platform. Ordinary CPython and free-threaded
ABIs use distinct wheels. See [platform support](platforms.md)
for the exact interpreter and dependency matrix.

## Use compatible native dependencies

The core requires NumPy 2.5.3 or newer and `packaging>=22.0`. Windows
also installs tzdata. The pandas extra requires pandas 3.0.6 on Python
3.15 or Windows ARM64 and 2.3.3 elsewhere. The free-threaded qualification
uses pandas 3.0.6. The Polars extra has a 2.0.0 minimum. For free-threaded
Pldt, use an upstream Polars runtime
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

if sysconfig.get_config_var("Py_GIL_DISABLED") != 1 or sys.version_info[:2] not in {(3, 14), (3, 15)}:
    raise SystemExit("Use free-threaded CPython 3.14t or 3.15t.")
before = sys._is_gil_enabled()
if before:
    raise SystemExit("The GIL is enabled at startup. Start without -X gil=1 or PYTHON_GIL=1.")

import polars as pl
import rstimes.pldt

after_import = sys._is_gil_enabled()
source = pl.Series("event", ["2024-01-31 14:30", None]).str.to_datetime(time_unit="us")
frame = source.to_frame()
expr = pl.col("event").pldt.add(months=1)
selected = frame.select(expr)["event"]
events = frame.lazy().select(expr).collect()["event"]
after_query = sys._is_gil_enabled()
if after_import or after_query:
    raise SystemExit("A loaded extension enabled the GIL. Check the installed wheel and dependencies.")
print(events[0].date())
print(before, after_import, after_query)
```

**Output**

```text
2024-02-29
False False False
```

The three booleans show the state at startup, after imports, and after both
queries. Using ordinary CPython or starting with `-X gil=1` stops with
an environment message. If an extension enables the GIL, check the ABI
and the native dependencies for that interpreter.

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
