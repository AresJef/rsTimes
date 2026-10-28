"""Public exports and typed Unix millisecond conversion signatures."""
from .pydt import Pydt as Pydt
from datetime import datetime
from .delta import Delta as Delta

def to_unix_ms(value: datetime) -> int:
    """Floor an aware datetime to integer Unix milliseconds.

Parameters
----------
value : datetime
    An aware datetime to convert.

Returns
-------
int
    Unix milliseconds, floored when there is a sub-millisecond remainder.

Raises
------
TypeError
    An argument has an unsupported type.
ValueError
    The datetime is timezone-naive.
OverflowError
    The conversion exceeds the supported UTC datetime range.

Examples
--------
>>> to_unix_ms(datetime(1970, 1, 1, tzinfo=timezone.utc))
0"""
    ...

def from_unix_ms(value: int) -> datetime:
    """Return a UTC-aware datetime for integer Unix milliseconds.

Parameters
----------
value : int
    Integer Unix milliseconds. bool and non-int inputs are rejected.

Returns
-------
datetime
    A standard datetime with timezone.utc attached.

Raises
------
TypeError
    An argument has an unsupported type.
OverflowError
    The milliseconds are outside years 1 through 9999.

Examples
--------
>>> from_unix_ms(0).isoformat()
'1970-01-01T00:00:00+00:00'"""
    ...
from .parser import Configs as Configs, parse_str as parse_str, parse as parse
from .pddt import Pddt as Pddt
from .parser import parse_to_epoch as parse_to_epoch
