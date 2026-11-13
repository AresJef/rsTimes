"""Configs edits/imports interpret real stored strings before internal hashing."""
import copy
import numpy as np
import pytest
from rstimes import Configs, Pydt

NAMES = (("jump", None), ("pertain", None), ("utc", None), ("tzoffset", 3600),
         ("month", 2), ("weekday", 3), ("hms", 1), ("ampm", 1))


class StoredWord(str):
    def __str__(self):
        return "differentword"

    def lower(self):
        raise AssertionError("configuration must use stored text")


@pytest.mark.parametrize("name,number", NAMES)
@pytest.mark.parametrize("text_type", (str, np.str_, StoredWord))
def test_all_namespace_edits_use_stored_tokens(name, number, text_type) -> None:
    token = text_type("Roleword")
    cfg = Configs()
    cfg.clear_settings()
    add = getattr(cfg, "add_" + name)
    assert add(token, seconds=number) if name == "tzoffset" else add(token) if number is None else add(token, number)
    expected = {"roleword"} if number is None else {"roleword": number}
    assert getattr(cfg, name) == expected
    assert getattr(cfg, "del_" + name)(token)
    assert not getattr(cfg, name)
    table = {token} if number is None else {token: number}
    assert getattr(cfg, "set_" + name)(table)
    assert getattr(cfg, name) == expected


@pytest.mark.parametrize("text_type", (str, np.str_, StoredWord))
def test_region_registration_and_deletion_use_stored_key(text_type) -> None:
    token = text_type("Asia/Shanghai")
    cfg = Configs()
    assert cfg.add_tzone(token)
    assert cfg.tzone == {"Asia/Shanghai"}
    assert cfg.del_tzone(token)
    assert cfg.tzone == set()
    assert cfg.set_tzone({token})
    assert cfg.tzone == {"Asia/Shanghai"}


@pytest.mark.parametrize("token,reads", ((object(), 0), ("", 1), (StoredWord("word"), 1)))
def test_token_type_and_numeric_error_order(token, reads: int) -> None:
    calls = []
    original = LookupError("numeric conversion")

    class Number:
        def __index__(self):
            calls.append("index")
            raise original

    with pytest.raises(LookupError if reads else TypeError) as caught:
        Configs().add_month(token, Number())
    assert len(calls) == reads
    if reads:
        assert caught.value is original


def test_commit_recheck_keeps_callback_edit_and_rejects_new_conflict() -> None:
    cfg = Configs()
    before = cfg.month

    class Number:
        def __index__(self):
            cfg.add_weekday("roleword", 3)
            return 2

    with pytest.raises(ValueError, match="conflict"):
        cfg.set_month({"roleword": Number()})
    assert cfg.month == before and cfg.weekday["roleword"] == 3


def test_stored_token_edits_keep_copy_and_existing_expr_snapshot() -> None:
    pl = pytest.importorskip("polars")
    cfg = Configs()
    cfg.set_month({StoredWord("rolemonth"): 10})
    saved = copy.deepcopy(cfg)
    old = pl.col("text").pldt.strptime("%d %B %Y", unit="ns", cfg=cfg)
    cfg.add_month(StoredWord("rolemonth"), 11)
    new = pl.col("text").pldt.strptime("%d %B %Y", unit="ns", cfg=cfg)
    frame = pl.DataFrame({"text": ["14 rolemonth 2024"]})
    assert frame.select(old).to_series().to_physical().to_list() == [1728864000000000000]
    assert frame.select(new).to_series().to_physical().to_list() == [1731542400000000000]
    assert Pydt.strptime("14 rolemonth 2024", "%d %B %Y", cfg=saved) == Pydt(2024, 10, 14)


class HashWord(StoredWord):
    armed = False

    def __hash__(self):
        if type(self).armed:
            raise AssertionError("internal table hashed an unprepared word")
        return str.__hash__(self)


@pytest.mark.parametrize("source,target", (("JUMP", "jump"), ("PERTAIN", "pertain"),
    ("UTCZONE", "utc"), ("TZOFFSET", "tzoffset"), ("MONTHS", "month"),
    ("WEEKDAYS", "weekday"), ("HMS", "hms"), ("AMPM", "ampm")))
def test_parserinfo_prepares_tokens_before_own_table_hash(source: str, target: str) -> None:
    parserinfo = pytest.importorskip("dateutil.parser").parserinfo
    info = parserinfo()
    for name in ("JUMP", "PERTAIN", "UTCZONE", "TZOFFSET", "MONTHS", "WEEKDAYS", "HMS", "AMPM"):
        setattr(info, name, None)
    word = HashWord("Roleword")
    setattr(info, source, {word: 3600} if source == "TZOFFSET" else [word])
    HashWord.armed = True
    try:
        cfg = Configs.from_parserinfo(info)
    finally:
        HashWord.armed = False
    expected = {"roleword"} if source in ("JUMP", "PERTAIN", "UTCZONE") else {"roleword": 3600 if source == "TZOFFSET" else 1 if source == "MONTHS" else 0}
    assert getattr(cfg, target) == expected


def test_parserinfo_keeps_real_source_dictionary_export() -> None:
    parserinfo = pytest.importorskip("dateutil.parser").parserinfo
    calls = []

    class Source(dict):
        def __iter__(self):
            return super().__iter__()

        def keys(self):
            calls.append("keys")
            return super().keys()

        def __getitem__(self, key):
            calls.append("get")
            return super().__getitem__(key)

    info = parserinfo()
    info.TZOFFSET = Source({"rolezone": 3600})
    cfg = Configs.from_parserinfo(info)
    assert cfg.tzoffset == {"rolezone": 3600} and calls == ["keys", "get"]
