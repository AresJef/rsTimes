"""Use public locale metadata without depending on POSIX nl_langinfo."""
from datetime import datetime
import locale
import pytest
from rstimes import Pddt, Pydt
import rstimes._formatting as formatting


@pytest.mark.parametrize("fmt", ["%c", "%x", "%X"])
def test_composite_formats_work_without_nl_langinfo(monkeypatch, fmt):
    original = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, "C")
        with monkeypatch.context() as patch:
            patch.delattr(locale, "nl_langinfo", raising=False)
            formatting._locale_data.cache_clear()
            formatting._with_locale.cache_clear()
            for value in [datetime(2024, 5, 7, 13, 14, 15), datetime(2000, 2, 29, 1, 2, 3)]:
                text = value.strftime(fmt)
                expected = datetime.strptime(text, fmt)
                assert Pydt.strptime(text, fmt) == expected
                assert Pddt.strptime([text], fmt)[0].to_pydatetime() == expected
    finally:
        locale.setlocale(locale.LC_TIME, original)
        formatting._locale_data.cache_clear()
        formatting._with_locale.cache_clear()
