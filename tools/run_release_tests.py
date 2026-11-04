"""Run installed-package regression tests, with a separate frozen-oracle lane.

The pandas3 product matrix cannot co-install cytimes3.1.0, which declares
pandas<3. A compatible pandas2.3 lane runs the complete original suite; the
product matrix also runs the independently frozen upstream string corpus.
"""
import argparse
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import sys
import sysconfig

import pytest
import rstimes._native as native


def run_tests(options: list[str]) -> int:
    """Keep actual t execution GIL-free through the entire selected test lane."""
    free_threaded = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    assert native._free_threaded_build() is free_threaded
    if free_threaded:
        assert getattr(sys, "_is_gil_enabled")() is False, "GIL enabled before regression tests"
    result = pytest.main(options)
    if free_threaded:
        assert getattr(sys, "_is_gil_enabled")() is False, "a regression-test path re-enabled the GIL"
    return int(result)


def main():
    """Select the explicit test lane and run its complete applicable suite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-oracle", action="store_true")
    parser.add_argument("--core", action="store_true")
    parser.add_argument("--junitxml", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = Path(args.junitxml).resolve()
    os.environ.setdefault("RSTIMES_THREAD_CASE_EVIDENCE", str(
        report.parent / (report.stem + "-thread-cases")))
    sys.path.insert(0, str(root / "tests/parser"))
    if args.core and args.with_oracle:
        parser.error("--core cannot be combined with --with-oracle")
    if args.core:
        paths = [
            "test_optional_dateutil.py", "test_release_matrix.py",
            "test_free_threaded_contract.py", "test_thread_case_watchdog.py",
            "parser/test_frozen_parse.py", "parser/test_entrypoints.py",
            "parser/test_behavior_revision.py", "parser/test_object_parse.py",
        ]
        if importlib.util.find_spec("polars") is not None:
            paths.append("pldt")
        options = ["-q", *(str(root / "tests" / path) for path in paths),
                   "--junitxml", args.junitxml]
        raise SystemExit(run_tests(options))
    options = ["-q", str(root / "tests"), "--junitxml", args.junitxml]
    if args.with_oracle:
        assert importlib.metadata.version("cytimes") == "3.1.0"
    else:
        # These modules import the original implementation. They remain intact
        # and mandatory in the separate, dependency-compatible oracle job.
        oracle_modules = (
            "parser/test_configs.py", "parser/test_scan.py",
            "parser/test_upstream_parse.py", "parser/test_boundaries.py",
            "pydt/test_review_regressions.py", "pydt/test_constructors_calendar.py",
            "pydt/test_arithmetic_state.py", "pydt/test_calendar_adjustment.py",
            "pddt/test_official_conveniences.py",
        )
        options.extend("--ignore=" + str(root / "tests" / path) for path in oracle_modules)
        options.append("--deselect=tests/pydt/test_approved_refactor.py"
                       "::test_weekday_method_matches_datetime_and_official_value")
        options.append("--deselect=tests/pddt/test_calendar.py"
                       "::test_calendar_cache_is_correct_for_shuffled_and_repeated_days")
    raise SystemExit(run_tests(options))


if __name__ == "__main__":
    main()
