"""One-time native timezone preparation, independent of date-container classes.

The shared local detector remains iana-time-zone. Native rules come from the
pinned mature Rust IANA database and TZif/POSIX parser on every platform.
No custom operating-system directory or Python resource fallback is maintained.
"""

from datetime import timezone
from functools import lru_cache
import zoneinfo

from ._optional import POLARS as pl
from ._localization import resolve_timezone, _UTC_ALIASES
from ._native import _pldt_zone_context, _pldt_named_zone_context
from .errors import _own_error

_UTC = _pldt_zone_context("UTC", b"", 0)


def _read(zone):
    key = zone.key
    if not isinstance(key, str) or not key:
        raise _own_error(ValueError("timezone requires a valid named IANA key"), "tz", zone)
    # Validate the real host encoding once, without any date rows.
    pl.Series("", [], dtype=pl.Datetime("us", key))
    return _pldt_named_zone_context(key)


@lru_cache(maxsize=128)
def _cached(zone):
    return _read(zone)


def prepare_timezone(value):
    """Return immutable native rules; naive/UTC/fixed paths do not probe DST."""
    value = resolve_timezone(value)
    if value is None:
        return None
    if type(value) is timezone:
        offset = value.utcoffset(None)
        seconds = offset.days * 86400 + offset.seconds
        if offset.microseconds or seconds % 3600:
            raise _own_error(ValueError("this fixed offset cannot be represented by a Polars timezone; choose an IANA zone or target UTC"), "tz", value)
        if seconds == 0:
            return _UTC
        key = f"Etc/GMT{'-' if seconds > 0 else '+'}{abs(seconds) // 3600}"
        try:
            value = zoneinfo.ZoneInfo(key)
        except zoneinfo.ZoneInfoNotFoundError as error:
            raise _own_error(ValueError("this whole-hour fixed offset has no equivalent supported IANA timezone"), "tz", value) from error
    if not isinstance(value, zoneinfo.ZoneInfo):
        raise _own_error(ValueError("custom tzinfo cannot be encoded in a Polars datetime dtype; choose a named target timezone"), "tz", value)
    key = value.key
    if isinstance(key, str) and key.lower() in _UTC_ALIASES:
        return _UTC
    if type(value) is zoneinfo.ZoneInfo:
        return _cached(value)
    # Real subclass protocol remains host-side and is not globally memoized.
    return _read(value)
