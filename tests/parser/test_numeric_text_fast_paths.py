"""Independent boundary protection for numeric-only performance changes."""
from decimal import Decimal
import random
import struct

import pytest

from rstimes import parse_to_float, parse_to_integer


def bits(value):
    return struct.pack("!d", value)


@pytest.mark.parametrize("count", [1, 6, 15, 16, 17, 18, 19, 38, 39, 80])
@pytest.mark.parametrize("sign", ["", "+", "-"])
def test_integer_native_word_boundary_keeps_signed128_capacity(count, sign):
    text = sign + "9" * count
    expected = int(text)
    for prefix, strict in [("", True), ("数量 ", False)]:
        token = prefix + text
        if -(2**127) <= expected < 2**127:
            assert parse_to_integer(token, strict=strict) == expected
        else:
            with pytest.raises(OverflowError):
                parse_to_integer(token, strict=strict)


@pytest.mark.parametrize("separator", [".", ","])
@pytest.mark.parametrize("negative", [False, True])
def test_decimal_word_boundary_and_divisor_are_correctly_rounded(separator, negative):
    # Decimal(text) preserves the exact input, without Decimal-context division.
    for mantissa in [0, 1, 3, 29, 10**15 - 1, 10**15,
                     2**53 - 1, 2**53, 2**53 + 1, 10**18 - 1]:
        for places in range(21):
            digits = str(mantissa).zfill(places + 1)
            text = digits if places == 0 else digits[:-places] + "." + digits[-places:]
            text = ("-" if negative else "") + text
            expected = float(Decimal(text))
            token = text.replace(".", separator)
            assert bits(parse_to_float(token)) == bits(expected), text
            assert bits(parse_to_float("\ud800价 " + token, strict=False)) == bits(expected), text


def test_seeded_short_decimal_formats_have_independent_binary64_expectations():
    rng = random.Random(9031618)
    for _ in range(4000):
        size = rng.randrange(1, 20)
        digits = "".join(str(rng.randrange(10)) for _ in range(size))
        split = rng.randrange(size + 1)
        text = digits[:split] + "." + digits[split:]
        if rng.randrange(2):
            text = "-" + text
        expected = float(Decimal(text))
        assert bits(parse_to_float(text)) == bits(expected), text
        assert bits(parse_to_float(text.replace(".", ","))) == bits(expected), text


def test_seeded_integer_chunks_keep_complete_signed128_values():
    rng = random.Random(0x49128)
    for _ in range(2000):
        text = rng.choice(["", "+", "-"]) + "".join(
            str(rng.randrange(10)) for _ in range(rng.randrange(1, 46)))
        expected = int(text)
        for prefix, strict in [("", True), ("价", False), ("😀", False)]:
            if -(2**127) <= expected < 2**127:
                assert parse_to_integer(prefix + text, strict=strict) == expected
            else:
                with pytest.raises(OverflowError):
                    parse_to_integer(prefix + text, strict=strict)


def test_four_digit_byte_classification_rejects_all_nondigit_latin1_bytes():
    for position in range(1, 5):
        for code in range(256):
            text = "123456"[:position] + chr(code) + "123456"[position + 1:]
            if 48 <= code <= 57:
                assert parse_to_integer(text) == int(text)
            else:
                with pytest.raises(ValueError):
                    parse_to_integer(text)
            end = next((i for i, char in enumerate(text) if not "0" <= char <= "9"), len(text))
            assert parse_to_integer(text, strict=False) == int(text[:end])


@pytest.mark.parametrize("value", [2**64 - 1, 2**64, 2**64 + 1, -(2**64 - 1), -2**64, -(2**64 + 1)])
def test_native_word_promotes_only_at_its_real_capacity(value):
    assert parse_to_integer(str(value)) == value
    assert parse_to_integer("USD " + str(value), strict=False) == value
    assert parse_to_integer("价格" + str(value), strict=False) == value


@pytest.mark.parametrize("function", [parse_to_integer, parse_to_float])
def test_token_remains_a_supported_keyword_and_none_flags_are_rejected(function):
    assert function(token="123") == 123
    for option in ["strict", "allow_grouping"]:
        with pytest.raises(TypeError, match=option):
            function(token="123", **{option: None})


@pytest.mark.parametrize("function", [parse_to_integer, parse_to_float])
def test_invalid_grouping_precedes_large_value_conversion(function):
    with pytest.raises(ValueError, match="group"):
        function("9" * 50 + ",23,456", allow_grouping=True)


@pytest.mark.parametrize("length", [18, 19, 127, 128, 129, 1000])
def test_leading_zero_and_long_prefix_keep_complete_numeric_fragment(length):
    zeros = "0" * length
    prefix = "价格" * length
    assert parse_to_integer(zeros + "17") == 17
    assert parse_to_integer(prefix + zeros + "17", strict=False) == 17
    assert bits(parse_to_float(prefix + zeros + "0.3", strict=False)) == bits(0.3)


@pytest.mark.parametrize("prefix", ["x", "价格", "😀", "\ud800", "x" * 128])
def test_first_digit_search_keeps_adjacent_sign_and_decimal_meaning(prefix):
    for fragment, expected_float, expected_integer in [
        ("-.5", -0.5, 5), ("+.5", 0.5, 5), (".,5", 0.5, 5),
        ("--5", -5.0, -5), ("+x-5", -5.0, -5),
        (".x5", 5.0, 5), ("-,5", -0.5, 5),
    ]:
        assert bits(parse_to_float(prefix + fragment, strict=False)) == bits(expected_float)
        assert parse_to_integer(prefix + fragment, strict=False) == expected_integer
