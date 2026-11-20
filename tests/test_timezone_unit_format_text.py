"""Raw text roles for timezone names, units and Pydt format emptiness."""
from datetime import timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pytest

pytest.importorskip("pandas")
pytest.importorskip("polars")
from rstimes import Pydt, Pddt, Pldt


class UTCDisplay(str):
    def lower(self):
        return "utc"


class UnitAlias(str):
    def __eq__(self, other):
        return other in ("ns", "us")

    __hash__ = str.__hash__


class EmptyDisplay(str):
    def __eq__(self, other):
        return other == ""

    __hash__ = str.__hash__


@pytest.mark.parametrize("base", (Pydt, Pddt, Pldt))
def test_timezone_name_uses_stored_name_before_alias_cache(base) -> None:
    zone = UTCDisplay("Asia/Shanghai")
    if base is Pydt:
        value = base(2024, 1, 1, tzinfo=zone)
        assert value.utcoffset() == timedelta(hours=8)
    elif base is Pddt:
        assert base(["2024-01-01"], tz=zone, unit="ns").asi8.tolist() == [1704038400000000000]
    else:
        assert base(["2024-01-01"], tz=zone, unit="ns").to_physical().to_list() == [1704038400000000000]


def test_pldt_zoneinfo_key_is_read_as_stored_text() -> None:
    zone = ZoneInfo.no_cache(UTCDisplay("Asia/Shanghai"))
    assert zone.utcoffset(Pydt(2024, 1, 1)) == timedelta(hours=8)
    value = Pldt(["2024-01-01"], tz=zone, unit="ns")
    assert value.to_physical().to_list() == [1704038400000000000]
    assert value.dtype.time_zone == "Asia/Shanghai"


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("unit", ("us", np.str_("us"), UnitAlias("us")))
def test_lossless_unit_reduction_rejects_nonzero_tail(base, unit: str) -> None:
    with pytest.raises(ValueError):
        base([1], unit="ns").as_unit(unit, round_ok=False)


@pytest.mark.parametrize("base", (Pddt, Pldt))
@pytest.mark.parametrize("unit", ("us", np.str_("us"), UnitAlias("us")))
def test_lossless_unit_reduction_selects_requested_stored_unit(base, unit: str) -> None:
    value = base([1000, None], unit="ns").as_unit(unit, round_ok=False)
    if base is Pddt:
        assert value.unit == "us" and value.asi8.tolist() == [1, -(1 << 63)]
    else:
        assert value.dtype.time_unit == "us" and value.to_physical().to_list() == [1, None]


@pytest.mark.parametrize("fmt", ("%Y", np.str_("%Y"), EmptyDisplay("%Y")))
def test_pydt_format_emptiness_uses_stored_length(fmt: str) -> None:
    assert Pydt(2024, 1, 2).__format__(fmt) == "2024"


def test_pydt_business_format_receives_original_nonempty_specification() -> None:
    seen = []

    class Business(Pydt):
        def strftime(self, fmt):
            seen.append(fmt)
            return "business output"

        def isoformat(self, sep="T", timespec="auto"):
            return "business ISO"

    spec = EmptyDisplay("%Y")
    value = Business(2024, 1, 2)
    assert value.__format__(spec) == "business output"
    assert len(seen) == 1 and seen[0] is spec
    assert value.__format__("") == "business ISO"
