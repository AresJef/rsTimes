"""Approved identity, one-time dependency and finite-reentry regressions."""

import json
import subprocess
import sys
import textwrap

import pytest


def run_child(source):
    """Keep process-local module changes isolated and bound a broken cache wait."""
    result = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(source)],
        capture_output=True, text=True, timeout=8,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_numpy_public_alias_changes_do_not_authorize_foreign_layouts():
    result = run_child('''
        import json
        import numpy as np
        # Their own initialization requires NumPy's public aliases. Finish it
        # before changing aliases, keeping rstimes' native cache cold.
        import pandas, polars
        Date, Duration = np.datetime64, np.timedelta64
        value = Date("2024-01-01", "us")
        class Fake: pass
        np.datetime64 = Fake
        np.timedelta64 = Fake
        from rstimes import Delta, parse_to_epoch
        assert Delta(days=1).__add__(Fake()) is NotImplemented
        assert Delta(days=1).__add__(Duration(2, "D")).days == 3
        print(json.dumps({"epoch": parse_to_epoch(value, unit="us")}))
    ''')
    assert result == {"epoch": 1704067200000000}


def test_numpy_capsule_preparation_can_reenter_before_publication():
    result = run_child('''
        import json, types
        import numpy as np
        import numpy._core._multiarray_umath as api
        from rstimes import parse_to_epoch
        value = np.datetime64("2024-01-01", "us")
        entered = False
        inner = None
        class Module(types.ModuleType):
            def __getattribute__(self, name):
                global entered, inner
                if name == "_ARRAY_API" and not entered:
                    entered = True
                    inner = parse_to_epoch(value, unit="us")
                return super().__getattribute__(name)
        api.__class__ = Module
        outer = parse_to_epoch(value, unit="us")
        print(json.dumps({"entered": entered, "inner": inner, "outer": outer}))
    ''')
    assert result == {"entered": True, "inner": 1704067200000000,
                      "outer": 1704067200000000}


def test_dateutil_type_preparation_can_reenter_before_publication():
    result = run_child('''
        import json, types
        import dateutil.relativedelta as module
        from rstimes import Delta
        value = module.relativedelta(days=2)
        entered = False
        inner = None
        class Module(types.ModuleType):
            def __getattribute__(self, name):
                global entered, inner
                if name == "relativedelta" and not entered:
                    entered = True
                    inner = Delta.from_relativedelta(value).days
                return super().__getattribute__(name)
        module.__class__ = Module
        outer = Delta.from_relativedelta(value).days
        print(json.dumps({"entered": entered, "inner": inner, "outer": outer}))
    ''')
    assert result == {"entered": True, "inner": 2, "outer": 2}


@pytest.mark.parametrize("missing", [[], ["pandas"], ["polars"], ["pandas", "polars"]])
def test_optional_dependencies_have_the_same_one_time_absence_policy(missing):
    result = run_child('''
        import builtins, json
        missing = MISSING
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name in missing:
                raise ModuleNotFoundError("test unavailable " + name, name=name)
            return original(name, *args, **kwargs)
        builtins.__import__ = guarded
        import rstimes
        from rstimes._optional import HAS_PANDAS, HAS_POLARS
        assert rstimes.parse_str("2024-01-02").year == 2024
        assert rstimes.Pydt(2024, 1, 2).year == 2024
        if "pandas" in missing:
            try: rstimes.Pddt
            except ImportError as error: assert "rstimes[pandas]" in str(error)
            else: raise AssertionError("Pddt silently worked without pandas")
        print(json.dumps({"pandas": HAS_PANDAS, "polars": HAS_POLARS}))
    '''.replace("MISSING", repr(missing)))
    assert result == {"pandas": "pandas" not in missing,
                      "polars": "polars" not in missing}


@pytest.mark.parametrize("package", ["pandas", "polars"])
def test_optional_package_internal_import_errors_are_not_hidden(package):
    result = run_child('''
        import builtins, json
        original = builtins.__import__
        package = PACKAGE
        def guarded(name, *args, **kwargs):
            if name == package:
                raise ModuleNotFoundError("broken package dependency", name=package + ".broken")
            return original(name, *args, **kwargs)
        builtins.__import__ = guarded
        try: import rstimes
        except ModuleNotFoundError as error: print(json.dumps({"name": error.name}))
        else: raise AssertionError("broken dependency was silently ignored")
    '''.replace("PACKAGE", repr(package)))
    assert result == {"name": package + ".broken"}


