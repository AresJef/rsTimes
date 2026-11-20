"""Named NumPy construction retains source precision and first-error order."""
import numpy as np
import pytest

from rstimes import Pddt

NAT = -(2**63)


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
@pytest.mark.parametrize("size", (0, 1, 3))
def test_nat_scalar_retains_declared_unit_through_broadcast(unit, size):
    result = Pddt.fromdatetime64(np.datetime64("NaT", "3" + unit), size=size)
    assert result.unit == unit
    assert result.asi8.tolist() == [NAT] * size
    assert result.isna().tolist() == [True] * size


@pytest.mark.parametrize("carrier", (list, tuple, iter, lambda items: np.array(items, dtype="O")))
@pytest.mark.parametrize("reverse", [False, True])
def test_object_nat_participates_in_implicit_unit_once(carrier, reverse):
    values = [np.datetime64(2, "s"), np.datetime64("NaT", "3ns")]
    expected = [2_000_000_000, NAT]
    if reverse:
        values.reverse()
        expected.reverse()
    result = Pddt.fromdatetime64(carrier(values), name="stamp", tz="UTC")
    assert result.unit == "ns" and result.name == "stamp"
    assert result.asi8.tolist() == expected
    assert result.isna().tolist() == [tick == NAT for tick in expected]


@pytest.mark.parametrize("carrier", ("scalar", "typed", "object"))
def test_actual_multiplier_value_decodes_once_and_keeps_explicit_precision(carrier):
    scalar = np.datetime64(2, "3ns")
    source = {"scalar": scalar, "typed": np.array([2], dtype="datetime64[3ns]"),
              "object": [scalar]}[carrier]
    kwargs = {"size": 1} if carrier == "scalar" else {}
    result = Pddt.fromdatetime64(source, **kwargs)
    assert result.unit == "ns" and result.asi8.tolist() == [6]
    with pytest.raises(ValueError, match="loss|precision|unit"):
        Pddt.fromdatetime64(source, unit="us", **kwargs)


def test_generic_nat_object_and_generic_native_dtype_have_different_roles():
    value = Pddt.fromdatetime64([np.datetime64("NaT")])
    assert value.unit == "s" and value.asi8.tolist() == [NAT]
    for source in (np.empty(0, dtype="datetime64"), np.array(["NaT"], dtype="datetime64")):
        with pytest.raises(ValueError, match="unsupported NumPy datetime unit"):
            Pddt.fromdatetime64(source)
    for dtype in ("ns", "3ns"):
        empty = Pddt.fromdatetime64(np.empty(0, dtype=f"datetime64[{dtype}]"))
        missing = Pddt.fromdatetime64(np.array(["NaT"], dtype=f"datetime64[{dtype}]"))
        assert empty.unit == missing.unit == "ns" and missing.asi8.tolist() == [NAT]
    assert Pddt.fromdatetime64([np.datetime64("NaT", "ns")], unit="s").unit == "s"


@pytest.mark.parametrize("size", (None, 0))
def test_source_unit_validation_precedes_scalar_count(size):
    with pytest.raises(ValueError, match="unsupported NumPy date unit"):
        Pddt.fromdatetime64(np.datetime64("NaT", "ps"), size=size)
    if size is None:
        with pytest.raises(ValueError, match="requires size"):
            Pddt.fromdatetime64(np.datetime64("NaT", "ns"))


def test_public_options_precede_bad_numpy_source():
    value = np.datetime64("NaT", "ps")
    with pytest.raises(ValueError, match="unit") as raised:
        Pddt.fromdatetime64(value, size=-1, unit="invalid")
    assert "NumPy" not in str(raised.value)
    with pytest.raises(ValueError, match="size"):
        Pddt.fromdatetime64(value, size=-1)
    with pytest.raises(TypeError, match="size"):
        Pddt.fromdatetime64(value, size=True)


def test_one_iterator_consumes_only_the_first_invalid_value():
    calls = []

    def source():
        calls.append(0)
        yield np.datetime64("NaT", "ps")
        calls.append(1)
        yield np.datetime64("2024-01-01", "D")

    with pytest.raises(ValueError, match=r"dt64\[0\].*unsupported NumPy date unit"):
        Pddt.fromdatetime64(source())
    assert calls == [0]


def test_numpy_factory_keeps_original_iterator_error_and_independent_controls():
    marker = LookupError("broken reader")

    def source():
        yield np.datetime64(1, "us")
        raise marker

    with pytest.raises(LookupError) as observed:
        Pddt.fromdatetime64(source())
    assert observed.value is marker
    value = np.datetime64("NaT", "ns")
    assert Pddt(np.array([value])).unit == "ns"
    assert Pddt.parse(np.array([value])).isna().tolist() == [True]
