# Native windows on an rsTimes date column

## Read a rolling date minimum

(ref-pldt-native-rolling-min)=
```python
from rstimes import Pldt

events = Pldt([0, 2_000_000_000, 4_000_000_000], unit="ns", tz="UTC", name="event")
rolling = events.rolling_min(window_size=2)
print(rolling.to_physical().to_list())
```

**Output**

```text
[None, 0, 2000000000]
```

Pldt inherits native rolling and cumulative analysis methods. A row window
uses an integer `window_size`; a time window uses a `by` column and a duration
such as `'3s'`. These methods return ordinary native Series. Their statistical
units and numerical precision rules are separate from rsTimes calendar changes
and explicit date differences.

The following data is at 0, 2 and 4 seconds after the Unix epoch, stored in ns
with UTC metadata. This makes the mathematical window answers explicit.

## Row windows returning dates and ranks

The default fixed window needs two valid values when `window_size=2`.
The first result is therefore null. Mean and median return dates at the
window midpoint; min/max return extrema. Native quantile's default nearest
interpolation selects the upper of the two ordered values in this example.
Rank returns Float64, with a null before the full window is available.

`min_samples` counts non-null observations. It controls whether a result exists;
it does not fill a missing input date. A Datetime return dtype also does not
imply that a numerical statistical kernel is an exact-integer ns algorithm.
Use the explicit rsTimes difference and calendar interfaces for their stated
semantics and precision contracts.

## Time windows with a separate ordering column

The sorted date column below also supplies the `by` axis. With `closed='right'`
and a 3-second window, each row after the first includes the previous and
current dates. The default `min_samples=1` permits a first-row result.
The time axis and the date values are distinct parameter roles even when the
same column supplies both.

## Statistical numerical outputs

For this ns date storage, native standard deviation is a Float64 value in
physical ns and variance is in ns squared. Neither result is a Duration Series.
With the default sample correction `ddof=1`, one observation is insufficient;
two observations separated by 2 seconds have variance `2e18` ns squared and
standard deviation `sqrt(2) * 1e9` ns. The checks use an explicit floating
comparison to those mathematical values.

## Numerical-only operations and cumulative expressions

The inherited rolling sum, skew, kurtosis and custom rolling-map kernels below
reject this Datetime dtype. They do not choose an elapsed duration or a calendar
operation for you. If you intend numerical analysis of a duration, first
produce the appropriate duration or numerical column explicitly.

`cumulative_eval` actually executes its expression over expanding windows and
returns a materialized Series. The maximum of each growing prefix is the
current date in this ascending input.

These are inherited provider operations; the
[native Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
defines their additional statistical options and stability labels. For
rsTimes workflows, continue with [date queries](../guides/pldt-queries.md),
[explicit differences](../guides/pldt-differences.md), or
[lazy date expressions](../guides/expressions.md).
