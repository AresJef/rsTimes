# Known behavior defects and protocol limits

These cases are disclosed separately from ordinary supported behavior. A
successful example run on this page means that the stated defect or limitation
was reproduced. It does **not** mean that the erroneous product behavior meets
the intended contract. The website's release identity determines which package
was actually checked; a candidate result is not evidence for another release.

## Business ZoneInfo targets lose their overridden offset

**Known defect RV03.** A ZoneInfo subclass may implement a real application
offset different from its key. Pldt currently uses that key for a target zone,
silently ignoring the overridden offset. The example intends 12:00 at +02:00,
which is 10:00 UTC, but produces 12:00 UTC. This is an incorrect two-hour shift.

Use an exact ordinary ZoneInfo object for native named-zone targets. If an
application zone has custom semantics, normalize a genuinely aware standard
datetime to UTC through its actual timezone protocol before supplying the known
instant. That workaround is demonstrated below; do not simply replace its zone
with UTC.

```{doctest} known-zoneinfo-target-defect
>>> from datetime import datetime, timedelta, timezone
>>> from zoneinfo import ZoneInfo
>>> from copy import copy, deepcopy
>>> import polars as pl
>>> from rstimes import Pldt, Pddt, Delta
>>> class BusinessZone(ZoneInfo):
...     def utcoffset(self, value):
...         return timedelta(hours=2)
...     def dst(self, value):
...         return timedelta(0)
...     def fromutc(self, value):
...         return (value + timedelta(hours=2)).replace(tzinfo=self)
>>> zone = BusinessZone('UTC')
>>> local_clock = datetime(2024, 1, 1, 12)
>>> intended = local_clock.replace(tzinfo=zone).astimezone(timezone.utc)
>>> intended.isoformat()
'2024-01-01T10:00:00+00:00'
>>> wrong = Pldt([local_clock], tz=zone, unit='us')
>>> (wrong.dtype.time_zone, wrong.to_physical().to_list())
('UTC', [1704110400000000])
>>> wrong.to_physical().to_list() != [1704103200000000]
True
>>> Pldt([intended], tz='UTC', unit='us').to_physical().to_list()
[1704103200000000]
```

## Named copy has incomplete reduction fallback

**Known defect RV04.** For a real Pddt/Pldt subclass with disabled copy hooks,
`__reduce_ex__ = None`, and a legitimate `__reduce__`, standard
`copy.copy`/`copy.deepcopy` select the reduction. The named `.copy` method
instead raises TypeError. Use the standard copy functions for this specific
configuration. Ordinary date-core copies and the concrete hooks exercised in
the copy guides remain separate, verified cases.

```{doctest} known-named-copy-reduction-defect
>>> for base in (Pddt, Pldt):
...     class Business(base):
...         __copy__ = None
...         __deepcopy__ = None
...         __reduce_ex__ = None
...         def __reduce__(self):
...             return str, ('application reduction',)
...     value = Business([0], unit='us')
...     assert copy(value) == deepcopy(value) == 'application reduction'
...     for deep in (False, True):
...         try:
...             value.copy(deep=deep)
...         except TypeError:
...             continue
...         raise AssertionError('known named-copy defect changed; review the documentation')
```

Descriptors returning None or raising AttributeError have the same missing-hook
fallback responsibility. A dynamically supplied `__reduce_ex__` can instead be
silently bypassed by named copy. These additional public examples compare the
same actual object with the standard copy functions.

```{doctest} known-named-copy-dynamic-fallback
>>> class NoneReducer:
...     def __get__(self, instance, owner):
...         return None
>>> class MissingReducer:
...     def __get__(self, instance, owner):
...         raise AttributeError('application reduction is absent')
>>> for base in (Pddt, Pldt):
...     for descriptor, expected_error in ((NoneReducer(), TypeError), (MissingReducer(), AttributeError)):
...         class Business(base):
...             __copy__ = None
...             __deepcopy__ = None
...             __reduce_ex__ = descriptor
...             def __reduce__(self):
...                 return str, ('available fallback',)
...         value = Business([0], unit='us')
...         assert copy(value) == deepcopy(value) == 'available fallback'
...         for deep in (False, True):
...             try:
...                 value.copy(deep=deep)
...             except expected_error:
...                 continue
...             raise AssertionError('known descriptor fallback defect changed')
>>> for base in (Pddt, Pldt):
...     class Dynamic(base):
...         __copy__ = None
...         __deepcopy__ = None
...         def __getattribute__(self, name):
...             if name == '__reduce_ex__':
...                 return lambda protocol: (str, ('dynamic reduction',))
...             return super().__getattribute__(name)
...     value = Dynamic([0], unit='us')
...     assert copy(value) == deepcopy(value) == 'dynamic reduction'
...     assert type(value.copy()) is Dynamic and type(value.copy(deep=True)) is Dynamic
```

A future product fix must preserve genuine descriptor errors, callback choices,
aliases and memo cycles instead of swallowing arbitrary failures.

## Error preview can replace a callback exception

**Known defect RV05.** Python permits a class's real `__name__` to be a str
subclass. During error-context preview, slicing that name can run its custom
hook. If that hook raises, the display exception can replace the original
integer-protocol exception. The current example observes this wrong exception
identity through Delta and the two vector ordinal factories.

```{doctest} known-type-name-preview-defect
>>> original = LookupError('actual integer callback failed')
>>> display = RuntimeError('type-name display hook ran')
>>> class TypeName(str):
...     def __getitem__(self, key):
...         raise display
>>> class BadIndex:
...     def __index__(self):
...         raise original
>>> BadIndex.__name__ = TypeName('ActualBadIndex')
>>> for action in (lambda: Delta(day=BadIndex()), lambda: Pddt.fromordinal(BadIndex(), size=1), lambda: Pldt.fromordinal(BadIndex(), size=1)):
...     try:
...         action()
...     except RuntimeError as caught:
...         assert caught is display and caught is not original
...     else:
...         raise AssertionError('known error-preview defect changed; review the documentation')
```

This defect limits a universal promise about original exception preservation.
The normal callback examples elsewhere use ordinary type names and explicitly
check their own exception identity. Do not rely on catching the original
exception for this special configuration until the product is fixed.

## Scalar external timezone protocol limitation

Pydt's own timezone operations are distinct from explicitly calling inherited
`datetime.astimezone` or handing a Pydt to `ZoneInfo.fromutc`. Around a repeated
hour, those external paths can produce the wrong occurrence and instant. See
the [executed scalar example and built-in datetime carrier workaround](../guides/pydt-timezones.md).

These findings do not authorize a documentation build to alter the product,
stubs or release payload. Maintenance must rerun the reproductions against a
new actual package, update the affected guides, and retain separate results
for corrected behavior and any remaining defects.
