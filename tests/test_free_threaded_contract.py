"""Protect real NoGIL imports, shared reads and callback-safe native boundaries.

The import test starts an unforced interpreter. Parallel correctness tests also
run on ordinary CPython; they make no unsupported throughput or speedup claim.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timedelta
from datetime import timezone
import json
from pathlib import Path
import pickle
import subprocess
import sys
import sysconfig
import threading

import pytest

from rstimes import Configs, Delta, Pydt, parse_str


@pytest.mark.skipif(not sysconfig.get_config_var("Py_GIL_DISABLED"),
                    reason="requires a free-threaded CPython build")
def test_complete_import_and_work_keep_unforced_gil_disabled():
    """Build capability and actual GIL state are independent acceptance facts."""
    pytest.importorskip("pandas", reason="four-class integration needs optional pandas")
    pytest.importorskip("polars", reason="four-class integration needs optional Polars")
    code = """
import os,sys,sysconfig,json
assert 'PYTHON_GIL' not in os.environ
assert sysconfig.get_config_var('Py_GIL_DISABLED') == 1
assert not sys._is_gil_enabled(), 'GIL already enabled before importing dependencies'
import numpy,pandas,polars
from rstimes import Configs,Delta,Pydt,Pddt,Pldt,parse_str
import rstimes._native as native
assert native._free_threaded_build() is True
assert not sys._is_gil_enabled(), 'a complete import re-enabled the GIL'
cfg=Configs()
assert parse_str('29 February 2024',cfg=cfg).isoformat()=='2024-02-29T00:00:00'
assert (Pydt(2024,1,31)+Delta(months=1)).isoformat()=='2024-02-29T00:00:00'
assert Pddt(['2024-01-31']).to_next_month().day.tolist()==[29]
assert Pldt(['2024-01-31']).to_next_month().dt.day().to_list()==[29]
assert not sys._is_gil_enabled(), 'actual work re-enabled the GIL'
print(json.dumps({'native':native.__file__,'gil_enabled':sys._is_gil_enabled()}))
"""
    import os
    env = dict(os.environ)
    env.pop("PYTHON_GIL", None)
    result = subprocess.run([sys.executable, "-I", "-c", code], env=env,
                            cwd=Path(sys.prefix), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["gil_enabled"] is False


@pytest.mark.skipif(not sysconfig.get_config_var("Py_GIL_DISABLED"),
                    reason="requires a free-threaded CPython build")
def test_core_import_and_work_keep_unforced_gil_disabled():
    """The core NoGIL contract never requires optional container dependencies."""
    code = """
import os,sys,sysconfig
assert 'PYTHON_GIL' not in os.environ and 'gil' not in sys._xoptions
assert sysconfig.get_config_var('Py_GIL_DISABLED') == 1
assert not sys._is_gil_enabled()
from rstimes import Configs,Delta,Pydt,parse_str
import rstimes._native as native
assert native._free_threaded_build() is True
assert parse_str('29 February 2024',cfg=Configs()).day == 29
assert (Pydt(2024,1,31)+Delta(months=1)).day == 29
assert not sys._is_gil_enabled()
"""
    import os
    env = dict(os.environ)
    env.pop("PYTHON_GIL", None)
    result = subprocess.run([sys.executable, "-I", "-c", code], env=env,
                            cwd=Path(sys.prefix), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_reports_its_actual_compiled_threading_abi():
    """Runtime GIL state alone cannot identify the installed binary's ABI."""
    import rstimes._native as native
    assert native._free_threaded_build() is bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_shared_cold_delta_hash_repr_and_state_are_consistent(workers):
    """Concurrent first publication must not mutate frozen values or state."""
    shared = Delta(days=1, nanoseconds=2)
    expected_hash = hash(Delta(days=1, nanoseconds=2))
    barrier = threading.Barrier(workers)

    def read():
        barrier.wait(timeout=10)
        for _ in range(80):
            assert (shared.days, shared.nanoseconds) == (1, 2)
            assert hash(shared) == expected_hash
            assert repr(shared) == "<'Delta' (days=1, nanoseconds=2)>"
            assert copy.copy(shared) == Delta(days=1, nanoseconds=2)
            assert pickle.loads(pickle.dumps(shared)) == Delta(days=1, nanoseconds=2)
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        assert all(pool.map(lambda _: read(), range(workers)))


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_shared_configs_first_display_and_parse_are_read_only(workers):
    """Internal cache initialization is not a conflicting business edit."""
    cfg = Configs()
    cfg.add_month("harvest", 10)
    barrier = threading.Barrier(workers)

    def read():
        barrier.wait(timeout=10)
        for _ in range(40):
            assert parse_str("7 harvest 2024", cfg=cfg) == datetime(2024, 10, 7)
            assert cfg.month["harvest"] == 10
            assert repr(cfg)
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        assert all(pool.map(lambda _: read(), range(workers)))


