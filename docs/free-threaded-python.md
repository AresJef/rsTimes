# Free-threaded Python

This development checkout adds one-source support for ordinary CPython
3.12–3.15 and free-threaded CPython 3.14t / 3.15t. `Delta`, Parser / `Configs`,
`Pydt`, `Pddt`, and `Pldt` keep the same date semantics and public interfaces.
The current project is qualifying the installed distributions; its final
acceptance record determines which build is adopted. The publicly released
`0.2.0b2` is an older, ordinary-GIL distribution. A matching version string
does not identify the new development binary.

## Interpreter and dependencies

Use an rsTimes wheel for the actual interpreter ABI and platform. A `cp314t`
or `cp315t` ABI is distinct from the corresponding ordinary ABI. Installing an
ordinary wheel or changing its filename does not provide free-threaded support.
Only 64-bit interpreters are in this project's supported matrix.

NumPy remains required, with a minimum of 2.5.3. Windows also requires the
declared tzdata dependency. The container libraries remain optional:

- `Delta`, Parser / `Configs`, and `Pydt` do not require pandas or Polars.
- `Pddt` requires pandas. Its free-threaded qualification uses pandas 3.0.6;
  pandas 2 compatibility remains an ordinary-GIL profile.
- `Pldt` requires a compatible upstream Polars runtime for that free-threaded
  interpreter. The qualification version is Polars 2.1.0, official source
  commit `7f902bd3ffd27ff82d14278a09a295ff2f7aed92`. The ordinary Polars 2.0.0
  minimum remains unchanged.
- dateutil integration remains optional. Install python-dateutil to import
  parserinfo or relativedelta values through their documented adapters.

All native dependencies loaded by the application must support execution with
the GIL disabled. The Intel macOS free-threaded profile requires macOS 14.0 or
later. With NumPy 2.5.3, the macOS ARM64 CPython 3.14 and 3.15 profiles also
require macOS 14.0 or later, for ordinary and free-threaded interpreters alike.
These requirements come from the complete dependency set; an rsTimes wheel
with an older deployment tag does not lower the dependency requirements.
Wheel tags do not prove execution on every older operating-system release.

## Polars ownership and availability

Polars and its runtime are maintained by the Polars project. rsTimes maintains
its own Series / Expr namespaces, SDK bridge, and native expression plugins.
It does not patch a Polars fork or provide an rsTimes-specific Polars runtime.

Internal development and CI may compile the fixed, unmodified official source
when a suitable upstream free-threaded wheel is unavailable. Those internal
test builds are not a user installation channel or a promise that an official
wheel is already published for every interpreter and platform. Obtain a
compatible Polars build from upstream; rsTimes does not download, install, or
switch runtimes in the user's environment.

With compatible upstream dependencies and the matching rsTimes t wheel,
the normal APIs work without a separate user-facing rsTimes mode. Support for
an arbitrary future Polars version is not implied by this qualification.

## Check actual execution

In a fresh free-threaded interpreter, check the state before and after imports
and representative work:

```python
import sys
import sysconfig

assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
assert sys._is_gil_enabled() is False

from rstimes import Delta, Pydt

assert Pydt(2024, 1, 31) + Delta(months=1) == Pydt(2024, 2, 29)
assert sys._is_gil_enabled() is False
```

If using pandas or Polars, repeat the final state check after importing them
and executing `Pddt` or `Pldt` work. Importing an incompatible extension can
enable the GIL. A successful import by itself is insufficient evidence.
Qualification does not force `PYTHON_GIL=0` or `-X gil=0` to hide this behavior.

## Share configuration for reading

Finish edits before submitting work to threads. Shared readonly parsing,
including first cache preparation, is supported:

```python
from concurrent.futures import ThreadPoolExecutor
from rstimes import Configs, parse_str

cfg = Configs()
cfg.add_month("harvest", 10)
texts = ["7 harvest 2024", "8 harvest 2024"]

with ThreadPoolExecutor(max_workers=2) as pool:
    values = list(pool.map(lambda text: parse_str(text, cfg=cfg), texts))

assert [(value.month, value.day) for value in values] == [(10, 7), (10, 8)]
```

Different `Configs` instances can be edited concurrently. Overlapping business
edits or edit/read operations on the same instance can raise a clear
`RuntimeError`; synchronize such operations in application code. Same-thread
callbacks retain their documented reentry behavior. Internal readonly cache
publication is not a business edit and must not reject ordinary shared reads.

## Data, callbacks, and performance

Keep shared input data stable during a call. Owners and snapshots protect the
library's references; they do not make arbitrary external array writes,
resizes, shared iterator consumption, or application state transactional.
Application-defined constructors, descriptors, timezone callbacks, and state
protocols remain the application's synchronization responsibility.

The library does not add a user thread pool. Polars retains its own execution
pool; application threads and Polars threads can therefore overlap. Report
their settings when comparing throughput.

Free-threaded support is not a claim that every call is faster or that four
threads produce four times the throughput. Ordinary-build regression guards,
t single-thread cost, and t multithread throughput are separate measurements.
The final project report retains their actual quality, results, and limits.
