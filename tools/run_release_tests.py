"""Run installed-package regression tests, with a separate frozen-oracle lane.

The pandas3 product matrix cannot co-install cytimes3.1.0, which declares
pandas<3. A compatible pandas2.3 lane runs the complete original suite; the
product matrix also runs the independently frozen upstream string corpus.
"""
import argparse
import importlib.metadata
from pathlib import Path
import sys

import pytest


def main():
    """Select the explicit test lane and run its complete applicable suite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-oracle", action="store_true")
    parser.add_argument("--core", action="store_true")
    parser.add_argument("--junitxml", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tests/parser"))
    if args.core and args.with_oracle:
        parser.error("--core cannot be combined with --with-oracle")
    if args.core:
        paths = [
            "test_optional_dateutil.py", "test_release_matrix.py",
            "parser/test_frozen_parse.py", "parser/test_entrypoints.py",
            "parser/test_behavior_revision.py", "parser/test_object_parse.py",
        ]
        options = ["-q", *(str(root / "tests" / path) for path in paths),
                   "--junitxml", args.junitxml]
        raise SystemExit(pytest.main(options))
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
        )
        options.extend("--ignore=" + str(root / "tests" / path) for path in oracle_modules)
        options.append("--deselect=tests/pydt/test_approved_refactor.py"
                       "::test_weekday_method_matches_datetime_and_official_value")
    raise SystemExit(pytest.main(options))


if __name__ == "__main__":
    main()
