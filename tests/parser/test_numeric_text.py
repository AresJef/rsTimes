"""Independent contracts for the two standalone Rust numeric text functions."""
from decimal import Decimal
import inspect
import itertools
import math
import random
import re
import struct

import numpy as np
import pytest

import rstimes
from rstimes.parser import parse_to_float, parse_to_integer


@pytest.mark.parametrize("text,expected", [
    ("0", 0), ("+0", 0), ("-0", 0), ("123", 123), ("-123", -123),
    (str(2**63), 2**63), (str(2**127 - 1), 2**127 - 1),
    (str(-(2**127)), -(2**127)), ("0" * 1000 + "17", 17),
])
def test_integer_exact_signed128(text, expected):
    result = parse_to_integer(text)
    assert type(result) is int and result == expected


@pytest.mark.parametrize("text", [str(2**127), str(-(2**127) - 1), "9" * 1000])
@pytest.mark.parametrize("strict", [False, True])
def test_integer_overflow_is_not_a_shorter_prefix(text, strict):
    with pytest.raises(OverflowError, match="parse_to_integer"):
        parse_to_integer(text, strict=strict)


@pytest.mark.parametrize("value", [2**127 - 1, -(2**127)])
@pytest.mark.parametrize("separator", [",", "."])
def test_grouped_integer_keeps_the_full_signed128_boundary(value, separator):
    token = f"{value:,}".replace(",", separator)
    assert parse_to_integer(token, allow_grouping=True) == value


@pytest.mark.parametrize("value", [2**127, -(2**127) - 1])
def test_grouped_integer_overflow_is_checked_after_valid_groups(value):
    with pytest.raises(OverflowError):
        parse_to_integer(f"{value:,}", allow_grouping=True, strict=False)


@pytest.mark.parametrize("text,expected", [
    ("0", 0.0), ("-0", -0.0), (".5", 0.5), (",5", 0.5),
    ("1.", 1.0), ("1,", 1.0), ("0.3", 0.3), ("0.29", 0.29),
    ("0.123456789123", 0.123456789123),
    ("0.99999999999999999999", 1.0),
    ("18446744073709551616", float(2**64)),
    ("0.123456789012345678901234567890", float(Decimal("0.123456789012345678901234567890"))),
    ("1" + "0" * 100, 1e100), ("1e308", 1e308),
    ("1.25e-3", 0.00125), ("1,25E+3", 1250.0),
    ("0." + "0" * 323 + "5", 5e-324), ("-1e-999", -0.0),
])
def test_float_correct_binary64_bits(text, expected):
    result = parse_to_float(text)
    assert type(result) is float
    assert struct.pack("!d", result) == struct.pack("!d", expected)


def test_float_heap_fallback_preserves_wide_text_and_large_finite_values():
    integer = 10**200
    assert parse_to_float(f"{integer:,}", allow_grouping=True) == 1e200
    assert parse_to_float("\ud800 " + str(integer), strict=False) == 1e200


@pytest.mark.parametrize("text", ["1e309", "-1e9999", "9" * 1000])
@pytest.mark.parametrize("strict", [False, True])
def test_float_overflow_remains_checked(text, strict):
    with pytest.raises(OverflowError, match="parse_to_float"):
        parse_to_float(text, strict=strict)


@pytest.mark.parametrize("function", [parse_to_integer, parse_to_float])
@pytest.mark.parametrize("text", ["", "abc", "NaN", "inf", "--", ".", "１２３"])
def test_no_ascii_number_is_an_error(function, text):
    for strict in [False, True]:
        with pytest.raises(ValueError):
            function(text, strict=strict)


