"""Prove the minimum native package and genuine pandas subclass installation."""
import pickle
import numpy as np
import pandas as pd
import pytest
from rstimes import Pddt, Pydt, Delta, parse

@pytest.mark.parametrize('unit',['s','ms','us','ns'])
def test_native_unit_and_nat(unit):
    values=np.array([0,1,-9223372036854775808],dtype='i8').view('datetime64['+unit+']')
    result=Pddt(values,name='sample')
    assert isinstance(result,pd.DatetimeIndex)
    assert type(result) is Pddt
    assert result.unit==unit
    assert result.asi8.tolist()==[0,1,-9223372036854775808]
    assert result.name=='sample'
    assert isinstance(result[:1],Pddt)

def test_existing_modules_still_import_and_run():
    assert Pydt(2024,1,1).add(days=1).day==2
    assert (Pydt(2024,1,1)+Delta(days=1)).day==2
    assert parse('2024-01-02').day==2
