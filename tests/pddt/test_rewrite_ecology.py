import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt

@pytest.mark.parametrize('indices,kwargs',[([2,0],{}),([True,False],{}),([0.0,1.0],{}),([-1,0],{}),([-1,0],{'allow_fill':True,'fill_value':True}),([0,1],{'axis':0})])
def test_take_preserves_complete_mature_result_or_original_failure(indices,kwargs):
    values=np.array(['2024-01-01','NaT','2024-01-03'],dtype='datetime64[us]')
    x=Pddt(values,name='dates');base=pd.DatetimeIndex(values,name='dates')
    try:expected=base.take(indices,**kwargs)
    except Exception as error:
        with pytest.raises(type(error)) as caught:x.take(indices,**kwargs)
        assert str(caught.value)==str(error)
    else:
        actual=x.take(indices,**kwargs)
        assert actual.array.equals(expected.array) and actual.name==expected.name

@pytest.mark.parametrize('repeats',[2,True,False,2.0,[1,2,0],np.array([2,0,1]),pd.Series([2,0,1])])
def test_repeat_preserves_mature_broadcast_conversion_and_errors(repeats):
    values=np.array(['2024-01-01','NaT','2024-01-03'],dtype='datetime64[us]')
    x=Pddt(values,name='dates');base=pd.DatetimeIndex(values,name='dates')
    try:expected=base.repeat(repeats)
    except Exception as error:
        with pytest.raises(type(error)) as caught:x.repeat(repeats)
        assert str(caught.value)==str(error)
    else:
        actual=x.repeat(repeats)
        assert actual.array.equals(expected.array) and actual.name==expected.name


def test_dataframe_index_selection_boolean_filter_sort_and_membership_work():
    x=Pddt(['2024-01-03','2024-01-01','2024-01-02'],name='dates')
    frame=pd.DataFrame({'value':[3,1,2]},index=x)
    assert frame.loc['2024-01-01','value']==1
    assert frame.sort_index()['value'].tolist()==[1,2,3]
    assert frame.loc[x.is_day([3,9,2]),'value'].tolist()==[3,2]
    assert x.isin([pd.Timestamp('2024-01-02')]).tolist()==[False,False,True]
    assert isinstance(x[0],pd.Timestamp)
    assert x[x.day>1].day.tolist()==[3,2]
    assert x.repeat(1).unit==x.unit


def test_series_arithmetic_alignment_and_comparison_keep_mature_dispatch():
    x=Pddt(['2024-01-01','2024-01-02'])
    values=pd.Series(pd.to_timedelta([1,2],unit='D'),index=['b','a'])
    result=x+values
    assert isinstance(result,pd.Series) and result.index.tolist()==['b','a']
    assert result.dt.day.tolist()==[2,4]
    assert (x==pd.DatetimeIndex(['2024-01-01','2024-01-03'])).tolist()==[True,False]
