"""Independent duration expectations and the approved raw-field import rules."""

from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
import random
from zoneinfo import ZoneInfo

from dateutil.relativedelta import MO, relativedelta
import pytest

from rstimes import Delta, Pydt


DATA = json.loads((Path(__file__).parent / "data/relativedelta-normalization-20261022.json").read_text(encoding='utf-8'))
FIXED = ("weeks", "days", "hours", "minutes", "seconds", "milliseconds", "microseconds")
FACTORS = (604800000000, 86400000000, 3600000000, 60000000, 1000000, 1000, 1)
RELATIVE = ("years", "months", "days", "hours", "minutes", "seconds", "microseconds")
STARTS = (datetime(2024, 1, 31, 13, 14, 15, 123456), datetime(2023, 2, 28),
          datetime(2024, 2, 29), datetime(2024, 3, 31), datetime(2025, 12, 31), datetime(2000, 2, 29))


def micros(value):
    """Read a fixed duration using integer arithmetic, without total_seconds()."""
    if isinstance(value, timedelta):
        return (value.days * 86400 + value.seconds) * 1000000 + value.microseconds
    return (((value.days * 24 + value.hours) * 60 + value.minutes) * 60 + value.seconds) * 1000000 + value.microseconds


@pytest.mark.parametrize("options", DATA["fractional_inputs"])
def test_delta_fractional_duration_matches_independent_standard(options):
    expected = micros(timedelta(**options))
    assert micros(Delta(**options)) == expected
    assert micros(Delta(**dict(reversed(options.items())))) == expected
    positional = (0, 0, 0, 0, *(options[k] for k in ("days", "hours", "minutes", "seconds")), 0, options["microseconds"])
    assert micros(Delta(*positional)) == expected


@pytest.mark.parametrize("options", DATA["fractional_inputs"])
def test_import_fractional_duration_uses_actual_source_fields(options):
    source = relativedelta(**options)
    fixed = {name: getattr(source, name) for name in RELATIVE[2:]}
    expected = micros(timedelta(**fixed))
    assert micros(Delta.from_relativedelta(source)) == expected


def test_all_seven_units_share_the_standard_small_tail_order():
    rng = random.Random(20261022)
    choices = (-1.5, -1.1, -0.3, -0.5, -1e-7, 0.0, 1e-7, 0.1, 0.5, 1.1, 1.5, 1 / 3)
    for _ in range(700):
        options = {unit: rng.choice(choices) for unit in FIXED}
        expected = micros(timedelta(**options))
        assert micros(Delta(**options)) == expected
        assert micros(Delta(**dict(reversed(options.items())))) == expected


def test_fractional_cancellation_on_both_sides_of_rounding_boundaries():
    # Choose inputs near half a microsecond after large fractional units cancel.
    # Expected answers still come only from the independent standard timedelta.
    for sign in (-1, 1):
        for week in (0.1, 0.3, 0.99999999999999):
            options = dict(weeks=sign * week, days=-sign * 0.3,
                           hours=sign * 1.1, minutes=-sign * 0.2,
                           seconds=sign * 0.3, milliseconds=-sign * 0.1)
            scaled = sum((value - math.trunc(value)) * factor
                         for (unit, factor) in zip(FIXED, FACTORS)
                         if (value := options.get(unit, 0)))
            for distance in (-1 / 512, -1 / 1024, -1 / 2048, 0, 1 / 2048, 1 / 1024, 1 / 512):
                options["microseconds"] = 0.5 - (scaled - math.floor(scaled)) + distance
                assert micros(Delta(**options)) == micros(timedelta(**options))


@pytest.mark.parametrize("integer", [2**53 + 1, -(2**53 + 1), 2**63 - 1, -(2**63)])
@pytest.mark.parametrize("seconds", [-0.0000005, 0.0000005])
def test_large_microsecond_integer_and_fraction_use_full_parity(integer, seconds):
    expected = micros(timedelta(microseconds=integer, seconds=seconds))
    assert micros(Delta(microseconds=integer, seconds=seconds)) == expected


def test_source_import_does_not_add_storage_or_change_immutable_values():
    value = Delta(days=1)
    before = hash(value)
    source = relativedelta(days=1.5)
    assert Delta.__basicsize__ == 64
    assert value + source == Delta(days=2, hours=12)
    assert value.days == 1 and hash(value) == before


@pytest.mark.parametrize("field,factor", zip(FIXED, FACTORS))
@pytest.mark.parametrize("number", [-1.5, -0.5, -0.0, 0.5, 1.5, 2.5])
def test_each_fixed_float_unit_and_mixed_absolute_constructor(field, factor, number):
    options = {field: number}
    expected = micros(timedelta(**options))
    assert micros(Delta(**options)) == expected
    mixed = Delta(month=2, **options)
    assert mixed.month == 2 and micros(mixed) == expected


@pytest.mark.parametrize("field,factor", zip(FIXED, FACTORS))
@pytest.mark.parametrize("number", [2**53 + 1, -(2**53 + 1)])
def test_large_integer_units_remain_exact(field, factor, number):
    expected = number * factor
    if not -(2**63) <= expected // 86400000000 < 2**63:
        with pytest.raises(OverflowError):
            Delta(**{field: number})
    else:
        assert micros(Delta(**{field: number})) == expected


