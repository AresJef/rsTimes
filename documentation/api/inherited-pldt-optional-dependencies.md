# Missing native optional libraries

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

```{doctest} inherited-pldt-native-missing-dependencies
>>> import importlib.util
>>> import polars as pl
>>> from rstimes import Pldt
>>> assert all(importlib.util.find_spec(name) is None for name in ('jax', 'torch', 'altair'))
>>> value = Pldt(pl.Series('event', [1704067200000000123, None], dtype=pl.Datetime('ns', 'UTC')))
>>> for package, action in [('jax', value.to_jax), ('torch', value.to_torch)]:
...     try:
...         action()
...     except ModuleNotFoundError as error:
...         assert package in str(error)
...     else:
...         raise AssertionError('the missing optional package must be reported')
>>> try:
...     value.plot
... except pl.exceptions.ModuleUpgradeRequiredError as error:
...     assert 'altair' in str(error).lower()
... else:
...     raise AssertionError('the missing plotting dependency must be reported')
>>> (value.dtype, value.to_physical().to_list())
(Datetime(time_unit='ns', time_zone='UTC'), [1704067200000000123, None])
```

Choose compatible upstream packages for the platform and Python interpreter in
which the application runs. Installing an optional plotting or tensor library
does not add native Datetime tensor support; the installed-library page still
requires explicit dtype, unit, timezone and null handling.
