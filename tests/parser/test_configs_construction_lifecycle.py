"""Configs publishes complete values in new; init never resets live rules."""
import copy
import pickle
from datetime import datetime

import numpy as np
import polars as pl
import pytest
from dateutil.parser import parserinfo

from rstimes import Configs, Pddt, Pldt, Pydt, parse, parse_str, parse_to_epoch


@pytest.mark.parametrize("yearfirst,dayfirst", [(True, False), (False, True), (False, False), (True, True), (np.bool_(False), np.bool_(True))])
def test_public_new_returns_a_complete_configuration(yearfirst, dayfirst):
    actual = Configs.__new__(Configs, yearfirst=yearfirst, dayfirst=dayfirst)
    expected = Configs(yearfirst=yearfirst, dayfirst=dayfirst)
    assert actual.yearfirst is bool(yearfirst) and actual.dayfirst is bool(dayfirst)
    for name in ("jump", "pertain", "utc", "tzoffset", "month", "weekday", "hms", "ampm", "tzone"):
        assert getattr(actual, name) == getattr(expected, name)
    assert parse_str("14 harvest 2024", default=datetime(2024, 1, 1), cfg=custom_month(actual)) == datetime(2024, 10, 14)


def custom_month(cfg):
    cfg.add_month("harvest", 10)
    return cfg


@pytest.mark.parametrize("bad", [None, 0, 1, "True", [], object()])
@pytest.mark.parametrize("flag", ["yearfirst", "dayfirst"])
def test_direct_new_keeps_the_same_strict_boolean_contract(flag, bad):
    with pytest.raises(TypeError, match=flag):
        Configs.__new__(Configs, **{flag: bad})


@pytest.mark.parametrize("direct", [False, True])
def test_init_is_noop_and_reset_has_an_explicit_separate_role(direct):
    cfg = Configs.__new__(Configs) if direct else Configs()
    custom_month(cfg)
    cfg.add_tzone("Europe/Paris")
    snapshot = pickle.dumps(cfg)
    mapping = cfg.month
    cfg.__init__(yearfirst=False, dayfirst=True)
    assert (cfg.yearfirst, cfg.dayfirst) == (True, False)
    assert cfg.month == mapping and cfg.tzone == {"Europe/Paris"}
    assert pickle.dumps(cfg) == snapshot
    cfg.reset_settings()
    assert "harvest" not in cfg.month and cfg.tzone == set()
    assert (cfg.yearfirst, cfg.dayfirst) == (True, False)
    assert mapping["harvest"] == 10


@pytest.mark.parametrize("restore", [copy.copy, copy.deepcopy, lambda x: pickle.loads(pickle.dumps(x))])
def test_copies_and_restore_keep_flags_and_independently_editable_rules(restore):
    cfg = custom_month(Configs(yearfirst=False, dayfirst=True))
    cfg.add_tzone("Europe/Paris")
    result = restore(cfg)
    result.__init__()
    result.set_month({"harvest": 11})
    assert result is not cfg and not result.yearfirst and result.dayfirst
    assert result.tzone == cfg.tzone == {"Europe/Paris"}
    assert cfg.month["harvest"] == 10 and result.month["harvest"] == 11


def test_import_and_all_parser_consumers_use_complete_constructed_rules():
    info = parserinfo(yearfirst=False, dayfirst=True)
    cfg = Configs.from_parserinfo(info)
    info.dayfirst = False
    assert not cfg.yearfirst and cfg.dayfirst
    expected = datetime(2024, 5, 7)
    for entry in (parse_str, parse, Pydt.parse):
        assert entry("07/05/2024", cfg=cfg, isoformat=False) == expected
    assert parse_to_epoch("07/05/2024", cfg=cfg, isoformat=False, unit="us") == 1715040000000000
    assert Pddt(["07/05/2024"], cfg=cfg, unit="us")[0] == expected
    assert Pldt(["07/05/2024"], cfg=cfg, unit="us").to_physical().to_list() == [1715040000000000]


@pytest.mark.parametrize("engine", ["auto", "streaming"])
def test_init_keeps_old_expr_and_real_edits_keep_creation_time_snapshots(engine):
    cfg = custom_month(Configs())
    old = pl.col("text").pldt.parse(unit="us", cfg=cfg)
    cfg.__init__(yearfirst=False, dayfirst=True)
    after_init = pl.col("text").pldt.parse(unit="us", cfg=cfg)
    cfg.set_month({"harvest": 11})
    edited = pl.col("text").pldt.parse(unit="us", cfg=cfg)
    frame = pl.LazyFrame({"text": ["14 harvest 2024", None]})
    for expr, month in ((old, 10), (after_init, 10), (edited, 11)):
        assert frame.select(expr).collect(engine=engine)["text"].to_list() == [datetime(2024, month, 14), None]


@pytest.mark.parametrize("args,kwargs", [((True, False, True), {}), ((False,), {"yearfirst": True}), ((), {"unknown": True})])
def test_new_rejects_invalid_binding_before_constructing_state(args, kwargs):
    with pytest.raises(TypeError, match="Configs"):
        Configs.__new__(Configs, *args, **kwargs)


@pytest.mark.parametrize("direct", [False, True])
def test_constructor_reads_real_keyword_text_without_display_hooks(direct):
    class Keyword(str):
        def __str__(self):
            raise AssertionError("keyword display hook must not run")

        def __getitem__(self, key):
            raise AssertionError("keyword slicing hook must not run")

    factory = (lambda **kw: Configs.__new__(Configs, **kw)) if direct else Configs
    cfg = factory(**{Keyword("yearfirst"): False, Keyword("dayfirst"): True})
    assert not cfg.yearfirst and cfg.dayfirst and cfg.month["january"] == 1


@pytest.mark.parametrize("direct", [False, True])
def test_unknown_non_utf8_keyword_still_has_constructor_type_error(direct):
    factory = (lambda **kw: Configs.__new__(Configs, **kw)) if direct else Configs
    with pytest.raises(TypeError, match="Configs.*unknown keyword"):
        factory(**{"\ud800": True})
