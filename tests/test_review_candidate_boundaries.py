"""Independent behavior controls for the bounded full-review candidates."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone, tzinfo
from fractions import Fraction
from importlib import resources
import pickle
import sysconfig
from threading import Event
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from rstimes import Configs, Pydt


def test_configs_serialization_captures_one_atomic_vocabulary():
    left, right = {"flip": 1, "flop": 2}, {"flip": 3, "flop": 4}
    cfg = Configs()
    cfg.set_month(left)
    old = cfg.month
    old["flip"] = 12
    assert cfg.month == left
    snapshot = cfg.__reduce__()[2]
    serialized = pickle.dumps(cfg)
    entered, release = Event(), Event()

    class MonthIndex:
        def __index__(self):
            entered.set()
            assert release.wait(10)
            return right["flip"]

    with ThreadPoolExecutor(max_workers=1) as pool:
        writer = pool.submit(cfg.set_month, {"flip": MonthIndex(), "flop": right["flop"]})
        try:
            assert entered.wait(10)
            if sysconfig.get_config_var("Py_GIL_DISABLED"):
                for serialize in (cfg.__reduce__, lambda: pickle.dumps(cfg)):
                    with pytest.raises(RuntimeError, match="concurrent business editing/reading overlaps"):
                        serialize()
            else:
                assert cfg.__reduce__()[2] == snapshot
                assert pickle.loads(pickle.dumps(cfg)).month == left
        finally:
            release.set()
        assert writer.result(timeout=10) is True

    assert cfg.month == right and cfg.__reduce__()[2][4][4] == right
    assert snapshot[4][4] == left and pickle.loads(serialized).month == left

    def read_months(_):
        return cfg.month, cfg.__reduce__()[2][4][4], pickle.loads(pickle.dumps(cfg)).month

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(read_months, range(16))) == [(right, right, right)] * 16


def test_calendar_owned_int64_survives_later_iterator_and_lazy_literal_edit():
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    years = np.array([2020, 2021], dtype="int64")
    year = pl.Series("year", years)
    assert np.shares_memory(year.to_numpy(allow_copy=False), years)

    class Days:
        calls = 0

        def __iter__(self):
            self.calls += 1
            years[:] = 2030
            return iter((60, 60))

    days = Days()
    result = Pldt.fromdayofyear(year, days, unit="ms")
    assert days.calls == 1 and years.tolist() == [2030, 2030]
    assert result.name == "year"
    assert result.to_physical().to_list() == [1582934400000, 1614556800000]

    raw = np.array([60, 61], dtype="int64")
    literal = pl.Series("doy", raw)
    assert np.shares_memory(literal.to_numpy(allow_copy=False), raw)
    expr = pl.col("year").pldt.fromdayofyear(literal, unit="ms")
    raw[:] = 1
    frame = pl.LazyFrame({"year": [2020, 2021]})
    materialized = frame.select(expr).collect()["year"]
    assert materialized.to_physical().to_list() == [1582934400000, 1614643200000]


def test_pddt_mixed_fixed_sources_keep_explicit_instant_and_real_protocol():
    pytest.importorskip("pandas")
    from rstimes import Pddt

    fixed = datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=2)))
    other = datetime(2024, 1, 1, tzinfo=timezone(timedelta(minutes=-90), "business name"))
    values = (fixed, other)
    target = Pddt(values, tz="UTC", unit="us")
    assert target.asi8.tolist() == [1704060000000000, 1704072600000000]
    assert str(target.tz) == "UTC"
    with pytest.raises(ValueError, match="explicit target tz"):
        Pddt(values, unit="us")

    marker = LookupError("real source offset")

    class BusinessZone(tzinfo):
        def utcoffset(self, value):
            raise marker

    failed = datetime(2024, 1, 1, tzinfo=BusinessZone())
    with pytest.raises(LookupError) as caught:
        Pddt((fixed, failed, other), tz="UTC", unit="us")
    assert caught.value is marker


@pytest.mark.parametrize("target", (None, "America/New_York"))
@pytest.mark.parametrize("ambiguous", ("raise", "infer"))
def test_pldt_rescales_native_aware_instants_without_localizing(target, ambiguous):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    source = pl.Series("utc_stamp", [-1000, None, 1704067200000000000],
                       dtype=pl.Datetime("ns", "UTC"))
    value = Pldt(source, tz=target, unit="us", ambiguous=ambiguous)
    assert value.to_physical().to_list() == [-1, None, 1704067200000000]
    assert value.dtype == pl.Datetime("us", target or "UTC")
    assert value.name == "utc_stamp"
    assert source.to_physical().to_list() == [-1000, None, 1704067200000000000]


def test_pldt_native_aware_rescale_keeps_early_policy_and_row_failures():
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    source = pl.Series("utc", [None, -1, -2], dtype=pl.Datetime("ns", "UTC"))
    with pytest.raises(ValueError, match=r"data\[1\].*precision"):
        Pldt(source, unit="us")
    with pytest.raises(ValueError, match="length"):
        Pldt(source, unit="us", ambiguous=[True])
    assert Pldt(source).as_unit("us", round_ok=True).to_physical().to_list() == [None, -1, -1]
    wide = pl.Series("utc", [0, None, 2**63 - 1], dtype=pl.Datetime("us", "UTC"))
    with pytest.raises(OverflowError, match=r"data\[2\].*capacity"):
        Pldt(wide, unit="ns")


def test_pldt_native_target_keeps_actual_zone_qualification():
    pytest.importorskip("polars")
    from rstimes import Pldt

    class Passive(ZoneInfo):
        pass

    class Business(ZoneInfo):
        def utcoffset(self, dt):
            return timedelta(hours=2)

    class Rebound(Business):
        utcoffset = ZoneInfo.utcoffset

    for zone in (ZoneInfo("UTC"), ZoneInfo.no_cache("UTC"), Passive("UTC")):
        out = Pldt([0], unit="ns", tz=zone)
        assert out.to_physical().to_list() == [0] and out.dtype.time_zone == "UTC"
    for zone in (Business("UTC"), Rebound("UTC")):
        with pytest.raises(ValueError):
            Pldt([0], unit="ns", tz=zone)
    tzdata = pytest.importorskip("tzdata")
    with resources.files(tzdata).joinpath("zoneinfo", "UTC").open("rb") as stream:
        file_zone = ZoneInfo.from_file(stream, key="UTC")
    with pytest.raises(ValueError):
        Pldt([], unit="ns", tz=file_zone)
    source = datetime(1970, 1, 1, tzinfo=Business("UTC"))
    assert Pldt([source], unit="ns", tz="UTC").to_physical().to_list() == [-7200000000000]


def test_scalar_seconds_keeps_coordinate_meaning():
    value = Pydt(1969, 12, 31, 23, 59, 59, 999940)
    assert value.toseconds() == -60 * 0.000001
    assert value.toseconds(utc=True) == -60 * 0.000001
    aware = value.replace(tzinfo=timezone(timedelta(minutes=330)))
    assert aware.toseconds() == value.toseconds()
    assert aware.toseconds(utc=True) == (-60 - 19800000000) * 0.000001


def test_column_seconds_keep_exact_rounding_and_missing():
    ticks = [-60, 0, 60]
    target = [float(Fraction(tick, 1000000)) for tick in ticks]
    pd = pytest.importorskip("pandas")
    pl = pytest.importorskip("polars")
    from rstimes import Pddt, Pldt

    result = Pddt(ticks + [None], unit="us").toseconds()
    assert result[:3].tolist() == target and pd.isna(result[3])
    result = Pldt(ticks + [None], unit="us").pldt.toseconds()
    assert result.dtype == pl.Float64 and result.to_list() == target + [None]


def test_pldt_dst_infer_keeps_independent_nulls_and_the_repeated_hour():
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    region = "America/New_York"
    source = pl.Series("when", [1704067200000000000, None], dtype=pl.Datetime("ns", "UTC"))
    result = Pldt(source, tz=region, unit="us", ambiguous="infer")
    assert result.name == "when"
    assert result.dtype == pl.Datetime("us", region)
    assert result.to_physical().to_list() == [1704067200000000, None]
    null = pl.Series("empty", [None, None], dtype=pl.Datetime("us"))
    assert Pldt(null, tz=region, unit="us", ambiguous="infer").to_physical().to_list() == [None, None]
    texts = pl.LazyFrame({"time": ["2024-11-03 01:30:00"] * 2})
    expr = pl.col("time").pldt.parse(tz=region, unit="us", ambiguous="infer")
    assert texts.select(expr).collect()["time"].to_physical().to_list() == [
        1730611800000000, 1730615400000000
    ]


def test_regional_format_combines_wall_offset_and_name_on_real_collect():
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    date = Pldt([1730611800000000000,1730615400000000000,-1000000001,None],
                tz="America/New_York", unit="ns", name="stamp")
    expected = ["2024-11-03T01:30:00-04:00", "2024-11-03T01:30:00-05:00",
                "1969-12-31T18:59:58.999999999-05:00", None]
    assert date.pldt.isoformat().to_list() == expected
    expr = pl.col("stamp").pldt.strftime("%Y-%m-%d %H:%M:%S.%f %z %Z")
    result = date.to_frame().lazy().select(expr).collect()["stamp"]
    assert result.dtype == pl.String
    assert result.to_list() == [
        "2024-11-03 01:30:00.000000000 -0400 EDT",
        "2024-11-03 01:30:00.000000000 -0500 EST",
        "1969-12-31 18:59:58.999999999 -0500 EST", None,
    ]
