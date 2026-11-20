# Work with timezone, copy, and error protocols

Version 1.0.0 corrects three beta behaviors below. Each example
uses the published release. The external Pydt timezone protocol
boundary still applies.

## Choose a representable target timezone

(compat-reject-custom-date-target)=
```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from rstimes import Pldt

class BusinessZone(ZoneInfo):
    def utcoffset(self, value):
        return timedelta(hours=2)

zone = BusinessZone("UTC")
try:
    Pldt([datetime(2024, 1, 1, 12)], tz=zone)
except ValueError as error:
    print(type(error).__name__)
```

**Output**

```text
ValueError
```

In 1.0.0, a custom target that cannot be represented in a Polars
dtype is rejected. The beta accepted this target by its key and
lost its custom offset (RV03). An aware source can supply its
actual offset before conversion to a standard zone.
{ref}`Convert an aware source <pldt-business-zone-as-source>`
for that example.

## Let a copy use your application reduction

(compat-copy-business-reduction)=
```python
from rstimes import Pddt

class EventIndex(Pddt):
    __copy__ = None
    __deepcopy__ = None
    __reduce_ex__ = None

    def __reduce__(self):
        return str, ("application copy",)

events = EventIndex([0], unit="us")
print(events.copy())
```

**Output**

```text
application copy
```

Named Pddt and Pldt copies in 1.0.0 use the genuine available
copy or reduction protocol. The beta missed the fallback in
this case (RV04). Custom protocols choose their result and can
raise application exceptions. For normal copy and memo behavior,
see [Pddt state](../guides/pddt-protocols.md) and
[Pldt state](../guides/pldt-state.md).

## Catch the application exception raised by an integer input

(compat-preserve-index-exception)=
```python
from rstimes import Delta

class ProjectInputError(Exception):
    pass

original = ProjectInputError("invalid application input")

class Count:
    def __index__(self):
        raise original

try:
    Delta(days=Count())
except ProjectInputError as caught:
    print(caught is original)
```

**Output**

```text
True
```

1.0.0 preserves this exception. The beta could replace an
original integer error with one from formatting an unusual
type name (RV05). The release regression also exercises that
type-name path along with Pddt and Pldt factory errors.
See [error handling](../api/errors.md) for domain and built-in errors.

## Call external timezone code with a standard datetime

Pydt's own `tz_convert` and `astimezone` preserve the intended
instant. A direct call such as `ZoneInfo.fromutc(value)` runs an
external standard-library protocol. During the repeated New York
hour, it can choose the later instant for a Pydt.
[Use a standard datetime carrier](../guides/pydt-timezones.md)
with the same clock, zone and fold when passing it to external code.
