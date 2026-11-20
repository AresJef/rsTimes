"""PR-038: stored name text and callback-after native-source protection."""
from datetime import date, time
import numpy as np
import polars as pl
import pytest
from rstimes import Pldt

EVENTS = []

class FalseText(str):
    def __bool__(self):
        EVENTS.append("bool")
        return False
    def __str__(self):
        EVENTS.append("str")
        return "wrong displayed name"

class ErrorText(str):
    def __bool__(self):
        raise AssertionError("name truth hook must not choose stored text")
    def __str__(self):
        raise AssertionError("name display hook must not choose stored text")

class EqualText(str):
    def __eq__(self, other):
        EVENTS.append("eq")
        return True
    def __ne__(self, other):
        EVENTS.append("ne")
        return False
    __hash__ = str.__hash__


def named_input(entry, name, length):
    numbers = list(range(length))
    texts = ["2024-01-01", "2024-01-02"][:length]
    if entry == "construct_list":
        result, expected = Pldt(numbers, unit="us", name=name), numbers
    elif entry == "construct_datetime_ndarray":
        result, expected = Pldt(np.array(numbers, dtype="datetime64[us]"), unit="us", name=name), numbers
    elif entry == "fromdatetime64_array":
        result, expected = Pldt.fromdatetime64(np.array(numbers, dtype="datetime64[us]"), unit="us", name=name), numbers
    elif entry == "construct_ndarray":
        result, expected = Pldt(np.array(numbers, dtype=np.int64), unit="us", name=name), numbers
    elif entry == "seconds_list":
        result, expected = Pldt.fromseconds(numbers, unit="us", name=name), [x*1000000 for x in numbers]
    elif entry == "seconds_series":
        result, expected = Pldt.fromseconds(pl.Series("source", numbers, dtype=pl.Int64), unit="us", name=name), [x*1000000 for x in numbers]
    elif entry == "microseconds_list":
        result, expected = Pldt.frommicroseconds(numbers, unit="us", name=name), numbers
    elif entry == "iso_list":
        result, expected = Pldt.fromisoformat(texts, unit="us", name=name), [1704067200000000, 1704153600000000][:length]
    elif entry == "strptime_list":
        result, expected = Pldt.strptime(texts, "%Y-%m-%d", unit="us", name=name), [1704067200000000, 1704153600000000][:length]
    elif entry == "strptime_series":
        result, expected = Pldt.strptime(pl.Series("source", texts, dtype=pl.String), "%Y-%m-%d", unit="us", name=name), [1704067200000000, 1704153600000000][:length]
    elif entry == "now":
        result, expected = Pldt.now(length, tz="UTC", unit="us", name=name), None
    elif entry == "fromdate_list":
        result, expected = Pldt.fromdate([date(2024,1,1)]*length, unit="us", name=name), [1704067200000000]*length
    elif entry == "combine":
        result, expected = Pldt.combine(date(2024,1,1), time(1), size=length, unit="us", name=name), [1704070800000000]*length
    elif entry == "date_range":
        result, expected = Pldt.date_range("2024-01-01", periods=length, freq="D", unit="us", name=name), [1704067200000000,1704153600000000][:length]
    else:
        assert entry == "calendar"
        result, expected = Pldt.fromordinal([719163+x for x in numbers], unit="us", name=name), [86400000000*x for x in numbers]
    assert type(result) is Pldt and result.dtype.time_unit == "us" and len(result) == length
    if expected is not None:
        assert result.to_physical().to_list() == expected
    return result


