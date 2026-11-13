"""Shared calendar behavior and approved final-month clamping changes."""
from datetime import datetime,timedelta
from itertools import product
import pytest
from rstimes import Pydt
from cytimes import Pydt as Official

CALLS=[('to_year',(1,2,29)),('to_curr_year',('Sep',31)),('to_prev_year',()),('to_next_year',()),
 ('to_quarter',(1,2,31)),('to_curr_quarter',(3,31)),('to_prev_quarter',()),('to_next_quarter',()),
 ('to_month',(-2,)),('to_curr_month',(31,)),('to_prev_month',()),('to_next_month',()),
 ('to_weekday',(1,0)),('to_curr_weekday',('Sunday',)),('to_prev_weekday',()),('to_next_weekday',()),
 ('to_monday',()),('to_tuesday',()),('to_wednesday',()),('to_thursday',()),('to_friday',()),('to_saturday',()),('to_sunday',()),
 ('to_day',(40,)),('to_yesterday',()),('to_tomorrow',()),('normalize',()),
 ('to_datetime',(2025,6,30,25,90,70,2000000)),('to_date',(2024,2,29)),('to_time',(25,61,60,1000000))]
DATES=[(2024,1,31),(2024,2,29),(2024,5,7),(1900,3,1),(2000,12,31)]

@pytest.mark.parametrize('ymd,call',list(product(DATES,CALLS)))
def test_calendar_adjustments_equal_official(ymd,call):
 name,args=call;p=Pydt(*ymd,15,30,1,123456);o=Official(*ymd,15,30,1,123456,fold=0)
 if name in ('to_datetime','to_time') and 25 in args:
  with pytest.raises(ValueError, match='hour'): getattr(p,name)(*args)
  return
 actual=getattr(p,name)(*args);expected=getattr(o,name)(*args)
 assert actual==expected
 assert type(actual) is Pydt
 assert actual.fold==0

@pytest.mark.parametrize('unit',['Y','Q','M','W','D','h','m','min','s','ms','us','ns','Jan','September','三月','Mon','Sunday','星期三'])
@pytest.mark.parametrize('method',['to_first_of','to_last_of','to_start_of','to_end_of'])
def test_boundaries_equal_official(unit,method):
 p=Pydt(2024,5,7,15,30,1,123456);o=Official(2024,5,7,15,30,1,123456,fold=0)
 try: expected=getattr(o,method)(unit)
 except (ValueError,TypeError):
  with pytest.raises((ValueError,TypeError)): getattr(p,method)(unit)
 else:
  actual=getattr(p,method)(unit)
  assert actual==expected
  assert getattr(actual,method.replace('to_','is_'))(unit)

@pytest.mark.parametrize('ymdhms',[(1969,12,31,23,59,59,999500),(2024,5,7,15,30,30,500000),(2024,5,7,15,31,30,500000)])
@pytest.mark.parametrize('method',['round','floor','ceil'])
@pytest.mark.parametrize('unit',['D','h','m','min','s','ms','us','ns'])
def test_rounding_equal_official(ymdhms,method,unit):
 p=Pydt(*ymdhms);o=Official(*ymdhms,fold=0)
 assert getattr(p,method)(unit)==getattr(o,method)(unit)

@pytest.mark.parametrize('precision',[0,1,2,3,4,5,6,7])
def test_fractional_precision(precision):
 p=Pydt(2024,5,7,15,30,1,123456)
 result=p.fsp(precision)
 assert result==Official(2024,5,7,15,30,1,123456,fold=0).fsp(precision)
 if precision>=6: assert result is p

def test_final_day_clamp_and_standard_replace_differ():
 p=Pydt(2024,1,31,12)
 assert p.to_date(month=2)==datetime(2024,2,29,12)
 assert p.to_datetime(month=2)==datetime(2024,2,29,12)
 with pytest.raises(ValueError): p.replace(month=2)

def test_integer_roles_no_longer_truncate_floats():
 p=Pydt(2024,1,31)
 for call in (lambda:p.to_month(1.9),lambda:p.to_day(-1.9),
              lambda:p.to_time(hour=25.9),lambda:p.fsp(3.9),
              lambda:Pydt.fromordinal(738886.9),
              lambda:Pydt.frommicroseconds(-1.9)):
  with pytest.raises(TypeError):call()
 with pytest.raises(ValueError):p.to_time(hour=25)
 for n in (float('nan'),float('inf')):
  with pytest.raises(TypeError):p.to_day(n)
 with pytest.raises(OverflowError):p.to_day(1<<40)

