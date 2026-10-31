# Pldt: native Polars date columns and expressions

This guide describes the current **local PLDT development candidate**. The
previously published `0.2.0b2` is the frozen reference; publication of this work
is a separate action. The public classes are `Delta`, `Pydt`, `Pddt` and `Pldt`.

Install the optional Polars capability to use `Pldt`. NumPy remains a default
dependency. Ordinary Pldt calculations require neither pandas nor dateutil,
PyArrow or Babel. Special pandas range rules and Arrow exports retain their
explicit optional dependencies. Importing `Pldt` registers `.pldt` on native
Polars Series and Expr once; an already occupied third-party name is an error.

## Eager and lazy use

```python
import polars as pl
from rstimes import Delta, Pldt

x = Pldt(["2024-01-31T12:34:56.123456789", None], name="time")
assert isinstance(x, pl.Series)
assert x.dtype == pl.Datetime("ns")
assert x.nanosecond.to_list() == [789, None]

eager = x.to_next_month()
expr = pl.col("time").pldt.to_next_month()
assert isinstance(eager, Pldt)
assert isinstance(expr, pl.Expr)
frame = pl.DataFrame({"time": x})
lazy_result = frame.lazy().select(expr).collect()["time"]
assert lazy_result.to_physical().to_list() == eager.to_physical().to_list()
```

There is no custom Expr wrapper and no `to_expr()` step. DataFrame/LazyFrame,
filter, select, group/window and collection are native Polars operations. Date
work executes in native Rust kernels, not a Python per-row UDF. A scalar Expr
such as `max()` retains native aggregation cardinality; a concrete one-row
column is a column, not a scalar.

`Pldt` is a real Series subclass. It retains Polars' mutable **shell** model;
it is not an immutable pandas index. Ordinary native slicing, clone, indexing
and element extraction retain Polars' return/protocol boundaries. Integer,
Boolean, String, Date, Time, Struct and Duration results are ordinary Series;
time tables are eager DataFrames or native Struct Exprs. Not every result is
wrapped as Pldt, and a native scalar is not automatically Pydt.

## Input, units, missing data and ownership

Construction requires one-dimensional ordered data: supported iterables,
NumPy columns, pandas native date columns/Pddt when installed, and Polars
Date/Datetime columns. Scalar input belongs in `[value]` or in a named factory
with `size`. Mapping/set/frozenset/table/Expr/nested and two-dimensional inputs
are not silently converted or flattened. Native dtype/unit/timezone/validity
drive dispatch; types are not guessed from names or a first row.

Polars has Datetime `ms`, `us` and `ns`, with no `s` storage type. Initial unit
selection occurs before parsing: native supported units are retained, text
retains its declared fractional resolution, bare numeric ticks default to ns,
and untyped empty/missing-only input defaults to ms. Explicit initial units
must be lossless. Existing operations keep the current unit: precision loss is
ValueError, actual capacity loss is OverflowError. Explicitly call
`as_unit(unit=..., round_ok=...)`; there is no automatic fallback.

```python
import numpy as np

x = Pldt([-1500, None], unit="ns")
assert x.as_unit("us").to_physical().to_list() == [-2, None]
# x.as_unit("us", round_ok=False) raises ValueError: the conversion is inexact.
assert x.dtype == pl.Datetime("ns")

minimum = -(1 << 63)
wide = Pldt([minimum, None], unit="ns")
assert wide.to_physical().to_list() == [minimum, None]
assert wide.is_null().to_list() == [False, True]
```

Null has a separate validity bit; valid int64 MIN is not null. Exports to a
NaT-sentinel representation reject a real collision by default. Set
`allow_nat_collision=True` only to explicitly allow that loss; it does not
permit overflow or arbitrary precision loss. Arrow-backed pandas output can
preserve validity independently. `to_physical()` plus validity preserves the
complete native representation without requiring Python datetime capacity.

