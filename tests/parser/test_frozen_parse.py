"""Keep every retained upstream and focused scan string portable to CPython3.15.

Expected values come from frozen cyTimes3.1.0 plus the existing independent
approved-behavior adapter, never from the Rust candidate being tested.
"""
from datetime import date, datetime
import json
from pathlib import Path

import pytest
from rstimes import Configs, parse_str

from cases import configured, outcome
from outcomes import error_category

DATA = json.loads((Path(__file__).with_name("data") / "frozen_parse_contract.json").read_text(encoding='utf-8'))
CONFIG = configured(Configs)


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda case: case["id"])
def test_retained_string_contract_without_importing_upstream(case):
    """Check exact successful fields, fold, timezone and public failure category."""
    kwargs = dict(case["kwargs"])
    kind, values = case["default"]
    kwargs["default"] = (date if kind == "date" else datetime)(*values)
    kwargs["cfg"] = CONFIG if case["configured"] else None
    actual = outcome(lambda: parse_str(case["text"], **kwargs))
    if "error_category" in case:
        assert "error" in actual, (case, actual)
        assert error_category(actual["error"]) == case["error_category"]
    else:
        assert actual == case["expected"], (case, actual)
