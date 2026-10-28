"""Shared, deterministic inputs for the frozen Delta and installed candidate.

Add a rule here when its implementation slice starts; this file is not a copy
of the upstream probe or an unlimited random-input generator.
"""
from datetime import date, datetime, timedelta, timezone
from importlib import import_module
from typing import NamedTuple

FIELDS = (
    "years", "months", "days", "hours", "minutes", "seconds", "microseconds",
    "year", "month", "day", "weekday", "hour", "minute", "second", "microsecond",
)
PARAMETERS = (
    "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds",
    "milliseconds", "microseconds", "year", "month", "day", "weekday", "hour",
    "minute", "second", "millisecond", "microsecond",
)


class Case(NamedTuple):
    """One deterministic operation with stable identity and requirement links.

    run is a zero-argument workload callable. difference identifies an approved
    migration policy; it never authorizes arbitrary result mismatches.
    """
    id: str
    group: str
    requirements: tuple[str, ...]
    run: object
    difference: str | None = None


def type_name(value):
    """Return a stable qualified type name with the approved package-name mapping."""
    cls = type(value)
    name = f"{cls.__module__}.{cls.__qualname__}"
    if name == "cytimes.delta.Delta":
        return "rstimes.delta.Delta"
    if cls.__module__ == "cytimes.errors":
        return f"rstimes.errors.{cls.__qualname__}"
    return name


def pack(value, Delta):
    """Record values and types, never a process-specific memory address."""
    if isinstance(value, Delta):
        return {"type": type_name(value), "fields": {k: getattr(value, k) for k in FIELDS}}
    if isinstance(value, datetime):
        return {"type": type_name(value), "iso": value.isoformat(), "fold": value.fold,
                "tz": str(value.tzinfo), "tz_key": getattr(value.tzinfo, "key", None)}
    if isinstance(value, date):
        return {"type": type_name(value), "iso": value.isoformat()}
    if isinstance(value, timedelta):
        return {"type": type_name(value), "fields": [value.days, value.seconds, value.microseconds]}
    if isinstance(value, (tuple, list)):
        return {"type": type_name(value), "items": [pack(x, Delta) for x in value]}
    if isinstance(value, dict):
        return {"type": type_name(value), "items": {str(k): pack(v, Delta) for k, v in value.items()}}
    if value is NotImplemented:
        return {"type": type_name(value), "value": "NotImplemented"}
    if value is None or isinstance(value, (bool, int, float, str)):
        return {"type": type_name(value), "value": value}
    return {"type": type_name(value)}


def error_record(error):
    """Serialize exception type, message and explicit cause without memory addresses."""
    return {"type": type_name(error), "message": str(error),
            "cause": None if error.__cause__ is None else error_record(error.__cause__)}


def observe(case, Delta):
    """Execute a case and record either its structured result or exception chain."""
    try:
        return {"case": case.id, "requirements": case.requirements, "difference": case.difference,
                "result": pack(case.run(), Delta)}
    except Exception as error:
        return {"case": case.id, "requirements": case.requirements, "difference": case.difference,
                "error": error_record(error)}


def date_fixtures():
    """Return fixed calendar, timezone and subtype inputs shared by parity and timing."""
    from zoneinfo import ZoneInfo
    calendar_inputs = [
        ("1900-not-leap", date(1900, 1, 31), dict(months=1)),
        ("2000-leap", date(2000, 1, 31), dict(months=1)),
        ("year-one", date(1, 1, 1), dict()),
        ("year-last", date(9999, 12, 31), dict()),
        ("negative-month", date(2024, 1, 31), dict(months=-1)),
        ("cross-year", date(2024, 12, 31), dict(months=1)),
        ("clamp-before-day", date(2024, 1, 31), dict(months=1, days=1)),
        ("weekday-same-week", date(2024, 3, 3), dict(weekday=0)),
        ("temporary-year-zero", date(1, 1, 1), dict(years=-1, days=366)),
        ("temporary-year-10000", date(9999, 12, 31), dict(years=1, days=-366)),
        ("negative-days", date(2000, 3, 1), dict(days=-1)),
    ]
    date_inputs = calendar_inputs + [
        ("clamp-equal-new", date(2023, 2, 28), dict(day=31)),
        ("all-replacements", date(2024, 1, 31), dict(year=2023, month=2, day=31, days=1)),
        ("positive-us", date(2024, 3, 1), dict(microseconds=1)),
        ("negative-us", date(2024, 3, 1), dict(microseconds=-1)),
        ("negative-time", date(2024, 3, 1), dict(hours=-25)),
        ("absolute-time", date(2024, 3, 1), dict(hour=23, minute=59, second=59, microseconds=1)),
        ("year-zero-error", date(1, 1, 1), dict(years=-1)),
        ("year-10000-error", date(9999, 12, 31), dict(days=1)),
    ]
    ny = ZoneInfo("America/New_York")
    datetime_inputs = [
        ("clamp-equal-new", datetime(2023,2,28), dict(day=31)),
        ("month-end", datetime(2024,1,31,23,30), dict(months=1,hours=2)),
        ("us-before", datetime(2024,3,1), dict(microseconds=-1)),
        ("us-after", datetime(2024,2,29,23,59,59,999999), dict(microseconds=1)),
        ("absolute-time", datetime(2024,1,1,1,2,3,4), dict(hour=0,minute=0,second=0,microsecond=0)),
        ("combined", datetime(2024,1,31,23,59,59,999999), dict(year=2023,month=2,day=31,weekday=0,microseconds=1)),
        ("utc", datetime(2024,1,31,23,30,tzinfo=timezone.utc), dict(months=1,hours=2)),
        ("ny-gap", datetime(2024,3,10,1,30,tzinfo=ny), dict(hours=1)),
        ("ny-fold", datetime(2024,11,3,1,30,tzinfo=ny,fold=1), dict(minutes=1)),
        ("ny-unchanged", datetime(2024,11,3,1,30,tzinfo=ny,fold=1), dict()),
        ("year-one", datetime(1,1,1), dict()),
        ("year-last", datetime(9999,12,31,23,59,59,999999), dict()),
        ("year-zero-error", datetime(1,1,1), dict(microseconds=-1)),
        ("year-10000-error", datetime(9999,12,31,23,59,59,999999), dict(microseconds=1)),
    ]
    return calendar_inputs, date_inputs, datetime_inputs


