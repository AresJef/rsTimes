"""Default restoration prevalidates real slot names before applying any part."""
import pytest


class SlotName(str):
    pass


class PretendText:
    @property
    def __class__(self):
        return str


@pytest.fixture(params=("Pddt", "Pldt"))
def series_class(request):
    pytest.importorskip({"Pddt": "pandas", "Pldt": "polars"}[request.param])
    import rstimes

    return getattr(rstimes, request.param)


@pytest.mark.parametrize("bad_key", [11, PretendText()], ids=("int", "pretend-str"))
def test_default_slot_name_prevalidation_is_atomic(series_class, bad_key):
    value = series_class([7], unit="ns", name="stamp")
    with pytest.raises(TypeError, match="slot names must be strings"):
        value.__setstate__(({"business": "changed"}, {"allowed": 1, bad_key: 2}))
    assert not hasattr(value, "business") and not hasattr(value, "allowed")
    assert value.name == "stamp" and value[0].isoformat().startswith("1970-01-01")


def test_true_slot_name_and_user_setter_remain_real_protocols(series_class):
    marker = LookupError("actual business setter")
    trace = []

    class Business(series_class):
        def __setattr__(self, name, value):
            if name == "allowed":
                trace.append((name, value))
            if name == "raise_here":
                raise marker
            super().__setattr__(name, value)

    value = Business([7], unit="ns", name="stamp")
    with pytest.raises(LookupError) as observed:
        value.__setstate__(({"business": 1}, {SlotName("allowed"): 2, "raise_here": 3}))
    assert observed.value is marker and trace == [("allowed", 2)]
    assert value.business == 1 and value.allowed == 2 and value.name == "stamp"
