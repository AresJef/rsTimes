"""Native Duration values keep their independent validity (N03, D01)."""
import numpy as np
import pytest

pl = pytest.importorskip("polars")
pytest.importorskip("pandas")
from rstimes import Pddt

MIN = -(1 << 63)
MAX = (1 << 63) - 1


def dates(ticks: list[int], unit: str) -> Pddt:
    return Pddt(np.array(ticks, dtype=f"datetime64[{unit}]"), unit=unit, name="time")


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
@pytest.mark.parametrize("reflected", (False, True))
def test_valid_minimum_and_null_are_distinct(unit: str, reflected: bool) -> None:
    source = dates([1, 1, 0], unit)
    duration = pl.Series("span", [MIN, None, MIN + 1], dtype=pl.Duration(unit))
    result = source.__radd__(duration) if reflected else source + duration
    assert result.asi8.tolist() == [MIN + 1, MIN, MIN + 1]
    assert result.unit == unit
    assert result.name == "time"
    assert source.asi8.tolist() == [1, 1, 0]


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
def test_minimum_span_can_cancel_to_maximum_date(unit: str) -> None:
    result = dates([-1], unit) - pl.Series("span", [MIN], dtype=pl.Duration(unit))
    assert result.asi8.tolist() == [MAX]


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
def test_valid_result_colliding_with_nat_is_overflow(unit: str) -> None:
    with pytest.raises(OverflowError, match=r"result\[0\]"):
        dates([0], unit) + pl.Series("span", [MIN], dtype=pl.Duration(unit))


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
def test_numpy_duration_minimum_remains_missing(unit: str) -> None:
    result = dates([1], unit) + np.array([MIN], dtype=f"timedelta64[{unit}]")
    assert result.asi8.tolist() == [MIN]


@pytest.mark.parametrize("unit", ("ms", "us", "ns"))
def test_slice_and_multiple_chunks_keep_validity(unit: str) -> None:
    first = pl.Series("span", [9, MIN], dtype=pl.Duration(unit))
    second = pl.Series("span", [None, MIN + 1, 8], dtype=pl.Duration(unit))
    duration = pl.concat([first, second], rechunk=False).slice(1, 3)
    assert (dates([1, 1, 0], unit) + duration).asi8.tolist() == [MIN + 1, MIN, MIN + 1]


class ExportedDuration(pl.Series):
    casts = 0

    def cast(self, *args: object, **kwargs: object) -> pl.Series:
        self.casts += 1
        return pl.Series("span", [17], dtype=pl.Int64)


def test_native_duration_uses_stored_values_not_cast_override() -> None:
    duration = ExportedDuration("span", [5], dtype=pl.Duration("ns"))
    assert (dates([1], "ns") + duration).asi8.tolist() == [6]
    assert duration.casts == 0


def test_explicit_duration_conversion_uses_exported_values() -> None:
    duration = ExportedDuration("span", [5], dtype=pl.Duration("ns"))
    exported = duration.cast(pl.Int64).to_numpy().view("timedelta64[ns]")
    assert (dates([1], "ns") + exported).asi8.tolist() == [18]
    assert duration.casts == 1


def test_empty_duration_and_length_validation() -> None:
    result = dates([], "ns") + pl.Series("span", [], dtype=pl.Duration("ns"))
    assert len(result) == 0 and result.unit == "ns"
    with pytest.raises(ValueError, match="length"):
        dates([1, 2], "ns") + pl.Series("span", [5], dtype=pl.Duration("ns"))


def test_normal_positive_and_negative_spans() -> None:
    duration = pl.Series("span", [5, -5, None], dtype=pl.Duration("ns"))
    assert (dates([1, 1, 1], "ns") + duration).asi8.tolist() == [6, -4, MIN]
