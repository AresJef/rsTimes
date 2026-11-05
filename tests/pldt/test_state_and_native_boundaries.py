"""L01-L04: independent buffers, real business protocols and native containers."""
import copy
import gc
import pickle

import numpy as np
import polars as pl
import pytest

from rstimes import Delta, Pldt
from rstimes._pldt_state import restore


class Business(Pldt):
    __slots__ = ('label', 'unset')
    new_calls = 0
    init_calls = 0
    def __new__(cls, data, **kwargs):
        cls.new_calls += 1
        return super().__new__(cls)
    def __init__(self, data, **kwargs):
        type(self).init_calls += 1
        super().__init__(data, **kwargs)


def ticks(value):
    return value.to_physical().to_list()


@pytest.mark.parametrize('unit', ['ms', 'us', 'ns'])
@pytest.mark.parametrize('zone', [None, 'UTC', 'America/New_York'])
def test_core_copy_and_pickle_keep_full_domain_validity_and_metadata(unit, zone):
    values = [-(1 << 63), None, -(1 << 63) + 1, (1 << 63) - 1]
    x = Pldt(pl.Series('time', values, dtype=pl.Int64).cast(pl.Datetime(unit, zone)))
    for result in [copy.copy(x), copy.deepcopy(x), *[pickle.loads(pickle.dumps(x, protocol=p)) for p in (0, 2, 4, 5)]]:
        assert type(result) is Pldt and result is not x
        assert result.dtype == x.dtype and result.name == 'time'
        assert result.is_null().to_list() == [False, True, False, False]
        assert ticks(result) == values
    assert ticks(x) == values


def test_business_dict_slots_cycles_aliases_and_no_initialization_on_restore():
    x = Business([0, None, 123456789], unit='ns', name='events')
    shared = ['business']
    x._business = shared
    x.label = shared
    x.reference = x
    _ = x.dt
    _ = x.pldt
    state = x.__getstate__()
    assert state[0]['_business'] is shared and state[1]['label'] is shared
    assert '_s' not in state[0] and 'dt' not in state[0] and 'pldt' not in state[0]
    assert 'unset' not in state[1]
    before = Business.new_calls, Business.init_calls
    shallow = copy.copy(x)
    deep = copy.deepcopy(x)
    loaded = pickle.loads(pickle.dumps(x))
    assert (Business.new_calls, Business.init_calls) == before
    assert shallow is not x and shallow.label is shared and shallow.reference is x
    assert shallow.__dict__ is not x.__dict__
    for result in (deep, loaded):
        assert type(result) is Business and ticks(result) == [0, None, 123456789]
        assert result.label is result._business and result.label is not shared
        assert result.reference is result
        assert not hasattr(result, 'unset')
        assert 'dt' not in result.__dict__ and 'pldt' not in result.__dict__
        assert result.pldt._series is result
    shallow.append(Pldt([5], unit='ns'))
    assert len(shallow) == 4 and len(x) == 3


def test_deepcopy_uses_the_actual_supplied_memo_for_business_aliases():
    x = Business([0])
    original = ['original']
    replacement = ['supplied']
    x.label = original
    x.alias = original
    x.reference = x
    memo = {id(original): replacement}
    result = copy.deepcopy(x, memo)
    assert result.label is replacement and result.alias is replacement
    assert result.reference is result and memo[id(x)] is result


@pytest.mark.parametrize('unit', ['ms', 'us', 'ns'])
def test_physical_deep_buffers_are_distinct_shallow_buffers_can_share(unit):
    array = np.array([-(1 << 63), 0, (1 << 63) - 1], dtype=np.int64)
    x = Pldt(array, unit=unit)
    shallow, deep = copy.copy(x), copy.deepcopy(x)
    original = x.to_physical().to_numpy()
    shallow_array = shallow.to_physical().to_numpy()
    deep_array = deep.to_physical().to_numpy()
    assert original.ctypes.data == shallow_array.ctypes.data
    assert original.ctypes.data != deep_array.ctypes.data
    array[1] = 100
    assert ticks(deep) == [-(1 << 63), 0, (1 << 63) - 1]
    del array, x, original
    gc.collect()
    assert ticks(deep) == [-(1 << 63), 0, (1 << 63) - 1]
    assert len(shallow) == 3


