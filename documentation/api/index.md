# API reference

Find the signature, arguments, return type and errors for a public entry
by its name. The rsTimes classes and functions use the declarations from
the installed 1.1.1 wheel. The Series and Expr references describe their
registered namespaces. Follow an example link to see a runnable use.

| Task | Reference |
| --- | --- |
| Parse a date or numeric token, or configure parsing | [Parser and Configs](reference/rstimes/parser/index.rst) |
| Change an elapsed or calendar amount | [Delta](reference/rstimes/delta/index.rst) |
| Work with a Python datetime | [Pydt](reference/rstimes/pydt/index.rst) |
| Work with a pandas datetime index | [Pddt](reference/rstimes/pddt/index.rst) |
| Work with a native Polars date column | [Pldt](reference/rstimes/pldt/index.rst) and [Series.pldt](polars-series.rst) |
| Build a native date expression | [Expr.pldt](polars-expressions.rst) |
| Diagnose a failed call | [Errors](errors.md) and [troubleshooting](../troubleshooting.md) |

The inherited references describe supported arguments, return families, and
date-dtype limits on actual rsTimes objects. They link to native parameter
references for additional options.

```{toctree}
:maxdepth: 1
:caption: Classes, functions and protocols

reference/rstimes/index
inherited-delta
inherited-configs
inherited-pydt
errors
```

```{toctree}
:maxdepth: 1
:caption: Registered date namespaces

namespaces
polars-series
polars-expressions
```

```{toctree}
:maxdepth: 1
:caption: pandas inherited entries

inherited-pddt-reference
inherited-pddt-fields
inherited-pddt-indexing
inherited-pddt-containers
inherited-pddt-output
inherited-pddt-protocols
array-dispatch-protocols
inherited-pddt-compatibility
```

```{toctree}
:maxdepth: 1
:caption: Polars inherited entries

inherited-pldt-reference
inherited-pldt-container
inherited-pldt-transformations
inherited-pldt-analysis
inherited-pldt-windows
inherited-pldt-comparisons
inherited-pldt-representations
inherited-pldt-numeric
inherited-pldt-accessors
inherited-polars-datetime-reference
inherited-polars-datetime
inherited-pldt-arrow
inherited-pldt-sql
inherited-pldt-optional
inherited-pldt-optional-dependencies
```
