# rsTimes documentation

Use rsTimes 1.0.0 to parse dates, adjust calendars, and work with date columns.
Start with the data you have, or [install rsTimes and move your first date](getting-started/index.md).

| Your data or task | Start here |
| --- | --- |
| A Python date or datetime | [Move a date with Delta](guides/delta.md) or [work with one timestamp](guides/pydt.md) |
| A pandas date index | [Create a Pddt index](guides/pddt.md) |
| A Polars date column | [Work with a Pldt column](guides/pldt.md) |
| A Polars expression or LazyFrame | [Parse a column in a query](getting-started/polars-query.md) |
| Date strings or epoch values | [Parse a date or timestamp](guides/parsing.md) |
| An existing beta installation | [Upgrade to 1.0.0](compatibility/migration.md) |

[Look up an API](api/index.md) for its signature, return type, and examples.

```{toctree}
:maxdepth: 1

Getting started <getting-started/index>
Concepts <concepts/index>
Guides <guides/index>
Recipes <recipes/index>
API reference <api/index>
Compatibility <compatibility/index>
Troubleshooting <troubleshooting>
Development <development/index>
```
