"""Independent unit semantics and binding-phase errors at the epoch boundary."""

import inspect

import numpy as np
import pytest

from rstimes import parse_to_epoch


@pytest.mark.parametrize("unit,expected", [
    ("s", 0), ("ms", 123), ("us", 123456), ("ns", 123456789),
])
def test_epoch_output_unit_has_exact_public_string_meaning(unit, expected):
    assert parse_to_epoch("1970-01-01T00:00:00.123456789", unit=unit) == expected


@pytest.mark.parametrize("unit,expected", [
    ("s", 3_000_000_000), ("ms", 3_000_000), ("us", 3000), ("ns", 3),
])
def test_epoch_input_unit_has_exact_numeric_tick_meaning(unit, expected):
    assert parse_to_epoch(3, unit="ns", input_unit=unit) == expected


@pytest.mark.parametrize("parameter", ["unit", "input_unit"])
@pytest.mark.parametrize("value", [None, True, False, 0, 1.0, np.int64(1),
                                   np.bool_(False), b"us", bytearray(b"us")])
def test_epoch_units_reject_non_strings_including_explicit_none(parameter, value):
    with pytest.raises(TypeError):
        parse_to_epoch(0, **{parameter: value})


@pytest.mark.parametrize("parameter", ["unit", "input_unit"])
@pytest.mark.parametrize("value", ["", "US", "Ns", "microseconds", "μs"])
def test_epoch_unknown_units_are_value_errors_with_the_parameter(parameter, value):
    with pytest.raises(ValueError, match=parameter):
        parse_to_epoch(0, **{parameter: value})


@pytest.mark.parametrize("parameter", ["unit", "input_unit"])
def test_epoch_unit_encoding_error_stays_in_argument_extraction(parameter):
    with pytest.raises(UnicodeEncodeError) as caught:
        parse_to_epoch(0, **{parameter: "\ud800"})
    assert any(parameter in note for note in caught.value.__notes__)


@pytest.mark.parametrize("parameter", ["unit", "input_unit"])
@pytest.mark.parametrize("word", ["s", "ms", "us", "ns"])
def test_epoch_string_subclass_uses_stored_text_without_str_callback(parameter, word):
    class Literal(str):
        def __str__(self):
            raise AssertionError("unit strings must use stored Unicode")

    options = {"unit": "ns", "input_unit": "s", parameter: Literal(word)}
    reference = {"unit": "ns", "input_unit": "s", parameter: word}
    assert parse_to_epoch(3, **options) == parse_to_epoch(3, **reference)


def test_invalid_string_unit_does_not_run_subclass_repr_for_error_preview():
    class Literal(str):
        def __repr__(self):
            raise AssertionError("the error preview must not invoke unit repr")

    with pytest.raises(ValueError, match="unit"):
        parse_to_epoch(0, unit=Literal("invalid"))


@pytest.mark.parametrize("options,expected,parameter", [
    ({"unit": "invalid", "strict": 1}, TypeError, "strict"),
    ({"unit": "invalid", "input_unit": None}, TypeError, "input_unit"),
    ({"unit": "invalid", "input_unit": "invalid"}, ValueError, "unit"),
    ({"unit": "\ud800", "strict": 1}, UnicodeEncodeError, "unit"),
    ({"input_unit": "\ud800", "strict": 1}, TypeError, "strict"),
])
def test_epoch_unit_value_validation_preserves_binding_error_order(options, expected, parameter):
    with pytest.raises(expected) as caught:
        parse_to_epoch(0, **options)
    assert parameter in " ".join([str(caught.value), *getattr(caught.value, "__notes__", [])])


def test_epoch_signature_keeps_string_defaults_and_parameter_order():
    parameters = inspect.signature(parse_to_epoch).parameters
    assert list(parameters) == ["dtobj", "unit", "default", "yearfirst", "dayfirst",
                                "ignoretz", "isoformat", "strict", "cfg", "input_unit"]
    assert parameters["unit"].default == "us"
    assert parameters["input_unit"].default == "s"
    assert parameters["input_unit"].kind is inspect.Parameter.KEYWORD_ONLY
