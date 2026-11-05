# Choose a Pldt output representation

Date transformations return Pldt. Numeric, text, Date, Time, and local Datetime
queries return ordinary Polars Series with native nulls. Time-field tables are
DataFrames. Explicit Python object exits have their own precision and year
limits; they are available for eager columns, rather than Expr.

## Native numbers and temporal columns

`toseconds` returns Float64 local wall-clock seconds by default; `utc=True` uses
aware instants. `tomicroseconds` returns Int64 and floors nanoseconds at this
explicit output. `timestamp` returns Unix instant seconds, interpreting a naive
source in the process-local zone. Floats do not preserve every distant
nanosecond; retain integer physical ticks plus the unit and null bitmap for an
exact interchange.

```{doctest} pldt-native-output-roles
>>> from datetime import time, timezone
>>> from zoneinfo import ZoneInfo
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt, Pydt
>>> source = Pldt(['1970-01-01T08:00:00.000000999', None], tz='Asia/Shanghai', name='event')
>>> outputs = [
...     ('toseconds', (), pl.Float64, 28800.000000999),
...     ('toseconds', (True,), pl.Float64, 0.000000999),
...     ('tomicroseconds', (), pl.Int64, 28800000000),
...     ('tomicroseconds', (True,), pl.Int64, 0),
...     ('timestamp', (), pl.Float64, 0.000000999),
...     ('toordinal', (), pl.Int64, 719163),
...     ('ctime', (), pl.String, 'Thu Jan  1 08:00:00 1970'),
...     ('month_name', (), pl.String, 'January'),
...     ('weekday_name', ('fr_FR',), pl.String, 'jeudi'),
...     ('tzname', (), pl.String, 'CST'),
... ]
>>> for owner in (source, pl.Series(source).pldt):
...     for method, arguments, dtype, expected in outputs:
...         result = getattr(owner, method)(*arguments)
...         assert type(result) is pl.Series and result.dtype == dtype and result.name == 'event'
...         assert result.to_list() == [expected, None]
...     for attribute, dtype, expected in [('values_naive', pl.Datetime('ns'), 28800000000999), ('date', pl.Date, 0), ('time', pl.Time, 28800000000999)]:
...         result = getattr(owner, attribute)
...         assert type(result) is pl.Series and result.dtype == dtype
...         assert result.to_physical().to_list() == [expected, None]
>>> Pldt([-1, None], unit='ns').tomicroseconds().to_list()
[-1, None]
>>> Pldt(['2024-01-01', '2024-07-01', None], tz='America/New_York').tzname().to_list()
['EST', 'EDT', None]
>>> Pldt(['2024-01-01', None]).tzname().to_list()
[None, None]
>>> for unit, scale in [('ms', 1000), ('us', 1000000), ('ns', 1000000000)]:
...     assert Pldt([1, -1, None], unit=unit).toseconds().to_list() == [1 / scale, -1 / scale, None]
>>> for action, error in [(lambda: source.toseconds(1), TypeError), (lambda: source.tomicroseconds(None), TypeError), (lambda: Pldt([2**63 - 1], unit='ms').tomicroseconds(), OverflowError), (lambda: Pldt([2**63 - 1], unit='ms').date, OverflowError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('an output exceeded its representation contract')
```

## Fixed-schema time tables

Local and UTC tables contain nine native integer columns. Every child is null
for a source null. `tm_isdst` is −1 for an unspecified local adjustment, 0 for
zero, and 1 for a legal nonzero adjustment. UTC tables always use 0. Naive UTC
table fields do not move.

```{doctest} pldt-time-table-output
>>> keys = ['tm_year', 'tm_mon', 'tm_mday', 'tm_hour', 'tm_min', 'tm_sec', 'tm_wday', 'tm_yday', 'tm_isdst']
>>> dtypes = [pl.Int64, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int8, pl.Int16, pl.Int8]
>>> for owner in (source, pl.Series(source).pldt):
...     local, utc = owner.timedf(), owner.utctimedf()
...     assert type(local) is pl.DataFrame and type(utc) is pl.DataFrame
...     assert local.schema == utc.schema == dict(zip(keys, dtypes))
...     assert local.row(0) == (1970, 1, 1, 8, 0, 0, 3, 1, 0)
...     assert utc.row(0) == (1970, 1, 1, 0, 0, 0, 3, 1, 0)
...     assert local.row(1) == utc.row(1) == (None,) * 9
>>> naive = Pldt(['1970-01-01', None])
>>> (naive.timedf()['tm_isdst'].to_list(), naive.utctimedf()['tm_isdst'].to_list())
([-1, None], [0, None])
>>> for method in ('timedf', 'utctimedf'):
...     empty = getattr(Pldt([]), method)()
...     assert empty.shape == (0, 9) and empty.schema == dict(zip(keys, dtypes))
```

