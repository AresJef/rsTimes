"""Owned fault bodies used only by watchdog acceptance tests."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from _thread_case_watchdog import stage


def passes(workers=2):
    barrier = threading.Barrier(workers)

    def work(index):
        barrier.wait(timeout=2)
        return index + 1

    with ThreadPoolExecutor(max_workers=workers) as pool:
        assert list(pool.map(work, range(workers))) == list(range(1, workers + 1))
    stage("normal workers finished")


def raises():
    raise LookupError("controlled test-body failure")


def skips():
    pytest.skip("controlled optional-dependency skip")


def hangs_after_barrier():
    barrier = threading.Barrier(2)

    def callback(_):
        barrier.wait(timeout=2)
        stage("callback passed barrier and is blocked")
        # Event.wait releases the GIL. Neither the result iterator nor the
        # executor context can finish unless the owning process is stopped.
        threading.Event().wait()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(callback, range(2)))
