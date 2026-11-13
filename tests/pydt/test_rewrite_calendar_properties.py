"""Native readonly properties keep the approved stored-field and error contracts."""
import calendar
from datetime import datetime

import pytest

from rstimes import Pydt


@pytest.mark.parametrize("name", ["day_of_year", "days_in_month", "is_leap_year"])
@pytest.mark.parametrize("year,month,day", [(1900, 2, 28), (2000, 2, 29), (2024, 12, 31)])
def test_native_property_reads_stored_fields_and_keeps_its_documentation(name, year, month, day):
    class Child(Pydt):
        year = property(lambda self: 1)
        month = property(lambda self: 1)
        day = property(lambda self: 1)

    date = datetime(year, month, day)
    expected = {
        "day_of_year": date.timetuple().tm_yday,
        "days_in_month": calendar.monthrange(year, month)[1],
        "is_leap_year": calendar.isleap(year),
    }[name]
    descriptor = getattr(Pydt, name)
    assert isinstance(descriptor, property)
    assert "Returns" in descriptor.__doc__
    assert descriptor.fget(date) == expected
    value = Child(year, month, day)
    assert getattr(value, name) == expected
    with pytest.raises(AttributeError):
        setattr(value, name, expected)


@pytest.mark.parametrize("name", ["day_of_year", "days_in_month", "is_leap_year"])
def test_native_property_bad_receiver_names_the_public_entry(name):
    with pytest.raises(TypeError, match="Pydt[.]" + name):
        getattr(Pydt, name).fget(object())
