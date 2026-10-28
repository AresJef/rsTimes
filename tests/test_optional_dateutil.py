"""Keep core use independent of dateutil without changing real integrations.

Each scenario uses a fresh installed-package process. The import finder makes
absence or a broken provider deterministic even in the full integration lane;
release CI additionally runs these cases in genuinely minimal environments.
"""
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


BOOTSTRAP = """
import importlib.abc
import sys

blocked = {"dateutil", "pandas", "polars"}
attempts = []

class Missing(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            attempts.append(fullname)
            raise ModuleNotFoundError("No module named " + repr(fullname),
                                      name=fullname.split(".", 1)[0])

sys.meta_path.insert(0, Missing())
"""


def installed_process(source):
    """Execute assertions through a clean interpreter, outside the source tree."""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", textwrap.dedent(source)],
        cwd=Path(sys.prefix), text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_without_dateutil_pandas_or_polars():
    installed_process(BOOTSTRAP + """
from datetime import datetime, date, timezone
import copy, pickle
from rstimes import Configs, Delta, Pydt, parse, parse_str, parse_to_epoch
cfg = Configs()
cfg.add_month("ownmonth", 2)
assert parse_str("29 ownmonth 2024", cfg=cfg) == datetime(2024, 2, 29)
assert parse_str("2024-02-30") == datetime(2024, 2, 29)
try:
    parse_str("2024-02-30", strict=True)
except ValueError:
    pass
else:
    raise AssertionError("strict accepted an invalid date")
assert parse(date(2024, 1, 2)) == datetime(2024, 1, 2)
assert parse_to_epoch(1e-9, unit="ns") == 1
assert Pydt(2024, 1, 31) + Delta(months=1) == datetime(2024, 2, 29)
assert copy.deepcopy(Delta(days=1)) == Delta(days=1)
assert pickle.loads(pickle.dumps(cfg)).month == cfg.month
assert not any(name in sys.modules for name in blocked)
""")


def test_missing_dateutil_keeps_unknown_operand_negotiation():
    installed_process(BOOTSTRAP + """
from rstimes import Delta, Pydt
delta = Delta(days=1)
assert delta.__add__(object()) is NotImplemented
assert delta.__radd__(object()) is NotImplemented
assert delta.__sub__(object()) is NotImplemented
assert delta.__rsub__(object()) is NotImplemented
class Right:
    def __radd__(self, value):
        return "right"
assert delta + Right() == "right"
assert Pydt(2024, 1, 1) + Right() == "right"
try:
    delta + object()
except TypeError as error:
    assert "dateutil" not in str(error)
else:
    raise AssertionError("unsupported operand was accepted")
""")


@pytest.mark.parametrize("entry", ["Configs.from_parserinfo", "Delta.from_relativedelta"])
def test_explicit_adapter_reports_missing_dependency(entry):
    installed_process(BOOTSTRAP + """
from rstimes import Configs, Delta
entry = """ + repr(entry) + """
owner, method = entry.split(".")
try:
    getattr({"Configs": Configs, "Delta": Delta}[owner], method)(object())
except ImportError as error:
    assert entry in str(error)
    assert "rstimes[dateutil]" in str(error)
    assert error.args == (str(error),)
else:
    raise AssertionError("missing explicit integration was not reported")
""")


def test_absent_dateutil_is_prepared_once():
    installed_process(BOOTSTRAP + """
from rstimes import Configs, Delta
initial = len([name for name in attempts if name == "dateutil"])
assert initial == 1
for _ in range(10):
    assert Delta().__add__(object()) is NotImplemented
    for call in (lambda: Configs.from_parserinfo(object()),
                 lambda: Delta.from_relativedelta(object())):
        try:
            call()
        except ImportError:
            pass
        else:
            raise AssertionError("missing adapter was accepted")
assert len([name for name in attempts if name == "dateutil"]) == initial
""")


def test_polars_epoch_adapter_does_not_require_dateutil():
    pytest.importorskip("polars")
    installed_process(BOOTSTRAP.replace(
        '{"dateutil", "pandas", "polars"}', '{"dateutil", "pandas"}'
    ) + """
import polars as pl
from rstimes import parse_to_epoch
value = 1704164645123456789
series = pl.Series("event", [value], dtype=pl.Int64).cast(pl.Datetime("ns"))
assert parse_to_epoch(series, unit="ns") == value
assert "dateutil" not in sys.modules and "pandas" not in sys.modules
""")


@pytest.mark.parametrize("kind", ["runtime", "import", "nested_missing"])
def test_broken_dateutil_is_not_treated_as_absent(kind):
    installed_process("""
import importlib.abc
import sys
kind = """ + repr(kind) + """
marker = (RuntimeError("dateutil initialization failed") if kind == "runtime"
          else ImportError("dateutil provider failed") if kind == "import"
          else ModuleNotFoundError("dateutil internal dependency failed",
                                   name="provider_internal_dependency"))
class Broken(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "dateutil":
            raise marker
        if fullname in {"pandas", "polars"}:
            raise ModuleNotFoundError("not installed", name=fullname)
sys.meta_path.insert(0, Broken())
try:
    import rstimes
except BaseException as error:
    assert error is marker, (type(error), str(error))
else:
    raise AssertionError("a broken provider was hidden")
""")
