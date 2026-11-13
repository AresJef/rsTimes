"""Preserve the existing Delta nanosecond rules with public pandas 3 classes."""
from datetime import timedelta
import pandas as pd
from rstimes import Delta


def test_existing_delta_preserves_timestamp_nanosecond_tail():
    start=pd.Timestamp('2024-01-31 12:34:56.123456789')
    result=Delta(days=1)+start
    assert result==pd.Timestamp('2024-02-01 12:34:56.123456789')
    assert result.nanosecond==789


def test_existing_delta_rounds_pandas_span_once():
    start=pd.Timestamp('2024-01-01 00:00:00.000000123')
    result=Delta(microsecond=1).to_timedelta(start)
    assert type(result) is timedelta
    assert result==timedelta(microseconds=1)
