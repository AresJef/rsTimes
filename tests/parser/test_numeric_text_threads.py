"""Shared immutable numeric text is safe under ordinary and t interpreters."""
import json
import subprocess
import sys

import pytest


@pytest.mark.parametrize("workers", [2, 4])
def test_numeric_text_shared_reads_have_a_reclaimable_process_deadline(workers):
    code = r'''
from concurrent.futures import ThreadPoolExecutor
import json
import sys
from rstimes import parse_to_float, parse_to_integer

gil_before = getattr(sys, "_is_gil_enabled", lambda: True)()
integer_text = "quantity -123.456.789 items"
floating_text = "price -1.234,56 EUR"
def run(seed):
    total = 0
    for _ in range(500):
        assert parse_to_integer(integer_text, strict=False, allow_grouping=True) == -123456789
        assert parse_to_float(floating_text, strict=False, allow_grouping=True) == -1234.56
        assert parse_to_integer("-170141183460469231731687303715884105728") == -(2**127)
        try:
            parse_to_integer("1,23,456", allow_grouping=True)
        except ValueError:
            total += 1
        else:
            raise AssertionError("invalid grouping accepted")
    return total
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    values = list(pool.map(run, range(WORKERS)))
gil_after = getattr(sys, "_is_gil_enabled", lambda: True)()
assert gil_before == gil_after
print(json.dumps(dict(values=values, gil_before=gil_before, gil_after=gil_after)))
'''.replace("WORKERS", str(workers))
    # The whole child is reclaimed on timeout, even if a thread stalls or an
    # executor cannot shut down. Never leave a thread stress test in pytest itself.
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code],
                            text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["values"] == [500] * workers
