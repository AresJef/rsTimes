"""PR-036: each cache/publication scenario starts with an actual fresh process."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("first", ("Asia/Shanghai","UTC"))
@pytest.mark.parametrize("mode", ("host_first","native_first","expression_first",
    "retry_host","retry_native","host_validation_precedes_publication",
    "native_success_host_unavailable","host_success_native_unavailable",
    "host_loses_native","host_loses_host","concurrent_same_name","lazy_and_explicit"))
def test_local_identity_first_success_and_backend_responsibilities(mode,first):
    result = subprocess.run([sys.executable,"-I","-B",str(Path(__file__).with_name("_product_ready_local_cases.py")),mode,first],
                            text=True,capture_output=True,timeout=25)
    assert result.returncode == 0, result.stdout+result.stderr
    record = json.loads(result.stdout)
    assert record["checks"] and record["gil_before"] == record["gil_after"]
