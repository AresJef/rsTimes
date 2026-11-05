# Install rsTimes and run your first calendar change

These docs target **rsTimes 0.2.0b3**, a beta release. Use a virtual environment
for the intended Python interpreter and install that exact version:

```shell
python -m pip install "rsTimes==0.2.0b3"
```

NumPy is required. On Windows, the package also declares tzdata. pandas,
Polars and dateutil remain optional. Install only the integrations your work
uses; the combined command below enables all three:

```shell
python -m pip install "rsTimes[dateutil,pandas,polars]==0.2.0b3"
```

The individual extra names are `dateutil`, `pandas` and `polars`. PyArrow is
required for the Arrow examples but is a separate optional package. Restart
an already running interpreter after adding an integration. The
[compatibility guide](../compatibility/index.md) gives the actual Python/ABI,
platform, dependency and free-threaded conditions.

## Verify the version and change a date

Delta describes the change; Pydt holds one scalar date. Adding one month
clamps January 31 to the last day of February without changing the original.
This example needs only the default installation.

```{doctest} getting-started-calendar-change
>>> from importlib.metadata import version
>>> from rstimes import Delta, Pydt
>>> version('rsTimes')
'0.2.0b3'
>>> start = Pydt(2024, 1, 31, 12)
>>> changed = start + Delta(months=1)
>>> (type(changed) is Pydt, changed.isoformat(), changed.tzinfo is None)
(True, '2024-02-29T12:00:00', True)
>>> start.isoformat()
'2024-01-31T12:00:00'
```

## Choose the container, then follow its guide

| Your data | Start with | Next task |
|---|---|---|
| A calendar adjustment | [Delta](../guides/delta.md) | Relative amounts, absolute fields and ns projection |
| One scalar date | [Pydt](../guides/pydt.md) | Construction, parsing, timezone work and Python interoperability |
| A pandas date index | [Pddt](../guides/pddt.md) | Units, NaT, vector operations and `.pddt` field replacement |
| A Polars date column | [Pldt](../guides/pldt.md) | Native date storage, nulls and eager operations |
| A Polars query | [Expr `.pldt`](../guides/expressions.md) | Build expressions, then execute select/collect |
| Text and custom vocabularies | [Parsing and Configs](../guides/parsing.md) | Input grammar, defaults, flags and optional adapters |

Read the [concepts](../concepts/index.md) before moving between containers.
Use the [recipes](../recipes/index.md) for complete tasks and the
[API reference](../api/index.md) for a particular entry. Source development
and documentation maintenance have separate [developer instructions](../development/index.md).
