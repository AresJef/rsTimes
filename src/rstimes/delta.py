"""Public home of the Rust-backed :class:`Delta` calendar increment.

``rstimes.Delta`` and ``rstimes.delta.Delta`` are the same native class.
Delta values are immutable and compare by their fields with other Delta values.
Use apply_many for ordered batches and to_timedelta for exact time spans.
Only load pickle obtained from a trusted source.

Examples:
    >>> from datetime import date
    >>> date(2024, 1, 31) + Delta(months=1)
    datetime.date(2024, 2, 29)
    >>> delta = Delta(microseconds=-1)
    >>> (delta.days, delta.hours, delta.minutes, delta.seconds, delta.microseconds)
    (-1, 23, 59, 59, 999999)
"""
from ._native import Delta

__all__ = ["Delta"]
