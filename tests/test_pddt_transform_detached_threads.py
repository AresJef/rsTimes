"""Shared large Pddt reads finish inside the established process watchdog."""
from concurrent.futures import ThreadPoolExecutor
import sys
import threading

import pytest

from _thread_case_watchdog import bounded_case, stage


@pytest.mark.parametrize("workers", [1, 2, 4])
@pytest.mark.parametrize("unit", ["us", "ns"])
@bounded_case(optional_modules=("pandas",))
def test_shared_large_public_transforms_and_errors_complete_in_real_callers(workers, unit):
    np = pytest.importorskip("numpy", reason="Pddt requires optional NumPy")
    from rstimes import Pddt

    size = 65536
    original = np.array(["2024-01-31T12:34:56.123456789", "NaT", "2024-03-31T01:02:03.000000001"], dtype="datetime64[ns]").astype(f"datetime64[{unit}]")
    answer = np.array(["2024-02-29T12:34:56.123456789", "NaT", "2024-04-30T01:02:03.000000001"], dtype="datetime64[ns]").astype(f"datetime64[{unit}]")
    source = Pddt(np.resize(original, size), name="shared")
    before = source.asi8.copy()
    expected = np.resize(answer, size).view("i8")
    error_source = Pddt(np.zeros(size, dtype="i8"), unit="us")
    years = np.zeros(size, dtype="i8")
    years[-1] = (1 << 63)-1
    nanos = np.zeros(size, dtype="i8")
    nanos[0] = 1
    gate = threading.Barrier(workers + 1)
    gil_before = getattr(sys, "_is_gil_enabled", lambda: None)()

    def read():
        ident = threading.get_ident()
        gate.wait(timeout=15)
        stage("large public transform callers passed ready gate")
        result = source.add(months=1)
        assert type(result) is Pddt and result.unit == unit and result.name == "shared"
        assert result.tz is None and np.array_equal(result.asi8, expected)
        del result
        with pytest.raises(OverflowError) as error:
            error_source.add(years=years, nanoseconds=nanos)
        assert str(error.value) == f"Pddt.add(): result[{size-1}]: integer overflow in Delta date arithmetic"
        return ident

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(read) for _ in range(workers)]
        gate.wait(timeout=15)
        callers = [future.result(timeout=20) for future in futures]
    assert len(set(callers)) == workers
    assert np.array_equal(source.asi8, before) and not error_source.asi8.any()
    assert getattr(sys, "_is_gil_enabled", lambda: None)() is gil_before
