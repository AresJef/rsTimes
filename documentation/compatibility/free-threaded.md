# Free-threaded Python

rsTimes 0.2.0b3 publishes distinct wheels for CPython 3.14t and 3.15t, using the
same source as ordinary CPython 3.12–3.15. Use the actual interpreter ABI: an
ordinary `cp314` ABI wheel does not become a `cp314t` ABI wheel by renaming it.
The APIs do not require a separate rsTimes mode.

## Dependencies and actual availability

NumPy remains required. Pddt needs a compatible pandas; the free-threaded
qualification uses pandas 3.0.6. Pldt needs a compatible Polars runtime; the
internal qualification uses the fixed, unmodified official Polars 2.1.0 source
at commit `7f902bd3ffd27ff82d14278a09a295ff2f7aed92`.

Polars and its runtime are maintained by Polars. rsTimes does not maintain a
fork, supply a self-built runtime to users, or install/switch one in a user's
environment. The internal builds used to verify the Pldt examples below are
validation dependencies, not an installation channel. Their success does not
mean an official t runtime wheel is published for every platform. Obtain a
compatible runtime from upstream before running the Polars example.

All loaded native dependencies must work with the GIL disabled. Intel macOS
free-threaded qualification requires macOS 14 or later. With NumPy 2.5.3,
macOS ARM64 CPython 3.14/3.15 ordinary and t profiles also require macOS 14 or
later. A lower deployment tag on an rsTimes wheel does not lower a dependency's
OS requirement. See the [distribution and dependency table](platforms.md).

## Verify state before and after real work

Run this page in a fresh 3.14t or 3.15t interpreter with the compatible
dependencies above. It checks the build flag and actual GIL state before and
after imports and work. The example does not use `PYTHON_GIL=0` or `-X gil=0`.

```{doctest} free-threaded-actual-date-work
>>> import os
>>> import sys
>>> import sysconfig
>>> (sysconfig.get_config_var('Py_GIL_DISABLED'), sys._is_gil_enabled())
(1, False)
>>> (os.environ.get('PYTHON_GIL') is None, 'gil' not in sys._xoptions)
(True, True)
>>> import pandas as pd
>>> import polars as pl
>>> from rstimes import Configs, Delta, Pydt, Pddt, Pldt, parse_str
>>> sys._is_gil_enabled()
False
>>> scalar = Pydt(2024, 1, 31) + Delta(months=1)
>>> (type(scalar) is Pydt, scalar.isoformat())
(True, '2024-02-29T00:00:00')
>>> index = Pddt([123, None], unit='ns', name='event') + Delta(nanoseconds=1)
>>> (type(index) is Pddt, index.unit, index.name, index.asi8.tolist())
(True, 'ns', 'event', [124, -9223372036854775808])
>>> pd.isna(index[1])
True
>>> column = Pldt([123, None], unit='ns', name='event') + Delta(nanoseconds=1)
>>> (type(column) is Pldt, column.dtype, column.to_physical().to_list(), column.is_null().to_list())
(True, Datetime(time_unit='ns', time_zone=None), [124, None], [False, True])
>>> expression = pl.col('event').pldt.add(nanoseconds=1)
>>> type(expression) is pl.Expr
True
>>> frame = column.to_frame()
>>> eager = frame.select(expression)
>>> lazy = frame.lazy().select(expression).collect()
>>> (eager.equals(lazy), eager.schema == {'event': pl.Datetime('ns')}, eager['event'].to_physical().to_list())
(True, True, [125, None])
>>> sys._is_gil_enabled()
False
```

## Share completed configuration for reads

Finish application edits before sharing one Configs instance. This actual
two-thread example synchronizes worker start, reads one completed vocabulary,
checks the dates and verifies that neither worker nor the caller enabled the
GIL. It is a correctness example, not a throughput or linear-scaling claim.

```{doctest} free-threaded-shared-config-reads
>>> from concurrent.futures import ThreadPoolExecutor
>>> from threading import Barrier
>>> cfg = Configs()
>>> added = cfg.add_month('harvest', 10)
>>> (type(added) is bool, added)
(True, True)
>>> ready = Barrier(2)
>>> def read_date(text):
...     ready.wait(timeout=5)
...     result = parse_str(text, cfg=cfg)
...     return result.month, result.day, sys._is_gil_enabled()
>>> with ThreadPoolExecutor(max_workers=2) as pool:
...     results = list(pool.map(read_date, ['7 harvest 2024', '8 harvest 2024']))
>>> results
[(10, 7, False), (10, 8, False)]
>>> sys._is_gil_enabled()
False
```

Different Configs instances can be edited independently. Overlapping business
edit/read or edit/edit operations on the same instance can raise RuntimeError;
synchronize those operations in application code. Internal read-cache
preparation is separate from an application edit.

If an extension enables the GIL on import, a successful import alone has not
met the condition checked here. Inspect that dependency's compatibility and
repeat the state checks after actual work. Do not force the GIL off to conceal
an import that enabled it. For copy/state and application callbacks, retain the
ordinary [protocol guarantees and known cases](../concepts/returns-and-protocols.md).
