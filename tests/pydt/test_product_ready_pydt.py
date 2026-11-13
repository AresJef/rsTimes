"""ProductReady Pydt regressions preserve the mature Python output domain."""
from datetime import datetime

import pytest

from rstimes import Pydt


@pytest.mark.parametrize("literal", ["", "日期", "🌏", "\0", "\ud800", "\udfff"])
@pytest.mark.parametrize("suffix,expanded", [("%Y", "%Y"), ("%%f", "%%f"),
                                           ("%f", "123456"), ("%.3f", ".123"),
                                           ("%.0f", "")])
def test_python_strftime_literals_keep_mature_platform_result(literal, suffix, expanded):
    ordinary = datetime(2024, 1, 2, 3, 4, 5, 123456)
    value = Pydt.fromdatetime(ordinary)
    try:
        expected = ordinary.strftime(literal + expanded)
    except Exception as error:
        with pytest.raises(type(error)):
            value.strftime(literal + suffix)
    else:
        assert value.strftime(literal + suffix) == expected


@pytest.mark.parametrize("literal", ["", "日期", "🌏", "\0", "\ud800", "\udfff"])
def test_strptime_literal_codepoints_are_preserved_and_mismatch_is_a_value_error(literal):
    text = "2024-01-02" + literal
    fmt = "%Y-%m-%d" + literal
    expected = datetime.strptime(text, fmt)
    assert Pydt.strptime(text, fmt) == expected
    with pytest.raises(ValueError, match="does not match") as observed:
        Pydt.strptime(text + "X", fmt + "Y")
    assert not isinstance(observed.value, UnicodeEncodeError)


def test_restore_validates_the_same_snapshot_with_interleaved_source_edit():
    """Drive the known validation/capture gap once, without a scheduling lottery."""
    import linecache
    import sys

    dictionary = {"saved": "good"}
    value = Pydt(2024, 1, 2)
    code = Pydt.__setstate__.__code__
    injected = False
    previous = sys.gettrace()

    def interleave(frame, event, arg):
        nonlocal injected
        if frame.f_code is code and event == "line" and not injected:
            statement = linecache.getline(code.co_filename, frame.f_lineno).lstrip()
            if statement.startswith("slot_items ="):
                dictionary[12345] = "unvalidated source edit"
                injected = True
        return interleave

    try:
        sys.settrace(interleave)
        value.__setstate__((dictionary, {"extra": 2}))
    finally:
        sys.settrace(previous)
    assert injected and 12345 in dictionary
    assert 12345 not in value.__dict__
    assert value.saved == "good" and value.extra == 2


@pytest.mark.parametrize("part", ["dictionary", "slots"])
def test_restore_rejects_invalid_key_before_applying_either_part(part):
    value = Pydt(2024, 1, 2)
    value.old = "retained"
    dictionary, slots = {"new": 1}, {"extra": 2}
    (dictionary if part == "dictionary" else slots)[42] = "invalid"
    with pytest.raises(TypeError):
        value.__setstate__((dictionary, slots))
    assert value.__dict__ == {"old": "retained"}


def test_restore_keeps_real_dictionary_update_tuple_and_original_exception():
    from datetime import timezone

    dictionary, slots = {"saved": []}, {"extra": 2}
    calls = []
    marker = LookupError("business update")

    class BusinessMapping:
        def update(self, entries):
            assert type(entries) is tuple
            calls.append(entries)
            dictionary[12345] = "late"
            slots[12345] = "late"
            raise marker

    mapping = BusinessMapping()

    class Child(Pydt):
        def __getattribute__(self, name):
            return mapping if name == "__dict__" else super().__getattribute__(name)

    value = Child(2024, 1, 2, tzinfo=timezone.utc, fold=1)
    original_hash = hash(value)
    with pytest.raises(LookupError) as observed:
        value.__setstate__((dictionary, slots))
    assert observed.value is marker and len(calls) == 1
    assert calls[0] == (("saved", dictionary["saved"]),)
    assert (value.year, value.month, value.day, value.tzinfo, value.fold) == (2024, 1, 2, timezone.utc, 1)
    assert hash(value) == original_hash
