# Pandas date operators and saved state

Calendar Delta values and actual elapsed durations have different meanings.
A duration can be a timedelta, pandas Timedelta, NumPy timedelta64, or a
matching positional duration column. Arithmetic retains Pddt's unit and rejects
an unrepresentable result. Subtracting dates returns pandas TimedeltaIndex at
the finer participating resolution, rather than Pddt.

## Arithmetic, row operands, and pandas dispatch

```{doctest} pddt-arithmetic-protocols
>>> from datetime import date, datetime, timedelta, timezone
>>> import numpy as np
>>> import pandas as pd
>>> from rstimes import Pddt, Delta
>>> source = Pddt(['2024-03-09 12:00', None], tz='America/New_York', name='event')
>>> for duration in (timedelta(days=1), pd.Timedelta(days=1), np.timedelta64(24, 'h')):
...     forward, reflected = source + duration, duration + source
...     assert type(forward) is Pddt and type(reflected) is Pddt
...     assert forward.hour.dropna().tolist() == [13.0] and forward.unit == source.unit and forward.name == 'event'
...     assert forward.asi8.tolist() == reflected.asi8.tolist() and forward.isna().tolist() == [False, True]
>>> ((source + Delta(days=1)).hour.dropna().tolist(), (Delta(days=1) + source).hour.dropna().tolist())
([12.0], [12.0])
>>> source.__radd__(timedelta(days=1)).hour.dropna().tolist()
[13.0]
>>> dates = Pddt(['2024-01-31', '2024-02-29'], unit='ns')
>>> (dates + [Delta(months=1), Delta(months=2)]).month.tolist()
[2, 4]
>>> (dates - Delta(months=1)).month.tolist()
[12, 1]
>>> epoch = Pddt([0, 1, None], unit='ns', name='event')
>>> durations = pd.TimedeltaIndex(np.array([1, 2, 3], dtype='timedelta64[ns]'))
>>> (epoch + durations).asi8.tolist()
[1, 3, -9223372036854775808]
>>> difference = Pddt([1, None], unit='us', name='event') - np.datetime64(1, 'ns')
>>> (type(difference) is pd.TimedeltaIndex, difference.unit, difference.name, difference.asi8.tolist())
(True, 'ns', 'event', [999, -9223372036854775808])
>>> date_difference = Pddt(['2024-01-03', '2024-01-05'], unit='s') - [date(2024, 1, 1), None]
>>> (type(date_difference) is pd.TimedeltaIndex, date_difference.asi8.tolist())
(True, [172800, -9223372036854775808])
>>> reflected_difference = datetime(1970, 1, 2) - Pddt([0, None], unit='s')
>>> (type(reflected_difference) is pd.TimedeltaIndex, reflected_difference.unit, reflected_difference.asi8.tolist())
(True, 'us', [86400000000, -9223372036854775808])
>>> assert (epoch + timedelta(0)) is epoch and (epoch + Delta()) is epoch
>>> for call, exception in ((lambda: dates + [Delta()], ValueError), (lambda: dates + [Delta(), None], TypeError), (lambda: epoch + np.timedelta64(1, 'M'), TypeError), (lambda: epoch - '1970-01-01', TypeError), (lambda: Pddt([0], unit='s') + Delta(nanoseconds=1), ValueError), (lambda: Pddt([2**63-1], unit='ns') + np.timedelta64(1, 'ns'), OverflowError), (lambda: Pddt([0], unit='s') - datetime(1970, 1, 1, tzinfo=timezone.utc), TypeError)):
...     try:
...         call()
...     except exception:
...         continue
...     raise AssertionError('invalid arithmetic request accepted')
```

Pandas Series/DataFrame own their complete label/column dispatch. Direct Pddt
arithmetic methods return NotImplemented for these operands so pandas can
perform its actual operation. A pandas DateOffset likewise retains its mature
calendar protocol rather than receiving the library's extra integer rules.

```{doctest} pddt-pandas-owned-dispatch
>>> spans = pd.Series([timedelta(days=1), timedelta(days=2)], index=['b', 'a'], name='span')
>>> plain = Pddt(['2024-01-01', '2024-01-01'])
>>> (plain.__add__(spans) is NotImplemented, plain.__radd__(spans) is NotImplemented, plain.__sub__(spans) is NotImplemented)
(True, True, True)
>>> owned = spans + plain
>>> (type(owned) is pd.Series, owned.index.tolist(), owned.dt.day.tolist())
(True, ['b', 'a'], [2, 3])
>>> (Pddt(['2024-01-31']) + pd.offsets.MonthEnd()).day.tolist()
[29]
```

## Subtypes and copy ownership

Changed date results preserve the appropriate subclass and its actual
construction protocol. An unchanged result may be the original object.
Copy/save instead restore the immutable date core without rerunning business
construction. Shallow copies use a new shell with safe shared date storage and
shared business references. Deep copies use an independent buffer and one memo
for business aliases and cycles. `copy(deep=...)` requires a real bool.

