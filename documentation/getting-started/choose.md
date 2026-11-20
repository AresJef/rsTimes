# Choose a date API for your data

Choose by the Python object you have and the result you need.

| I have | Use | What I get |
| --- | --- | --- |
| One date or datetime | [`Delta` for calendar arithmetic](../guides/delta.md) | The date or datetime type follows the operand's rules. |
| One timestamp with date and time fields | [`Pydt`](../guides/pydt.md) | A Python datetime subclass with microsecond precision. |
| A pandas date index | [`Pddt`](../guides/pddt.md) | A pandas DatetimeIndex subclass. Choose seconds, milliseconds, microseconds, or nanoseconds as your data requires. |
| A Polars Series | [`Pldt` or the Series `.pldt` namespace](../guides/pldt.md) | Date results use Pldt. Queries return the appropriate native Series. |
| A Polars column expression | [The Expr `.pldt` namespace](polars-query.md) | A Polars Expr that runs in a DataFrame or LazyFrame query. |
| Raw text or an epoch value | [`parse_str`, `parse`, or `parse_to_epoch`](../guides/parsing.md) | A scalar datetime or an integer epoch in the requested unit. |

Use [units and missing dates](../concepts/units-and-missing.md) before choosing
a representation for nanosecond data or dates far from the epoch.
