# Date namespaces

Namespace accessors expose date operations on an owning container. Reading the
accessor and then calling its method is one public path into that operation;
the accessor is not a separate user-constructed helper class.

## Pddt field replacement

<span id="rstimes.Pddt.pddt"></span>
`x.pddt` is the date-field namespace belonging to a Pddt. It takes no arguments.
Use its `replace` method for strict field replacement. With pandas 3.1,
inherited `x.replace(to_replace, value, regex=False)` replaces whole index
values and returns pandas' own Index type. That inherited method is absent
with the tested pandas 2.3.3 and 3.0.6. It does not replace this date-field API.

<span id="rstimes.Pddt.pddt.replace"></span>
`x.pddt.replace(year=None, month=None, day=None, hour=None, minute=None,
second=None, microsecond=None, nanosecond=None, tzinfo=..., *,
ambiguous='raise', nonexistent='raise')` returns the corresponding Pddt class.
Here `...` denotes an omitted timezone argument: it retains the existing zone;
explicit None removes the zone without moving the clock.

| Parameter role | Meaning and boundary |
|---|---|
| Calendar/clock fields | Integer index scalar or equal-length positional column. Explicit None preserves an optional field; pd.NA/NaN are not that instruction. |
| `year` | Zero, negative, and wide values are real years within the current unit's capacity. |
| `month`, `day` | Numeric 1–12 / 1–31; the complete date must be valid. A strict February 31 raises ValueError. |
| `hour`, `minute`, `second` | 0–23 / 0–59 / 0–59. Zero sets a real zero. |
| `microsecond`, `nanosecond` | 0–999999 / 0–999. Microsecond replacement clears the old ns tail, then an explicit ns tail is applied. |
| `tzinfo` | A timezone/name or None, with local clock interpretation. |
| `ambiguous`, `nonexistent` | The explicit column localization policies, independent of scalar fold. |

The original unit, name, row order, and source NaT positions remain. TypeError
rejects unsupported numeric roles; ValueError rejects invalid dates, target
lengths, unresolved local times or lost precision; OverflowError rejects
unrepresentable results. Failed calculations do not modify the source column.

```{doctest} pddt-namespace-reference
>>> from rstimes import Pddt
>>> import pandas as pd
>>> source = Pddt(['2024-01-31T12:34:56.123456789', None], tz='UTC', name='event')
>>> result = source.pddt.replace(day=[1, None], hour=0, nanosecond=2)
>>> (type(result) is Pddt, result.unit, result.name, result.isna().tolist(), result.isoformat().dropna().tolist())
(True, 'ns', 'event', [False, True], ['2024-01-01T00:34:56.123456002+00:00'])
>>> source.day.dropna().tolist()
[31.0]
>>> if hasattr(source, 'replace'):
...     inherited = source.replace({source[0]: pd.Timestamp('2024-02-01', tz='UTC')})
...     assert type(inherited) is pd.DatetimeIndex and inherited.name == 'event'
...     assert inherited.day.dropna().tolist() == [1.0] and inherited.isna().tolist() == [False, True]
... else:
...     assert tuple(int(part) for part in pd.__version__.split('.')[:2]) < (3, 1)
>>> try:
...     source.pddt.replace(month=2)
... except ValueError as error:
...     print(type(error).__name__)
ValueError
```

```{doctest} pddt-namespace-regional-policies
>>> repeated = Pddt(['2024-11-03 01:30', None], unit='ns')
>>> localized = repeated.pddt.replace(tzinfo='America/New_York', ambiguous=False)
>>> (localized.tz_convert('UTC').isoformat().dropna().tolist(), localized.isna().tolist())
(['2024-11-03T06:30:00+00:00'], [False, True])
>>> gap = Pddt(['2024-03-10 02:30'], unit='us')
>>> gap.pddt.replace(tzinfo='America/New_York', nonexistent='shift_forward').isoformat().tolist()
['2024-03-10T03:00:00-04:00']
```

For complete workflows, see [Pddt calendar operations](../guides/pddt-calendar.md)
and [timezone policies](../guides/pddt-timezones.md).
