# Generate pandas date ranges

`Pddt.date_range` accepts `start` as its first positional argument; `end`,
`periods`, `freq`, and other options are keywords. With a frequency, supply
exactly two of start/end/periods. Without a frequency, three supplied values
request evenly spaced dates. Otherwise the default step is one calendar day.
Endpoints use the shared parser and target timezone rules. Numeric endpoints
are ticks at `unit`, or ns when omitted.

## Endpoints, direction, and inclusion

```{doctest} pddt-range-endpoints
>>> from datetime import timedelta
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt, Configs
>>> forward = Pddt.date_range('2024-01-01', periods=np.int64(3), unit='s', name='day')
>>> (type(forward) is Pddt, forward.unit, forward.name, forward.day.tolist(), forward.freqstr)
(True, 's', 'day', [1, 2, 3], 'D')
>>> Pddt.date_range(end='2024-01-03', periods=3).day.tolist()
[1, 2, 3]
>>> Pddt.date_range('2024-01-03', periods=3, freq='-1D').day.tolist()
[3, 2, 1]
>>> for inclusive, days in (('both', [1, 2, 3]), ('left', [1, 2]), ('right', [2, 3]), ('neither', [2])):
...     result = Pddt.date_range('2024-01-01', end='2024-01-03', freq='D', inclusive=inclusive)
...     assert type(result) is Pddt and result.day.tolist() == days
>>> Pddt.date_range(0, end=2, periods=3, freq=None, unit='ns').asi8.tolist()
[0, 1, 2]
>>> Pddt.date_range('2024-01-01', periods=0, tz='UTC', unit='ms').empty
True
>>> Pddt.date_range('2024-01-01 15:30', periods=2, normalize=True).hour.tolist()
[0, 0]
>>> config = Configs()
>>> config.add_month('harvest', 10)
True
>>> Pddt.date_range('1 harvest 2024', periods=2, cfg=config).month.tolist()
[10, 10]
```

## Fixed and calendar frequencies

Current string vocabulary is the same on pandas 2 and 3. Use `min` for minutes,
`ME` for month end, and the listed calendar codes. Removed aliases such as `M`
are not accepted. Exact decimal or compound fixed frequencies are supported
when their complete step is an integer number of nanoseconds. Negative steps
generate descending ranges. A zero step is invalid.

The table inside this executable example gives two independently specified
Gregorian dates for every listed calendar-frequency family. Month/quarter/year
end schedules align the first result on or after the start. Weekly and fiscal
anchors are part of the frequency, not parser date-order preferences.

```{doctest} pddt-range-frequency-families
>>> calendar = [
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
>>> for frequency, expected in calendar:
...     result = Pddt.date_range('2024-01-01', periods=2, freq=frequency)
...     assert type(result) is Pddt and result.strftime('%Y-%m-%d').tolist() == expected
>>> for frequency, step in (('h', 3600000000000), ('min', 60000000000), ('s', 1000000000), ('ms', 1000000), ('us', 1000), ('ns', 1), ('1.5s', 1500000000), ('1h30min', 5400000000000), (timedelta(seconds=2), 2000000000)):
...     result = Pddt.date_range(0, periods=3, freq=frequency, unit='ns')
...     assert result.asi8.tolist() == [0, step, 2 * step]
>>> fine = Pddt.date_range(0, periods=3, freq='500ns')
>>> (fine.unit, fine.asi8.tolist())
('ns', [0, 500, 1000])
```

Custom business calendars preserve their actual weekmask and holiday rules.
General DateOffset, business-hour, fiscal RE/REQ, and genuine custom offset
rules use pandas' mature range executor with the already interpreted endpoints.
Their supported parameters, results, and original errors remain pandas' own.
The final result is wrapped as Pddt, and frequency metadata is retained only
when it still validates for that result.

