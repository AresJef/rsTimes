"""Keep native tokenization consistent with Python Unicode letters on all OSes."""
from datetime import datetime
import pytest
from rstimes import Configs, parse_str


@pytest.mark.parametrize("word", ["février", "二月", "فبراير", "𐐀𐐁", "ḀḂ"])
def test_configured_unicode_month_keeps_python_letter_semantics(word):
    assert word.isalpha()
    cfg = Configs()
    cfg.add_month(word, 2)
    assert parse_str("29 " + word + " 2024", cfg=cfg) == datetime(2024, 2, 29)