def test_parser_does_not_retain_a_configs_borrow_across_constructor_callback():
    """A real target-class callback may inspect the shared configuration again."""
    cfg = Configs()
    cfg.add_month("harvest", 10)
    visits = []

    class Date(datetime):
        def __new__(cls, *args, **kwargs):
            visits.append(cfg.month["harvest"])
            return super().__new__(cls, *args, **kwargs)

    result = parse_str("7 harvest 2024", cfg=cfg, dtclass=Date)
    assert type(result) is Date
    assert result == datetime(2024, 10, 7)
    assert visits == [10]


def test_configs_numeric_callback_can_reenter_the_same_instance():
    """An edit admission flag must not become a lock around user callbacks."""
    cfg = Configs()

    class Month:
        def __index__(self):
            cfg.add_weekday("workday", 2)
            assert cfg.weekday["workday"] == 2
            return 10

    assert cfg.add_month("harvest", Month()) is True
    assert cfg.month["harvest"] == 10
    assert cfg.weekday["workday"] == 2


def test_different_configs_instances_can_edit_in_overlapping_callbacks():
    """Per-instance business admission cannot serialize independent objects."""
    configs = [Configs(), Configs()]
    rendezvous = threading.Barrier(2)

    class Month:
        def __index__(self):
            rendezvous.wait(timeout=10)
            return 10

    def edit(cfg):
        assert cfg.add_month("harvest", Month()) is True
        return parse_str("7 harvest 2024", cfg=cfg)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(edit, configs)) == [datetime(2024, 10, 7)] * 2


@pytest.mark.skipif(not sysconfig.get_config_var("Py_GIL_DISABLED"),
                    reason="edit admission is specific to free-threaded builds")
def test_configs_overlapping_edit_reports_conflict_before_a_second_conversion():
    """The first edit remains valid; another thread cannot silently commit over it."""
    cfg = Configs()
    entered, release = threading.Event(), threading.Event()
    second_visits = []

    class Month:
        def __index__(self):
            entered.set()
            assert release.wait(timeout=10)
            return 10

    class Day:
        def __index__(self):
            second_visits.append(True)
            return 2

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cfg.add_month, "harvest", Month())
        try:
            assert entered.wait(timeout=10)
            with pytest.raises(RuntimeError, match="Configs.*concurrent"):
                _ = cfg.month
            with pytest.raises(RuntimeError, match="Configs.*concurrent"):
                parse_str("7 October 2024", cfg=cfg)
            with pytest.raises(RuntimeError, match="Configs.*concurrent"):
                cfg.add_weekday("workday", Day())
        finally:
            release.set()
        assert future.result(timeout=10) is True
    assert second_visits == []
    assert cfg.month["harvest"] == 10


@pytest.mark.parametrize("descriptor", [False, True])
def test_delta_special_method_reads_the_actual_mro_without_metaclass_hooks(descriptor):
    """A replacement __mro__ property cannot hide real arithmetic definitions."""
    visits = []

    class Meta(type):
        @property
        def __mro__(cls):
            raise AssertionError("user __mro__ property was consulted")

        def __getattribute__(cls, name):
            if name == "__dict__":
                raise AssertionError("user __dict__ hook was consulted")
            return super().__getattribute__(name)

    def equality(self, other):
        visits.append(other)
        return True

    class Equality:
        def __get__(self, value, owner):
            return lambda other: equality(value, other)

    class Child(Delta, metaclass=Meta):
        __eq__ = Equality() if descriptor else equality

    other = Delta(days=2)
    assert (Child(days=1) != other) is False
    assert visits == [other]


