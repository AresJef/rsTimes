"""Approved public None and integer rules, independent of the legacy outputs."""
from datetime import datetime
import warnings
import numpy as np
import pytest
from rstimes import Delta, Pydt

ABSOLUTE = {'year': (1, 9999), 'month': (1, 12), 'day': (1, 31),
            'weekday': (0, 6), 'hour': (0, 23), 'minute': (0, 59),
            'second': (0, 59), 'millisecond': (0, 999), 'microsecond': (0, 999999)}

def absolute_value(delta, field):
    return delta.microsecond // 1000 if field == 'millisecond' and delta.microsecond is not None else getattr(delta, 'microsecond' if field == 'millisecond' else field)

class Index:
    def __init__(self, value):
        self.value = value
    def __index__(self):
        return self.value

class IntOnly:
    def __int__(self):
        return 1

@pytest.mark.parametrize('field', ABSOLUTE)
def test_delta_none_means_unset(field):
    assert absolute_value(Delta(**{field: None}), field) is None
    assert Delta(**{field: None}) == Delta()

@pytest.mark.parametrize('field,limits', ABSOLUTE.items())
def test_delta_explicit_integer_bounds_and_zero(field, limits):
    lower, upper = limits
    for value in (lower, upper):
        assert absolute_value(Delta(**{field: value}), field) == value
        assert absolute_value(Delta(**{field: np.int64(value)}), field) == value
        assert absolute_value(Delta(**{field: Index(value)}), field) == value
    for value in (lower - 1, -20):
        with pytest.raises(ValueError, match=field):
            Delta(**{field: value})
    if field not in {'year', 'month', 'day'}:
        with pytest.raises(ValueError, match=field):
            Delta(**{field: upper + 1})
    else:
        assert absolute_value(Delta(**{field: upper + 1}), field) == upper

@pytest.mark.parametrize('field', ABSOLUTE)
@pytest.mark.parametrize('value', [1.0, 1.9, '1', IntOnly()])
def test_delta_absolute_fields_reject_truncating_conversion(field, value):
    with pytest.raises(TypeError):
        Delta(**{field: value})

@pytest.mark.parametrize('shape', ['single', 'two', 'mixed', 'positional'])
def test_delta_all_constructor_shapes_obey_none_and_ranges(shape):
    def make(hour):
        if shape == 'single':
            return Delta(hour=hour)
        if shape == 'two':
            return Delta(days=1, hour=hour)
        if shape == 'mixed':
            return Delta(0, hour=hour)
        return Delta(*([0] * 10 + [None] * 4 + [hour]))
    assert make(None).hour is None
    assert make(0).hour == 0
    with pytest.raises(ValueError):
        make(-1)
    with pytest.raises(ValueError):
        make(24)
    with pytest.raises(TypeError,match="hour"):
        make(1.0)

BASE = Pydt(2024, 5, 17, 12, 34, 56, 123456)

@pytest.mark.parametrize('method,fields', [('to_datetime', ['year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond']), ('to_date', ['year', 'month', 'day']), ('to_time', ['hour', 'minute', 'second', 'microsecond'])])
def test_pydt_optional_field_rules(method, fields):
    for field in fields:
        lower, upper = ABSOLUTE[field]
        call = getattr(BASE, method)
        assert call(**{field: None}) is BASE
        result = call(**{field: np.int64(lower)})
        assert getattr(result, field) == lower
        for value in (lower - 1, upper + 1):
            with pytest.raises(ValueError, match=field):
                call(**{field: value})
        for value in (1.0, IntOnly()):
            with pytest.raises(TypeError):
                call(**{field: value})
    if 'day' in fields:
        assert getattr(BASE, method)(month=2, day=31).day == 29

@pytest.mark.parametrize('kind', ['year', 'quarter', 'month'])
@pytest.mark.parametrize('prefix', ['to_', 'to_curr_', 'to_prev_', 'to_next_'])
def test_pydt_calendar_day_rules(kind, prefix):
    method = getattr(BASE, prefix + kind)
    args = (0,) if prefix == 'to_' else ()
    assert method(*args, day=None).hour == BASE.hour
    for day in (0, -1, 32):
        with pytest.raises(ValueError, match='day'):
            method(*args, day=day)
    with pytest.raises(TypeError):
        method(*args, day=9.0)

@pytest.mark.parametrize('prefix', ['to_', 'to_curr_', 'to_prev_', 'to_next_'])
def test_pydt_month_selectors(prefix):
    args = (0,) if prefix == 'to_' else ()
    for kind, upper in [('year', 12), ('quarter', 3)]:
        method = getattr(BASE, prefix + kind)
        assert method(*args, month=None).hour == BASE.hour
        for month in (0, -1, upper + 1):
            with pytest.raises(ValueError):
                method(*args, month=month)