## Text display and locale

ISO auto display emits a nonzero nanosecond tail with nine digits, an exact
microsecond fraction with six, and no fraction for a whole second. Explicit
timespecs truncate only the text. A separator is one Unicode character.
`strftime('%f')` emits nine digits at ns storage and six at ms/us. Its explicit
`%.0f`–`%.9f` forms omit or include a dot with the requested precision.
Month/weekday names use the bundled CLDR data, independently of Configs parsing
vocabulary.

```{doctest} pldt-text-output
>>> fraction = Pldt([123456789, None], unit='ns', name='event')
>>> specs = {'auto': '00:00:00.123456789', 'hours': '00', 'h': '00', 'minutes': '00:00', 'm': '00:00', 'min': '00:00', 'seconds': '00:00:00', 's': '00:00:00', 'milliseconds': '00:00:00.123', 'ms': '00:00:00.123', 'microseconds': '00:00:00.123456', 'us': '00:00:00.123456', 'nanoseconds': '00:00:00.123456789', 'ns': '00:00:00.123456789'}
>>> for owner in (fraction, pl.Series(fraction).pldt):
...     for timespec, clock in specs.items():
...         result = owner.isoformat(sep='日', timespec=timespec)
...         assert type(result) is pl.Series and result.dtype == pl.String and result.name == 'event'
...         assert result.to_list() == ['1970-01-01日' + clock, None]
...     assert [owner.strftime('%.' + str(p) + 'f')[0] for p in range(10)] == ['', '.1', '.12', '.123', '.1234', '.12345', '.123456', '.1234567', '.12345678', '.123456789']
>>> for unit, tick, expected in [('ms', 123, '123000'), ('us', 123456, '123456'), ('ns', 123456789, '123456789')]:
...     assert Pldt([tick], unit=unit).strftime('%f').to_list() == [expected]
>>> fraction.strftime('%%f|%.3f|%.9f|%.0f').to_list()
['%f|.123|.123456789|', None]
>>> (source.month_name('zh_CN').to_list(), source.weekday_name('fr_FR').to_list())
(['一月', None], ['jeudi', None])
>>> for action, error in [(lambda: fraction.isoformat(sep=''), ValueError), (lambda: fraction.isoformat(timespec='bad'), ValueError), (lambda: fraction.strftime(None), TypeError), (lambda: fraction.month_name('no_such_locale'), ValueError), (lambda: fraction.weekday_name(1), TypeError)]:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('invalid display option was accepted')
```

## Explicit Python objects

`datetime()` returns an object ndarray of Pydt or None. The `timetz` property
returns standard-library time objects or None. Both intentionally truncate to
microseconds and preserve regional fold. Native `time` above retains all nine
fraction digits. Python datetime years must fit 1–9999; a native clock-only Time
or Python time can still represent a broad date's clock.

```{doctest} pldt-python-object-output
>>> repeated = Pldt(['2024-11-03T01:30:00.123456789', None], tz='America/New_York', ambiguous=False)
>>> for owner in (repeated, pl.Series(repeated).pldt):
...     objects, clocks = owner.datetime(), owner.timetz
...     assert type(objects) is np.ndarray and objects.dtype == object
...     assert type(objects[0]) is Pydt and objects[1] is None
...     assert objects[0].fold == 1 and objects[0].microsecond == 123456
...     assert objects[0].tzinfo == ZoneInfo('America/New_York')
...     assert type(clocks[0]) is time and clocks[0].fold == 1 and clocks[1] is None
>>> (repeated.nanosecond.to_list(), repeated.time.to_physical().to_list())
([789, None], [5400123456789, None])
>>> Pldt([0], tz=ZoneInfo('UTC')).datetime()[0].tzinfo is timezone.utc
True
>>> for tick in (-2**63, 2**63 - 1):
...     broad = Pldt([tick], unit='us')
...     try:
...         broad.datetime()
...     except OverflowError:
...         pass
...     else:
...         raise AssertionError('Python year capacity was exceeded')
...     assert type(broad.timetz[0]) is time
...     assert broad.time.to_physical()[0] == (tick * 1000) % 86400000000000
>>> (hasattr(pl.col('event').pldt, 'datetime'), hasattr(pl.col('event').pldt, 'timetz'))
(False, False)
```

