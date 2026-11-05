"""DCR04: error context does not execute a metaclass display descriptor."""
from concurrent.futures import CancelledError

import pytest

from rstimes import Delta, Pddt, Pldt, Pydt, parse_to_epoch
from rstimes.errors import _preview
from rstimes._native import _pydt_from_ordinal


CALLS = (
    ("Pddt", lambda value: Pddt([0], unit=value), False),
    ("Pldt", lambda value: Pldt([0], unit=value), False),
    ("Delta", lambda value: Delta(day=value), True),
    ("Pydt.fromordinal", lambda value: Pydt.fromordinal(value), True),
    ("Pddt.fromordinal", lambda value: Pddt.fromordinal(value), True),
    ("Pldt.fromordinal", lambda value: Pldt.fromordinal(value), True),
    ("parse_to_epoch", parse_to_epoch, False),
)


def bad_value(mode, calls, original):
    def displayed_name(cls):
        calls.append("display_name")
        if mode == "raises":
            raise RuntimeError("unnecessary type display callback")
        return 17 if mode == "non_string" else "displayed-name"

    meta = type("DisplayMeta", (type,), {} if mode == "control" else {"__name__": property(displayed_name)})

    class Bad(metaclass=meta):
        def __index__(self):
            calls.append("index")
            raise original

        def __repr__(self):
            calls.append("repr")
            raise AssertionError("user repr must not run")

        def __str__(self):
            calls.append("str")
            raise AssertionError("user str must not run")

        def __len__(self):
            calls.append("len")
            raise AssertionError("user length must not run")

    if mode == "long":
        type.__dict__["__name__"].__set__(Bad, "B" * 10000)
    return Bad()


@pytest.mark.parametrize("mode", ("control", "raises", "non_string", "long"))
@pytest.mark.parametrize("entry,call,indexed", CALLS, ids=[item[0] for item in CALLS])
def test_public_error_context_uses_real_bounded_type_name(mode, entry, call, indexed):
    calls = []
    cause = RuntimeError("original cause")
    original = LookupError("actual index failure")
    original.__cause__ = cause
    original.add_note("original business note")
    value = bad_value(mode, calls, original)
    with pytest.raises(LookupError if indexed else TypeError) as caught:
        call(value)
    if indexed:
        assert caught.value is original and caught.value.args == ("actual index failure",)
        assert caught.value.__cause__ is cause
        assert caught.value.__notes__[0] == "original business note"
        assert calls == ["index"]
    else:
        assert entry in str(caught.value)
        assert calls == []
    # The exact builtin class name is bounded independently of user displays.
    preview = _preview(value)
    assert len(preview) <= 120 and preview.startswith("<B")
    assert calls == (["index"] if indexed else [])


@pytest.mark.parametrize("exception", (MemoryError, CancelledError, KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("entry,call,indexed", [item for item in CALLS if item[2]], ids=[item[0] for item in CALLS if item[2]])
def test_critical_callback_error_gets_no_preview_or_added_entry_note(exception, entry, call, indexed):
    calls = []
    original = exception("critical callback")
    original.add_note("already present")
    value = bad_value("raises", calls, original)
    expected_notes = ["already present"]
    if entry == "Pydt.fromordinal":
        # PyO3's argument extraction adds its own note before the Python error
        # layer receives the exception. Preserve that real boundary behavior.
        native_error = exception("critical callback")
        native_error.add_note("already present")
        native_calls = []
        with pytest.raises(exception) as native_caught:
            _pydt_from_ordinal(Pydt, bad_value("raises", native_calls, native_error), None)
        assert native_caught.value is native_error and native_calls == ["index"]
        expected_notes = native_error.__notes__.copy()
    with pytest.raises(exception) as caught:
        call(value)
    assert caught.value is original and original.__notes__ == expected_notes
    assert calls == ["index"]
