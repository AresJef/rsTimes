"""CR05: protect corrected public claims without changing runtime admission."""
from datetime import datetime
from pathlib import Path
import numpy as np
import pytest
from rstimes import Configs, Pydt, parse


class Index:
    def __index__(self):
        return 1


class IntOnly:
    def __int__(self):
        return 1


@pytest.mark.parametrize("namespace", ["tzoffset", "month", "weekday", "hms", "ampm"])
@pytest.mark.parametrize("value,accepted", [(1, True), (np.int64(1), True), (Index(), True),
                                           (True, False), (np.bool_(True), False),
                                           (1.0, False), ("1", False), (IntOnly(), False)])
def test_cr05_mapping_documentation_preserves_actual_index_admission(namespace, value, accepted):
    cfg = Configs()
    if accepted:
        assert getattr(cfg, "set_" + namespace)({"reviewtoken": value}) is True
        assert getattr(cfg, namespace)["reviewtoken"] == 1
    else:
        with pytest.raises(TypeError):
            getattr(cfg, "set_" + namespace)({"reviewtoken": value})


@pytest.mark.parametrize("method", ["__add__", "__sub__", "__repr__", "__format__"])
def test_cr05_owned_pydt_protocol_has_runtime_user_documentation(method):
    assert getattr(Pydt, method).__doc__


def test_cr05_object_guide_no_longer_promises_boolean_seconds():
    guide = (Path(__file__).resolve().parents[1] / "docs/Parser对象解析使用说明.md").read_text()
    assert "bool沿官方规则作为0或1秒" not in guide
    with pytest.raises(TypeError):
        parse(True)


@pytest.mark.parametrize("method", ["toseconds", "tomicroseconds"])
def test_cr05_utc_documentation_matches_real_boolean_contract(method):
    events = []

    class Truth:
        def __bool__(self):
            events.append("bool")
            return True

    value = Pydt.fromdatetime(datetime(2024, 1, 1))
    for option in (1, Truth()):
        with pytest.raises(TypeError):
            getattr(value, method)(utc=option)
    assert events == []
    assert "Other non-text values use their Python truth value" not in getattr(Pydt, method).__doc__
