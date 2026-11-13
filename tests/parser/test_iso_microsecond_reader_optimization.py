"""Independent date and integer answers at a six-digit fraction boundary."""
from datetime import datetime, timedelta, timezone

import pytest

from rstimes import parse_str, parse_to_epoch


class FractionText(str):
    def __str__(self):
        raise AssertionError("read the stored string")

    def __len__(self):
        raise AssertionError("read the stored length")

    def __getitem__(self, key):
        raise AssertionError("read the stored characters")


@pytest.mark.parametrize("carrier", [str, FractionText])
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("fraction", ["0", "1", "123", "000001", "123456", "999999", "1234567", "123456789"])
def test_iso_fraction_keeps_value_and_exact_string_boundary(carrier, strict, fraction):
    token = carrier("2024-05-07T15:30:01." + fraction)
    expected = datetime(2024, 5, 7, 15, 30, 1, int(fraction[:6].ljust(6, "0")))
    result = parse_str(token, strict=strict)
    assert type(result) is datetime and result == expected


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("clock,offset", [("00:00:30.123456", timedelta(seconds=30, microseconds=123456)),
                                           ("02:30:00.000001", timedelta(hours=2, minutes=30, microseconds=1))])
def test_six_digit_timezone_fraction_keeps_its_real_signed_microseconds(strict, sign, clock, offset):
    token = "2024-05-07T15:30:01.123456" + ("+" if sign > 0 else "-") + clock
    expected = datetime(2024, 5, 7, 15, 30, 1, 123456, tzinfo=timezone(sign * offset))
    result = parse_str(token, strict=strict, ignoretz=False)
    assert result.replace(tzinfo=None) == expected.replace(tzinfo=None)
    assert result.utcoffset() == sign * offset


@pytest.mark.parametrize("strict", [False, True])
def test_nondigit_in_six_byte_tail_keeps_the_existing_general_grammar(strict):
    # strict validates fields and conflicts; it is not a full-format consumer.
    result = parse_str("2024-05-07T15:30:01.12345x", strict=strict)
    assert result == datetime(2024, 5, 7, 15, 30, 1, 123450)


@pytest.mark.parametrize("fraction", ["123456", "123456789"])
@pytest.mark.parametrize("sign", [-1, 1])
def test_nano_policy_and_microsecond_offset_keep_one_complete_integer_epoch(fraction, sign):
    token = "2024-05-07T15:30:01." + fraction + ("+" if sign > 0 else "-") + "00:00:30.123456"
    delta = datetime(2024, 5, 7, 15, 30, 1) - datetime(1970, 1, 1)
    expected = ((delta.days * 86400 + delta.seconds) * 10**9
                + int(fraction.ljust(9, "0")) - sign * (30 * 10**9 + 123456 * 1000))
    assert parse_to_epoch(token, unit="ns", ignoretz=False) == expected


@pytest.mark.parametrize("separator", ["t", " "])
def test_six_digits_retain_other_existing_iso_clock_separators(separator):
    assert parse_str("2024-05-07" + separator + "15:30:01.123456") == datetime(2024, 5, 7, 15, 30, 1, 123456)
