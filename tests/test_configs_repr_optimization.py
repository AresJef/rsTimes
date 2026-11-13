"""Configuration summaries read the effective rule sizes and live order method."""
import copy

import pytest

from rstimes import Configs

NAMES = ("jump", "pertain", "utc", "tzoffset", "month", "weekday", "hms", "ampm")


def assert_current_sizes(cfg):
    text = repr(cfg)
    for name in NAMES:
        assert f"{name}={len(getattr(cfg, name))}" in text
    return text


def test_summary_tracks_edits_and_independent_copies():
    cfg = Configs()
    assert_current_sizes(cfg)
    original = copy.copy(cfg)
    cfg.add_month("specialmonth", 2)
    cfg.add_jump("specialjump")
    assert_current_sizes(cfg)
    assert_current_sizes(original)
    assert len(cfg.month) == len(original.month) + 1
    assert len(cfg.jump) == len(original.jump) + 1


@pytest.mark.parametrize("yearfirst,dayfirst,order", [
    (True, True, "Y/D/M"), (True, False, "Y/M/D"),
    (False, True, "D/M/Y"), (False, False, "M/D/Y"),
])
def test_summary_uses_current_order_flags(yearfirst, dayfirst, order):
    cfg = Configs(yearfirst=yearfirst, dayfirst=dayfirst)
    text = assert_current_sizes(cfg)
    assert f"({order}: yearfirst={yearfirst} dayfirst={dayfirst}" in text


def test_summary_methods_cannot_be_replaced_on_the_immutable_config_type():
    with pytest.raises(TypeError, match="immutable"):
        setattr(Configs, "order_hint", lambda self: "USER-ORDER")
