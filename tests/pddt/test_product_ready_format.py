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
