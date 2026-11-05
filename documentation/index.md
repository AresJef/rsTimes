# rsTimes documentation

Work with calendar changes, scalar datetimes, pandas indexes, and Polars columns
using one set of date rules. Choose the container that fits your data, then use
the guides for complete workflows and the reference for individual calls.

This development preview follows the latest implementation being prepared for
release. A published version will identify the exact package used for its examples.

| Your task | Start here |
|---|---|
| Move a date by calendar months or exact nanoseconds | [Calendar changes](guides/delta.md) |
| Parse text or convert a value to integer epoch ticks | [Parsing](guides/parsing.md) |
| Keep units and missing values in a pandas index | [pandas dates](guides/pddt.md) |
| Transform a Polars column in a lazy query | [Polars expressions](guides/expressions.md) |

```{toctree}
:maxdepth: 2
:caption: User guide

guides/delta
guides/delta-interop
guides/delta-protocols
guides/parsing
guides/configs
guides/configs-state
guides/parserinfo
guides/parser-interop
guides/unix-milliseconds
guides/pydt
guides/pydt-calendar
guides/pydt-timezones
guides/pydt-boundaries
guides/pydt-output
guides/pydt-protocols
guides/pydt-interop
guides/pddt
guides/pddt-factories
guides/pddt-timezones
guides/pddt-ranges
guides/pddt-calendar
guides/pddt-boundaries
guides/pddt-output
guides/pddt-protocols
guides/pddt-interop
guides/pldt
guides/pldt-factories
guides/pldt-timezones
guides/pldt-ranges
guides/pldt-interop
guides/pldt-pandas-arrow
guides/pldt-output
guides/pldt-calendar
guides/pldt-boundaries
guides/pldt-queries
guides/pldt-differences
guides/pldt-arithmetic
guides/pldt-state
guides/expressions
guides/expressions-inputs
guides/expressions-calendar
guides/expressions-boundaries
guides/expressions-queries
guides/expressions-timezones
guides/expressions-output
guides/expressions-execution
compatibility/optional-dependencies
compatibility/known-issues
```

```{toctree}
:maxdepth: 1
:caption: API reference

api/reference/rstimes/index
api/inherited-delta
api/inherited-configs
api/inherited-pydt
api/namespaces
api/polars-series
api/polars-expressions
api/inherited-pddt-fields
api/inherited-pddt-indexing
api/inherited-pddt-containers
api/inherited-pddt-output
api/inherited-pddt-protocols
api/inherited-pddt-compatibility
api/inherited-pddt-reference
api/inherited-pldt-container
api/inherited-pldt-numeric
api/inherited-pldt-comparisons
api/inherited-pldt-representations
api/inherited-pldt-transformations
api/inherited-pldt-accessors
api/inherited-pldt-optional
api/inherited-pldt-optional-dependencies
api/inherited-pldt-reference
api/inherited-polars-datetime
api/inherited-polars-datetime-reference
api/errors
```
