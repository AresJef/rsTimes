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
    """Return interpreter, platform and installed dependency versions for evidence."""
    versions = {}
    for name in ("cytimes", "rstimes", "numpy", "pandas", "python-dateutil", "tzdata", "pendulum", "babel", "typing-extensions"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": sys.version, "executable": sys.executable,
            "platform": platform.platform(), "machine": platform.machine(), "dependencies": versions}


def worker(package, selected, revision=False):
    """Observe selected deterministic cases in an isolated installed package.

    Args:
        package (str): cytimes or rstimes to import.
        selected (str): Comma-separated groups, all, or a candidate-only contract group.

    Returns:
        dict: Environment, loaded package path, input hash and structured observations.

    Raises:
        ValueError: No cases match the selected groups."""
    spec = importlib.util.spec_from_file_location("delta_cases", CASES)
    loaded_cases = importlib.util.module_from_spec(spec)
    sys.modules["delta_cases"] = loaded_cases
    spec.loader.exec_module(loaded_cases)
    shared = vars(loaded_cases)
    wanted = set(selected.split(","))
    contract = bool(wanted & {"state", "pickle-copy", "exports", "candidate-contracts"})
    Delta, records = (shared["candidate_cases"](package, revision=revision) if contract
                      else shared["cases"](package))
    chosen = records if "all" in wanted or "candidate-contracts" in wanted else [r for r in records if r.group in wanted]
    if not chosen:
        raise ValueError(f"No implemented cases for groups {sorted(wanted)}")
    loaded = sys.modules[package]
    return {"environment": environment(), "package_file": loaded.__file__,
            "inputs_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
            "rows": [shared["observe"](case, Delta) for case in chosen]}


def python_in(env):
    """Return the platform-specific Python executable inside env."""
    return Path(env).resolve() / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run_worker(env, package, group, revision=False):
    """Run one isolated worker and parse its complete JSON result.

    Args:
        env (str | Path): Installed virtual environment.
        package (str): Package selected by the worker.
        group (str): Case group selection.

    Raises:
        RuntimeError: The worker exits unsuccessfully.
        subprocess.TimeoutExpired: The worker exceeds the 60-second limit.
        ValueError: Worker output is not valid JSON."""
    command = [str(python_in(env)), "-I", str(Path(__file__).resolve()),
               "--worker", package, "--group", group]
    if revision:
        command.append("--revision")
    run = subprocess.run(command, text=True, capture_output=True, timeout=60)
    if run.returncode:
        raise RuntimeError(f"Worker failed ({run.returncode}): {run.stderr}")
    result = json.loads(run.stdout)
    result["command"] = command
    result["stderr"] = run.stderr
    return result


def compare(reference, candidate, policies=None):
    """Return unapproved differences between complete reference/candidate observations.

    D1 must reject real overflow. Approved module/type-name differences are handled
    explicitly; missing or duplicate case IDs cannot silently pass.

    Raises:
        ValueError: Case IDs are duplicated or the case sets differ."""
    expected = {r["case"]: r for r in reference["rows"]}
    actual = {r["case"]: r for r in candidate["rows"]}
    if len(expected) != len(reference["rows"]) or len(actual) != len(candidate["rows"]):
        raise ValueError("Duplicate case IDs cannot silently replace an observation")
    if expected.keys() != actual.keys():
        raise ValueError("Case sets differ; missing rows cannot pass")
    differences = []
    for name in expected:
        if policies and name in policies:
            policy = policies[name]
            matches = (actual[name].get("result") == policy["result"] if "result" in policy
                       else actual[name].get("error", {}).get("type") == policy["error_type"])
            if not matches:
                differences.append({"case": name, "required_revision": policy,
                                    "expected": expected[name], "actual": actual[name]})
            continue
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
    """Verify that the oracle records agree with repeated/reference expectations.

    Args:
        oracle (str | Path): Frozen reference environment.

    Returns:
        dict: Self-check status and observations."""
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
    """Run native wheel smoke checks using the specified installed candidate.

    Args:
        wheel (str | Path): Wheel whose identity is recorded.
        candidate (str | Path): Installed environment to validate.

    Returns:
        dict: Wheel hash, environment checks and subprocess results."""
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
    """Run the original timestamp tests in candidate and report their exit status."""
    command = [str(python_in(candidate)), "-I", "-m", "pytest", "--import-mode=importlib",
               str(ROOT / "tests/test_rstimes.py")]
    run = subprocess.run(command, text=True, capture_output=True, timeout=120)
    return {"status": "passed" if run.returncode == 0 else "failed", "command": command,
            "stdout": run.stdout, "stderr": run.stderr, "returncode": run.returncode}


def main():
    """Dispatch the requested validation group and optionally save a fresh report.

    Raises:
        FileExistsError: A report path would overwrite earlier evidence.
        SystemExit: Invalid CLI arguments or failed validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("cytimes", "rstimes"))
    parser.add_argument("--group", default="all")
    parser.add_argument("--oracle-env", default=str(ROOT / ".local/delta/oracle"))
    parser.add_argument("--candidate-env", default=str(ROOT / ".local/delta/candidate"))
    parser.add_argument("--wheel")
    parser.add_argument("--report")
    parser.add_argument("--revision", action="store_true", help="Apply explicit approved revision expectations")
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, args.group, args.revision), ensure_ascii=False))
        return
    if args.group == "selfcheck":
        result = selfcheck(args.oracle_env)
    elif args.group in {"state", "pickle-copy", "exports", "candidate-contracts"}:
        candidate = run_worker(args.candidate_env, "rstimes", args.group, args.revision)
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
        candidate = run_worker(args.candidate_env, "rstimes", args.group, args.revision)
        policies = None
        if args.revision:
            spec = importlib.util.spec_from_file_location("revision_inputs", CASES)
            shared = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(shared)
            policies = shared.revision_expectations()
            if args.group == "all" and not set(policies) <= {row["case"] for row in reference["rows"]}:
                raise ValueError("A revision policy names an absent legacy input")
        differences = compare(reference, candidate, policies)
        originals = {row["case"]: row for row in reference["rows"]}
        approved = [{"case": row["case"], "decision": "D1", "reference": originals[row["case"]],
                     "candidate": row} for row in candidate["rows"]
                    if row.get("difference") == "D1" and row.get("error", {}).get("type") == "builtins.OverflowError"
                    and "result" in originals[row["case"]]
                    and (not policies or row["case"] not in policies)]
        if policies:
            approved.extend({"case": row["case"], "decision": policies[row["case"]]["rule"],
                             "required": policies[row["case"]], "reference": originals[row["case"]],
                             "candidate": row} for row in candidate["rows"] if row["case"] in policies)
        for row in candidate["rows"]:
            if row["case"] in PACKAGE_NAME_ERRORS:
                original = originals[row["case"]]
                if original != row and not compare({"rows": [original]}, {"rows": [row]}):
                    approved.append({"case": row["case"], "decision": "F2 exact quoted package type name",
                                     "reference": original, "candidate": row})
        result = {"status": "failed" if differences else "passed", "reference": reference,
                  "candidate": candidate, "differences": differences, "approved_differences": approved}
    if args.group == "all":
        contracts = run_worker(args.candidate_env, "rstimes", "candidate-contracts", args.revision)
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