def cases(package):
    """Build deterministic common cases for an installed package's Delta class.

    Returns:
        tuple: Delta type and ordered Case records with requirement IDs and any
            approved difference policy. Callable closures execute the real operations."""
    Delta = import_module(package).Delta
    class Child(Delta):
        pass
    Child.__qualname__ = "Child"
    globals()["Child"] = Child
    class IntInput:
        def __int__(self): return 4
    class IndexInput:
        def __index__(self): return 3
    class BadInt:
        def __int__(self): return "bad"
    class RaisesInt:
        def __int__(self): raise ValueError("conversion failed")

    def datetime_observation():
        original = datetime(2024, 1, 31, 23, 30, tzinfo=timezone.utc)
        result = original + Delta(months=1, hours=2)
        return {"result": result, "is_input": result is original,
                "tz_is_input": result.tzinfo is original.tzinfo}

    def reinitialize():
        original = Delta(days=1)
        same = original
        returned = original.__init__(days=2)
        return {"value": original, "same_object": original is same, "returned": returned}

    def child_storage():
        child = Child(days=1)
        child.extra = "kept"
        return {"value": child, "dict": child.__dict__}

    def failed_reinitialization():
        value = Delta(days=2, year=2024)
        try:
            value.__init__(days=None)
        except Exception as error:
            return {"value": value, "error": error_record(error)}
        return {"value": value, "error": None}

    def remove_days():
        value = Delta()
        del value.days

    property_value = Delta(years=1, months=-13, days=1, hours=-25, microseconds=-1,
                           year=2024, month=2, day=29, weekday=0, hour=0, minute=0, second=0, microsecond=0)

    records = [
        Case("selfcheck:construct", "selfcheck", ("A03", "A10", "B01", "B15"),
             lambda: Delta(months=-1, microseconds=-1)),
        Case("selfcheck:datetime", "selfcheck", ("K02", "M03"),
             datetime_observation),
        Case("selfcheck:error", "selfcheck", ("K09",), lambda: Delta(days=None)),
        Case("allocation:raw", "allocation", ("G01",), lambda: Delta.__new__(Delta)),
        Case("allocation:raw-args", "allocation", ("G01",), lambda: Delta.__new__(Delta, years=2)),
        Case("allocation:normal", "allocation", ("M01",), lambda: Delta()),
        Case("allocation:reinit", "allocation", ("M01", "H04"), reinitialize),
        Case("allocation:storage", "allocation", ("H04",),
             lambda: (hasattr(Delta(), "__dict__"), hasattr(Delta(), "__weakref__"))),
        Case("allocation:child", "allocation", ("H04",), child_storage),
        Case("allocation:module", "allocation", ("H04",),
             lambda: (Delta.__module__ == package + ".delta",
                      Delta is import_module(package + ".delta").Delta)),
        Case("properties:all", "properties-init", tuple(f"B{i:02d}" for i in range(1,16)),
             lambda: tuple(getattr(property_value, name) for name in FIELDS)),
        Case("properties:types", "properties-init", tuple(f"B{i:02d}" for i in range(1,16)),
             lambda: tuple(type_name(getattr(property_value, name)) for name in FIELDS)),
        Case("properties:write", "properties-init", ("B03",), lambda: setattr(Delta(), "days", 2)),
        Case("properties:delete", "properties-init", ("B03",), remove_days),
        Case("properties:private", "properties-init", ("H04",), lambda: getattr(Delta(), "_days")),
        Case("properties:failure-state", "properties-init", ("M01",), failed_reinitialization),
        Case("properties:reinit", "properties-init", ("M01",), reinitialize),
        Case("properties:raw", "properties-init", ("G01",), lambda: Delta.__new__(Delta)),
        Case("properties:bool-empty", "properties-init", ("M10",), lambda: bool(Delta())),
        Case("properties:bool-absolute-zero", "properties-init", ("M10",), lambda: bool(Delta(second=0))),
        Case("properties:bool-cancel", "properties-init", ("M10",), lambda: bool(Delta(days=1, hours=-24))),
        Case("properties:immutable-type", "properties-init", ("H04",),
             lambda: setattr(Delta, "_rs_probe", 1)),
    ]
    from decimal import Decimal
    from fractions import Fraction
    import numpy as np
    numeric_values = [("bool", True), ("float", -1.9), ("int", IntInput()),
                      ("index", IndexInput()), ("none", None), ("string", "2"),
                      ("numpy", np.int64(2))]
    for index, parameter in enumerate(PARAMETERS):
        requirement = (f"A{index+1:02d}", "K09")
        for label, value in numeric_values:
            records.append(Case(f"coercion:{parameter}:{label}", "coercion", requirement,
                                lambda parameter=parameter, value=value: Delta(**{parameter: value})))
        bits = 32 if index < 4 or index >= 10 else 64
        for label, value in [("over", 2**(bits-1)), ("under", -2**(bits-1)-1)]:
            records.append(Case(f"coercion:{parameter}:{label}", "coercion", requirement,
                                lambda parameter=parameter, value=value: Delta(**{parameter: value})))
    for parameter in ("years", "days"):
        for label, value in [("nan", float("nan")), ("inf", float("inf")),
                             ("decimal", Decimal("1.9")), ("fraction", Fraction(-19, 10)),
                             ("bad-int", BadInt()), ("raises-int", RaisesInt())]:
            records.append(Case(f"coercion:{parameter}:{label}", "coercion", ("K09",),
                                lambda parameter=parameter, value=value: Delta(**{parameter: value})))
    for parameter, bits in [("years", 32), ("days", 64), ("hours", 64), ("microseconds", 64)]:
        for label, value in [("max", 2**(bits-1)-1), ("min", -2**(bits-1))]:
            records.append(Case(f"coercion:{parameter}:{label}", "coercion", ("K09",),
                                lambda parameter=parameter, value=value: Delta(**{parameter: value})))
    records.extend([
        Case("coercion:positional", "coercion", ("A04", "A05"), lambda: Delta(0, 0, 0, 2, 3)),
        Case("coercion:unknown", "coercion", ("M01",), lambda: Delta(foo=1)),
        Case("coercion:too-many", "coercion", ("M01",), lambda: Delta(*range(20))),
        Case("coercion:duplicate", "coercion", ("M01",), lambda: Delta(1, years=1)),
    ])
    relatives = [
        ("zero", {}), ("month-negative", {"months": -1}), ("us-negative", {"microseconds": -1}),
        ("quarter-cancel", {"quarters": 1, "months": -3}),
        ("days-cancel", {"days": 1, "hours": -24}),
        ("weeks-days", {"weeks": 2, "days": 3}),
        ("millisecond", {"milliseconds": -1}),
        ("mixed", {"years": 1, "months": -13, "days": 1, "hours": -25, "microseconds": -1}),
        ("carry", {"microseconds": 1_000_000, "seconds": 59, "minutes": 59, "hours": 23}),
    ]
    for label, values in relatives:
        records.append(Case(f"relative:{label}", "relative", ("A01", "A10"), lambda values=values: Delta(**values)))
    overflows = [
        ("years", {"years": 2**31-1, "months": 12}),
        ("quarters", {"quarters": 2**31-1}),
        ("weeks", {"weeks": 2**31-1}),
        ("days", {"days": 2**63-1, "hours": 24}),
        ("milliseconds", {"milliseconds": 2**63-1}),
        ("us-addition", {"microseconds": 2**63-1, "milliseconds": 1}),
        ("negative-years", {"years": -2**31, "months": -1}),
        ("negative-quarters", {"quarters": -2**31}),
        ("negative-weeks", {"weeks": -2**31}),
        ("negative-milliseconds", {"milliseconds": -2**63}),
    ]
    for label, values in overflows:
        records.append(Case(f"relative:overflow:{label}", "relative", ("A01", "A10"),
                            lambda values=values: Delta(**values), "D1"))
    absolutes = [
        ("defaults", {}),
        ("zeros", dict(year=0, month=0, day=0, weekday=0, hour=0, minute=0, second=0, microsecond=0)),
        ("clamps", dict(year=10000, month=13, day=32, weekday=7, hour=24, minute=60, second=60, microsecond=1000000)),
        ("negative", dict(year=-2, month=-2, day=-2, weekday=-2, hour=-2, minute=-2, second=-2, microsecond=-2)),
    ]
    for ms, us in [(-1, -1), (-1, 0), (-1, 1000001), (0, -1), (0, 0), (2, 123456), (1000, 1000001)]:
        absolutes.append((f"ms-us:{ms}:{us}", {"millisecond": ms, "microsecond": us}))
    for label, values in absolutes:
        records.append(Case(f"absolute:{label}", "absolute", tuple(f"A{i:02d}" for i in range(11,20)) + ("K04",), lambda values=values: Delta(**values)))
    calendar_inputs, date_inputs, datetime_inputs = date_fixtures()
    ny = next(value.tzinfo for label,value,_ in datetime_inputs if label=="ny-fold")
    def applied(original, values, operation):
        delta = Delta(**values)
        if operation == "add": result = original + delta
        elif operation == "radd": result = delta + original
        elif operation == "sub": result = original - delta
        elif operation == "method-add": result = delta.__add__(original)
        elif operation == "method-radd": result = delta.__radd__(original)
        else: result = delta.__rsub__(original)
        return {"result": result, "is_input": result is original,
                "tz_is_input": not isinstance(original, datetime) or result.tzinfo is original.tzinfo}
    for label, original, values in calendar_inputs:
        records.append(Case("calendar:"+label, "calendar-core", ("K03",),
                            lambda original=original, values=values: applied(original, values, "add")))
    for label, original, values in date_inputs:
        for operation in ("add", "radd", "sub", "method-add", "method-radd", "method-sub"):
            records.append(Case(f"date:{label}:{operation}", "date", ("K01", "K03", "M03", "M04", "M06"),
                                lambda original=original, values=values, operation=operation: applied(original, values, operation)))
    for label, original, values in datetime_inputs:
        for operation in ("add", "radd", "sub", "method-add", "method-radd", "method-sub"):
            records.append(Case(f"datetime:{label}:{operation}", "datetime", ("K02", "K03", "M03", "M04", "M06"),
                                lambda original=original, values=values, operation=operation: applied(original, values, operation)))
    class DateChild(date): pass
    class DateTimeChild(datetime): pass
    class RejectDate(date):
        def __new__(cls, *args, **kwargs):
            if kwargs: raise RuntimeError("date constructor refused")
            return super().__new__(cls, *args)
    class RejectDateTime(datetime):
        def __new__(cls, *args, **kwargs):
            if kwargs: raise RuntimeError("datetime constructor refused")
            return super().__new__(cls, *args)
    for cls in (DateChild, DateTimeChild, RejectDate, RejectDateTime):
        original = cls(2024,1,31)
        for label, values in (("same", {}), ("changed", {"months":1}), ("invalid", {"years":-2024})):
            records.append(Case(f"date-subclass:{cls.__name__}:{label}", "date-subclass", ("K01", "K02", "K03", "K09"),
                                lambda original=original, values=values: applied(original, values, "add")))
    relative_pairs = [
        ("positive", dict(years=1,months=2,days=3,hours=4,minutes=5,seconds=6,microseconds=7), dict(months=11,hours=23,microseconds=999999)),
        ("negative", dict(months=-1,microseconds=-1), dict(months=-13,seconds=-61)),
        ("cancel", dict(years=1,days=1), dict(years=-1,days=-1)),
        ("child", dict(days=1), dict(hours=2)),
    ]
    for label, left_values, right_values in relative_pairs:
        left = (Child if label=="child" else Delta)(**left_values); right = Delta(**right_values)
        for operation in ("add", "sub"):
            records.append(Case(f"delta-arithmetic:{label}:{operation}", "delta-arithmetic", ("M03", "M05"),
                                lambda left=left,right=right,operation=operation: left+right if operation=="add" else left-right))
    for name in FIELDS[7:]:
        for label,left_value,right_value in [("both",2,3),("left",2,-1),("right",-1,3),("zero",-1,0)]:
            left = Delta(**{name:left_value}); right = Delta(**{name:right_value})
            for operation in ("add","sub"):
                records.append(Case(f"delta-arithmetic:{name}:{label}:{operation}", "delta-arithmetic", ("M03","M05"),
                                    lambda left=left,right=right,operation=operation: left+right if operation=="add" else left-right))
    for label, left, right, operation in [
        ("add-years",Delta(years=2**31-1),Delta(years=1),"add"),
        ("sub-years",Delta(years=-2**31),Delta(years=1),"sub"),
        ("add-days",Delta(days=2**63-1),Delta(days=1),"add"),
        ("sub-days",Delta(days=-2**63),Delta(days=1),"sub")]:
        records.append(Case("delta-arithmetic:overflow:"+label,"delta-arithmetic",("M03","M05","K09"),
                            lambda left=left,right=right,operation=operation: left+right if operation=="add" else left-right,"D1"))
    duration_inputs = [("positive",timedelta(days=3,seconds=4,microseconds=5)),
                       ("negative-us",timedelta(microseconds=-1)),
                       ("negative-day",timedelta(days=-1,seconds=1)),
                       ("maximum",timedelta.max)]
    def duration_apply(delta, duration, op):
        if op=="add": return delta+duration
        if op=="radd": return duration+delta
        if op=="sub": return delta-duration
        if op=="rsub": return duration-delta
        return getattr(delta,"__"+op[7:]+"__")(duration)
    for label,duration in duration_inputs:
        for setting,delta in [("relative",Delta(months=-1,microseconds=-1)),
                              ("absolute",Delta(days=1,year=2024,weekday=0,hour=0))]:
            for op in ("add","radd","sub","rsub","method-add","method-radd","method-sub","method-rsub"):
                records.append(Case(f"timedelta:{label}:{setting}:{op}","timedelta",("M03","M04","M05","M06"),
                                    lambda delta=delta,duration=duration,op=op: duration_apply(delta,duration,op)))
    for label,values in [("negative-month",dict(months=-1)),("negative-us",dict(microseconds=-1)),
                         ("opposite-signs",dict(months=-1,days=1)),("absolute",dict(months=-1,microseconds=-1,year=2024,hour=0))]:
        for op in ("neg","abs"):
            value=Child(**values)
            records.append(Case(f"unary:{label}:{op}","unary",("M07","M08"),lambda value=value,op=op: -value if op=="neg" else abs(value)))
    for name,minimum in [("years",-2**31),("days",-2**63)]:
        for op in ("neg","abs"):
            value=Delta(**{name:minimum})
            records.append(Case(f"unary:overflow:{name}:{op}","unary",("M07","M08","K09"),lambda value=value,op=op: -value if op=="neg" else abs(value),"D1"))
    class Reflect:
        def __radd__(self,other):return "reflected addition"
        def __rsub__(self,other):return "reflected subtraction"
        def __add__(self,other):return NotImplemented
        def __sub__(self,other):return NotImplemented
    for name,value in [("int",3),("none",None),("reflect",Reflect()),("delta",Delta(days=1)),("date",date(2024,1,1))]:
        for method in ("__add__","__radd__","__sub__","__rsub__"):
            records.append(Case(f"dispatch:{name}:{method}","dispatch",("K05","M03","M04","M05","M06"),
                                lambda method=method,value=value:getattr(Delta(),method)(value)))
    records.extend([
        Case("dispatch:reflect-expression:add","dispatch",("K05",),lambda:Delta()+Reflect()),
        Case("dispatch:reflect-expression:sub","dispatch",("K05",),lambda:Delta()-Reflect()),
    ])
    for method in ("__add__","__radd__","__sub__","__rsub__"):
        records.append(Case("dispatch:keyword:"+method,"dispatch",("K05",),lambda method=method:getattr(Delta(),method)(o=3)))
    for method in ("__add__","__radd__","__sub__","__rsub__"):
        for label,other in (("delta",Delta(days=1)),("duration",timedelta(microseconds=-1))):
            records.append(Case(f"dispatch:class-call:{method}:{label}","dispatch",("K05",),
                                lambda method=method,other=other:getattr(Delta,method)(Delta(),other)))
    from dateutil.relativedelta import relativedelta, MO, SU
    rd_inputs = [
        ("integer",relativedelta(years=1,months=-13,days=2,hours=-25,microseconds=-1)),
        ("fraction",relativedelta(days=-1.5,hours=2.25,minutes=-1.5,seconds=1.25,microseconds=1.5)),
        ("absolute",relativedelta(year=2024,month=2,day=31,hour=0,minute=0,second=0,microsecond=0)),
        ("weekday-n",relativedelta(weekday=MO(2))),
        ("weekday-negative",relativedelta(weekday=SU(-2))),
        ("leapdays",relativedelta(years=1,leapdays=1)),
    ]
    for label,rd in rd_inputs:
        for cls in (Delta,Child):
            records.append(Case(f"dateutil:from:{label}:{cls.__name__}","dateutil",("M02","K08"),lambda rd=rd,cls=cls:cls.from_relativedelta(rd)))
        delta=Delta(months=-1,days=1,year=2023,weekday=0,hour=2)
        for op in ("add","radd","sub","rsub","method-add","method-radd","method-sub","method-rsub"):
            records.append(Case(f"dateutil:arithmetic:{label}:{op}","dateutil",("M03","M04","M05","M06","K08"),
                                lambda rd=rd,delta=delta,op=op:duration_apply(delta,rd,op)))
    for label,rd in (("none",None),("int",3),("string","rd"),("delta",Delta())):
        records.append(Case("dateutil:invalid:"+label,"dateutil",("M02","K08"),lambda rd=rd:Delta.from_relativedelta(rd)))
    class RaisesRelativeDelta(relativedelta):
        def normalized(self):raise ValueError("normalized callback failed")
    class EmptyRelativeDelta(relativedelta):
        def normalized(self):return None
    for cls in (RaisesRelativeDelta,EmptyRelativeDelta):
        records.append(Case("dateutil:callback:"+cls.__name__,"dateutil",("M02","K08"),lambda cls=cls:Delta.from_relativedelta(cls())))
    def relative_error_shape():
        errors=import_module(package+".errors")
        if package == "cytimes":
            return [issubclass(errors.InvalidRelativeDelta,parent) for parent in
                    (TypeError,errors.DeltaError,errors.cyTimesTypeError,errors.cyTimesError,Exception)]
        # Standard argument errors are deliberately outside the three domain classes.
        try:
            Delta.from_relativedelta(object())
        except TypeError as error:
            return [type(error) is TypeError, isinstance(error, Exception),
                    not isinstance(error, errors.RstimesError)]
        raise AssertionError("from_relativedelta accepted an unsupported input")
    records.append(Case("dateutil:error-hierarchy","dateutil",("K08",),relative_error_shape))
    numpy_units = ("Y","M","W","D","h","m","s","ms","us","ns","ps","fs","as")
    for kind,constructor in (("datetime",np.datetime64),("timedelta",np.timedelta64)):
        group="numpy-"+kind
        for unit in numpy_units:
            for label,value in (("positive",2),("negative",-1)):
                scalar=constructor(value,unit);delta=Delta(months=1,days=1,microseconds=1,year=2024,hour=0)
                for op in ("add","radd","sub","rsub","method-add","method-radd","method-sub","method-rsub"):
                    records.append(Case(f"{group}:{unit}:{label}:{op}",group,("K05","K06" if kind=="datetime" else "K07"),
                                        lambda scalar=scalar,delta=delta,op=op:duration_apply(delta,scalar,op)))
        for unit in ("2us","3D","2M"):
            scalar=constructor(2,unit)
            records.append(Case(f"{group}:multiplier:{unit}",group,("K06" if kind=="datetime" else "K07",),lambda scalar=scalar:Delta()+scalar))
        for unit in ("ns","us","D","M"):
            scalar=constructor("NaT",unit)
            for op in ("add","radd","sub","rsub","method-add","method-radd","method-sub","method-rsub"):
                difference="D1" if unit in ("D","M") and op in (("add","method-add","method-radd","method-rsub") if kind=="datetime" else ("add","sub","method-add","method-radd","method-sub","method-rsub")) else None
                records.append(Case(f"{group}:NaT:{unit}:{op}",group,("K06" if kind=="datetime" else "K07",),
                                    lambda scalar=scalar,op=op:duration_apply(Delta(),scalar,op),difference))
    for kind,constructor in (("datetime",np.datetime64),("timedelta",np.timedelta64)):
        records.append(Case("numpy-"+kind+":generic-NaT","numpy-"+kind,("K06" if kind=="datetime" else "K07",),
                            lambda constructor=constructor:Delta().__add__(constructor("NaT"))))
    class PretendNumpy:
        @property
        def __class__(self):return np.datetime64
    records.append(Case("numpy-datetime:impostor","numpy-datetime",("K05",),lambda:Delta().__add__(PretendNumpy())))
    import pandas as pd
    import cytimes
    import pendulum
    thirdparty = [
        ("pandas-normal",pd.Timestamp("2024-01-31T23:30:00"),dict(months=1,hours=2)),
        ("pandas-ns-change",pd.Timestamp("2024-01-31T23:30:00.123456789"),dict(months=1)),
        ("pandas-ns-identity",pd.Timestamp("2024-01-31T23:30:00.123456789"),dict()),
        ("pandas-missing",pd.NaT,dict(days=1)),
        ("pandas-duration",pd.Timedelta("-1ns"),dict(microseconds=1)),
        ("pydt-normal",cytimes.Pydt(2024,1,31,23,30),dict(months=1,hours=2)),
        ("pydt-tz-fold",cytimes.Pydt(2024,11,3,1,30,tzinfo=ny,fold=1),dict(minutes=1)),
        ("pendulum-date",pendulum.date(2024,1,31),dict(months=1)),
        ("pendulum-datetime",pendulum.datetime(2024,1,31,23,30,tz="UTC"),dict(months=1,hours=2)),
        ("pendulum-fold",pendulum.datetime(2024,11,3,1,30,tz="America/New_York",fold=1),dict(minutes=1)),
    ]
    for label,value,values in thirdparty:
        delta=Delta(**values)
        for op in ("add","radd","rsub","method-add","method-radd","method-rsub"):
            records.append(Case(f"thirdparty:{label}:{op}","thirdparty",("K01","K02","K05"),
                                lambda delta=delta,value=value,op=op:duration_apply(delta,value,op)))
    from operator import eq,ne,lt,le,gt,ge
    comparisons = [
        ("same",Delta(days=1),Delta(days=1),None),
        ("different",Delta(days=1),Delta(days=2),None),
        ("child",Delta(days=1),Child(days=1),None),
        ("duration",Delta(microseconds=-1),timedelta(microseconds=-1),None),
        ("duration-absolute-zero",Delta(second=0),timedelta(),None),
        ("duration-month",Delta(months=1),timedelta(days=30),None),
        ("rd-fraction",Delta(days=1,hours=12),relativedelta(days=1.5),None),
        ("rd-weekday-n",Delta(weekday=0),relativedelta(weekday=MO(3)),None),
        ("np-ns",Delta(microseconds=-1),np.timedelta64(-1,"ns"),None),
        ("np-month",Delta(days=30,hours=10,minutes=29,seconds=6),np.timedelta64(1,"M"),None),
        ("none",Delta(),None,None),
        ("int",Delta(),0,None),
        ("date",Delta(),date(2024,1,1),None),
        ("overflow-self",Delta(days=2**63-1),timedelta(),"D1"),
        ("overflow-other",Delta(),timedelta.max,"D1"),
    ]
    for label,left,right,difference in comparisons:
        for name,operation in (("eq",eq),("ne",ne),("direct-eq",lambda a,b:a.__eq__(b)),("direct-ne",lambda a,b:a.__ne__(b))):
            records.append(Case(f"compare:{label}:{name}","compare",("M09","G02"),lambda left=left,right=right,operation=operation:operation(left,right),difference))
        if difference is None:
            records.append(Case(f"compare:{label}:reverse-eq","compare",("M09","G02"),lambda left=left,right=right:right==left))
    for unit in numpy_units:
        scalar=np.timedelta64(-1,unit)
        records.append(Case(f"compare:numpy:{unit}","compare",("M09","K07"),lambda scalar=scalar:Delta().__eq__(scalar)))
    for name,operation in (("lt",lt),("le",le),("gt",gt),("ge",ge)):
        records.append(Case("compare:ordering:"+name,"compare",("G03","G04","G05","G06"),lambda operation=operation:operation(Delta(),Delta())))
        records.append(Case("compare:ordering-direct:"+name,"compare",("G03","G04","G05","G06"),lambda name=name:getattr(Delta(),"__"+name+"__")(Delta())))
    class ReflectedEquality:
        def __eq__(self,other):return "equality reflected"
        def __ne__(self,other):return "inequality reflected"
    records.extend([
        Case("compare:reflection-eq","compare",("M09",),lambda:Delta()==ReflectedEquality()),
        Case("compare:reflection-ne","compare",("M09",),lambda:Delta()!=ReflectedEquality()),
    ])
    def hash_shape(value):
        raw = tuple(-1 if getattr(value,name) is None else getattr(value,name) for name in FIELDS)
        first = hash(value); second = hash(value)
        return {"matches_tuple":first==hash(raw),"cached_same":first==second,"set_count":len({value,Delta(days=value.days)}),
                "lookup":{value:"stored"}[value]}
    def hash_reinitialization():
        value=Delta(days=1);first=hash(value);value.__init__(days=2)
        return (first!=hash(value),hash(value)==hash(Delta(days=2)))
    for label,value in (("empty",Delta()),("relative",Delta(months=-1,microseconds=-1)),
                        ("absolute-zero",Delta(second=0)),("child",Child(year=2024,hour=0))):
        records.append(Case("hash-text:hash:"+label,"hash-text",("H01","M12"),lambda value=value:hash_shape(value)))
        records.append(Case("hash-text:repr:"+label,"hash-text",("M11",),lambda value=value:(repr(value),str(value),repr(value)==str(value))))
    records.extend([
        Case("hash-text:reinitialize","hash-text",("M01","M12"),hash_reinitialization),
        Case("hash-text:raw","hash-text",("G01","M12","M11"),lambda:(hash(Delta.__new__(Delta)),repr(Delta.__new__(Delta)))),
        Case("hash-text:cross-type-defect","hash-text",("M09","M12"),lambda:(Delta(days=1)==timedelta(days=1),hash(Delta(days=1))==hash(timedelta(days=1)))),
    ])
    # S7.4: callback reentry and bounded release protect the native boundary.
    # Existing output cases do not establish that nested init avoids conflicting
    # Rust borrows, or that temporary subclass cycles/reference owners release.
    def reentry_integer(fail=False):
        value = Delta(days=1)
        class Nested:
            def __int__(self):
                value.__init__(hours=7)
                if fail:
                    raise ValueError("nested integer failure")
                return 2
        try:
            value.__init__(days=Nested())
        except ValueError as error:
            return {"delta": value, "error": error_record(error)}
        return value

    def reentry_dateutil():
        from dateutil.relativedelta import relativedelta
        value = Delta(days=1)
        class Nested(relativedelta):
            def normalized(self):
                value.__init__(days=3)
                return relativedelta(days=2)
        return (value + Nested(days=2), value)

    def bounded_release():
        import copy
        import gc
        import sys
        import weakref
        import numpy as np
        class Life(Delta):
            pass
        tz = timezone(timedelta(seconds=1234))
        original = datetime(2024, 2, 29, 12, tzinfo=tz)
        duration = np.timedelta64(3, "us")
        # Warm type/helper caches before comparing retained references.
        temporary = copy.copy(Delta(days=1)) + duration
        del temporary
        gc.collect()
        owners = (Delta, original, tz, duration)
        before = tuple(sys.getrefcount(owner) for owner in owners)
        for index in range(2000):
            value = Delta(months=-1, days=index % 7)
            applied = original + value
            converted = value + duration
            cloned = copy.copy(value)
            hash(value)
            str(value)
            del value, applied, converted, cloned
        gc.collect()
        after = tuple(sys.getrefcount(owner) for owner in owners)
        references = []
        for index in range(100):
            value = Life(days=index)
            value.cycle = value
            references.append(weakref.ref(value))
        del value
        gc.collect()
        assert before == after, "Temporary operations retained an owner reference"
        assert all(reference() is None for reference in references), "Subclass cycles were retained"
        return {"owners_released": before == after,
                "subclass_cycles_released": all(reference() is None for reference in references),
                "ordinary_iterations": 2000, "cyclic_instances": 100}

    records.extend([
        Case("lifecycle:integer-reentry", "lifecycle", ("M01", "H04", "S4"), reentry_integer),
        Case("lifecycle:integer-reentry-error", "lifecycle", ("M01", "K09", "S4"), lambda: reentry_integer(True)),
        Case("lifecycle:dateutil-reentry", "lifecycle", ("M02", "K03", "S4"), reentry_dateutil),
        Case("lifecycle:bounded-release", "lifecycle", ("H04", "S4"), bounded_release),
    ])
    return Delta, records


