"""Actual Configs tables retain owned display values and captured native rules."""
import copy
from datetime import datetime
import pickle

import numpy as np
import pytest

from rstimes import Configs, parse_str

NAMES = ('jump', 'pertain', 'utc', 'tzoffset', 'month', 'weekday', 'hms', 'ampm')
VALUES = (None, None, None, 3600, 2, 4, 1, 1)


@pytest.mark.parametrize('name,value', tuple(zip(NAMES, VALUES)))
def test_each_table_display_is_independent_across_edit_copy_restore_and_reset(name, value):
    cfg = Configs(yearfirst=False, dayfirst=True)
    original = getattr(cfg, name)
    copies = [copy.copy(cfg), copy.deepcopy(cfg), pickle.loads(pickle.dumps(cfg))]
    mapping = {'bespokeword'} if value is None else {'bespokeword': value}
    assert getattr(cfg, 'set_' + name)(mapping) is True
    expected = mapping.copy()
    assert getattr(cfg, name) == expected
    display = getattr(cfg, name)
    display.clear()
    assert getattr(cfg, name) == expected
    for saved in copies:
        assert getattr(saved, name) == original
    restored = Configs()
    restored.__setstate__(cfg.__reduce__()[2])
    assert getattr(restored, name) == expected
    assert getattr(cfg, 'del_' + name)('bespokeword') is True
    assert getattr(cfg, name) == (set() if value is None else {})
    assert getattr(restored, name) == expected
    assert cfg.reset_settings() is True
    assert getattr(cfg, name) == original
    assert cfg.yearfirst is False and cfg.dayfirst is True


@pytest.mark.parametrize('token_type', [str, np.str_])
@pytest.mark.parametrize('form', ['straße', 'STRASSE', 'Straße'])
def test_unicode_case_expansion_and_word_lengths_remain_available(token_type, form):
    cfg = Configs()
    cfg.set_month({token_type('Straße'): 2})
    assert cfg.month == {'straße': 2}
    assert parse_str('1 ' + form + ' 2024', cfg=cfg) == datetime(2024, 2, 1)


def test_real_str_storage_is_normalized_without_business_lower_hook():
    class Word(str):
        def lower(self):
            raise AssertionError('must use native str storage')
    cfg = Configs()
    cfg.set_month({Word('Straße'): 2})
    assert cfg.month == {'straße': 2}
    assert parse_str('1 STRASSE 2024', cfg=cfg) == datetime(2024, 2, 1)


def test_failed_conflict_keeps_cached_owner_and_all_original_rules():
    cfg = Configs()
    before = cfg.month
    with pytest.raises(ValueError):
        cfg.add_month('pm', 2)
    assert cfg.month == before
    cfg.month.clear()
    assert cfg.month == before


def test_numeric_callback_precedes_empty_word_error_and_retains_original_exception():
    calls = []
    marker = LookupError('actual numeric callback')
    class Code:
        def __index__(self):
            calls.append('index')
            raise marker
    cfg = Configs()
    with pytest.raises(LookupError) as seen:
        cfg.add_month('', Code())
    assert seen.value is marker and calls == ['index']
    with pytest.raises(TypeError):
        cfg.del_month(1)
    with pytest.raises(ValueError):
        cfg.del_month('')


def test_expr_captures_original_config_owner_before_edit_and_reset():
    pl = pytest.importorskip('polars')
    from rstimes import Pldt  # lazily registers the official Expr namespace
    assert Pldt is not None
    cfg = Configs()
    cfg.set_month({'harvest': 2})
    frame = pl.DataFrame({'text': ['1 harvest 2024', None]})
    expr = pl.col('text').pldt.parse(unit='ns', cfg=cfg)
    cfg.set_month({'harvest': 3})
    updated = pl.col('text').pldt.parse(unit='ns', cfg=cfg)
    cfg.reset_settings()
    assert frame.lazy().select(expr).collect().to_series().dt.month().to_list() == [2, None]
    assert frame.select(updated).to_series().dt.month().to_list() == [3, None]


@pytest.mark.parametrize('workers', [2, 4])
def test_concurrent_owned_copies_detach_cache_and_rules(workers):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve()
    spec = importlib.util.spec_from_file_location(
        'configs_thread_deadline', path.parents[1] / '_thread_case_watchdog.py')
    deadline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deadline)
    result = deadline.run_case(path, '_concurrent_owned_copies', (workers,))
    assert result['status'] == 'passed', result


def _concurrent_owned_copies(workers):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    original = Configs()
    original.set_month({'harvest': 2})
    original_display = original.month
    aliases = [copy.copy(original) for _ in range(workers)]
    barrier = threading.Barrier(workers)
    def edit_and_read(index):
        cfg = aliases[index]
        for cycle in range(20):
            barrier.wait(timeout=10)
            assert cfg.month == {'harvest': 2 if cycle == 0 else index + 3}
            assert cfg.set_month({'harvest': index + 3}) is True
            own = cfg.month
            assert own == {'harvest': index + 3}
            own.clear()
            assert original.month == {'harvest': 2}
            assert cfg.month == {'harvest': index + 3}
        return True
    with ThreadPoolExecutor(max_workers=workers) as pool:
        assert all(pool.map(edit_and_read, range(workers)))
    assert original.month == original_display == {'harvest': 2}
