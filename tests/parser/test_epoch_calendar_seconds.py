"""An independent datetime/400-year oracle protects native-width calendar work."""

from datetime import datetime

import pytest

from rstimes import parse_to_epoch


@pytest.mark.parametrize("year", [0, 1969, 2024, 10000, 1_000_000, 2_147_483_647])
@pytest.mark.parametrize("isoformat", [False, True])
@pytest.mark.parametrize("suffix,offset_seconds", [("Z", 0), ("+08:00", 28800),
                                                  ("-05:30", -19800)])
@pytest.mark.parametrize("unit,scale", [("s", 10**9), ("ms", 10**6),
                                      ("us", 1000), ("ns", 1)])
def test_calendar_seconds_stay_exact_through_the_full_parser_year_range(
    year, isoformat, suffix, offset_seconds, unit, scale,
):
    # Gregorian400-year cycles preserve leap days and weekdays. Reduce into
    # datetime's real supported range, then add whole cycles using Python ints.
    cycles, remainder = divmod(year - 2000, 400)
    representative = datetime(2000 + remainder, 12, 31, 23, 59, 59, 123456)
    delta = representative - datetime(1970, 1, 1)
    days = delta.days + cycles * 146097
    nanos = ((days * 86400 + delta.seconds - offset_seconds) * 10**9
             + delta.microseconds * 1000 + 789)
    text = f"{year:04d}-12-31T23:59:59.123456789{suffix}"

    result = parse_to_epoch(text, unit=unit, isoformat=isoformat)

    assert type(result) is int
    assert result == nanos // scale
