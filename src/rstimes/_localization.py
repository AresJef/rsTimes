"""Shared names and timezone boundaries, independent of Pydt and Pddt."""

from datetime import timezone, tzinfo
from functools import lru_cache
from os import environ
from zoneinfo import ZoneInfo

from ._native import _local_timezone_name, _localized_name, _resolve_optional_timezone
from .errors import _own_error, _external_error, _preview, _raise_argument_context


@lru_cache(maxsize=1)
def local_timezone():
    """Resolve the first actual local request; failed attempts remain retryable."""
    name = environ.get("TZ")
    if name is None:
        name = _local_timezone_name()
    elif name.startswith(":"):
        name = name[1:]
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError) as error:
        raise _own_error(ValueError(
            f"local timezone {_preview(name)} is unavailable; provide installed timezone data "
            "or set TZ to a valid IANA name such as 'Asia/Shanghai'"
        )) from error


_UTC_ALIASES = frozenset({"z", "utc", "gmt", "gmt0", "gmt+0", "gmt-0", "zulu",
                         "universal", "greenwich", "etc/utc", "etc/gmt", "etc/gmt0",
                         "etc/gmt+0", "etc/gmt-0", "etc/zulu", "etc/universal"})


@lru_cache(maxsize=128)
def named_timezone(name):
    """Reuse standard timezone objects for actual name inputs."""
    try:
        lower = name.lower()
    except Exception as error:
        raise _external_error(error)
    if lower == "local":
        return local_timezone()
    if lower in _UTC_ALIASES:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError) as error:
        raise _own_error(ValueError(f"timezone name {_preview(name)} is invalid or timezone data is unavailable")) from error


def resolve_timezone(value, parameter="tz"):
    """Keep valid tzinfo values; convert real named pytz zones only."""
    try:
        if value is None or type(value) is timezone or type(value) is ZoneInfo:
            return value
        if issubclass(type(value), str):
            if type(value) is str:
                return named_timezone(value)
            try:
                return named_timezone(value)
            except Exception as error:
                raise _external_error(error)
        if not issubclass(type(value), tzinfo):
            raise _own_error(TypeError("must be an IANA name, tzinfo, or None"), parameter, value)
        if issubclass(type(value), ZoneInfo):
            return value
        return _resolve_optional_timezone(value, named_timezone)
    except Exception as error:
        _raise_argument_context(error, "", parameter, value)
