# Copy and preserve native date columns

Default copy/save operations preserve Pldt's unit, timezone, name, complete
integer date domain and independent nulls. They restore a validated native core
without rerunning ordinary business initialization. Date transformations instead
use the corresponding business constructor. Genuine custom hooks can choose
other returns.

**Known defect RV04:** named `.copy` has incomplete reduction fallback for
None, missing and dynamically supplied reducers. Use standard copy functions
for the [specific affected configurations](../compatibility/known-issues.md).
The ordinary and concrete custom cases below do not assert that defect is fixed.

## Core dates and buffer isolation

Shallow copy creates a new Series shell and can share safe native date buffers.
Deep copy physically isolates date buffers and uses one memo for business
references. Nulls remain independent from a valid minimum tick. `deep` requires
a genuine Python or NumPy boolean.

```{doctest} pldt-core-copy-and-isolation
>>> from copy import copy, deepcopy
>>> import pickle
>>> import numpy as np
>>> import polars as pl
>>> from rstimes import Pldt
>>> values = [-2**63, None, -2**63 + 1, 2**63 - 1]
>>> for unit in ('ms', 'us', 'ns'):
...     for zone in (None, 'UTC', 'America/New_York'):
...         source = Pldt(pl.Series('event', values, dtype=pl.Datetime(unit, zone)))
...         for result in (copy(source), deepcopy(source), source.copy(), source.copy(deep=True), source.__copy__(), source.__deepcopy__({})):
...             assert type(result) is Pldt and result is not source
...             assert result.dtype == source.dtype and result.name == 'event'
...             assert result.to_physical().to_list() == values
...             assert result.is_null().to_list() == [False, True, False, False]
>>> raw = np.array([-2**63, 0, 2**63 - 1], dtype=np.int64)
>>> source = Pldt(raw, unit='ns', name='event')
>>> shallow, deep = copy(source), deepcopy(source)
>>> a, b, c = [value.to_physical().to_numpy() for value in (source, shallow, deep)]
>>> (a.ctypes.data == b.ctypes.data, a.ctypes.data != c.ctypes.data)
(True, True)
>>> returned = shallow.append(Pldt([5], unit='ns'))
>>> (returned is shallow, len(shallow), len(source), deep.to_physical().to_list())
(True, 4, 3, [-9223372036854775808, 0, 9223372036854775807])
>>> named = source.copy(name='renamed', deep=np.bool_(True))
>>> (named.name, source.name, named.dtype == source.dtype)
('renamed', 'event', True)
>>> try:
...     source.copy(deep=1)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

## Real subclasses, aliases, slots, and cycles

The actual namespace caches are omitted from saved business state and rebind to
the restored receiver. Initialized slots are preserved; an unset slot stays
unset. Shallow business references remain shared; deep aliases and cycles use
the same memo as the date object.

```{doctest} pldt-business-copy-protocol
>>> builds = []
>>> class Business(Pldt):
...     __slots__ = ('label', 'unset')
...     def __new__(cls, data, **options):
...         builds.append('new')
...         return super().__new__(cls)
...     def __init__(self, data, **options):
...         builds.append('init')
...         super().__init__(data, **options)
>>> business = Business([0, None, 123456789], unit='ns', name='event')
>>> shared = ['application']
>>> business.label = business.items = business.alias = shared
>>> business.loop = business
>>> _ = business.dt, business.pldt
>>> state = business.__getstate__()
>>> (state[0]['items'] is shared, state[1]['label'] is shared, '_s' in state[0], 'pldt' in state[0], 'unset' in state[1])
(True, True, False, False, False)
>>> builds.clear()
>>> changed = business.to_next_month()
>>> (type(changed) is Business, builds)
(True, ['new', 'init'])
>>> builds.clear()
>>> shallow = copy(business)
>>> (shallow is not business, shallow.label is shared, shallow.loop is business)
(True, True, True)
>>> deep = deepcopy(business)
>>> (type(deep) is Business, deep.label is deep.items is deep.alias, deep.label is not shared, deep.loop is deep, hasattr(deep, 'unset'), builds)
(True, True, True, True, False, [])
>>> (deep.pldt.year.to_list(), deep.year.to_list(), 'pldt' in deep.__getstate__()[0])
([1970, None, 1970], [1970, None, 1970], False)
>>> replacement = ['supplied memo']
>>> memo = {id(shared): replacement}
>>> result = deepcopy(business, memo)
>>> (result.label is result.alias is replacement, result.loop is result, memo[id(business)] is result)
(True, True, True)
```

## Pickle and business state

The recipe separates a versioned native date core from ordinary business state.
Core bytes and validity do not expose the mutable Series owner. Business state
cannot overwrite `_s`. Only load trusted pickle data, and do not treat private
recipe positions as a stable interchange format. For long-lived external data,
choose an explicit native representation with a recorded schema and version.

```{doctest} pldt-state-and-pickle
>>> source = Pldt([-2**63, None, 123456789], unit='ns', tz='UTC', name='event')
>>> source.items = []
>>> source.alias = source.items
>>> source.loop = source
>>> for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
...     restored = pickle.loads(pickle.dumps(source, protocol=protocol))
...     assert type(restored) is Pldt and restored is not source
...     assert restored.dtype == source.dtype and restored.name == 'event'
...     assert restored.to_physical().to_list() == [-2**63, None, 123456789]
...     assert restored.items is restored.alias and restored.items is not source.items
...     assert restored.loop is restored
>>> for recipe in (source.__reduce__(), source.__reduce_ex__(4)):
...     assert type(recipe) is tuple and len(recipe) == 3 and callable(recipe[0])
...     rebuilt = recipe[0](*recipe[1])
...     assert type(rebuilt) is Pldt and rebuilt.dtype == source.dtype
...     assert rebuilt.__setstate__(recipe[2]) is None
...     assert rebuilt.items is source.items and rebuilt.to_physical().to_list() == [-2**63, None, 123456789]
>>> target = Pldt([0], unit='us')
>>> (target.__setstate__(None), target.__setstate__({'note': 'restored'}), target.note)
(None, None, 'restored')
>>> for state, error in [({'_s': object()}, ValueError), (({}, {'bad': 1, 42: 2}), TypeError), ([], TypeError), ((None,), ValueError)]:
...     try:
...         target.__setstate__(state)
...     except error:
...         continue
...     raise AssertionError('invalid or core-replacing business state was accepted')
>>> target.to_physical().to_list()
[0]
```

A pickled application class must be available through its defining module.
This fresh-process example verifies a genuine subclass, aliases, cycles and
constructor counters while its `__main__` definition is available to pickle.

```{doctest} pldt-business-pickle-fresh-process
>>> import subprocess, sys
>>> program = '\n'.join([
...     'import pickle',
...     'from rstimes import Pldt',
...     'class Business(Pldt):',
...     '    calls = 0',
...     '    def __init__(self, data, **options):',
...     '        Business.calls += 1',
...     '        super().__init__(data, **options)',
...     "source = Business([0, None, 123], unit='ns', tz='UTC', name='event')",
...     'source.items = source.alias = []',
...     'source.loop = source',
...     'for protocol in range(pickle.HIGHEST_PROTOCOL + 1):',
...     '    result = pickle.loads(pickle.dumps(source, protocol=protocol))',
...     '    assert type(result) is Business and Business.calls == 1',
...     '    assert result.items is result.alias and result.loop is result',
...     '    assert result.to_physical().to_list() == [0, None, 123]',
... ])
>>> completed = subprocess.run([sys.executable, '-I', '-c', program], capture_output=True, text=True, check=True, timeout=20)
>>> (completed.returncode, completed.stdout, completed.stderr)
(0, '', '')
```

## Concrete custom copy and error hooks

```{doctest} pldt-custom-copy-state-hooks
>>> class Choices(Pldt):
...     def __copy__(self):
...         return 'application shallow'
...     def __deepcopy__(self, memo):
...         return 'application deep'
>>> value = Choices([0])
>>> (value.copy(), value.copy(deep=True), copy(value), deepcopy(value))
('application shallow', 'application deep', 'application shallow', 'application deep')
>>> marker = RuntimeError('application state failed')
>>> class FailedState(Pldt):
...     def __getstate__(self):
...         raise marker
>>> value = FailedState([0])
>>> for action in (lambda: value.copy(), lambda: copy(value), lambda: deepcopy(value), lambda: pickle.dumps(value)):
...     try:
...         action()
...     except RuntimeError as caught:
...         assert caught is marker
...     else:
...         raise AssertionError('the genuine state exception was lost')
```
