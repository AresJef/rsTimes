# Scalar boundaries, rounding, and differences

Choose a calendar day with `to_first_of` / `to_last_of`, retaining the clock.
Choose a period's first or last representable local time with `to_start_of` /
`to_end_of`. `normalize` finds the first existing time within the current date.
Their corresponding `is_*` methods use the same definitions.

## Calendar days and exact period boundaries

```{doctest} pydt-first-last-days
>>> from datetime import timedelta
>>> from rstimes import Pydt
>>> source = Pydt(2024, 2, 29, 12, 34, 56, 123456, tzinfo='UTC')
>>> cases = [('Y', '2024-01-01', '2024-12-31'), ('Q', '2024-01-01', '2024-03-31'), ('M', '2024-02-01', '2024-02-29'), ('W', '2024-02-26', '2024-03-03'), ('January', '2024-01-01', '2024-01-31')]
>>> for unit, first, last in cases:
...     a, b = source.to_first_of(unit), source.to_last_of(unit)
...     assert type(a) is Pydt and type(b) is Pydt
...     assert a.date().isoformat() == first and b.date().isoformat() == last
...     assert (a.hour, a.minute, a.second, a.microsecond) == (12, 34, 56, 123456)
...     assert (b.hour, b.minute, b.second, b.microsecond) == (12, 34, 56, 123456)
...     assert a.is_first_of(unit) is True and b.is_last_of(unit) is True
>>> (source.is_last_of('M'), source.is_end_of('M'))
(True, False)
```

For exact boundaries, Pydt's final tick is one microsecond. The `ns` unit here
is an existing alias for an unchanged microsecond value, rather than a new
nanosecond representation.

```{doctest} pydt-start-end-boundaries
>>> periods = [
...     ('Y', '2024-01-01T00:00:00', '2024-12-31T23:59:59.999999'),
...     ('Q', '2024-01-01T00:00:00', '2024-03-31T23:59:59.999999'),
...     ('M', '2024-02-01T00:00:00', '2024-02-29T23:59:59.999999'),
...     ('W', '2024-02-26T00:00:00', '2024-03-03T23:59:59.999999'),
...     ('D', '2024-02-29T00:00:00', '2024-02-29T23:59:59.999999'),
...     ('h', '2024-02-29T12:00:00', '2024-02-29T12:59:59.999999'),
...     ('m', '2024-02-29T12:34:00', '2024-02-29T12:34:59.999999'),
...     ('s', '2024-02-29T12:34:56', '2024-02-29T12:34:56.999999'),
...     ('ms', '2024-02-29T12:34:56.123000', '2024-02-29T12:34:56.123999'),
...     ('us', '2024-02-29T12:34:56.123456', '2024-02-29T12:34:56.123456'),
...     ('ns', '2024-02-29T12:34:56.123456', '2024-02-29T12:34:56.123456'),
...     ('Monday', '2024-02-26T00:00:00', '2024-02-26T23:59:59.999999'),
... ]
>>> for unit, start, end in periods:
...     a, b = source.to_start_of(unit), source.to_end_of(unit)
...     assert type(a) is Pydt and type(b) is Pydt
...     assert a.isoformat() == start + '+00:00' and b.isoformat() == end + '+00:00'
...     assert a.is_start_of(unit) is True and b.is_end_of(unit) is True
>>> (source.to_start_of('us') is source, source.to_end_of('ns') is source)
(True, True)
>>> source.normalize().isoformat()
'2024-02-29T00:00:00+00:00'
```

Regional midnight can be missing. In São Paulo on 2018-11-04, normalization
finds 01:00 within that date rather than borrowing the previous date.

```{doctest} pydt-missing-midnight
>>> regional = Pydt(2018, 11, 4, 12, tzinfo='America/Sao_Paulo')
>>> (regional.normalize().isoformat(), regional.to_start_of('D').isoformat())
('2018-11-04T01:00:00-02:00', '2018-11-04T01:00:00-02:00')
>>> regional.normalize().is_start_of('D')
True
```

## Round clock fields or snap to a period start

`round(freq)` uses ties to even. `floor` chooses an aligned result no later
than the input and `ceil` one no earlier. They accept single D/h/m/min/s/ms/us
units and the existing ns alias. Multi-frequency forms such as `15min` are
unsupported.

`snap(unit)` instead chooses the nearest existing period start, measuring
aware distances as actual instants. A tie chooses the later start. It also
accepts Y/Q/M/W and stored month/weekday names. It can skip wholly missing
periods; it does not manufacture a missing boundary.

