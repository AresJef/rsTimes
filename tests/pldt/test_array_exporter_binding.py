"""RV02: real once-bound exporters determine NumPy post-cast protection."""
import numpy as np
import polars as pl
import pytest

from rstimes import Pldt


class ForwardingLookup(Pldt):
    def __getattribute__(self, name):
        return super().__getattribute__(name)


class DisplayMeta(type(Pldt)):
    def __getattribute__(cls, name):
        if name == "__getattribute__":
            return lambda self, key: object.__getattribute__(self, key)
        return super().__getattribute__(name)


class DisplayLookup(Pldt, metaclass=DisplayMeta):
    pass


@pytest.mark.parametrize("cls", [Pldt, ForwardingLookup, DisplayLookup])
@pytest.mark.parametrize("values,unit,dtype", [
    ([1], "ns", "datetime64[us]"),
    ([1], "ns", "datetime64[ms]"),
    ([0, None], "us", "int64"),
    ([0, None], "us", "float64"),
    ([(1 << 63) - 1], "ns", "float64"),
])
def test_library_exporter_retains_value_and_validity_guard_with_neutral_lookup(cls, values, unit, dtype):
    x = cls(values, unit=unit)
    with pytest.raises(ValueError):
        np.asarray(x, dtype=dtype)
    assert x.to_physical().to_list() == values


@pytest.mark.parametrize("cls", [Pldt, ForwardingLookup, DisplayLookup])
def test_lossless_copy_and_nat_controls_are_preserved(cls):
    x = cls([1000, None], unit="ns")
    out = np.asarray(x, dtype="datetime64[us]")
    assert out.view("i8").tolist() == [1, -(1 << 63)]
    no_null = cls([1000], unit="ns")
    same = no_null.__array__(np.dtype("datetime64[ns]"), copy=False)
    assert same.dtype == np.dtype("datetime64[ns]")
    with pytest.raises(RuntimeError, match="copy"):
        x.__array__(np.dtype("datetime64[us]"), copy=False)
    with pytest.raises(OverflowError):
        np.asarray(cls([-(1 << 63)], unit="ns"))
    with pytest.raises((OverflowError, ValueError)):
        np.asarray(cls(["2500-01-01"], unit="us"), dtype="datetime64[ns]")
    writable = cls([1], unit="us").__array__(copy=True)
    assert writable.flags.writeable


def test_descriptor_returning_library_method_is_bound_once_and_still_protected():
    lookups = []
    class Export:
        def __get__(self, value, owner):
            lookups.append(value)
            return Pldt.to_numpy.__get__(value, owner)
    class Wrapped(Pldt):
        to_numpy = Export()
    x = Wrapped([1], unit="ns")
    with pytest.raises(ValueError):
        np.asarray(x, dtype="datetime64[us]")
    assert lookups == [x]


def test_base_export_uses_one_actual_source_for_export_and_conversion_checks():
    reads = []
    class SourceLookup(Pldt):
        def __getattribute__(self, name):
            if name == "_s":
                reads.append(name)
            return super().__getattribute__(name)
    x = SourceLookup([1000, None], unit="ns")
    for export in (lambda: x.to_numpy(), lambda: np.asarray(x, dtype="datetime64[us]")):
        reads.clear()
        result = export()
        assert result.view("i8").tolist() == ([1000, -(1 << 63)] if result.dtype == np.dtype("datetime64[ns]") else [1, -(1 << 63)])
        assert reads == ["_s"]


def test_live_public_base_export_override_keeps_its_business_result(monkeypatch):
    calls = []
    def export(self, **kwargs):
        calls.append(kwargs)
        return np.array([7, 8])
    x = Pldt([0, 1], unit="ns")
    monkeypatch.setattr(Pldt, "to_numpy", export)
    assert np.asarray(x, dtype=float).tolist() == [7., 8.]
    assert calls == [{"writable": False, "allow_copy": True}]


@pytest.mark.parametrize("binding", ["method", "descriptor", "static", "class"])
def test_genuine_exporter_choices_and_single_call_are_preserved(binding):
    calls, lookups = [], []
    def export(**kwargs):
        calls.append(kwargs)
        return np.array([7, 8])
    if binding == "method":
        class Business(Pldt):
            def to_numpy(self, **kwargs):
                return export(**kwargs)
    elif binding == "descriptor":
        class Export:
            def __get__(self, value, owner):
                lookups.append(value)
                return export
        class Business(Pldt):
            to_numpy = Export()
    elif binding == "static":
        class Business(Pldt):
            to_numpy = staticmethod(export)
    else:
        class Business(Pldt):
            @classmethod
            def to_numpy(cls, **kwargs):
                return export(**kwargs)
    x = Business([0, 1], unit="us")
    assert np.asarray(x, dtype=float).tolist() == [7., 8.]
    assert calls == [{"writable": False, "allow_copy": True}]
    assert len(lookups) == (1 if binding == "descriptor" else 0)


def test_real_exporter_exception_keeps_identity_and_does_not_repeat_lookup():
    original = LookupError("actual exporter")
    calls = []
    class Export:
        def __get__(self, value, owner):
            calls.append("bind")
            def execute(**kwargs):
                calls.append("call")
                raise original
            return execute
    class Business(Pldt):
        to_numpy = Export()
    with pytest.raises(LookupError) as caught:
        np.asarray(Business([0]), dtype=float)
    assert caught.value is original
    assert calls == ["bind", "call"]
