"""A1/A2/B1/C4: mode, actual layouts, once-read targets and final construction."""
import sys
import numpy as np
import pytest

pytest.importorskip("pandas")
pl = pytest.importorskip("polars")
from rstimes import Configs, Pddt, Pldt


@pytest.mark.parametrize("fmt", (None, 1))
def test_expr_strptime_invalid_format_is_not_parse(fmt) -> None:
    with pytest.raises(TypeError, match="fmt"):
        expr = pl.col("text").pldt.strptime(fmt, unit="us")
        pl.DataFrame({"text": ["2024-01-01"]}).lazy().select(expr).collect()


def test_expr_parse_and_formatted_parse_keep_distinct_valid_modes() -> None:
    frame = pl.DataFrame({"text": ["1970-01-01", None]})
    for expr in (pl.col("text").pldt.parse(unit="us"), pl.col("text").pldt.strptime("%Y-%m-%d", unit="us")):
        assert frame.lazy().select(expr).collect()["text"].to_physical().to_list() == [0, None]


class DisplayConfigs:
    @property
    def __class__(self):
        return Configs


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("size", (0, 1))
def test_actual_config_type_is_checked_even_on_native_fast_input(base, size: int) -> None:
    source = np.arange(size, dtype="int64").view("datetime64[us]")
    with pytest.raises(TypeError, match="cfg"):
        base(source, cfg=DisplayConfigs())


class DisplayArray:
    @property
    def __class__(self):
        return np.ndarray

    def __array__(self, *args, **kwargs):
        raise AssertionError("an ordinary iterable must not enter the native array path")

    def __iter__(self):
        return iter([0, 2])


def test_display_array_identity_does_not_override_actual_iterable_role() -> None:
    assert Pldt(DisplayArray(), unit="ns").to_physical().to_list() == [0, 2]


def test_real_array_subclass_keeps_strides_and_byteorder_support() -> None:
    class Array(np.ndarray):
        pass
    source = np.arange(6, dtype=">i8")[::2].view(Array)
    assert Pldt(source, unit="ns").to_physical().to_list() == [0, 2, 4]
    assert source.tolist() == [0, 2, 4]


def test_diff_target_name_is_read_once() -> None:
    calls = []
    original = LookupError("second target read")

    class Target(pl.Series):
        @property
        def name(self):
            calls.append("name")
            if len(calls) > 1:
                raise original
            return "target"

    target = Target("target", [0, 1], dtype=pl.Int64)
    calls.clear()
    value = Pddt([86400, 86400], unit="s").diff(target, "s")
    assert value.tolist() == [86400, 86399] and calls == ["name"]


def test_diff_first_actual_getter_error_is_preserved() -> None:
    original = LookupError("first target read")

    class Target(pl.Series):
        @property
        def name(self):
            raise original

    with pytest.raises(LookupError) as caught:
        Pddt([86400], unit="s").diff(Target("target", [0], dtype=pl.Int64), "s")
    assert caught.value is original


@pytest.mark.parametrize("kind", ("list", "string", "object"))
def test_exact_strptime_builds_final_class_without_generic_initialization(kind: str) -> None:
    text = "1970-01-01T00:00:00.123456789"
    source = [text, None] if kind == "list" else pl.Series("source", [text, None], dtype=pl.String if kind == "string" else pl.Object)
    calls = []
    previous = sys.getprofile()
    code = Pldt.__init__.__code__

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is code:
            calls.append("init")

    try:
        sys.setprofile(observe)
        value = Pldt.strptime(source, "%Y-%m-%dT%H:%M:%S.%f", unit="ns", name="time", tz="UTC")
    finally:
        sys.setprofile(previous)
    assert type(value) is Pldt and value.name == "time"
    assert value.dtype == pl.Datetime("ns", "UTC")
    assert value.to_physical().to_list() == [123456789, None]
    assert calls == []


def test_strptime_business_constructor_and_error_are_not_bypassed() -> None:
    calls = []

    class Business(Pldt):
        def __new__(cls, data, **kwargs):
            calls.append("new")
            return super().__new__(cls)

        def __init__(self, data, **kwargs):
            calls.append("init")
            super().__init__(data, **kwargs)

    value = Business.strptime(["1970-01-01"], "%Y-%m-%d")
    assert type(value) is Business and calls == ["new", "init"]
    original = LookupError("business constructor")

    class Broken(Pldt):
        def __init__(self, *args, **kwargs):
            raise original

    with pytest.raises(LookupError) as caught:
        Broken.strptime(["1970-01-01"], "%Y-%m-%d")
    assert caught.value is original


@pytest.mark.parametrize("kind", ("list", "string", "object", "null"))
@pytest.mark.parametrize("name", (None, "target"))
def test_strptime_exports_exact_final_wrapper_once(kind: str, name) -> None:
    text = "1970-01-01T00:00:00.123456789"
    source = [text, None] if kind == "list" else pl.Series(
        "source", [None, None] if kind == "null" else [text, None],
        dtype={"string": pl.String, "object": pl.Object, "null": pl.Null}[kind])
    calls = []
    previous = sys.getprofile()
    code = Pldt._from_pyseries.__func__.__code__

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is code and frame.f_locals.get("cls") is Pldt:
            calls.append("final Pldt")

    try:
        sys.setprofile(observe)
        result = Pldt.strptime(source, "%Y-%m-%dT%H:%M:%S.%f", unit="ns", name=name, tz="UTC")
    finally:
        sys.setprofile(previous)
    assert type(result) is Pldt and result.dtype == pl.Datetime("ns", "UTC")
    assert result.name == (name if name is not None else "" if kind == "list" else "source")
    assert result.to_physical().to_list() == ([None, None] if kind == "null" else [123456789, None])
    assert calls == ["final Pldt"]
