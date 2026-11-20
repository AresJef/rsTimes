# Pair row arguments and reuse Polars date expressions

## Use one calendar offset per group

(expr-broadcast-group-offset)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([0, 0, 0, None], dtype=pl.Datetime("us")),
    "site": ["A", "B", "A", "B"],
    "days": [1, 2, 3, 4],
})
expr = pl.col("event").pldt.add(days=pl.col("days").max()).over("site")
print(frame.lazy().select(expr).collect()["event"].to_physical().to_list())
```

**Output**

```text
[259200000000, 345600000000, 259200000000, None]
```

The expression takes the maximum day count within each site and
applies it to that group's dates. `over` maps results to the
original row positions. `group_by(...).agg(...)` can return
grouped lists of dates. The declared output dtype describes how
Polars represents the operation.

A genuine scalar expression, such as `pl.lit(3)` or a valid
scalar aggregate, broadcasts within its logical domain.
A one-element column such as `pl.col("days").head(1)` still
has to match the logical input length.
A concrete Delta vector also matches those positions. Filtering
before computing the date changes which rows need a matching
vector. Filtering the computed result keeps the already applied
changes.

## Reuse the configuration captured by a query

(expr-freeze-parser-default)=
```python
import polars as pl
from rstimes import Configs
import rstimes.pldt

config = Configs()
frame = pl.DataFrame({"raw": ["12:30", None]})
expr = pl.col("raw").pldt.parse(
    unit="us", cfg=config, default="14 Jan 2024",
).alias("event")
config.set_month({"jan": 8})
print(frame.lazy().select(expr).collect()["event"].to_list())
```

**Output**

```text
[datetime.datetime(2024, 1, 14, 12, 30), None]
```

This expression captured January 14 before the edit. A new
expression or a new eager call sees the updated month vocabulary.
Text parsing reads the stored text of a `str` subclass. To use
that subclass's custom conversion, call `str(value)` explicitly
before passing the result.

Configs, complete defaults, prepared format data and concrete
Delta rules are held by the created expression. A dynamic
Python arithmetic override belongs in an eager call.

## Recreate a query from a native expression in the same environment

(expr-restore-native-query)=
```python
import io

import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([0, None], dtype=pl.Datetime("ns")),
})
prepared = pl.col("event").pldt.add(nanoseconds=1)
expr = pl.Expr.deserialize(io.BytesIO(prepared.meta.serialize()))
print(frame.select(expr)["event"].to_physical().to_list())
```

**Output**

```text
[1, None]
```

The restored query uses the same compatible installed plugin.
Load trusted plans. For a durable workflow, retain source data,
schema, configuration and query code so you can build the
query against the intended package and Polars versions.

Elementwise date work can use native streaming. Order-sensitive
inference requires the whole logical sequence within a group.
A row index in a plugin error refers to the available logical
batch position. Upstream filters and grouping can change its
relationship to the original input file.