@pytest.mark.parametrize('method,args', [
    ('to_next_month', ()), ('add', ()), ('as_unit', ('ns',)),
    ('normalize', ()), ('snap', ('D',)),
])
def test_owned_date_results_invoke_one_normal_business_constructor(method, args):
    x = Business(['2024-01-31T12:00'], unit='ns')
    before = Business.new_calls, Business.init_calls
    result = getattr(x, method)(*args)
    assert type(result) is Business
    assert (Business.new_calls - before[0], Business.init_calls - before[1]) == (1, 1)
    before = Business.new_calls, Business.init_calls
    _ = x.year
    _ = x.toseconds()
    _ = x.datetime()
    assert (Business.new_calls, Business.init_calls) == before


def test_real_reduce_copy_and_state_failures_keep_the_original_protocol():
    original = RuntimeError('business reduction failure')
    class Bad(Pldt):
        def __reduce_ex__(self, protocol):
            raise original
    x = Bad([0])
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(RuntimeError) as caught:
            operation(x)
        assert caught.value is original
    class Custom(Pldt):
        def __copy__(self):
            return 'real shallow'
        def __deepcopy__(self, memo):
            return memo['actual']
    x = Custom([0])
    assert copy.copy(x) == 'real shallow'
    assert copy.deepcopy(x, {'actual': 'real deep'}) == 'real deep'
    class Reduce(Pldt):
        def __reduce__(self):
            return str, ('real reduce',)
    assert copy.copy(Reduce([0])) == 'real reduce'
    assert copy.deepcopy(Reduce([0])) == 'real reduce'
    class State(Pldt):
        def __getstate__(self):
            raise original
    with pytest.raises(RuntimeError) as caught:
        copy.deepcopy(State([0]))
    assert caught.value is original


def test_custom_reduction_list_iterators_and_shared_business_values():
    shared = ['value']
    class Custom(Pldt):
        def __reduce_ex__(self, protocol):
            return list, (), None, iter((shared, shared))
    x = Custom([0])
    shallow = copy.copy(x)
    deep = copy.deepcopy(x)
    assert shallow[0] is shallow[1] is shared
    assert deep[0] is deep[1] and deep[0] is not shared


def test_reduce_core_does_not_expose_native_owner_or_mutable_internal_cache():
    x = Pldt([-(1 << 63), None, 1], unit='ns')
    _ = x.pldt
    recipe = x.__reduce__()
    assert recipe[1][1:3] == ('rstimes.pldt', 1)
    assert type(recipe[1][3]) is bytes and type(recipe[1][4]) is bytes
    assert recipe[2] is None
    args = list(recipe[1])
    args[3] = (7).to_bytes(8, 'little', signed=True) + args[3][8:]
    result = restore(*args)
    assert ticks(result) == [7, None, 1] and ticks(x) == [-(1 << 63), None, 1]


@pytest.mark.parametrize('index,replacement,error', [
    (0, str, TypeError), (1, 'rstimes.pddt', ValueError), (2, True, TypeError), (2, 2, ValueError),
    (3, bytearray(24), TypeError), (3, b'bad', ValueError),
    (4, b'\x00\x00', ValueError), (4, b'\xff', ValueError),
    (5, 's', ValueError), (5, None, TypeError), (6, 'Unknown/Zone', ValueError),
    (7, None, TypeError), (8, True, TypeError), (8, 3, ValueError),
])
def test_core_restore_validates_marker_version_length_mask_unit_and_metadata(index, replacement, error):
    x = Pldt([0, None, 1], unit='ns')
    args = list(x.__reduce__()[1])
    args[index] = replacement
    with pytest.raises(error):
        restore(*args)
    assert ticks(x) == [0, None, 1]


def test_default_business_restore_cannot_replace_validated_core():
    x = Pldt([0])
    with pytest.raises(ValueError, match='core'):
        x.__setstate__({'_s': object()})
    with pytest.raises(TypeError):
        x.__setstate__(({}, {'bad': 1, 42: 2}))
    assert ticks(x) == [0]


def test_original_native_slices_containers_and_source_owner_are_preserved():
    x = Pldt([123456789, None, 223456789], unit='ns', name='time')
    result = x[0:1]
    assert type(result) is Pldt and ticks(result) == [123456789]
    assert result.dtype == pl.Datetime('ns') and result.name == 'time'
    assert x[0].microsecond == 123456 and x[1] is None
    native = pl.Series(x)
    assert x.diff().equals(native.diff())
    assert x.filter(x.is_not_null()).to_physical().to_list() == [123456789, 223456789]
    assert x.gather([2, 0]).to_physical().to_list() == [223456789, 123456789]
    del x, native
    gc.collect()
    assert ticks(result) == [123456789]


