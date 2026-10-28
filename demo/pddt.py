"""Run representative Pddt and parse_to_epoch examples with the adopted wheel.

Run ``python demo/pddt.py`` from any directory. Timings are batch averages for
interactive comparison; the acceptance report contains formal measurements.
"""
from pathlib import Path
import json
import os
import sys


def _launch_selected_environment():
    """Select the shared demo environment before importing rsTimes."""
    here=Path(__file__).resolve()
    selected=json.loads((here.parent/'runtime.json').read_text(encoding='utf-8'))
    environment=(here.parents[1]/selected['environment']).resolve()
    python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if __name__=='__main__' and (Path(sys.prefix).resolve()!=environment or not sys.flags.isolated):
        os.execv(str(python),[str(python),'-I',str(here),*sys.argv[1:]])
    sys.path.insert(0,str(here.parent))


_launch_selected_environment()
import delta as _delta_demo  # Reuse the common version and native identity check.
from datetime import date,datetime,timedelta,timezone
from statistics import median
from importlib.metadata import version
from time import perf_counter_ns
import copy
import pickle
import numpy as np
import pandas as pd
try:
    import polars as pl
except ModuleNotFoundError as error:
    if error.name != "polars":
        raise
    pl = None
from rstimes import Pddt,Configs,Delta,parse_to_epoch,_native


def _show(label,operation,reference=None):
    """Print one result and short batch-average timings for identical work."""
    result=operation()
    print(f'\n{label}\n  rsTimes: {result}')
    calls=16
    def elapsed(call):
        batches=[]
        for _ in range(3):
            start=perf_counter_ns()
            for _ in range(calls):call()
            batches.append((perf_counter_ns()-start)/calls/1000)
        return median(batches)
    print(f'  {elapsed(operation):.3f} us/call (demo only)')
    if reference is not None:
        expected=reference()
        if isinstance(result,pd.Index):
            pd.testing.assert_index_equal(pd.Index(result),pd.Index(expected),exact=False)
        else:assert result==expected,(result,expected)
        print(f'  pandas:  {expected}\n  {elapsed(reference):.3f} us/call (demo only)')


def constructor_demo():
    """Choose a unit before parsing and retain native array precision."""
    text=['2024-01-31 12:30','2024-02-29 12:30']
    _show('Text defaults to microseconds',lambda:Pddt(text),lambda:pd.DatetimeIndex(text))
    _show('Explicit milliseconds',lambda:Pddt(text,unit='ms'),lambda:pd.DatetimeIndex(text,dtype='datetime64[ms]'))
    native=np.array(['2024-01-01T00:00:00.123456789','NaT'],dtype='datetime64[ns]')
    _show('Native nanoseconds and NaT',lambda:Pddt(native),lambda:pd.DatetimeIndex(native))
    _show('Dates outside the nanosecond range',lambda:Pddt(['1000-01-01'],unit='us'))


def calendar_demo():
    """Apply calendar fields in one batch, clipping at the destination month end."""
    x=Pddt(['2024-01-31 12:30','2024-02-29 09:15'])
    for label,call in [('One month later',lambda:x.to_month(1)),
                       ('Combined calendar and clock addition',lambda:x.add(months=2,days=3,hours=4)),
                       ('Absolute fields',lambda:x.replace(month=2,day=28,hour=9)),
                       ('Start of month',lambda:x.to_start_of('M')),
                       ('End of quarter',lambda:x.to_end_of('Q')),
                       ('Next Monday',lambda:x.to_next_weekday('Monday'))]:
        _show(label,call)
    print('Month shifts clip days; adding and subtracting a month need not undo one another.')


def precision_and_query_demo():
    """Convert units, trim fractions, and inspect standard pandas properties."""
    x=Pddt(['2024-02-29 12:34:56.123456789',None])
    _show('Explicit precision trimming',lambda:x.fsp(3))
    _show('Convert to microseconds',lambda:x.as_unit('us'),lambda:pd.DatetimeIndex(x).as_unit('us'))
    print('Standard properties:',x.year.tolist(),x.date.tolist(),x.days_in_month.tolist())
    print('ISO calendar:\n',x.isocalendar())
    other=x-pd.Timedelta(days=2)
    _show('Count crossed day boundaries',lambda:x.diff(other,'D'))


def timezone_demo():
    """Localize calendar values and choose an explicit DST-gap policy."""
    x=Pddt(['2024-03-09 02:30'],tz='America/New_York')
    _show('One calendar day with automatic gap handling',lambda:x.to_day(1))
    _show('Explicit missing-time localization',lambda:Pddt(['2024-03-10 02:30'],tz='America/New_York',nonexistent='shift_forward'))
    _show('Convert the same instant to Shanghai',lambda:x.tz_convert('Asia/Shanghai'),
          lambda:pd.DatetimeIndex(x).tz_convert('Asia/Shanghai'))
    print('Pydt output:',x.datetime(),'timezone names:',x.tzname().tolist())


