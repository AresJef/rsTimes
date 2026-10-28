"""Focused grammar checks use the oracle plus independent approved policies."""
from datetime import datetime

import pytest
from cytimes.parser import parse as reference_parse
from rstimes.parser import parse_str as parse
from approved_behavior import expected_parse, error_category

DEFAULT = datetime(2001, 2, 3, 4, 5, 6, 7)

# ISO success, partial ISO continuations, and each generic handler share the
# exact same public call. Fixed dates avoid current-day and year-window drift.
INPUTS = [
    "2024-02-29", "20240229", "2024-060", "2024060", "2023-366",
    "2020-W53-7", "2021-W53-7", "2020W537", "2020W53-7", "2024-W05",
    "2024W05x", "2024/02/29", "2024.02.29", "2024-02-30",
    "2024-02-29T12:34:56", "20240229t123456", "2024-02-29 12:34:56.123456789",
    "2024-02-29T12:34:56,5Z", "2024-02-29T12:34:56+0530",
    "2024-02-29T12:34:56-05:30", "2024-02-29T12:34",
    "2024-02-29T12:34:56. UTC", "2024-02-29 12:34:56 PM",
    "2024-02-29 12:34:56Z Monday", "2024-02-29T12:34:56 xyz 99",
    "Feb 29 2024", "29-Feb-2024", "Feb-29-2024", "February, 2024",
    "Feb of 2024", "2024 W05-3", "2024 W53-7", "240229", "20240229123456",
    "2024-02-29 1234", "2024-02-29 123456.1234567", "12h04m05.5s",
    "12.5h", "12.5m", "12.5s", "12,5h", "12 AM", "12pm", "0 PM",
    "Feb 29 2024 12:34:56 UTC+3", "Feb 29 2024 12:34:56 GMT-0230",
    "Feb 29 2024 12:34:56 CET+03", "Feb 29 2024 12:34:56 +24:00",
    "\t\nFeb\t29  2024\r", "Feb\u00a029\u00a02024", "年月 Feb 29 2024",
    "𐐀 Feb 29 2024", "\ud800 Feb 29 2024", "Feb.29.2024", "a.1 Feb 29 2024",
]


def outcome(fn, text, isoformat, ignoretz, cfg=None):
    try:
        return ("value", fn(text, default=DEFAULT, isoformat=isoformat, ignoretz=ignoretz, cfg=cfg))
    except Exception as exc:
        # Public failure category and causal category are contractual. Native
        # arithmetic overflow deliberately replaces the oracle's wraparound.
        cause = exc.__cause__
        return ("error", error_category({"type": type(exc).__name__, "message": str(exc), "cause": {"type": type(cause).__name__, "message": str(cause)} if cause else None}, legacy=fn is expected_parse))


@pytest.mark.parametrize("text", INPUTS)
@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("ignoretz", [False, True])
def test_scan_matches_approved_behavior(text, isoformat, ignoretz):
    assert outcome(parse, text, isoformat, ignoretz) == outcome(expected_parse, text, isoformat, ignoretz)




