# Inherited pandas protocols and unsupported operations

Pddt inherits pandas' vector comparisons, NumPy dispatch and Index container
protocols. Availability of a Python method name does not mean every dtype
supports its operation. Numeric multiplication, division, powers, bitwise
operations and unary numeric operators are not date transformations. The
examples below exercise each exposed protocol and assert its native error.
See [pandas Index](https://pandas.pydata.org/pandas-docs/stable/reference/indexing.html)
for the complete provider interface.

## Vector comparisons

Comparisons return NumPy Boolean arrays. A missing date compares False for
ordered/equality comparisons and True for inequality in these profiles.
Use an explicit aware timestamp when comparing an aware index.

```{doctest} inherited-pddt-comparison-protocols
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt
>>> value = Pddt(['2024-01-01', '2024-01-02', '2024-01-03', None], unit='ns', tz='UTC', name='event')
>>> middle = pd.Timestamp('2024-01-02', tz='UTC')
>>> comparisons = {
...     '__eq__': [False, True, False, False], '__ne__': [True, False, True, True],
...     '__lt__': [True, False, False, False], '__le__': [True, True, False, False],
...     '__gt__': [False, False, True, False], '__ge__': [False, True, True, False],
... }
>>> for method, expected in comparisons.items():
...     result = getattr(value, method)(middle)
...     assert type(result) is np.ndarray and result.dtype == np.dtype('bool')
...     assert result.tolist() == expected
```

## NumPy dispatch and reflected date subtraction

`np.asarray` invokes the inherited array protocol. Supplying a datetime dtype
preserves the requested precision but drops timezone metadata after conversion
to UTC. NumPy comparisons and date arithmetic dispatch through
`__array_ufunc__`. In these verified cases, adding an elapsed day produces Pddt,
while subtracting a date produces an ordinary pandas TimedeltaIndex. Timedelta
integer values use that result's actual `unit`.

Reflected subtraction, `timestamp - value`, has the provider's TimedeltaIndex
result; it does not call the rsTimes `diff` method or return Delta objects.
`+=` rebinds an index variable to a new date result; the original immutable
index and aliases retain their dates.

```{doctest} inherited-pddt-array-protocols
>>> original_ticks = [1704067200000000000, 1704153600000000000, 1704240000000000000, -9223372036854775808]
>>> array = np.asarray(value, dtype='datetime64[ns]')
>>> (type(array) is np.ndarray, str(array.dtype), array.view('i8').tolist() == original_ticks)
(True, 'datetime64[ns]', True)
>>> np.equal(value, middle).tolist()
[False, True, False, False]
>>> added = np.add(value, np.timedelta64(1, 'D'))
>>> (type(added) is Pddt, added.unit, str(added.tz), added.name, added.asi8.tolist())
(True, 'ns', 'UTC', 'event', [1704153600000000000, 1704240000000000000, 1704326400000000000, -9223372036854775808])
>>> elapsed = np.subtract(value, middle)
>>> (type(elapsed) is pd.TimedeltaIndex, elapsed.unit, elapsed.asi8.tolist())
(True, 'ns', [-86400000000000, 0, 86400000000000, -9223372036854775808])
>>> reverse = value.__rsub__(pd.Timestamp('2024-01-04', tz='UTC'))
>>> (type(reverse) is pd.TimedeltaIndex, reverse.unit, reverse.asi8.tolist(), reverse.name)
(True, 'ns', [259200000000000, 172800000000000, 86400000000000, -9223372036854775808], 'event')
>>> rebound = value
>>> rebound += pd.Timedelta(days=1)
>>> (type(rebound) is Pddt, rebound.asi8.tolist() == added.asi8.tolist(), value.asi8.tolist() == original_ticks)
(True, True, True)
```

## Explicitly unsupported numeric and Boolean roles

Each method below is exercised on Pddt. TypeError is the expected native result,
including the reflected protocols with an integer left operand. For Boolean
row selection, use an explicit mask. For date arithmetic, use a documented
calendar or elapsed-time operand; raw numeric operators are not a substitute.
The string accessor is likewise unavailable for a date dtype.

```{doctest} inherited-pddt-unsupported-protocols
>>> def error_name(call):
...     try:
...         call()
...     except Exception as error:
...         return type(error).__name__
...     raise AssertionError('an error was required')
>>> for method in ('__abs__', '__neg__', '__pos__', '__invert__'):
...     assert error_name(lambda: getattr(value, method)()) == 'TypeError'
>>> unsupported_binary = (
...     '__and__', '__or__', '__xor__', '__rand__', '__ror__', '__rxor__',
...     '__truediv__', '__rtruediv__', '__floordiv__', '__rfloordiv__',
...     '__mod__', '__rmod__', '__divmod__', '__rdivmod__',
...     '__pow__', '__rpow__', '__mul__', '__rmul__',
... )
>>> for method in unsupported_binary:
...     assert error_name(lambda: getattr(value, method)(2)) == 'TypeError'
>>> (error_name(value.all), error_name(value.any), error_name(lambda: value.str))
('TypeError', 'TypeError', 'AttributeError')
>>> error_name(lambda: np.multiply(value, 2))
'TypeError'
>>> (error_name(lambda: bool(value)), error_name(lambda: bool(Pddt([]))), error_name(lambda: hash(value)))
('ValueError', 'ValueError', 'TypeError')
```

An Index has no scalar truth value, including an empty Index, and is unhashable.
Use `empty`, `len`, `isna`, `isin` or a comparison mask according to the task.
The disabled `__hash__` is a protocol boundary, not a callable hash method.

## Display protocols

Display formatting follows pandas and can vary across dependency releases.
`repr`, `str` and the empty `format` specification return strings identifying
Pddt, the values, the missing row and date metadata. A nonempty numeric format
specification is not supported. Use rsTimes strftime for a date format.

```{doctest} inherited-pddt-display-protocols
>>> display = repr(value)
>>> (type(display) is str, 'Pddt(' in display, '2024-01-01' in display, 'NaT' in display, 'datetime64[ns, UTC]' in display, "name='event'" in display)
(True, True, True, True, True, True)
>>> (str(value) == display, format(value, '') == display)
(True, True)
>>> error_name(lambda: format(value, '.2f'))
'TypeError'
```
