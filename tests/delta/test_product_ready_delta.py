"""ProductReady Delta metadata keeps strict codec and immutable native values."""
import pytest

from rstimes import Delta


CORE17 = ("years", "months", "days", "hours", "minutes", "seconds", "microseconds", "nanoseconds",
          "year", "month", "day", "weekday", "hour", "minute", "second", "microsecond", "nanosecond")


class MetadataDelta(Delta):
    pass


class Dictionary(dict):
    pass


class Key(str):
    pass


def test_delta_restores_independent_shallow_metadata_without_changing_core():
    value = MetadataDelta(months=1, nanoseconds=1, nanosecond=123)
    value.old = "replaced"
    fields, initial_hash = tuple(getattr(value, name) for name in CORE17), hash(value)
    payload = []
    dictionary = {"payload": payload, "me": value}
    value.__setstate__(dictionary)
    assert value.__dict__ is not dictionary and "old" not in value.__dict__
    assert value.payload is payload and value.me is value
    dictionary[42] = "late edit"
    assert 42 not in value.__dict__
    assert tuple(getattr(value, name) for name in CORE17) == fields
    assert hash(value) == initial_hash


@pytest.mark.parametrize("invalid", [Dictionary(ok=1), {42: "invalid"}, {Key("name"): "invalid"}])
@pytest.mark.parametrize("part", ["dictionary", "slots"])
def test_delta_rejects_noncanonical_metadata_before_applying_either_part(invalid, part):
    value = MetadataDelta(nanoseconds=1)
    value.old = "retained"
    state = (invalid, {"extra": 2}) if part == "dictionary" else ({"new": 1}, invalid)
    with pytest.raises(TypeError):
        value.__setstate__(state)
    assert value.__dict__ == {"old": "retained"}
    assert value.nanoseconds == 1
