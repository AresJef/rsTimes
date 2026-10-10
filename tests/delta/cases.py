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
    id: str
    group: str
    requirements: tuple[str, ...]
    run: object
    difference: str | None = None


def type_name(value):
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
    return {"type": type_name(error), "message": str(error),
            "cause": None if error.__cause__ is None else error_record(error.__cause__)}


def observe(case, Delta):
    try:
        return {"case": case.id, "requirements": case.requirements, "difference": case.difference,
                "result": pack(case.run(), Delta)}
    except Exception as error:
        return {"case": case.id, "requirements": case.requirements, "difference": case.difference,
                "error": error_record(error)}


def date_fixtures():
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
        raise AssertionError("invalid input must fail")

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
        return [issubclass(errors.InvalidRelativeDelta,parent) for parent in
                (TypeError,errors.DeltaError,errors.cyTimesTypeError,errors.cyTimesError,Exception)]
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
    return Delta, output

def candidate_cases(package):
    """D2: validate this package's state contract without submitting it upstream."""
    if package != "rstimes": raise ValueError("New state format belongs only to rstimes")
    import copy
    import pickle
    import sys
    Delta=import_module(package).Delta
    class ContractChild(Delta): pass
    ContractChild.__qualname__="ContractChild"
    globals()["ContractChild"]=ContractChild
    class ConstructorChild(Delta):
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
        assert b"rstimes.delta" in encoded and b"cytimes" not in encoded
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
        tree=ast.parse((package_root/"delta.pyi").read_text())
        klass=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=="Delta")
        methods={node.name for node in klass.body if isinstance(node,ast.FunctionDef)}
        required=set(FIELDS)|{"__init__","from_relativedelta","__add__","__radd__","__sub__","__rsub__","__neg__","__abs__","__eq__","__bool__","__repr__","__hash__"}
        assert required<=methods
        constructor=next(node for node in klass.body if isinstance(node,ast.FunctionDef) and node.name=="__init__")
        assert tuple(arg.arg for arg in constructor.args.args[1:])==PARAMETERS
        assert all(hasattr(Delta,name) for name in required)
        assert set(loaded.__all__)=={"Delta","to_unix_ms","from_unix_ms"}
        return True
    def derived_truth():
        value = Delta(days=1)
        assert bool(value)
        value.__init__()
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
