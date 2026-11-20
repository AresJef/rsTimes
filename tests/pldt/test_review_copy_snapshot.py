"""Copy and serialization pair the native date owner with its sorting flags."""
import copy
from datetime import datetime, timedelta
import pickle
import sys
import threading

import numpy as np
import polars as pl
import pytest

from rstimes import Pldt
from rstimes import _pldt_state


def named_copy(source):
    return source.copy(name="result")


def named_deepcopy(source):
    return source.copy(name="result", deep=True)


def pickle_copy(source):
    return pickle.loads(pickle.dumps(source))


def assert_extrema(source):
    ticks = source.to_physical().to_list()
    valid = [value for value in ticks if value is not None]
    epoch = datetime(1970, 1, 1)
    assert source.min() == epoch + timedelta(milliseconds=min(valid))
    assert source.max() == epoch + timedelta(milliseconds=max(valid))


@pytest.mark.parametrize("operation", (
    copy.copy, Pldt.__copy__, Pldt.copy, named_copy, copy.deepcopy, named_deepcopy, pickle_copy,
))
@pytest.mark.parametrize("schedule", ("before", "between", "after"))
def test_ordered_copy_metadata_describes_the_same_snapshot(operation, schedule):
    source = Pldt([1, 2], unit="ms", name="stamp").set_sorted()
    tail = Pldt([0], unit="ms", name="stamp")
    reader = _pldt_state.recipe if operation is pickle_copy else _pldt_state.copy_value
    read_calls = (_pldt_state.plain_series.__code__, _pldt_state._sorted.__code__)
    start, finished = threading.Event(), threading.Event()
    reads = []
    errors = []

    def append():
        if start.wait(10):
            try:
                source.append(tail)
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()

    def observe(frame, event, _):
        if frame.f_code not in read_calls or frame.f_back.f_code is not reader.__code__:
            return observe
        if event == "call":
            reads.append(frame.f_code)
        at_barrier = ((schedule == "before" and event == "call" and len(reads) == 1)
                      or (schedule == "between" and event == "call" and len(reads) == 2)
                      or (schedule == "after" and event == "return" and len(reads) == 2))
        if at_barrier and not start.is_set():
            start.set()
            assert finished.wait(10), "writer never completed its public append"
        return observe

    writer = threading.Thread(target=append)
    writer.start()
    previous_trace = sys.gettrace()
    sys.settrace(observe)
    try:
        result = operation(source)
    finally:
        sys.settrace(previous_trace)
        start.set()
        writer.join(11)
    assert not writer.is_alive() and finished.is_set() and not errors
    assert len(reads) == 2 and set(reads) == set(read_calls)
    assert source.to_physical().to_list() == [1, 2, 0]
    ticks = result.to_physical().to_list()
    assert ticks in ([1, 2], [1, 2, 0])
    assert isinstance(result, Pldt) and result is not source
    assert source.name == "stamp"
    assert result.name == ("result" if operation in (named_copy, named_deepcopy) else "stamp")
    assert_extrema(result)
    assert result.flags["SORTED_ASC"] == (ticks == [1, 2])


@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("operation", (copy.copy, copy.deepcopy, pickle_copy))
def test_stable_sorted_column_preserves_nulls_and_direction(descending, operation):
    ticks = [None, 2, 1] if descending else [None, 1, 2]
    original = Pldt(ticks, name="stamp", unit="ms").set_sorted(descending=descending)
    result = operation(original)
    assert result.flags["SORTED_DESC" if descending else "SORTED_ASC"]
    assert result.to_physical().to_list() == ticks
    assert_extrema(result)


def test_copy_shell_and_buffers_preserve_ownership():
    base = -(2**63)
    original = Pldt(pl.Series("stamp", [base, 1, 2], dtype=pl.Datetime("ns")))
    shallow, deep = copy.copy(original), copy.deepcopy(original)
    values = original.to_physical().to_numpy()
    assert np.shares_memory(shallow.to_physical().to_numpy(), values)
    assert not np.shares_memory(deep.to_physical().to_numpy(), values)
    original.append(Pldt([None], name="stamp", unit="ns"))
    assert original.to_physical().to_list() == [base, 1, 2, None]
    for result in (shallow, deep):
        assert result.to_physical().to_list() == [base, 1, 2]


@pytest.mark.parametrize(("ticks", "flag", "ordered"), [
    ([None, 1, 2], 1, True),
    ([2, 1, None], 2, True),
    ([None, 1, None], 1, False),
    ([1, None, 2], 1, False),
    ([1, 3, 2], 1, False),
    ([3, 2, 4], 2, False),
    ([None, -(2**63), 1], 1, True),
])
def test_restoration_checks_the_claimed_order_and_nulls_once(ticks, flag, ordered):
    original = Pldt(pl.Series("stamp", ticks, dtype=pl.Datetime("ns")))
    restore, args, state = original.__reduce__()
    assert state is None
    restored = restore(*args[:-1], flag)
    assert restored.to_physical().to_list() == ticks
    assert restored.flags == {
        "SORTED_ASC": flag == 1 and ordered,
        "SORTED_DESC": flag == 2 and ordered,
    }