`copy=False` permits safe sharing, not universal zero-copy. Known writable
NumPy storage can require one owned result before native detached execution.
`copy=True` physically isolates dates and validity. Source append/state-handle
replacement cannot change a separately constructed Pldt's shell. Keeping an
owner or a read-only NumPy view does not freeze a writable base alias; arbitrary
external raw-pointer writes are outside the concurrent snapshot promise.

## Parser and named factories

Ordinary text uses the existing Rust Parser grammar, Configs and strict rules.
`isoformat=True` means ISO-first with shared fallback, not ISO-only. Ordering is
explicit non-None > Configs > yearfirst=True/dayfirst=False. A required default
must be independently complete and only supplies YMD/year reference, not the
column's time, timezone or fold. Empty/NaT/NaN markers are distinct from failed
parsing; bad text is not silently turned into null.

```python
parsed = pl.DataFrame({"text": ["2024-02-29T12:00:00.123456789"]})
expr = pl.col("text").pldt.parse(unit="ns")
assert parsed.select(expr)["text"].dtype == pl.Datetime("ns")
formatted = Pldt.strptime(["1970-01-01 00:00:00.123456789"],
                         "%Y-%m-%d %H:%M:%S.%f", unit="ns")
assert formatted.nanosecond.to_list() == [789]
```

Expr parsing freezes Configs/default/format and must determine output schema
before reading rows. Formats with `%f` need an explicit Expr unit, timezone
directives need an explicit target zone. `%Z` uses Configs' explicit names;
there is no automatic local abbreviation guess. `fromisoformat` is the strict
ISO-only factory. `fromdate`, `fromdatetime`, `fromdatetime64` keep their actual
source roles and do not become general string parsers.

| Factory or export | Meaning |
|---|---|
| `fromseconds` | Calendar-coordinate seconds, with supported fractions |
| `frommicroseconds` | Integer calendar-coordinate microseconds |
| `fromtimestamp` / `utcfromtimestamp` | Real Unix seconds/instants |
| `toseconds(utc=False)` | Float64 local calendar-coordinate seconds |
| `tomicroseconds(utc=False)` | Int64 local calendar-coordinate microseconds |
| `timestamp()` | Float64 real Unix seconds; naive input needs the local service |
| `fromdate` | Local YMD only; clear source clock/fraction/timezone |
| `fromdatetime` | Keep complete precision; explicit target replaces zone, preserving wall fields |
| `fromdatetime64` | Decode actual NumPy dates/units/multipliers; target localizes the decoded clocks |
| `fromordinal` / `fromisocalendar` / `fromdayofyear` | Native integer calendars, including representable zero/negative/wide years |
| `combine` | Independent date and clock roles; one final native column |
| `now` / `today` / `utcnow` | Current time at requested resolution; today retains the clock, no fabricated ns |
| `date_range` | Native common elapsed/calendar generation; only approved special rules delegate to optional pandas |

```python
clock = Pldt(["1970-01-01 08:00:00"], tz="Asia/Shanghai")
assert clock.toseconds().to_list() == [28800.0]
assert clock.toseconds(utc=True).to_list() == [0.0]
assert clock.timestamp().to_list() == [0.0]
assert Pldt.fromseconds([1e-9], unit="ns").to_physical().to_list() == [1]
assert Pldt.frommicroseconds([1], unit="ns").to_physical().to_list() == [1000]
```

Bare constructor `Pldt([1], unit="ms")` means one millisecond tick, while
`fromseconds([1], unit="ms")` means one second stored as 1000 milliseconds.
Do not confuse a storage unit with the input quantity.

## Calendar changes, arithmetic and period operations

Optional field None retains the original; zero/negative numbers are real
values where meaningful. Integer-only parameters reject bool and floats.
Scalar modification targets broadcast; collections must be exactly source
length and are matched by position, not labels. Single-element collections do
not expand dates. Frequency, unit, precision and ordinary switches stay scalar.

