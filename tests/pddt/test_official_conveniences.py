"""Common convenience behavior against the immutable official 3.1.0 wheel.

Default resolution, standard properties, strict errors, NaT fixes and fixed-unit
precision are checked independently; they are approved differences.
"""
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt

pytestmark=pytest.mark.skipif(not pd.__version__.startswith('2.3.'),reason='official 3.1.0 comparison uses its compatible fixed pandas 2.3 environment')

CASES=[
 ('to_curr_year',(),{'month':'Feb','day':31}),('to_prev_year',(),{}),('to_next_year',(),{}),
 ('to_year',(-2,),{'month':12,'day':31}),
 ('to_curr_quarter',(),{'month':2,'day':31}),('to_prev_quarter',(),{}),('to_next_quarter',(),{}),('to_quarter',(-2,),{'month':1,'day':1}),
 ('to_curr_month',(),{'day':31}),('to_prev_month',(),{}),('to_next_month',(),{}),('to_month',(-13,),{'day':29}),
 ('to_monday',(),{}),('to_tuesday',(),{}),('to_wednesday',(),{}),('to_thursday',(),{}),('to_friday',(),{}),('to_saturday',(),{}),('to_sunday',(),{}),
 ('to_curr_weekday',('Friday',),{}),('to_prev_weekday',(),{}),('to_next_weekday',(),{}),('to_weekday',(-3,'Monday'),{}),
 ('to_yesterday',(),{}),('to_tomorrow',(),{}),('to_day',(-10,),{}),
 ('replace',(),{'year':2022,'month':2,'day':31,'hour':25}),
 ('to_datetime',(),{'month':12,'hour':9,'minute':45,'microsecond':123456,'nanosecond':789}),
 ('to_date',(),{'year':2020,'month':2,'day':31}),('to_time',(),{'hour':25,'minute':99,'second':99}),
 ('to_first_of',('Y',),{}),('to_first_of',('Q',),{}),('to_first_of',('M',),{}),('to_first_of',('W',),{}),
 ('to_last_of',('Q',),{}),('to_last_of',('February',),{}),
 ('to_start_of',('Y',),{}),('to_start_of',('D',),{}),('to_start_of',('ms',),{}),
 ('to_end_of',('M',),{}),('to_end_of',('h',),{}),('to_end_of',('us',),{}),
 ('normalize',(),{}),('fsp',(3,),{}),('fsp',(7,),{}),
 ('round',('s',),{}),('ceil',('s',),{}),('floor',('s',),{}),
 ('add',(),{'years':1,'quarters':2,'months':-3,'days':-2,'hours':25,'microseconds':123}),
 ('sub',(),{'months':13,'hours':25,'microseconds':123}),
 ('days_in_year',(),{}),('days_bf_year',(),{}),('day_of_year',(),{}),
 ('days_in_quarter',(),{}),('days_bf_quarter',(),{}),('day_of_quarter',(),{}),('days_bf_month',(),{}),
 ('is_year',(2024,),{}),('is_month',('February',),{}),('is_weekday',('Sunday',),{}),
 ('is_first_of',('M',),{}),('is_last_of',('Y',),{}),('is_start_of',('s',),{}),('is_end_of',('s',),{}),
 ('toordinal',(),{}),('toseconds',(),{}),('tomicroseconds',(),{}),('leap_bt_year',(1900,),{}),
]

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
@pytest.mark.parametrize('tz',[None,'UTC','America/New_York'])
@pytest.mark.parametrize('name,args,kwargs',CASES,ids=[x[0]+str(i) for i,x in enumerate(CASES)])
def test_official_shared_conveniences(unit,tz,name,args,kwargs):
    from cytimes import Pddt as Original
    values=np.array(['2020-02-29T12:34:56.123456789','2023-01-31T09:10:11.987654321','2024-05-08T00:00:00','2024-12-31T23:59:59.999999999'],dtype='datetime64[ns]').astype('datetime64['+unit+']')
    rust=Pddt(values,tz=tz);original=Original(values,tz=tz)
    if name in ('replace','to_time') and kwargs.get('hour') == 25:
        with pytest.raises(ValueError,match='hour'):
            getattr(rust.pddt if name == "replace" else rust,name)(*args,**kwargs)
        return
    if (name == 'to_datetime' and unit != 'ns'
            or name in ('add','sub') and unit in ('s','ms')):
        with pytest.raises(ValueError,match='requested unit'):
            getattr(rust.pddt if name == "replace" else rust,name)(*args,**kwargs)
        return
    a=getattr(rust.pddt if name == "replace" else rust,name) if name == 'day_of_year' else getattr(rust.pddt if name == "replace" else rust,name)(*args,**kwargs)
    b=getattr(original,name)(*args,**kwargs)
    if isinstance(a,pd.DatetimeIndex):
        assert a.unit==b.unit
        np.testing.assert_array_equal(a.asi8,b.asi8)
        assert str(a.tz)==str(b.tz)
    elif name=='toseconds' and unit=='ns':
        from fractions import Fraction
        expected=np.array([float(Fraction(int(t),1000000000)) for t in rust.values_naive.view('i8')])
        np.testing.assert_array_equal(np.asarray(a),expected)
    else:
        np.testing.assert_array_equal(np.asarray(a),np.asarray(b))
