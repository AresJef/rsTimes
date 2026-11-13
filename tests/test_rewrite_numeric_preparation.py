"""P04 boundary protocols are prepared once before scalar or batch kernels."""
import numpy as np
import pytest

from rstimes._native import _integer_arg


def test_index_callback_runs_once_and_preserves_its_integer():
    class Counted:
        calls = 0

        def __index__(self):
            self.calls += 1
            return -17

    value = Counted()
    assert _integer_arg(value, "Pddt.offset", "offset") == -17
    assert value.calls == 1


def test_index_callback_keeps_the_original_exception_object():
    failure = RuntimeError("source failed")

    class Broken:
        def __index__(self):
            raise failure

    with pytest.raises(RuntimeError) as caught:
        _integer_arg(Broken(), "Pddt.offset", "offset")
    assert caught.value is failure


@pytest.mark.parametrize("bad", [True, np.bool_(False), 1.0, "1"])
def test_integer_preparation_does_not_coerce_other_scalar_roles(bad):
    with pytest.raises(TypeError):
        _integer_arg(bad, "Pddt.offset", "offset")
