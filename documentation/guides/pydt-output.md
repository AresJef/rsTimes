# Scalar output and formatting

Pydt stores microseconds. Integer output keeps those microseconds exactly;
floating seconds can lose low digits far from the epoch. Choose whether you
want clock fields measured from 1970-01-01 or the corresponding UTC instant.

## Clock coordinates and Unix timestamps

`toseconds()` and `tomicroseconds()` use local clock coordinates by default.
With `utc=True` they subtract an aware UTC offset. A naive value has no offset
to subtract. Inherited `timestamp()` follows Python's POSIX convention: an
aware input is an instant; a naive input is interpreted in the local timezone.
Use an explicit timezone when exchanging Unix timestamps.

```{doctest} pydt-epoch-output
>>> from datetime import date, datetime, time, timedelta, timezone
>>> import time as time_module
>>> from rstimes import Pydt
>>> value = Pydt(1970, 1, 1, 8, tzinfo='Asia/Shanghai')
>>> (value.toseconds(), value.toseconds(utc=True), value.timestamp())
(28800.0, 0.0, 0.0)
>>> (value.tomicroseconds(), value.tomicroseconds(utc=True))
(28800000000, 0)
>>> (type(value.toseconds()) is float, type(value.tomicroseconds()) is int)
(True, True)
>>> negative = Pydt(1969, 12, 31, 23, 59, 59, 500000)
>>> (negative.toseconds(), negative.tomicroseconds(), negative.tomicroseconds(utc=True))
(-0.5, -500000, -500000)
>>> maximum = Pydt(9999, 12, 31, 23, 59, 59, 999999)
>>> maximum.tomicroseconds()
253402300799999999
>>> for method in ('toseconds', 'tomicroseconds'):
...     for invalid in (1, None, 'true'):
...         try:
...             getattr(value, method)(utc=invalid)
...         except TypeError:
...             continue
...         raise AssertionError((method, invalid))
```

## Standard calendar containers

`timetuple` and `timedict` use local calendar fields. `utctimetuple` and
`utctimedict` use UTC fields for aware values, and leave naive clock fields
unchanged. Local `tm_isdst` is −1 for an unknown DST adjustment, 0 for zero,
and 1 for any legal nonzero adjustment. UTC output always uses 0.
The weekday is Monday=0 and the day of year is one-based.

```{doctest} pydt-calendar-output
>>> tuple(value.timetuple())
(1970, 1, 1, 8, 0, 0, 3, 1, 0)
>>> tuple(value.utctimetuple())
(1970, 1, 1, 0, 0, 0, 3, 1, 0)
>>> (type(value.timetuple()) is time_module.struct_time, type(value.utctimetuple()) is time_module.struct_time)
(True, True)
>>> keys = ('tm_year', 'tm_mon', 'tm_mday', 'tm_hour', 'tm_min', 'tm_sec', 'tm_wday', 'tm_yday', 'tm_isdst')
>>> local_fields, utc_fields = value.timedict(), value.utctimedict()
>>> (tuple(local_fields), tuple(local_fields.values()), tuple(utc_fields.values()))
(('tm_year', 'tm_mon', 'tm_mday', 'tm_hour', 'tm_min', 'tm_sec', 'tm_wday', 'tm_yday', 'tm_isdst'), (1970, 1, 1, 8, 0, 0, 3, 1, 0), (1970, 1, 1, 0, 0, 0, 3, 1, 0))
>>> assert type(local_fields) is dict and all(type(v) is int for v in local_fields.values())
>>> naive = Pydt(1970, 1, 1, 8)
>>> (naive.timetuple().tm_isdst, naive.timedict()['tm_isdst'], naive.utctimedict()['tm_isdst'])
(-1, -1, 0)
>>> (value.date(), value.time().isoformat(), value.timetz().isoformat())
(datetime.date(1970, 1, 1), '08:00:00', '08:00:00')
>>> (type(value.date()) is date, type(value.time()) is time, type(value.timetz()) is time)
(True, True, True)
>>> (value.time().tzinfo is None, value.timetz().tzinfo is value.tzinfo, value.toordinal())
(True, True, 719163)
>>> tuple(value.isocalendar())
(1970, 1, 4)
>>> value.ctime()
'Thu Jan  1 08:00:00 1970'
```

