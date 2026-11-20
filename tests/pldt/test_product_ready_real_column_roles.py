"""PR-034: the same real column roles reach the same native preparation."""
from collections.abc import Mapping
from datetime import date, datetime

import numpy as np
import polars as pl
import pytest
from rstimes import Delta, Pldt


DAY = 86_400_000_000
DATES = [datetime(2024, 1, 1), datetime(2024, 1, 2)]
TICKS = [19723 * DAY, 19724 * DAY]


def source(raw, storage, mode, events):
    class PassiveArray(np.ndarray):
        pass
    class PassiveSeries(pl.Series):
        pass
    class DisplayArray(np.ndarray):
        @property
        def __class__(self):
            events.append("display")
            return pl.DataFrame
    class DisplaySeries(pl.Series):
        @property
        def __class__(self):
            events.append("display")
            return pl.DataFrame
    if storage == "numpy":
        if mode == "ordinary":
            return raw
        return raw.view(PassiveArray if mode == "passive" else DisplayArray)
    cls = pl.Series if mode == "ordinary" else PassiveSeries if mode == "passive" else DisplaySeries
    if raw.dtype.kind == "O" and all(type(value) is Delta for value in raw):
        return cls("input", list(raw), dtype=pl.Object)
    return cls("input", raw)


def call_role(role, value):
    base = Pldt(DATES, unit="us")
    if role == "constructor":
        return Pldt(value, unit="us")
    if role in ("fromseconds", "frommicroseconds", "fromordinal", "fromisoformat"):
        return getattr(Pldt, role)(value, unit="us")
    if role == "strptime":
        return Pldt.strptime(value, "%Y-%m-%d", unit="us")
    if role == "combine":
        return Pldt.combine(value, None, unit="us")
    if role == "is_month":
        return base.is_month(value)
    if role == "to_month":
        return base.to_month(value)
    if role == "diff":
        return base.pldt.diff(value, "s")
    expr = pl.col("clock").pldt.is_month(value) if role == "is_month_expr" else pl.col("clock").pldt.diff(value, "s")
    return pl.DataFrame({"clock": base}).lazy().select(expr).collect().to_series()


@pytest.mark.parametrize("storage", ("numpy", "polars"))
@pytest.mark.parametrize("mode", ("ordinary", "passive", "display"))
@pytest.mark.parametrize("role", (
    "constructor", "fromseconds", "frommicroseconds", "fromordinal", "fromisoformat",
    "strptime", "combine", "is_month", "to_month", "diff", "is_month_expr", "diff_expr"))
