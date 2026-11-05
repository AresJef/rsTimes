# Generate native Polars date ranges

`Pldt.date_range` is an eager factory returning Pldt. Supply exactly two of
start/end/periods with a frequency. With all three and freq=None it generates
an integer-grid subdivision. Otherwise the default step is one calendar day.
Only start is positional; other options are keywords. Numeric endpoints are
ticks at unit, or ns when omitted, rather than the seconds of fromtimestamp.

Pldt has no Index or freq metadata. To use a completed range in a lazy query,
insert its Series with a native Polars literal; it is not regenerated at collect.

```{doctest} pldt-range-endpoints
>>> from datetime import timedelta
>>> import importlib.util
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Configs
>>> result = Pldt.date_range('2024-01-01', periods=np.int64(3), name='day')
>>> (type(result) is Pldt, result.dtype, result.name, result.day.to_list())
(True, Datetime(time_unit='us', time_zone=None), 'day', [1, 2, 3])
>>> Pldt.date_range(end='2024-01-03', periods=3).day.to_list()
[1, 2, 3]
>>> Pldt.date_range('2024-01-03', periods=3, freq='-1D').day.to_list()
[3, 2, 1]
>>> for inclusive, expected in (('both', [1, 2, 3]), ('left', [1, 2]), ('right', [2, 3]), ('neither', [2])):
...     assert Pldt.date_range('2024-01-01', end='2024-01-03', freq='D', inclusive=inclusive).day.to_list() == expected
>>> Pldt.date_range(0, end=5, periods=4, unit='ns').to_physical().to_list()
[0, 1, 3, 5]
>>> Pldt.date_range(5, end=0, periods=4, unit='ns').to_physical().to_list()
[5, 3, 1, 0]
>>> empty = Pldt.date_range('2024-01-01', periods=0, tz='UTC', unit='ms')
>>> (len(empty), empty.dtype)
(0, Datetime(time_unit='ms', time_zone='UTC'))
>>> Pldt.date_range('2024-01-01 15:30', periods=2, normalize=True).hour.to_list()
[0, 0]
>>> expression = pl.lit(result).alias('day')
>>> eager, lazy = pl.select(expression), pl.LazyFrame().select(expression).collect()
>>> assert type(expression) is pl.Expr and eager.schema == lazy.schema == {'day': pl.Datetime('us')}
>>> eager['day'].to_physical().to_list() == lazy['day'].to_physical().to_list() == result.to_physical().to_list()
True
```

## Ordinary frequencies need no pandas

Native rules include fixed ns/us/ms/s/min/h durations, exact decimal/compound
steps, calendar D/W, month/quarter/year boundaries, static business rules,
semi-month boundaries, and position weekdays. Use current names such as min,
ME, and QS-JAN. The two dates for each rule below are explicit Gregorian
expectations, and every rule is actually invoked in Polars-only validation.

```{doctest} pldt-range-native-frequencies
>>> cases = [
...     ('D', ['2024-01-01', '2024-01-02']),
...     ('B', ['2024-01-01', '2024-01-02']),
...     ('C', ['2024-01-01', '2024-01-02']),
...     ('W', ['2024-01-07', '2024-01-14']),
...     ('W-MON', ['2024-01-01', '2024-01-08']),
...     ('MS', ['2024-01-01', '2024-02-01']),
...     ('ME', ['2024-01-31', '2024-02-29']),
...     ('QS-JAN', ['2024-01-01', '2024-04-01']),
...     ('QE-DEC', ['2024-03-31', '2024-06-30']),
...     ('YS-JAN', ['2024-01-01', '2025-01-01']),
...     ('YE-DEC', ['2024-12-31', '2025-12-31']),
...     ('BMS', ['2024-01-01', '2024-02-01']),
...     ('BME', ['2024-01-31', '2024-02-29']),
...     ('BQS-JAN', ['2024-01-01', '2024-04-01']),
...     ('BQE-DEC', ['2024-03-29', '2024-06-28']),
...     ('BYS-JAN', ['2024-01-01', '2025-01-01']),
...     ('BYE-DEC', ['2024-12-31', '2025-12-31']),
...     ('CBMS', ['2024-01-01', '2024-02-01']),
...     ('CBME', ['2024-01-31', '2024-02-29']),
...     ('SMS', ['2024-01-01', '2024-01-15']),
...     ('SME', ['2024-01-15', '2024-01-31']),
...     ('WOM-2MON', ['2024-01-08', '2024-02-12']),
...     ('LWOM-FRI', ['2024-01-26', '2024-02-23']),
... ]
>>> for frequency, expected in cases:
...     actual = Pldt.date_range('2024-01-01', periods=2, freq=frequency)
...     assert type(actual) is Pldt and actual.isoformat().to_list() == [d + 'T00:00:00' for d in expected]
>>> for frequency, step in (('h', 3600000000000), ('min', 60000000000), ('s', 1000000000), ('ms', 1000000), ('us', 1000), ('ns', 1), ('1.5s', 1500000000), ('1h30min', 5400000000000), (timedelta(seconds=2), 2000000000)):
...     actual = Pldt.date_range(0, periods=3, freq=frequency, unit='ns')
...     assert actual.dtype == pl.Datetime('ns') and actual.to_physical().to_list() == [0, step, 2 * step]
>>> (Pldt.date_range(0, periods=3, freq='500ns').dtype, Pldt.date_range(0, periods=3, freq='500ns').to_physical().to_list())
(Datetime(time_unit='ns', time_zone=None), [0, 500, 1000])
```