```{doctest} pddt-copy-and-subclass
>>> from copy import copy, deepcopy
>>> builds = []
>>> class Business(Pddt):
...     __slots__ = ('slot',)
...     def __new__(cls, data, **kwargs):
...         builds.append('new')
...         return super().__new__(cls, data, **kwargs)
...     def __init__(self, data, **kwargs):
...         builds.append('init')
>>> business = Business([0, None], unit='ns', tz='UTC', name='event')
>>> business.items = []
>>> business.alias = business.items
>>> business.slot = business.items
>>> business.loop = business
>>> builds.clear()
>>> changed = business + timedelta(days=1)
>>> (type(changed) is Business, builds)
(True, ['new', 'init'])
>>> builds.clear()
>>> for shallow in (copy(business), business.copy(), business.copy(deep=False), business.__copy__()):
...     assert type(shallow) is Business and shallow is not business
...     assert shallow.items is business.items and shallow.slot is business.items and shallow.loop is business
...     assert np.shares_memory(shallow.asi8, business.asi8)
>>> memo = {}
>>> for deep in (deepcopy(business), business.copy(deep=True), business.__deepcopy__(memo)):
...     assert type(deep) is Business and deep is not business and deep.loop is deep
...     assert deep.items is deep.alias is deep.slot and deep.items is not business.items
...     assert not np.shares_memory(deep.asi8, business.asi8) and deep.asi8.tolist() == business.asi8.tolist()
>>> (memo[id(business)].loop is memo[id(business)], builds)
(True, [])
>>> named = business.copy(name='renamed', deep=True)
>>> (named.name, business.name, named.unit, str(named.tz))
('renamed', 'event', 'ns', 'UTC')
>>> try:
...     business.copy(deep=1)
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

## Versioned date core and business state

The pickle recipe stores a versioned date core separately from metadata.
`__getstate__` returns a business-state snapshot, excluding internal date/cache
fields. `__setstate__` cannot overwrite those internals. The concrete hook
examples below verify their own returns and exception identity. **Known defect
RV04:** named `.copy` has incomplete None/missing/dynamic reduction fallback;
use standard copy functions for the configurations in
[the executed known-issue examples](../compatibility/known-issues.md).
This is an unresolved product defect, so these examples are not a claim that
all custom protocols conform. Only load trusted pickle data; legacy Pddt pickle
formats are not automatically migrated.

```{doctest} pddt-state-and-pickle
>>> import pickle
>>> plain = Pddt.date_range('2024-01-01', periods=2, freq='D', unit='ns', tz='UTC', name='event')
>>> plain.items = []
>>> plain.alias = plain.items
>>> plain.loop = plain
>>> state = plain.__getstate__()
>>> (type(state) is dict, '_data' not in state, state is not plain.__dict__, state['items'] is plain.items)
(True, True, True, True)
>>> for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
...     restored = pickle.loads(pickle.dumps(plain, protocol=protocol))
...     assert type(restored) is Pddt and restored is not plain and restored.asi8.tolist() == plain.asi8.tolist()
...     assert restored.unit == 'ns' and str(restored.tz) == 'UTC' and restored.name == 'event' and restored.freq == plain.freq
...     assert restored.items is restored.alias and restored.items is not plain.items and restored.loop is restored
>>> for recipe in (plain.__reduce__(), plain.__reduce_ex__(4)):
...     assert type(recipe) is tuple and len(recipe) == 3 and callable(recipe[0])
...     rebuilt = recipe[0](*recipe[1])
...     assert type(rebuilt) is Pddt and rebuilt.asi8.tolist() == plain.asi8.tolist()
...     assert rebuilt.__setstate__(recipe[2]) is None and rebuilt.items is plain.items
>>> target = Pddt([0], unit='s')
>>> (target.__setstate__(None), target.__setstate__({'note': 'restored'}), target.note)
(None, None, 'restored')
>>> for state, exception in (({'_data': 'bad'}, ValueError), ((None, {'_name': 'bad'}), ValueError), ([], TypeError), ((None,), ValueError)):
...     try:
...         target.__setstate__(state)
...     except exception:
...         continue
...     raise AssertionError('invalid business state accepted')
>>> target.asi8.tolist()
[0]
```

```{doctest} pddt-original-hooks
>>> class CopyChoices(Pddt):
...     def __copy__(self):
...         return 'application shallow result'
...     def __deepcopy__(self, memo):
...         return 'application deep result'
>>> choices = CopyChoices([0], unit='s')
>>> (choices.copy(), choices.copy(deep=True), copy(choices), deepcopy(choices))
('application shallow result', 'application deep result', 'application shallow result', 'application deep result')
>>> marker = RuntimeError('business state failed')
>>> class FailedState(Pddt):
...     def __getstate__(self):
...         raise marker
>>> failed = FailedState([0], unit='s')
>>> for action in (lambda: copy(failed), lambda: deepcopy(failed), lambda: pickle.dumps(failed)):
...     try:
...         action()
...     except RuntimeError as caught:
...         assert caught is marker
...     else:
...         raise AssertionError('original state error lost')
```

See the standard [copy](https://docs.python.org/3/library/copy.html) and
[pickle](https://docs.python.org/3/library/pickle.html) references for custom
protocol conventions, and the inherited pandas reference for index operations
whose result type belongs to pandas.
