"""CR04: numeric callbacks cannot introduce an unrepresentable live rule."""
from dateutil.relativedelta import MO, relativedelta
import pytest
from rstimes import Delta


def test_cr04_immutable_name_cache_retains_live_field_order():
    events = []
    names = {"years", "months", "days", "hours", "minutes", "seconds", "microseconds",
             "year", "month", "day", "weekday", "hour", "minute", "second", "microsecond", "leapdays"}

    class Source(relativedelta):
        def __getattribute__(self, name):
            if name in names:
                events.append(name)
            return super().__getattribute__(name)

    source = Source(days=1.5)
    events.clear()
    assert Delta.from_relativedelta(source) == Delta(days=1, hours=12)
    assert events == ["weekday", "leapdays", "years", "months", "days", "hours", "minutes",
                      "seconds", "microseconds", "year", "month", "day", "weekday", "hour",
                      "minute", "second", "microsecond", "weekday", "leapdays"]


@pytest.mark.parametrize("field", ["years", "year", "month", "day", "hour", "minute", "second", "microsecond"])
@pytest.mark.parametrize("direction", ["factory", "add", "radd", "sub", "rsub", "batch"])
def test_cr04_live_weekday_after_numeric_callback_is_rejected(field, direction):
    source = relativedelta()
    events = []

    class SetWeekday:
        def __index__(self):
            events.append("index")
            source.weekday = MO
            return 1

    setattr(source, field, SetWeekday())
    delta = Delta(days=2)
    run = {"factory": lambda: Delta.from_relativedelta(source), "add": lambda: delta + source,
           "radd": lambda: source + delta, "sub": lambda: delta - source,
           "rsub": lambda: source - delta, "batch": lambda: delta.apply_many([source])}[direction]
    with pytest.raises(ValueError, match="weekday"):
        run()
    assert events == ["index"]


def test_cr04_late_numeric_exception_is_the_original_object():
    marker = RuntimeError("source clock conversion failed")

    class Failing:
        def __index__(self):
            raise marker

    source = relativedelta()
    source.microsecond = Failing()
    with pytest.raises(RuntimeError) as caught:
        Delta.from_relativedelta(source)
    assert caught.value is marker
