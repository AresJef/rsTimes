# Copy and save parsing configurations

Copied Configs objects have independently editable rules and preferences.
`copy.copy`, `copy.deepcopy`, and a pickle round trip do not leave the two
configurations connected by a writable token table.

## Copy an editable configuration

```{doctest} configs-independent-copy
>>> from copy import copy, deepcopy
>>> from rstimes import Configs, parse_str
>>> source = Configs(yearfirst=False, dayfirst=True)
>>> source.add_month('harvest', 10)
True
>>> shallow, deep = copy(source), deepcopy(source)
>>> (type(shallow) is Configs, type(deep) is Configs, shallow is not source, deep is not source)
(True, True, True, True)
>>> shallow.set_month({'harvest': 2})
True
>>> (source.month['harvest'], shallow.month['harvest'], deep.month['harvest'])
(10, 2, 10)
>>> parse_str('7 harvest 2024', cfg=source).isoformat()
'2024-10-07T00:00:00'
>>> direct = source.__copy__()
>>> memo = {}
>>> direct_deep = source.__deepcopy__(memo)
>>> (direct is not source, direct.month == source.month, memo[id(source)] is direct_deep)
(True, True, True)
```

## Save the versioned snapshot

Use pickle for ordinary persistence and load only trusted data. Configs uses
its reduction recipe to carry the validated configuration snapshot. Its
inherited `__getstate__()` returns `None`; that method alone is not its
serialization format.

The current version 2 snapshot includes the two preferences, eight word tables,
and registered region names. A recognized version 1 five-tuple can restore
the word tables and flags without the newer region collection. Other versions
or malformed layouts fail. This is distinct from Delta's rejection of its old
state format.

```{doctest} configs-pickle-state
>>> import pickle
>>> source.add_tzone('Asia/Shanghai')
True
>>> loaded = pickle.loads(pickle.dumps(source, protocol=pickle.HIGHEST_PROTOCOL))
>>> (type(loaded) is Configs, loaded is not source, loaded.month == source.month, loaded.tzone == source.tzone)
(True, True, True, True)
>>> loaded.del_month('harvest')
True
>>> 'harvest' in source.month
True
>>> source.__getstate__() is None
True
>>> recipe = source.__reduce__()
>>> alternate = source.__reduce_ex__(pickle.HIGHEST_PROTOCOL)
>>> (type(recipe) is tuple, len(recipe), callable(recipe[0]), recipe[2] == alternate[2])
(True, 3, True, True)
>>> state = recipe[2]
>>> (state[:4], len(state), len(state[4]))
(('rstimes.Configs', 2, False, True), 6, 8)
>>> restored = Configs()
>>> restored.__setstate__(state) is None
True
>>> (restored.yearfirst, restored.dayfirst, restored.month['harvest'], 'Asia/Shanghai' in restored.tzone)
(False, True, 10, True)
>>> restored.del_month('harvest')
True
>>> 'harvest' in source.month
True
>>> older = (state[0], 1, state[2], state[3], state[4])
>>> restored.__setstate__(older)
>>> (restored.month['harvest'], restored.tzone)
(10, set())
```

Restoration validates the new snapshot before replacing the rules. Invalid
state does not partly change the receiver. The snapshot containers are
independent; they are not live handles into its lookup tables. Region names
that cannot be loaded on another machine can be retained with a warning;
using an unavailable region then raises an error.

```{doctest} configs-invalid-state
>>> before = restored.month
>>> invalid_version = (state[0], 99, *state[2:])
>>> try:
...     restored.__setstate__(invalid_version)
... except ValueError as error:
...     print(type(error).__name__, restored.month == before)
ValueError True
>>> try:
...     restored.__setstate__(None)
... except TypeError as error:
...     print(type(error).__name__, restored.month == before)
TypeError True
```

## Object protocols retain Python meanings

Configs instances compare by identity, rather than by the contents of their
tables. A copy may contain the same words and still compare unequal. They are
hashable objects but are not ordered calendars. The empty format specification
uses their string representation; numeric format specifications are unsupported.

```{doctest} configs-object-protocols
>>> (source == source, source != direct, source.__eq__(direct) is NotImplemented, source.__ne__(source))
(True, True, True, False)
>>> (type(source.__hash__()) is int, type(source.__repr__()) is str, source.__str__() == source.__repr__(), source.__format__('') == str(source))
(True, True, True, True)
>>> for name in ('__lt__', '__le__', '__gt__', '__ge__'):
...     assert getattr(source, name)(direct) is NotImplemented
>>> try:
...     source.__format__('.2f')
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

See [the copy module](https://docs.python.org/3/library/copy.html) and
[pickle](https://docs.python.org/3/library/pickle.html) for Python's protocols.
For importing dateutil vocabulary, use [parserinfo adaptation](parserinfo.md).
