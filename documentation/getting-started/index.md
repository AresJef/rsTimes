# Move your first date with rsTimes

Install rsTimes 1.1.1 in a Python environment. You can move a standard Python
date with `Delta` as soon as the installation finishes.

```bash
python -m pip install "rsTimes==1.1.1"
```

## Add one month to a billing date

(getting-started-calendar-change)=
```python
from datetime import date

from rstimes import Delta

invoice_date = date(2024, 1, 31)
next_invoice = invoice_date + Delta(months=1)
print(next_invoice)
```

**Output**

```text
2024-02-29
```

February has no 31st day. A calendar month moves this date to the last day of
February, which is February 29 in 2024. The result is a Python `date`.

## Start with the kind of data you have

- A single date or time uses [Pydt](../guides/pydt.md) for date and time operations.
- A pandas date index uses [Pddt](../guides/pddt.md). Install the `pandas` extra for this path.
- A Polars column or query uses [Pldt and the date namespace](../guides/pldt.md).
  [Parse dates in a Polars query](polars-query.md) to see how a missing value is handled.

[Choose a date API for your data](choose.md) to compare return types.
[Installation](install.md) covers the optional extras and supported interpreters. If you used the beta, read
[what changed in 1.1.1](../compatibility/migration.md).

```{toctree}
:hidden:

install
choose
polars-query
```
