# Optional dependency boundaries

NumPy is required. Ordinary Delta, Configs, parsing, and Pydt use does not need
pandas, Polars, dateutil, Arrow, or Babel. Pddt requires pandas; Pldt and `.pldt`
require Polars. Loading either optional date class is an explicit operation.

| Feature | Optional package / extra |
|---|---|
| Pddt | pandas / `rsTimes[pandas]` |
| Pldt and Polars namespaces | polars / `rsTimes[polars]` |
| Delta.from_relativedelta and Configs.from_parserinfo | python-dateutil / `rsTimes[dateutil]` |
| Arrow interchange | pyarrow where required by the chosen interchange operation |

Install optional integrations before starting the process. Restart Python after
adding a previously absent integration: a cached absence is not a hot-install
mechanism. A broken installation or nested import failure keeps its original
exception rather than being silently treated as an absent dependency.

## Verify the core operations

```{doctest} core-without-optional-packages
>>> from datetime import date
>>> from rstimes import Delta, Configs, Pydt, parse_str
>>> (date(2024, 1, 31) + Delta(months=1)).isoformat()
'2024-02-29'
>>> parse_str('2024-01-02', cfg=Configs()).isoformat()
'2024-01-02T00:00:00'
>>> Pydt(2024, 1, 1).to_tomorrow().isoformat()
'2024-01-02T00:00:00'
```

The following checks work in either a core-only or a full environment. The
absent branch verifies the installation error; the present branch executes a
real date operation. Documentation validation runs both environments, so an
unvisited branch is not counted as evidence for that environment.

```{doctest} optional-date-class-contracts
>>> import importlib.util
>>> import rstimes
>>> for name, package, extra in (('Pddt', 'pandas', 'pandas'), ('Pldt', 'polars', 'polars')):
...     if importlib.util.find_spec(package) is None:
...         try:
...             getattr(rstimes, name)
...         except ImportError as error:
...             assert 'rstimes[' + extra + ']' in str(error)
...         else:
...             raise AssertionError('missing integration was accepted')
...     else:
...         date_class = getattr(rstimes, name)
...         dates = date_class([0], unit='ns')
...         assert type(dates) is date_class and len(dates) == 1
...         if name == 'Pddt':
...             assert dates.unit == 'ns' and dates.asi8.tolist() == [0]
...         else:
...             assert dates.dtype.time_unit == 'ns' and dates.to_physical().to_list() == [0]
```

dateutil adapters follow the same dependency boundary. An absent dateutil raises
an `ImportError` naming the public integration and installation extra; ordinary
Rust parsing remains available.

```{doctest} optional-dateutil-contracts
>>> if importlib.util.find_spec('dateutil') is None:
...     for call in (lambda: Delta.from_relativedelta(object()), lambda: Configs.from_parserinfo(object())):
...         try:
...             call()
...         except ImportError as error:
...             assert 'rstimes[dateutil]' in str(error)
...         else:
...             raise AssertionError('missing dateutil was accepted')
... else:
...     from dateutil.relativedelta import relativedelta
...     from dateutil.parser import parserinfo
...     assert Delta.from_relativedelta(relativedelta(months=1)).months == 1
...     assert Configs.from_parserinfo(parserinfo()).month['jan'] == 1
```

Documentation builders have their own development dependencies. For example,
Sphinx uses Babel while building the website; that does not add Babel to the
rsTimes runtime dependency set.
