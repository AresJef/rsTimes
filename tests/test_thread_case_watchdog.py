"""DCR05: fault controls prove deadlines, diagnostics and later progress."""
from pathlib import Path

import pytest

from _thread_case_watchdog import run_case


CASES = Path(__file__).with_name("_thread_watchdog_cases.py")


@pytest.mark.parametrize("workers", (1, 2, 4))
def test_normal_thread_case_retains_arguments_and_reaps_its_child(workers):
    result = run_case(CASES, "passes", kwargs={"workers": workers})
    assert result["status"] == "passed" and result["returncode"] == 0
    assert result["reaped"] is True and result["timed_out"] is False
    assert result["stage"] == "test body finished"


def test_block_after_barrier_is_bounded_and_next_case_still_runs():
    result = run_case(CASES, "hangs_after_barrier", case_id="controlled-after-barrier",
                      startup=30, execution=0.8, cleanup=3)
    assert result["status"] == "timeout" and result["timeout_phase"] == "execution"
    assert result["case_id"] == "controlled-after-barrier"
    assert result["stage"] == "callback passed barrier and is blocked"
    assert result["reaped"] is True and result["returncode"] != 0
    assert result["elapsed_seconds"] < 35
    assert "Timeout" in result["output"] and "hangs_after_barrier" in result["output"]
    following = run_case(CASES, "passes")
    assert following["status"] == "passed" and following["reaped"] is True


def test_startup_hang_is_bounded_separately_from_case_execution():
    module = Path(__file__).with_name("_thread_watchdog_import_hang.py")
    result = run_case(module, "unused", startup=1.5, execution=30, cleanup=3)
    assert result["status"] == "timeout" and result["timeout_phase"] == "startup"
    assert result["stage"] == "importing test and installed native"
    assert result["elapsed_seconds"] < 6 and result["reaped"] is True
    assert "Timeout" in result["output"] and "_thread_watchdog_import_hang" in result["output"]


def test_original_failure_and_skip_are_not_reclassified_as_pass():
    failure = run_case(CASES, "raises")
    assert failure["status"] == "failed" and failure["returncode"] != 0
    assert "controlled test-body failure" in failure["output"] and failure["reaped"] is True
    skipped = run_case(CASES, "skips")
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "controlled optional-dependency skip"
