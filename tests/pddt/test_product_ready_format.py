"""ProductReady format admission preserves native and mature output contracts."""
import numpy as np
import pandas as pd
import pytest

from rstimes import Pddt


class Format(str):
    """A passive, supported subclass with ordinary stored format text."""


@pytest.mark.parametrize("factory", [str, Format, np.str_])
@pytest.mark.parametrize("fmt,expected", [("%Y", "2024"), ("", ""),
                                         ("%%f", "%f"), ("%f", "123456789"),
                                         ("%.3f", ".123")])
@pytest.mark.parametrize("shape", ["empty", "missing", "valid", "mixed"])
def test_format_subclass_has_same_admission_on_system_and_fraction_paths(factory, fmt,
                                                                        expected, shape):
    import math

    stamp = "2024-01-02T03:04:05.123456789"
    values = {"empty": [], "missing": [None], "valid": [stamp], "mixed": [stamp, None]}[shape]
    result = Pddt(values, unit="ns", name="stamp").strftime(factory(fmt))
    assert result.name == "stamp"
    if fmt in ("%Y", "", "%%f"):
        standard = pd.DatetimeIndex([pd.Timestamp(value) if value is not None else pd.NaT
                                     for value in values]).strftime(fmt)
        assert result.dtype == standard.dtype
    else:
        assert result.dtype == object
    assert len(result) == len(values)
    for value, output in zip(values, result):
        if value is None:
            assert type(output) is float and math.isnan(output)
        else:
            assert type(output) is str and output == expected


@pytest.mark.parametrize("literal", ["", "日期", "🌏", "\0", "\ud800", "\udfff"])
def test_python_format_literals_preserve_dates_fraction_and_missing(literal):
    stamp = pd.Timestamp("2024-01-02T03:04:05.123456789")
    source = Pddt([stamp, None], unit="ns", name="stamp")
    expected = stamp.strftime(literal + "%Y|123456789|.123|")
    result = source.strftime(literal + "%Y|%f|%.3f|%.0f")
    assert result.name == "stamp" and result[0] == expected
    assert pd.isna(result[1])
    fmt = "%Y-%m-%d" + literal
    parsed = Pddt.strptime(["2024-01-02" + literal], fmt)
    assert parsed.unit == "us" and parsed.asi8.tolist() == [1704153600000000]


@pytest.mark.parametrize("values", [[], [None], [None, None]])
@pytest.mark.parametrize("fmt", ["%.12f", "\ud800%.12f"])
def test_invalid_fraction_format_is_checked_even_without_valid_dates(values, fmt):
    with pytest.raises(ValueError, match="fraction precision") as observed:
        Pddt(values, unit="us").strftime(fmt)
    assert not isinstance(observed.value, UnicodeEncodeError)


@pytest.mark.parametrize("values", [[], [None], ["2024-01-02T03:04:05.123456789"]])
@pytest.mark.parametrize("display", ["raises", "pretends_str"])
def test_nonstring_format_uses_real_type_without_display_class(values, display):
    calls = []

    class NotAFormat:
        @property
        def __class__(self):
            calls.append("display class")
            if display == "raises":
                raise LookupError("unrelated display identity")
            return str

    with pytest.raises(TypeError) as observed:
        Pddt(values, unit="ns").strftime(NotAFormat())
    assert not calls
    assert "Pddt.strftime(): format=" in str(observed.value)


@pytest.mark.parametrize("fmt,expected", [("%Y", "2024"), ("%f", "123456789"),
                                         ("%.3f", ".123")])
def test_real_string_subclass_ignores_display_and_sequence_overrides(fmt, expected):
    class StoredFormat(str):
        def __str__(self):
            raise AssertionError("display is not the format's stored content")

        def __getitem__(self, key):
            raise AssertionError("format storage is not a business sequence")

        def __len__(self):
            raise AssertionError("format length comes from real string storage")

    source = Pddt(["2024-01-02T03:04:05.123456789", None], unit="ns", name="stamp")
    result = source.strftime(StoredFormat(fmt))
    assert result.name == "stamp" and result[0] == expected and pd.isna(result[1])
