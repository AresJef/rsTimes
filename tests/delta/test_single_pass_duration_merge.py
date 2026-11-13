"""Independent integer oracle for a single final day/clock normalization."""
import numpy as np
import pytest

from rstimes import Delta

DAY = 86_400_000_000_000


@pytest.mark.parametrize("days,clock", [(-(2**63), 0), (-(2**63), DAY-1), (2**63-1, 0), (2**63-1, DAY-1), (-1, 1), (0, DAY-1)])
@pytest.mark.parametrize("unit,scale", [("us", 1000), ("ns", 1), ("2D", 2*DAY)])
@pytest.mark.parametrize("ticks", [-1, 1])
@pytest.mark.parametrize("operation", ["add", "sub", "radd", "rsub"])
def test_numpy_duration_normalizes_once_at_final_signed_day_boundary(days, clock, unit, scale, ticks, operation):
    left = Delta(days=days, nanoseconds=clock, nanosecond=2)
    right = np.timedelta64(ticks, unit)
    total = days * DAY + clock
    expected = (total + ticks*scale if operation in ("add", "radd")
                else total - ticks*scale if operation == "sub" else ticks*scale - total)
    expected_day, expected_clock = divmod(expected, DAY)

    def calculate():
        if operation == "add":
            return left + right
        if operation == "sub":
            return left - right
        if operation == "radd":
            return right + left
        return right - left

    if not -(2**63) <= expected_day < 2**63:
        with pytest.raises(OverflowError):
            calculate()
    else:
        result = calculate()
        actual_clock = ((result.hours*60 + result.minutes)*60 + result.seconds)*1_000_000_000 + result.microseconds*1000 + result.nanoseconds
        assert (result.days, actual_clock) == (expected_day, expected_clock)
        assert result.nanosecond == 2
    assert left.days == days and left.nanosecond == 2
