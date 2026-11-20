"""Safe error previews use the real name payload without business hooks."""
from concurrent.futures import CancelledError

import pytest

from rstimes import Delta, Pddt, Pldt, Pydt, parse_str, parse_to_float, parse_to_integer
from rstimes.errors import _preview


ENTRIES = (
    ("Delta", lambda x: Delta(day=x), True),
    ("Pydt.fromordinal", Pydt.fromordinal, True),
    ("Pddt.fromordinal", lambda x: Pddt.fromordinal(x, size=1), True),
    ("Pldt.fromordinal", lambda x: Pldt.fromordinal(x, size=1), True),
    ("parse_str", parse_str, False),
    ("parse_to_integer", parse_to_integer, False),
    ("parse_to_float", parse_to_float, False),
    ("integer.strict", lambda x: parse_to_integer("3", strict=x), False),
    ("float.grouping", lambda x: parse_to_float("3", allow_grouping=x), False),
)


def payload_value(name, calls, original):
    """Put a real str subclass in type storage, rather than fake its metaclass."""
    class Name(str):
        def fail(self, *args, **kwargs):
            calls.append("display")
            raise RuntimeError("type-name display must not execute")

        __getitem__ = __len__ = __str__ = __repr__ = __add__ = __radd__ = __format__ = fail

    class Value:
        def __index__(self):
            calls.append("index")
            raise original

        def __repr__(self):
            calls.append("value display")
            raise RuntimeError("value display must not execute")

    Value.__name__ = Name(name)
    return Value()


@pytest.mark.parametrize("name", ["BusinessValue", "日期" * 500])
@pytest.mark.parametrize("entry,action,indexed", ENTRIES, ids=[x[0] for x in ENTRIES])
def test_real_type_name_payload_cannot_mask_public_failure(name, entry, action, indexed):
    calls = []
    original = LookupError("original numeric callback")
    cause = ValueError("business cause")
    original.__cause__ = cause
    original.add_note("business note")
    value = payload_value(name, calls, original)
    with pytest.raises(LookupError if indexed else TypeError) as caught:
        action(value)
    if indexed:
        assert caught.value is original
        assert original.args == ("original numeric callback",)
        assert original.__cause__ is cause
        assert original.__notes__[0] == "business note"
    assert calls == (["index"] if indexed else [])
    assert len(_preview(value)) <= 120
    assert calls == (["index"] if indexed else [])


@pytest.mark.parametrize("size", [9, 512, 1_000_000])
@pytest.mark.parametrize("unicode", [False, True])
def test_name_read_is_bounded_and_keeps_existing_plain_name_output(size, unicode):
    name = ("日" if unicode else "X") * size
    calls = []
    value = payload_value(name, calls, LookupError("unused"))
    expected = ("<" + name[:116] + ("..." if len(name) > 116 else "") + ">")[:120]
    assert _preview(value) == expected
    assert calls == []


@pytest.mark.parametrize("exception", [MemoryError, CancelledError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("entry,action,indexed", [x for x in ENTRIES if x[2]], ids=[x[0] for x in ENTRIES if x[2]])
def test_critical_error_does_not_preview_real_name_subclass(exception, entry, action, indexed):
    calls = []
    original = exception("critical callback")
    original.add_note("already present")
    with pytest.raises(exception) as caught:
        action(payload_value("BusinessValue", calls, original))
    assert caught.value is original
    assert original.__notes__[0] == "already present"
    assert calls == ["index"]
