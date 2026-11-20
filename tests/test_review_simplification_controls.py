"""Independent controls for validations retained through structural changes."""
from datetime import date, datetime, timedelta

import numpy as np
import pytest

from rstimes import Delta, Pydt, parse_str


def test_delta_restores_private_slots_even_when_setter_modifies_incoming_state():
    payload = []
    dictionary = {"business": payload}
    slots = {"a": payload, "b": payload}
    visits = []

    class Business(Delta):
        __slots__ = ("a", "b", "__dict__")

        def __setattr__(self, field, value):
            if field == "a":
                visits.append(field)
                slots.pop("b")
                dictionary.clear()
                self.__dict__["during"] = "setter called"
            super().__setattr__(field, value)

    target = Business(days=1, nanoseconds=7)
    Delta.__setstate__(target, (dictionary, slots))
    assert target.days == 1 and target.nanoseconds == 7
    assert target.a is target.b is target.business is payload
    assert target.during == "setter called" and visits == ["a"]
    assert list(slots) == ["a"] and dictionary == {}


@pytest.mark.parametrize("source, expected", (
    (np.datetime64(-1, "M"), datetime(1969, 12, 1)),
    (np.datetime64(1, "3M"), datetime(1970, 4, 1)),
    (np.datetime64("2000", "Y"), datetime(2000, 1, 1)),
    (np.datetime64("0001", "Y"), datetime(1, 1, 1)),
))
def test_numpy_calendar_units_use_independent_month_starts(source, expected):
    assert Pydt.fromdatetime64(source) == expected


def test_wide_numpy_year_and_nat_still_respect_final_policy():
    with pytest.raises((ValueError, OverflowError), match="year|range"):
        Pydt.fromdatetime64(np.datetime64("12000", "Y"))
    with pytest.raises(ValueError, match="NaT"):
        Pydt.fromdatetime64(np.datetime64("NaT", "M"))


@pytest.mark.parametrize("base", (date(1, 2, 3), date(1970, 2, 3), date(1972, 2, 3), date(2024, 2, 3)))
@pytest.mark.parametrize("strict", (False, True))
def test_real_default_date_still_supplies_missing_prefix(base, strict):
    class BusinessDate(date):
        @property
        def year(self):
            raise AssertionError("use native calendar storage")

    expected = datetime.combine(base, datetime(2024, 3, 1, 12, 34, 56).time())
    for value in (base, BusinessDate(base.year, base.month, base.day), expected):
        assert parse_str("12:34:56", default=value, strict=strict) == expected
    for value in ("1970-01-01", 0, 0.0):
        assert parse_str("12:34:56", default=value, strict=strict) == datetime(1970, 1, 1, 12, 34, 56)


def test_pddt_calendar_precheck_still_sees_values_hidden_by_empty_or_missing_rows():
    pytest.importorskip("pandas")
    from rstimes import Pddt

    with pytest.raises(ValueError, match="ISO week"):
        Pddt.fromisocalendar([], 0, 1)
    with pytest.raises(ValueError, match="ISO week"):
        Pddt.fromisocalendar([None], [0], [0])
    assert Pddt.fromisocalendar([2024, 2024], 9, [1, None], unit="s").asi8.tolist() == [
        1708905600, -(2**63),
    ]


@pytest.mark.parametrize("with_values", (False, True))
@pytest.mark.parametrize("name", (None, "", "override"))
@pytest.mark.parametrize("timezone", (None, "America/New_York", "UTC"))
def test_pandas_native_date_constructor_preserves_the_prepared_name(with_values, name, timezone):
    pd = pytest.importorskip("pandas")
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    class StoredName(str):
        def __str__(self):
            raise AssertionError("use stored name")

    values = pd.DatetimeIndex(["2024-01-01", None] if with_values else [],
                              tz=timezone, name=StoredName("from_pandas")).as_unit("ns")
    dtype = pl.Datetime("ns", "UTC")
    for selected in (name, StoredName(name) if name is not None else None):
        result = Pldt(values, unit="ns", name=selected, tz="UTC")
        assert result.name == ("from_pandas" if name is None else name)
        assert result.dtype == dtype
        offset = 5 * 3600 * 10**9 if timezone == "America/New_York" else 0
        assert result.to_physical().to_list() == ([1704067200000000000 + offset, None] if with_values else [])


def test_fixed_subtraction_keeps_direction_borrow_and_absolute_fields():
    value = Delta(days=2, nanoseconds=1, day=7)
    span = timedelta(days=1, microseconds=1)

    def ticks(delta):
        seconds = ((delta.days * 24 + delta.hours) * 60 + delta.minutes) * 60 + delta.seconds
        return seconds * 10**9 + delta.microseconds * 1000 + delta.nanoseconds

    for foreign in (span, np.timedelta64(86_400_000_001, "us")):
        forward, reverse = value - foreign, foreign - value
        assert forward.day == reverse.day == 7
        assert ticks(forward) == 86_400_000_000_000 - 999
        assert ticks(reverse) == -ticks(forward)