def test_sorted_claim_is_preserved_only_when_compatible_with_restored_values():
    x = Pldt([0, 1, 2], unit='ns').set_sorted()
    assert x.flags['SORTED_ASC']
    assert copy.copy(x).flags['SORTED_ASC']
    assert copy.deepcopy(x).flags['SORTED_ASC']
    assert pickle.loads(pickle.dumps(x)).flags['SORTED_ASC']
    args = list(x.__reduce__()[1])
    args[3] = np.array([2, 0, 1], dtype='<i8').tobytes()
    result = restore(*args)
    assert ticks(result) == [2, 0, 1]
    assert not result.flags['SORTED_ASC'] and not result.flags['SORTED_DESC']


def test_core_snapshot_precedes_a_real_state_hook_that_mutates_the_source_shell():
    class Mutating(Pldt):
        def __getstate__(self):
            self.append(Pldt([2], unit='ns'))
            return {'saved': 'business'}
    for operation in (copy.copy, copy.deepcopy):
        x = Mutating([0, 1], unit='ns')
        result = operation(x)
        assert ticks(x) == [0, 1, 2]
        assert ticks(result) == [0, 1] and result.saved == 'business'


def test_custom_state_setter_receives_its_original_state_and_exception():
    class Custom(Pldt):
        def __getstate__(self):
            return 42
        def __setstate__(self, state):
            self.business = state
    for operation in (copy.copy, copy.deepcopy):
        assert operation(Custom([0])).business == 42
    original = RuntimeError('real state setter')
    class Bad(Custom):
        def __setstate__(self, state):
            raise original
    with pytest.raises(RuntimeError) as caught:
        copy.deepcopy(Bad([0]))
    assert caught.value is original


def test_business_date_constructor_may_return_its_normal_foreign_result():
    class Foreign(Pldt):
        return_foreign = False
        def __new__(cls, data, **kwargs):
            return ['business'] if cls.return_foreign else super().__new__(cls)
    x = Foreign(['2024-01-31'])
    Foreign.return_foreign = True
    assert x.to_next_month() == ['business']
    assert x.pldt.to_next_month() == ['business']


def test_ordinary_native_expr_serialization_keeps_plugin_rules_without_wrapper():
    import io
    expr = pl.col('time').pldt.add_delta(Delta(nanoseconds=1)).pldt.strftime('%S%.9f')
    assert type(expr) is pl.Expr
    restored = [pickle.loads(pickle.dumps(expr)), pl.Expr.deserialize(io.BytesIO(expr.meta.serialize()))]
    frame = pl.DataFrame({'time': Pldt([0, None], unit='ns')})
    for result in restored:
        assert type(result) is pl.Expr
        assert frame.select(result)['time'].to_list() == ['00.000000001', None]


def test_other_date_classes_import_a_real_business_column_without_source_construction():
    from rstimes._optional import PANDAS
    if PANDAS is None:
        pytest.skip('Pddt requires optional pandas')
    from rstimes import Pddt
    source = Business([0, None, 123456789], unit='ns', name='time')
    before = Business.new_calls, Business.init_calls
    plain = Pldt(source)
    pandas = Pddt(source)
    assert ticks(plain) == [0, None, 123456789]
    assert pandas.unit == 'ns' and pandas.asi8.tolist() == [0, -(1 << 63), 123456789]
    assert (Business.new_calls, Business.init_calls) == before


@pytest.mark.parametrize('dtype', [pl.Int64, pl.String, pl.Date, pl.Boolean])
def test_native_dtype_changing_results_have_plain_series_output_roles(dtype):
    x = Pldt([0, 1], unit='ns', name='time')
    try:
        expected = pl.Series(x).cast(dtype)
    except Exception as original:
        with pytest.raises(type(original)) as caught:
            x.cast(dtype)
        assert caught.value.args == original.args
        return
    result = x.cast(dtype)
    assert type(result) is pl.Series
    assert result.dtype == dtype
    assert type(copy.copy(result)) is pl.Series
    assert type(copy.deepcopy(result)) is pl.Series
    assert result.equals(expected)
    assert result.to_numpy().dtype == expected.to_numpy().dtype
    assert type(x[0:1]) is Pldt
    assert type(x.clone()) is Pldt
