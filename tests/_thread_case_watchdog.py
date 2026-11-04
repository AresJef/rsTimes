"""Bound only the native/reentrant cases in test_free_threaded_contract.

A fresh interpreter owns all test threads. The parent can terminate that one
process even when an executor's shutdown cannot finish. This helper never
enters product code or performance measurements.
"""
from __future__ import annotations

import faulthandler
from functools import wraps
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
import traceback
from typing import Callable


STARTUP_SECONDS = 60.0
CASE_SECONDS = 30.0
CLEANUP_SECONDS = 5.0
_PROGRESS_PATH: Path | None = None
_PROGRESS: dict[str, object] = {}
_PROGRESS_LOCK = threading.Lock()


def stage(label: str) -> None:
    """Publish the last known test stage, including from a worker callback."""
    _record("running", label)


def _record(status: str, label: str, **details: object) -> None:
    if _PROGRESS_PATH is None:
        return
    with _PROGRESS_LOCK:
        _PROGRESS.update(status=status, stage=label, **details)
        # Append complete records; do not replace a file the Windows parent
        # may currently be reading. An unfinished final line is ignored.
        with _PROGRESS_PATH.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(_PROGRESS) + "\n")


def _stop(process: subprocess.Popen, seconds: float) -> bool:
    """Reap only the owned child, with a bounded terminate/kill sequence."""
    if process.poll() is not None:
        return True
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=seconds / 2)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=seconds / 2)
        except subprocess.TimeoutExpired:
            return False
    return True


def run_case(module: Path, function: str, args: tuple = (), kwargs: dict | None = None,
             *, case_id: str | None = None, startup: float = STARTUP_SECONDS,
             execution: float = CASE_SECONDS, cleanup: float = CLEANUP_SECONDS) -> dict:
    """Run one explicit test body, preserving stage/output and bounded cleanup."""
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="rstimes-thread-case-") as directory:
        root = Path(directory)
        payload, progress, output = root / "case.json", root / "progress.jsonl", root / "output.txt"
        payload.write_text(json.dumps({"module": str(module.resolve()), "function": function,
            "args": args, "kwargs": kwargs or {}, "case_id": case_id or function,
            "startup": startup, "startup_deadline": started + startup,
            "execution": execution, "cleanup": cleanup}), encoding="utf-8")
        env = dict(os.environ)
        env.pop("PYTHON_GIL", None)
        command = [sys.executable, "-I", "-X", "faulthandler", str(Path(__file__).resolve()),
                   "--child", str(payload), str(progress)]
        latest: dict = {"case_id": case_id or function, "status": "startup", "stage": "launch"}
        phase, deadline, timed_out = "startup", started + startup, False
        with output.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(command, cwd=module.parent, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT)
            reaped = False
            try:
                while True:
                    if progress.is_file():
                        lines = progress.read_text(encoding="utf-8").splitlines(keepends=True)
                        complete = [line for line in lines if line.endswith("\n")]
                        if complete:
                            latest = json.loads(complete[-1])
                    now = time.monotonic()
                    if phase == "startup" and latest["status"] == "running":
                        phase, deadline = "execution", now + execution
                    if phase != "cleanup" and latest["status"] in ("passed", "failed", "skipped"):
                        phase, deadline = "cleanup", now + cleanup
                    if process.poll() is not None:
                        reaped = True
                        break
                    if now >= deadline:
                        timed_out = True
                        break
                    time.sleep(0.02)
            finally:
                reaped = _stop(process, cleanup) if process.poll() is None else True
            result = dict(latest, returncode=process.returncode, child_pid=process.pid,
                          reaped=reaped, elapsed_seconds=time.monotonic() - started,
                          timed_out=timed_out, timeout_phase=phase if timed_out else None)
        result["output"] = output.read_text(encoding="utf-8", errors="replace")[-24000:]
        if timed_out or not reaped:
            result["status"] = "timeout"
        elif process.returncode != 0 or latest["status"] not in ("passed", "skipped"):
            result["status"] = "failed"
        result.update(python=sys.executable, command=command,
                      source_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),
                      helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      limits={"startup": startup, "execution": execution, "cleanup": cleanup})
        evidence = os.environ.get("RSTIMES_THREAD_CASE_EVIDENCE")
        if evidence:
            folder = Path(evidence)
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix="thread-case-",
                                             dir=folder, encoding="utf-8", delete=False) as saved:
                json.dump(result, saved, indent=2)
                saved.write("\n")
        return result


