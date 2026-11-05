# Scalar operators, subclasses, and saved state

Ordinary datetime comparisons and hashing retain Python's rules. In particular,
two aware values sharing the same timezone object compare their wall clocks,
including the standard treatment of fold. See the concrete repeated-hour
example in [scalar timezones](pydt-timezones.md).

## Comparisons and operator negotiation

```{doctest} pydt-comparison-protocols
>>> from datetime import date, datetime, timedelta, timezone
>>> from rstimes import Pydt, Delta
>>> value = Pydt(2024, 1, 1)
>>> other = datetime(2024, 1, 2)
>>> (value == datetime(2024, 1, 1), value != other, value < other, value <= other, other > value, other >= value)
(True, True, True, True, True, True)
>>> for method, expected in (('__eq__', False), ('__ne__', True), ('__lt__', True), ('__le__', True), ('__gt__', False), ('__ge__', False)):
...     assert getattr(value, method)(other) is expected
...     assert getattr(value, method)(object()) is NotImplemented
>>> (hash(value) == hash(datetime(2024, 1, 1)), value.__hash__() == hash(value))
(True, True)
>>> try:
...     value < object()
... except TypeError as error:
...     print(type(error).__name__)
TypeError
>>> aware = Pydt(2024, 1, 1, tzinfo='UTC')
>>> (value == aware, value != aware)
(False, True)
>>> try:
...     value < aware
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

Adding a supported duration returns Pydt. Subtracting a date returns a standard
`timedelta`; subtracting a duration returns a date. A calendar Delta uses its
own relative and absolute fields. Unsupported operands return NotImplemented
from a direct special-method call so Python can try the other operand.

```{doctest} pydt-arithmetic-protocols
>>> (value + timedelta(days=1)).isoformat()
'2024-01-02T00:00:00'
>>> (timedelta(days=1) + value).isoformat()
'2024-01-02T00:00:00'
>>> value.__radd__(timedelta(hours=1)).isoformat()
'2024-01-01T01:00:00'
>>> (value - timedelta(microseconds=1)).isoformat()
'2023-12-31T23:59:59.999999'
>>> [(type(result) is timedelta, result.total_seconds()) for result in (other - value, value.__rsub__(other), value - date(2024, 1, 1), value - '2024-01-01')]
[(True, 86400.0), (True, 86400.0), (True, 0.0), (True, 0.0)]
>>> (Pydt(2024, 1, 31) + Delta(months=1)).isoformat()
'2024-02-29T00:00:00'
>>> (Pydt(2024, 1, 31) - Delta(months=1)).isoformat()
'2023-12-31T00:00:00'
>>> (value.__add__(object()) is NotImplemented, value.__radd__(object()) is NotImplemented, value.__sub__('not a date') is NotImplemented)
(True, True, True)
>>> class RightOperand:
...     def __radd__(self, left):
...         return ('negotiated', left.year)
>>> value + RightOperand()
('negotiated', 2024)
>>> try:
...     Pydt(9999, 12, 31) + timedelta(days=1)
... except OverflowError as error:
...     print(type(error).__name__)
OverflowError
```

## Immutable date fields and mutable application metadata

Date fields are established by `__new__`. The inherited initializer cannot
replace those immutable fields. A normal subclass may add dictionary or slot
attributes; calendar operations retain the appropriate date subtype. A shallow
copy shares metadata references, while a deep copy preserves aliases and cycles
through its memo. Application initializers are not rerun during ordinary copy.

```{doctest} pydt-subclass-copy
>>> value.__init__(2025, 2, 3) is None
True
>>> value.isoformat()
'2024-01-01T00:00:00'
>>> from copy import copy, deepcopy
>>> initializations = []
>>> class Annotated(Pydt):
...     __slots__ = ('label',)
...     def __init__(self, *args, **kwargs):
...         initializations.append(1)
...         self.label = ['source']
...         self.info = {'self': self}
>>> source = Annotated(2024, 2, 29, 12, tzinfo='UTC', fold=1)
>>> selected = source.to_month(1)
>>> (type(selected) is Annotated, selected.isoformat())
(True, '2024-03-29T12:00:00+00:00')
>>> before_copy = len(initializations)
>>> shallow, deep = copy(source), deepcopy(source)
>>> (type(shallow) is Annotated, shallow is not source, shallow.label is source.label, shallow.info is source.info)
(True, True, True, True)
>>> (type(deep) is Annotated, deep is not source, deep.label is not source.label, deep.info is not source.info, deep.info['self'] is deep)
(True, True, True, True, True)
>>> (shallow.fold, deep.fold, len(initializations) == before_copy)
(1, 1, True)
>>> memo = {}
>>> again = deepcopy(source, memo)
>>> memo[id(source)] is again
True
```

## Save date fields separately from metadata

The default pickle recipe reconstructs the date, timezone, and fold before
restoring dictionary and slot metadata. `__getstate__` is inherited from object
and describes metadata, not the immutable date. Treat the reconstruction recipe
as opaque; old Cython pickle formats are unsupported. Only load trusted pickle
data.

```{doctest} pydt-state-and-pickle
>>> import pickle
>>> plain = Pydt(2024, 11, 3, 1, 20, 30, 123456, tzinfo='America/New_York', fold=1)
>>> plain.items = [1, 2]
>>> plain.loop = plain
>>> plain.__getstate__()['items']
[1, 2]
>>> source.__getstate__()[1]['label']
['source']
>>> for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
...     restored = pickle.loads(pickle.dumps(plain, protocol=protocol))
...     assert type(restored) is Pydt and restored is not plain
...     assert restored.isoformat() == '2024-11-03T01:20:30.123456-05:00'
...     assert restored.fold == 1 and restored.loop is restored
...     assert restored.items == [1, 2] and restored.items is not plain.items
>>> for recipe in (plain.__reduce__(), plain.__reduce_ex__(4)):
...     assert type(recipe) is tuple and len(recipe) == 3 and callable(recipe[0])
...     rebuilt = recipe[0](*recipe[1])
...     assert type(rebuilt) is Pydt and rebuilt.isoformat() == plain.isoformat() and rebuilt.fold == 1
...     assert rebuilt.__setstate__(recipe[2]) is None
...     assert rebuilt.items is plain.items
>>> target = Pydt(2024, 1, 1)
>>> target.__setstate__({'label': 'restored'}) is None
True
>>> (target.label, target.isoformat(), target.__setstate__(None))
('restored', '2024-01-01T00:00:00', None)
>>> source.__setstate__(({'note': 'dictionary'}, {'label': ['slot']})) is None
True
>>> (source.note, source.label, source.year)
('dictionary', ['slot'], 2024)
>>> for invalid in ([], {1: 'bad key'}, ({}, [])):
...     try:
...         target.__setstate__(invalid)
...     except TypeError:
...         continue
...     raise AssertionError(invalid)
>>> try:
...     target.__setstate__((None, {'year': 2000}))
... except AttributeError as error:
...     print(type(error).__name__, target.year)
AttributeError 2024
```

`__setstate__` validates metadata container shapes before assignments. A later
application setter can still raise after earlier metadata assignments; it is
not a transaction over arbitrary user code. Real business hooks keep their own
return values and exception objects.

```{doctest} pydt-original-business-error
>>> marker = RuntimeError('application formatting failed')
>>> class BusinessDate(Pydt):
...     def strftime(self, spec):
...         raise marker
>>> try:
...     format(BusinessDate(2024, 1, 1), '%Y')
... except RuntimeError as caught:
...     print(caught is marker)
True
```

The [datetime reference](https://docs.python.org/3/library/datetime.html),
[copy reference](https://docs.python.org/3/library/copy.html), and
[pickle reference](https://docs.python.org/3/library/pickle.html) describe the
standard protocols used here. Additional NumPy, pandas, and dateutil operand
roles are covered in [scalar interoperability](pydt-interop.md).
