"""All date-string entrances read real Unicode storage without conversion."""
from datetime import date, datetime

import pytest

from rstimes import Configs, Pddt, Pldt, Pydt, parse, parse_str, parse_to_epoch
from rstimes.errors import ParseError


class StoredText(str):
    def __str__(self):
        raise AssertionError("the text entrance must read native storage")

    def __len__(self):
        raise AssertionError("do not call an overridden length")

    def __getitem__(self, key):
        raise AssertionError("do not call overridden indexing")

    def __iter__(self):
        raise AssertionError("do not call overridden iteration")

    def __repr__(self):
        raise AssertionError("do not call overridden display")


@pytest.mark.parametrize("marker", ["é", "词", "𐐀"])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("isoformat", [False, True])
def test_text_entrance_reads_subclass_storage_of_each_unicode_kind(marker, strict, isoformat):
    cfg = Configs()
    cfg.add_jump(marker)
    token = StoredText(marker + " 1970-01-01 00:00:00.123456789")
    actual = parse_str(token, cfg=cfg, strict=strict, isoformat=isoformat)
    assert type(actual) is datetime
    assert actual == datetime(1970, 1, 1, 0, 0, 0, 123456)


def _object_result(entry, token, strict=False):
    if entry == "parse":
        return parse(token, strict=strict), datetime(1970, 1, 2, 0, 0, 0, 123456)
    if entry == "Pydt.parse":
        return Pydt.parse(token, strict=strict), Pydt(1970, 1, 2, 0, 0, 0, 123456)
    if entry == "parse_to_epoch":
        return parse_to_epoch(token, unit="ns", strict=strict), 86_400_123_456_789
    if entry == "Pddt.parse":
        return Pddt.parse([token], strict=strict).asi8.tolist(), [86_400_123_456_789]
    return Pldt.parse([token], strict=strict).to_physical().to_list(), [86_400_123_456_789]


OBJECT_ENTRIES = ["parse", "Pydt.parse", "parse_to_epoch", "Pddt.parse", "Pldt.parse"]


@pytest.mark.parametrize("entry", OBJECT_ENTRIES)
@pytest.mark.parametrize("hook_raises", [False, True])
@pytest.mark.parametrize("strict", [False, True])
def test_object_entrances_read_input_storage_without_calling_str(entry, hook_raises, strict):
    events = []

    class Input(str):
        def __str__(self):
            events.append("str")
            if hook_raises:
                raise RuntimeError("this conversion must not happen")
            return StoredText("1970-01-03T00:00:00.987654321")

    actual, expected = _object_result(entry, Input("1970-01-02T00:00:00.123456789"), strict)
    assert actual == expected
    assert events == []


@pytest.mark.parametrize("entry", OBJECT_ENTRIES)
def test_shared_object_readers_ignore_all_overridden_text_hooks(entry):
    actual, expected = _object_result(entry, StoredText("1970-01-02T00:00:00.123456789"))
    assert actual == expected


def test_three_scalar_entrances_interpret_the_same_stored_date():
    class Input(str):
        def __str__(self):
            return StoredText("1970-01-02")

    token = Input("1970-01-01")
    assert parse_str(token) == datetime(1970, 1, 1)
    assert parse(token) == datetime(1970, 1, 1)
    assert parse_to_epoch(token, unit="s") == 0
    # Explicit conversion remains available when the caller requests it.
    assert parse(str(token)) == datetime(1970, 1, 2)


@pytest.mark.parametrize("entry", [parse_str, parse, parse_to_epoch])
def test_bad_stored_text_does_not_use_a_successful_conversion_as_fallback(entry):
    class Input(str):
        def __str__(self):
            return "1970-01-02"

    token = Input("unrecognizable")
    with pytest.raises(ParseError):
        entry(token)


@pytest.mark.parametrize("value", [None, 1, b"1970-01-01", date(1970, 1, 1)])
def test_text_entrance_still_rejects_non_strings(value):
    with pytest.raises(TypeError, match="dtstr"):
        parse_str(value)


def test_fake_class_attribute_is_not_a_real_string_subclass():
    class Fake:
        @property
        def __class__(self):
            raise AssertionError("do not inspect a display class")

        def __str__(self):
            raise AssertionError("do not convert an unsupported object")

        def __repr__(self):
            raise AssertionError("do not display an unsupported object")

    with pytest.raises(TypeError, match="dtstr"):
        parse_str(Fake())


def test_subclass_default_reads_stored_date_and_keeps_final_constructor():
    events = []

    class Default(str):
        def __str__(self):
            events.append("default")
            raise AssertionError("string defaults use native storage too")

    def build(**fields):
        events.append("build")
        return datetime(**fields)

    assert parse_str(StoredText("12:34"), default=Default("2024-05-07"), dtclass=build) == datetime(2024, 5, 7, 12, 34)
    assert events == ["build"]


def test_subclass_input_keeps_cfg_validation_without_display_or_conversion():
    with pytest.raises(TypeError, match="cfg"):
        parse_str(StoredText("1970-01-01"), cfg=object())


@pytest.mark.parametrize("entry", ["Pydt.strptime", "Pddt.strptime", "Pldt.strptime", "Pydt.fromisoformat", "Pddt.fromisoformat", "Pldt.fromisoformat"])
def test_related_text_factories_read_stored_input_without_string_conversion(entry):
    text = StoredText("1970-01-02T00:00:00.123456")
    cls_name, method = entry.split(".")
    cls = {"Pydt": Pydt, "Pddt": Pddt, "Pldt": Pldt}[cls_name]
    args = (text, "%Y-%m-%dT%H:%M:%S.%f") if method == "strptime" else (text,)
    kwargs = {} if cls_name == "Pydt" else {"size": 2}
    actual = getattr(cls, method)(*args, **kwargs)
    expected = datetime(1970, 1, 2, 0, 0, 0, 123456)
    if cls_name == "Pydt":
        assert actual == expected
    else:
        assert list(actual) == [expected, expected]


@pytest.mark.parametrize("entry", [parse_str, parse, parse_to_epoch, Pydt.parse])
def test_all_scalar_string_defaults_follow_the_same_native_storage_contract(entry):
    kwargs = {"unit": "s"} if entry is parse_to_epoch else {}
    actual = entry(StoredText("12:34"), default=StoredText("1970-01-02"), **kwargs)
    assert actual == (131640 if entry is parse_to_epoch else datetime(1970, 1, 2, 12, 34))


@pytest.mark.parametrize("cls", [Pddt, Pldt])
def test_shared_combine_reads_stored_date_and_clock(cls):
    actual = cls.combine([date(1970, 1, 2)], StoredText("03:04:05.123456"))
    assert list(actual) == [datetime(1970, 1, 2, 3, 4, 5, 123456)]


@pytest.mark.parametrize("cls", [Pddt, Pldt])
def test_shared_difference_target_reads_stored_text(cls):
    source = cls(["1970-01-02"])
    actual = (source.pldt if cls is Pldt else source).diff(StoredText("1970-01-01"), "s")
    assert list(actual) == [86400]
