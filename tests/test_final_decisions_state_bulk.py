"""F19/F20: live iteration, immutable values and real serialization hooks."""

import copy
import pickle
import subprocess
import sys
import threading
from datetime import datetime

import pytest

from rstimes import Delta, Pydt


class SavedDelta(Delta):
    def __getstate__(self):
        return {"note": self.note}

    def __setstate__(self, state):
        self.note = state["note"]
        self.lock = threading.Lock()


class WholeDelta(Delta):
    def __reduce__(self):
        return (list, (["whole recipe"],))


class HiddenPydtMeta(type):
    def __getattribute__(self, name):
        if name == "__getstate__":
            return object.__getstate__
        if name == "__reduce__":
            return Pydt.__reduce__
        return super().__getattribute__(name)


class SavedPydt(Pydt, metaclass=HiddenPydtMeta):
    def __getstate__(self):
        return {"note": self.note}

    def __setstate__(self, state):
        self.note = state["note"]


class WholePydt(Pydt, metaclass=HiddenPydtMeta):
    def __reduce__(self):
        return (list, (["whole recipe"],))


def test_delta_custom_extra_state_preserves_immutable_core_before_restore():
    value = SavedDelta(days=1)
    value.note = "saved"
    value.lock = threading.Lock()
    result = pickle.loads(pickle.dumps(value))
    assert type(result) is SavedDelta and result.days == 1 and result.note == "saved"
    assert result.lock is not value.lock


@pytest.mark.parametrize("value", [WholeDelta(days=1), WholePydt(2024, 1, 2)])
def test_whole_reduce_override_can_choose_another_result_type(value):
    assert pickle.loads(pickle.dumps(value)) == ["whole recipe"]


def test_pydt_state_hook_uses_real_mro_and_receives_arbitrary_custom_state():
    value = SavedPydt(2024, 1, 2)
    value.note = "saved"
    result = pickle.loads(pickle.dumps(value))
    assert type(result) is SavedPydt and result == datetime(2024, 1, 2)
    assert result.note == "saved"


def test_runtime_reduction_changes_are_not_frozen_as_absent():
    class Child(Delta): pass
    value = Child(days=2)
    assert type(value.__reduce_ex__(4)) is tuple
    Child.__reduce__ = lambda self: (list, (["updated"],))
    assert value.__reduce_ex__(4) == (list, (["updated"],))
    class DateChild(Pydt): pass
    value = DateChild(2024, 1, 2)
    value.__reduce_ex__(4)
    DateChild.__reduce__ = lambda self: (list, (["updated"],))
    assert value.__reduce_ex__(4) == (list, (["updated"],))


@pytest.mark.parametrize("base", [Delta, Pydt])
def test_restore_snapshots_both_dictionaries_before_target_lookup(base):
    dictionary = {"note": "saved"}
    slots = {"slot": "kept"}
    class Child(base):
        __slots__ = ("slot", "__dict__") if base is Delta else ("slot",)
        def __getattribute__(self, name):
            if name == "__dict__" and dictionary:
                dictionary.clear()
                slots.clear()
            return super().__getattribute__(name)
    value = Child(days=1) if base is Delta else Child(2024, 1, 2)
    value.old = "existing"
    base.__setstate__(value, (dictionary, slots))
    assert value.note == "saved" and value.slot == "kept"
    assert hasattr(value, "old") is (base is Pydt)


@pytest.mark.parametrize("operation", ["clear", "replace", "delete", "insert", "append"])
def test_first_bulk_item_survives_numpy_type_preparation_callback(operation):
    code = r'''
import sys, types
import numpy as np
import pandas, polars
from datetime import datetime
from rstimes import Delta
module = np._core._multiarray_umath
original_class = type(module)
values = [np.datetime64("2024-01-01", "us"), np.datetime64("2025-01-01", "us")]
armed = True
class DuringPreparation(original_class):
    def __getattribute__(self, name):
        global armed
        if name == "_ARRAY_API" and armed:
            armed = False
            op = sys.argv[1]
            if op == "clear": values.clear()
            elif op == "replace": values[0] = np.datetime64("2030-01-01", "us")
            elif op == "delete": del values[0]
            elif op == "insert": values.insert(0, np.datetime64("2030-01-01", "us"))
            else: values.append(np.datetime64("2030-01-01", "us"))
        return super().__getattribute__(name)
module.__class__ = DuringPreparation
result = Delta(days=1).apply_many(values)
module.__class__ = original_class
expected = {"clear": [2024], "replace": [2024, 2025], "delete": [2024],
            "insert": [2024, 2024, 2025], "append": [2024, 2025, 2030]}[sys.argv[1]]
assert not armed, "first preparation was not exercised"
assert result == [datetime(y, 1, 2) for y in expected], (result, expected)
'''
    result = subprocess.run([sys.executable, "-c", code, operation], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr

