"""Prepare complete static frequency metadata for the native range generator."""
from datetime import timedelta,timezone
from zoneinfo import ZoneInfo
import sys
import re
import numpy as np
from ._optional import PANDAS as pd
from ._native import _pddt_frequency
from .errors import _own_error, _external_error

_MONTHS = {name: i for i, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
_WEEKDAYS = {name: i for i, name in enumerate(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"))}
_SIMPLE = re.compile(r"^([+-]?\d*)\s*([A-Za-z]+)(?:-([A-Za-z0-9-]+))?$")
_FIXED_PART = re.compile(r"(\d+(?:\.\d*)?|\.\d+)\s*(min|ms|us|ns|D|h|s)")
_SCALES = {"D": 86400_000_000_000, "h": 3600_000_000_000,
           "min": 60_000_000_000, "s": 1_000_000_000,
           "ms": 1_000_000, "us": 1000, "ns": 1}

_INVALID_METADATA=(ValueError,)
if pd is not None:
    # pandas2 already owns these actual optional backend exception types.
    # Do not import or require pytz in a pandas3 environment.
    _pytz_errors=sys.modules.get("pytz.exceptions")
    if _pytz_errors is not None:
        _INVALID_METADATA+=tuple(getattr(_pytz_errors,name) for name in
            ("AmbiguousTimeError","NonExistentTimeError"))
    _o = pd.offsets
    # Keys are actual classes, never the operand's class/module display name.
    _NATIVE = {
        _o.Nano: ("fixed", 1), _o.Micro: ("fixed", 1000),
        _o.Milli: ("fixed", 1_000_000), _o.Second: ("fixed", 1_000_000_000),
        _o.Minute: ("fixed", 60_000_000_000), _o.Hour: ("fixed", 3600_000_000_000),
        _o.Day: ("days", None), _o.Week: ("week", None),
        _o.BusinessDay: ("business", None), _o.CustomBusinessDay: ("business", None),
        _o.MonthBegin: ("boundary", (1, True, False)),
        _o.MonthEnd: ("boundary", (1, False, False)),
        _o.QuarterBegin: ("boundary", (3, True, False)),
        _o.QuarterEnd: ("boundary", (3, False, False)),
        _o.YearBegin: ("boundary", (12, True, False)),
        _o.YearEnd: ("boundary", (12, False, False)),
        _o.BusinessMonthBegin: ("boundary", (1, True, True)),
        _o.BusinessMonthEnd: ("boundary", (1, False, True)),
        _o.BQuarterBegin: ("boundary", (3, True, True)),
        _o.BQuarterEnd: ("boundary", (3, False, True)),
        _o.BYearBegin: ("boundary", (12, True, True)),
        _o.BYearEnd: ("boundary", (12, False, True)),
        _o.CustomBusinessMonthBegin: ("boundary", (1, True, True)),
        _o.CustomBusinessMonthEnd: ("boundary", (1, False, True)),
        _o.SemiMonthBegin: ("semi", True), _o.SemiMonthEnd: ("semi", False),
        _o.WeekOfMonth: ("wom", False), _o.LastWeekOfMonth: ("wom", True),
    }
    _METADATA = {*_NATIVE, _o.DateOffset, _o.BusinessHour, _o.CustomBusinessHour, _o.FY5253, _o.FY5253Quarter}
    _CODES = {
        "D": _o.Day, "B": _o.BusinessDay, "C": _o.CustomBusinessDay,
        "MS": _o.MonthBegin, "ME": _o.MonthEnd,
        "QS": _o.QuarterBegin, "QE": _o.QuarterEnd,
        "YS": _o.YearBegin, "YE": _o.YearEnd,
        "BMS": _o.BusinessMonthBegin, "BME": _o.BusinessMonthEnd,
        "BQS": _o.BQuarterBegin, "BQE": _o.BQuarterEnd,
        "BYS": _o.BYearBegin, "BYE": _o.BYearEnd,
        "CBMS": _o.CustomBusinessMonthBegin, "CBME": _o.CustomBusinessMonthEnd,
        "SMS": _o.SemiMonthBegin, "SME": _o.SemiMonthEnd,
        "bh": _o.BusinessHour, "cbh": _o.CustomBusinessHour,
    }


def _metadata_fixed(step, minimum=None):
    """Optional pandas frequency metadata must not narrow the native value range."""
    for scale, cls in ((3600_000_000_000, _o.Hour), (60_000_000_000, _o.Minute),
                       (1_000_000_000, _o.Second), (1_000_000, _o.Milli),
                       (1000, _o.Micro), (1, _o.Nano)):
        if minimum is not None and scale > _SCALES[minimum]:
            continue
        if step % scale == 0:
            try:
                return cls(step // scale)
            except OverflowError:
                return None


def _from_string(value):
    """Use one 3.x vocabulary on pandas2 as well; removed aliases stay removed."""
    text = value.strip()
    sign = -1 if text.startswith("-") else 1
    unsigned = text[1:] if text.startswith(("-", "+")) else text
    parts = list(_FIXED_PART.finditer(unsigned))
    if parts and "".join(m.group(0).replace(" ", "") for m in parts) == unsigned.replace(" ", ""):
        if len(parts) == 1 and parts[0].group(2) == "D":
            whole, _, fraction = parts[0].group(1).partition(".")
            numerator = int((whole or "0") + fraction)
            denominator = 10 ** len(fraction)
            if numerator % denominator == 0:
                return _o.Day(sign * (numerator // denominator)), None
        # Explicit decimal coefficients use exact integer scaling.
        total = 0
        for part in parts:
            coefficient, unit = part.groups()
            whole, _, fraction = coefficient.partition(".")
            numerator = int((whole or "0") + fraction)
            denominator = 10 ** len(fraction)
            scaled, remainder = divmod(numerator * _SCALES[unit], denominator)
            if remainder:
                raise _own_error(ValueError("frequency is finer than one nanosecond"), "freq", value)
            total += scaled
        minimum = min((m.group(2) for m in parts), key=_SCALES.__getitem__)
        return _metadata_fixed(sign * total, minimum), sign * total
    match = _SIMPLE.fullmatch(text)
    if match:
        number, code, anchor = match.groups()
        n = -1 if number == "-" else 1 if number in ("", "+") else int(number)
        if code in ("h", "min", "s", "ms", "us", "ns") and anchor is None:
            step = n * _SCALES[code]
            return _metadata_fixed(step, code), step
        if code == "W":
            weekday = 6 if anchor is None else _WEEKDAYS.get(anchor)
            if weekday is None:
                raise _own_error(ValueError("weekly frequency requires MON through SUN"), "freq", value)
            return _o.Week(n, weekday=weekday), None
        if code in ("WOM", "LWOM") and anchor is not None:
            if code == "WOM" and len(anchor) == 4 and anchor[0] in "1234" and anchor[1:] in _WEEKDAYS:
                return _o.WeekOfMonth(n, week=int(anchor[0])-1, weekday=_WEEKDAYS[anchor[1:]]), None
            if code == "LWOM" and anchor in _WEEKDAYS:
                return _o.LastWeekOfMonth(n, weekday=_WEEKDAYS[anchor]), None
        if code in _CODES:
            kwargs = {}
            if code in ("QS", "QE", "BQS", "BQE"):
                month = _MONTHS.get(anchor, None) if anchor is not None else (1 if code.endswith("S") else 12)
                if month is None:
                    raise _own_error(ValueError("quarter frequency needs a JAN through DEC anchor"), "freq", value)
                kwargs["startingMonth"] = month
            elif code in ("YS", "YE", "BYS", "BYE"):
                month = _MONTHS.get(anchor, None) if anchor is not None else (1 if code.endswith("S") else 12)
                if month is None:
                    raise _own_error(ValueError("annual frequency needs a JAN through DEC anchor"), "freq", value)
                kwargs["month"] = month
            elif code in ("SMS", "SME") and anchor is not None:
                if not anchor.isascii() or not anchor.isdecimal():
                    raise _own_error(ValueError("semi-month frequency needs a numeric day anchor"), "freq", value)
                kwargs["day_of_month"] = int(anchor)
            elif anchor is not None:
                raise _own_error(ValueError("this frequency does not accept an anchor"), "freq", value)
            return _CODES[code](n, **kwargs), None
        if code in ("RE", "REQ"):
            # Explicitly approved special fiscal Offset; pandas executes it.
            try:
                return pd.tseries.frequencies.to_offset(text), None
            except Exception as error:
                raise _external_error(error)
    raise _own_error(ValueError(
        "unsupported frequency; use current names such as '15min', 'ME', 'QS-JAN', "
        "or a pandas DateOffset object for a custom rule"
    ), "freq", value)


def frequency(value):
    """Return a native plan, optional original metadata and a delegate flag."""
    if value is None:
        return None, None, False
    if isinstance(value, str):
        if type(value) is not str:
            try:
                value = str(value)
            except Exception as error:
                raise _external_error(error)
        offset, step = _from_string(value)
        if step is not None:
            precision = "s"
            if type(offset) is _o.Nano:
                precision = "ns"
            elif type(offset) is _o.Micro:
                precision = "us"
            elif type(offset) is _o.Milli:
                precision = "ms"
            return _pddt_frequency("fixed", 1 if step > 0 else -1, {"tick": step, "precision": precision}), offset, False
    elif isinstance(value, timedelta):
        plan = _pddt_frequency("duration", 1, {"duration": value})
        return plan, _metadata_fixed(plan.tick), False
    elif isinstance(value, _o.DateOffset):
        offset = value
    else:
        raise _own_error(TypeError("must be a frequency string, timedelta or pandas DateOffset"), "freq", value)
    spec = _NATIVE.get(type(offset))
    if spec is None:
        # Genuine custom callbacks and extra general/fiscal/business-hour semantics
        # stay wholly with the mature executor, with their original parameters.
        return None, offset, True
    kind, detail = spec
    props = {"normalize": offset.normalize}
    kwargs = offset.kwds
    if kind == "fixed":
        props["tick"] = offset.n * detail
        props["precision"] = {1:"ns",1000:"us",1_000_000:"ms"}.get(detail,"s")
    elif kind == "week":
        props["weekday"] = kwargs.get("weekday")
    elif kind == "boundary":
        stride, start, business = detail
        props.update(stride=stride, start=start, business=business,
            anchor=kwargs["startingMonth"] if stride == 3 else kwargs["month"] if stride == 12 else 1)
    elif kind == "semi":
        props.update(start=detail, day=kwargs["day_of_month"])
    elif kind == "wom":
        props.update(last=detail, weekday=kwargs["weekday"], week=0 if detail else kwargs["week"])
    calendar = kwargs.get("calendar")
    if calendar is not None:
        if type(calendar) is not np.busdaycalendar:
            return None, offset, True
        props["mask"] = calendar.weekmask.astype("uint8").tobytes()
        props["holidays"] = calendar.holidays.view("int64").tobytes()
    if "offset" in kwargs:
        props["duration"] = kwargs["offset"]
    return _pddt_frequency(kind, offset.n, props), offset, False


def attach_frequency(array, metadata):
    """Retain a standard frequency only when public pandas validation agrees.

    Localization may make a regular wall sequence irregular. A failed metadata
    validation does not invalidate its correctly computed date values. Genuine
    custom callback rules are not executed again just to recover metadata.
    """
    if metadata is None or type(metadata) not in _METADATA:
        return
    if array.tz is not None and type(array.tz) not in (timezone,ZoneInfo):
        # Do not run arbitrary timezone callbacks again just for optional freq.
        return
    try:
        array.freq = metadata
    except _INVALID_METADATA:
        # This path is limited to exact mature built-in frequency classes;
        # arbitrary subclass callback failures are never swallowed here.
        return
    except Exception as error:
        raise _external_error(error)


def rounding_step(value):
    """Read a positive fixed rounding grid, retaining the current vocabulary."""
    plan, metadata, delegated = frequency(value)
    if type(metadata) is _o.Day:
        step=metadata.n*_SCALES["D"]
    else:
        step=None if plan is None else plan.tick
    if delegated or step is None or step<=0:
        raise _own_error(ValueError("rounding requires a positive fixed frequency, such as '15min', 'h' or 'D'"),"freq",value)
    return step


def mature_units(metadata,source):
    """Separate a mature engine's working precision from its initial output unit."""
    if type(metadata) not in _METADATA:
        return None,None
    units=('s','ms','us','ns')
    index=units.index(source)
    kwargs=metadata.kwds
    generic=type(metadata) is _o.DateOffset
    business=type(metadata) in (_o.BusinessHour,_o.CustomBusinessHour)
    if any(key in kwargs for key in ('nanosecond','nanoseconds')):
        index=3
    elif business or any(key in kwargs for key in ('microsecond','microseconds')):
        index=max(index,2)
    offset=kwargs.get('offset')
    if isinstance(offset,pd.Timedelta):
        index=max(index,units.index(offset.unit))
    # DateOffset may use fractional seconds without an explicit microsecond key.
    # Generate those with at least us, then the native finalizer keeps exact output.
    return units[max(index,2) if generic or business else index],units[index]
