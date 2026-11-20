# Apply timezones in a Polars date query

## Interpret a naive clock and convert it to UTC

(expr-localize-then-convert)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({
    "event": pl.Series([28_800_000_000, None], dtype=pl.Datetime("us")),
})
expr = pl.col("event").pldt.tz_localize("Asia/Shanghai").pldt.tz_convert("UTC")
print(frame.lazy().select(expr).collect()["event"].to_physical().to_list())
```

**Output**

```text
[0, None]
```

The result is Datetime(us, UTC). `tz_localize` determines the
instant from naive clock fields, and `tz_convert` changes the
zone on already aware dates. `tz_localize(None)` or
`tz_switch(None)` keeps local clock fields without the zone.
`tz_convert(None)` gives a UTC clock without the zone.
An explicit `base_tz` enables `tz_switch` on a naive column.
`astimezone()` uses the local zone by default.

## Resolve a nonexistent clock at a unit boundary

(expr-shift-daylight-saving-gap)=
```python
import polars as pl
import rstimes.pldt

frame = pl.DataFrame({"raw": ["2024-03-10 02:30", None]})
expr = pl.col("raw").pldt.parse(
    unit="ns", tz="America/New_York", nonexistent="shift_forward",
).pldt.isoformat()
print(frame.select(expr)["raw"].to_list())
```

**Output**

```text
['2024-03-10T03:00:00-04:00', None]
```

(expr-clock-policies)=
## Choose policies for a gap or a repeat

`shift_forward` selects the first valid clock. `shift_backward`
chooses the tick immediately before it. Use a single timedelta to
request an explicit move. An `ambiguous` Boolean column pairs with
the full logical input, including missing rows. `ambiguous="infer"`
uses the logical order within a column or group and needs enough
evidence for a repeated interval.

(expr-timezone-queries)=
## Query an offset or daylight saving time

`utcoffset_seconds()` returns Int64 with null when there is no
offset. `is_dst()` returns Boolean and uses False at null dates.
Both use the actual offset rules for the date. A logical timezone
or source dtype error may appear during schema resolution or run
time. Wrong static policy types can fail at expression creation.
