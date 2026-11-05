# Delta values, batches, and persistence

Delta values are immutable. Construct a new change to choose different fields.
Calling `__init__` again leaves an already constructed value and its hash intact.
This rule also lets subclasses put business metadata in their own initializer.

```{doctest} delta-immutable-construction
>>> from rstimes import Delta
>>> value = Delta.__new__(Delta, nanoseconds=7)
>>> (type(value) is Delta, value.nanoseconds)
(True, 7)
>>> original_hash = hash(value)
>>> value.__init__(nanoseconds=999) is None
True
>>> (value.nanoseconds, hash(value) == original_hash)
(7, True)
>>> try:
...     value.nanoseconds = 9
... except AttributeError as error:
...     print(type(error).__name__)
AttributeError
```

## Equality, truth, representation, and ordering

Equal normalized values have equal hashes. Nanosecond settings participate in
equality and truth: an absolute zero setting is present, while `None` is absent.
Delta does not define an ordering by elapsed duration, because calendar months
and absolute settings need a date context. A comparison with another kind
uses normal Python reflected negotiation.

```{doctest} delta-value-protocols
>>> same = Delta(nanoseconds=1000)
>>> (same == Delta(microseconds=1), same != Delta(), hash(same) == hash(Delta(microseconds=1)))
(True, True, True)
>>> (value.__eq__(None) is NotImplemented, value.__ne__(None) is NotImplemented)
(True, True)
>>> all(getattr(value, method)(Delta()) is NotImplemented for method in ('__lt__', '__le__', '__gt__', '__ge__'))
True
>>> try:
...     value < Delta()
... except TypeError as error:
...     print(type(error).__name__)
TypeError
>>> (bool(Delta()), bool(value), bool(Delta(nanosecond=0)))
(False, True, True)
>>> (type(repr(value)) is str, 'nanoseconds=7' in repr(value), str(value) == repr(value), format(value) == str(value))
(True, True, True, True)
>>> try:
...     format(value, '.2f')
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

Use ordinary expressions for arithmetic. A direct reflected-method call is a
protocol probe: for example, a Delta on the left normally handles Delta+Delta
itself, while an explicit reflected call with another Delta returns
`NotImplemented`. Unsupported protocols can give the other operand a chance;
they are not automatic conversions into a zero Delta.

```{doctest} delta-direct-arithmetic-protocols
>>> from datetime import date, timedelta
>>> change = Delta(days=1)
>>> change.__add__(date(2024, 2, 28)) == date(2024, 2, 29)
True
>>> change.__radd__(timedelta(hours=2)) == Delta(days=1, hours=2)
True
>>> change.__sub__(timedelta(hours=2)) == Delta(hours=22)
True
>>> change.__rsub__(timedelta(hours=2)) == Delta(days=-1, hours=2)
True
>>> (change.__radd__(Delta()) is NotImplemented, change.__rsub__(Delta()) is NotImplemented)
(True, True)
>>> (-change == Delta(days=-1), abs(-change) == change)
(True, True)
```

## Process an ordered batch

`apply_many(values)` returns a Python list in input order, using the same
operation as `value + delta` for each item. It accepts an iterable, including a
one-shot generator. Result types follow the individual operands. An empty
iterable returns an empty list.

```{doctest} delta-ordered-batches
>>> from datetime import datetime
>>> operands = (item for item in (date(2024, 2, 28), datetime(2024, 2, 28, 12), timedelta(hours=2)))
>>> results = change.apply_many(operands)
>>> [type(item).__name__ for item in results]
['date', 'datetime', 'Delta']
>>> results == [date(2024, 2, 29), datetime(2024, 2, 29, 12), Delta(days=1, hours=2)]
True
>>> (change.apply_many([]), list(operands))
([], [])
```

A failing item stops the call without returning a partial list. The iterator's
consumed values and any external side effects are not rolled back. A real
business callback keeps its original exception.

```{doctest} delta-batch-callback
>>> failure = RuntimeError('business calendar unavailable')
>>> class BusinessDate(date):
...     def __add__(self, other):
...         raise failure
>>> try:
...     change.apply_many([date(2024, 1, 1), BusinessDate(2024, 1, 2)])
... except RuntimeError as error:
...     print(error is failure)
True
```

## Copy business metadata

A shallow copy is a distinct shell of the same class with shared metadata
references. A deep copy uses one memo to preserve aliases and cycles. Default
copying does not rerun the business initializer; custom copy or state hooks
keep their normal Python responsibilities and original exceptions.

```{doctest} delta-subclass-copy
>>> from copy import copy, deepcopy
>>> initializations = []
>>> class BusinessDelta(Delta):
...     def __init__(self, *, days=0):
...         initializations.append(days)
...         self.items = []
...         self.alias = self.items
...         self.loop = self
>>> business = BusinessDelta(days=1)
>>> shallow, deep = copy(business), deepcopy(business)
>>> (type(shallow) is BusinessDelta, shallow is not business, shallow.items is business.items)
(True, True, True)
>>> (type(deep) is BusinessDelta, deep.items is not business.items, deep.items is deep.alias, deep.loop is deep)
(True, True, True, True)
>>> initializations
[1]
>>> (value.__copy__() == value, value.__deepcopy__({}) == value)
(True, True)
```

See the standard-library [copy reference](https://docs.python.org/3/library/copy.html)
for memo and custom-hook conventions.

## Save and restore a value

Use `pickle` for ordinary persistence, and only load data from a trusted source.
The current default state is a four-tuple with a marker, version 2, 17 normalized
fields, and metadata. Old version 1 and old byte formats are rejected rather
than automatically migrated. `__setstate__` may restore metadata, but cannot
replace an existing immutable value with a different one.

```{doctest} delta-state-and-pickle
>>> import pickle
>>> state = value.__getstate__()
>>> (state[0], state[1], len(state[2]), state[2][:8])
('rstimes.delta', 2, 17, (0, 0, 0, 0, 0, 0, 0, 7))
>>> value.__setstate__(state) is None
True
>>> restored = pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
>>> (type(restored) is Delta, restored == value, restored is not value)
(True, True, True)
>>> for recipe in (value.__reduce__(), value.__reduce_ex__(pickle.HIGHEST_PROTOCOL)):
...     assert type(recipe) is tuple and callable(recipe[0])
...     assert recipe[0](*recipe[1]) == value
>>> try:
...     value.__setstate__(Delta(days=1).__getstate__())
... except ValueError as error:
...     print(type(error).__name__, value.nanoseconds)
ValueError 7
>>> try:
...     value.__setstate__((state[0], 1, state[2], state[3]))
... except ValueError as error:
...     print(type(error).__name__)
ValueError
```

The binary reconstruction payload uses a defined little-endian encoding rather
than the Rust memory layout. Treat reconstruction recipes as opaque. Applications
with their own business-state protocol control that protocol; the default
format is not imposed on a user-defined state mapping.