## NumPy export and dtype conversion

Default NumPy output retains unit and instants but cannot distinguish a valid
minimum tick from NaT. The default rejects that collision. The explicit
`allow_nat_collision=True` option permits only that loss. It does not permit
rounding, overflow, or erasing other missing positions. `__array__` has no such
collision opt-in.

Native dtype changes must preserve values and missingness. Finer subnanosecond
destinations are allowed when every actual date fits. Y/M destinations must
preserve the exact calendar value. `copy=False` forbids a required cast; normal
`to_numpy` flags follow Polars' export protocol.

```{doctest} pldt-numpy-output-contract
>>> for unit in ('ms', 'us', 'ns'):
...     minimum = Pldt([-2**63, None, 0], unit=unit)
...     for export in (minimum.to_numpy, lambda: np.asarray(minimum), lambda: np.array(minimum)):
...         try:
...             export()
...         except OverflowError:
...             continue
...         raise AssertionError('valid minimum was silently turned into NaT')
...     lossy = minimum.to_numpy(allow_nat_collision=True)
...     assert lossy.dtype == np.dtype(f'datetime64[{unit}]')
...     assert np.isnat(lossy).tolist() == [True, True, False]
...     assert minimum.is_null().to_list() == [False, True, False]
>>> ordinary = Pldt([0, 1], unit='us')
>>> (ordinary.to_numpy().flags.writeable, ordinary.to_numpy(writable=True).flags.writeable)
(False, True)
>>> np.asarray(ordinary, dtype='datetime64[ns]').view('int64').tolist()
[0, 1000]
>>> np.array(ordinary, copy=True).flags.writeable
True
>>> for unit, multiplier in [('ps', 1000), ('fs', 1000000), ('as', 1000000000)]:
...     converted = np.asarray(Pldt([0, 1, None], unit='ns'), dtype=f'datetime64[{unit}]')
...     assert converted.view('int64').tolist() == [0, multiplier, -2**63]
>>> for dtype in ('datetime64[Y]', 'datetime64[M]', 'datetime64[D]'):
...     exact = np.asarray(Pldt(['1970-01-01', None]), dtype=dtype)
...     assert exact.view('int64').tolist() == [0, -2**63]
>>> invalid = [
...     (lambda: ordinary.__array__(np.dtype('datetime64[ns]'), copy=False), RuntimeError),
...     (lambda: np.asarray(Pldt([1], unit='ns'), dtype='datetime64[us]'), ValueError),
...     (lambda: np.asarray(Pldt([0, None], unit='us'), dtype='int64'), ValueError),
...     (lambda: np.asarray(Pldt(['2500-01-01'], unit='us'), dtype='datetime64[ns]'), OverflowError),
...     (lambda: np.asarray(Pldt([2**63 - 1], unit='ns'), dtype='float64'), ValueError),
...     (lambda: np.asarray(Pldt(['2024-01-01']), dtype='datetime64[ps]'), OverflowError),
...     (lambda: Pldt([0]).to_numpy(allow_nat_collision=1), TypeError),
... ]
>>> for action, error in invalid:
...     try:
...         action()
...     except error:
...         continue
...     raise AssertionError('unsafe NumPy conversion was accepted')
>>> calls = []
>>> class ApplicationExit(Pldt):
...     def to_numpy(self, **options):
...         calls.append(options)
...         return np.array([7, 8])
>>> np.asarray(ApplicationExit([0, 1]), dtype=float).tolist()
[7.0, 8.0]
>>> len(calls)
1
```

A genuine application override owns its return. Neutral attribute forwarding
does not remove the library export's precision and validity checks. For a
lossless pandas target with valid minimum ticks, use the Arrow-backed options in
[pandas and Arrow exchange](pldt-pandas-arrow.md).