```{doctest} pydt-rounding-and-snap
>>> middle = Pydt(2024, 1, 2, 12, 30, tzinfo='UTC')
>>> (middle.round('h').hour, middle.snap('h').hour, middle.floor('h').hour, middle.ceil('h').hour)
(12, 13, 12, 13)
>>> (Pydt(2024, 1, 2, 13, 30).round('h').hour, Pydt(2024, 1, 2, 12, 0, 0, 500000).round('s').second)
(14, 0)
>>> expectations = [('D', '2024-03-01T00:00:00', '2024-02-29T00:00:00'), ('h', '2024-02-29T13:00:00', '2024-02-29T12:00:00'), ('min', '2024-02-29T12:35:00', '2024-02-29T12:34:00'), ('s', '2024-02-29T12:34:57', '2024-02-29T12:34:56'), ('ms', '2024-02-29T12:34:56.124000', '2024-02-29T12:34:56.123000')]
>>> for unit, upper, lower in expectations:
...     assert source.ceil(unit).isoformat() == upper + '+00:00'
...     assert source.floor(unit).isoformat() == lower + '+00:00'
...     assert type(source.round(unit)) is Pydt
>>> rounded = [('D', '2024-03-01T00:00:00'), ('h', '2024-02-29T13:00:00'), ('m', '2024-02-29T12:35:00'), ('min', '2024-02-29T12:35:00'), ('s', '2024-02-29T12:34:56'), ('ms', '2024-02-29T12:34:56.123000'), ('us', '2024-02-29T12:34:56.123456'), ('ns', '2024-02-29T12:34:56.123456')]
>>> for unit, expected in rounded:
...     assert source.round(unit).isoformat() == expected + '+00:00'
>>> (source.snap('Monday').isoformat(), source.snap('February').isoformat())
('2024-03-04T00:00:00+00:00', '2024-02-01T00:00:00+00:00')
>>> negative = Pydt(1969, 12, 31, 23, 59, 59, 500000)
>>> (negative.floor('s').isoformat(), negative.ceil('s').isoformat(), negative.round('s').isoformat())
('1969-12-31T23:59:59', '1970-01-01T00:00:00', '1970-01-01T00:00:00')
>>> try:
...     source.round('15min')
... except ValueError as error:
...     print(type(error).__name__)
ValueError
```

`fsp(precision)` truncates fractional decimal places. It does not round. Values
at six or more places leave the microsecond scalar unchanged; a negative
precision is invalid. Precision itself uses the integer index protocol.

```{doctest} pydt-fractional-precision
>>> [source.fsp(precision).microsecond for precision in (0, 1, 2, 3, 4, 5, 6, 9)]
[0, 100000, 120000, 123000, 123400, 123450, 123456, 123456]
>>> for precision, expected in ((-1, ValueError), (1.0, TypeError), (True, TypeError)):
...     try:
...         source.fsp(precision)
...     except expected:
...         continue
...     raise AssertionError(precision)
```

## Count crossed boundaries

`self.diff(other, unit)` computes self's unit bucket minus the other's. It is
not the elapsed duration divided by a unit length. `inclusive='one'` keeps
that difference; `both` adds one to its magnitude and `neither` subtracts one.
With equal boundaries, absolute=True and neither can therefore return −1.
Aware operands are compared using their UTC instant coordinates; mixing naive
and aware values is an error.

```{doctest} pydt-boundary-diff
>>> late, early = Pydt(2024, 2, 1), Pydt(2024, 1, 31, 23, 59, 59)
>>> (late - early, late.diff(early, 'D'), late.diff(early, 'M'))
(datetime.timedelta(seconds=1), 1, 1)
>>> (late.diff(early, 'D', inclusive='both'), late.diff(early, 'D', inclusive='neither'), early.diff(late, 'D'))
(2, 0, -1)
>>> (early.diff(late, 'D', absolute=True), late.diff(late, 'D', absolute=True, inclusive='neither'))
(1, -1)
>>> expected_units = {'Y': 0, 'Q': 0, 'M': 1, 'W': 0, 'D': 1, 'h': 1, 'm': 1, 'min': 1, 's': 1, 'ms': 1000, 'us': 1000000}
>>> for unit, expected in expected_units.items():
...     result = late.diff(early, unit)
...     assert type(result) is int and result == expected
>>> a, b = Pydt(1970, 1, 1, tzinfo='UTC'), Pydt(1970, 1, 1, 8, tzinfo='Asia/Shanghai')
>>> a.diff(b, 'h')
0
>>> for call, expected in ((lambda: a.diff(late, 'D'), TypeError), (lambda: late.diff(early, 'ns'), ValueError), (lambda: late.diff(early, 'D', absolute=1), TypeError), (lambda: late.diff(early, 'D', inclusive='unknown'), ValueError)):
...     try:
...         call()
...     except expected:
...         continue
...     raise AssertionError('invalid diff option accepted')
```

Unknown or empty period names raise ValueError; unsupported name types raise
TypeError. A legitimate nonmatch in a boundary query returns False. For elapsed
datetime subtraction and fold, see [scalar timezones](pydt-timezones.md).

```{doctest} pydt-boundary-invalid-inputs
>>> for method in ('to_first_of', 'to_last_of', 'to_start_of', 'to_end_of', 'is_first_of', 'is_last_of', 'is_start_of', 'is_end_of', 'snap'):
...     for argument, exception in (('', ValueError), ('unknown', ValueError), (None, TypeError), (True, TypeError)):
...         try:
...             getattr(source, method)(argument)
...         except exception:
...             continue
...         raise AssertionError((method, argument))
>>> (source.is_first_of('M'), source.is_start_of('D'))
(False, False)
```