def benchmark_cases(package):
    """Use the same input factories; timing excludes result packing."""
    Delta, functional = cases(package)
    by_id = {case.id: case for case in functional}
    output = []
    for identifier in ("relative:zero", "relative:mixed", "absolute:clamps"):
        original = by_id[identifier]
        output.append(Case(identifier, "B1", original.requirements, original.run))
    arithmetic_ids = [f"delta-arithmetic:{label}:{op}" for label in ("positive","negative","cancel") for op in ("add","sub")]
    arithmetic_ids += ["delta-arithmetic:year:both:add","delta-arithmetic:year:both:sub",
                       "unary:negative-month:neg","unary:negative-us:abs","unary:opposite-signs:abs"]
    duration_ids = [f"timedelta:{label}:{setting}:{op}" for label,setting in
                    (("positive","relative"),("positive","absolute"),("negative-us","relative"),("negative-us","absolute"))
                    for op in ("add","radd","sub","rsub")]
    for group, identifiers in (("B3",arithmetic_ids),("B4",duration_ids)):
        for identifier in identifiers:
            original = by_id[identifier]
            output.append(Case(identifier,group,original.requirements,original.run))
    value = by_id["absolute:clamps"].run()
    output.extend([
        Case("getters:single", "B2", ("B03",), lambda: value.days),
        Case("getters:all", "B2", tuple(f"B{i:02d}" for i in range(1,16)),
             lambda: tuple(getattr(value, name) for name in FIELDS)),
        Case("bool:mixed", "B2", ("M10",), lambda: bool(value)),
    ])
    _, dates, datetimes = date_fixtures()
    fixtures = {label: (value, kwargs) for label, value, kwargs in dates + datetimes}
    fixed = [("cross-year", "date"), ("month-end", "datetime"), ("us-before", "datetime"),
             ("utc", "datetime"), ("ny-fold", "datetime"), ("ny-unchanged", "datetime")]
    workload = [(fixtures[label][0], fixtures[label][1], Delta(**fixtures[label][1])) for label, _ in fixed]
    for label, kind in fixed:
        original, values = fixtures[label]
        delta = Delta(**values)
        output.append(Case("date-call:"+label+":reuse", "B5", ("K01", "K02"),
                           lambda original=original, delta=delta: original + delta))
        output.append(Case("date-call:"+label+":construct", "B5", ("K01", "K02", "M01"),
                           lambda original=original, values=values: original + Delta(**values)))
    def composed(construct):
        results = []
        for original, values, delta in workload:
            result = original + (Delta(**values) if construct else delta)
            results.append((result.year, result.month, result.day))
        return tuple(results)
    output.extend([Case("date-combination:reuse", "B5", ("K01", "K02"), lambda: composed(False)),
                   Case("date-combination:construct", "B5", ("K01", "K02", "M01"), lambda: composed(True))])
    import copy
    import pickle
    relative_factory = by_id["relative:mixed"].run
    same_left, same_right = relative_factory(), relative_factory()
    cached = relative_factory()
    hash(cached)
    output.extend([
        Case("protocol:eq-equal","B6",("M09",),lambda:same_left==same_right),
        Case("protocol:eq-different","B6",("M09",),lambda:same_left==value),
        Case("protocol:hash-first","B6",("M12",),lambda:hash(relative_factory())),
        Case("protocol:hash-cached","B6",("M12",),lambda:hash(cached)),
        Case("protocol:repr","B6",("M11",),lambda:repr(value)),
        Case("protocol:str","B6",("M11",),lambda:str(value)),
    ])
    relative_ids=["dateutil:from:integer:Delta","dateutil:from:fraction:Delta","dateutil:from:absolute:Delta",
                  "dateutil:from:weekday-n:Delta","dateutil:arithmetic:absolute:add",
                  "dateutil:arithmetic:fraction:rsub","dateutil:arithmetic:weekday-n:radd"]
    numpy_ids=[f"numpy-datetime:{unit}:negative:{op}" for unit in ("ns","us","D","M","Y")
               for op in ("add","method-rsub")]
    numpy_ids += [f"numpy-timedelta:{unit}:negative:{op}" for unit in ("ns","us","D","M","Y")
                  for op in ("add","sub","method-rsub")]
    for group,identifiers in (("B7",relative_ids),("B8",numpy_ids)):
        for identifier in identifiers:
            original=by_id[identifier]
            output.append(Case(identifier,group,original.requirements,original.run))
    Child=globals()["Child"]
    for kind,stored in (("base",Delta(days=2,weekday=0,second=0)),("child",Child(months=-1,microseconds=-1,year=2024))):
        if kind=="child":stored.extra={"list":[1,2]}
        hash(stored)
        encoded=pickle.dumps(stored,protocol=5)
        output.extend([
            Case("save:"+kind+":write","B9",("G07",),lambda stored=stored:pickle.dumps(stored,protocol=5)),
            Case("save:"+kind+":read","B9",("G07",),lambda encoded=encoded:pickle.loads(encoded)),
            Case("save:"+kind+":copy","B9",("H02",),lambda stored=stored:copy.copy(stored)),
            Case("save:"+kind+":deepcopy","B9",("H03",),lambda stored=stored:copy.deepcopy(stored)),
        ])
    from cytimes import Pydt
    from zoneinfo import ZoneInfo
    pydt = Pydt(2024, 1, 31, 23, 30)
    pydt_fold = Pydt(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    pydt_parsed = Pydt.parse("2024-06-15 15:45:00")
    pydt_month = Delta(months=1)
    pydt_sub = Delta(months=1, hours=2)
    pydt_absolute = Delta(hour=9, minutes=30)
    pydt_minute = Delta(minutes=1)
    pydt_empty = Delta()
    output.extend([
        Case("pydt:month:add", "B10", ("K01", "K05"), lambda: pydt + pydt_month),
        Case("pydt:month:sub", "B10", ("K01", "K05"), lambda: pydt - pydt_sub),
        Case("pydt:month:radd", "B10", ("K01", "K05"), lambda: pydt_month + pydt),
        Case("pydt:absolute:add", "B10", ("K01", "K05"), lambda: pydt_parsed + pydt_absolute),
        Case("pydt:fold:add", "B10", ("K01", "K05"), lambda: pydt_fold + pydt_minute),
        Case("pydt:empty:add", "B10", ("K01", "K05"), lambda: pydt + pydt_empty),
    ])
    return Delta, output

def revision_contract_cases(package, selected):
    """Check approved new behavior directly; these are not legacy parity cases."""
    Delta = import_module(package).Delta
    records = []
    if "H01" in selected:
        def keys():
            class Child(Delta):
                pass
            values = [Delta(days=1), Delta(days=1), Child(days=1)]
            assert all(value == values[0] and hash(value) == hash(values[0]) for value in values)
            assert len(set(values)) == 1 and {values[0]: "value"}[values[2]] == "value"
            assert Delta(days=2) != values[0]
            assert Delta(hour=0) != Delta()
            return True
        def foreign():
            from dateutil.relativedelta import relativedelta
            import numpy as np
            value = Delta(days=1)
            others = [timedelta(days=1), relativedelta(days=1), np.timedelta64(1, "D"), None, 1, object()]
            for other in others:
                assert value.__eq__(other) is NotImplemented
                assert value.__ne__(other) is NotImplemented
            assert (value == timedelta(days=1)) is False
            assert (timedelta(days=1) == value) is False
            return True
        records.extend([Case("revision:equal-keys", "H01", ("H01",), keys),
                        Case("revision:foreign-comparison", "H01", ("H01",), foreign)])
    if "H02" in selected:
        def construction():
            args = (1,2,3,4,5,6,7,8,9,10,2024,10,31,0,23,59,59,999,999999)
            expected = (1,9,33,6,7,8,9010,2024,10,31,0,23,59,59,999999)
            class Keyword(str):
                pass
            dynamic = {("~" + name)[1:]: value for name, value in zip(PARAMETERS, args)}
            subclasses = {Keyword(name): value for name, value in zip(PARAMETERS, args)}
            for value in (Delta(*args), Delta(**dict(zip(PARAMETERS, args))),
                          Delta.__new__(Delta, *args), Delta(**dynamic), Delta(**subclasses)):
                assert tuple(getattr(value, name) for name in FIELDS) == expected
            raw = Delta.__new__(Delta)
            assert not raw and raw == Delta()
            for fn in (lambda: Delta(unknown=1), lambda: Delta(1, years=2), lambda: Delta(*range(20))):
                try:
                    fn()
                except TypeError:
                    pass
                else:
                    raise AssertionError("Invalid constructor arguments were accepted")
            return True
        def repeat_init():
            value = Delta(days=1, hour=0)
            fields = tuple(getattr(value, name) for name in FIELDS)
            cache = hash(value)
            mapping = {value: "stable"}
            for kwargs in ({"days": 2}, {}, {"hour": 9}):
                value.__init__(**kwargs)
                assert tuple(getattr(value, name) for name in FIELDS) == fields
                assert hash(value) == cache and mapping[value] == "stable"
            assert (value + Delta(days=2)).days == 3 and value.days == 1
            return True
        def conversions():
            existing = Delta(days=2)
            mapping = {existing: "stable"}
            class Number:
                def __int__(self):
                    existing.__init__(days=99)
                    return 3
            assert Delta(days=Number()).days == 3 and existing.days == 2
            class Failure:
                def __int__(self):
                    existing.__init__(days=99)
                    raise ValueError("conversion failure")
            try:
                Delta(days=Failure())
            except ValueError as error:
                assert str(error) == "conversion failure"
            else:
                raise AssertionError("Conversion error did not propagate")
            assert mapping[existing] == "stable" and existing.days == 2
            return True
        def subtype_new():
            class Child(Delta):
                def __new__(cls, name, **kwargs):
                    return Delta.__new__(cls, **kwargs)
                def __init__(self, name, **kwargs):
                    self.name = name
            value = Child("child", days=3)
            assert value.days == 3 and value.name == "child"
            Delta.__init__(value, days=99)
            assert value.days == 3
            return True
        def unary_dispatch():
            """Protect subclass overrides when native unary slots are installed."""
            class Inherited(Delta):
                pass
            value = Inherited(months=-1, microseconds=-1, hour=0)
            before = tuple(getattr(value, name) for name in FIELDS)
            for result, method in ((-value, Delta.__neg__), (abs(value), Delta.__abs__)):
                assert type(result) is Delta and result == method(value)
            class Override(Delta):
                def __neg__(self):
                    return "custom negative"
                def __abs__(self):
                    return "custom absolute"
            custom = Override(days=-1)
            assert -custom == "custom negative" and abs(custom) == "custom absolute"
            assert type(Delta.__neg__(custom)) is Delta
            assert type(Delta.__abs__(custom)) is Delta
            assert tuple(getattr(value, name) for name in FIELDS) == before
            for original, expected in ((Delta(months=-1, days=1), Delta(months=1, days=1)),
                                       (Delta(microseconds=-1), Delta(microseconds=1)),
                                       (Delta(days=-1, hour=0), Delta(days=1, hour=0))):
                result = abs(original)
                assert result == expected and bool(result) == bool(expected)
                assert date(2024, 2, 15) + result == date(2024, 2, 15) + expected
            return True
        def descriptor_receiver():
            """Reject foreign receivers before native arithmetic payload access."""
            class Forged:
                @property
                def __class__(self):
                    return Delta
            for method in (Delta.__add__, Delta.__radd__, Delta.__sub__, Delta.__rsub__):
                for receiver in (None, 1, Forged()):
                    try:
                        method(receiver, timedelta(days=1))
                    except TypeError:
                        pass
                    else:
                        raise AssertionError("A foreign method receiver was accepted")
            return True
        records.extend([Case("revision:constructor-new", "H02", ("H02",), construction),
                        Case("revision:repeat-init", "H02", ("H02",), repeat_init),
                        Case("revision:conversion-callback", "H02", ("H02",), conversions),
                        Case("revision:subtype-new", "H02", ("H02",), subtype_new),
                        Case("revision:unary-subclass-dispatch", "H02", ("H02", "H07"), unary_dispatch),
                        Case("revision:descriptor-receiver", "H02", ("H02",), descriptor_receiver)])
    if "H08" in selected:
        def fractional_equivalence():
            _, integers = revision_benchmark_cases(package, "revision-reference")
            _, fractions = revision_benchmark_cases(package, "revision-candidate")
            lookup = {c.id: c for c in integers if c.group == "F1"}
            for case in fractions:
                if case.group == "F1":
                    expected, actual = lookup[case.id].run(), case.run()
                    assert pack(actual, Delta) == pack(expected, Delta), case.id
                    assert hash(actual) == hash(expected) and bool(actual) == bool(expected)
            return True
        def fractional_rounding():
            inputs = [{"weeks": -.5}, {"days": -1.25}, {"hours": -.5},
                      {"minutes": 1.25}, {"seconds": -.0000005},
                      {"microseconds": -.5}, {"microseconds": -1.5},
                      {"microseconds": 2.5}, {"microseconds": 1, "seconds": .0000005},
                      {"microseconds": -1, "seconds": .0000005},
                      {"microseconds": 999999, "seconds": .0000015},
                      {"milliseconds": .0005, "microseconds": 1}]
            for kwargs in inputs:
                expected = timedelta(**kwargs)
                assert Delta(**kwargs).to_timedelta() == expected, kwargs
            assert Delta(days=2**53+1, hours=.5) == Delta(days=2**53+1, minutes=30)
            assert Delta(microseconds=2**53+1, seconds=.0000005) == Delta(microseconds=2**53+2)
            assert Delta(years=2.9, months=-1.7, hour=25.8, millisecond=2.9, microsecond=123456.9) == Delta(years=2, months=-1, hour=23, microsecond=2456)
            class FloatChild(float): pass
            assert Delta(hours=FloatChild(1.5)) == Delta(hours=1, minutes=30)
            return True
        def fractional_errors():
            for name in ("weeks", "days", "hours", "minutes", "seconds", "milliseconds", "microseconds"):
                for value, kind in [(float("nan"), ValueError), (float("inf"), OverflowError),
                                    (-float("inf"), OverflowError), (1e100, OverflowError)]:
                    try:
                        Delta(**{name: value})
                    except kind:
                        pass
                    else:
                        raise AssertionError((name, value, "accepted invalid fractional input"))
            return True
        records.extend([Case("revision:fractional-equivalence", "H08", ("H08",), fractional_equivalence),
                        Case("revision:fractional-rounding", "H08", ("H08",), fractional_rounding),
                        Case("revision:fractional-errors", "H08", ("H08",), fractional_errors)])
    if "H09" in selected:
        def wide_input():
            assert Delta(weeks=2**31) == Delta(days=7*2**31)
            assert Delta(quarters=2**31) == Delta(years=2**29)
            assert Delta(months=2**31) == Delta(years=(2**31)//12, months=(2**31)%12)
            assert Delta(years=2**31, months=-12) == Delta(years=2**31-1)
            assert Delta(weeks=float(2**31)+.5) == Delta(days=7*2**31+3, hours=12)
            assert Delta(year=2**40, month=2**40, day=2**40, weekday=2**40, hour=2**40,
                         minute=2**40, second=2**40, microsecond=2**40) == Delta(
                         year=9999, month=12, day=31, weekday=6, hour=23, minute=59, second=59, microsecond=999999)
            assert Delta(millisecond=2**40, microsecond=2**40).microsecond == 999000+(2**40)%1000
            assert Delta(year=-2**40, hour=-2**40) == Delta()
            from dateutil.relativedelta import relativedelta
            assert Delta.from_relativedelta(relativedelta(hour=2**40)) == Delta(hour=23)
            return True
        def wide_input_overflow():
            for kwargs in ({"days": 2**63}, {"year": 2**63}, {"weeks": 2**62},
                           {"days": 2**63-1, "hours": 24}):
                try:
                    Delta(**kwargs)
                except OverflowError:
                    pass
                else:
                    raise AssertionError((kwargs, "accepted a real 64-bit overflow"))
            return True
        records.extend([Case("revision:wide-input", "H09", ("H09",), wide_input),
                        Case("revision:wide-input-overflow", "H09", ("H09",), wide_input_overflow)])
    if "H09_STORAGE" in selected:
        def wide_storage():
            import copy, pickle
            maximum, minimum = 2**63-1, -2**63
            for year in (maximum, minimum, 2**53+1, -2**53-1):
                value = Delta(years=year, months=11, microsecond=3)
                assert value.years == year and value.months == 11 and value.microsecond == 3
                assert hash(value) == hash(tuple(getattr(value, k) if getattr(value, k) is not None else -1 for k in FIELDS))
                for result in (copy.copy(value), copy.deepcopy(value), pickle.loads(pickle.dumps(value))):
                    assert result is not value and result == value and hash(result) == hash(value)
            value = Delta(years=2**53+1, months=11, microsecond=3)
            other = Delta(months=1, microsecond=4)
            assert value + other == Delta(years=2**53+2, microsecond=4)
            assert value - other == Delta(years=2**53+1, months=10, microsecond=3)
            assert value.apply_many([other])[0] == other + value
            assert -value == Delta(years=-2**53-1, months=-11, microsecond=3)
            return True
        def wide_calendar():
            year = 2**31+1
            previous = year-1
            ordinal = previous*365 + previous//4 - previous//100 + previous//400 + 1
            delta = Delta(years=2**31, days=1-ordinal)
            for value in (date(1,1,1), datetime(1,1,1)):
                assert value + delta == value
                assert delta.apply_many([value])[0] == value
            for call in (lambda: date(1,1,1) + Delta(years=2**63-1),
                         lambda: date(1,1,1) - Delta(years=-2**63),
                         lambda: -Delta(years=-2**63),
                         lambda: Delta(years=2**63-1, months=11) + Delta(months=1)):
                try:
                    call()
                except OverflowError:
                    pass
                else:
                    raise AssertionError("Accepted real wide-year overflow")
            return True
        records.extend([Case("revision:wide-storage", "H09", ("H09",), wide_storage),
                        Case("revision:wide-calendar", "H09", ("H09",), wide_calendar)])
    if "H04" in selected:
        import copy
        import pickle
        class RevisionChild(Delta):
            def __new__(cls, name, **kwargs):
                return Delta.__new__(cls, **kwargs)
            def __init__(self, name, **kwargs):
                self.name = name
        RevisionChild.__qualname__ = "RevisionChild"
        globals()["RevisionChild"] = RevisionChild
        class RevisionSlots(Delta):
            __slots__ = ()
        RevisionSlots.__qualname__ = "RevisionSlots"
        globals()["RevisionSlots"] = RevisionSlots
        def saved_values():
            values = [Delta(), Delta(days=-2, hour=0), RevisionChild("child", days=2), RevisionSlots(days=2)]
            values[2].extra = [1, 2]
            for value in values:
                hash(value)
                for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
                    result = pickle.loads(pickle.dumps(value, protocol=protocol))
                    assert result is not value and type(result) is type(value)
                    assert result == value and hash(result) == hash(value)
                    assert getattr(result, "__dict__", None) == getattr(value, "__dict__", None)
                for deep in (False, True):
                    result = copy.deepcopy(value) if deep else copy.copy(value)
                    assert result is not value and type(result) is type(value) and result == value
                    if hasattr(value, "extra"):
                        assert (result.extra is value.extra) is (not deep)
            return True
        def saved_cycles():
            value = RevisionChild("cycle", days=2)
            value.self_reference = value
            shared = [1, 2]
            value.left = shared
            value.right = shared
            for result in (copy.deepcopy(value), pickle.loads(pickle.dumps(value))):
                assert result.self_reference is result and result.left is result.right
                assert result.left is not shared and result == value
            result = copy.copy(value)
            assert result.self_reference is value and result.left is shared
            return True
        def state_guards():
            from rstimes._native import _restore_delta
            value = Delta(days=1)
            mapping = {value: "stable"}
            state = value.__getstate__()
            other = Delta(days=2).__getstate__()
            bad_cache = hash(tuple(state[2])) ^ 8
            # D09: a derived cache may be discarded; fields and immutability
            # remain independently validated.
            value.__setstate__((state[0], state[1], state[2], bad_cache, state[4]))
            assert mapping[value] == "stable"
            malformed = [(other, ValueError),
                         ((state[0], 99, state[2], state[3], state[4]), ValueError),
                         ((state[0], state[1], tuple([True] + list(state[2][1:])), -1, None), TypeError)]
            for bad, error_type in malformed:
                try:
                    value.__setstate__(bad)
                except error_type:
                    pass
                else:
                    raise AssertionError("Invalid or changed state was accepted")
                assert value.days == 1 and mapping[value] == "stable"
            value.__setstate__(value.__getstate__())
            assert value.days == 1
            restored = _restore_delta(Delta, state[2], bad_cache)
            assert restored == value and hash(restored) == hash(value)
            payload = value.__reduce__()[1][1]
            assert type(payload) is bytes
            bad_payloads = [payload[:40], payload[:7] + b"\x63" + payload[8:],
                            payload[:16] + (12).to_bytes(8, "little", signed=True) + payload[24:]]
            stale_cache = payload[:-8] + bad_cache.to_bytes(8, "little", signed=True)
            assert hash(_restore_delta(Delta, stale_cache)) == hash(value)
            for bad in bad_payloads:
                for restore in (lambda: _restore_delta(Delta, bad), lambda: Delta.__new__(Delta, bad)):
                    try:
                        restore()
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Malformed native state payload was accepted")
            return True
        records.extend([Case("revision:pickle-copy", "H04", ("H04",), saved_values),
                        Case("revision:pickle-copy-cycles", "H04", ("H04",), saved_cycles),
                        Case("revision:state-guards", "H04", ("H04",), state_guards)])
    if "H05" in selected:
        from dateutil.relativedelta import relativedelta, MO
        def relative_rules():
            unsupported = [relativedelta(weekday=MO(n)) for n in (None, -2, -1, 0, 1, 2)]
            unsupported += [relativedelta(weekday=0)]
            unsupported += [relativedelta(leapdays=n) for n in (-1, 1, .5)]
            unsupported += [relativedelta(yearday=60), relativedelta(yearday=200)]
            delta = Delta(days=1)
            operations = [Delta.from_relativedelta, lambda rd: delta + rd, lambda rd: rd + delta,
                          lambda rd: delta - rd, lambda rd: rd - delta]
            for value in unsupported:
                for operation in operations:
                    try:
                        operation(value)
                    except ValueError as error:
                        assert "cannot be represented" in str(error)
                    else:
                        raise AssertionError("Unsupported relative date rule was accepted")
            value = Delta.from_relativedelta(relativedelta(days=1, leapdays=0, hour=25))
            assert value.days == 1 and value.hour == 23
            assert Delta.from_relativedelta(relativedelta(days=1.5)).hours == 12
            return True
        def relative_errors():
            class Failure(relativedelta):
                def normalized(self):
                    raise RuntimeError("normalization failure")
            for operation in (Delta.from_relativedelta, lambda rd: Delta() + rd):
                try:
                    operation(Failure())
                except RuntimeError as error:
                    assert str(error) == "normalization failure"
                else:
                    raise AssertionError("Normalization error did not propagate")
            return True
        records.extend([Case("revision:dateutil-rules", "H05", ("H05",), relative_rules),
                        Case("revision:dateutil-errors", "H05", ("H05",), relative_errors)])
    if "H11" in selected:
        def fixed_duration():
            for kwargs in ({}, {"days": 2, "hours": 3}, {"microseconds": -1},
                           {"days": 999999999, "hours": 23, "microseconds": 1},
                           {"days": -999999999}):
                assert Delta(**kwargs).to_timedelta() == timedelta(**kwargs)
            for value in (Delta(months=1), Delta(years=1), Delta(hour=0), Delta(weekday=0)):
                try:
                    value.to_timedelta()
                except ValueError:
                    pass
                else:
                    raise AssertionError("Calendar fields did not require a start")
            for days in (-1000000000, 1000000000, 2**63-1):
                try:
                    Delta(days=days).to_timedelta()
                except OverflowError:
                    pass
                else:
                    raise AssertionError("timedelta range overflow was accepted")
            return True
        def anchored_duration():
            from zoneinfo import ZoneInfo
            from cytimes import Pydt
            inputs = [(date(2024,1,31), Delta(months=1)), (date(2023,1,31), Delta(months=1)),
                      (date(2024,1,15), Delta(hours=25)), (datetime(2024,1,15,12), Delta(hour=9)),
                      (datetime(2024,3,10,1,30,tzinfo=ZoneInfo("America/New_York")), Delta(hours=1)),
                      (datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=1), Delta(minutes=1)),
                      (Pydt(2024,1,31,12), Delta(months=1))]
            for start, delta in inputs:
                expected = (start + delta) - start
                actual = delta.to_timedelta(start)
                assert actual == expected and type(actual) is type(expected)
            # Protect the builtin span path's narrowing, carries and fallbacks.
            from random import Random
            from datetime import tzinfo
            def outcome(call):
                try:
                    value = call()
                    return ("value", type(value), value)
                except Exception as error:
                    return ("error", type(error), str(error))
            anchors = [date.min, date.max, datetime.min, datetime.max,
                       datetime(2024,11,3,1,30,tzinfo=ZoneInfo("America/New_York"),fold=1)]
            amounts = [Delta(), Delta(days=-1), Delta(months=1, day=31), Delta(microseconds=-1),
                       Delta(hours=1), Delta(years=2**31), Delta(days=2**63-1), Delta(years=-2**63)]
            pairs = [(start, delta) for start in anchors for delta in amounts]
            rng = Random(9601)
            for _ in range(96):
                year = rng.choice((1, 4, 1900, 2000, 2024, 9999))
                month, day = rng.randint(1,12), rng.choice((1,28))
                delta = Delta(years=rng.randint(-1,1), months=rng.randint(-18,18),
                              days=rng.randint(-1000,1000), hours=rng.randint(-30,30),
                              microseconds=rng.randint(-1000001,1000001),
                              day=rng.choice((-1,28,31)), weekday=rng.choice((-1,0,6)))
                pairs.extend([(date(year,month,day), delta),
                              (datetime(year,month,day,23,59,59,rng.randint(0,999999)), delta)])
            for start, delta in pairs:
                assert outcome(lambda: delta.to_timedelta(start)) == outcome(lambda: (start + delta) - start)
            class QuietZone(tzinfo):
                def utcoffset(self, value):
                    raise AssertionError("same-zone subtraction must not inspect offsets")
            start = datetime(2024,1,1,23,59,tzinfo=QuietZone(),fold=1)
            assert Delta(minutes=2).to_timedelta(start) == (start + Delta(minutes=2)) - start
            class SpecialSpan(timedelta): pass
            class DateChild(date):
                def __sub__(self, other): return SpecialSpan(days=7)
            start = DateChild(2024,1,1)
            assert type(Delta(days=1).to_timedelta(start)) is timedelta
            assert Delta(days=1).to_timedelta(start) == timedelta(days=7)
            class DeltaChild(Delta):
                def __radd__(self, start): return start + timedelta(days=7)
            assert DeltaChild(days=1).to_timedelta(date(2024,1,1)) == timedelta(days=7)
            try:
                Delta().to_timedelta("2024-01-01")
            except TypeError:
                pass
            else:
                raise AssertionError("Invalid start type was accepted")
            return True
        records.extend([Case("revision:fixed-timedelta", "H11", ("H11",), fixed_duration),
                        Case("revision:anchored-timedelta", "H11", ("H11",), anchored_duration)])
    if "H10" in selected:
        def bulk_matrix():
            _, left = revision_benchmark_cases(package, "revision-reference")
            _, right = revision_benchmark_cases(package, "revision-candidate")
            expected = {case.id: case for case in left if case.group.startswith("A")}
            for case in right:
                if not case.group.startswith("A"):
                    continue
                first, second = expected[case.id].run(), case.run()
                assert len(first) == len(second)
                for a, b in zip(first, second):
                    assert pack(a, Delta) == pack(b, Delta), case.id
            return True
        def bulk_iteration():
            delta = Delta(days=1)
            assert delta.apply_many([]) == []
            values = [date(2024,1,1), datetime(2024,1,1,12), Delta(hours=1), timedelta(hours=1)]
            assert [pack(x, Delta) for x in delta.apply_many(iter(values))] == [pack(x + delta, Delta) for x in values]
            consumed = []
            def invalid():
                for value in (values[0], None, values[1]):
                    consumed.append(value)
                    yield value
            try:
                delta.apply_many(invalid())
            except TypeError:
                pass
            else:
                raise AssertionError("Unsupported middle item was accepted")
            assert len(consumed) == 2
            def broken():
                yield values[0]
                raise RuntimeError("iteration failure")
            try:
                delta.apply_many(broken())
            except RuntimeError as error:
                assert str(error) == "iteration failure"
            else:
                raise AssertionError("Iterator error did not propagate")
            original = date(2024,1,1)
            assert Delta().apply_many([original])[0] is original
            return True
        def bulk_overrides():
            class CustomDate(date):
                def __add__(self, other):
                    return ("date override", other.days)
            class CustomDelta(Delta):
                def __radd__(self, other):
                    return "reflected override"
            assert Delta(days=2).apply_many([CustomDate(2024,1,1)]) == [("date override", 2)]
            assert CustomDelta(days=2).apply_many([date(2024,1,1)]) == ["reflected override"]
            class CustomList(list):
                def __iter__(self):
                    return iter([date(2024,2,1)])
            assert Delta(days=1).apply_many(CustomList([date(2024,1,1)])) == [date(2024,2,2)]
            def changing_input():
                values = []
                class Mutator:
                    def __add__(self, other):
                        values.append(date(2024,1,1))
                        return "first"
                values.append(Mutator())
                return values
            delta = Delta(days=1)
            assert delta.apply_many(changing_input()) == [value + delta for value in changing_input()]
            from cytimes import Pydt
            values = [Pydt(2024, 1, 31), Pydt(2024, 1, 15)]
            original = Pydt.__dict__.get("__add__")
            try:
                Pydt.__add__ = lambda self, other: ("patched Pydt addition", self.day)
                assert Delta(days=1).apply_many(values) == [value + Delta(days=1) for value in values]
            finally:
                if original is None:
                    del Pydt.__add__
                else:
                    Pydt.__add__ = original
            from dateutil.relativedelta import relativedelta
            original_add, original_normalized = relativedelta.__add__, relativedelta.normalized
            delta = Delta(days=1, hour=9)
            values = [relativedelta(days=2), relativedelta(hour=0)]
            expected = [value + delta for value in values]  # Initialize the exact-type cache.
            try:
                relativedelta.__add__ = lambda self, other: ("patched dateutil addition", self.days)
                assert delta.apply_many(values) == [value + delta for value in values]
                relativedelta.__add__ = lambda self, other: NotImplemented
                assert delta.apply_many(values) == expected
                def raises(self, other):
                    raise RuntimeError("dateutil callback failure")
                relativedelta.__add__ = raises
                for call in (lambda: values[0] + delta, lambda: delta.apply_many(values)):
                    try:
                        call()
                    except RuntimeError as error:
                        assert str(error) == "dateutil callback failure"
                    else:
                        raise AssertionError("dateutil callback error was lost")
                relativedelta.__add__ = original_add
                for bulk in (False, True):
                    mutable = list(values)
                    def normalized(self):
                        mutable.clear()
                        return original_normalized(self)
                    relativedelta.normalized = normalized
                    result = delta.apply_many(mutable) if bulk else [value + delta for value in mutable]
                    assert result == expected[:1]
            finally:
                relativedelta.__add__, relativedelta.normalized = original_add, original_normalized
            return True
        def bulk_native_boundaries():
            # Protect packed absolute merges, explicit zero flags and real carries.
            pairs = [(Delta(hours=23, microseconds=999999, hour=9), Delta(hours=1, microseconds=1, hour=0)),
                     (Delta(years=-1, months=11, day=31), Delta(months=1, day=2)),
                     (Delta(years=2**31-1), Delta(years=1)),
                     (Delta(days=2**63-1), Delta(days=1)),
                     (Delta(days=2**63-1, hours=23), Delta(hours=1)),
                     (Delta(years=2**63-1, days=2**63-1, hours=23), Delta(years=1, hours=1)),
                     (timedelta(microseconds=-1), Delta(microseconds=1)),
                     (timedelta(days=1), Delta(hour=0, minute=0, second=0, microsecond=0))]
            def result(call):
                try:
                    value = call()
                    return ("ok", pack(value, Delta), bool(value), hash(value),
                            date(2024, 1, 1) + value if abs(value.days) < 100 else None)
                except Exception as error:
                    return ("error", type(error).__name__, str(error))
            for left, right in pairs:
                assert result(lambda: left + right) == result(lambda: right.apply_many([left])[0])
            def mutating():
                values = [Delta()]
                class Item:
                    def __add__(self, other):
                        values.clear()
                        return "retained callback operand"
                values.append(Item())
                return values
            assert Delta(days=1).apply_many(mutating()) == [v + Delta(days=1) for v in mutating()]
            import gc
            class Collector:
                def __add__(self, other):
                    gc.collect()
                    for item in gc.get_objects():
                        if type(item) is list and len(item) == 17:
                            tuple(item)  # Reserved output slots must be valid objects.
                    return "collected"
            assert Delta(days=1).apply_many([Collector() for _ in range(17)]) == ["collected"] * 17
            return True
        records.extend([Case("revision:bulk-matrix", "H10", ("H10",), bulk_matrix),
                        Case("revision:bulk-iteration", "H10", ("H10",), bulk_iteration),
                        Case("revision:bulk-overrides", "H10", ("H10",), bulk_overrides),
                        Case("revision:bulk-native-boundaries", "H10", ("H10",), bulk_native_boundaries)])
    return Delta, records


def revision_benchmark_cases(package, variant):
    """Define both public-call sides of the revision contract in one input source.

    Template calls exercise transport before new methods exist. They have their
    own IDs and never count as evidence for the real float or bulk APIs.
    """
    Delta = import_module(package).Delta
    reference = variant.endswith("reference")
    if variant.startswith("template"):
        values = [datetime(2024, 1, 31, 12, i) for i in range(32)]
        delta = Delta(days=1)
        def loop():
            result = []
            for value in values:
                result.append(value + delta)
            return result
        return Delta, [Case("template:construct", "T1", ("N03",),
                            lambda: Delta(days=1, hours=1) if reference else Delta(hours=25)),
                       Case("template:batch", "T1", ("N03",),
                            loop if reference else lambda: [value + delta for value in values])]
    records = []
    floats = [
        ("weeks", {"weeks": 1.5}, {"days": 10, "hours": 12}),
        ("days", {"days": .5}, {"hours": 12}),
        ("hours", {"hours": 1.5}, {"hours": 1, "minutes": 30}),
        ("minutes", {"minutes": 1.5}, {"minutes": 1, "seconds": 30}),
        ("seconds", {"seconds": 1.5}, {"seconds": 1, "microseconds": 500000}),
        ("milliseconds", {"milliseconds": 1.5}, {"microseconds": 1500}),
        ("microseconds", {"microseconds": 1.5}, {"microseconds": 2}),
        ("negative", {"hours": -1.5}, {"hours": -1, "minutes": -30}),
        ("mixed", {"days": 1.5, "hours": -12}, {"days": 1}),
        ("round", {"seconds": .0000005}, {"microseconds": 0}),
    ]
    for name, fractional, integer in floats:
        kwargs = integer if reference else fractional
        records.append(Case("float:" + name, "F1", ("H08", "P02"), lambda kwargs=kwargs: Delta(**kwargs)))
    from zoneinfo import ZoneInfo
    from dateutil.relativedelta import relativedelta
    from cytimes import Pydt
    import numpy as np
    ny = ZoneInfo("America/New_York")
    factories = [
        ("date-month-end", "A1", lambda i: date(2024, 1, 31), {"months": 1}),
        ("datetime-relative", "A1", lambda i: datetime(2024, 1, 15, 12, i % 60), {"days": 1, "hours": 2}),
        ("datetime-absolute", "A1", lambda i: datetime(2024, 1, 15, 12, i % 60), {"hour": 9}),
        ("datetime-aware", "A1", lambda i: datetime(2024, 11, 3, 1, i % 60, tzinfo=ny, fold=1), {"minutes": 1}),
        ("delta-relative", "A2", lambda i: Delta(days=i % 31, hours=i % 24), {"days": 1, "hours": 2}),
        ("delta-absolute", "A2", lambda i: Delta(days=i % 31, hour=13), {"hour": 9, "days": 1}),
        ("timedelta-positive", "A3", lambda i: timedelta(days=i % 31, seconds=2), {"days": 1, "hours": 2}),
        ("timedelta-negative", "A3", lambda i: timedelta(microseconds=-i-1), {"microseconds": -1}),
        ("pydt-month", "A4", lambda i: Pydt(2024, 1, 31, 12, i % 60), {"months": 1}),
        ("pydt-absolute", "A4", lambda i: Pydt(2024, 1, 15, 12, i % 60), {"hour": 9}),
        ("dateutil-relative", "A5", lambda i: relativedelta(days=i % 31, hours=1), {"days": 1}),
        ("dateutil-absolute", "A5", lambda i: relativedelta(day=31, hour=13), {"hour": 9}),
        ("numpy-datetime", "A6", lambda i: np.datetime64("2024-01-15T12:00:00", "us"), {"days": 1}),
        ("numpy-timedelta", "A6", lambda i: np.timedelta64(i+1, "us"), {"days": 1}),
    ]
    mixed = [lambda: date(2024, 1, 15), lambda: datetime(2024, 1, 15, 12),
             lambda: Delta(hours=1), lambda: timedelta(hours=1), lambda: Pydt(2024, 1, 15, 12),
             lambda: relativedelta(hours=1), lambda: np.datetime64("2024-01-15", "us"),
             lambda: np.timedelta64(1, "h")]
    factories.append(("mixed", "A7", lambda i: mixed[i % len(mixed)](), {"days": 1}))
    for name, group, factory, kwargs in factories:
        delta = Delta(**kwargs)
        for size in (1024, 10000):
            values = [factory(i) for i in range(size)]
            run = (lambda values=values, delta=delta: [value + delta for value in values]) if reference else (
                lambda values=values, delta=delta: delta.apply_many(values))
            records.append(Case(f"bulk:{name}:{size}", group + ":" + str(size), ("H10", "P03", "P04"), run))
    conversions = [
        ("positive", {"days": 2, "hours": 3}, None),
        ("negative", {"microseconds": -1}, None),
        ("month-leap", {"months": 1}, date(2024, 1, 31)),
        ("month-normal", {"months": 1}, date(2023, 1, 31)),
        ("absolute", {"hour": 9}, datetime(2024, 1, 15, 12)),
        ("aware", {"hours": 1}, datetime(2024, 3, 10, 1, 30, tzinfo=ny)),
    ]
    for name, kwargs, start in conversions:
        delta = Delta(**kwargs)
        def manual(delta=delta, start=start):
            return ((start + delta) - start if start is not None else timedelta(
                days=delta.days, hours=delta.hours, minutes=delta.minutes,
                seconds=delta.seconds, microseconds=delta.microseconds))
        run = manual if reference else lambda delta=delta, start=start: delta.to_timedelta(start)
        records.append(Case("to-timedelta:" + name, "X1", ("H11",), run))
    return Delta, records


def candidate_cases(package, revision=False):
    """Build this package's own state, copy, export and lifecycle contract cases."""
    if package != "rstimes": raise ValueError("New state format belongs only to rstimes")
    import copy
    import pickle
    import sys
    Delta=import_module(package).Delta
    class ContractChild(Delta): pass
    ContractChild.__qualname__="ContractChild"
    globals()["ContractChild"]=ContractChild
    class ConstructorChild(Delta):
        if revision:
            def __new__(cls, required, **kwargs):
                return Delta.__new__(cls, **kwargs)
        def __init__(self, required, **kwargs):
            super().__init__(**kwargs)
            self.required=required
    ConstructorChild.__qualname__="ConstructorChild"
    globals()["ConstructorChild"]=ConstructorChild
    def successful_restore(child=False,raw=False):
        original=ContractChild(days=2,second=0) if child else Delta(days=2,second=0)
        if raw: original=Delta.__new__(Delta)
        if child: original.extra={"list":[1,2]}
        hash(original)
        state=original.__getstate__()
        assert state[0:2]==("rstimes.delta",1) and len(state)==5 and len(state[2])==15
        if revision:
            from rstimes._native import _restore_delta
            restored = _restore_delta(type(original), state[2], state[3])
        else:
            restored=Delta.__new__(type(original))
        restored.__setstate__(state)
        assert tuple(getattr(restored,key) for key in FIELDS)==tuple(getattr(original,key) for key in FIELDS)
        assert restored.__getstate__()==state and hash(restored)==hash(original)
        if child: assert restored.__dict__==original.__dict__ and restored.__dict__ is not original.__dict__
        return True
    records=[Case("state:normal","state",("G09",),successful_restore),
             Case("state:child","state",("G09","H04"),lambda:successful_restore(True)),
             Case("state:raw","state",("G01","G09"),lambda:successful_restore(raw=True))]
    def invalid_state(make,exception):
        value=ContractChild(days=2,year=2024)
        value.extra={"keep":[1]}
        hash(value)
        before=value.__getstate__()
        bad=make(before)
        try: value.__setstate__(bad)
        except exception: pass
        else: raise AssertionError("Malformed state was accepted")
        assert value.__getstate__()==before
        return True
    def change(state,index,value):
        result=list(state);result[index]=value;return tuple(result)
    def field(state,index,value):
        values=list(state[2]);values[index]=value;return change(state,2,tuple(values))
    malformed=[
        ("root-list",lambda state:list(state),TypeError),
        ("short",lambda state:state[:-1],ValueError),
        ("long",lambda state:state+(None,),ValueError),
        ("marker",lambda state:change(state,0,"rstimes.delta.other"),ValueError),
        ("version",lambda state:change(state,1,2),ValueError),
        ("version-type",lambda state:change(state,1,"1"),TypeError),
        ("fields-list",lambda state:change(state,2,list(state[2])),TypeError),
        ("fields-short",lambda state:change(state,2,state[2][:-1]),ValueError),
        ("fields-long",lambda state:change(state,2,state[2]+(0,)),ValueError),
        ("field-float",lambda state:field(state,2,2.0),TypeError),
        ("field-bool",lambda state:field(state,2,True),TypeError),
        ("field-huge",lambda state:field(state,2,2**64),OverflowError),
        ("year-range",lambda state:field(state,0,2**31),ValueError),
        ("month-normal",lambda state:field(state,1,12),ValueError),
        ("hour-normal",lambda state:field(state,3,-1),ValueError),
        ("abs-year-zero",lambda state:field(state,7,0),ValueError),
        ("abs-weekday",lambda state:field(state,10,7),ValueError),
        ("last-field",lambda state:field(state,14,1000000),ValueError),
        ("hash-type",lambda state:change(state,3,1.5),TypeError),
        ("hash-mismatch",lambda state:change(state,3,state[3]+1),ValueError),
        ("dict-list",lambda state:change(state,4,[]),TypeError),
        ("dict-key",lambda state:change(state,4,{1:"bad"}),TypeError),
    ]
    for label,make,exception in malformed:
        if revision and label in ("hash-type", "hash-mismatch"):
            def discard_cache(make=make):
                value=Delta(days=1); before=value.__getstate__(); expected=hash(value)
                value.__setstate__(make(value.__getstate__()))
                assert value.days == 1 and hash(value) == expected
                assert value.__getstate__()[2] == before[2]
                return True
            records.append(Case("state:discard:"+label,"state",("G09",),discard_cache))
            continue
        records.append(Case("state:reject:"+label,"state",("G09",),lambda make=make,exception=exception:invalid_state(make,exception)))
    def reject_base_dictionary():
        value=Delta(days=1);before=value.__getstate__();bad=change(before,4,{"x":1})
        try:value.__setstate__(bad)
        except ValueError:pass
        else:raise AssertionError("Base dictionary was accepted")
        assert value.__getstate__()==before
        return True
    records.append(Case("state:base-dictionary","state",("G09",),reject_base_dictionary))
    def roundtrip(protocol,kind):
        value=Delta(days=2,weekday=0,second=0) if kind=="base" else ContractChild(months=-1,microseconds=-1,year=2024)
        if kind=="constructor":value=ConstructorChild("constructor-required",days=2)
        if kind!="base":value.extra={"list":[1,2]}
        hash(value)
        encoded=pickle.dumps(value,protocol=protocol)
        assert (b"rstDlt" in encoded if revision else b"rstimes.delta" in encoded) and b"cytimes" not in encoded
        result=pickle.loads(encoded)
        assert type(result) is type(value) and result is not value and result.__getstate__()==value.__getstate__()
        assert "cytimes" not in sys.modules, "Restoring own pickle imported cytimes"
        return True
    for protocol in range(6):
        for kind in ("base","child","constructor"):
            records.append(Case(f"pickle-copy:protocol:{protocol}:{kind}","pickle-copy",("G07","H02","H03"),lambda protocol=protocol,kind=kind:roundtrip(protocol,kind)))
    def copied(deep,child):
        value=ContractChild(days=2) if child else Delta(days=2)
        if child:value.extra={"list":[1,2]}
        hash(value)
        result=copy.deepcopy(value) if deep else copy.copy(value)
        assert result is not value and type(result) is type(value) and result.__getstate__()==value.__getstate__()
        if child:assert (result.extra is value.extra) is (not deep)
        return True
    for deep in (False,True):
        for child in (False,True):
            records.append(Case(f"pickle-copy:copy:{deep}:{child}","pickle-copy",("H02","H03"),lambda deep=deep,child=child:copied(deep,child)))
    def deep_cycle():
        value=ContractChild(days=2)
        value.self_reference=value
        result=copy.deepcopy(value)
        assert result is not value and result.self_reference is result and result.days==2
        return True
    class SlotChild(Delta):__slots__=()
    SlotChild.__qualname__="SlotChild"
    globals()["SlotChild"]=SlotChild
    def slot_copy(deep):
        value=SlotChild(days=2)
        result=copy.deepcopy(value) if deep else copy.copy(value)
        assert type(result) is SlotChild and result is not value and result.days==2
        assert not hasattr(result,"__dict__")
        return True
    records.extend([Case("pickle-copy:cycle","pickle-copy",("H03",),deep_cycle),
                    Case("pickle-copy:slots-shallow","pickle-copy",("H02",),lambda:slot_copy(False)),
                    Case("pickle-copy:slots-deep","pickle-copy",("H03",),lambda:slot_copy(True))])
    def exports():
        import ast
        from pathlib import Path
        loaded=import_module(package)
        submodule=import_module(package+".delta")
        assert loaded.Delta is submodule.Delta and Delta.__module__=="rstimes.delta"
        package_root=Path(loaded.__file__).parent
        assert (package_root/"py.typed").is_file()
        tree=ast.parse((package_root/"delta.pyi").read_text(encoding='utf-8'))
        klass=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=="Delta")
        methods={node.name for node in klass.body if isinstance(node,ast.FunctionDef)}
        required=set(FIELDS)|{"__init__","from_relativedelta","__add__","__radd__","__sub__","__rsub__","__neg__","__abs__","__eq__","__bool__","__repr__","__hash__"}
        if revision:
            required |= {"__new__", "apply_many", "to_timedelta"}
        assert required<=methods
        constructor=next(node for node in klass.body if isinstance(node,ast.FunctionDef) and node.name==("__new__" if revision else "__init__"))
        assert tuple(arg.arg for arg in constructor.args.args[1:])==PARAMETERS
        assert all(hasattr(Delta,name) for name in required)
        assert set(loaded.__all__)=={"Delta","to_unix_ms","from_unix_ms"}
        return True
    def derived_truth():
        value = Delta(days=1)
        assert bool(value)
        value.__init__()
        if revision:
            assert bool(value) and value.days == 1
            for state in (Delta().__getstate__(), Delta.__new__(Delta).__getstate__()):
                try:
                    value.__setstate__(state)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Immutable fields were overwritten")
            assert bool(value) and value.days == 1
            return True
        assert not bool(value)
        value.__init__(second=0)
        assert bool(value)
        value.__setstate__(Delta().__getstate__())
        assert not bool(value)
        value.__setstate__(Delta.__new__(Delta).__getstate__())
        assert bool(value)
        return True
    records.append(Case("state:derived-truth", "state", ("M10", "M01", "G09"), derived_truth))
    def descriptor_receiver():
        for name in FIELDS:
            descriptor=getattr(Delta,name)
            try:descriptor.__get__(object(),Delta)
            except TypeError:pass
            else:raise AssertionError("Getter accepted a non-Delta receiver")
        return True
    records.append(Case("state:getter-receiver","state",("B01","H04"),descriptor_receiver))
    records.append(Case("exports:interface-and-stub","exports",("M01","H04"),exports))
    return Delta,records


