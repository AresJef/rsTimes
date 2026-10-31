"""D01.O4: immutable owners and the original snapshot time are both required."""
import gc
import weakref
import warnings

import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt
import rstimes._native as native


def _rescale(snapshot):
    packed = native._pddt_rescale(snapshot, "us", "ns", False, "Pddt.as_unit")
    return np.frombuffer(packed, dtype="i8").tolist()


def test_immutable_byte_owner_survives_original_array_deletion_and_slice_offset():
    source = np.frombuffer(np.arange(2048, dtype="i8").tobytes(), dtype="i8")[256:1792]
    snapshot = native._pddt_data(source)
    assert isinstance(snapshot, native._PddtTicks)
    owner = weakref.ref(source)
    del source
    gc.collect()
    assert owner() is None
    assert _rescale(snapshot) == [value * 1000 for value in range(256, 1792)]


@pytest.mark.parametrize("count", [1, 2048])
def test_whole_immutable_range_reuses_its_exact_byte_owner(count):
    owner = np.arange(count, dtype="i8").tobytes()
    source = np.frombuffer(owner, dtype="i8")
    snapshot = native._pddt_data(source)
    assert snapshot is owner
    assert _rescale(snapshot) == [value * 1000 for value in range(count)]


@pytest.mark.parametrize("readonly", [False, True])
def test_external_writable_alias_always_gets_an_independent_snapshot(readonly):
    owner = np.array([1, 2, 3], dtype="i8")
    source = owner.view()
    source.flags.writeable = not readonly
    snapshot = native._pddt_data(source)
    assert type(snapshot) is bytes
    owner[:] = 99
    assert _rescale(snapshot) == [1000, 2000, 3000]


@pytest.mark.parametrize("form", ["stride", "reverse", "endian", "empty", "zero-dim"])
def test_nonborrowable_layout_keeps_the_actual_ordered_bytes_snapshot(form):
    source = np.frombuffer(np.arange(8, dtype="i8").tobytes(), dtype="i8")
    if form == "stride":
        source = source[::2]
    elif form == "reverse":
        source = source[::-1]
    elif form == "endian":
        source = source.astype(">i8")
    elif form == "empty":
        source = source[:0]
    else:
        source = np.array(1, dtype="i8")
    snapshot = native._pddt_data(source)
    assert type(snapshot) is bytes and snapshot == source.tobytes()


def test_true_array_subclass_keeps_its_actual_tobytes_protocol_once():
    calls = []

    class Values(np.ndarray):
        def tobytes(self, *args, **kwargs):
            calls.append("tobytes")
            return np.array([7, 8], dtype="i8").tobytes()

    source = np.frombuffer(b"\x00" * 16, dtype="i8").view(Values)
    snapshot = native._pddt_data(source)
    assert calls == ["tobytes"] and _rescale(snapshot) == [7000, 8000]


def test_public_query_snapshots_mutable_values_before_later_unit_callback():
    column = np.array(["2024-01-01", "2024-02-01"], dtype="datetime64[us]").view("i8")
    armed = [False]
    calls = []

    class View(Pddt):
        @property
        def asi8(self):
            return column

        @property
        def unit(self):
            if armed[0]:
                armed[0] = False
                calls.append("unit")
                column[:] = np.datetime64("2030-01-01", "us").astype("i8")
            return "us"

    value = View(np.array(["2024-01-01", "2024-02-01"], dtype="datetime64[us]"))
    armed[0] = True
    result = value.year
    assert result.tolist() == [2024, 2024] and calls == ["unit"]
    assert column.tolist() == [1893456000000000, 1893456000000000]


def test_public_query_captures_immutable_geometry_before_later_unit_callback():
    original = np.array(["2021-01-01", "2022-01-01", "2023-01-01", "2024-01-01"],
                        dtype="datetime64[us]").view("i8")
    column = np.frombuffer(original.tobytes(), dtype="i8")
    armed = [False]

    class View(Pddt):
        @property
        def asi8(self):
            return column

        @property
        def unit(self):
            if armed[0]:
                armed[0] = False
                # Deliberately mutate the same valid view's geometry; making a
                # new reshaped view would not test the captured argument.
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=DeprecationWarning,
                                            message="Setting the (shape|strides) on a NumPy array.*")
                    column.shape = (2, 2)
                    column.strides = (8, 16)
                gc.collect()
            return "us"

    value = View(original.view("datetime64[us]"))
    armed[0] = True
    assert value.year.tolist() == [2021, 2022, 2023, 2024]
    assert column.shape == (2, 2) and column.strides == (8, 16)


@pytest.mark.parametrize("kind", [RuntimeError, MemoryError, KeyboardInterrupt, SystemExit])
def test_public_query_preserves_original_snapshot_callback_exception(kind):
    error = kind("snapshot callback")
    calls = []

    class Source:
        def tobytes(self):
            calls.append("snapshot")
            raise error

    class View(Pddt):
        @property
        def asi8(self):
            return Source()

    value = View(np.array([0], dtype="datetime64[us]"))
    with pytest.raises(kind) as caught:
        _ = value.year
    assert caught.value is error and calls == ["snapshot"]


def test_public_queries_and_rescale_keep_nat_name_unit_and_source():
    value = Pddt(["2024-01-02 12:34:56.123456", None], name="time")
    years = value.year.tolist()
    assert years[0] == 2024 and np.isnan(years[1])
    milliseconds = value.millisecond
    assert milliseconds[0] == 123 and milliseconds.isna().tolist() == [False, True]
    result = value.as_unit("ns")
    assert result.unit == "ns" and result.name == "time"
    assert result.asi8.tolist() == [1704198896123456000, -(2**63)]
    assert value.unit == "us" and value.asi8.tolist() == [1704198896123456, -(2**63)]
