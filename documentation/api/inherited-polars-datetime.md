# The inherited native Polars .dt namespace

`Pldt.dt` is Polars' original temporal namespace. Its methods keep Polars
parameter names, result types and errors. They do not automatically use
`.pldt` rules. In particular, native `.dt` date results are ordinary Series,
native nanosecond is the complete fraction, weekday uses ISO numbering, and
native predicates propagate nulls.

The following examples call every inherited `.dt` method on an actual Pldt.
Literal calendar/physical answers were checked independently with a standalone
Polars Series. See the [upstream temporal API](https://docs.pola.rs/api/python/stable/reference/series/temporal.html)
for its complete parameter reference; dependency versions in this site's
verification record identify the actual behavior tested here.

## Native integer and Boolean fields

```{doctest} inherited-polars-dt-fields
>>> from datetime import date, datetime, time
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> source_tick = int(np.datetime64('2024-02-29T04:34:56.123456789', 'ns').astype(np.int64))
>>> value = Pldt(pl.Series('event', [source_tick, None], dtype=pl.Datetime('ns', 'Asia/Shanghai')))
>>> fields = [
...     ('year', pl.Int32, 2024), ('month', pl.Int8, 2), ('day', pl.Int8, 29),
...     ('hour', pl.Int8, 12), ('minute', pl.Int8, 34), ('second', pl.Int8, 56),
...     ('millisecond', pl.Int32, 123), ('microsecond', pl.Int32, 123456),
...     ('nanosecond', pl.Int32, 123456789), ('quarter', pl.Int8, 1),
...     ('week', pl.Int8, 9), ('weekday', pl.Int8, 4), ('ordinal_day', pl.Int16, 60),
...     ('days_in_month', pl.Int8, 29), ('iso_year', pl.Int32, 2024),
...     ('millennium', pl.Int32, 3), ('century', pl.Int32, 21),
...     ('is_leap_year', pl.Boolean, True), ('is_business_day', pl.Boolean, True),
... ]
>>> for method, dtype, expected in fields:
...     result = getattr(value.dt, method)()
...     assert type(result) is pl.Series and result.name == 'event' and result.dtype == dtype
...     assert result.to_list() == [expected, None]
>>> (value.dt.nanosecond().to_list(), value.nanosecond.to_list())
([123456789, None], [789, None])
>>> (value.dt.weekday().to_list(), value.weekday.to_list())
([4, None], [3, None])
>>> (value.dt.is_leap_year().to_list(), value.is_leap_year.to_list())
([True, None], [True, False])
>>> value.dt.second(fractional=True).to_list()
[56.123456789, None]
```

## Native date transformations and zone roles

Native field replacement is `.dt.replace`, native unit casting is
`.dt.cast_time_unit`, and whole-value replacement remains `Series.replace`.
`combine` uses the local date and retains the aware source zone in the tested
native API. It is not a promise of naive output. Converting a timezone keeps
the instant; replacing it reinterprets the clock. Native timezone replacement
uses the keyword `non_existent`, distinct from rsTimes' `nonexistent`.

```{doctest} inherited-polars-dt-transformations
>>> def check(result, dtype, ticks):
...     assert type(result) is pl.Series and result.dtype == dtype and result.name == 'event'
...     assert result.to_physical().to_list() == ticks
>>> check(value.dt.cast_time_unit('us'), pl.Datetime('us', 'Asia/Shanghai'), [1709181296123456, None])
>>> check(value.dt.combine(time(9, 30), time_unit='ns'), pl.Datetime('ns', 'Asia/Shanghai'), [1709170200000000000, None])
>>> check(value.dt.convert_time_zone('UTC'), pl.Datetime('ns', 'UTC'), [1709181296123456789, None])
>>> check(value.dt.replace_time_zone('UTC'), pl.Datetime('ns', 'UTC'), [1709210096123456789, None])
>>> check(value.dt.replace(day=1), pl.Datetime('ns', 'Asia/Shanghai'), [1706762096123456789, None])
>>> check(value.dt.month_start(), pl.Datetime('ns', 'Asia/Shanghai'), [1706762096123456789, None])
>>> check(value.dt.month_end(), pl.Datetime('ns', 'Asia/Shanghai'), [1709181296123456789, None])
>>> check(value.dt.offset_by('1mo'), pl.Datetime('ns', 'Asia/Shanghai'), [1711686896123456789, None])
>>> check(value.dt.add_business_days(1, holidays=[date(2024, 3, 1)]), pl.Datetime('ns', 'Asia/Shanghai'), [1709526896123456789, None])
>>> check(value.dt.round('1h'), pl.Datetime('ns', 'Asia/Shanghai'), [1709182800000000000, None])
>>> check(value.dt.truncate('1h'), pl.Datetime('ns', 'Asia/Shanghai'), [1709179200000000000, None])
>>> check(value.dt.date(), pl.Date, [19782, None])
>>> check(value.dt.time(), pl.Time, [45296123456789, None])
>>> check(value.dt.epoch('ns'), pl.Int64, [1709181296123456789, None])
>>> check(value.dt.timestamp('ns'), pl.Int64, [1709181296123456789, None])
>>> check(value.dt.base_utc_offset(), pl.Duration('ms'), [28800000, None])
>>> check(value.dt.dst_offset(), pl.Duration('ms'), [0, None])
>>> value.to_physical().to_list()
[1709181296123456789, None]
```

Native casting can deliberately lose precision. Use the corresponding checked
rsTimes operation when its documented unit, capacity or localization rules are
needed. Native business calendars accept explicit week masks and holiday dates;
the example excludes Friday March 1, so Thursday February 29 moves to Monday
March 4 while keeping the clock.

## Text and Python scalar exits

Native strftime uses its own directives and fraction rules. `%f` is nine-digit
nanoseconds even on ms/us native storage, whereas rsTimes strftime uses six
digits for those units. The native `min`/`max` methods here return standard
Python datetime and intentionally limit fractions to microseconds.

```{doctest} inherited-polars-dt-text-and-scalars
>>> check(value.dt.strftime('%Y-%m-%d %H:%M:%S%.9f'), pl.String, ['2024-02-29 12:34:56.123456789', None])
>>> check(value.dt.to_string('%Y-%m-%d %H:%M:%S%.9f%:z'), pl.String, ['2024-02-29 12:34:56.123456789+08:00', None])
>>> for method in ('min', 'max'):
...     result = getattr(value.dt, method)()
...     assert type(result) is datetime and result.isoformat() == '2024-02-29T12:34:56.123456+08:00'
...     assert getattr(Pldt([], unit='ns').dt, method)() is None
>>> coarse = Pldt([123, None], unit='ms')
>>> (coarse.dt.strftime('%f').to_list(), coarse.strftime('%f').to_list())
(['123000000', None], ['123000', None])
```

## Duration totals reject a Datetime receiver

All seven visible `total_*` methods require Duration. They reject the Pldt
Datetime receiver with the same native error as a plain Datetime Series.
Subtracting dates produces the appropriate native Duration Series; the second
half demonstrates the methods on that supported dtype. This does not claim
Duration is a Pldt storage dtype.

```{doctest} inherited-polars-dt-duration-role
>>> methods = {'total_days': 1, 'total_hours': 25, 'total_minutes': 1501, 'total_seconds': 90061, 'total_milliseconds': 90061002, 'total_microseconds': 90061002003, 'total_nanoseconds': 90061002003004}
>>> native = pl.Series('event', [source_tick, None], dtype=pl.Datetime('ns', 'Asia/Shanghai'))
>>> for method in methods:
...     errors = []
...     for namespace in (value.dt, native.dt):
...         try:
...             getattr(namespace, method)()
...         except pl.exceptions.SchemaError as error:
...             errors.append(type(error))
...         else:
...             raise AssertionError('Duration total accepted a Datetime receiver')
...     assert errors == [pl.exceptions.SchemaError, pl.exceptions.SchemaError]
>>> duration = pl.Series('duration', [90061002003004, None], dtype=pl.Duration('ns'))
>>> for method, expected in methods.items():
...     result = getattr(duration.dt, method)()
...     assert type(result) is pl.Series and result.dtype == pl.Int64 and result.to_list() == [expected, None]
>>> fractional = duration.dt.total_seconds(fractional=True)
>>> (fractional.dtype == pl.Float64, fractional.to_list())
(True, [90061.002003004, None])
```

The [rsTimes eager guide](../guides/pldt.md) and
[native output guide](../guides/pldt-output.md) cover the `.pldt` contract.
Do not interchange native and rsTimes namespace names based on similar spelling.

## Native namespace indexing protocol

`x.dt[item]` delegates to native Series indexing. A scalar returns a standard
Python datetime or None and therefore truncates nanoseconds to microseconds.
A slice or integer gather returns an ordinary native Series with its exact
date unit and null bitmap. Upstream's int-only method annotation does not fully
express the observed slice/gather runtime support.

```{doctest} inherited-polars-dt-index-protocol
>>> small = Pldt([123, None], unit='ns', name='event')
>>> (type(small.dt[0]) is datetime, small.dt[0].isoformat(), small.dt[1] is None)
(True, '1970-01-01T00:00:00', True)
>>> for selector in (slice(0, 1), [0], np.array([0], dtype=np.int64), pl.Series([0], dtype=pl.Int64)):
...     selected = small.dt[selector]
...     assert type(selected) is pl.Series and selected.dtype == pl.Datetime('ns')
...     assert selected.name == 'event' and selected.to_physical().to_list() == [123]
>>> try:
...     small.dt['unknown']
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```
