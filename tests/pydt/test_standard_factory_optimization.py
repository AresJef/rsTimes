"""Causal checks for copying trusted standard factory results."""
from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo
import pytest
from rstimes import Pydt

@pytest.mark.parametrize('timestamp', [1730611800, 1730615400])
def test_instant_factory_keeps_both_repeated_occurrences(timestamp):
    zone = ZoneInfo('America/New_York')
    expected = datetime.fromtimestamp(timestamp, zone)
    result = Pydt.fromtimestamp(timestamp, zone)
    assert type(result) is Pydt
    assert (result.fold, result.timestamp(), result.tzinfo) == (expected.fold, timestamp, zone)

@pytest.mark.parametrize('factory', [
    lambda cls: cls.now(timezone.utc),
    lambda cls: cls.utcnow(),
    lambda cls: cls.fromtimestamp(0, timezone.utc),
    lambda cls: cls.utcfromtimestamp(0),
    lambda cls: cls.fromisoformat('2024-05-07T12:30:00+02:00'),
])
def test_child_factories_keep_fromdatetime_override(factory):
    marker = object()
    received = []
    class Child(Pydt):
        @classmethod
        def fromdatetime(cls, value, tz=None):
            received.append(value)
            return marker
    assert factory(Child) is marker
    assert len(received) == 1 and isinstance(received[0], datetime)


def test_custom_request_keeps_protocol_even_when_result_uses_standard_zone():
    marker = Pydt(2024, 5, 7, tzinfo=timezone.utc)
    class Custom(tzinfo):
        def utcoffset(self, value): return timezone.utc.utcoffset(value)
        def dst(self, value): return timezone.utc.dst(value)
        def fromutc(self, value): return marker
    assert Pydt.now(Custom()) is marker
    assert Pydt.fromtimestamp(0, Custom()) is marker


def test_base_standard_factories_use_builtin_conversion(monkeypatch):
    def unexpected(cls, value, tz=None):
        raise AssertionError('standard base factory must use its own conversion')
    monkeypatch.setattr(Pydt, 'fromdatetime', classmethod(unexpected))
    for result in (Pydt.now(timezone.utc), Pydt.utcnow(),
                   Pydt.fromtimestamp(0, timezone.utc), Pydt.utcfromtimestamp(0),
                   Pydt.fromisoformat('2024-05-07T12:30:00+02:00')):
        assert type(result) is Pydt