def bounded_case(function: Callable | None = None, *, optional_modules: tuple[str, ...] = ()) -> Callable:
    """Preserve pytest IDs/parameters while guarding this file's explicit cases."""
    def decorate(body: Callable) -> Callable:
        @wraps(body)
        def guarded(*args, **kwargs):
            # These two optional-integration bodies start with importorskip.
            # Preserve their original skip location/reason in absent-dep lanes.
            if any(importlib.util.find_spec(name) is None for name in optional_modules):
                return body(*args, **kwargs)
            import pytest
            case_id = os.environ.get("PYTEST_CURRENT_TEST", body.__name__).rsplit(" (", 1)[0]
            result = run_case(Path(body.__code__.co_filename), body.__name__, args, kwargs,
                              case_id=case_id)
            if result["status"] == "skipped":
                pytest.skip(result["reason"])
            if result["status"] != "passed":
                details = {key: value for key, value in result.items() if key != "output"}
                pytest.fail("bounded thread case failed: " + json.dumps(details) + "\n" + result["output"],
                            pytrace=False)
        return guarded
    return decorate(function) if function is not None else decorate


def _child(payload_path: Path, progress_path: Path) -> int:
    global _PROGRESS_PATH
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    _PROGRESS_PATH = progress_path
    _PROGRESS.update(case_id=payload["case_id"], child_pid=os.getpid())
    # The imported test module must share this exact progress sink/lock.
    sys.modules["_thread_case_watchdog"] = sys.modules[__name__]
    faulthandler.enable(all_threads=True)
    # Interpreter/bootstrap imports already consume the parent's startup
    # budget. Schedule diagnostics before that same absolute deadline.
    faulthandler.dump_traceback_later(max(0.001, payload["startup_deadline"] - time.monotonic() - 0.1))
    _record("startup", "importing test and installed native")
    pytest_module = None
    try:
        module_path = Path(payload["module"])
        sys.path.insert(0, str(module_path.parent))
        spec = importlib.util.spec_from_file_location("_rstimes_bounded_test", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        import pytest as pytest_module
        import rstimes._native as native
        free_threaded = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
        assert native._free_threaded_build() is free_threaded
        if free_threaded:
            assert "gil" not in sys._xoptions and not sys._is_gil_enabled()
        body = getattr(module, payload["function"])
        body = getattr(body, "__wrapped__", body)
        faulthandler.cancel_dump_traceback_later()
        faulthandler.dump_traceback_later(max(0.1, payload["execution"] - 0.1))
        _record("running", "test body", native=native.__file__, free_threaded=free_threaded)
        body(*payload["args"], **payload["kwargs"])
        if free_threaded:
            assert not sys._is_gil_enabled(), "actual thread case re-enabled the GIL"
        _record("passed", "test body finished")
        return 0
    except BaseException as error:
        if pytest_module is not None and isinstance(error, pytest_module.skip.Exception):
            _record("skipped", "original body skipped", reason=str(error))
            return 0
        traceback.print_exc()
        _record("failed", "test body/import failed", error_type=type(error).__name__)
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()
        faulthandler.dump_traceback_later(max(0.1, payload["cleanup"] - 0.1))


if __name__ == "__main__":
    assert len(sys.argv) == 4 and sys.argv[1] == "--child"
    raise SystemExit(_child(Path(sys.argv[2]), Path(sys.argv[3])))
