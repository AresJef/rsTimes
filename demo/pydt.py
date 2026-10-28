"""Compare representative Pydt operations with the frozen original.

Run ``python demo/pydt.py`` from any directory. Like the Delta and Parser
demos, this uses runtime.json to select and verify the adopted local wheel.
Timings are informal observations, not formal performance acceptance.
"""
from pathlib import Path
import json
import os
import sys


def _launch_selected_environment():
    """Use the shared demo selection before importing either implementation."""
    here = Path(__file__).resolve()
    root = here.parents[1]
    selected = json.loads((here.parent / "runtime.json").read_text())
    environment = (root / selected["environment"]).resolve()
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if __name__ == "__main__" and (Path(sys.prefix).resolve() != environment or not sys.flags.isolated):
        os.execv(str(python), [str(python), "-I", str(here), *sys.argv[1:]])
    sys.path.insert(0, str(here.parent))


_launch_selected_environment()
import delta as _delta_demo  # Reuse the existing version/native identity check.
from datetime import datetime, date, timedelta, timezone
from importlib.metadata import version
from statistics import median
from time import perf_counter_ns
from zoneinfo import ZoneInfo
import copy
import pickle
import numpy as np
import pandas as pd
from cytimes import Pydt as PydtO
from rstimes import Pydt as PydtR, Delta, Configs, _native


def _describe(value):
    """Show real fields and fold without depending on legacy display formatting."""
    if isinstance(value, datetime):
        fields = [getattr(datetime, key).__get__(value) for key in
                  ("year", "month", "day", "hour", "minute", "second", "microsecond")]
        zone = datetime.tzinfo.__get__(value)
        return f"{fields}; tz={zone}; fold={datetime.fold.__get__(value)}"
    return repr(value)


def _show(label, operation, *, difference=None, iterations=128):
    """Print paired results and median batch-average timings."""
    outcomes = []
    print(f"\n{label}")
    for name, cls in (("Original", PydtO), ("Rust", PydtR)):
        try:
            result = operation(cls)
            shown = _describe(result)
            batches = []
            for _ in range(3):
                start = perf_counter_ns()
                for _ in range(iterations):
                    operation(cls)
                batches.append((perf_counter_ns() - start) / iterations)
            print(f"  {name:8}: {shown}\n            {median(batches) / 1000:.3f} us/call (demo only)")
            outcomes.append(("value", shown))
        except Exception as error:
            print(f"  {name:8}: {type(error).__name__}: {error}")
            outcomes.append(("error", type(error).__name__))
    if difference:
        print(f"  Approved behavior: {difference}")
    elif outcomes[0] != outcomes[1]:
        raise AssertionError(f"Unexpected result difference: {label}: {outcomes}")


def constructor_demo():
    """Build from explicit fields and the supported date input families."""
    _show("Explicit construction", lambda cls: cls(2024, 5, 7, 15, 30, fold=0))
    _show("Default fold", lambda cls: cls(2024, 5, 7),
          difference="The new default fold is 0, matching datetime.")
    _show("Date input", lambda cls: cls.fromdate(date(2024, 5, 7)),
          difference="New constructors use fold=0 unless the input carries fold.")
    _show("Exact negative epoch", lambda cls: cls.frommicroseconds(-1),
          difference="New constructors default to fold=0.")
    _show("NumPy nanosecond input", lambda cls: cls.fromdatetime64(np.datetime64("2024-05-07T15:30:01.123456789")),
          difference="Both use microsecond fields; the new default fold is 0.")


    _show("Combine clock fields from datetime", lambda cls: cls.combine(
        date(2024, 5, 7), datetime(2000, 1, 1, 9, 30)),
        difference="A datetime clock supplies only time, timezone and fold.")
    try:
        PydtR.combine(date(2024, 5, 7), pd.NaT)
    except ValueError as error:
        print("\nMissing combine time:", type(error).__name__, error)
    else:
        raise AssertionError("Pydt.combine must reject a missing pandas clock")


def fields_demo():
    """Read date and clock fields directly, without accessor aliases."""
    _show("Date and clock fields", lambda cls: (
        cls(2024, 5, 7, 15, 30, 45, 123456, fold=0).year,
        cls(2024, 5, 7, 15, 30, 45, 123456, fold=0).microsecond,
        cls(2024, 5, 7, 15, 30, 45, 123456, fold=0).millisecond,
        cls(2024, 5, 7, 15, 30, 45, 123456, fold=0).quarter))
    print("  Rust uses p.year, p.millisecond, p.quarter and p.weekday().")
    print("  The twelve old access_*() aliases are no longer available.")
    for name in ("day_of_year", "days_in_month", "is_leap_year"):
        _show(f"Calendar property: {name}", lambda cls, name=name:
              getattr(cls(2024, 5, 7, fold=0), name) if cls is PydtR
              else getattr(cls(2024, 5, 7, fold=0), name)())


