"""RV02 shared reads and real exporters, bounded by the existing test watchdog."""
from concurrent.futures import ThreadPoolExecutor
import threading

import numpy as np
import pytest

from _thread_case_watchdog import bounded_case


@pytest.mark.parametrize("workers", [2, 4])
@bounded_case(optional_modules=("polars",))
def test_rv02_actual_exporter_and_guard_are_safe_for_shared_reads(workers):
    pytest.importorskip("polars", reason="Pldt export integration requires optional Polars")
    from rstimes import Pldt

    class Neutral(Pldt):
        def __getattribute__(self, name):
            return super().__getattribute__(name)

    source = Neutral([1000, None, 3000], unit="ns")
    bad = Neutral([1], unit="ns")
    calls = 0
    lock = threading.Lock()

    class Business(Pldt):
        def to_numpy(self, **kwargs):
            nonlocal calls
            with lock:
                calls += 1
            return np.array([7, 8])

    business = Business([0, 1])

    def read(_):
        for _ in range(100):
            assert np.asarray(source, dtype="datetime64[us]").view("i8").tolist() == [1, -(1 << 63), 3]
            with pytest.raises(ValueError):
                np.asarray(bad, dtype="datetime64[us]")
            assert np.asarray(business, dtype=float).tolist() == [7., 8.]
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        assert list(executor.map(read, range(workers))) == [True] * workers
    assert calls == workers * 100
    assert source.to_physical().to_list() == [1000, None, 3000]
    assert bad.to_physical().to_list() == [1]