Native replace/round/diff keep their Polars meaning. Use `.pldt.replace(...)`
for strict date-field replacement, `.pldt.round/ceil/floor(freq=...)` for date
rounding and `.pldt.diff(target, unit)` for signed boundary counts. Pddt uses
`.pddt.replace(...)` for the same date-field role. Convenience `to_datetime`,
`to_date`, `to_time` and year/quarter/month/weekday/day moves retain their
separate valid upper-selection/month-end behavior.

```python
x = Pldt(["2024-01-31", "2024-03-31"], unit="ns")
assert x.pldt.replace(month=2, day=28).day.to_list() == [28, 28]
assert x.to_date(month=2, day=31).day.to_list() == [29, 29]
assert x.add(months=[1, 2]).month.to_list() == [2, 5]
assert (x + Delta(nanoseconds=1)).nanosecond.to_list() == [1, 1]
assert Pldt([1], unit="us").add(microseconds=1, nanoseconds=-1000).to_physical().to_list() == [1]
```

`Delta` calendar days/months and fixed elapsed Duration are different across
DST. Date subtraction returns native Duration; named `add_delta/sub_delta`
retain actual Delta absolute fields and ns. Unknown operands and genuine
subclass operator callbacks retain Python negotiation; no DateOffset guessing.

First/last/start/end and their four queries use the same period boundaries.
Snap accepts one natural unit or a saved month/weekday name, compares real
candidate instants and takes the later candidate on a tie. It is not arbitrary
`15min` frequency rounding. `fsp(precision)` truncates the fractional second
without carrying, preserves unit and never fabricates finer source data.

## Timezones, queries, outputs and business state

`tz_localize` interprets naive clocks; `tz_convert` preserves known instants.
`tz_localize(None)` removes the zone while retaining clocks;
`tz_convert(None)` first goes to UTC, then removes it. The native column has
one timezone. UTC metadata returns `timezone.utc`; other encoded keys return
ZoneInfo, not the original Python input identity. The backend's actual zone
set is `tz_available`; local lookup is lazy. Native/host timezone database
versions and historical representation/capacity differences remain explicit.

Full ambiguous policies include raise/NaT/infer/true booleans/equal-length true
boolean masks. Nonexistent accepts its complete single strategy or timedelta.
Infer is native Rust and preserves logical order across chunks. Automatic
calendar/rounding/period methods preserve their mathematical direction and
period meaning rather than blindly applying a generic gap shift. Naive, UTC
and representable fixed offsets avoid unnecessary regional checks.

Field/calendar queries return nullable Int64; source-null Boolean queries are
False. Query targets are validated even when the source is null. ISO tables
have UInt32 children and reject a negative ISO year rather than wrap it; signed
`isoyear()` remains available. Time tables keep their fixed nine-field schema.

ISO/ctime/name/timezone-name outputs are native and retain actual ns. Shared
strftime `%f` emits 9 digits for ns, 6 for ms/us; `%.1f` through `%.9f` emit a
dot and a truncated/padded fraction, `%.0f` emits nothing. Numeric fields run
natively. System-locale/platform-specific formatting is eager-only; Expr does
not silently collect or fall back to a Python UDF. The same approved fraction
rules apply to Pydt and Pddt.

`.datetime()` explicitly exports an object ndarray of Pydt/None at us precision;
`.timetz` exports standard time/None. Native Date/Time exports remain Series.
Native scalar extraction follows Polars' own Python output and precision rules.

`copy`, `copy.copy`, `copy.deepcopy` and trusted pickle preserve core values,
validity, unit, zone, name and actual business dict/slots. Deep copy uses one
memo and physically distinct buffers; restore/copy does not rerun business
initialization. Ordinary new date results of a real Pldt subclass invoke its
normal constructor once. Native Expr serialization remains Polars' protocol;
rsTimes does not download plugins or execute arbitrary plans on load.

The installed `pldt.pyi` documents every own eager/namespace method. Concrete
Pldt operations retain type information, including its typed `.pldt` and
subclass results. Recognition of dynamically registered `.pldt` on a plain
Polars Expr/Series depends on the external checker; no global stub mutation or
extra checker plugin is installed.
