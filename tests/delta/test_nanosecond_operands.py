"""Full-precision public operand routes, independent of us carrier storage."""

from calendar import monthrange
from datetime import date, datetime, timedelta
import subprocess
import sys

import numpy as np
import pytest

from rstimes import Delta

DAY = 86_400_000_000_000
SCALES = {"Y":31_556_952_000_000_000,"M":2_629_746_000_000_000,
          "W":604_800_000_000_000,"D":DAY,"h":3_600_000_000_000,
          "m":60_000_000_000,"s":1_000_000_000,"ms":1_000_000,"us":1000,"ns":1}


def fixed_ns(value):
    return (value.days*DAY + ((value.hours*60+value.minutes)*60+value.seconds)*1_000_000_000
            + value.microseconds*1000 + value.nanoseconds)


@pytest.mark.parametrize("unit", SCALES)
@pytest.mark.parametrize("ticks", [-1500,-1,0,1,1500])
def test_numpy_duration_all_units_and_ordinary_directions(unit,ticks):
    source = np.timedelta64(ticks,unit)
    delta = Delta(nanoseconds=1500)
    exact = ticks*SCALES[unit]
    assert fixed_ns(delta+source) == exact+1500
    assert fixed_ns(delta-source) == 1500-exact
    if unit in ("Y","M"):
        with pytest.raises(TypeError):
            source+delta
        with pytest.raises(TypeError):
            source-delta
        with pytest.raises(TypeError):
            delta.apply_many([source])
    else:
        assert fixed_ns(source+delta) == exact+1500
        assert fixed_ns(source-delta) == exact-1500
        assert fixed_ns(delta.apply_many([source])[0]) == exact+1500


@pytest.mark.parametrize("unit", SCALES)
@pytest.mark.parametrize("ticks", [-1,0,1,1500])
def test_numpy_datetime_all_units_preserve_output_roles(unit,ticks):
    source = np.datetime64(ticks,unit)
    # NumPy supplies an independent Gregorian day and ordinary us clock;
    # exact remainder is retained separately in the only finer source unit.
    day = source.astype("datetime64[D]").item()
    source_us = int(source.astype("datetime64[us]").astype(np.int64))
    tail = ticks % 1000 if unit == "ns" else 0
    exact = source_us*1000+tail
    # Use integer divmod for nearest-even, avoiding a floating oracle at large epochs.
    quotient,remainder = divmod(exact-1,1000)
    expected = datetime(1970,1,1)+timedelta(microseconds=quotient+(remainder>500 or (remainder==500 and quotient%2)))
    delta = Delta(nanoseconds=-1)
    assert type(delta+source) is datetime
    assert delta+source == expected
    if unit in ("Y","M","W","D"):
        assert type(source+delta) is date
        assert source+delta == day-timedelta(days=1)
        assert type(delta.apply_many([source])[0]) is date
        assert delta.apply_many([source])[0] == day-timedelta(days=1)
    else:
        assert type(source+delta) is datetime
        assert source+delta == expected
        assert delta.apply_many([source])[0] == expected
    with pytest.raises(TypeError):
        delta-source


@pytest.mark.parametrize("kind", ["datetime64","timedelta64"])
@pytest.mark.parametrize("multiplier", [1,2,1000,2**31-1])
def test_numpy_ns_dtype_multiplier_precedes_final_rounding(kind,multiplier):
    source=np.array([3],dtype=f"{kind}[{multiplier}ns]")[0]
    delta=Delta(nanoseconds=500)
    exact=3*multiplier
    if kind == "timedelta64":
        assert fixed_ns(source+delta)==exact+500
        assert fixed_ns(source-delta)==exact-500
    else:
        assert source+delta == datetime(1970,1,1)+timedelta(microseconds=round((exact+500)/1000))
        assert source-delta == datetime(1970,1,1)+timedelta(microseconds=round((exact-500)/1000))


@pytest.mark.parametrize("kind", [np.datetime64,np.timedelta64])
@pytest.mark.parametrize("unit", ["ps","fs","as"])
def test_numpy_finer_unsupported_units_remain_rejected(kind,unit):
    source=kind(1,unit)
    for operation in (lambda: source+Delta(),lambda: Delta()+source,
                      lambda: source-Delta(),lambda: Delta().apply_many([source])):
        with pytest.raises(TypeError):
            operation()


@pytest.mark.parametrize("kind", [np.datetime64,np.timedelta64])
def test_numpy_nat_does_not_erase_into_a_generic_missing_operand(kind):
    source=kind("NaT","ns")
    for operation in (lambda: source+Delta(),lambda: Delta()+source,
                      lambda: source-Delta(),lambda: Delta().apply_many([source])):
        with pytest.raises(ValueError):
            operation()


