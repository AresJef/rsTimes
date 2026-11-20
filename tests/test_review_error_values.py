"""Library-owned name failures display one bounded value and a trusted role."""
from datetime import datetime, tzinfo

import numpy as np
import pytest

from rstimes import Delta, Pydt


class StoredText(str):
    def __str__(self):
        raise AssertionError("display conversion")

    def __repr__(self):
        raise AssertionError("display representation")


class PassiveText(str):
    pass


@pytest.fixture(params=("Pydt", "Pddt", "Pldt", "Pddt range", "Pldt range"))
def timezone_boundary(request):
    entry = request.param
    if entry == "Pydt":
        return "tzinfo", lambda zone: Pydt(2024, 1, 1, tzinfo=zone)
    pytest.importorskip("pandas" if entry.startswith("Pddt") else "polars")
    import rstimes

    cls = getattr(rstimes, entry.split()[0])
    if entry.endswith("range"):
        return "tz", lambda zone: cls.date_range("2024-01-01", periods=2, freq="D", tz=zone)
    return "tz", lambda zone: cls(["2024-01-01"], tz=zone)


@pytest.mark.parametrize("kind", (str, PassiveText, StoredText, np.str_))
def test_named_zone_errors_keep_library_context(timezone_boundary, kind):
    parameter, constructor = timezone_boundary
    with pytest.raises(ValueError, match=parameter + r"(?:=|:)") as observed:
        constructor(kind("Bad/Review-Zone"))
    assert "Bad/Review-Zone" in str(observed.value)
    assert isinstance(observed.value.__cause__, KeyError)
    assert not getattr(observed.value, "__notes__", [])
    with_zone = constructor(kind("Asia/Shanghai"))
    if isinstance(with_zone, datetime):
        assert str(with_zone.tzinfo) == "Asia/Shanghai"
    elif hasattr(with_zone, "tz"):
        assert str(with_zone.tz) == "Asia/Shanghai"
    else:
        assert with_zone.dtype.time_zone == "Asia/Shanghai"


def test_timezone_callback_preserves_original_exception():
    marker = LookupError("business timezone callback")
    marker.add_note("kept note")

    class BrokenZone(tzinfo):
        def utcoffset(self, _):
            raise marker

    with pytest.raises(LookupError) as observed:
        Pydt(2024, 1, 1, tzinfo=BrokenZone()).tz_convert("UTC")
    assert observed.value is marker
    assert "kept note" in observed.value.__notes__


@pytest.fixture(params=("Pydt", "Pddt"))
def selector(request):
    if request.param == "Pydt":
        return Pydt(2024, 1, 1)
    pytest.importorskip("pandas")
    from rstimes import Pddt

    return Pddt(["2024-01-01", "2024-02-02"])


@pytest.mark.parametrize("kind", (str, PassiveText, StoredText))
@pytest.mark.parametrize("method, field", (
    ("is_month", "month"), ("to_year", "month"),
    ("is_weekday", "weekday"), ("to_weekday", "weekday"),
))
def test_selector_text_is_shown_once(selector, kind, method, field):
    for text in ("actual_calendar_token", "actual_calendar_token" + "私" * 200 + "\n'"):
        value = kind(text)
        args = (0, value) if method.startswith("to_") else (value,)
        with pytest.raises(ValueError, match=rf"\b{field}:") as observed:
            getattr(selector, method)(*args)
        message = str(observed.value)
        assert message.count("actual_calendar_token") == 1
        if len(text) > 120:
            assert f"length {len(text)}" in message
    control = "Jan" if field == "month" else "Mon"
    value = kind(control)
    args = (0, value) if method.startswith("to_") else (value,)
    getattr(selector, method)(*args)


@pytest.mark.parametrize("method", ("is_month", "to_year"))
def test_pddt_column_position_and_iterator_identity(method):
    pytest.importorskip("pandas")
    from rstimes import Pddt

    dates = Pddt(["2024-01-01", "2024-01-02"], name="stamp")
    method = getattr(dates, method)
    args = (0,) if method.__name__ == "to_year" else ()
    with pytest.raises(ValueError, match=r"month\[1\]:") as observed:
        method(*args, ["jan", StoredText("actual_calendar_token")])
    assert str(observed.value).count("actual_calendar_token") == 1

    marker = LookupError("business sequence error")
    marker.add_note("original note")
    seen = []

    def values():
        seen.append(0)
        yield "jan"
        seen.append(1)
        raise marker

    with pytest.raises(LookupError) as original:
        method(*args, values())
    assert original.value is marker and seen == [0, 1]
    assert marker.__notes__[0] == "original note"
    assert sum("reading month[1]" in note for note in marker.__notes__) == 1


def assert_native_preview(message, prefix, name):
    assert prefix in message
    preview = message.split(prefix, 1)[1].splitlines()[0]
    assert len(preview) <= 120
    assert "text_token" in preview and "\\n" in preview
    assert f"length {len(name)}" in preview
    assert "private_end" not in message


@pytest.mark.parametrize("additional", ({}, {"days": 1}, {"days": 1, "hours": 2, "minutes": 3, "seconds": 4}))
def test_delta_unrecognized_keywords_have_bounded_escaped_previews(additional):
    value = "text_token\n'\0" + "私" * 199 + "private_end"
    with pytest.raises(TypeError) as observed:
        Delta(**{value: 1, **additional})
    assert_native_preview(str(observed.value), "unexpected keyword argument ", value)


@pytest.mark.parametrize("query", ("to_year", "to_weekday"))
def test_native_pldt_name_preview_for_eager_and_actual_expr(query):
    pl = pytest.importorskip("polars")
    from rstimes import Pldt

    value = "text_token\n'\0" + "私" * 199 + "private_end"
    name_kind = "month" if query == "to_year" else "weekday"
    prefix = f"unknown {name_kind} name "
    source = Pldt(["2024-01-01"], name="stamp", unit="ns")
    for owner in (source, pl.Series(source).pldt):
        with pytest.raises(ValueError) as observed:
            getattr(owner, query)(0, value)
        assert_native_preview(str(observed.value), prefix, value)
    frame = source.to_frame().with_columns(pl.lit(value).alias("key")).lazy()
    expr = getattr(pl.col("stamp").pldt, query)(0, pl.col("key"))
    with pytest.raises(pl.exceptions.ComputeError) as observed:
        frame.select(expr).collect()
    assert_native_preview(str(observed.value), prefix, value)