```{doctest} pddt-range-custom-and-mature-frequencies
>>> business = pd.offsets.CustomBusinessDay(weekmask='Mon Wed Fri', holidays=['2024-01-03'])
>>> Pddt.date_range('2024-01-01', periods=3, freq=business).strftime('%Y-%m-%d').tolist()
['2024-01-01', '2024-01-05', '2024-01-08']
>>> for frequency in ('bh', 'cbh'):
...     result = Pddt.date_range('2024-01-01', periods=2, freq=frequency)
...     assert result.isoformat().tolist() == ['2024-01-01T09:00:00', '2024-01-01T10:00:00']
>>> general = pd.offsets.DateOffset(days=1, hours=2)
>>> Pddt.date_range('2024-01-01', periods=3, freq=general).isoformat().tolist()
['2024-01-01T00:00:00', '2024-01-02T02:00:00', '2024-01-03T04:00:00']
>>> for frequency in (pd.offsets.FY5253(startingMonth=1, weekday=6, variation='nearest'), pd.offsets.FY5253Quarter(startingMonth=1, weekday=6, variation='nearest')):
...     expected = pd.date_range('2024-01-01', periods=3, freq=frequency)
...     result = Pddt.date_range('2024-01-01', periods=3, freq=frequency)
...     assert type(result) is Pddt and result.as_unit('us').asi8.tolist() == expected.as_unit('us').asi8.tolist()
```

## Calendar days across a clock change

`D` keeps the local clock when a region changes offset. Fixed `24h` advances
actual elapsed time. Explicit DST policies resolve newly interpreted local
dates; they do not relocalize an already known instant. A boolean mask refers
to the full generated sequence before inclusive endpoints are removed.

```{doctest} pddt-range-dst-and-unit
>>> daily = Pddt.date_range('2024-03-09 12:00', periods=3, freq='D', tz='America/New_York')
>>> elapsed = Pddt.date_range('2024-03-09 12:00', periods=3, freq='24h', tz='America/New_York')
>>> (daily.hour.tolist(), elapsed.hour.tolist(), np.diff(daily.asi8).tolist())
([12, 12, 12], [12, 13, 13], [82800000000, 86400000000])
>>> shifted = Pddt.date_range('2024-03-09 02:30', periods=3, freq='D', tz='America/New_York', nonexistent='shift_forward')
>>> shifted.hour.tolist()
[2, 3, 2]
>>> chosen = Pddt.date_range('2024-11-02 01:30', end='2024-11-04 01:30', freq='D', tz='America/New_York', ambiguous=[True, False, True], inclusive='right')
>>> (chosen.isoformat().tolist(), chosen[0].fold)
(['2024-11-03T01:30:00-05:00', '2024-11-04T01:30:00-05:00'], 1)
>>> try:
...     Pddt.date_range('2024-11-02 01:30', end='2024-11-04 01:30', freq='D', tz='America/New_York', ambiguous=[False, True], inclusive='right')
... except ValueError as error:
...     print(type(error).__name__)
ValueError
>>> for call, exception in ((lambda: Pddt.date_range(0, periods=2, freq='500ns', unit='us'), ValueError), (lambda: Pddt.date_range('9999-01-01', periods=2, freq='D', unit='ns'), OverflowError), (lambda: Pddt.date_range('2024-01-01', end='2024-01-03', periods=3, freq='D'), ValueError), (lambda: Pddt.date_range('2024-01-01', periods=True), TypeError), (lambda: Pddt.date_range('2024-01-01', periods=-1), ValueError), (lambda: Pddt.date_range('2024-01-01', periods=2, normalize=1), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid range request accepted')
>>> for frequency in ('0s', '0.1ns', 'M', 'unknown'):
...     try:
...         Pddt.date_range('2024-01-01', periods=2, freq=frequency)
...     except ValueError:
...         continue
...     raise AssertionError(frequency)
```

See pandas' [offset reference](https://pandas.pydata.org/docs/reference/offset_frequency.html)
for the full parameters of the explicitly delegated rules. Custom business
frequency code `C` alone does not record a custom object's holidays; preserve
that object when reproducing a schedule.
