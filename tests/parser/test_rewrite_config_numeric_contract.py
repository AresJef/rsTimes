"""P04: configuration codes are integers; ordering switches are booleans."""
from dateutil.parser import parserinfo
import numpy as np
import pytest

from rstimes import Configs, parse_str


@pytest.mark.parametrize("flag", [0, 1, None, [], object()])
def test_order_flags_do_not_apply_generic_truth_conversion(flag):
    with pytest.raises(TypeError):
        Configs(yearfirst=flag)
    with pytest.raises(TypeError):
        Configs(dayfirst=flag)


def test_numpy_boolean_flags_are_real_supported_flags():
    cfg = Configs(yearfirst=np.bool_(False), dayfirst=np.bool_(True))
    assert cfg.yearfirst is False and cfg.dayfirst is True
    assert parse_str("07/05/2024", cfg=cfg).month == 5


@pytest.mark.parametrize("namespace", ["month", "weekday", "hms", "ampm"])
@pytest.mark.parametrize("bad", [True, np.bool_(False)])
def test_add_and_set_codes_reject_boolean_values(namespace, bad):
    cfg = Configs()
    with pytest.raises(TypeError):
        getattr(cfg, "add_" + namespace)("zzcustom", bad)
    with pytest.raises(TypeError):
        getattr(cfg, "set_" + namespace)({"zzcustom": bad})


@pytest.mark.parametrize("bad", [True, np.bool_(False)])
def test_offset_components_and_total_are_not_boolean_flags(bad):
    cfg = Configs()
    for component in ("hours", "minutes", "seconds"):
        with pytest.raises(TypeError):
            cfg.add_tzoffset("zzcustom", **{component: bad})
    with pytest.raises(TypeError):
        cfg.set_tzoffset({"zzcustom": bad})


def test_source_flags_and_offset_codes_obey_their_actual_roles():
    info = parserinfo()
    info.yearfirst = 1
    with pytest.raises(TypeError):
        Configs.from_parserinfo(info)
    info.yearfirst = False
    info.TZOFFSET = {"zzcustom": True}
    with pytest.raises(TypeError):
        Configs.from_parserinfo(info)


def test_invalid_flag_does_not_call_a_user_truth_hook():
    class Trap:
        def __bool__(self):
            raise AssertionError("not a boolean scalar")

    with pytest.raises(TypeError):
        Configs(yearfirst=Trap())
