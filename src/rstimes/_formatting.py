"""Shared pure-format preparation; word meanings remain native call inputs."""
from functools import lru_cache
import calendar as _calendar
import locale as _locale
import re as _re
import time as _time
from ._native import _strptime_compile
from .errors import _own_error, _external_error, _raise_argument_context


@lru_cache(maxsize=128)
def _compile(fmt):
    try:
        return _strptime_compile(fmt)
    except Exception as error:
        _raise_argument_context(error, "", "fmt", fmt)


def prepare_format(fmt):
    """Cache structure only; actual Configs and locale data are not frozen here."""
    if not isinstance(fmt, str):
        raise _own_error(TypeError("must be a strptime format string"), "fmt", fmt)
    if type(fmt) is not str:
        try:
            fmt = str(fmt)
        except Exception as error:
            raise _external_error(error)
    compiled = _compile(fmt)
    if not compiled.needs_locale:
        return compiled
    try:
        current = _locale.setlocale(_locale.LC_TIME)
    except Exception as error:
        raise _external_error(error)
    return _with_locale(fmt, current)


@lru_cache(maxsize=16)
def _locale_data(current):
    """Read only requested system templates; never change the global locale."""
    try:
        if hasattr(_locale, "nl_langinfo"):
            templates = {key: _locale.nl_langinfo(getattr(_locale, name)) for key, name in
                (("c", "D_T_FMT"), ("x", "D_FMT"), ("X", "T_FMT"), ("r", "T_FMT_AMPM"))}
            words = {
                "b": [(_locale.nl_langinfo(getattr(_locale, f"ABMON_{i}")), i) for i in range(1, 13)],
                "B": [(_locale.nl_langinfo(getattr(_locale, f"MON_{i}")), i) for i in range(1, 13)],
                "a": [(_locale.nl_langinfo(getattr(_locale, f"ABDAY_{i}")), (i+5)%7) for i in range(1, 8)],
                "A": [(_locale.nl_langinfo(getattr(_locale, f"DAY_{i}")), (i+5)%7) for i in range(1, 8)],
                "p": [(_locale.nl_langinfo(_locale.AM_STR), 0), (_locale.nl_langinfo(_locale.PM_STR), 1)],
            }
        else:
            templates, words = _public_locale_templates()
        after = _locale.setlocale(_locale.LC_TIME)
    except Exception as error:
        raise _external_error(error)
    if after != current:
        raise _own_error(RuntimeError("LC_TIME changed while preparing format data; retry after locale settings are stable"))
    return templates, words


def _public_locale_templates():
    """Prepare Windows composite metadata through public strftime/calendar APIs.

    Distinct probe fields identify system formatting once per locale. This
    extracts templates only: it never parses user data or imports LocaleTime.
    """
    ampm = [_time.strftime("%p", (1999, 3, 17, hour, 44, 55, 2, 76, -1))
            for hour in (1, 22)]
    words = {"b": list(zip(_calendar.month_abbr[1:], range(1, 13))),
             "B": list(zip(_calendar.month_name[1:], range(1, 13))),
             "a": list(zip(_calendar.day_abbr[:], range(7))),
             "A": list(zip(_calendar.day_name[:], range(7))),
             "p": list(zip(ampm, range(2)))}
    replacements = {"1999": "%Y", "99": "%y", "03": "%m", "3": "%m",
                    "17": "%d", "22": "%H", "10": "%I", "44": "%M", "55": "%S",
                    "%": "%%"}
    for code, index in (("B", 2), ("b", 2), ("A", 2), ("a", 2), ("p", 1)):
        word = words[code][index][0]
        if word:
            replacements.setdefault(word, "%" + code)
    for name in (*_time.tzname, "UTC", "GMT"):
        if name:
            replacements.setdefault(name, "%Z")
    pattern = _re.compile("|".join(_re.escape(word)
                          for word in sorted(replacements, key=len, reverse=True)))
    probe = (1999, 3, 17, 22, 44, 55, 2, 76, -1)
    templates = {code: pattern.sub(lambda match: replacements[match[0]],
                                   _time.strftime("%" + code, probe))
                 for code in ("c", "x", "X")}
    templates["r"] = "%I:%M:%S %p"
    return templates, words


@lru_cache(maxsize=128)
def _with_locale(fmt, current):
    templates, words = _locale_data(current)
    return _strptime_compile(fmt, templates, words)