ENTRIES = ("construct_list", "construct_datetime_ndarray", "fromdatetime64_array", "construct_ndarray",
           "seconds_list", "seconds_series", "microseconds_list", "iso_list", "strptime_list",
           "strptime_series", "now", "fromdate_list", "combine", "date_range", "calendar")


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("length", (0, 2))
@pytest.mark.parametrize("name_type", (str, np.str_, FalseText, ErrorText, EqualText))
@pytest.mark.parametrize("text", ("clock", ""))
def test_each_name_entry_consumes_stored_text_before_truth_or_comparison(entry, length, name_type, text):
    name = name_type(text)
    EVENTS.clear()
    result = named_input(entry, name, length)
    assert result.name == text and type(result.name) is str
    assert not EVENTS


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("length", (0, 2))
def test_omitted_name_keeps_existing_source_fallback(entry, length):
    result = named_input(entry, None, length)
    assert result.name == ("source" if entry in ("seconds_series", "strptime_series") else "")


@pytest.mark.parametrize("deep", (False, True))
@pytest.mark.parametrize("text", ("old", "new"))
@pytest.mark.parametrize("name_type", (str, np.str_, FalseText, EqualText))
def test_real_self_copy_uses_prepared_name_and_never_renames_source(deep, text, name_type):
    calls = []
    class Business(Pldt):
        def __copy__(self):
            calls.append("copy")
            return self
        def __deepcopy__(self, memo):
            calls.append("deepcopy")
            return self
    source = Business([-(2**63), None], unit="ns", name="old")
    EVENTS.clear()
    if text == "new":
        with pytest.raises(ValueError):
            source.copy(name=name_type(text), deep=deep)
    else:
        assert source.copy(name=name_type(text), deep=deep) is source
    assert source.name == "old" and source.to_physical().to_list() == [-(2**63), None]
    assert calls == ["deepcopy" if deep else "copy"] and not EVENTS


@pytest.mark.parametrize("deep", (False, True))
@pytest.mark.parametrize("requested", ("after", "old"))
def test_self_copy_guard_reads_native_source_name_after_real_callback(deep, requested):
    calls = []
    class Replacing(Pldt):
        def selected(self):
            calls.append("copy")
            result = pl.Series(self).rename("after")
            object.__setattr__(self, "_s", result._s)
            return self
        def __copy__(self):
            return self.selected()
        def __deepcopy__(self, memo):
            return self.selected()
    source = Replacing([1, None], unit="ns", name="old")
    if requested == "old":
        with pytest.raises(ValueError):
            source.copy(name=FalseText(requested), deep=deep)
    else:
        assert source.copy(name=FalseText(requested), deep=deep) is source
    assert source.name == "after" and source.to_physical().to_list() == [1, None]
    assert calls == ["copy"]


@pytest.mark.parametrize("name", (0, 1.5, b"clock", object()))
@pytest.mark.parametrize("length", (0, 2))
def test_non_text_names_are_rejected_even_for_empty_input(name, length):
    with pytest.raises(TypeError):
        Pldt(list(range(length)), unit="us", name=name)


@pytest.mark.parametrize("deep", (False, True))
@pytest.mark.parametrize("broken", (False, True))
@pytest.mark.parametrize("name_type", (str, np.str_, FalseText, EqualText))
def test_external_copy_result_receives_exact_name_once_and_keeps_original_error(deep, broken, name_type):
    calls = []
    marker = LookupError("business name setter")
    class Result:
        @property
        def name(self):
            return "clock"
        @name.setter
        def name(self, value):
            assert type(value) is str and value == "clock"
            calls.append("name")
            if broken:
                raise marker
    returned = Result()
    class Business(Pldt):
        def __copy__(self):
            calls.append("copy")
            return returned
        def __deepcopy__(self, memo):
            calls.append("deepcopy")
            return returned
    source = Business([7, None], unit="ns", name="source")
    EVENTS.clear()
    if broken:
        with pytest.raises(LookupError) as observed:
            source.copy(name=name_type("clock"), deep=deep)
        assert observed.value is marker
    else:
        assert source.copy(name=name_type("clock"), deep=deep) is returned
    assert calls == ["deepcopy" if deep else "copy", "name"] and not EVENTS
    assert source.name == "source" and source.to_physical().to_list() == [7, None]
