"""ProductReady Pydt regressions preserve the mature Python output domain."""
from datetime import datetime

import pytest

from rstimes import Pydt


@pytest.mark.parametrize("literal", ["", "日期", "🌏", "\0", "\ud800", "\udfff"])
@pytest.mark.parametrize("suffix,expanded", [("%Y", "%Y"), ("%%f", "%%f"),
                                           ("%f", "123456"), ("%.3f", ".123"),
                                           ("%.0f", "")])
def test_python_strftime_literals_keep_mature_platform_result(literal, suffix, expanded):
    ordinary = datetime(2024, 1, 2, 3, 4, 5, 123456)
    value = Pydt.fromdatetime(ordinary)
    try:
        expected = ordinary.strftime(literal + expanded)
    except Exception as error:
        with pytest.raises(type(error)):
            value.strftime(literal + suffix)
    else:
        assert value.strftime(literal + suffix) == expected


@pytest.mark.parametrize("literal", ["", "日期", "🌏", "\0", "\ud800", "\udfff"])
def test_strptime_literal_codepoints_are_preserved_and_mismatch_is_a_value_error(literal):
    text = "2024-01-02" + literal
    fmt = "%Y-%m-%d" + literal
    expected = datetime.strptime(text, fmt)
    assert Pydt.strptime(text, fmt) == expected
    with pytest.raises(ValueError, match="does not match") as observed:
        Pydt.strptime(text + "X", fmt + "Y")
    assert not isinstance(observed.value, UnicodeEncodeError)
