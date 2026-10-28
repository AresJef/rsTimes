"""Approved P02/P03/P05/P16 foundations for the replacement Pddt."""
import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_native_array_retains_unit_missing_and_index_role(unit):
    source = np.array([0, 1, np.iinfo("int64").min], dtype="int64").view(
        f"datetime64[{unit}]"
    )
    result = Pddt(source, unit=unit, name="events")
    assert isinstance(result, pd.DatetimeIndex)
    assert result.unit == unit
    assert result.name == "events"
    np.testing.assert_array_equal(result.asi8, [0, 1, np.iinfo("int64").min])
    assert pd.DataFrame({"value": [1, 2, 3]}, index=result).index is result


def test_ordinary_empty_and_native_empty_have_distinct_defaults():
    assert Pddt([]).unit == "s"
    assert Pddt(np.array([], dtype="datetime64[ns]")).unit == "ns"


@pytest.mark.parametrize("shape", [(2, 1), ()])
def test_non_vector_native_input_is_not_flattened(shape):
    with pytest.raises(ValueError, match="one-dimensional"):
        Pddt(np.zeros(shape, dtype="datetime64[us]"))


def test_copy_true_isolates_native_input_but_copy_false_may_share():
    data = np.array([1, 2], dtype="int64").view("datetime64[us]")
    isolated = Pddt(data, copy=True)
    borrowed = Pddt(data, copy=False)
    data[0] = np.datetime64(7, "us")
    assert isolated.asi8[0] == 1
    assert borrowed.asi8[0] == 7


def test_unit_conversion_floors_negative_ticks_and_preserves_missing():
    data = np.array([-1500, 1500, np.iinfo("int64").min], dtype="int64").view(
        "datetime64[ns]"
    )
    result = Pddt(data, name="events").as_unit("us")
    assert type(result) is Pddt
    assert result.unit == "us" and result.name == "events"
    np.testing.assert_array_equal(result.asi8, [-2, 1, np.iinfo("int64").min])


def test_explicit_construction_and_lossless_conversion_reject_precision_loss():
    data = np.array([1], dtype="int64").view("datetime64[ns]")
    with pytest.raises(ValueError):
        Pddt(data, unit="us")
    with pytest.raises(ValueError):
        Pddt(data).as_unit("us", round_ok=False)


def test_finer_conversion_checks_capacity_instead_of_wrapping():
    data = np.array([2**63 - 1], dtype="int64").view("datetime64[s]")
    with pytest.raises(OverflowError):
        Pddt(data).as_unit("ns")


@pytest.mark.parametrize("bad", [0, 1, None, "False", [], object()])
def test_copy_option_rejects_non_boolean_even_for_empty_input(bad):
    with pytest.raises(TypeError, match="bool"):
        Pddt([], copy=bad)


def test_numpy_bool_option_is_supported_without_generic_truth_conversion():
    assert len(Pddt([], copy=np.bool_(True))) == 0


def test_option_does_not_call_arbitrary_truth_protocol():
    class Trap:
        def __bool__(self):
            raise AssertionError("truth callback must not run")

    with pytest.raises(TypeError, match="bool"):
        Pddt([], strict=Trap())


def test_numeric_none_scalar_is_not_an_empty_collection():
    with pytest.raises(TypeError):
        Pddt(None)


def test_non_contiguous_input_keeps_position_and_owner():
    source = np.arange(8, dtype="int64").view("datetime64[us]")[::-2]
    result = Pddt(source)
    np.testing.assert_array_equal(result.asi8, [7, 5, 3, 1])
    np.testing.assert_array_equal(result.as_unit("ns").asi8, [7000, 5000, 3000, 1000])


def test_dtype_multiplier_is_applied_instead_of_relabelled():
    source = np.array([1, -2], dtype="int64").view("datetime64[3us]")
    result = Pddt(source)
    assert result.unit == "us"
    np.testing.assert_array_equal(result.asi8, [3, -6])


def test_non_native_byte_order_keeps_actual_values():
    source = np.array([1, -2], dtype=">i8").view(">M8[us]")
    result = Pddt(source)
    np.testing.assert_array_equal(result.asi8, [1, -2])


def test_wide_years_are_not_constrained_by_python_datetime():
    source = np.array(["0000-01-01", "10000-01-01"], dtype="datetime64[us]")
    result = Pddt(source).as_unit("s")
    np.testing.assert_array_equal(result.asi8, [-62167219200, 253402300800])