## Special rules use optional mature pandas execution

General DateOffset combinations, genuine custom offsets, business hours, and
52/53-week fiscal rules retain their mature pandas executor. Static rules
remain native even when pandas is installed. A requested special rule without
pandas raises an explicit ImportError rather than changing its meaning.

```{doctest} pldt-range-optional-pandas
>>> if importlib.util.find_spec('pandas') is not None:
...     import pandas as pd
...     assert Pldt.date_range('2024-01-01', periods=2, freq='bh').hour.to_list() == [9, 10]
...     business = pd.offsets.CustomBusinessDay(weekmask='Mon Wed Fri', holidays=['2024-01-03'])
...     assert Pldt.date_range('2024-01-01', periods=3, freq=business).day.to_list() == [1, 5, 8]
...     general = Pldt.date_range('2024-01-01', periods=3, freq=pd.offsets.DateOffset(days=1, hours=2))
...     assert type(general) is Pldt and general.hour.to_list() == [0, 2, 4]
...     fiscal = pd.offsets.FY5253(startingMonth=1, weekday=6, variation='nearest')
...     actual = Pldt.date_range('2024-01-01', periods=3, freq=fiscal)
...     expected = pd.date_range('2024-01-01', periods=3, freq=fiscal)
...     assert actual.as_unit('us').to_physical().to_list() == expected.as_unit('us').asi8.tolist()
... else:
...     try:
...         Pldt.date_range('2024-01-01', periods=2, freq='bh')
...     except ImportError as error:
...         assert 'pandas' in str(error)
...     else:
...         raise AssertionError('missing special-rule dependency was ignored')
```

## DST, endpoint precision, and invalid requests

A calendar D keeps local clock meaning across DST; a fixed 24h advances elapsed
time. Policies interpret newly generated regional clocks. Masks cover the whole
generated sequence before inclusive endpoints are removed. Every supplied
endpoint must fit the requested unit, even when it is excluded or the result
is empty. normalize=True deliberately clears the clock before precision checks.

```{doctest} pldt-range-dst-and-validation
>>> daily = Pldt.date_range('2024-03-09 12:00', periods=3, freq='D', tz='America/New_York')
>>> elapsed = Pldt.date_range('2024-03-09 12:00', periods=3, freq='24h', tz='America/New_York')
>>> (daily.hour.to_list(), elapsed.hour.to_list(), np.diff(daily.to_physical().to_numpy()).tolist())
([12, 12, 12], [12, 13, 13], [82800000000, 86400000000])
>>> chosen = Pldt.date_range('2024-11-02 01:30', end='2024-11-04 01:30', freq='D', tz='America/New_York', ambiguous=[True, False, True], inclusive='right')
>>> chosen.isoformat().to_list()
['2024-11-03T01:30:00-05:00', '2024-11-04T01:30:00-05:00']
>>> for call, exception in ((lambda: Pldt.date_range(0, periods=2, freq='500ns', unit='us'), ValueError), (lambda: Pldt.date_range('2024-01-01', end='2024-01-03', periods=3, freq='D'), ValueError), (lambda: Pldt.date_range('2024-01-01', periods=True), TypeError), (lambda: Pldt.date_range('2024-01-01', periods=-1), ValueError), (lambda: Pldt.date_range('2024-01-01', periods=2, normalize=1), TypeError), (lambda: Pldt.date_range('2024-11-02 01:30', end='2024-11-04 01:30', tz='America/New_York', ambiguous=[False, True], inclusive='right'), ValueError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid range request accepted')
>>> for frequency in ('0s', '0.1ns', 'M', 'unknown'):
...     try:
...         Pldt.date_range('2024-01-01', periods=2, freq=frequency)
...     except ValueError:
...         continue
...     raise AssertionError(frequency)
```