def calendar_demo():
    """Move through months, quarters and weekdays."""
    _show("Month-end adjustment", lambda cls: cls(2024, 1, 31, fold=0).to_month(1))
    _show("Next quarter", lambda cls: cls(2024, 5, 7, fold=0).to_next_quarter(month=1, day=1))
    _show("This Monday", lambda cls: cls(2024, 5, 7, 15, fold=0).to_monday())
    _show("Reject out-of-range clock fields", lambda cls: cls(2024, 5, 7, fold=0).to_time(hour=25, minute=70),
          difference="Rust rejects explicit clock values outside their ranges; use None to retain a field.")
    _show("Calendar facts", lambda cls: (cls(2024, 5, 7, fold=0).quarter,
                                        cls(2024, 5, 7, fold=0).days_in_year(),
                                        cls(2024, 5, 7, fold=0).day_of_quarter()))


def period_demo():
    """Find calendar boundaries and inspect fields without changing the value."""
    _show("Quarter end", lambda cls: cls(2024, 5, 7, fold=0).to_end_of("Q"))
    _show("Week start", lambda cls: cls(2024, 5, 7, 15, fold=0).to_start_of("W"))
    _show("Last representable date is Sunday?", lambda cls: cls(9999, 12, 31, fold=0).is_last_of("W"))
    _show("Unknown boundary predicate", lambda cls: cls(2024, 1, 1, fold=0).is_start_of("unknown"),
          difference="Unknown or empty names now raise ValueError; valid nonmatches return False.")


    value = PydtR(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    observed = (value.to_start_of("us") is value, value.to_end_of("ns") is value,
                value.is_start_of("us"), value.is_end_of("us"), value.fold)
    print("\nRust minimum precision (identity, identity, start, end, fold):", observed)
    assert observed == (True, True, True, True, 1)


def precision_demo():
    """Round or trim clock fields, retaining repeated-time fold."""
    _show("Round to minute", lambda cls: cls(2024, 5, 7, 15, 30, 45, 123456, fold=0).round("min"))
    _show("Trim milliseconds", lambda cls: cls(2024, 5, 7, 15, 30, 1, 123456, fold=0).fsp(3))
    _show("Trim while keeping fold", lambda cls: cls(2024, 11, 3, 1, 30, 1, 123456,
           tzinfo=ZoneInfo("America/New_York"), fold=1).fsp(3),
          difference="The new fsp preserves repeated-time fold and uses the shared regional gap rule.")


def timezone_demo():
    """Convert instants and show the explicit local-calendar gap policy."""
    zones = PydtR(2024, 1, 1).tz_available
    assert isinstance(zones, set) and all(isinstance(key, str) for key in zones)
    print('\nAvailable timezone names (independent set):', len(zones))
    _show("UTC to New York", lambda cls: cls(2024, 5, 7, 15, tzinfo=timezone.utc, fold=0).tz_convert("America/New_York"))
    _show("UTC conversion at the spring transition", lambda cls: cls(2024, 3, 10, 2, 30, tzinfo=timezone.utc, fold=0).tz_convert("America/New_York"),
          difference="The new conversion preserves the instant without treating UTC as local wall time.")
    _show("Move across a missing local time", lambda cls: cls(2024, 3, 9, 2, 30,
           tzinfo=ZoneInfo("America/New_York"), fold=0).to_day(1),
          difference="Calendar moves prefer the source UTC offset and choose an existing result; this forward move reaches03:30.")
    _show("Convert None means naive UTC", lambda cls: cls(2024, 5, 7, 12,
           tzinfo=ZoneInfo("Asia/Shanghai"), fold=0).tz_convert(None))


def arithmetic_demo():
    """Use calendar increments, standard durations, Delta and NumPy operands."""
    _show("Calendar increments", lambda cls: cls(2024, 5, 7, 15, fold=0).add(months=2, days=3, hours=4))
    _show("Standard timedelta", lambda cls: cls(2024, 5, 7, fold=0) + timedelta(days=2, seconds=3))
    _show("Shared Rust Delta", lambda cls: cls(2024, 1, 31, fold=0) + Delta(months=1))
    _show("NumPy duration", lambda cls: cls(2024, 5, 7, fold=0) + np.timedelta64(90, "m"))
    _show("Month boundaries crossed", lambda cls: cls(2024, 1, 31, fold=0).diff("2024-02-01", "M"))


def standard_datetime_demo():
    """Show the approved standard-library interface and equality rules."""
    _show("weekday() method", lambda cls: cls(2024, 5, 7, fold=0).weekday()
          if cls is PydtR else cls(2024, 5, 7, fold=0).weekday,
          difference="Rust uses datetime's weekday() method; frozen cyTimes 3.1.0 exposes a property.")
    _show("ISO calendar interface", lambda cls: cls(2024, 5, 7, fold=0).isocalendar(),
          difference="The new result is the standard ISO calendar tuple, rather than a dictionary.")
    _show("Strict replace", lambda cls: cls(2024, 1, 31, fold=0).replace(month=2),
          difference="Standard replace rejects the invalid February date; use to_date(month=2) to clamp.")
    def repeated(cls):
        a=cls(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=0)
        b=cls(2024,11,3,1,30,tzinfo=a.tzinfo,fold=1)
        return (a==b, hash(a)==hash(b), a-b)
    _show("Same-timezone repeated values", repeated,
          difference="Comparison, hash and subtraction now follow standard datetime consistently.")


    stamp = pd.Timestamp("2024-01-01 00:00:00.000000123")
    _show("Timestamp nanosecond equality", lambda cls: cls(2024, 1, 1, fold=0) == stamp,
          difference="Rust compares the Timestamp nanosecond remainder; these values differ.")
    stamp = pd.Timestamp("2024-01-01 00:00:00.000000877")
    _show("Timestamp difference rounded once", lambda cls: cls(2024, 1, 1, fold=0) - stamp,
          difference="Rust returns standard timedelta(microseconds=-1), rounding only at the end.")


def parse_demo():
    """Parse with the completed Parser and customize a stored month word."""
    _show("Common date string", lambda cls: cls.parse("2024-05-07T15:30:01"),
          difference="The new class shares the completed Parser and defaults fold to 0.")
    cfg=Configs();cfg.add_month("harvest",10)
    print("\nRust configuration:", PydtR.parse("14 harvest 2026",cfg=cfg))
    print("Rust strict parse:", PydtR.parse("2024-02-29",strict=True))
    numeric = PydtR.strptime("2024001", "%Y0%m")
    assert (numeric.year, numeric.month, numeric.day) == (2024, 1, 1)
    print("Rust strptime with a literal digit:", numeric)
    try:
        numeric.to_date(month="February")
    except TypeError as error:
        print("Month replacement requires an integer:", error)
    else:
        raise AssertionError("Month names are not numeric replacement fields")



class ChildR(PydtR):
    """A normal user subclass with writable extra state."""
    __slots__=("tag",)


def state_demo():
    """Save values and ordinary subclass metadata through Python protocols."""
    _show("Pickle round trip", lambda cls: pickle.loads(pickle.dumps(cls(2024,5,7,fold=1))),
          difference="The new version supports value, timezone, fold and normal subclass state.")
    value=ChildR(2024,5,7,fold=1);value.tag={"labels":["saved"]};value.extra="dictionary"
    for label,result in (("copy",copy.copy(value)),("deepcopy",copy.deepcopy(value)),
                         ("pickle",pickle.loads(pickle.dumps(value)))):
        print(f"  Rust {label}: {type(result).__name__}; fold={result.fold}; tag={result.tag}; extra={result.extra}")
    result=value.to_month(1)
    print("  Calendar result retains child type:",type(result).__name__)


def selection_demo():
    """Distinguish omitted fields, clock zero and strict explicit creation."""
    value=PydtR(2024,1,31,12,30)
    print("\nNone keeps the hour:",value.to_time(hour=None) is value)
    print("Zero sets midnight hour:",value.to_time(hour=0))
    print("Month-end date adjustment:",value.to_date(month=2,day=31))
    print("Timezone names in replace:",value.replace(tzinfo="Asia/Shanghai"))
    for operation in (lambda:PydtR(2024,3,10,2,30,tzinfo="America/New_York"),
                      lambda:PydtR(2024,3,10,1,30,tzinfo="America/New_York").replace(hour=2)):
        try:operation()
        except ValueError as error:print("Expected missing-time error:",error)
        else:raise AssertionError("An explicit missing time must be rejected")


def snap_demo():
    """Show calendar names, later ties and real repeated-time distances."""
    value=PydtR(2024,6,15,12,30)
    for unit in ("Y","Q","M","W","D","h","min","s","ms","us","Friday","April"):
        print(f"  Rust snap({unit!r}):",value.snap(unit))
    repeated=PydtR(2024,11,3,1,50,tzinfo="America/New_York",fold=0)
    result=repeated.snap("h")
    print("  Repeated hour:",result,"fold=",result.fold)
    assert (result.hour,result.minute,result.fold)==(1,0,1)



def current_time_demo():
    """Ask whether ordinary naive and regional values are before or after now."""
    for zone in (None, ZoneInfo("America/New_York")):
        _show(f"Past query, tz={zone}",
              lambda cls: cls(2000, 5, 7, 12, tzinfo=zone).is_past())
        _show(f"Future query, tz={zone}",
              lambda cls: cls(2090, 5, 7, 12, tzinfo=zone).is_future())
    print("  Rust regional queries compare real instants, including repeated hours.")


def all_demo():
    """Run all representative groups under the selected adopted artifact."""
    print(f"rsTimes {version('rstimes')} | {_native.__file__}")
    print("Timings are demo observations; approved differences are labelled.")
    for function in (constructor_demo,fields_demo,calendar_demo,period_demo,precision_demo,
                     timezone_demo,arithmetic_demo,standard_datetime_demo,parse_demo,state_demo,selection_demo,snap_demo,current_time_demo):
        print(f"\n=== {function.__name__} ===")
        function()


if __name__=="__main__":
    all_demo()