def test_timestamp_absolute_and_relative_fraction_use_one_exact_clock():
    pd=pytest.importorskip("pandas")
    source=pd.Timestamp("2024-01-01 00:00:00.123456789")
    for delta,expected in [
        (Delta(nanoseconds=1),"2024-01-01 00:00:00.123456790"),
        (Delta(nanosecond=2),"2024-01-01 00:00:00.123456002"),
        (Delta(microsecond=1),"2024-01-01 00:00:00.000001000"),
        (Delta(microsecond=1,nanosecond=2),"2024-01-01 00:00:00.000001002"),
        (Delta(nanosecond=2)+Delta(microsecond=1),"2024-01-01 00:00:00.000001002"),
    ]:
        assert source+delta == pd.Timestamp(expected)
        assert delta+source == pd.Timestamp(expected)
        assert delta.apply_many([source])[0] == pd.Timestamp(expected)
    assert source-Delta(nanoseconds=789) == pd.Timestamp("2024-01-01 00:00:00.123456000")


@pytest.mark.parametrize("ns", [1,500,999,1500,-1,-1500])
def test_pandas_duration_four_directions_keep_true_ticks(ns):
    pd=pytest.importorskip("pandas")
    source=pd.Timedelta(ns,unit="ns")
    delta=Delta(nanoseconds=1)
    assert fixed_ns(source+delta) == ns+1
    assert fixed_ns(delta+source) == ns+1
    assert fixed_ns(source-delta) == ns-1
    assert fixed_ns(delta-source) == 1-ns
    assert fixed_ns(delta.apply_many([source])[0]) == ns+1


def test_timestamp_anchor_rounds_actual_span_after_exact_target():
    pd=pytest.importorskip("pandas")
    source=pd.Timestamp("2024-01-01 00:00:00.000001")
    assert Delta(nanoseconds=500).to_timedelta(source)==timedelta(0)
    assert Delta(nanoseconds=1500).to_timedelta(source)==timedelta(microseconds=2)


@pytest.mark.parametrize("year", [-10000,0,12024,100000])
def test_coarse_wide_timestamp_does_not_force_ns_to_preserve_zero(year):
    pd=pytest.importorskip("pandas")
    source=pd.Timestamp(np.datetime64(f"{year:04d}-01-01","s"))
    assert source+Delta(nanosecond=0) is source
    assert (source+Delta(days=1)).year == year
    assert (source+Delta(days=1)).day == 2


def test_numpy_source_capacity_cannot_be_rescued_by_an_absolute_field():
    source=np.datetime64("12024-01-01","D")
    with pytest.raises((OverflowError,ValueError)):
        Delta(year=2024)+source


@pytest.mark.parametrize("container", [list, tuple, iter])
@pytest.mark.parametrize("text,kwargs,expected", [
    ("2024-01-31T23:59:59.999999000", {"months":1,"days":3,"hours":2},
     datetime(2024,3,4,1,59,59,999999)),
    ("2024-01-31T23:59:59.999999500", {"months":1,"days":3,"hours":2},
     datetime(2024,3,4,2)),
    ("2024-01-31T23:59:59.999998500", {"months":1,"days":3,"hours":2},
     datetime(2024,3,4,1,59,59,999998)),
    ("2024-03-31T00:00:00.000000000", {"months":-1,"days":-3,"hours":-2},
     datetime(2024,2,25,22)),
    ("2024-01-31T23:59:59.999999000", {"months":1,"days":3,"hours":2,"hour":0},
     datetime(2024,3,3,2,59,59,999999)),
    ("2024-01-31T23:59:59.999999000", {"months":1,"days":3,"hours":2,"nanoseconds":1},
     datetime(2024,3,4,1,59,59,999999)),
])
def test_native_batch_calendar_clock_keeps_ns_until_final_projection(container,text,kwargs,expected):
    source=np.datetime64(text,"ns")
    delta=Delta(**kwargs)
    assert source+delta == expected
    result=delta.apply_many(container([source]*3))
    assert result == [expected]*3
    assert all(type(value) is datetime for value in result)


def test_native_batch_varied_microsecond_sources_use_independent_calendar_answers():
    sources=[datetime(2024,1,31,23,59,59,999999)+timedelta(hours=i) for i in range(1024)]
    # The independent standard-library answer selects the actual destination
    # month before adding the fixed days/hours; no rsTimes parser/kernel is used.
    expected=[]
    for source in sources:
        month=source.month+1
        year=source.year+(month>12)
        month=month%12 or 12
        day=min(source.day,monthrange(year,month)[1])
        expected.append(source.replace(year=year,month=month,day=day)+timedelta(days=3,hours=2))
    delta=Delta(months=1,days=3,hours=2)
    assert delta.apply_many(sources) == expected
    assert delta.apply_many([np.datetime64(value,"us") for value in sources]) == expected
    assert delta.apply_many([np.datetime64(value,"us") for value in sources[:1]]) == expected[:1]


