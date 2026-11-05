from datetime import datetime, timedelta
from typing_extensions import assert_type
import numpy as np
import pandas as pd
from rstimes import Delta, Configs, Pydt, Pddt, parse, parse_str, parse_to_epoch

cfg = Configs()
assert_type(parse_str('2024-01-01', strict=False, cfg=cfg), datetime)
assert_type(parse(datetime(2024, 1, 1)), datetime)
assert_type(parse_to_epoch('2024-01-01', unit='us'), int)
delta = Delta(months=1, days=1.5, hour=None)
assert_type(delta.to_timedelta(), timedelta)
p = Pydt(2024, 1, 1)
assert_type(p.day_of_year, int)
assert_type(p.days_in_month, int)
assert_type(p.is_leap_year, bool)
assert_type(p.weekday(), int)
assert_type(p + delta, Pydt)
assert_type(p - datetime(2024, 1, 1), timedelta)
x = Pddt(['2024-01-01', None], unit='us')
assert_type(x.to_date(day=[1, None]), Pddt)
assert_type(x.add(months=[1, 2]), Pddt)
assert_type(x.diff(['2024-01-01', '2024-01-02'], 'D'), pd.Index)
assert_type(x.as_unit('ms', round_ok=True), Pddt)
assert_type(x.snap(unit='Monday'), Pddt)
assert_type(x.round(freq='15min'), Pddt)
assert_type(x.datetime(), np.ndarray)
assert_type(Pddt.fromseconds([0, 1], unit='us'), Pddt)
assert_type(Pddt.frommicroseconds([0, 1], unit='us'), Pddt)
assert_type(Pddt.date_range('2024-01-01', periods=2), Pddt)

assert_type(p.to_date(month=2), Pydt)
assert_type(p.to_datetime(month=np.int64(2), hour=0), Pydt)

# F01 namespace return and D04/E05 target keywords remain fully typed.
assert_type(x.pddt.replace(day=3), Pddt)
assert_type(Pddt.fromisoformat(["2024-01-01"], tz="UTC", ambiguous=False), Pddt)
assert_type(Pddt.strptime(["2024-01-01"], "%Y-%m-%d", tz="UTC"), Pddt)

class DateIndex(Pddt):
    pass

assert_type(DateIndex(["2024-01-01"]).pddt.replace(day=2), DateIndex)
