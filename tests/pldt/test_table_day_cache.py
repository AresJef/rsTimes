"""Independent datetime answers across repeated days and DST transitions."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from rstimes import Pldt


@pytest.mark.parametrize("zone", [None, "UTC", "America/New_York", "Europe/Dublin"])
@pytest.mark.parametrize("chunks", [False, True])
def test_tables_cache_calendar_days_without_caching_dst_or_clocks(zone, chunks):
    stamps = [
        "2024-03-10T06:30:00", "2024-03-10T07:30:00", None,
        "2024-03-10T07:45:00", "2024-03-10T06:30:00",
        "2024-10-27T00:30:00", "2024-10-27T01:30:00",
        "2021-01-01T12:34:56", "2020-12-31T23:59:59",
        "2024-03-10T07:30:00",
    ]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    instants = [None if value is None else datetime.fromisoformat(value).replace(tzinfo=timezone.utc) for value in stamps]
    values = [None if value is None else int((value - epoch).total_seconds()) * 1_000_000_000 + 123 for value in instants]
    raw = pl.Series("time", values, dtype=pl.Int64).cast(pl.Datetime("ns", zone))
    if chunks:
        raw = pl.concat([raw.head(2), raw.slice(2, 4), raw.slice(6)], rechunk=False)
    x = Pldt(raw)
    local = [None if value is None else value if zone is None else value.astimezone(ZoneInfo(zone)) for value in instants]
    iso = [None if value is None else dict(zip(("year", "week", "day"), value.isocalendar())) for value in local]
    expected = []
    # These are the canonical negative-DST rules explicitly agreed for Dublin;
    # the host's system TZif may instead encode Ireland's winter as standard.
    dublin_dst = [1, 1, None, 1, 1, 0, 1, 1, 1, 1]
    for index, value in enumerate(local):
        if value is None:
            expected.append(None)
            continue
        fields = list(value.timetuple())
        fields[8] = (-1 if zone in (None, "UTC") else dublin_dst[index]
                     if zone == "Europe/Dublin" else int(value.dst() != timedelta(0)))
        expected.append(dict(zip(("tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec", "tm_wday", "tm_yday", "tm_isdst"), fields)))
    assert x.isocalendar().to_list() == iso
    actual = x.timedf().to_dicts()
    assert actual == [dict.fromkeys(expected[0]) if row is None else row for row in expected]
    expressions = raw.to_frame().lazy().select(
        pl.col("time").pldt.isocalendar().alias("iso"),
        pl.col("time").pldt.timedf().alias("clock"),
    ).collect()
    assert expressions["iso"].to_list() == iso
    assert expressions["clock"].to_list() == expected
