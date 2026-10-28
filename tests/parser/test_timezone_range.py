"""Separate invalid offsets from component conversion overflow."""
import pytest
from rstimes import Configs
from rstimes.errors import ConfigError

@pytest.mark.parametrize('hours', [1193046, 2**30, -(2**30)])
def test_representable_components_invalid_total(hours):
    cfg = Configs()
    before = cfg.tzoffset
    with pytest.raises(ConfigError):
        cfg.add_tzoffset('checkedalias', hours=hours)
    assert cfg.tzoffset == before


def test_unrepresentable_component_is_overflow():
    with pytest.raises(OverflowError):
        Configs().add_tzoffset('checkedalias', hours=2**100)


@pytest.mark.parametrize('seconds', [-86399, -1, 0, 1, 86399])
def test_config_offset_boundaries_are_exclusive(seconds):
    cfg = Configs()
    cfg.add_tzoffset('checkedalias', seconds=seconds)
    assert cfg.tzoffset['checkedalias'] == seconds
