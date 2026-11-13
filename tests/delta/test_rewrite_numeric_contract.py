"""P04: keep Delta normalization, change only the approved input roles."""
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction

from dateutil.relativedelta import relativedelta
import numpy as np
import pytest

from rstimes import Delta


@pytest.mark.parametrize("field", ["years", "quarters", "months"])
@pytest.mark.parametrize("value", [1.0, np.float32(1.0), "1", Decimal(1)])
def test_calendar_amounts_require_integer_protocol(field, value):
    with pytest.raises(TypeError):
        Delta(**{field: value})


@pytest.mark.parametrize("field", ["years", "quarters", "months"])
def test_calendar_amounts_accept_index_once(field):
    class Index:
        calls = 0

        def __index__(self):
            self.calls += 1
            return 2

    value = Index()
    assert Delta(**{field: value}) == Delta(**{field: 2})
    assert value.calls == 1


@pytest.mark.parametrize("field", [
    "years", "quarters", "months", "weeks", "days", "hours", "minutes",
    "seconds", "milliseconds", "microseconds", "year", "month", "day",
    "weekday", "hour", "minute", "second", "millisecond", "microsecond",
])
@pytest.mark.parametrize("value", [True, np.bool_(False)])
def test_public_constructor_rejects_boolean_numeric_values(field, value):
    with pytest.raises(TypeError):
        Delta(**{field: value})


@pytest.mark.parametrize("kind", [float, np.float16, np.float32, np.float64])
@pytest.mark.parametrize("field,factor", [
    ("weeks", 604800000000), ("days", 86400000000), ("hours", 3600000000),
    ("minutes", 60000000), ("seconds", 1000000), ("milliseconds", 1000),
    ("microseconds", 1),
])
def test_fixed_duration_floats_keep_the_stored_fraction(kind, field, factor):
    value = kind(-1.125)
    micros = round(Fraction(float(value)) * factor)
    expected = timedelta(microseconds=micros)
    assert datetime(2024, 5, 7) + Delta(**{field: value}) == datetime(2024, 5, 7) + expected


@pytest.mark.parametrize("value", [Fraction(1, 2), Decimal("0.5"), 1+0j, "0.5"])
def test_fixed_duration_does_not_coerce_other_numeric_families(value):
    with pytest.raises(TypeError):
        Delta(hours=value)


def test_unsupported_float_protocol_is_never_called():
    class OnlyFloat:
        def __float__(self):
            raise AssertionError("not an allowed scalar type")

    with pytest.raises(TypeError):
        Delta(hours=OnlyFloat())


def test_longdouble_is_not_admitted_when_it_is_a_distinct_type():
    if any(np.longdouble is kind for kind in (np.float16, np.float32, np.float64)):
        pytest.skip("This platform exposes longdouble as an allowed actual alias")
    with pytest.raises(TypeError):
        Delta(hours=np.longdouble("0.5"))


def test_source_booleans_keep_dateutil_meaning_without_public_boolean_admission():
    source = relativedelta(days=True, month=True, hour=False)
    assert Delta.from_relativedelta(source) == Delta(days=1, month=1, hour=0)


def test_source_calendar_float_is_rejected_even_when_dateutil_field_is_mutated():
    source = relativedelta()
    source.years = 1.0
    with pytest.raises(TypeError):
        Delta.from_relativedelta(source)


@pytest.mark.parametrize("kind", [np.float16, np.float32, np.float64])
def test_source_fraction_uses_the_same_fixed_duration_normalization(kind):
    source = relativedelta()
    source.hours = kind(1.5)
    imported = Delta.from_relativedelta(source)
    assert imported == Delta(minutes=90)
    assert Delta() + source == imported
    assert source + Delta() == imported
    assert Delta() - source == Delta(minutes=-90)
    assert source - Delta() == imported


def test_float_subclass_keeps_the_real_stored_numeric_value():
    class Stored(np.float32):
        def __float__(self):
            raise AssertionError("the scalar's stored value should be read")

    assert Delta(hours=Stored(1.5)) == Delta(minutes=90)


@pytest.mark.parametrize("arguments", [
    lambda: Delta(True, 2),
    lambda: Delta(years=1, days=True),
    lambda: Delta(years=1, days=2, hours=True),
    lambda: Delta(years=1, days=2, hours=3, minutes=np.bool_(True)),
])
def test_primitive_constructor_shortcuts_do_not_bypass_boolean_rejection(arguments):
    with pytest.raises(TypeError):
        arguments()


@pytest.mark.parametrize("kind", [np.float16, np.float32, np.float64])
def test_non_decimal_float_storage_is_preserved_through_import_and_bulk(kind):
    value = kind(1.1)
    expected = timedelta(microseconds=round(Fraction(float(value)) * 3600000000))
    actual = datetime(2024, 5, 7) + Delta(hours=value)
    assert actual == datetime(2024, 5, 7) + expected
    source = relativedelta()
    source.hours = value
    assert Delta().apply_many([source]) == [Delta(hours=value)]


@pytest.mark.parametrize("operation,entry", [
    (lambda: datetime(1, 1, 1).date() - Delta(days=1), "Delta.__rsub__"),
    (lambda: datetime(9999, 12, 31).date() + Delta(days=1), "Delta.__radd__"),
    (lambda: Delta(days=1) + datetime(9999, 12, 31).date(), "Delta.__add__"),
])
def test_date_failure_names_the_actual_arithmetic_direction(operation, entry):
    with pytest.raises(ValueError) as caught:
        operation()
    detail = str(caught.value) + " " + " ".join(getattr(caught.value, "__notes__", ()))
    assert entry in detail
