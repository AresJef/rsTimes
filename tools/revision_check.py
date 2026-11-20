"""Run the approved Delta revision contracts in an explicitly installed environment."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    """Observe all selected assertions and preserve failures and binary provenance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = ROOT / "tests/delta/cases.py"
    spec = importlib.util.spec_from_file_location("delta_cases", path)
    shared = importlib.util.module_from_spec(spec)
    sys.modules["delta_cases"] = shared
    spec.loader.exec_module(shared)
    Delta, cases = shared.revision_contract_cases("rstimes", set(args.contracts.split(",")))
    if not cases:
        raise ValueError("No revision contracts were selected")
    import rstimes._native as native
    rows = [shared.observe(case, Delta) for case in cases]
    failures = [row for row in rows if row.get("result", {}).get("value") is not True]
    result = {"version": importlib.metadata.version("rstimes"), "python": sys.executable,
              "native": native.__file__, "native_sha256": hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
              "release": native.release_build(), "inputs_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "rows": rows, "passed": not failures}
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": not failures, "cases": len(cases), "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
