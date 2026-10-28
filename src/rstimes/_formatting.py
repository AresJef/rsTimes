"""Shared pure-format preparation; word meanings remain native call inputs."""
from functools import lru_cache
import locale as _locale
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
    if not hasattr(_locale, "nl_langinfo"):
        raise _own_error(NotImplementedError(
            "this platform does not expose LC_TIME format templates; use explicit date directives"
        ))
    try:
        templates = {key: _locale.nl_langinfo(getattr(_locale, name)) for key, name in
            (("c", "D_T_FMT"), ("x", "D_FMT"), ("X", "T_FMT"), ("r", "T_FMT_AMPM"))}
        words = {
            "b": [(_locale.nl_langinfo(getattr(_locale, f"ABMON_{i}")), i) for i in range(1, 13)],
            "B": [(_locale.nl_langinfo(getattr(_locale, f"MON_{i}")), i) for i in range(1, 13)],
            "a": [(_locale.nl_langinfo(getattr(_locale, f"ABDAY_{i}")), (i+5)%7) for i in range(1, 8)],
            "A": [(_locale.nl_langinfo(getattr(_locale, f"DAY_{i}")), (i+5)%7) for i in range(1, 8)],
            "p": [(_locale.nl_langinfo(_locale.AM_STR), 0), (_locale.nl_langinfo(_locale.PM_STR), 1)],
        }
        after = _locale.setlocale(_locale.LC_TIME)
    except Exception as error:
        raise _external_error(error)
    if after != current:
        raise _own_error(RuntimeError("LC_TIME changed while preparing format data; retry after locale settings are stable"))
    return templates, words


@lru_cache(maxsize=128)
def _with_locale(fmt, current):
    templates, words = _locale_data(current)
    return _strptime_compile(fmt, templates, words)
