"""Observed public boundary differences and native default-date reads."""
from datetime import datetime
import importlib.util
from pathlib import Path
import pytest
from cytimes.parser import parse as original_parse
from rstimes.parser import parse_str as parse
from approved_behavior import outcomes_equal

spec=importlib.util.spec_from_file_location("_boundary_cases",Path(__file__).with_name("cases.py"))
cases=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)

class FailBool:
    def __bool__(self):
        raise RuntimeError("truth callback")

def bad_constructor(**kwargs):
    return ()

def missing_constructor(**kwargs):
    return None

def raising_constructor(**kwargs):
    raise RuntimeError("constructor callback")

@pytest.mark.parametrize("kwargs",[
    dict(dtstr=None),
    dict(dtstr=None,cfg=object()),
    dict(dtstr=3,ignoretz=FailBool()),
    dict(dtstr="\ud800"),
    dict(dtstr="\ud800 12:34"),
    dict(dtstr="2024-01-01",dtclass=bad_constructor),
    dict(dtstr="2024-01-01",dtclass=missing_constructor),
    dict(dtstr="2024-01-01",dtclass=raising_constructor),
    dict(dtstr="2024-01-01",yearfirst=FailBool()),
    dict(dtstr="2024-01-01",dayfirst=FailBool()),
])
def test_known_boundary_matches_reference(kwargs):
    if any(isinstance(v, FailBool) for v in kwargs.values()):
        with pytest.raises(TypeError):
            parse(**kwargs)
    else:
        assert outcomes_equal(cases.outcome(lambda:parse(**kwargs)), cases.outcome(lambda:original_parse(**kwargs)))

def test_default_date_uses_native_fields():
    class Date(datetime):
        @property
        def year(self):
            raise RuntimeError("must not read overridden property")
    value=Date(2024,2,29,11,22,33)
    assert parse("12:34",default=value)==original_parse("12:34",default=value)



def test_constructor_does_not_wrap_control_exceptions():
    def stop(**kwargs):
        raise SystemExit(7)
    def invoke(function):
        try:
            function("2024-01-01", dtclass=stop)
        except BaseException as error:
            return type(error).__name__, str(error), error.__cause__
        raise AssertionError("constructor was not invoked")
    assert invoke(parse) == invoke(original_parse)



def test_datetime_constructor_keyword_order_and_fold_type():
    from datetime import datetime
    def invoke(function):
        observed = []
        def factory(**kwargs):
            observed.append((tuple(kwargs), type(kwargs["fold"]).__name__))
            return datetime(**kwargs)
        value = function("2024-01-01", dtclass=factory)
        return value, observed
    assert invoke(parse) == invoke(original_parse)


def test_explicit_standard_datetime_constructor():
    from datetime import datetime
    assert parse("2024-01-01", dtclass=datetime) == original_parse("2024-01-01", dtclass=datetime)


def test_text_subclass_is_rejected_before_scanning():
    class Text(str):
        pass
    assert outcomes_equal(cases.outcome(lambda: parse(Text("2024-01-01"))), cases.outcome(
        lambda: original_parse(Text("2024-01-01"))))



def test_base_configuration_type_is_immutable():
    from cytimes.parser import Configs as OriginalConfigs
    from rstimes.parser import Configs
    for cls in (OriginalConfigs, Configs):
        with pytest.raises(TypeError, match="immutable type"):
            cls.add_month = cls.add_month