@pytest.mark.parametrize("text,integer,floating", [
    ("价格 -123元", -123, -123.0), (" 123 ", 123, 123.0),
    ("12abc34", 12, 12.0), ("金额 - abc 12元", 12, 12.0),
    ("价格.abc5", 5, 5.0), ("\ud80012元", 12, 12.0),
    ("😀-12元", -12, -12.0), ("\x0012\x00", 12, 12.0),
])
def test_loose_extracts_one_contiguous_number(text, integer, floating):
    assert parse_to_integer(text, strict=False) == integer
    assert parse_to_float(text, strict=False) == floating
    for function in [parse_to_integer, parse_to_float]:
        with pytest.raises(ValueError):
            function(text)


@pytest.mark.parametrize("text,expected", [
    ("12.5", 12), ("12,5", 12), (".5", 5), ("1e3", 1),
])
def test_integer_loose_extracts_digits_without_float_conversion(text, expected):
    assert parse_to_integer(text, strict=False) == expected
    with pytest.raises(ValueError):
        parse_to_integer(text)


@pytest.mark.parametrize("text,expected", [
    ("12.5.6", 12.5), ("12,5,6", 12.5), ("1e+", 1.0),
    ("1e", 1.0), ("1e-3kg", 0.001),
])
def test_float_loose_longest_complete_prefix(text, expected):
    assert parse_to_float(text, strict=False) == expected
    with pytest.raises(ValueError):
        parse_to_float(text)


@pytest.mark.parametrize("text,integer,floating", [
    ("1.234", 1234, 1.234), ("1,234", 1234, 1.234),
    ("12,345", 12345, 12.345), ("-123.456", -123456, -123.456),
    ("1,234,567", 1234567, 1234567.0),
    ("1.234.567", 1234567, 1234567.0),
])
def test_grouping_type_priority(text, integer, floating):
    assert parse_to_integer(text, allow_grouping=True) == integer
    assert parse_to_float(text, allow_grouping=True) == floating
    assert parse_to_integer("数量 " + text + "件", strict=False, allow_grouping=True) == integer
    assert parse_to_float("金额 " + text + "元", strict=False, allow_grouping=True) == floating


@pytest.mark.parametrize("text,expected", [
    ("1.234,56", 1234.56), ("1,234.56", 1234.56),
    ("12,34", 12.34), ("1234,567", 1234.567),
    ("1,234,567.89", 1234567.89), ("1.234.567,89", 1234567.89),
    ("1,234.56e2", 123456.0), ("1,234e2", 123.4),
])
def test_grouped_float_does_not_remove_a_decimal_part(text, expected):
    assert parse_to_float(text, allow_grouping=True) == expected
    for strict in [False, True]:
        with pytest.raises(ValueError):
            parse_to_integer(text, strict=strict, allow_grouping=True)


@pytest.mark.parametrize("text", [
    "1,23,456", "1.23.456", "1,,234", "1..234", "1234,567,890",
    "1.234,5.6", "1,234.5,6", "1,234,", "1.234.",
])
@pytest.mark.parametrize("function", [parse_to_integer, parse_to_float])
@pytest.mark.parametrize("strict", [False, True])
def test_grouping_errors_cannot_be_evaded_by_loose_extraction(function, strict, text):
    with pytest.raises(ValueError, match="group"):
        function(text, strict=strict, allow_grouping=True)


@pytest.mark.parametrize("function", [parse_to_integer, parse_to_float])
@pytest.mark.parametrize("value", [None, 12, 1.5, True, b"12", bytearray(b"12"), [], object()])
def test_input_types_are_not_coerced(function, value):
    with pytest.raises(TypeError, match="token"):
        function(value)


class NativeText(str):
    """Business methods must not change the stored immutable Unicode content."""
    def __str__(self):
        raise AssertionError("display hook called")

    def __len__(self):
        raise AssertionError("length hook called")

    def __getitem__(self, key):
        raise AssertionError("item hook called")


def test_real_string_subclasses_use_native_content():
    assert parse_to_integer(NativeText("123")) == 123
    assert parse_to_float(NativeText("1,25")) == 1.25
    with pytest.raises(ValueError):
        parse_to_float(NativeText("invalid"))


