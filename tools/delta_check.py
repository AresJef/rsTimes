"""Compare installed Delta packages in isolated CPython processes."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests/delta/cases.py"
PACKAGE_NAME_ERRORS = set(json.loads((CASES.parent / "package_name_errors.json").read_text())["case_ids"]) | {"properties:write", "properties:delete", "properties:private", "properties:immutable-type", "dateutil:invalid:delta"}


def environment():
    versions = {}
    for name in ("cytimes", "rstimes", "numpy", "pandas", "python-dateutil", "tzdata", "pendulum", "babel", "typing-extensions"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": sys.version, "executable": sys.executable,
            "platform": platform.platform(), "machine": platform.machine(), "dependencies": versions}


def worker(package, selected):
    spec = importlib.util.spec_from_file_location("delta_cases", CASES)
    loaded_cases = importlib.util.module_from_spec(spec)
    sys.modules["delta_cases"] = loaded_cases
    spec.loader.exec_module(loaded_cases)
    shared = vars(loaded_cases)
    wanted = set(selected.split(","))
    contract = bool(wanted & {"state", "pickle-copy", "exports", "candidate-contracts"})
    Delta, records = shared["candidate_cases" if contract else "cases"](package)
    chosen = records if "all" in wanted or "candidate-contracts" in wanted else [r for r in records if r.group in wanted]
    if not chosen:
        raise ValueError(f"No implemented cases for groups {sorted(wanted)}")
    loaded = sys.modules[package]
    return {"environment": environment(), "package_file": loaded.__file__,
            "inputs_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
            "rows": [shared["observe"](case, Delta) for case in chosen]}


def python_in(env):
    return Path(env).resolve() / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run_worker(env, package, group):
    command = [str(python_in(env)), "-I", str(Path(__file__).resolve()),
               "--worker", package, "--group", group]
    run = subprocess.run(command, text=True, capture_output=True, timeout=60)
    if run.returncode:
        raise RuntimeError(f"Worker failed ({run.returncode}): {run.stderr}")
    result = json.loads(run.stdout)
    result["command"] = command
    result["stderr"] = run.stderr
    return result


def compare(reference, candidate):
    expected = {r["case"]: r for r in reference["rows"]}
    actual = {r["case"]: r for r in candidate["rows"]}
    if len(expected) != len(reference["rows"]) or len(actual) != len(candidate["rows"]):
        raise ValueError("Duplicate case IDs cannot silently replace an observation")
    if expected.keys() != actual.keys():
        raise ValueError("Case sets differ; missing rows cannot pass")
    differences = []
    for name in expected:
        # D1 must reject overflow even if silently wrapping would match upstream.
        if expected[name].get("difference") == "D1":
            if (actual[name].get("difference") == "D1"
                    and actual[name].get("error", {}).get("type") == "builtins.OverflowError"
                    and "result" in expected[name]):
                continue
            differences.append({"case": name, "required": "D1 OverflowError",
                                "expected": expected[name], "actual": actual[name]})
            continue
        if expected[name] == actual[name]:
            continue
        if name in PACKAGE_NAME_ERRORS:
            mapped = copy.deepcopy(expected[name])
            if mapped.get("error", {}).get("type") in {"builtins.AttributeError", "builtins.TypeError", "rstimes.errors.InvalidRelativeDelta"}:
                mapped["error"]["message"] = mapped["error"]["message"].replace(
                    "'cytimes.delta.Delta'", "'rstimes.delta.Delta'")
                if mapped == actual[name]:
                    continue
        differences.append({"case": name, "expected": expected[name], "actual": actual[name]})
    return differences


def selfcheck(oracle):
    first = run_worker(oracle, "cytimes", "selfcheck")
    second = run_worker(oracle, "cytimes", "selfcheck")
    assert not compare(first, second), "Reference observations changed"
    wrong_field = copy.deepcopy(second)
    wrong_field["rows"][0]["result"]["fields"]["days"] += 1
    wrong_error = copy.deepcopy(second)
    wrong_error["rows"][2]["error"]["type"] = "builtins.ValueError"
    assert len(compare(first, wrong_field)) == 1
    assert len(compare(first, wrong_error)) == 1
    overflow_contract = copy.deepcopy(first)
    overflow_contract["rows"] = [overflow_contract["rows"][0]]
    overflow_contract["rows"][0]["difference"] = "D1"
    assert len(compare(overflow_contract, overflow_contract)) == 1, "D1 cannot accept matching wraparound"
    return {"status": "passed", "reference": first,
            "selfcheck": {"stable_reference": True, "detects_field_error": True,
                          "detects_exception_type_error": True, "requires_D1_overflow_error": True}}


def installed(wheel, candidate):
    wheel = Path(wheel).resolve(strict=True)
    interpreter = python_in(candidate)
    run = subprocess.run([str(interpreter), "-I", "-m", "pip", "install", "--no-deps",
                          "--force-reinstall", str(wheel)], text=True, capture_output=True, timeout=120)
    if run.returncode:
        raise RuntimeError(run.stderr)
    script = "import json,rstimes,rstimes._native as n; print(json.dumps({'package':rstimes.__file__,'native':n.__file__}))"
    loaded = subprocess.run([str(interpreter), "-I", "-c", script], text=True,
                            capture_output=True, check=True, timeout=30)
    files = json.loads(loaded.stdout)
    assert Path(files["package"]).is_relative_to(Path(candidate).resolve())
    assert Path(files["native"]).suffix in (".so", ".pyd")
    return {"status": "passed", "wheel": str(wheel),
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(), "loaded": files}


def existing(candidate):
    command = [str(python_in(candidate)), "-I", "-m", "pytest", "--import-mode=importlib",
               str(ROOT / "tests/test_rstimes.py")]
    run = subprocess.run(command, text=True, capture_output=True, timeout=120)
    return {"status": "passed" if run.returncode == 0 else "failed", "command": command,
            "stdout": run.stdout, "stderr": run.stderr, "returncode": run.returncode}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("cytimes", "rstimes"))
    parser.add_argument("--group", default="all")
    parser.add_argument("--oracle-env", default=str(ROOT / ".local/delta/oracle"))
    parser.add_argument("--candidate-env", default=str(ROOT / ".local/delta/candidate"))
    parser.add_argument("--wheel")
    parser.add_argument("--report")
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, args.group), ensure_ascii=False))
        return
    if args.group == "selfcheck":
        result = selfcheck(args.oracle_env)
    elif args.group in {"state", "pickle-copy", "exports", "candidate-contracts"}:
        candidate = run_worker(args.candidate_env, "rstimes", args.group)
        failures = [row for row in candidate["rows"] if row.get("result") != {"type": "builtins.bool", "value": True}]
        result = {"status": "failed" if failures else "passed", "candidate": candidate, "differences": failures,
                  "contract": "D2 new-package contract; each row asserts its fields, errors and invariants"}
    elif args.group == "installed":
        if not args.wheel:
            parser.error("installed requires --wheel")
        result = installed(args.wheel, args.candidate_env)
    elif args.group == "existing":
        result = existing(args.candidate_env)
    else:
        reference = run_worker(args.oracle_env, "cytimes", args.group)
        candidate = run_worker(args.candidate_env, "rstimes", args.group)
        differences = compare(reference, candidate)
        originals = {row["case"]: row for row in reference["rows"]}
        approved = [{"case": row["case"], "decision": "D1", "reference": originals[row["case"]],
                     "candidate": row} for row in candidate["rows"]
                    if row.get("difference") == "D1" and row.get("error", {}).get("type") == "builtins.OverflowError"
                    and "result" in originals[row["case"]]]
        for row in candidate["rows"]:
            if row["case"] in PACKAGE_NAME_ERRORS:
                original = originals[row["case"]]
                if original != row and not compare({"rows": [original]}, {"rows": [row]}):
                    approved.append({"case": row["case"], "decision": "F2 exact quoted package type name",
                                     "reference": original, "candidate": row})
        result = {"status": "failed" if differences else "passed", "reference": reference,
                  "candidate": candidate, "differences": differences, "approved_differences": approved}
    if args.group == "all":
        contracts = run_worker(args.candidate_env, "rstimes", "candidate-contracts")
        contract_failures = [row for row in contracts["rows"] if row.get("result") != {"type": "builtins.bool", "value": True}]
        result["candidate_contracts"] = contracts
        result["differences"].extend(contract_failures)
        if contract_failures:
            result["status"] = "failed"
    result["utc"] = datetime.now(timezone.utc).isoformat()
    if args.report:
        output = Path(args.report)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(f"Do not overwrite an earlier result: {output}")
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "report": args.report,
                      "differences": len(result.get("differences", ())),
                      "approved_differences": len(result.get("approved_differences", ()))}, ensure_ascii=False))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