def test_two_constructor_callbacks_can_overlap_and_read_the_shared_configs():
    """No library-wide lock or mutable Configs borrow may enclose a callback."""
    cfg = Configs()
    cfg.add_month("harvest", 10)
    rendezvous = threading.Barrier(2)

    class Date(Pydt):
        def __new__(cls, *args, **kwargs):
            assert cfg.month["harvest"] == 10
            rendezvous.wait(timeout=10)
            return super().__new__(cls, *args, **kwargs)

    def construct(_):
        return parse_str("7 harvest 2024", cfg=cfg, dtclass=Date)

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(construct, range(2)))
    assert all(type(value) is Date and value == datetime(2024, 10, 7) for value in result)


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_stable_shared_date_columns_and_expression_execute_independently(workers):
    """All four classes retain precision and null positions under shared reads."""
    pd = pytest.importorskip("pandas")
    pl = pytest.importorskip("polars")
    from rstimes import Pddt, Pldt

    text = "2024-01-31T12:34:56.123456789"
    pandas_dates = Pddt([text, None], unit="ns")
    polars_dates = Pldt([text, None], unit="ns")
    frame = pl.DataFrame({"time": polars_dates})
    expression = pl.col("time").pldt.to_next_month()
    scalar = Pydt(2024, 1, 31, 12, 34, 56, 123456)
    delta = Delta(months=1)
    expected = datetime(2024, 2, 29, 12, 34, 56, 123456)
    epoch = datetime(1970, 1, 1)
    expected_ns = ((expected - epoch) // timedelta(microseconds=1)) * 1000 + 789
    barrier = threading.Barrier(workers)

    def calculate(_):
        barrier.wait(timeout=10)
        for _ in range(12):
            assert scalar + delta == expected
            shifted = pandas_dates.to_next_month()
            assert shifted.unit == "ns"
            assert shifted.asi8.tolist() == [expected_ns, pd.NaT.value]
            assert polars_dates.to_next_month().to_physical().to_list() == [expected_ns, None]
            assert frame.select(expression).to_series().to_physical().to_list() == [expected_ns, None]
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        assert all(pool.map(calculate, range(workers)))


@pytest.mark.parametrize("workers", [2, 4])
def test_shared_region_conversion_keeps_both_dst_instants_and_nanoseconds(workers):
    """Concurrent region preparation cannot conflate the two repeated clocks."""
    pd = pytest.importorskip("pandas")
    pl = pytest.importorskip("polars")
    from rstimes import Pddt, Pldt

    epoch = datetime(1970, 1, 1)
    early = ((datetime(2024, 11, 3, 5, 30) - epoch) // timedelta(seconds=1)) * 10**9 + 789
    late = early + 3600 * 10**9
    pandas_dates = Pddt([early, None, late], unit="ns", tz="UTC")
    polars_dates = Pldt([early, None, late], unit="ns", tz="UTC")
    frame = pl.DataFrame({"time": polars_dates})
    scalars = [Pydt(2024, 11, 3, hour, 30, tzinfo=timezone.utc) for hour in (5, 6)]
    barrier = threading.Barrier(workers)

    def convert(_):
        barrier.wait(timeout=10)
        for _ in range(8):
            values = [value.tz_convert("America/New_York") for value in scalars]
            assert [(v.hour, v.minute, v.fold, v.utcoffset()) for v in values] == [
                (1, 30, 0, timedelta(hours=-4)), (1, 30, 1, timedelta(hours=-5))]
            pandas_result = pandas_dates.tz_convert("America/New_York")
            assert pandas_result.asi8.tolist() == [early, pd.NaT.value, late]
            assert (pandas_result[0].fold, pandas_result[2].fold) == (0, 1)
            polars_result = polars_dates.tz_convert("America/New_York")
            assert polars_result.to_physical().to_list() == [early, None, late]
            expr = pl.col("time").pldt.tz_convert("America/New_York")
            result = frame.select(expr).to_series()
            assert result.to_physical().to_list() == [early, None, late]
            assert result.dt.strftime("%z").to_list() == ["-0400", None, "-0500"]
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        assert all(pool.map(convert, range(workers)))
