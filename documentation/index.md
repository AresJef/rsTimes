# rsTimes documentation

Calendar operations for Python scalars, pandas indexes and Polars columns.
Choose the representation that fits your data, then follow a guide or use the
reference for an individual call.

These docs follow **rsTimes 0.2.0b3**, a beta release. Examples run against the
published package with declared dependency profiles.

| Your task | Start here |
|---|---|
| Install the package and run a first example | [Getting started](getting-started/index.md) |
| Move a date by calendar months or exact ns | [Delta calendar changes](guides/delta.md) |
| Parse text with configurable date vocabularies | [Parsing](guides/parsing.md) |
| Work with one scalar date and timezone | [Pydt](guides/pydt.md) |
| Keep units and missing dates in a pandas index | [Pddt](guides/pddt.md) |
| Transform native Polars dates eagerly | [Pldt](guides/pldt.md) |
| Execute date work in a lazy query | [Polars expressions](guides/expressions.md) |

```{toctree}
:maxdepth: 2

getting-started/index
concepts/index
guides/index
recipes/index
api/index
compatibility/index
troubleshooting
development/index
```

The [compatibility guide](compatibility/index.md) records actual dependency,
platform and free-threaded conditions. The [known issues](compatibility/known-issues.md)
page keeps deferred rsTimes protocol defects distinct from supported behavior.
