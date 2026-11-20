"""Only the supported modern NumPy provider is prepared, with retryable failures."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode', ['valid', 'no_name', 'modern_name', 'nested_name', 'reentrant'])
def test_actual_numpy_provider_failure_retry_cache_and_reentrancy(mode):
    code = r'''
import builtins,json
import numpy as np
from rstimes import parse_to_epoch
modern='numpy._core._multiarray_umath'
legacy='numpy.core._multiarray_umath'
mode=MODE
marker=ModuleNotFoundError('actual provider failure',name=None if mode=='no_name' else modern if mode=='modern_name' else 'numpy.transitive_missing')
original=builtins.__import__
attempts=[]
nested=[]
def guarded(name,*args,**kwargs):
    if name in (modern,legacy):
        attempts.append(name)
    if name==modern:
        if mode=='reentrant' and len(attempts)==1:
            nested.append(parse_to_epoch(np.datetime64(9,'us'),unit='us'))
        elif mode not in ('valid','reentrant'):
            raise marker
    return original(name,*args,**kwargs)
builtins.__import__=guarded
try:
    if mode in ('valid','reentrant'):
        assert parse_to_epoch(np.datetime64(1,'us'),unit='us')==1
    else:
        try:
            parse_to_epoch(np.datetime64(1,'us'),unit='us')
        except ModuleNotFoundError as actual:
            assert actual is marker
        else:
            raise AssertionError('provider failure was swallowed')
finally:
    builtins.__import__=original
assert attempts and legacy not in attempts
assert parse_to_epoch(np.datetime64(1,'us'),unit='us')==1
previous=len(attempts)
builtins.__import__=guarded
try:
    assert parse_to_epoch(np.datetime64(7,'us'),unit='us')==7
finally:
    builtins.__import__=original
assert len(attempts)==previous
assert nested==([9] if mode=='reentrant' else [])
print(json.dumps({'mode':mode,'attempts':attempts,'nested':nested,'retry':1,'hot':7}))
'''.replace('MODE', repr(mode))
    actual = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                            capture_output=True, text=True, timeout=30)
    assert actual.returncode == 0, actual.stdout + actual.stderr
    assert json.loads(actual.stdout)['retry'] == 1