def test_polars_real_series_subclass_is_not_filtered_by_name():
    pl = pytest.importorskip("polars")
    from rstimes import parse_to_epoch

    class ApplicationSeries(pl.Series):
        pass

    value = ApplicationSeries("date", [1704067200000000], dtype=pl.Datetime("us"))
    assert parse_to_epoch(value, unit="us") == 1704067200000000


def test_warm_third_party_dispatch_does_not_repeat_dependency_imports():
    result = run_child('''
        import builtins, json
        import rstimes
        from rstimes._optional import PANDAS, POLARS
        timestamp = PANDAS.Timestamp("2024-01-01")
        series = POLARS.Series([1704067200000000], dtype=POLARS.Datetime("us"))
        rstimes.parse(timestamp)
        rstimes.parse_to_epoch(series, unit="us")
        original = builtins.__import__
        seen = []
        def guarded(name, *args, **kwargs):
            caller = args[0].get("__name__", "") if args and args[0] else ""
            if name in ("pandas", "polars") and caller.startswith("rstimes"):
                seen.append(name)
            return original(name, *args, **kwargs)
        builtins.__import__ = guarded
        for _ in range(3):
            rstimes.parse(timestamp)
            rstimes.parse_to_epoch(series, unit="us")
        print(json.dumps({"repeated": seen}))
    ''')
    assert result == {"repeated": []}


def test_false_displayed_class_keeps_reflected_arithmetic():
    from datetime import timedelta
    from rstimes import Pydt

    class Other:
        @property
        def __class__(self):
            return timedelta

        def __radd__(self, value):
            return "reflected"

        def __rsub__(self, value):
            return "reflected subtraction"

    value = Pydt(2024, 1, 1)
    assert value + Other() == "reflected"
    assert value - Other() == "reflected subtraction"


@pytest.mark.parametrize("base", ["date", "datetime"])
def test_delta_result_uses_actual_date_subclass(base):
    from datetime import date, datetime
    from rstimes import Delta
    parent = date if base == "date" else datetime

    class Child(parent):
        @property
        def __class__(self):
            return parent

    result = Child(2024, 1, 1) + Delta(days=1)
    assert type(result) is Child
    assert result.day == 2


def test_relative_integer_protocol_ignores_metaclass_attribute_facade():
    from rstimes import Delta
    calls = []

    class Meta(type):
        def __getattribute__(cls, name):
            if name == "__index__":
                raise AttributeError(name)
            return super().__getattribute__(name)

    class Number(metaclass=Meta):
        def __index__(self):
            calls.append(1)
            return 2

    assert Delta(days=Number()).days == 2
    assert calls == [1]


@pytest.mark.parametrize("method", ["to_year", "to_curr_year", "to_prev_year", "to_next_year",
                                   "to_weekday", "to_curr_weekday", "to_prev_weekday", "to_next_weekday"])
def test_calendar_selectors_accept_index_protocol_once(method):
    from rstimes import Pydt
    calls = []
    weekday = "weekday" in method

    class Index:
        def __index__(self):
            calls.append(1)
            return 0 if weekday else 6

    operation = getattr(Pydt(2024, 5, 7), method)
    args = (0,) if method in ("to_year", "to_weekday") else ()
    result = operation(*args, **{"weekday" if weekday else "month": Index()})
    assert result.weekday() == 0 if weekday else result.month == 6
    assert calls == [1]


def test_fake_relativedelta_does_not_gain_conversion_or_arithmetic():
    from dateutil.relativedelta import relativedelta
    from rstimes import Delta

    class Proxy:
        @property
        def __class__(self):
            return relativedelta

    with pytest.raises(TypeError):
        Delta.from_relativedelta(Proxy())
    assert Delta(days=1).__add__(Proxy()) is NotImplemented


def test_index_query_is_not_captured_by_fake_string_class():
    from rstimes import Pydt

    class Index:
        @property
        def __class__(self):
            return str

        def __index__(self):
            return 9

    assert Pydt(2024, 9, 1).is_month(Index()) is True
