"""D01/D02 native preparation; public Expr execution is covered by PLDT tests."""
from datetime import datetime, timezone
import gc
import pickle

import numpy as np
import pytest

from rstimes import Configs, Pddt, Pydt, parse_str
from rstimes._native import _pldt_prepare_text


def _month(data, word):
    table = data["rules"]["tables"][4]
    if table is None:
        assert data["rules"]["version"] == 2
        return {"Jan": 1}[word]  # Fixed library word, independently specified.
    return dict((tuple(key), value) for key, value in table)[tuple(map(ord, word))]


@pytest.mark.parametrize("expression, expected_month", [(True, 1), (False, 3)])
def test_default_callback_cannot_change_prior_expr_snapshot_but_changes_eager_cfg(expression, expected_month):
    cfg = Configs()
    calls = []

    class Reference(str):
        def __str__(self):
            calls.append("default")
            cfg.set_month({"jan": 3})
            return "14 Jan 2024"

    prepared = _pldt_prepare_text(cfg=cfg, default=Reference("ignored"), expression=expression)
    assert calls == ["default"]
    data = prepared.plugin_kwargs()
    assert data["options"]["default"] == [2024, expected_month, 14]
    assert _month(data, "Jan") == expected_month
    cfg.set_month({"jan": 8})
    del cfg
    gc.collect()
    assert _month(prepared.plugin_kwargs(), "Jan") == expected_month
    assert calls == ["default"]
    assert pickle.loads(pickle.dumps(data)) == data
    data["rules"]["tables"][4] = []
    assert _month(prepared.plugin_kwargs(), "Jan") == expected_month


def test_default_only_exports_ymd_and_missing_default_does_not_use_today():
    assert _pldt_prepare_text().plugin_kwargs() == {
        "rules": None, "strict": False,
        "options": {"default": None, "yearfirst": None, "dayfirst": None, "isoformat": True},
    }
    default = datetime(2024, 5, 7, 12, 34, 56, 789, tzinfo=timezone.utc, fold=1)
    data = _pldt_prepare_text(default=default).plugin_kwargs()
    assert data["options"]["default"] == [2024, 5, 7]
    assert set(data["options"]) == {"default", "yearfirst", "dayfirst", "isoformat"}


def test_prepared_regions_are_values_and_keep_registered_availability():
    cfg = Configs()
    cfg.add_tzone("Asia/Shanghai")
    data = _pldt_prepare_text(cfg=cfg).plugin_kwargs()
    assert data["rules"]["regions"] == [
        ([ord(c) for c in "Asia/Shanghai"],
         {"key": "Asia/Shanghai", "available": True, "fixed_offset_us": None}),
    ]
    assert pickle.loads(pickle.dumps(data)) == data


@pytest.mark.parametrize("keyword", ["isoformat", "strict", "expression", "yearfirst", "dayfirst"])
@pytest.mark.parametrize("value", [0, 1, "true", [], object()])
def test_native_preparation_checks_true_boolean_roles(keyword, value):
    with pytest.raises(TypeError):
        _pldt_prepare_text(**{keyword: value})


def test_native_preparation_preserves_explicit_false_and_numpy_boolean():
    cfg = Configs(yearfirst=True, dayfirst=True)
    data = _pldt_prepare_text(cfg=cfg, yearfirst=np.bool_(False), dayfirst=False).plugin_kwargs()
    assert data["options"]["yearfirst"] is False
    assert data["options"]["dayfirst"] is False
    assert data["rules"]["flags"] == (True, True)


@pytest.mark.parametrize("default", ["May 7", True, np.bool_(True), object()])
def test_expression_default_must_be_independently_complete_at_preparation(default):
    with pytest.raises((TypeError, ValueError)):
        _pldt_prepare_text(default=default)


@pytest.mark.parametrize("text, fmt, expected", [
    ("٢٠٢٤-٠١-٠٢ ١٢:٣٤:٥٦.١٢٣٤٥٦٧٨٩٩", "%Y-%m-%d %H:%M:%S.%f", (2024, 1, 2, 12, 34, 56, 123456, 789)),
    ("20241-01-02", "%Y1-%m-%d", (2024, 1, 2, 0, 0, 0, 0, 0)),
    ("14 février 2024", "%d %B %Y", (2024, 2, 14, 0, 0, 0, 0, 0)),
])
def test_shared_formatted_exits_keep_calendar_and_final_precision(text, fmt, expected):
    y, m, d, h, mi, s, us, ns = expected
    scalar = Pydt.strptime(text, fmt)
    assert (scalar.year, scalar.month, scalar.day, scalar.hour, scalar.minute, scalar.second, scalar.microsecond) == expected[:7]
    column = Pddt.strptime(text, fmt, size=1, unit="ns")
    elapsed = datetime(y, m, d, h, mi, s, us) - datetime(1970, 1, 1)
    assert column.asi8.tolist() == [(elapsed.days * 86400 + elapsed.seconds) * 10**9 + us * 1000 + ns]


def test_unknown_region_error_keeps_isolated_surrogate_without_reencoding():
    with pytest.raises(ValueError) as result:
        parse_str("2024-01-01 [\ud800/Place]", ignoretz=False)
    assert "\\ud800/Place" in str(result.value)
