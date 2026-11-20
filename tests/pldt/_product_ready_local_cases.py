"""Fresh-process PR-036 scenarios; no persistent cache resets or product patches."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from zoneinfo import TZPATH, ZoneInfo, ZoneInfoNotFoundError, reset_tzpath
import hashlib
import json
import os
import sys
import sysconfig

mode, first = sys.argv[1:]
os.environ["TZ"] = first
import polars as pl
from rstimes import Pldt, Pydt
from importlib.util import find_spec
if find_spec("pandas") is not None:
    from rstimes import Pddt
else:
    Pddt = None
import rstimes._localization as service
import rstimes._native as native

before = getattr(sys,"_is_gil_enabled",lambda:None)()
if sysconfig.get_config_var("Py_GIL_DISABLED"):
    assert before is False, "free-threaded child must start actual work without GIL"
WALL = datetime(2024,1,1)
checks = []


def expected(key):
    return WALL.replace(tzinfo=ZoneInfo(key)).timestamp()


def host():
    return service.local_timezone()


def timestamp():
    return Pldt([WALL],unit="us").timestamp().to_list()[0]


def matches(key):
    assert host().key == key
    assert Pydt(2024,1,1).astimezone().tzinfo.key == key
    assert timestamp() == expected(key)
    if Pddt is not None:
        assert Pddt([WALL],unit="us").timestamp().tolist() == [expected(key)]
    checks.append("both backends and direct consumers: "+key)


def value_error(call):
    try:call()
    except ValueError as error:return error
    raise AssertionError("expected actual local backend failure")


second = "UTC" if first != "UTC" else "Asia/Shanghai"
if mode in ("host_first","native_first","expression_first"):
    if mode == "host_first":assert host().key == first
    elif mode == "native_first":assert timestamp() == expected(first)
    else:expr = pl.col("seconds").pldt.fromtimestamp(unit="us")
    os.environ["TZ"] = second
    if mode == "expression_first":
        frame = pl.DataFrame({"seconds":[0,None]},schema={"seconds":pl.Int64})
        result = frame.lazy().select(expr).collect().to_series()
        offset = int(datetime(1970,1,1,tzinfo=ZoneInfo(first)).utcoffset().total_seconds()*10**6)
        assert result.to_physical().to_list() == [offset,None]
        empty = pl.DataFrame({"seconds":[]},schema={"seconds":pl.Int64}).lazy().select(expr).collect().to_series()
        assert empty.to_list() == [] and empty.dtype == pl.Datetime("us")
        checks.append("actual captured lazy collect including empty")
    matches(first)
elif mode in ("retry_host","retry_native"):
    os.environ["TZ"] = "rsTimes/AbsentLocal"
    value_error(host if mode == "retry_host" else timestamp)
    os.environ["TZ"] = first
    matches(first)
elif mode == "host_validation_precedes_publication":
    original = service.ZoneInfo
    error = ZoneInfoNotFoundError("host data unavailable")
    def unavailable(key):raise error
    service.ZoneInfo = unavailable
    failure = value_error(host)
    assert failure.__cause__ is error
    service.ZoneInfo = original
    os.environ["TZ"] = second
    matches(second)
elif mode == "native_success_host_unavailable":
    original = service.ZoneInfo
    calls = []
    def unavailable(key):
        calls.append(key)
        if key == first:raise ZoneInfoNotFoundError("host winner unavailable")
        return original(key)
    service.ZoneInfo = unavailable
    assert timestamp() == expected(first)
    assert calls == [], "native-only initialization must not validate Python backend"
    os.environ["TZ"] = second
    value_error(host)
    assert calls == [first]
    assert timestamp() == expected(first)
    service.ZoneInfo = original
    matches(first)
elif mode == "host_success_native_unavailable":
    # Genuine Python-only tzdb entry, not a mocked successful Rust parser.
    path = next((Path(p)/"UTC" for p in TZPATH if (Path(p)/"UTC").is_file()), None)
    data = path.read_bytes() if path else resources.files("tzdata.zoneinfo").joinpath("UTC").read_bytes()
    with TemporaryDirectory() as directory:
        name = "rsTimes/HostOnly"
        target = Path(directory)/name
        target.parent.mkdir()
        target.write_bytes(data)
        reset_tzpath([directory])
        os.environ["TZ"] = name
        captured = host()
        assert captured.key == name
        os.environ["TZ"] = first
        value_error(timestamp)
        assert host() is captured
        checks.append("native cannot replace already successful Python-only identity")
elif mode in ("host_loses_native","host_loses_host"):
    original = service.ZoneInfo
    ready, release = Event(), Event()
    result, errors = [], []
    def gated(key):
        value = original(key)
        if key == first:
            ready.set()
            if not release.wait(8):raise AssertionError("loser release deadline")
        return value
    service.ZoneInfo = gated
    def loser():
        try:result.append(host())
        except BaseException as error:errors.append(error)
    thread = Thread(target=loser,daemon=True)
    thread.start()
    assert ready.wait(8), "loser did not reach validated backend boundary"
    os.environ["TZ"] = second
    if mode == "host_loses_native":assert timestamp() == expected(second)
    else:assert host().key == second
    release.set()
    thread.join(8)
    assert not thread.is_alive() and not errors
    assert len(result) == 1 and result[0].key == second
    service.ZoneInfo = original
    assert host().key == second
    matches(second)
    checks.append("loser result and host lru use actual winner")
elif mode == "concurrent_same_name":
    def request(i):return host().key if i%2 else timestamp()
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(request,range(8)))
    assert result == [first if i%2 else expected(first) for i in range(8)]
    matches(first)
elif mode == "lazy_and_explicit":
    os.environ["TZ"] = "rsTimes/AbsentLocal"
    for values in ([],[None,None]):
        assert Pldt(values,unit="us").timestamp().to_list() == values
        assert Pldt(values,unit="us").is_past().to_list() == [False]*len(values)
        assert Pldt(values,unit="us").is_future().to_list() == [False]*len(values)
    for key in ("UTC","Etc/GMT-8"):
        assert Pldt([0],unit="us",tz=key).timestamp().to_list() == [0.0]
    result = pl.DataFrame({"seconds":[0]}).lazy().select(pl.col("seconds").pldt.fromtimestamp(tz="UTC",unit="us")).collect().to_series()
    assert result.to_physical().to_list() == [0]
    value_error(lambda:pl.col("seconds").pldt.fromtimestamp(unit="us"))
    os.environ["TZ"] = first
    matches(first)
else:raise ValueError(mode)

after = getattr(sys,"_is_gil_enabled",lambda:None)()
assert before == after, "GIL state changed during actual work"
print(json.dumps({"mode":mode,"first":first,"checks":checks,"native":native.__file__,"native_sha256":hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),"gil_before":before,"gil_after":after},ensure_ascii=True))