@pytest.mark.parametrize("integer", [2**53, 2**53 + 1, 2**63 - 1, -(2**63)])
@pytest.mark.parametrize("fraction", [-0.5, 0.5])
def test_large_integer_plus_half_microsecond_keeps_integer_parity(integer, fraction):
    # A day is an even number of microseconds, so its exact integer contribution
    # does not change half-to-even parity in the small fractional component.
    value = Delta(days=integer, microseconds=fraction)
    assert micros(value) == integer * 86400000000


@pytest.mark.parametrize("options,accepted", zip(DATA["calendar_inputs"], DATA["calendar_accept"]))
def test_existing_calendar_inputs_keep_source_date_meaning(options, accepted):
    source = relativedelta(**options)
    if not accepted:
        with pytest.raises(ValueError):
            Delta.from_relativedelta(source)
        return
    converted = Delta.from_relativedelta(source)
    for start in STARTS:
        try:
            expected = start + source
        except (OverflowError, ValueError):
            with pytest.raises((OverflowError, ValueError)):
                start + converted
        else:
            assert start + converted == expected


@pytest.mark.parametrize("field,number", [
    ("years", 2), ("months", 3), ("days", 4), ("hours", 5),
    ("minutes", 6), ("seconds", 7), ("microseconds", 8),
    ("year", 2025), ("month", 6), ("day", 21), ("hour", 9),
    ("minute", 10), ("second", 11), ("microsecond", 12),
])
def test_each_supported_nonzero_source_field(field, number):
    converted = Delta.from_relativedelta(relativedelta(**{field: number}))
    assert getattr(converted, field) == number
    assert converted == Delta(**{field: number})


@pytest.mark.parametrize("direction", ["factory", "add", "radd", "sub", "rsub", "batch"])
def test_all_import_entries_read_raw_fields_and_never_call_normalized(direction):
    calls = []
    class Source(relativedelta):
        def normalized(self):
            calls.append(True)
            raise AssertionError("normalized() must not run")
    source = Source(days=1.5, hours=1.25)
    own = Delta(days=2, hour=9)
    converted = Delta(days=1.5, hours=1.25)
    operations = {
        "factory": (lambda: Delta.from_relativedelta(source), converted),
        "add": (lambda: own + source, own + converted),
        "radd": (lambda: source + own, converted + own),
        "sub": (lambda: own - source, own - converted),
        "rsub": (lambda: source - own, converted - own),
        "batch": (lambda: own.apply_many([source])[0], converted + own),
    }
    operation, expected = operations[direction]
    assert operation() == expected
    assert calls == []


@pytest.mark.parametrize("options", [{"weekday": MO(1)}, {"leapdays": 1}])
@pytest.mark.parametrize("direction", ["factory", "add", "radd", "sub", "rsub", "batch"])
def test_unsupported_source_rules_still_report_the_field(options, direction):
    source = relativedelta(**options)
    zero = Delta()
    operations = {"factory": lambda: Delta.from_relativedelta(source),
                  "add": lambda: zero + source, "radd": lambda: source + zero,
                  "sub": lambda: zero - source, "rsub": lambda: source - zero,
                  "batch": lambda: zero.apply_many([source])}
    with pytest.raises(ValueError, match=next(iter(options))):
        operations[direction]()


def test_real_source_field_callback_errors_are_not_swallowed():
    source = relativedelta(days=1)
    class Source(relativedelta):
        def __getattribute__(self, name):
            if name == "days":
                raise RuntimeError("actual days callback")
            return super().__getattribute__(name)
    source.__class__ = Source
    with pytest.raises(RuntimeError, match="actual days callback"):
        Delta.from_relativedelta(source)


@pytest.mark.parametrize("mutation", ["clear", "replace", "append"])
def test_batch_field_callback_preserves_current_item_and_live_iteration(mutation):
    source = relativedelta(days=1)
    tail = relativedelta(days=3)
    replacement = relativedelta(days=7)
    items = [source, tail]
    entered = False
    class Source(relativedelta):
        def __getattribute__(self, name):
            nonlocal entered
            if name == "days" and not entered:
                entered = True
                if mutation == "clear": items.clear()
                elif mutation == "replace": items[0] = replacement
                else: items.append(replacement)
            return super().__getattribute__(name)
    source.__class__ = Source
    expected = [Delta(days=1)]
    if mutation != "clear": expected.append(Delta(days=3))
    if mutation == "append": expected.append(Delta(days=7))
    assert Delta().apply_many(items) == expected


def test_import_does_not_change_delta_date_fold_and_subtraction_rules():
    source = relativedelta(month=13, months=-1)
    converted = Delta.from_relativedelta(source)
    assert converted == Delta(month=12)
    start = datetime(2024, 5, 17)
    assert start - converted == datetime(2024, 12, 17)
    assert start - source == datetime(2025, 2, 17)
    value = date(2024, 1, 1) + Delta.from_relativedelta(relativedelta(hours=1))
    assert type(value) is date and value == date(2024, 1, 1)
    repeated = datetime(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    assert (repeated + Delta.from_relativedelta(relativedelta())).fold == 1
    # Pydt's direct dateutil protocol keeps its wider calendar capabilities.
    assert Pydt(2024, 5, 7) + relativedelta(weekday=MO(2)) == datetime(2024, 5, 20)