@pytest.mark.parametrize("function", [parse_to_integer, parse_to_float])
@pytest.mark.parametrize("name", ["strict", "allow_grouping"])
@pytest.mark.parametrize("bad", [0, 1, None, "yes", [], object()])
def test_boolean_flags_follow_library_roles(function, name, bad):
    with pytest.raises(TypeError, match=name) as caught:
        function("", **{name: bad})
    assert function.__name__ in str(caught.value)


def test_numpy_boolean_options_are_supported():
    assert parse_to_integer("数量1,234件", strict=np.bool_(False), allow_grouping=np.bool_(True)) == 1234
    assert parse_to_float("金额1.234,56元", strict=np.bool_(False), allow_grouping=np.bool_(True)) == 1234.56


def test_flags_never_call_arbitrary_truth_hooks():
    class Trap:
        def __bool__(self):
            raise AssertionError("truth hook called")
    for function in [parse_to_integer, parse_to_float]:
        for name in ["strict", "allow_grouping"]:
            with pytest.raises(TypeError):
                function("1", **{name: Trap()})


def test_public_exports_and_keyword_only_options():
    for name, function in [("parse_to_integer", parse_to_integer), ("parse_to_float", parse_to_float)]:
        assert getattr(rstimes, name) is function
        assert function.__module__ == "rstimes.parser"
        signature = inspect.signature(function)
        assert signature.parameters["strict"].default is True
        assert signature.parameters["allow_grouping"].default is False
        with pytest.raises(TypeError):
            function("1", False)


def test_error_context_is_bounded_and_does_not_call_repr():
    class Trap:
        def __repr__(self):
            raise AssertionError("repr hook called")
    for function in [parse_to_integer, parse_to_float]:
        with pytest.raises(TypeError) as caught:
            function(Trap())
        assert function.__name__ in str(caught.value)
        with pytest.raises(ValueError) as caught:
            function("X" * 10000)
        assert len(str(caught.value)) < 1500
        assert "position" in str(caught.value)


def test_deterministic_generated_integers_and_decimals():
    rng = random.Random(65119)
    for _ in range(300):
        integer = rng.randrange(-(2**127), 2**127)
        assert parse_to_integer(str(integer)) == integer
        whole = rng.randrange(0, 10**15)
        fraction = str(rng.randrange(10**12)).zfill(12)
        plain = f"{whole}.{fraction}"
        expected = float(Decimal(plain))
        assert parse_to_float(plain) == expected
        assert parse_to_float(plain.replace(".", ",")) == expected
        for grouping, decimal in [(".", ","), (",", ".")]:
            grouped = f"{whole:,}".replace(",", grouping) + decimal + fraction
            assert parse_to_float(grouped, allow_grouping=True) == expected
    assert math.copysign(1, parse_to_float("-0,0")) == -1


def test_bounded_grammar_has_an_independent_regex_and_builtin_oracle():
    integer = re.compile(r"[+-]?[0-9]+", re.ASCII)
    floating = re.compile(r"[+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)(?:[eE][+-]?[0-9]+)?", re.ASCII)
    for length in range(5):
        for chars in itertools.product("01+-,.eX", repeat=length):
            text = "".join(chars)
            for strict in [True, False]:
                for function, grammar, converter in [
                    (parse_to_integer, integer, int), (parse_to_float, floating, float)
                ]:
                    match = grammar.fullmatch(text) if strict else grammar.search(text)
                    if match is None:
                        with pytest.raises(ValueError):
                            function(text, strict=strict)
                    else:
                        expected = converter(match.group().replace(",", "."))
                        result = function(text, strict=strict)
                        assert result == expected, (text, strict, function.__name__)


@pytest.mark.parametrize("text", ["+NaN", "-NaN", "+inf", "-inf", "Infinity", "+Infinity"])
def test_std_conversion_does_not_expand_special_value_syntax(text):
    with pytest.raises(ValueError):
        parse_to_float(text)
