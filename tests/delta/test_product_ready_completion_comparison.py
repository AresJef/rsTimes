"""PR-009/011: fixed completion convention and only relevant value methods."""
from datetime import date, datetime, timezone

import pytest
from rstimes import Delta, Pydt


@pytest.mark.parametrize("name", ("business", "\ud800", "tail\udfff", "\U0010ffff"))
@pytest.mark.parametrize("role", ("hash_none", "only_ne", "rebound"))
@pytest.mark.parametrize("inherited", (False, True))
@pytest.mark.parametrize("same", (False, True))
def test_unrelated_namespace_name_cannot_change_field_equality(name, role, inherited, same):
    namespace = {"__hash__": None}
    if role == "only_ne":
        namespace["__ne__"] = lambda self, other: "business inequality"
    elif role == "rebound":
        namespace.update(__eq__=Delta.__eq__, __ne__=Delta.__ne__)
    parent = type("Parent", (Delta,), namespace)
    cls = type("Child", (parent,), {}) if inherited else parent
    setattr(cls, name, object())
    left = Delta(days=1, nanoseconds=3)
    right = cls(days=1, nanoseconds=3 if same else 4)
    assert (left == right) is same and (right == left) is same
    assert Delta.__eq__(left, right) is same and Delta.__eq__(right, left) is same
    if role == "only_ne":
        assert (right != left) == "business inequality"
        assert Delta.__ne__(left, right) is NotImplemented
    else:
        assert (left != right) is (not same)
    with pytest.raises(TypeError):
        hash(right)
    assert type(hash(left)) is int


def test_live_special_method_changes_are_observed_without_cached_qualification():
    class Child(Delta):
        pass
    base, child = Delta(days=1), Child(days=1)
    assert Delta.__eq__(base, child) is True
    Child.__hash__ = lambda self: 17
    assert Delta.__eq__(base, child) is NotImplemented and hash(child) == 17
    Child.__hash__ = None
    assert Delta.__eq__(base, child) is True
    answer = object()
    Child.__eq__ = lambda self, other: answer
    assert Delta.__eq__(base, child) is NotImplemented
    assert (base == child) is answer
    Child.__eq__ = Delta.__eq__
    assert Delta.__eq__(base, child) is True


def test_actual_mro_lookup_does_not_call_metaclass_display_hooks():
    events = []
    class Meta(type):
        def __getattribute__(cls, name):
            if armed and name in ("__dict__", "__mro__"):
                events.append(name)
                raise AssertionError("display metadata is not actual MRO storage")
            return super().__getattribute__(name)
    armed = False
    cls = Meta("Child", (Delta,), {"__hash__": None, "\ud800": 1})
    right = cls(days=1)
    armed = True
    assert Delta.__eq__(Delta(days=1), right) is True
    assert events == []


@pytest.mark.parametrize("operation", ("add", "radd", "sub", "bulk"))
def test_datetime_subclass_constructed_once_with_fields_timezone_and_fold(operation):
    calls = []
    class Business(datetime):
        def __new__(cls, *args, **kwargs):
            if armed:
                calls.append((args, kwargs))
            return super().__new__(cls, *args, **kwargs)
    armed = False
    source = Business(2024, 1, 31, 12, 34, 56, 123456, tzinfo=timezone.utc, fold=1)
    armed = True
    change = Delta(months=1)
    result = source + change if operation == "add" else change + source if operation == "radd" else source - change if operation == "sub" else change.apply_many([source])[0]
    expected = datetime(2023, 12, 31, 12, 34, 56, 123456, tzinfo=timezone.utc, fold=1) if operation == "sub" else datetime(2024, 2, 29, 12, 34, 56, 123456, tzinfo=timezone.utc, fold=1)
    assert type(result) is Business and result == expected
    assert result.tzinfo is timezone.utc and result.fold == 1 and len(calls) == 1


@pytest.mark.parametrize("change", (Delta(), Delta(day=31), Delta(nanoseconds=1), Delta(nanoseconds=500)))
def test_unchanged_datetime_has_no_constructor_even_for_nonempty_delta(change):
    calls = []
    class Business(datetime):
        def __new__(cls, *args, **kwargs):
            if armed:
                calls.append(1)
            return super().__new__(cls, *args, **kwargs)
    armed = False
    source = Business(2024, 1, 31, microsecond=123456, fold=1)
    armed = True
    assert source + change is source and change.apply_many([source])[0] is source
    assert calls == []


@pytest.mark.parametrize("days", (-1, 1))
def test_date_only_constructor_convention_is_still_supported(days):
    class Business(date):
        pass
    source = Business(2024, 2, 28)
    result = source + Delta(days=days)
    assert type(result) is Business and result == date(2024, 2, 27 if days < 0 else 29)


def test_datetime_constructor_failure_is_original_and_never_retried():
    original = LookupError("actual date constructor failed")
    calls = []
    class Business(datetime):
        def __new__(cls, *args, **kwargs):
            if armed:
                calls.append(1)
                raise original
            return super().__new__(cls, *args, **kwargs)
    armed = False
    source = Business(2024, 1, 1)
    armed = True
    with pytest.raises(LookupError) as caught:
        source + Delta(days=1)
    assert caught.value is original and calls == [1]


def test_pydt_and_timestamp_keep_their_own_final_precision_and_capacity():
    source = Pydt(2024, 1, 31, microsecond=123456, fold=1, tzinfo=timezone.utc)
    result = source + Delta(months=1)
    assert type(result) is Pydt and (result.year, result.month, result.day, result.microsecond) == (2024, 2, 29, 123456)
    assert result.tzinfo is timezone.utc and result.fold == source.fold


def test_timestamp_retains_native_nanoseconds_through_its_public_replacement():
    pd = pytest.importorskip("pandas")
    timestamp = pd.Timestamp("2024-01-31T12:34:56.123456789", tz="UTC")
    result = timestamp + Delta(months=1)
    assert type(result) is pd.Timestamp and result == pd.Timestamp("2024-02-29T12:34:56.123456789", tz="UTC")
    assert result.nanosecond == 789
