"""DCR05: fault controls prove deadlines, diagnostics and later progress."""
from pathlib import Path
import json
import os
import stat

import pytest

import _thread_case_watchdog as watchdog
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


def test_startup_diagnostic_deadline_includes_child_bootstrap(tmp_path, monkeypatch):
    helper = Path(watchdog.__file__)
    delayed = tmp_path / "delayed_watchdog.py"
    source = helper.read_text(encoding="utf-8")
    original = '    raise SystemExit(_child(Path(sys.argv[2]), Path(sys.argv[3])))'
    assert source.count(original) == 1
    # Keep enough real bootstrap/diagnostic headroom on slow free-threaded
    # runners. A relative five-second arm after this two-second delay would
    # still miss the parent's absolute deadline, so the negative control is
    # preserved without relying on a subsecond scheduling window.
    delayed.write_text(source.replace(original, '    time.sleep(2.0)\n' + original), encoding="utf-8")
    monkeypatch.setattr(watchdog, "__file__", str(delayed))
    module = Path(__file__).with_name("_thread_watchdog_import_hang.py")
    result = run_case(module, "unused", startup=5.0, execution=30, cleanup=3)
    assert result["status"] == "timeout" and result["timeout_phase"] == "startup"
    assert result["reaped"] is True and result["elapsed_seconds"] < 10
    assert "Timeout" in result["output"] and "_thread_watchdog_import_hang" in result["output"]


def test_diagnostics_survive_a_delayed_native_timer(tmp_path, monkeypatch):
    helper = Path(watchdog.__file__)
    delayed = tmp_path / "delayed_native_timer_watchdog.py"
    source = helper.read_text(encoding="utf-8")
    original = '    faulthandler.enable(all_threads=True)'
    assert source.count(original) == 1
    injected = original + '\n    original_dump = faulthandler.dump_traceback_later\n    faulthandler.dump_traceback_later = lambda delay: original_dump(delay + 0.2)'
    delayed.write_text(source.replace(original, injected), encoding="utf-8")
    monkeypatch.setattr(watchdog, "__file__", str(delayed))
    result = run_case(CASES, "hangs_after_barrier", startup=30, execution=0.8, cleanup=3)
    assert result["status"] == "timeout" and result["timeout_phase"] == "execution"
    assert result["reaped"] is True and result["elapsed_seconds"] < 35
    assert "Timeout" in result["output"] and "hangs_after_barrier" in result["output"]


def test_original_failure_and_skip_are_not_reclassified_as_pass():
    failure = run_case(CASES, "raises")
    assert failure["status"] == "failed" and failure["returncode"] != 0
    assert "controlled test-body failure" in failure["output"] and failure["reaped"] is True
    skipped = run_case(CASES, "skips")
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "controlled optional-dependency skip"


def test_saved_evidence_is_readable_by_the_host_artifact_collector(tmp_path, monkeypatch):
    monkeypatch.setenv("RSTIMES_THREAD_CASE_EVIDENCE", str(tmp_path))
    result = run_case(CASES, "passes")
    assert result["status"] == "passed" and result["reaped"] is True
    receipt, = tmp_path.glob("thread-case-*.json")
    assert json.loads(receipt.read_text())["child_pid"] == result["child_pid"]
    if os.name != "nt":
        assert stat.S_IMODE(receipt.stat().st_mode) == 0o644
