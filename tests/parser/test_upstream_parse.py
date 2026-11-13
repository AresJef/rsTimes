"""Compare upstream datetime strings against the frozen official public API.

Inputs are local, so neither the original checkout nor another rewrite project
is needed. Approved century rules are derived independently of the Rust candidate.
"""

from datetime import date
import importlib.util
import json
from pathlib import Path

import pytest

reference = pytest.importorskip("cytimes.parser")
from rstimes.parser import Configs, parse_str as parse
from approved_behavior import expected_parse, outcomes_equal

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "data" / "upstream_datetimes.json").read_text(encoding='utf-8'))
SPEC = importlib.util.spec_from_file_location("_upstream_parser_values", HERE / "cases.py")
cases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cases)


@pytest.fixture(scope="module")
def configurations():
    """Give each implementation the upstream test's ten timezone aliases."""
    return cases.configured(reference.Configs), cases.configured(Configs)


@pytest.mark.parametrize("row", DATA["rows"], ids=[f"upstream-{i:03}" for i in range(len(DATA["rows"]))])
@pytest.mark.parametrize(
    "isoformat,ignoretz,configured", DATA["matrix"],
    ids=["iso-naive-config", "iso-aware-config", "general-naive-config",
         "general-aware-config", "iso-naive-default", "general-naive-default"],
)
def test_upstream_datetime_matches_approved_contract(row, isoformat, ignoretz, configured, configurations):
    """Require matching type, calendar fields, timezone details and fold."""
    original_cfg, rust_cfg = configurations
    kwargs = dict(default=date(1, 1, 1), yearfirst=False,
                  isoformat=isoformat, ignoretz=ignoretz)
    expected = cases.outcome(lambda: expected_parse(
        row[0], cfg=original_cfg if configured else None, **kwargs))
    actual = cases.outcome(lambda: parse(
        row[0], cfg=rust_cfg if configured else None, **kwargs))
    assert outcomes_equal(actual, expected), (row[0], kwargs, actual, expected)
