"""Frozen pandas3 range answers, independent of the installed pandas major."""
from datetime import timedelta,time
from pathlib import Path
from types import SimpleNamespace
import json
import os
import numpy as np
import pandas as pd

_PATH=Path(__file__).with_name('data')/'fixed-pandas3-ranges.json'
_RECORD=os.environ.get('RSTIMES_RECORD_FIXED_PANDAS3')
_DATA={} if _RECORD else json.loads(_PATH.read_text())['cases']


def _encode(value):
    if isinstance(value,pd.DateOffset):
        return {'offset':type(value).__name__,'n':value.n,'normalize':value.normalize,
                'kwargs':{k:_encode(v) for k,v in value.kwds.items() if k!='calendar'}}
    if isinstance(value,time):return {'clock':value.isoformat()}
    if isinstance(value,timedelta):return {'duration':[value.days,value.seconds,value.microseconds]}
    if isinstance(value,np.datetime64):return {'numpy_date':[str(value.dtype),int(value.view('int64'))]}
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,tuple):return {'tuple':[_encode(v) for v in value]}
    if isinstance(value,list):return [_encode(v) for v in value]
    if isinstance(value,dict):return {k:_encode(v) for k,v in value.items()}
    return value


def _decode(value):
    if isinstance(value,dict):
        if 'offset' in value and 'n' in value and 'kwargs' in value:return getattr(pd.offsets,value['offset'])(value['n'],normalize=value['normalize'],**_decode(value['kwargs']))
        if 'clock' in value:return time.fromisoformat(value['clock'])
        if 'duration' in value:return timedelta(*value['duration'])
        if 'numpy_date' in value:
            dtype,tick=value['numpy_date'];return np.array(tick,dtype='int64').view(dtype)[()]
        if 'tuple' in value:return tuple(_decode(v) for v in value['tuple'])
        return {k:_decode(v) for k,v in value.items()}
    if isinstance(value,list):return [_decode(v) for v in value]
    return value


def date_range(*args,**kwargs):
    key=json.dumps(_encode([list(args),kwargs]),sort_keys=True,separators=(',',':'))
    if _RECORD:
        assert pd.__version__=='3.0.6'
        result=pd.date_range(*args,**kwargs)
        item={'unit':result.unit,'ticks':result.asi8.tolist(),'freq':_encode(result.freq)}
        if key in _DATA:assert _DATA[key]==item
        _DATA[key]=item
        _PATH.parent.mkdir(exist_ok=True)
        _PATH.write_text(json.dumps({'pandas':'3.0.6','pandas_path':pd.__file__,'cases':_DATA},ensure_ascii=False,indent=2)+'\n')
        return result
    item=_DATA[key]
    return SimpleNamespace(unit=item['unit'],asi8=np.array(item['ticks'],dtype='int64'),freq=_decode(item['freq']))
