# Inherited Delta protocols

These protocols are available on a Delta through Python's object model. Delta's
calendar value does not add a duration ordering or a numeric format language.
For value equality, hashing, arithmetic, copying, and state, use the
[Delta reference](reference/rstimes/delta/index.rst).

| Entry | Parameters and result | Boundary |
|---|---|---|
| <span id="rstimes.Delta.__str__"></span>`Delta.__str__()` | No arguments; returns `str` using the Delta representation. | Does not produce a parsable serialization contract. |
| <span id="rstimes.Delta.__format__"></span>`Delta.__format__(format_spec)` | A string format specification; the empty string returns the ordinary string. | A nonempty numeric specification raises `TypeError`. |
| <span id="rstimes.Delta.__lt__"></span>`Delta.__lt__(other)` | An arbitrary other operand; direct call returns `NotImplemented` on ordinary Deltas. | `a < b` raises `TypeError` if reflected negotiation also declines. |
| <span id="rstimes.Delta.__le__"></span>`Delta.__le__(other)` | Same operand and return responsibility. | No less-or-equal calendar ordering. |
| <span id="rstimes.Delta.__gt__"></span>`Delta.__gt__(other)` | Same operand and return responsibility. | No greater-than calendar ordering. |
| <span id="rstimes.Delta.__ge__"></span>`Delta.__ge__(other)` | Same operand and return responsibility. | No greater-or-equal calendar ordering. |

```{doctest} delta-inherited-protocols
>>> from rstimes import Delta
>>> value = Delta(nanoseconds=1)
>>> (type(value.__str__()) is str, value.__format__('') == value.__str__())
(True, True)
>>> for method in ('__lt__', '__le__', '__gt__', '__ge__'):
...     assert getattr(value, method)(Delta()) is NotImplemented
>>> try:
...     value.__format__('.1f')
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

Python's [data model](https://docs.python.org/3/reference/datamodel.html)
describes reflected comparison negotiation and `NotImplemented`. The
[Delta protocol guide](../guides/delta-protocols.md) demonstrates these operations
alongside this library's immutable value and business-state rules.

## NumPy dispatch priority metadata

```{py:attribute} rstimes.Delta.__array_priority__
```

The priority is scalar dispatch metadata, not an elapsed amount or date unit.
The value is available on the class and an immutable Delta instance.

```{doctest} delta-native-array-priority-metadata
>>> from rstimes import Delta
>>> (type(Delta.__array_priority__) is float, Delta.__array_priority__)
(True, 1000.0)
>>> Delta().__array_priority__ == Delta.__array_priority__
True
```
