"""Default state validates and applies one stored batch (N04, decision D02)."""
import pytest

pytest.importorskip("pandas")
pytest.importorskip("polars")
from rstimes import Pddt, Pldt


def test_pddt_dictionary_lookup_cannot_replace_validated_core() -> None:
    incoming = {"payload": 2}
    replacement = Pddt(["2030-01-01"])
    armed = False

    class Business(Pddt):
        def __getattribute__(self, name):
            if armed and name == "__dict__":
                incoming["_data"] = replacement.array
            return super().__getattribute__(name)

    value = Business(["2024-01-01"])
    expected = value.asi8.tolist()
    armed = True
    Pddt.__setstate__(value, incoming)
    armed = False
    assert value.asi8.tolist() == expected
    assert value.payload == 2
    assert "_data" in incoming  # The real getter still ran once.


@pytest.mark.parametrize("base,core", ((Pddt, "_data"), (Pldt, "_s")))
def test_slot_setter_cannot_change_pending_batch(base, core: str) -> None:
    incoming = {"a": 1, "b": 2}
    replacement = base(["2030-01-01"])
    armed = False

    class Business(base):
        __slots__ = ("a", "b")

        def __setattr__(self, name, item):
            if armed and name == "a":
                incoming.pop("b", None)
                incoming[core] = getattr(replacement, core)
            super().__setattr__(name, item)

    value = Business(["2024-01-01"])
    before = value.asi8.tolist() if base is Pddt else value.to_physical().to_list()
    armed = True
    base.__setstate__(value, (None, incoming))
    armed = False
    after = value.asi8.tolist() if base is Pddt else value.to_physical().to_list()
    assert after == before
    assert value.a == 1 and value.b == 2
    assert core in incoming


class StoredState(dict):
    def __iter__(self):
        raise AssertionError("default state must read stored entries")

    def keys(self):
        raise AssertionError("default state must not call a mapping exporter")

    def __getitem__(self, key):
        raise AssertionError("default state must not dispatch a virtual getter")

    def __contains__(self, key):
        raise AssertionError("default state must validate stored keys")


@pytest.mark.parametrize("base", (Pddt, Pldt))
def test_default_dictionary_uses_stored_entries(base) -> None:
    value = base(["2024-01-01"])
    payload = []
    incoming = StoredState(payload=payload)
    base.__setstate__(value, incoming)
    assert value.payload is payload
    assert dict.__getitem__(incoming, "payload") is payload


@pytest.mark.parametrize("base,core", ((Pddt, "_data"), (Pldt, "_s")))
def test_core_keys_present_at_entry_are_rejected(base, core: str) -> None:
    value = base(["2024-01-01"])
    with pytest.raises(ValueError, match="core|internal"):
        base.__setstate__(value, StoredState({core: getattr(value, core)}))


@pytest.mark.parametrize("base", (Pddt, Pldt))
def test_real_slot_setter_keeps_original_exception(base) -> None:
    original = LookupError("business slot setter")

    class Business(base):
        __slots__ = ()

        @property
        def payload(self):
            return None

        @payload.setter
        def payload(self, item):
            raise original

    value = Business(["2024-01-01"])
    with pytest.raises(LookupError) as caught:
        base.__setstate__(value, (None, {"payload": 2}))
    assert caught.value is original


@pytest.mark.parametrize("base,core,error", ((Pddt, "_data", TypeError), (Pldt, "_s", ValueError)))
def test_existing_dictionary_and_slots_error_order_is_preserved(base, core: str, error) -> None:
    value = base(["2024-01-01"])
    with pytest.raises(error):
        base.__setstate__(value, ({core: getattr(value, core)}, 7))
