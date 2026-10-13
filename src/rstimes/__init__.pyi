"""Public exports and typed Unix millisecond conversion signatures."""

from datetime import datetime
from .delta import Delta as Delta

def to_unix_ms(value: datetime) -> int:
    """Floor an aware datetime to integer Unix milliseconds.

    Raises TypeError for non-datetimes and ValueError for naive or out-of-range
    UTC values. See the executable function docstring for examples.
    """
    ...
def from_unix_ms(value: int) -> datetime:
    """Return a UTC-aware datetime for integer Unix milliseconds.

    Rejects bool/non-int with TypeError and out-of-range values with ValueError.
    """
    ...