@pytest.mark.parametrize("unit", ["Y","M","W","D"])
@pytest.mark.parametrize("hours", [-2,2])
def test_native_batch_coarse_source_keeps_date_exit_with_whole_hours(unit,hours):
    source=np.datetime64("2024-01-31",unit)
    day=source.astype("datetime64[D]").item()
    expected=day-timedelta(days=1) if hours<0 else day
    result=Delta(hours=hours).apply_many([source,source])
    assert result == [expected,expected]
    assert all(type(value) is date for value in result)


def test_numpy_ns_direct_methods_keep_their_separate_reflected_contract():
    delta=Delta(nanoseconds=500)
    duration=np.timedelta64(1500,"ns")
    assert fixed_ns(delta.__add__(duration))==2000
    assert fixed_ns(delta.__sub__(duration))==-1000
    assert fixed_ns(delta.__radd__(duration))==2000
    assert fixed_ns(delta.__rsub__(duration))==1000
    value=np.datetime64("2024-01-01T00:00:00.000001500","ns")
    assert delta.__add__(value)==datetime(2024,1,1,microsecond=2)
    assert delta.__radd__(value)==datetime(2024,1,1,microsecond=2)
    assert delta.__rsub__(value)==datetime(2024,1,1,microsecond=1)
    assert delta.__sub__(value) is NotImplemented
    coarse=np.datetime64("2024-01-01","D")
    assert type(Delta().__radd__(coarse)) is datetime
    assert type(coarse+Delta()) is date


@pytest.mark.parametrize("expression",[
    "np.timedelta64(1500,'ns')+Delta(nanoseconds=1)",
    "np.timedelta64(1500,'ns')-Delta(nanoseconds=1)",
    "np.datetime64('2024-01-01T00:00:00.000001500','ns')+Delta(nanoseconds=1)",
    "Delta(nanoseconds=1).apply_many([np.timedelta64(1500,'ns')])[0]",
])
def test_ns_first_real_use_works_in_a_fresh_process_before_cache_warmup(expression):
    code="from datetime import datetime\nimport numpy as np\nfrom rstimes import Delta\nresult="+expression+"\n"
    if "datetime64" in expression:
        code+="assert result==datetime(2024,1,1,microsecond=2), result\n"
    else:
        expected=1499 if "-Delta" in expression else 1501
        code+=f"assert result==Delta(nanoseconds={expected}), result\n"
    run=subprocess.run([sys.executable,"-I","-c",code],capture_output=True,text=True,timeout=20)
    assert run.returncode==0,run.stderr


@pytest.mark.parametrize("unit,multiplier", [
    (unit, multiplier)
    for unit in SCALES
    for multiplier in (1, 1000 if unit == "ns" else 3)
])
def test_exact_us_numpy_clocks_keep_all_calendar_routes_and_output_roles(unit, multiplier):
    source = np.array(["2024-01-31T23:59:59.123456"],
                      dtype=f"datetime64[{multiplier}{unit}]")[0]
    original = int(source.astype(np.int64))
    base = source.astype("datetime64[us]").item()
    delta = Delta(months=1, days=3, hours=2)

    def expected(sign):
        year, month = divmod(base.year * 12 + base.month - 1 + sign, 12)
        month += 1
        day = min(base.day, monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day) + timedelta(days=sign * 3,
                                                                       hours=sign * 2)

    forward, backward = expected(1), expected(-1)
    result = delta + source
    assert type(result) is datetime and result == forward
    coarse = unit in ("Y", "M", "W", "D")
    result_type = date if coarse else datetime
    if coarse:
        forward, backward = forward.date(), backward.date()
    result = source + delta
    assert type(result) is result_type and result == forward
    result = source - delta
    assert type(result) is result_type and result == backward
    result = delta.apply_many([source])[0]
    assert type(result) is result_type and result == forward
    assert int(source.astype(np.int64)) == original


@pytest.mark.parametrize("unit", ["us", "ns"])
def test_exact_us_numpy_exit_preserves_absolute_calendar_and_weekday_order(unit):
    source = np.datetime64("2024-01-31T23:59:59.999999", unit)
    delta = Delta(year=2023, month=2, day=31, weekday=0, days=3, hours=2)
    forward = datetime(2023, 2, 27, 1, 59, 59, 999999)
    backward = datetime(2023, 2, 20, 21, 59, 59, 999999)
    assert delta + source == forward
    assert source + delta == forward
    assert source - delta == backward
    assert delta.apply_many([source]) == [forward]

