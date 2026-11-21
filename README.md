# rsTimes

rsTimes helps you work with calendar dates in Python, pandas, and Polars. Add a calendar month, parse a date string, or apply the same date operation to a column. The scalar and column APIs share a Rust implementation for common date rules.

## Install

```sh
python -m pip install rsTimes
```

The package is named `rsTimes` on PyPI. Import it as `rstimes`.

## Try a calendar month

An invoice dated January 31 renews on the last valid day of February when you add one calendar month. A fixed 30-day duration takes it into March.

```python
from datetime import datetime
from rstimes import Delta

invoice = datetime(2024, 1, 31)
renewal = invoice + Delta(months=1)
print(renewal.date())
# 2024-02-29
```

## Choose the API that fits your data

- Use `Delta` for calendar arithmetic on Python dates. Use `Pydt` for a single datetime or `parse_str` to read a date from text.
- Use `Pddt` for date columns or indexes in pandas. Install it with `python -m pip install "rsTimes[pandas]"`.
- Use `Pldt` for date columns in Polars or `.pldt` expressions in DataFrames and LazyFrames. Install it with `python -m pip install "rsTimes[polars]"`.

Wheels are available for 64-bit CPython 3.12–3.15 on macOS, Windows, and Linux. Free-threaded 3.14 and 3.15 wheels require compatible dependencies. rsTimes is MIT-licensed.

[Developer documentation](https://aresjef.github.io/rsTimes/) · [Release notes and platform support](https://github.com/AresJef/rsTimes/blob/v1.1.0/docs/releases/v1.1.0.md) · [Free-threaded setup](https://github.com/AresJef/rsTimes/blob/v1.1.0/docs/free-threaded-python.md) · [Type checking](https://github.com/AresJef/rsTimes/blob/v1.1.0/docs/type-checking.md) · [Report an issue](https://github.com/AresJef/rsTimes/issues)
