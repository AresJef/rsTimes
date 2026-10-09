from datetime import date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal

import pytest

from rstimes import from_unix_ms, to_unix_ms

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MIN_MS = -62_135_596_800_000
MAX_MS = 253_402_300_799_999


@pytest.mark.parametrize(
    ("microseconds", "milliseconds"),
    [(-1001, -2), (-1000, -1), (-999, -1), (-1, -1),
     (0, 0), (1, 0), (999, 0), (1000, 1), (1001, 1)],
)
def test_floor_submillisecond_precision(microseconds, milliseconds):
    assert to_unix_ms(EPOCH + timedelta(microseconds=microseconds)) == milliseconds


@pytest.mark.parametrize(
    "offset", [timedelta(hours=8), timedelta(hours=-7),
               timedelta(hours=5, minutes=30, microseconds=500)],
)
def test_offset_datetimes_represent_the_same_instant(offset):
    value = (EPOCH + offset).replace(tzinfo=timezone(offset))
    assert to_unix_ms(value) == 0


@pytest.mark.parametrize("milliseconds", [MIN_MS, -86_400_001, -1001, -1, 0, 1,
                                          1_700_000_000_123, MAX_MS])
def test_integer_roundtrip_and_utc_result(milliseconds):
    result = from_unix_ms(milliseconds)
    assert result.tzinfo is timezone.utc
    assert to_unix_ms(result) == milliseconds


def test_negative_millisecond_has_expected_date():
    assert from_unix_ms(-1) == datetime(1969, 12, 31, 23, 59, 59, 999000,
                                      tzinfo=timezone.utc)


def test_datetime_limits_and_far_future_precision():
    assert from_unix_ms(MIN_MS) == datetime.min.replace(tzinfo=timezone.utc)
    assert from_unix_ms(MAX_MS) == datetime(9999, 12, 31, 23, 59, 59, 999000,
                                          tzinfo=timezone.utc)
    assert to_unix_ms(datetime.max.replace(tzinfo=timezone.utc)) == MAX_MS
    assert to_unix_ms(datetime(9999, 12, 31, 23, 59, 59, 998999,
                              tzinfo=timezone.utc)) == MAX_MS - 1


@pytest.mark.parametrize("value", [None, True, False, 1, 1.5, "1970-01-01",
                                   date(1970, 1, 1), object()])
def test_to_unix_ms_rejects_non_datetime(value):
    with pytest.raises(TypeError):
        to_unix_ms(value)


class NoOffset(tzinfo):
    def utcoffset(self, value):
        return None


@pytest.mark.parametrize("value", [datetime(1970, 1, 1),
                                   datetime(1970, 1, 1, tzinfo=NoOffset())])
def test_to_unix_ms_rejects_naive_datetime(value):
    with pytest.raises(ValueError, match="timezone-aware"):
        to_unix_ms(value)


@pytest.mark.parametrize("value", [None, True, False, 1.0, "1", Decimal("1"),
                                   EPOCH, object()])
def test_from_unix_ms_rejects_non_integer_and_bool(value):
    with pytest.raises(TypeError):
        from_unix_ms(value)


@pytest.mark.parametrize("value", [MIN_MS - 1, MAX_MS + 1, -(10**100), 10**100])
def test_from_unix_ms_rejects_out_of_range_integer(value):
    with pytest.raises(ValueError, match="range"):
        from_unix_ms(value)


@pytest.mark.parametrize("value", [
    datetime.min.replace(tzinfo=timezone(timedelta(hours=1))),
    datetime.max.replace(tzinfo=timezone(timedelta(hours=-1))),
])
def test_to_unix_ms_rejects_out_of_range_utc_conversion(value):
    with pytest.raises(ValueError, match="range"):
        to_unix_ms(value)