def revision_expectations():
    """Give explicit approved outcomes for legacy inputs whose meaning changed.

    Standard timedelta supplies fractional results; Python integer divmod gives
    widened month/week results. These expectations never copy candidate output.
    All other legacy rows retain the frozen reference comparison.
    """
    def scalar(value):
        return {"type": type_name(value), "value": value}
    def delta(**values):
        return {"type": "rstimes.delta.Delta", "fields": {
            name: values.get(name, 0 if index < 7 else None) for index, name in enumerate(FIELDS)}}
    def sequence(*items):
        return {"type": "builtins.tuple", "items": list(items)}
    def mapping(**items):
        return {"type": "builtins.dict", "items": items}
    expected = {}
    def result(identifier, rule, value):
        expected[identifier] = {"rule": rule, "result": value}
    def error(identifier, rule, kind):
        expected[identifier] = {"rule": rule, "error_type": "builtins." + kind}

    for identifier in ("allocation:raw", "properties:raw"):
        result(identifier, "H02", delta())
    result("allocation:raw-args", "H02", delta(years=2))
    unchanged = mapping(value=delta(days=1), same_object=scalar(True), returned=scalar(None))
    for identifier in ("allocation:reinit", "properties:reinit"):
        result(identifier, "H02", unchanged)
    result("properties:failure-state", "H02", mapping(value=delta(days=2, year=2024), error=scalar(None)))
    for identifier in ("lifecycle:integer-reentry", "lifecycle:integer-reentry-error"):
        result(identifier, "H02", delta(days=1))
    result("lifecycle:dateutil-reentry", "H02", sequence(delta(days=3), delta(days=1)))
    result("hash-text:reinitialize", "H02", sequence(scalar(False), scalar(False)))
    result("hash-text:raw", "H02", sequence(scalar(hash((0,)*7 + (-1,)*8)), scalar("<'Delta' ()>")))
    result("hash-text:cross-type-defect", "H01", sequence(scalar(False), scalar(False)))

    labels = ("duration", "duration-absolute-zero", "duration-month", "rd-fraction", "rd-weekday-n",
              "np-ns", "np-month", "none", "int", "date", "overflow-self", "overflow-other")
    for label in labels:
        methods = ("eq", "ne", "direct-eq", "direct-ne") + (() if label.startswith("overflow-") else ("reverse-eq",))
        for method in methods:
            value = ({"type": "builtins.NotImplementedType", "value": "NotImplemented"}
                     if method.startswith("direct-") else scalar(method == "ne" and not label.startswith("rd-")))
            result(f"compare:{label}:{method}", "H01", value)
    for unit in ("Y", "M", "W", "D", "h", "m", "s", "ms", "us", "ns", "ps", "fs", "as"):
        result("compare:numpy:" + unit, "H01", {"type": "builtins.NotImplementedType", "value": "NotImplemented"})

    def widened(parameter, value):
        if parameter == "years": return delta(years=value)
        if parameter in ("months", "quarters"):
            years, months = divmod(value * (3 if parameter == "quarters" else 1), 12)
            return delta(years=years, months=months)
        if parameter == "weeks": return delta(days=value*7)
        maximum = {"year": 9999, "month": 12, "day": 31, "weekday": 6, "hour": 23,
                   "minute": 59, "second": 59, "millisecond": 999, "microsecond": 999999}[parameter]
        final = None if value < 0 else min(value, maximum)
        if parameter == "millisecond":
            return delta(microsecond=None if final is None else final*1000)
        return delta(**{parameter: final})
    for parameter in ("years", "quarters", "months", "weeks") + PARAMETERS[10:]:
        for label, value in (("over", 2**31), ("under", -2**31-1)):
            result(f"coercion:{parameter}:{label}", "H09", widened(parameter, value))
    for label, parameter, value in (("years", "years", 2**31), ("quarters", "quarters", 2**31-1),
                                  ("weeks", "weeks", 2**31-1), ("negative-quarters", "quarters", -2**31),
                                  ("negative-weeks", "weeks", -2**31)):
        result("relative:overflow:" + label, "H09", widened(parameter, value))
    result("relative:overflow:negative-years", "H09", delta(years=-2**31-1, months=11))
    result("delta-arithmetic:overflow:add-years", "H09", delta(years=2**31))
    result("delta-arithmetic:overflow:sub-years", "H09", delta(years=-2**31-1))
    for method in ("neg", "abs"):
        result("unary:overflow:years:" + method, "H09", delta(years=2**31))
    for parameter in PARAMETERS[3:10]:
        duration = timedelta(**{parameter: -1.9})
        result("coercion:" + parameter + ":float", "H08", delta(
            days=duration.days, hours=duration.seconds//3600,
            minutes=duration.seconds//60%60, seconds=duration.seconds%60,
            microseconds=duration.microseconds))
    error("coercion:days:nan", "H08", "ValueError")
    error("coercion:days:inf", "H08", "OverflowError")
    for label in ("weekday-n", "weekday-negative", "leapdays"):
        for kind in ("Delta", "Child"):
            error(f"dateutil:from:{label}:{kind}", "H05", "ValueError")
        for method in ("add", "radd", "sub", "rsub", "method-add", "method-radd", "method-sub", "method-rsub"):
            error(f"dateutil:arithmetic:{label}:{method}", "H05", "ValueError")
    return expected


