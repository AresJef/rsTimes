"""Actual descriptor callbacks keep their owners through invocation."""
import copy
import gc
import weakref
from datetime import timedelta

import pytest

from rstimes import Delta


@pytest.mark.parametrize('host', ['pddt', 'pldt'])
def test_selected_descriptor_is_owned_until_after_its_returned_callable(host):
    if host == 'pddt':
        pytest.importorskip('pandas')
        from rstimes import Pddt
        source = Pddt(['2024-01-01'], unit='s')
    else:
        pytest.importorskip('polars')
        from rstimes import Pldt
        source = Pldt(['2024-01-01'], unit='ns')
    events = []
    class Selected:
        def __get__(self, instance, owner):
            events.append('bind')
            del owner.__radd__
            def run(other):
                gc.collect()
                assert events == ['bind']
                events.append('call')
                return other + timedelta(days=1)
            return run
        def __del__(self):
            events.append('retired')
    class Business(Delta):
        pass
    rule = Selected()
    reference = weakref.ref(rule)
    Business.__radd__ = rule
    del rule
    result = source + [Business()]
    actual = result.day.tolist() if host == 'pddt' else result.pldt.day.to_list()
    assert actual == [2]
    gc.collect()
    assert reference() is None and events == ['bind', 'call', 'retired']


@pytest.mark.parametrize('operation', [copy.copy, copy.deepcopy, lambda value: value.__copy__()])
def test_real_getset_descriptor_rejects_an_incompatible_owner(operation):
    class Foreign:
        pass
    class Business(Delta):
        __dict__ = Foreign.__dict__['__dict__']
    with pytest.raises(TypeError, match='descriptor|apply'):
        operation(Business(nanoseconds=1))
