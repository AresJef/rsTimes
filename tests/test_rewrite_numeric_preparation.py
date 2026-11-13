"""P04 boundary protocols are prepared once before scalar or batch kernels."""
import numpy as np
import pytest

from rstimes._native import _integer_arg


def test_index_callback_runs_once_and_preserves_its_integer():
    class Counted:
        calls = 0

        def __index__(self):
            self.calls += 1
            return -17

    value = Counted()
    assert _integer_arg(value, "Pddt.offset", "offset") == -17
    assert value.calls == 1


def test_index_callback_keeps_the_original_exception_object():
    failure = RuntimeError("source failed")

    class Broken:
        def __index__(self):
            raise failure

    with pytest.raises(RuntimeError) as caught:
        _integer_arg(Broken(), "Pddt.offset", "offset")
    assert caught.value is failure


@pytest.mark.parametrize("bad", [True, np.bool_(False), 1.0, "1"])
def test_integer_preparation_does_not_coerce_other_scalar_roles(bad):
    with pytest.raises(TypeError):
        _integer_arg(bad, "Pddt.offset", "offset")

# ProductReady PR-021/025/041: real numeric role, one protocol, stored int.
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from rstimes import Pydt, from_unix_ms


@pytest.mark.parametrize("entry", ("fromseconds","fromtimestamp","utcfromtimestamp"))
@pytest.mark.parametrize("kind", ("float","index","protocol"))
def test_product_ready_factory_gate_does_not_read_displayed_class(entry,kind):
    events=[]
    class Float(float):
        @property
        def __class__(self):events.append("class");return bool
    class Index:
        @property
        def __class__(self):events.append("class");return bool
        def __index__(self):events.append("index");return 3
    class Protocol(Index):
        def __float__(self):events.append("float");return 2.5
    value = Float(1.25) if kind=="float" else Index() if kind=="index" else Protocol()
    seconds = 1.25 if kind=="float" else 2.5 if kind=="protocol" and entry=="fromseconds" else 3
    expected_events = [] if kind=="float" else ["float"] if kind=="protocol" and entry=="fromseconds" else ["index"]
    actual = Pydt.fromtimestamp(value,timezone.utc) if entry=="fromtimestamp" else getattr(Pydt,entry)(value)
    expected = datetime(1970,1,1)+timedelta(seconds=seconds)
    if entry!="fromseconds":expected=expected.replace(tzinfo=timezone.utc)
    assert type(actual) is Pydt and actual==expected and events==expected_events


@pytest.mark.parametrize("entry", ("fromseconds","fromtimestamp","utcfromtimestamp"))
@pytest.mark.parametrize("value", (True,False,np.bool_(True),np.bool_(False)))
def test_product_ready_real_boolean_is_still_not_epoch_seconds(entry,value):
    with pytest.raises(TypeError):
        Pydt.fromtimestamp(value,timezone.utc) if entry=="fromtimestamp" else getattr(Pydt,entry)(value)


@pytest.mark.parametrize("value", (Decimal("1.5"),Fraction(3,2)))
def test_product_ready_seconds_coercion_does_not_expand_timestamp_domain(value):
    assert Pydt.fromseconds(value)==datetime(1970,1,1,0,0,1,500000)
    for entry in ("fromtimestamp","utcfromtimestamp"):
        # The mature datetime call remains this ABI's independent authority.
        try:expected=datetime.fromtimestamp(value,timezone.utc)
        except Exception as error:
            with pytest.raises(type(error)):
                Pydt.fromtimestamp(value,timezone.utc) if entry=="fromtimestamp" else Pydt.utcfromtimestamp(value)
        else:
            actual=Pydt.fromtimestamp(value,timezone.utc) if entry=="fromtimestamp" else Pydt.utcfromtimestamp(value)
            assert actual==expected


@pytest.mark.parametrize("entry", ("fromseconds","fromtimestamp","utcfromtimestamp"))
def test_product_ready_numeric_conversion_retains_original_exception(entry):
    error=LookupError("actual number protocol")
    class Number:
        def __float__(self):raise error
        def __index__(self):raise error
    with pytest.raises(LookupError) as caught:
        Pydt.fromtimestamp(Number(),timezone.utc) if entry=="fromtimestamp" else getattr(Pydt,entry)(Number())
    assert caught.value is error


@pytest.mark.parametrize("role", range(3))
def test_product_ready_iso_integer_roles_use_one_real_index(role):
    class Index:
        calls=0
        def __index__(self):self.calls+=1;return (2024,1,1)[role]
    value=Index();args=[2024,1,1];args[role]=value
    assert Pydt.fromisocalendar(*args)==datetime(2024,1,1)
    assert value.calls==1


@pytest.mark.parametrize("method,n", (("is_year",2024),("is_quarter",1),("is_day",2),("is_month",1),("is_weekday",1)))
def test_product_ready_query_integer_role_uses_one_real_index(method,n):
    class Index:
        calls=0
        def __index__(self):self.calls+=1;return n
    value=Index()
    assert getattr(Pydt(2024,1,2),method)(value) is True and value.calls==1


@pytest.mark.parametrize("value", (-2**31,2**31-1))
def test_product_ready_query_signed32_endpoints_keep_legal_nonmatch(value):
    assert Pydt(2024,1,2).is_year(value) is False


@pytest.mark.parametrize("value", (-2**31-1,2**31))
def test_product_ready_query_signed32_neighbors_keep_overflow(value):
    with pytest.raises(OverflowError):Pydt(2024,1,2).is_year(value)


@pytest.mark.parametrize("kind", (int,"passive","rewrite","raise"))
@pytest.mark.parametrize("stored", (-1,0,1,-62135596800000,253402300799999,-62135596800001,253402300800000,10**100,-10**100))
def test_product_ready_unix_milliseconds_use_stored_integer_before_arithmetic(kind,stored):
    events=[]
    class Passive(int):pass
    class Rewriting(int):
        def __mul__(self,other):events.append("mul");return 0
        def __int__(self):events.append("int");return 0
        def __index__(self):events.append("index");return 0
    class Raising(Rewriting):
        def __mul__(self,other):events.append("mul");raise RuntimeError("business multiplication")
    cls = int if kind is int else Passive if kind=="passive" else Rewriting if kind=="rewrite" else Raising
    value=cls(stored)
    if -62135596800000 <= stored <= 253402300799999:
        expected=datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(milliseconds=stored)
        actual=from_unix_ms(value)
        assert type(actual) is datetime and actual.tzinfo is timezone.utc and actual==expected
    else:
        with pytest.raises(OverflowError):from_unix_ms(value)
    assert events==[]


@pytest.mark.parametrize("value", (None,True,False,np.bool_(True),np.int8(1),np.int64(1),np.uint64(1),1.0,"1",Decimal(1)))
def test_product_ready_unix_milliseconds_do_not_expand_to_other_numeric_roles(value):
    with pytest.raises(TypeError):from_unix_ms(value)


@pytest.mark.parametrize("method", ("__index__","__int__"))
def test_product_ready_unix_milliseconds_reject_protocol_only_without_running_it(method):
    events=[]
    class Number:pass
    def convert(self):events.append(method);return 1
    setattr(Number,method,convert)
    with pytest.raises(TypeError):from_unix_ms(Number())
    assert events==[]


def test_product_ready_unix_milliseconds_error_keeps_original_input_context():
    class Large(int):pass
    value=Large(10**100)
    with pytest.raises(OverflowError) as caught:from_unix_ms(value)
    note=caught.value.__notes__[-1]
    assert note.field=="value" and note.preview=="<Large>"
