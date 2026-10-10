"""Run with the clean wheel environment's Python -I; fail on native regressions."""
import argparse
import copy
from datetime import date, datetime
import json
from pathlib import Path
import pickle
import platform
import sys
import sysconfig

parser = argparse.ArgumentParser()
parser.add_argument("--require-macos-arm64-313", action="store_true")
args = parser.parse_args()
if args.require_macos_arm64_313:
    assert sys.platform == "darwin" and platform.machine() == "arm64"
    assert sys.version_info[:2] == (3, 13)
    assert not sysconfig.get_config_var("Py_GIL_DISABLED")

import numpy as np
from dateutil.relativedelta import relativedelta
import rstimes
from rstimes import Delta, from_unix_ms, to_unix_ms
import rstimes._native as native

assert Path(rstimes.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert Path(native.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert Path(native.__file__).suffix in (".so", ".pyd") and native.release_build()
assert date(2024, 1, 31) + Delta(months=1) == date(2024, 2, 29)
negative = Delta(microseconds=-1)
assert (negative.days, negative.hours, negative.minutes, negative.seconds,
        negative.microseconds) == (-1, 23, 59, 59, 999999)
assert Delta.from_relativedelta(relativedelta(months=1)) == Delta(months=1)
assert np.datetime64(-1, "us") + Delta(microseconds=1) == datetime(1970, 1, 1)
assert pickle.loads(pickle.dumps(negative, protocol=5)) == negative
assert copy.deepcopy(negative) == negative
try:
    Delta(weeks=2**31-1)
except OverflowError:
    pass
else:
    raise AssertionError("Intermediate overflow was accepted")
assert to_unix_ms(from_unix_ms(-1)) == -1
assert from_unix_ms(0).isoformat() == "1970-01-01T00:00:00+00:00"
print(json.dumps({"status": "passed", "package": rstimes.__file__,
                  "native": native.__file__, "release": True,
                  "python": platform.python_version(), "machine": platform.machine()}))