`timetz` retains the timezone object, but a regional timezone may need a date
before it can supply a UTC offset. Its string therefore need not contain an
offset. A standard fixed offset can format independently of a date.

```{doctest} pydt-time-output-offset
>>> Pydt(1970, 1, 1, 8, tzinfo=timezone(timedelta(hours=8))).timetz().isoformat()
'08:00:00+08:00'
>>> (type(Pydt.min) is datetime, type(Pydt.max) is datetime, Pydt.resolution)
(True, True, datetime.timedelta(microseconds=1))
>>> (Pydt.min.isoformat(), Pydt.max.isoformat())
('0001-01-01T00:00:00', '9999-12-31T23:59:59.999999')
```

## Text with explicit precision

Inherited `isoformat` accepts Python's separator and timespec options, and
truncates excluded clock fields. `str(value)` uses a space separator.
`strftime('%f')` writes six fractional digits. The explicit `%.1f` through
`%.9f` directives include a decimal point, truncating below six places and
padding zeros above six. `%.0f` emits nothing. Other directives follow the
platform's system formatting rules.

```{doctest} pydt-text-output
>>> fraction = Pydt(2024, 2, 29, 12, 34, 56, 123456, tzinfo='UTC')
>>> fraction.isoformat(sep=' ', timespec='milliseconds')
'2024-02-29 12:34:56.123+00:00'
>>> (str(fraction), format(fraction, ''), format(fraction, '%Y/%m/%d %H:%M:%S%.3f'))
('2024-02-29 12:34:56.123456+00:00', '2024-02-29 12:34:56.123456+00:00', '2024/02/29 12:34:56.123')
>>> fractions = ['', '.1', '.12', '.123', '.1234', '.12345', '.123456', '.1234560', '.12345600', '.123456000']
>>> for precision, expected in enumerate(fractions):
...     assert fraction.strftime('%.' + str(precision) + 'f') == expected
>>> (fraction.strftime('%f'), fraction.strftime(''), fraction.strftime('%%f'))
('123456', '', '%f')
>>> repr(Pydt(2024, 2, 29, 12, 34, 56, 123456, fold=1))
'Pydt(2024, 2, 29, 12, 34, 56, 123456, fold=1)'
>>> for call, exception in ((lambda: fraction.strftime(None), TypeError), (lambda: fraction.__format__(1), TypeError), (lambda: fraction.isoformat(timespec='nanoseconds'), ValueError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid format accepted')
```

Month and weekday names use the library's bundled CLDR data. None selects
English; a supported locale selects its language without requiring Babel at
runtime. Unsupported locales and nontext locale values are errors.

```{doctest} pydt-localized-output
>>> (fraction.month_name(), fraction.weekday_name('en_US'))
('February', 'Thursday')
>>> (fraction.month_name('fr_FR'), fraction.weekday_name('fr_FR'))
('février', 'jeudi')
>>> for method in ('month_name', 'weekday_name'):
...     for locale, exception in (('no_such_locale', ValueError), (1, TypeError)):
...         try:
...             getattr(fraction, method)(locale)
...         except exception:
...             continue
...         raise AssertionError((method, locale))
```

## Relative to the current clock

`is_past` and `is_future` compare with now, using aware instants or a naive
local clock as appropriate. Values around now can change while a program runs.
Use a margin when asserting behavior against a live clock.

```{doctest} pydt-relative-to-now
>>> for now in (Pydt.now(), Pydt.utcnow()):
...     past, future = now - timedelta(days=1), now + timedelta(days=1)
...     assert past.is_past() is True and past.is_future() is False
...     assert future.is_future() is True and future.is_past() is False
```
