"""Dedicated ISO factories accept one Python code point as the separator."""
from datetime import datetime

import numpy as np
import pytest

from rstimes import Pddt, Pydt


class IsoText(str):
    """A passive real str subclass, read by native storage."""


@pytest.mark.parametrize("separator", ["T", "x", "🕒", "\0", "\ud800", "\udfff"])
@pytest.mark.parametrize("factory", [str, IsoText, np.str_])
@pytest.mark.parametrize("scalar", [False, True])
def test_iso_factory_single_codepoint_matches_mature_datetime(separator, factory, scalar):
    text = "2024-01-02" + separator + "12:30:01.123456"
    expected = datetime.fromisoformat(text)
    span = expected - datetime(1970, 1, 1)
    ticks = (span.days * 86400 + span.seconds) * 1_000_000 + span.microseconds
    value = factory(text)
    result = Pddt.fromisoformat(value, size=1) if scalar else Pddt.fromisoformat([value])
    assert result.unit == "us" and result.asi8.tolist() == [ticks]
    assert Pydt.fromisoformat(text) == expected


@pytest.mark.parametrize("text", ["2024-01-02\ud800\udfff12:30", "2024-01-02\ud80012:30tail",
                                 "2024-02-30\ud80012:30", "2024-01-02\ud80024:00"])
def test_iso_codepoint_admission_does_not_relax_complete_grammar(text):
    with pytest.raises(ValueError):
        Pddt.fromisoformat([text])
