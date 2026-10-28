"""Run with the clean wheel environment's Python -I; fail on native regressions."""
import argparse
import copy
from datetime import date, datetime
import hashlib
from importlib.metadata import distribution, version
import json
from pathlib import Path
import pickle
import platform
import sys
import sysconfig

parser = argparse.ArgumentParser()
parser.add_argument("--require-macos-arm64-313", action="store_true")
parser.add_argument("--expect-version")
parser.add_argument("--with-pandas", action="store_true")
parser.add_argument("--with-polars", action="store_true")
args = parser.parse_args()
if args.require_macos_arm64_313:
    assert sys.platform == "darwin" and platform.machine() == "arm64"
    assert sys.version_info[:2] == (3, 13)
    assert not sysconfig.get_config_var("Py_GIL_DISABLED")

import numpy as np
from dateutil.relativedelta import relativedelta
import rstimes
from rstimes import Configs, Delta, Pydt, parse, parse_str, parse_to_epoch, from_unix_ms, to_unix_ms
import rstimes._native as native

assert Path(rstimes.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert Path(native.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert Path(native.__file__).suffix in (".so", ".pyd") and native.release_build()
if args.expect_version:
    assert version("rsTimes") == args.expect_version
package = Path(rstimes.__file__).parent
payload_sha256 = {}
source_package = Path(__file__).resolve().parents[1] / "src/rstimes"
for source in source_package.iterdir():
    if source.is_file() and source.suffix not in (".so", ".pyd", ".pyc"):
        installed = package / source.name
        assert installed.read_bytes() == source.read_bytes(), source.name
        payload_sha256[source.name] = hashlib.sha256(installed.read_bytes()).hexdigest()
for filename in ("__init__.pyi", "delta.pyi", "errors.pyi", "parser.pyi", "pydt.pyi", "pddt.pyi", "py.typed", "_localization_sources.json"):
    assert (package / filename).is_file(), filename
installed_files = [str(path) for path in distribution("rsTimes").files]
for filename in ("LICENSE", "NOTICE", "NOTICE-CPYTHON.txt", "NOTICE-UNICODE.txt", "NOTICE-IANA-TIME-ZONE.txt", "NOTICE-RUST-STDLIB.html"):
    assert any(path.endswith("/" + filename) for path in installed_files), filename
assert date(2024, 1, 31) + Delta(months=1) == date(2024, 2, 29)
negative = Delta(microseconds=-1)
assert (negative.days, negative.hours, negative.minutes, negative.seconds,
        negative.microseconds) == (-1, 23, 59, 59, 999999)
assert Delta.from_relativedelta(relativedelta(months=1)) == Delta(months=1)
assert np.datetime64(-1, "us") + Delta(microseconds=1) == datetime(1970, 1, 1)
assert pickle.loads(pickle.dumps(negative, protocol=5)) == negative
assert copy.deepcopy(negative) == negative
assert Delta(weeks=2**31-1).days == 15_032_385_529
try:
    Delta(weeks=2**63)
except OverflowError:
    pass
else:
    raise AssertionError("Real duration overflow was accepted")
assert to_unix_ms(from_unix_ms(-1)) == -1
assert from_unix_ms(0).isoformat() == "1970-01-01T00:00:00+00:00"
assert parse_str("2024-01-02T12:34+08:00", ignoretz=False).isoformat() == "2024-01-02T12:34:00+08:00"
assert parse_str("2024-02-30") == datetime(2024, 2, 29)
try:
    parse_str("2024-02-30", strict=True)
except ValueError:
    pass
else:
    raise AssertionError("Strict parsing accepted an invalid date")
assert parse(date(2024, 2, 29)) == datetime(2024, 2, 29)
assert parse_to_epoch(1e-9, unit="ns") == 1
assert parse_to_epoch(np.datetime64(-1, "ns"), unit="ns") == -1
for number in (True, np.bool_(False)):
    try:
        parse(number)
    except TypeError:
        pass
    else:
        raise AssertionError("A boolean was treated as epoch seconds")
cfg = Configs()
cfg.add_month("releasemonth", 2)
assert parse_str("29 releasemonth 2024", cfg=cfg) == datetime(2024, 2, 29)
cfg.add_tzone("Asia/Shanghai")
assert parse_str("2024-01-02 12:00 Asia/Shanghai", cfg=cfg, ignoretz=False).utcoffset().total_seconds() == 28_800
assert parse_str("29 releasemonth 2024", cfg=pickle.loads(pickle.dumps(cfg))) == datetime(2024, 2, 29)
assert issubclass(Pydt, datetime)
assert Pydt(2024, 1, 31).add(months=1) == datetime(2024, 2, 29)
assert Pydt(2024, 1, 2).weekday() == 1
assert Pydt(2024, 2, 29).month_name("en_US") == "February"
try:
    Pydt(2024, 3, 10, 2, 30, tzinfo="America/New_York")
except ValueError:
    pass
else:
    raise AssertionError("Pydt accepted a nonexistent regional time")
if args.with_pandas:
    import pandas as pd
    from rstimes import Pddt
    assert issubclass(Pddt, pd.DatetimeIndex)
    values = Pddt(["2024-01-31T12:30:00.123456789", None], unit="ns", name="events")
    result = values + Delta(months=1)
    assert type(result) is Pddt and result.unit == "ns" and result.name == "events"
    assert result[0].isoformat() == "2024-02-29T12:30:00.123456789"
    assert result.isna().tolist() == [False, True]
    assert Pddt(["0000-01-01"], unit="us").year.tolist() == [0]
    assert Pddt.strptime(["202411-01-03"], "%Y11-%m-%d", unit="us").year.tolist() == [2024]
    assert Pddt.date_range("2024-01-01", periods=3, freq="D", unit="us").day.tolist() == [1, 2, 3]
    assert Pddt(["2024-11-03 01:30"], tz="America/New_York", ambiguous=False)[0].fold == 1
if args.with_polars:
    import polars as pl
    from rstimes import Pddt
    column = pl.Series("events", [1, None], dtype=pl.Int64).cast(pl.Datetime("ns"))
    result = Pddt(column)
    assert result.unit == "ns" and result.asi8[0] == 1 and result.isna().tolist() == [False, True]
print(json.dumps({"status": "passed", "package": rstimes.__file__,
                  "native": native.__file__, "release": True,
                  "version": version("rsTimes"),
                  "native_sha256": hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
                  "python_payload_sha256": payload_sha256,
                  "pandas_checked": args.with_pandas, "polars_checked": args.with_polars,
                  "python": platform.python_version(), "machine": platform.machine()}))
