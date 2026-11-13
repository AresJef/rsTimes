"""Useful public error context with preserved standard categories and callbacks."""
from datetime import datetime, timedelta

import pytest

from rstimes import Configs, Delta, Pydt, parse, parse_to_epoch, parse_str


@pytest.mark.parametrize("call, category, entry, field", [
    (lambda: Delta(days="one"), TypeError, "Delta()", "days"),
    (lambda: Delta(days=10**100), OverflowError, "Delta()", "days"),
    (lambda: Delta(days=2**63-1) + Delta(days=1), OverflowError, "Delta.__add__", "operands"),
    (lambda: Delta(months=1).to_timedelta(), ValueError, "Delta.to_timedelta", "start"),
    (lambda: Delta(days=1).apply_many([datetime(2024, 1, 1), "bad"]), TypeError, "Delta.apply_many", "1"),
    (lambda: Configs().add_month("harvest", 1.5), TypeError, "Configs.add_month", "month"),
    (lambda: Configs().set_month({"harvest": 13}), ValueError, "Configs.set_month", "13"),
    (lambda: Configs().del_month(1), TypeError, "Configs.del_month", "token"),
    (lambda: parse(object()), TypeError, "parse()", "dtobj"),
    (lambda: parse(10**100), OverflowError, "parse()", "dtobj"),
    (lambda: parse_str("2024-01-02 12:99", strict=True), ValueError, "parse_str()", "minute"),
    (lambda: parse_to_epoch("bad"), ValueError, "parse_to_epoch()", "dtobj"),
    (lambda: parse_to_epoch(1, input_unit="bad"), ValueError, "parse_to_epoch()", "input_unit"),
    (lambda: Pydt.fromseconds("1"), TypeError, "Pydt.fromseconds", "seconds"),
    (lambda: Pydt.frommicroseconds(10**100), OverflowError, "Pydt.frommicroseconds", "us"),
    (lambda: Pydt.parse(object()), TypeError, "Pydt.parse", "dtobj"),
    (lambda: Pydt(2024, 1, 1).add(hours="bad"), TypeError, "Pydt.add", "hours"),
])
def test_public_failure_names_entry_and_relevant_argument(call, category, entry, field):
    with pytest.raises(category) as info:
        call()
    text = str(info.value) + " ".join(getattr(info.value, "__notes__", ()))
    assert entry in text and field in text


@pytest.mark.parametrize("exception", [RuntimeError("callback"), MemoryError("callback"),
    KeyboardInterrupt("callback")])
def test_custom_constructor_failures_are_not_reported_as_bad_parser_input(exception):
    def constructor(**kwargs):
        raise exception

    for entry in (parse, parse_str):
        with pytest.raises(type(exception)) as info:
            entry("2024-05-07", dtclass=constructor)
        assert info.value is exception


def test_custom_exception_subclass_keeps_identity():
    class Custom(ValueError):
        pass

    error = Custom("provider failed")

    class Number:
        def __index__(self):
            raise error

    with pytest.raises(Custom) as info:
        Delta(days=Number())
    assert info.value is error


@pytest.mark.parametrize("exception", [MemoryError("context"), KeyboardInterrupt("context")])
@pytest.mark.parametrize("domain_name,call", [
    ("ParseError", lambda: parse_str("not a date")),
    ("ConfigError", lambda: Configs().add_month("harvest", 13)),
])
def test_error_context_construction_propagates_new_failure(monkeypatch, exception, domain_name, call):
    from rstimes import errors

    original = getattr(errors, domain_name)
    calls = 0

    class Domain(original):
        def __new__(cls, *args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise exception
            return super().__new__(cls, *args)

    monkeypatch.setattr(errors, domain_name, Domain)
    with pytest.raises(type(exception)) as info:
        call()
    assert info.value is exception
    assert calls == 1


@pytest.mark.parametrize("exception", [MemoryError("message"), KeyboardInterrupt("message")])
@pytest.mark.parametrize("entry", ["delta", "parser"])
def test_error_message_failure_propagates_without_display_fallback(exception, entry):
    class Message:
        def __str__(self):
            raise exception

    error = ValueError(Message())

    class Number:
        def __index__(self):
            raise error

    def constructor(**kwargs):
        raise error

    with pytest.raises(ValueError) as info:
        if entry == "delta":
            Delta(days=Number())
        else:
            parse_str("2024-01-01", dtclass=constructor)
    assert info.value is error


def test_behavior_comparison_keeps_callback_failures_distinct():
    from outcomes import outcomes_equal

    expected = {"error": {"type": "builtins.RuntimeError", "message": "provider failure"}}
    wrapped = {"error": {"type": "rstimes.errors.ParserFailedError", "message": "bad input",
                         "cause": {"type": "builtins.RuntimeError", "message": "wrong"}}}
    different = {"error": {"type": "builtins.RuntimeError", "message": "wrong"}}
    assert not outcomes_equal(wrapped, expected)
    assert not outcomes_equal(different, expected)
    old_wrapper = {"error": {"type": "cytimes.errors.ParserFailedError", "message": "legacy wrapper",
                             "cause": expected["error"]}}
    assert outcomes_equal(expected, old_wrapper)
    wrong_wrapper = {"error": {"type": "rstimes.errors.ParserFailedError",
                               "message": "an integer is required"}}
    assert not outcomes_equal(wrong_wrapper, {"error": {"type": "builtins.TypeError", "message": "bad type"}})
