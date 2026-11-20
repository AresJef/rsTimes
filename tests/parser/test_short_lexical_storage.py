"""Independent public answers around short lexical storage and fallback paths."""
from datetime import datetime
import pytest
from rstimes import Configs, Pddt, Pldt, Pydt, parse, parse_str, parse_to_epoch
from rstimes.errors import ParseError

BASE = "Feb 29 2024 12:34:56.123456"
EXPECTED = datetime(2024, 2, 29, 12, 34, 56, 123456)
EXPECTED_NS = 1_709_210_096_123_456_000


@pytest.mark.parametrize("length", [27, 31, 32, 33, 64, 1024])
@pytest.mark.parametrize("entry", ["parse_str", "parse", "parse_to_epoch", "Pydt", "Pddt", "Pldt"])
def test_named_date_storage_boundary_uses_independent_date_answer(length, entry):
    value = " " * (length - len(BASE)) + BASE
    if entry == "parse_str":
        assert parse_str(value) == EXPECTED
    elif entry == "parse":
        assert parse(value) == EXPECTED
    elif entry == "parse_to_epoch":
        assert parse_to_epoch(value, unit="ns") == EXPECTED_NS
    elif entry == "Pydt":
        assert Pydt.parse(value) == Pydt(2024, 2, 29, 12, 34, 56, 123456)
    elif entry == "Pddt":
        assert Pddt.parse([value], unit="ns").asi8.tolist() == [EXPECTED_NS]
    else:
        assert Pldt.parse([value], unit="ns").to_physical().to_list() == [EXPECTED_NS]


@pytest.mark.parametrize("marker", ["é", "字", "𐐀"])
@pytest.mark.parametrize("padding", [0, 1, 2, 33])
def test_unicode_codepoint_boundary_is_independent_of_utf8_width(marker, padding):
    cfg = Configs()
    cfg.add_jump(marker)
    value = marker + " " + " " * padding + BASE
    assert parse_str(value, cfg=cfg) == EXPECTED
    assert Pldt.parse([value], unit="ns", cfg=cfg).to_physical().to_list() == [EXPECTED_NS]


@pytest.mark.parametrize("padding", [0, 32, 1024])
def test_lone_surrogate_still_reports_parse_error(padding):
    with pytest.raises(ParseError):
        parse_str(" " * padding + "\ud800")
