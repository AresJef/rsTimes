# Missing native optional libraries

## Catch an unavailable tensor dependency

(ref-pldt-missing-torch)=
```python
from rstimes import Pldt

events = Pldt([1, None], unit="ns")
try:
    events.to_torch()
except ModuleNotFoundError as error:
    print(type(error).__name__)
```

**Output**

```text
ModuleNotFoundError
```

Native Polars optional exits have their own dependency errors. They are
separate from the rsTimes pandas/Polars/dateutil extras. The tested profiles on
this page contain Polars but no JAX, Torch or Altair. A missing JAX or Torch
raises ModuleNotFoundError when its tensor exit is called. Reading `.plot`
without a compatible Altair raises Polars ModuleUpgradeRequiredError, including
when Altair is absent.

These are expected dependency failures, not successful tensor or chart exports.
The [installed-library examples](inherited-pldt-optional.md) separately execute
the real exits, actual rejection branches, physical integer tensors, validity
masks and native chart objects.

Choose compatible upstream packages for the platform and Python interpreter in
which the application runs. Installing an optional plotting or tensor library
does not add native Datetime tensor support; the installed-library page still
requires explicit dtype, unit, timezone and null handling.
