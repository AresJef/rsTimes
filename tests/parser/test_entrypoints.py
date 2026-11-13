"""Public entrypoints, approved parameter migration and callback boundaries."""
from datetime import datetime
import importlib
import inspect
import pytest


def functions():
    m=importlib.import_module("rstimes.parser")
    return m.parse_str,m.parse,m.Configs


def test_public_exports_share_native_functions():
    import rstimes
    text,obj,cls=functions()
    assert rstimes.parse_str is text
    assert rstimes.parse is obj
    assert text.__module__==obj.__module__=="rstimes.parser"


def test_parameter_order_and_positional_strict():
    text,obj,cls=functions()
    names=["dtstr","default","yearfirst","dayfirst","ignoretz","isoformat","strict","cfg","dtclass"]
    assert list(inspect.signature(text).parameters)==names
    assert list(inspect.signature(obj).parameters)==["dtobj"]+names[1:]
    for fn in (text,obj):
        assert fn("2024-05-07",None,None,None,True,True,True)==datetime(2024,5,7)
        with pytest.raises(TypeError):
            fn("2024-05-07",None,None,None,True,True,True,strict=False)


def test_keyword_migration_and_string_subclass_behavior():
    text,obj,_=functions()
    assert text(dtstr="2024-05-07")==obj(dtobj="2024-05-07")
    with pytest.raises(TypeError):obj(dtstr="2024-05-07")
    events=[]
    class Child(str):
        def __str__(self):
            events.append("str")
            return "2024-05-07"
    value=Child("2024-05-06")
    assert obj(value)==text(value)==datetime(2024,5,6)
    assert events==[]


def test_native_input_ignores_default_but_validates_actual_boolean_options():
    _, obj, _ = functions()
    events = []
    class Forbidden:
        def __bool__(self):
            events.append("bool")
            raise AssertionError("truth conversion must not run")
    value = datetime(2024, 5, 7)
    assert obj(value, default=Forbidden(), yearfirst=None, dayfirst=False,
               ignoretz=True, isoformat=True, strict=False) is value
    for name in ("yearfirst", "dayfirst", "ignoretz", "isoformat", "strict"):
        with pytest.raises(TypeError):
            obj(value, **{name: Forbidden()})
    assert events == []


def test_string_conversion_result_still_requires_builtin_string():
    """Historical case ID; the approved native-text contract never converts."""
    _, obj, _ = functions()
    events = []
    class Returned(str):
        pass
    class Child(str):
        def __str__(self):
            events.append("str")
            return Returned("2024-05-07")
    assert obj(Child("2024-05-06")) == datetime(2024, 5, 6)
    assert events == []


def test_string_checks_and_object_cfg_check_have_separate_priority():
    text,obj,_=functions()
    with pytest.raises(TypeError,match="dtstr"):text(None,cfg=object())
    with pytest.raises(TypeError,match="cfg"):obj(None,cfg=object())
    class Broken(str):
        def __str__(self):raise RuntimeError("str callback")
    assert obj(Broken("2024-05-07")) == datetime(2024, 5, 7)
    with pytest.raises(TypeError,match="cfg"):obj(Broken("x"),cfg=object())
