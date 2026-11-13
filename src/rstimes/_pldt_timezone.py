"""One-time native timezone preparation, independent of date-container classes.

The shared local detector remains iana-time-zone. Native rules come from the
pinned mature Rust IANA database and TZif/POSIX parser on every platform.
No custom operating-system directory or Python resource fallback is maintained.
"""

from __future__ import annotations

from datetime import timezone, tzinfo
from functools import lru_cache
from types import GetSetDescriptorType
from typing import TYPE_CHECKING, overload
import zoneinfo

from ._optional import POLARS as pl
from ._localization import resolve_timezone, _UTC_ALIASES
from ._native import _pldt_zone_context, _pldt_named_zone_context, _pldt_native_zone_rules
from .errors import _own_error, _raise_argument_context

if TYPE_CHECKING:
    from ._native import _PldtZoneContext

_UTC = _pldt_zone_context("UTC", b"", 0)


def _read_key(key: str) -> _PldtZoneContext:
    if type(key) is not str and issubclass(type(key), str):
        key = str.__str__(key)
    if not isinstance(key, str) or not key:
        raise _own_error(ValueError("timezone requires a valid named IANA key"))
    if type(key) is str and key == "UTC":
        return _UTC
    if key.lower() in _UTC_ALIASES:
        return _UTC
    # Validate the real host encoding once, without any date rows.
    pl.Series("", [], dtype=pl.Datetime("us", key))
    return _pldt_named_zone_context(key)


@lru_cache(maxsize=128)
def _cached(zone: zoneinfo.ZoneInfo) -> _PldtZoneContext | None:
    return _named_context(zone)


def _named_context(zone: zoneinfo.ZoneInfo) -> _PldtZoneContext | None:
    """Use standard provenance only after live lookup safety is established."""
    if not _pldt_native_zone_rules(zone, zoneinfo.ZoneInfo, GetSetDescriptorType):
        return None
    return _read_key(zone.key)


def prepare_source_timezone(value: zoneinfo.ZoneInfo) -> _PldtZoneContext | None:
    """Return native rules or None for the real-aware source reader.

    The caller supplies a ZoneInfo source. None requests actual fields/offsets,
    and never authorizes replacing an unverified source with its display key.
    """
    return _cached(value) if type(value) is zoneinfo.ZoneInfo else _named_context(value)


@overload
def prepare_timezone(value: None, parameter: str | None = "tz") -> None: ...
@overload
def prepare_timezone(value: str | tzinfo, parameter: str | None = "tz") -> _PldtZoneContext: ...
@overload
def prepare_timezone(value: object, parameter: str | None = "tz") -> _PldtZoneContext | None: ...
def prepare_timezone(value, parameter: str | None="tz"):
    """Prepare immutable native rules with the caller's actual error role.

    None leaves the role to an implicit-source reader. File-origin rules and
    business overrides are rejected before aliases; aware sources have a
    separate actual-value adapter. Naive/UTC/fixed paths never probe DST.
    """
    if value is None:
        return None
    kind = type(value)
    # These real stdlib values are already resolved. In particular, do not
    # traverse the generic name/pytz boundary again for a ZoneInfo subclass;
    # its complete live capability check below remains mandatory.
    if kind is not timezone and kind is not zoneinfo.ZoneInfo and not issubclass(kind, zoneinfo.ZoneInfo):
        value = resolve_timezone(value, parameter or "tz")
        if value is None:
            return None
        kind = type(value)
    if kind is timezone:
        offset = value.utcoffset(None)
        seconds = offset.days * 86400 + offset.seconds
        if offset.microseconds or seconds % 3600:
            raise _own_error(ValueError("this fixed offset cannot be represented by a Polars timezone; choose an IANA zone or target UTC"), parameter, value)
        if seconds == 0:
            return _UTC
        key = f"Etc/GMT{'-' if seconds > 0 else '+'}{abs(seconds) // 3600}"
        try:
            value = zoneinfo.ZoneInfo(key)
        except zoneinfo.ZoneInfoNotFoundError as error:
            raise _own_error(ValueError("this whole-hour fixed offset has no equivalent supported IANA timezone"), parameter, value) from error
        kind = type(value)
    if not isinstance(value, zoneinfo.ZoneInfo):
        raise _own_error(ValueError("custom tzinfo cannot be encoded in a Polars datetime dtype; choose a named target timezone"), parameter, value)
    try:
        if kind is zoneinfo.ZoneInfo:
            context = _cached(value)
        elif _pldt_native_zone_rules(value, zoneinfo.ZoneInfo, GetSetDescriptorType):
            context = _read_key(value.key)
        else:
            context = None
    except Exception as error:
        if parameter is None:
            raise
        _raise_argument_context(error, "", parameter, value)
    if context is None:
        raise _own_error(ValueError("file-origin or custom target timezone rules cannot be reliably encoded in a Polars datetime dtype; choose a standard named IANA target or convert the aware source to UTC first"), parameter, value)
    return context