def test_twelve_roles_use_real_source_and_independent_values(role, mode, storage):
    text_roles = ("fromisoformat", "strptime", "combine")
    raw = np.array(["2024-01-01", "2024-01-02"]) if role in text_roles else np.array(
        [719163, 719164] if role == "fromordinal" else [1, 2] if role in ("is_month", "to_month", "is_month_expr") else [0, 1])
    expected = {
        "constructor": [0, 1], "fromseconds": [0, 1_000_000], "frommicroseconds": [0, 1],
        "fromordinal": [0, DAY], "fromisoformat": TICKS, "strptime": TICKS, "combine": TICKS,
        "is_month": [True, False], "is_month_expr": [True, False],
        "to_month": [(19723 + 31) * DAY, (19724 + 60) * DAY],
        "diff": [TICKS[0] // 1_000_000, TICKS[1] // 1_000_000 - 1],
        "diff_expr": [TICKS[0] // 1_000_000, TICKS[1] // 1_000_000 - 1],
    }[role]
    events = []
    result = call_role(role, source(raw, storage, mode, events))
    assert result.to_physical().to_list() == expected
    assert result.dtype == (pl.Boolean if role.startswith("is_month") else pl.Int64 if role.startswith("diff") else pl.Datetime("us"))
    assert events == []


@pytest.mark.parametrize("storage", ("numpy", "polars"))
@pytest.mark.parametrize("mode", ("ordinary", "passive", "display"))
@pytest.mark.parametrize("entry", ("fromdate", "fromdatetime"))
def test_adjacent_real_date_factories_keep_existing_domains(entry, mode, storage):
    values = [date(2024, 1, 1), date(2024, 1, 2)] if entry == "fromdate" else DATES
    events = []
    raw = np.array(values, dtype=object)
    result = getattr(Pldt, entry)(source(raw, storage, mode, events), unit="us")
    assert result.to_physical().to_list() == TICKS
    assert events == []


@pytest.mark.parametrize("mode", ("ordinary", "passive", "display"))
def test_numpy_date_factory_keeps_numpy_only_domain(mode):
    events = []
    raw = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[us]")
    result = Pldt.fromdatetime64(source(raw, "numpy", mode, events), unit="us")
    assert result.to_physical().to_list() == TICKS and events == []
    with pytest.raises(TypeError, match="NumPy"):
        Pldt.fromdatetime64(source(raw, "polars", mode, events), unit="us")


@pytest.mark.parametrize("storage", ("numpy", "polars"))
@pytest.mark.parametrize("mode", ("ordinary", "passive", "display"))
@pytest.mark.parametrize("kind", ("delta", "duration", "date"))
def test_real_temporal_arithmetic_reuses_existing_native_domains(kind, mode, storage):
    if kind == "delta":
        raw = np.array([Delta(days=1), Delta(days=2)], dtype=object)
    elif kind == "duration":
        raw = np.array([1, 2], dtype="timedelta64[D]")
        if storage == "polars":
            raw = raw.astype("timedelta64[us]")
    else:
        raw = np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[us]")
    events = []
    other = source(raw, storage, mode, events)
    base = Pldt(DATES, unit="us")
    result = base - other if kind == "date" else base + other
    assert result.to_physical().to_list() == ([0, 0] if kind == "date" else [TICKS[0] + DAY, TICKS[1] + 2 * DAY])
    assert events == []


@pytest.mark.parametrize("role", (
    "constructor", "fromseconds", "fromordinal", "fromisoformat", "strptime", "combine",
    "is_month", "to_month", "diff", "is_month_expr", "diff_expr"))
@pytest.mark.parametrize("bad", ("frame", "lazy", "mapping", "registered", "set"))
def test_real_rejected_container_roles_and_mapping_registration_remain(role, bad):
    class Registered(list):
        pass
    Mapping.register(Registered)
    values = {
        "frame": pl.DataFrame({"x": [1, 2]}), "lazy": pl.DataFrame({"x": [1, 2]}).lazy(),
        "mapping": {"x": 1}, "registered": Registered([1, 2]), "set": {1, 2},
    }
    with pytest.raises(TypeError):
        call_role(role, values[bad])


@pytest.mark.parametrize("kind", ("delta", "date", "datetime", "integer", "native_ns"))
def test_business_column_snapshot_keeps_native_owner_and_skips_unrelated_callbacks(kind):
    from rstimes._polars import plain_series
    events = []
    class Business(pl.Series):
        def __getattribute__(self, name):
            if name == "_s" and armed:
                events.append("owner")
            return super().__getattribute__(name)
        def clone(self):
            raise AssertionError("business clone is not an input-reading protocol")
        def to_frame(self, *args, **kwargs):
            raise AssertionError("business to_frame must not be dispatched")
        @classmethod
        def _from_pyseries(cls, *args):
            raise AssertionError("business construction must not be dispatched")
    armed = False
    values, dtype = {
        "delta": ([Delta(days=1), None], pl.Object),
        "date": ([date(2024, 1, 1), None], pl.Object),
        "datetime": ([DATES[0], None], pl.Object),
        "integer": ([1, None], pl.Object),
        "native_ns": ([-2**63, None], pl.Datetime("ns")),
    }[kind]
    original = Business("clock", values, dtype=dtype)
    armed = True
    result = plain_series(original)
    assert events == ["owner"]
    assert type(result) is pl.Series and result.dtype == dtype and result.name == "clock"
    assert result.to_physical().to_list() == ([-2**63, None] if kind == "native_ns" else values)
    pl.Series.append(original, pl.Series("clock", values, dtype=dtype))
    assert len(original) == 4 and len(result) == 2
    assert result.null_count() == 1


def test_business_column_owner_failure_keeps_original_exception():
    from rstimes._polars import plain_series
    sentinel = LookupError("original native owner getter")
    events = []
    class Business(pl.Series):
        def __getattribute__(self, name):
            if name == "_s" and armed:
                events.append("owner")
                raise sentinel
            return super().__getattribute__(name)
    armed = False
    source_value = Business("clock", [1], dtype=pl.Object)
    armed = True
    with pytest.raises(LookupError) as caught:
        plain_series(source_value)
    assert caught.value is sentinel and events == ["owner"]