def correction_contract_cases(package):
    """Return the approved maintenance contracts, with independent expected values."""
    import copy
    import pickle
    from pathlib import Path
    import numpy as np
    import pandas as pd
    from dateutil.relativedelta import relativedelta, MO

    Delta = import_module(package).Delta
    records = []

    def add(label, group, run):
        records.append(Case("correction:" + label, group, (group,), run))

    def raises(kind, call):
        try:
            call()
        except kind:
            return True
        raise AssertionError(f"Expected {kind.__name__}")

    def wide(kwargs):
        factors = {"weeks": 604_800_000_000, "days": 86_400_000_000,
                   "hours": 3_600_000_000, "minutes": 60_000_000,
                   "seconds": 1_000_000, "milliseconds": 1_000, "microseconds": 1}
        total = sum(value * factors[key] for key, value in kwargs.items())
        days, remainder = divmod(total, 86_400_000_000)
        hours, remainder = divmod(remainder, 3_600_000_000)
        minutes, remainder = divmod(remainder, 60_000_000)
        seconds, micros = divmod(remainder, 1_000_000)
        result = Delta(**kwargs)
        assert tuple(getattr(result, key) for key in FIELDS[:7]) == (
            0, 0, days, hours, minutes, seconds, micros)
        return True

    for label, kwargs in (
        ("max-ms", {"milliseconds": 2**63-1}),
        ("min-ms", {"milliseconds": -2**63}),
        ("us-plus-ms", {"microseconds": 2**63-1, "milliseconds": 1}),
        ("cancel", {"milliseconds": 2**63-1, "microseconds": -2**63}),
        ("clock-cancel", {"seconds": 2**63-1, "minutes": -(2**63-1)//60}),
    ):
        add("wide:" + label, "F04", lambda kwargs=kwargs: wide(kwargs))
    add("wide:final-overflow", "F04", lambda: raises(
        OverflowError, lambda: Delta(days=2**63-1, hours=24)))

    def fractional_boundary(positive):
        amount = 2**63-1 if positive else -(2**63)
        extra = 1_800_000_000 if positive else -1_800_000_000
        days, rest = divmod(amount + extra, 86_400_000_000)
        hours, rest = divmod(rest, 3_600_000_000)
        minutes, rest = divmod(rest, 60_000_000)
        seconds, micros = divmod(rest, 1_000_000)
        result = Delta(microseconds=amount, hours=0.5 if positive else -0.5)
        assert tuple(getattr(result, name) for name in FIELDS[:7]) == (
            0, 0, days, hours, minutes, seconds, micros)
        return True
    for positive in (False, True):
        add(f"wide:fraction:{positive}", "F04", lambda positive=positive: fractional_boundary(positive))

    def wide_native(operation):
        if operation == "year-subtract":
            result = Delta(years=2**63-1) - Delta(years=-1, months=11)
            assert result.years == 2**63-1 and result.months == 1
        elif operation == "year-negate":
            result = -Delta(years=-2**63, months=1)
            assert result.years == 2**63-1 and result.months == 11
        elif operation == "day-negate":
            result = -Delta(days=-2**63, microseconds=1)
            assert result.days == 2**63-1 and (result.hours, result.minutes, result.seconds, result.microseconds) == (23, 59, 59, 999999)
        else:
            left, right = Delta(days=-2**63, hours=23), Delta(days=-1, hours=1)
            result = left + right if operation == "day-add" else right.apply_many([left])[0]
            assert result == Delta(days=-2**63)
        return True
    for operation in ("year-subtract", "year-negate", "day-negate", "day-add", "day-many"):
        add("wide:native:" + operation, "F04", lambda operation=operation: wide_native(operation))

    def wide_duration(reverse):
        if reverse:
            value = Delta(days=-2**63, microseconds=1)
            result = timedelta() - value
            expected = Delta(days=2**63-1, hours=23, minutes=59, seconds=59, microseconds=999999)
        else:
            value = Delta(days=-2**63, hours=23)
            result = value + timedelta(days=-1, hours=1)
            expected = Delta(days=-2**63)
        assert result == expected
        return True
    for reverse in (False, True):
        add(f"wide:duration:{reverse}", "F04", lambda reverse=reverse: wide_duration(reverse))

    def custom_comparison():
        class Child(Delta):
            def __eq__(self, other):
                return False
            __hash__ = None
        base, child = Delta(days=1), Child(days=1)
        assert (base == child, base != child, child == base, child != base) == (
            False, True, False, True)
        assert Delta.__eq__(base, child) is NotImplemented
        assert Delta.__ne__(base, child) is NotImplemented
        assert Delta.__eq__(child, base) is NotImplemented
        return True

    def inherited_comparison():
        class Child(Delta):
            pass
        class Ordered(Delta):
            def __lt__(self, other):
                return False
        for cls in (Child, Ordered):
            value = cls(days=1)
            assert value == Delta(days=1) and not (value != Delta(days=1))
            assert hash(value) == hash(Delta(days=1))
        class HashChild(Delta):
            __hash__ = None
        assert Delta.__eq__(Delta(days=1), HashChild(days=1)) is NotImplemented
        return True

    add("comparison:custom", "F05", custom_comparison)
    add("comparison:inherited", "F05", inherited_comparison)

    def timestamp_relative(micros, suffix, tz):
        start = pd.Timestamp("2024-01-31 23:59:59.999999" + suffix, tz=tz)
        delta = Delta(microseconds=micros)
        expected = start + pd.Timedelta(microseconds=micros)
        assert start + delta == expected
        assert delta + start == expected
        assert start - delta == start - pd.Timedelta(microseconds=micros)
        assert delta.apply_many([start, start]) == [expected, expected]
        assert type(start + delta) is pd.Timestamp
        return True

    for micros in (-2, -1, 0, 1, 2):
        for suffix in ("123", "999"):
            add(f"nano:relative:{micros}:{suffix}", "F07a",
                lambda micros=micros, suffix=suffix: timestamp_relative(micros, suffix, None))
    add("nano:timezone", "F07a", lambda: timestamp_relative(1, "123", "UTC"))

    def calendar_nanoseconds():
        start = pd.Timestamp("2024-01-31 12:00:00.000000123")
        assert start + Delta(months=1) == pd.Timestamp("2024-02-29 12:00:00.000000123")
        assert (start + Delta(hour=9)).nanosecond == 123
        assert (start + Delta(days=1, microsecond=-2)).nanosecond == 123
        return True

    def absolute_nanoseconds():
        start = pd.Timestamp("2024-01-01 00:00:00.000000123")
        for delta, microsecond in ((Delta(microsecond=0), 0),
                                   (Delta(millisecond=2, microsecond=123456), 2456)):
            result = start + delta
            assert result.microsecond == microsecond and result.nanosecond == 0
            assert delta.apply_many([start])[0] == result
        return True

    add("nano:calendar", "F07a", calendar_nanoseconds)
    add("nano:absolute", "F07a", absolute_nanoseconds)

    def duration_subclass():
        class Span(timedelta):
            pass
        class DateSpan(date):
            def __sub__(self, other):
                return Span(days=7)
        result = Delta(days=1).to_timedelta(DateSpan(2024, 1, 1))
        assert type(result) is timedelta and result == timedelta(days=7)
        return True

    def rounded_duration(nanos):
        class DateSpan(date):
            def __sub__(self, other):
                return pd.Timedelta(nanos, unit="ns")
        magnitude, remainder = divmod(abs(nanos), 1000)
        magnitude += int(remainder > 500 or (remainder == 500 and magnitude % 2))
        expected = timedelta(microseconds=magnitude if nanos >= 0 else -magnitude)
        result = Delta(days=1).to_timedelta(DateSpan(2024, 1, 1))
        assert type(result) is timedelta and result == expected
        return True

    add("duration:subclass", "F06", duration_subclass)
    for nanos in (0, 499, 500, 501, 877, 1500, 2500, 999_999_500,
                  86_400_000_000_000-500, -499, -500, -501, -877, -1500, -2500):
        add(f"duration:round:{nanos}", "F07b", lambda nanos=nanos: rounded_duration(nanos))

    def timestamp_duration():
        start = pd.Timestamp("2024-01-01 00:00:00.000000123")
        result = Delta(microseconds=1).to_timedelta(start)
        assert type(result) is timedelta and result == timedelta(microseconds=1)
        return True
    add("duration:timestamp", "F07b", timestamp_duration)

    parent = type("CorrectionSlotParent", (Delta,), {
        "__slots__": ("label",), "__module__": __name__})
    child = type("CorrectionSlotChild", (parent,), {
        "__slots__": ("payload", "owner", "unset", "__private"), "__module__": __name__})
    mixed = type("CorrectionMixedChild", (child,), {
        "__slots__": ("__dict__",), "__module__": __name__})
    globals().update(CorrectionSlotParent=parent, CorrectionSlotChild=child,
                     CorrectionMixedChild=mixed)

    def copied_slots(method, cls, protocol=None):
        value = cls(days=1, hour=9)
        value.label, value.payload, value.owner = "saved", [1, 2], value
        value._CorrectionSlotChild__private = 3
        if cls is mixed:
            value.extra = value.payload
        hash(value)
        result = (pickle.loads(pickle.dumps(value, protocol=protocol)) if method == "pickle"
                  else getattr(copy, method)(value))
        assert type(result) is cls and result is not value
        assert result.label == "saved" and result.payload == [1, 2]
        assert result._CorrectionSlotChild__private == 3 and not hasattr(result, "unset")
        assert result.days == 1 and result.hour == 9 and hash(result) == hash(value)
        assert (result.payload is value.payload) == (method == "copy")
        assert result.owner is (value if method == "copy" else result)
        if cls is mixed:
            assert result.extra is result.payload
        return True

    for cls in (child, mixed):
        for method in ("copy", "deepcopy"):
            add(f"slots:{cls.__name__}:{method}", "F08",
                lambda cls=cls, method=method: copied_slots(method, cls))
        for protocol in range(pickle.HIGHEST_PROTOCOL+1):
            add(f"slots:{cls.__name__}:pickle:{protocol}", "F08",
                lambda cls=cls, protocol=protocol: copied_slots("pickle", cls, protocol))

    def cache_restore():
        from rstimes._native import _restore_delta
        original = Delta(days=1)
        state = original.__getstate__()
        restored = _restore_delta(Delta, state[2], hash(original)+1)
        assert restored == original and hash(restored) == hash(original)
        original.__setstate__((state[0], state[1], state[2], hash(original)+1, state[4]))
        assert hash(original) == hash(Delta(days=1))
        return True

    def previous_pickle():
        path = Path(__file__).with_name("data") / "baseline97.pkl"
        value = pickle.loads(path.read_bytes())
        assert value == Delta(days=1, hour=9)
        return True

    add("restore:cache", "F09", cache_restore)
    add("restore:previous", "F11", previous_pickle)

    def relative_rule(rule, direction):
        calls = []
        class Clears(relativedelta):
            def normalized(self):
                calls.append(True)
                return relativedelta(days=1)
        value = Clears(**({"weekday": MO(1)} if rule == "weekday" else {"leapdays": 1}))
        operations = {
            "factory": lambda: Delta.from_relativedelta(value),
            "add": lambda: Delta() + value, "radd": lambda: value + Delta(),
            "sub": lambda: Delta() - value, "rsub": lambda: value - Delta(),
            "many": lambda: Delta().apply_many([value]),
        }
        raises(ValueError, operations[direction])
        assert not calls
        return True

    for rule in ("weekday", "leapdays"):
        for direction in ("factory", "add", "radd", "sub", "rsub", "many"):
            add(f"dateutil:{rule}:{direction}", "F10",
                lambda rule=rule, direction=direction: relative_rule(rule, direction))

    def relative_callbacks():
        class Introduces(relativedelta):
            def normalized(self):
                return relativedelta(weekday=MO(1))
        class Raises(relativedelta):
            def normalized(self):
                raise RuntimeError("normalization callback")
        raises(ValueError, lambda: Delta.from_relativedelta(Introduces(days=1)))
        raises(RuntimeError, lambda: Delta.from_relativedelta(Raises(days=1)))
        return True
    add("dateutil:callbacks", "F10", relative_callbacks)

    for cls in (np.datetime64, np.timedelta64):
        for unit in ("D", "M", "us", "ns"):
            value = cls("NaT", unit)
            operations = {
                "add": lambda value=value: Delta(days=1) + value,
                "radd": lambda value=value: value + Delta(days=1),
                "rsub": lambda value=value: value - Delta(days=1),
                "method-radd": lambda value=value: Delta(days=1).__radd__(value),
                "many": lambda value=value: Delta(days=1).apply_many([value]),
            }
            if cls is np.timedelta64:
                operations["sub"] = lambda value=value: Delta(days=1) - value
            for direction, operation in operations.items():
                add(f"nat:{cls.__name__}:{unit}:{direction}", "F12",
                    lambda operation=operation: raises(ValueError, operation))

    def normal_numpy():
        delta = Delta(days=1)
        assert type(delta + np.datetime64("2024-01-01", "D")) is datetime
        assert delta + np.timedelta64(2, "D") == Delta(days=3)
        raises(TypeError, lambda: delta + None)
        raises(OverflowError, lambda: delta + np.timedelta64(2**63-1, "D"))
        return True
    add("nat:normal-values", "F12", normal_numpy)

    def stable_method_entries():
        """Protect the public signatures and parser fallback of direct method entries."""
        import inspect
        value = Delta(days=1)
        assert str(inspect.signature(Delta.to_timedelta)) == "(self, /, start=None)"
        assert str(inspect.signature(Delta.apply_many)) == "(self, /, values)"
        assert value.to_timedelta() == value.to_timedelta(None) == value.to_timedelta(start=None)
        assert value.apply_many([]) == value.apply_many(values=[]) == []
        result = value.apply_many(iter([timedelta(days=1)]))
        assert result == [Delta(days=2)] and type(result) is list
        for call in (
            lambda: value.to_timedelta(None, None),
            lambda: value.to_timedelta(None, start=None),
            lambda: value.to_timedelta(unknown=None),
            lambda: Delta.to_timedelta(None),
            lambda: value.apply_many(),
            lambda: value.apply_many([], []),
            lambda: value.apply_many([], values=[]),
            lambda: value.apply_many(items=[]),
            lambda: Delta.apply_many(None, []),
        ):
            raises(TypeError, call)
        return True

    add("entries:public-calls", "F13", stable_method_entries)
    return Delta, records


def correction_performance_cases(package):
    """Return the fixed 66 maintenance inputs and seven equivalent float pairs."""
    import copy
    import pickle
    import numpy as np
    import pandas as pd
    from cytimes import Pydt
    from dateutil.relativedelta import relativedelta
    from zoneinfo import ZoneInfo

    Delta = import_module(package).Delta
    records, float_pairs = [], []

    def add(label, group, run):
        records.append(Case(label, group, ("performance-protection",), run))

    ordinary = {"empty": {}, "days": {"days": 1}, "negative": {"microseconds": -1},
                "mixed": {"days": 2, "hours": 25, "seconds": 61},
                "months": {"months": 13}, "absolute": {"hour": 25}}
    for label, kwargs in ordinary.items():
        add("construct:" + label, "construct", lambda kwargs=kwargs: Delta(**kwargs))
    equivalent = {"weeks": {"days": 10, "hours": 12}, "days": {"days": 1, "hours": 12},
                  "hours": {"hours": 1, "minutes": 30}, "minutes": {"minutes": 1, "seconds": 30},
                  "seconds": {"seconds": 1, "microseconds": 500000},
                  "milliseconds": {"microseconds": 1500}, "microseconds": {"microseconds": 2}}
    for unit, kwargs in equivalent.items():
        float_id, integer_id = "construct:float:" + unit, "construct:equivalent:" + unit
        add(float_id, "construct", lambda kwargs={unit: 1.5}: Delta(**kwargs))
        add(integer_id, "construct", lambda kwargs=kwargs: Delta(**kwargs))
        float_pairs.append((float_id, integer_id))

    left, right = Delta(days=2, hours=3), Delta(days=1, minutes=5)
    for label, run in (("add", lambda: left+right), ("sub", lambda: left-right),
                       ("neg", lambda: -left), ("abs", lambda: abs(left)),
                       ("timedelta-add", lambda: left+timedelta(days=1)),
                       ("timedelta-rsub", lambda: timedelta(days=1)-left)):
        add("arithmetic:" + label, "arithmetic", run)
    dt = datetime(2024, 1, 15, 12)
    fold = datetime(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    pydt = Pydt(2024, 1, 15, 12)
    stamp = pd.Timestamp(dt)
    for label, value, increment in (("date-month", date(2024, 1, 31), Delta(months=1)),
                                   ("datetime-hour", dt, Delta(hours=1)),
                                   ("fold-reuse", fold, Delta()),
                                   ("fold-change", fold, Delta(hours=1)),
                                   ("pydt", pydt, Delta(months=1)),
                                   ("timestamp", stamp, Delta(hours=1))):
        add("date:" + label, "date", lambda value=value, increment=increment: value+increment)
    equal = Delta(days=2, hours=3)
    hash(left)
    for label, run in (("eq", lambda: left==equal), ("ne", lambda: left!=right),
                       ("hash-first", lambda: hash(Delta(days=2, hours=3))),
                       ("hash-cached", lambda: hash(left)), ("getter", lambda: left.days)):
        add("value:" + label, "value", run)
    cls = type("CorrectionBenchmarkChild", (Delta,), {"__module__": __name__})
    globals()["CorrectionBenchmarkChild"] = cls
    child = cls(days=1)
    child.label = "saved"
    payload, child_payload = pickle.dumps(left), pickle.dumps(child)
    for label, run in (("copy", lambda: copy.copy(left)), ("deepcopy", lambda: copy.deepcopy(left)),
                       ("write", lambda: pickle.dumps(left)), ("read", lambda: pickle.loads(payload)),
                       ("child-copy", lambda: copy.copy(child)),
                       ("child-read", lambda: pickle.loads(child_payload))):
        add("state:" + label, "state", run)
    rd, nd, nt = relativedelta(days=2), np.datetime64("2024-01-15", "us"), np.timedelta64(2, "D")
    for label, run in (("rd-convert", lambda: Delta.from_relativedelta(rd)),
                       ("rd-add", lambda: left+rd), ("numpy-date", lambda: left+nd),
                       ("numpy-span", lambda: left+nt)):
        add("thirdparty:" + label, "thirdparty", run)
    for label, run in (("fixed", lambda: left.to_timedelta()),
                       ("date", lambda: Delta(months=1).to_timedelta(date(2024, 1, 31))),
                       ("datetime", lambda: left.to_timedelta(dt))):
        add("duration:" + label, "duration", run)
    increment = Delta(days=1)
    kinds = {"date-datetime": (date(2024, 1, 15), dt), "delta": (left,),
             "timedelta": (timedelta(days=2),), "pydt": (pydt,), "dateutil": (rd,),
             "numpy": (nd, nt), "mixed": (dt, left, timedelta(days=2), rd, nd, pydt, stamp),
             "timestamp": (stamp,)}
    for label, examples in kinds.items():
        for size in (1024, 10000):
            values = [examples[index % len(examples)] for index in range(size)]
            add(f"many:{label}:{size}", "many", lambda values=values: increment.apply_many(values))
    assert len(records) == 66 and len({case.id for case in records}) == 66
    return Delta, records, float_pairs