@pytest.mark.parametrize('prefix', ['to_', 'to_curr_', 'to_prev_', 'to_next_'])
def test_pydt_weekday_none_and_range(prefix):
    method = getattr(BASE, prefix + 'weekday')
    args = (0,) if prefix == 'to_' else ()
    assert method(*args, weekday=None).hour == BASE.hour
    for weekday in (-1, 7):
        with pytest.raises(ValueError):
            method(*args, weekday=weekday)

@pytest.mark.parametrize('method,value', [('is_year',2024),('is_quarter',2),('is_day',17),('is_month',5),('is_weekday',4)])
def test_pydt_queries_use_integer_protocol(method, value):
    call=getattr(BASE,method)
    assert call(Index(value)) is True
    assert call(np.int64(value)) is True
    with pytest.raises(TypeError):
        call(float(value))
    with pytest.raises(TypeError):
        call(IntOnly())

@pytest.mark.parametrize('method', ['is_month','is_weekday'])
@pytest.mark.parametrize('name',['','unknown'])
def test_pydt_unknown_name_is_explicit_error(method,name):
    with pytest.raises(ValueError):
        getattr(BASE,method)(name)

@pytest.mark.parametrize('field', ['year','month','day','hour','minute','second','microsecond','fold'])
def test_replace_numeric_none_retains_value(field):
    assert BASE.replace(**{field:None}) is BASE
    assert BASE.__replace__(**{field:None}) is BASE

def test_relative_zero_and_signed_duration_mean_real_increments():
    assert Delta(days=0) == Delta()
    assert Delta(hours=1.5) == Delta(hours=1,minutes=30)
    assert (BASE + Delta(days=-1)).day == 16
    with pytest.raises(TypeError):
        Delta(days=None)

@pytest.mark.parametrize('options', [dict(year=0),dict(month=0),dict(day=0),dict(hour=0),dict(minute=0),dict(second=0),dict(microsecond=0),dict(day=32),dict(days=-1),dict(days=1.5),dict(month=13,months=-1),dict(year=-1,years=2025),dict(month=25,months=-1)])
def test_relativedelta_source_meaning_is_preserved(options):
    from dateutil.relativedelta import relativedelta
    rd=relativedelta(**options)
    converted=Delta.from_relativedelta(rd)
    for start in (datetime(2024,5,17,13,14,15,123456), datetime(2023,1,31,9),datetime(2020,2,29)):
        assert start+converted == start+rd

@pytest.mark.parametrize('options',[dict(year=-1),dict(month=-1),dict(day=-1),dict(month=13),dict(hour=24),dict(minute=-1)])
def test_unrepresentable_relative_source_is_rejected(options):
    from dateutil.relativedelta import relativedelta
    with pytest.raises(ValueError,match='cannot be represented'):
        Delta.from_relativedelta(relativedelta(**options))

def test_relative_mixed_operators_and_batch_reuse_source_adapter():
    from dateutil.relativedelta import relativedelta
    zero=Delta()
    rd=relativedelta(month=13,months=-1)
    expected=Delta(month=12)
    assert zero+rd==expected
    assert rd+zero==expected
    assert zero-rd==expected
    assert rd-zero==expected
    assert zero.apply_many([rd])==[expected]

@pytest.mark.parametrize('method',['is_year','is_quarter','is_day','is_month','is_weekday'])
def test_query_integer_width_remains_the_existing_checked_width(method):
    with pytest.raises(OverflowError):
        getattr(BASE,method)(2**40)

def test_wide_optional_replacements_report_the_calendar_bound():
    with pytest.raises(ValueError,match='year'):
        BASE.to_date(year=2**40)


@pytest.mark.parametrize('options',[dict(year=2024.0),dict(month=5.0),dict(day=30.0),dict(hour=0.0),dict(minute=1.9)])
def test_relative_source_does_not_silently_coerce_invalid_absolute_floats(options):
    from dateutil.relativedelta import relativedelta
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning)
        source=relativedelta(**options)
    with pytest.raises(TypeError):
        Delta.from_relativedelta(source)

@pytest.mark.parametrize('options',[dict(year=0.0,month=0.0,day=0.0),dict(day=31.5)])
def test_relative_false_dates_and_always_month_end_keep_the_source_meaning(options):
    from dateutil.relativedelta import relativedelta
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning)
        source=relativedelta(**options)
        converted=Delta.from_relativedelta(source)
    for start in (datetime(2024,1,15),datetime(2024,2,15),datetime(2023,2,15)):
        assert start+converted==start+source


def test_delta_error_reports_one_entry_and_the_failed_field():
    for options in (dict(hour=9.0),dict(days=1,hour=9.0)):
        with pytest.raises(TypeError) as observed:Delta(**options)
        message=str(observed.value)
        assert message.count('Delta():')==1
        assert 'hour must be an integer or None' in message
