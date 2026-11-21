"""Shared optional dependencies, resolved once when their adapter is loaded."""

import sys
from typing import Literal

try:
    import pandas as PANDAS
except ModuleNotFoundError as error:
    if error.name != "pandas":
        raise
    PANDAS = None

try:
    import polars as POLARS
except ModuleNotFoundError as error:
    if error.name != "polars":
        raise
    POLARS = None

HAS_POLARS = POLARS is not None
HAS_PANDAS = PANDAS is not None
PANDAS_TIMESTAMP = PANDAS.Timestamp if PANDAS is not None else None
PANDAS_TIMEDELTA = PANDAS.Timedelta if PANDAS is not None else None
PANDAS_NAT_TYPE = type(PANDAS.NaT) if PANDAS is not None else None
POLARS_SERIES = POLARS.Series if POLARS is not None else None
# Prepare this upstream compatibility fact once, alongside the real type objects.
PANDAS_REPLACE_NEEDS_TAIL = PANDAS is not None and PANDAS.__version__.split(".", 1)[0] == "2"

# Retain the same type objects on both sides of the Python/Rust boundary.
# This extension has finished initialization before the shared adapter is loaded.
from ._native import _configure_optional

_configure_optional(
    PANDAS_TIMESTAMP, PANDAS_TIMEDELTA, PANDAS_NAT_TYPE, POLARS_SERIES,
    PANDAS_REPLACE_NEEDS_TAIL,
)


def _minimum_dependency_version(
    package: Literal["pandas", "polars"], python_version: tuple[int, int],
    sys_platform: str, platform_machine: str,
) -> str:
    """Select the floor declared by the package's installation extra."""
    if package == "polars":
        return "2.0.0"
    if python_version >= (3, 15) or (sys_platform == "win32" and platform_machine == "ARM64"):
        return "3.0.6"
    return "2.3.3"


def _warn_dependency_version(package: Literal["pandas", "polars"], actual: str) -> None:
    """Check a successfully loaded dependency at its adapter's import boundary."""
    from packaging.version import Version

    python_version = (sys.version_info.major, sys.version_info.minor)
    architecture = ""
    if package == "pandas" and python_version < (3, 15) and sys.platform == "win32":
        from platform import machine

        architecture = machine()
    minimum = _minimum_dependency_version(package, python_version, sys.platform, architecture)
    if Version(actual) >= Version(minimum):
        return

    from importlib import __file__ as importlib_file
    from os import sep
    from pathlib import Path
    from warnings import warn

    from .errors import DependencyWarning

    adapter, label = ("Pddt", "pandas") if package == "pandas" else ("Pldt", "Polars")
    warn(
        f"{adapter} is using {label} {actual}, below the supported minimum of {minimum} "
        "for this environment. Some operations may fail or produce unexpected results. "
        f'To upgrade, run `python -m pip install "rsTimes[{package}]"`.',
        DependencyWarning,
        # CPython 3.13 excludes the last filename character when matching a prefix.
        skip_file_prefixes=(str(Path(__file__).parent) + sep, importlib_file[:-1]),
    )
