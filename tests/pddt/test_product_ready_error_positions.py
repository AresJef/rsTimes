"""PR-033: only the active trustworthy position survives public reannotation."""
from concurrent.futures import CancelledError
from datetime import datetime, timedelta, tzinfo

import pytest
from rstimes import Pddt, errors

ENTRIES = ("year","is_dst","utcoffset_seconds","timedf","isoformat",
           "normalize","round","fsp","snap")


class Zone(tzinfo):
    def __init__(self, failure=None):
        self.failure = failure
        self.armed = False
        self.events = []
        self.bad_dst = False

    def utcoffset(self, value):return timedelta(0)
    def dst(self, value):
        if self.bad_dst and value is not None and value.day == 2:return 2
        return timedelta(0)
    def fromutc(self, value):
        self.events.append(value.day)
        if self.armed and value.day == 2:raise self.failure
        return value
    def tzname(self, value):return "BUSINESS"


def value_for(zone):
    result = Pddt([datetime(2024,1,day,tzinfo=zone) for day in (1,2)],unit="us")
    zone.events.clear()
    return result


def invoke(value, entry):
    if entry == "year":return value.year
    if entry in ("round","snap"):return getattr(value,entry)("h")
    if entry == "fsp":return value.fsp(3)
    return getattr(value,entry)()


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("historical", (False,True))
def test_actual_second_row_failure_retains_original_and_trustworthy_current_position(entry,historical):
    error = RuntimeError("real second-row timezone failure")
    cause = LookupError("original provider cause")
    error.__cause__ = cause
    error.add_note("user history")
    old = None
    if historical:
        errors._location_error(error,"old_call","data[7]")
        old = error.__notes__[-1]
    zone = Zone(error)
    value = value_for(zone)
    zone.armed = True
    with pytest.raises(RuntimeError) as failure:invoke(value,entry)
    assert failure.value is error and error.args == ("real second-row timezone failure",)
    assert error.__cause__ is cause and error.__notes__[0] == "user history"
    current = error.__notes__[-1]
    assert current.active and current.field == "result[1]"
    assert current.position == ("result",1)
    assert f"Pddt.{entry}" in current
    expected_events = [1,1,1,1,2] if entry in ("normalize","snap") else [1,2]
    assert "freq=" not in current and zone.events == expected_events
    if old is not None:
        assert error.__notes__[1] is old and not old.active and "data[7]" in old
        assert current is not old


@pytest.mark.parametrize("entry", ENTRIES)
def test_normal_public_timezone_paths_keep_values_and_callback_sequence(entry):
    zone = Zone()
    value = value_for(zone)
    actual = invoke(value,entry)
    if entry == "year":assert actual.tolist() == [2024,2024]
    elif entry == "is_dst":assert actual.tolist() == [False,False]
    elif entry == "utcoffset_seconds":assert actual.tolist() == [0,0]
    elif entry == "timedf":assert actual["tm_mday"].tolist() == [1,2]
    elif entry == "isoformat":assert actual.tolist() == ["2024-01-01T00:00:00+00:00","2024-01-02T00:00:00+00:00"]
    else:assert actual.asi8.tolist() == [1704067200000000,1704153600000000] and actual.unit == "us"
    expected_events = [1,1,1,1,2,2,2,2] if entry in ("normalize","snap") else [1,2]
    assert zone.events == expected_events


@pytest.mark.parametrize("entry", ("is_dst","timedf"))
def test_actual_invalid_dst_return_names_the_active_row(entry):
    zone = Zone()
    value = value_for(zone)
    zone.bad_dst = True
    with pytest.raises(TypeError) as failure:invoke(value,entry)
    assert "result[1]" in str(failure.value) and "dst()" in str(failure.value)
    assert f"Pddt.{entry}" in str(failure.value)


@pytest.mark.parametrize("kind", (MemoryError,CancelledError,KeyboardInterrupt))
@pytest.mark.parametrize("entry", ("year","round"))
def test_serious_callback_error_gets_no_explanatory_state(kind,entry):
    error = kind("stop")
    zone = Zone(error)
    value = value_for(zone)
    zone.armed = True
    with pytest.raises(kind) as failure:invoke(value,entry)
    assert failure.value is error and not hasattr(error,"__notes__")


def test_real_note_failure_remains_the_secondary_exception():
    error = RuntimeError("original")
    error.__notes__ = 1
    zone = Zone(error)
    value = value_for(zone)
    zone.armed = True
    with pytest.raises(TypeError,match="__notes__"):invoke(value,"year")


def test_plain_inner_role_is_remapped_and_text_alone_does_not_prove_a_row():
    error = RuntimeError("role")
    errors._external_error(error)
    errors._location_error(error,"inner","dtobj")
    errors._argument_error(error,"public","dt64",object())
    assert error.__notes__[-1].field == "dt64"
    misleading = RuntimeError("not an indexed call")
    errors._location_error(misleading,"inner","result[1]")
    errors._argument_error(misleading,"public","freq","h")
    assert misleading.__notes__[-1].field == "freq"