def configs_and_polars_demo():
    """Use shared text rules and optionally import a Polars datetime column."""
    cfg=Configs();cfg.add_month('mymonth',2)
    _show('Custom month token',lambda:Pddt(['29 mymonth 2024'],cfg=cfg))
    if pl is None:
        print('Polars is optional; this example is skipped.');return
    series=pl.Series('sample',[1704067200000000123,None],dtype=pl.Int64).cast(pl.Datetime('ns','UTC'))
    _show('Polars integer-backed input with a null',lambda:Pddt(series))


def epoch_demo():
    """Return one integer in the requested unit, without building a datetime."""
    inputs=[('Nanosecond text','1970-01-01T00:00:00.000000123','ns'),
            ('Aware instant','1970-01-01T08:00:00+08:00','us'),
            ('Typed NumPy value',np.datetime64('1970-01-01T00:00:00.123456789','ns'),'ns'),
            ('Python date',date(1970,1,2),'s'),
            ('Numeric seconds',1,'ms')]
    for label,value,unit in inputs:_show(label,lambda value=value,unit=unit:parse_to_epoch(value,unit))
    print('Numeric units differ intentionally:',Pddt([1],unit='ms')[0],
          'versus parse_to_epoch(1, unit="ms") =',parse_to_epoch(1,'ms'))


def copy_and_pickle_demo():
    """Retain values, unit, timezone, name, and frequency in saved copies."""
    x=Pddt.date_range('2024-01-01',periods=3,tz='UTC',name='sample',unit='us')
    reference = pd.DatetimeIndex(x)
    for label, operation, comparison in [
        ('copy', lambda:copy.copy(x), lambda:copy.copy(reference)),
        ('deepcopy', lambda:copy.deepcopy(x), lambda:copy.deepcopy(reference)),
        ('pickle', lambda:pickle.loads(pickle.dumps(x)),
         lambda:pickle.loads(pickle.dumps(reference))),
    ]:
        _show(label, operation, comparison)


def formatted_range_repair_demo():
    """Show literal format digits and lossless explicit endpoint units."""
    value = Pddt.strptime(["2024001"], "%Y0%m")
    assert value.year.tolist() == [2024] and value.month.tolist() == [1]
    print("\nNumeric literal in strptime:", value)
    try:
        Pddt.date_range("1970-01-01", end="1970-01-01 00:00:01.5", freq="s", unit="s")
    except ValueError as error:
        assert "end" in str(error) and "unit" in str(error)
        print("A supplied endpoint must fit the explicit unit:", error)
    else:
        raise AssertionError("A half-second endpoint cannot be preserved as whole seconds")
    exact = Pddt.date_range("1970-01-01", end="1970-01-01 00:00:01.5", freq="s", unit="ms")
    assert exact.asi8.tolist() == [0, 1000]
    print("The same range with millisecond storage:", exact)


def review_repair_demo():
    """Show real operand callbacks, empty metadata and lossless UTC endpoints."""
    class BusinessDelta(Delta):
        def __radd__(self, value):
            return value + timedelta(days=2)

    source = Pddt(["2024-01-01", "2024-01-03"], unit="s")
    adjusted = source + [BusinessDelta(days=1), BusinessDelta(days=1)]
    assert adjusted.asi8.tolist() == [1704240000, 1704412800]
    print("\nColumn arithmetic executes the subclass rule:", adjusted)

    empty = Pddt.fromdatetime(datetime(2024, 1, 1, tzinfo=timezone.utc), size=0)
    assert len(empty) == 0 and empty.tz == timezone.utc
    print("An empty scalar factory retains its source timezone:", empty)

    zone = timezone(timedelta(microseconds=1))
    start = datetime(2024, 1, 1, 9, 0, 0, 1, tzinfo=zone)
    exact = Pddt.date_range(start, periods=2, freq=pd.DateOffset(days=1), unit="s")
    assert exact.asi8.tolist() == [1704099600, 1704186000] and exact.unit == "s"
    print("Finer local coordinates can produce exact UTC seconds:", exact)


def main():
    """Run all examples with the verified, currently adopted local package."""
    print(f"rsTimes {version('rstimes')} | {_native.__file__}")
    print('Pddt / parse_to_epoch demo; pandas',pd.__version__)
    for demo in (constructor_demo,calendar_demo,precision_and_query_demo,timezone_demo,
                 configs_and_polars_demo,epoch_demo,formatted_range_repair_demo,
                 review_repair_demo,copy_and_pickle_demo):demo()


if __name__=='__main__':main()
