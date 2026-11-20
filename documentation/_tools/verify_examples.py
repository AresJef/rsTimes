"""Run page examples in isolated interpreters and record exact source and output."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import doctest
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import sysconfig
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"^```\{doctest\}(?:[ \t]+([^\n]*))?\n(.*?)^```[ \t]*$", re.M | re.S)
SCAN_EXAMPLES = runpy.run_path(str(ROOT / "_tools/example_blocks.py"))["scan_examples"]


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def identity() -> dict:
    import rstimes
    import rstimes._native as native

    package = Path(rstimes.__file__).resolve().parent
    installed = Path(sysconfig.get_path('purelib')).resolve() / 'rstimes'
    if package != installed:
        raise RuntimeError('Examples must import the installed wheel from this interpreter site-packages.')
    if Path(native.__file__).resolve().parent != package:
        raise RuntimeError('The loaded native module must belong to the installed package.')
    return {
        "version": importlib.metadata.version("rstimes"),
        "python": sys.version,
        "python_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        "package_path": str(package),
        "import_location_verified": True,
        "native": {p.name: sha(p.read_bytes()) for p in package.iterdir() if p.suffix in ('.so', '.pyd')},
        "stubs": {p.name: sha(p.read_bytes()) for p in package.glob("*.pyi")},
        "payload": {p.relative_to(package).as_posix(): sha(p.read_bytes()) for p in package.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'},
        "dependencies": installed_dependencies(),
        "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
    }


def installed_dependencies() -> dict:
    versions = {}
    for name in ('numpy', 'pandas', 'polars', 'polars-runtime-32', 'pyarrow', 'python-dateutil', 'pytz', 'tzdata', 'jax', 'jaxlib', 'torch', 'altair'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def load_data(name):
    return json.loads((ROOT / "_data" / (name + ".json")).read_text())


def check_runtime(actual, profile):
    release = load_data("release")
    inventory = load_data("public-api")
    expected = load_data("profiles")["profiles"][profile]
    matching = [w for w in release["files"].values() if w["packagetype"] == "bdist_wheel"
                and actual["native"] == {w["native"].removeprefix("rstimes/"): w["native_sha256"]}]
    if not matching or actual["stubs"] != inventory["stubs"] or actual["version"] != release["version"]:
        raise ValueError("The interpreter is not using the pinned public release")
    installed = {name: value for name, value in actual["payload"].items() if name not in actual["native"]}
    if installed != release["common_package_files"]:
        raise ValueError("Installed Python files differ from the public wheel")
    deps = {name: version for name, version in expected["dependencies"].items() if version is not None}
    if (actual["dependencies"] != deps or actual["python_minor"] != expected["python_minor"]
            or actual["gil_enabled"] is not expected["gil_enabled"]):
        raise ValueError(f"The interpreter and installed dependency versions do not match {profile}")
    return expected


def execute_program(program):
    """Run only inside a fresh, isolated interpreter working outside the source."""
    gil_before = getattr(sys, "_is_gil_enabled", lambda: True)()
    namespace = {"__name__": "__main__"}
    output, diagnostic = io.StringIO(), io.StringIO()
    caught, checks_error = None, None
    with redirect_stdout(output), redirect_stderr(diagnostic):
        try:
            exec(compile(program["code"], program["id"], "exec"), namespace)
        except Exception as error:
            caught = error
            namespace["example_error"] = error
        printed = output.getvalue().rstrip("\n")
        if caught is None or type(caught).__name__ == program.get("raises"):
            try:
                exec(compile(program["checks"], program["id"] + ":checks", "exec"), namespace)
            except Exception as error:
                checks_error = f"{type(error).__name__}: {error}"
    exception = None
    if caught is not None:
        exception = {"type": type(caught).__name__, "message": str(caught),
                     "notes": getattr(caught, "__notes__", [])}
    if exception is not None and type(caught).__name__ == program.get("raises"):
        printed = "\n".join(part for part in (printed, f"{exception['type']}: {exception['message']}") if part)
    return {
        "output": printed, "exception": exception, "checks_error": checks_error,
        "stderr": diagnostic.getvalue(), "gil_before": gil_before,
        "gil_after": getattr(sys, "_is_gil_enabled", lambda: True)(),
    }


def standalone_groups(programs, registrations, profile, expected_gil):
    groups = []
    for example in programs:
        registration = registrations[example.name]
        if profile not in registration["profiles"]:
            continue
        checks = "\n".join(registration["checks"])
        program = dict(id=example.name, code=example.code, checks=checks, raises=registration.get("raises"))
        with TemporaryDirectory(prefix="rstimes-doc-example-") as directory:
            child = subprocess.run(
                [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--execute"],
                input=json.dumps(program), text=True, capture_output=True, cwd=directory, timeout=90,
            )
        if child.returncode:
            actual = {"runner_error": child.stderr, "output": child.stdout}
            passed = False
        else:
            actual = json.loads(child.stdout)
            actual_error = (actual["exception"] or {}).get("type")
            passed = (actual["output"] == example.output and actual_error == registration.get("raises")
                      and not (actual["stderr"] or actual["checks_error"] or child.stderr)
                      and actual["gil_before"] is actual["gil_after"] is expected_gil)
        groups.append({
            "id": example.name, "format": "python", "sha256": sha(example.code.encode()),
            "output_sha256": sha(example.output.encode()), "checks_sha256": sha(checks.encode()),
            "expected_output": example.output, "actual": actual,
            "status": "pass" if passed else "fail", "assertions": len(registration["checks"]) + 1,
        })
    return groups


def legacy_groups(page, text, registrations, profile):
    """Keep old regression coverage while the beta pages are rewritten."""
    namespace = {"__name__": "__rstimes_documentation_example__"}
    output = io.StringIO()
    runner = doctest.DocTestRunner(verbose=True, optionflags=0)
    groups = []
    for index, match in enumerate(BLOCK.finditer(text), 1):
        name = (match[1] or f"example-{index}").strip()
        source = match[2]
        if profile not in registrations[name]["profiles"]:
            continue
        # No skips, global ellipsis, or regenerated expectations.
        if re.search(r"doctest:.*\b(?:SKIP|ELLIPSIS)\b", source):
            raise ValueError(f"{page}: skipped or loose examples are not accepted")
        test = doctest.DocTestParser().get_doctest(source, namespace, name, page.relative_to(ROOT).as_posix(), text[:match.start()].count("\n"))
        runner.run(test, out=output.write, clear_globs=False)
        namespace.update(test.globs)
        groups.append({"id": name, "sha256": sha(source.encode()), "assertions": len(test.examples)})
    return groups, runner.tries, runner.failures, output.getvalue()


def run_page(page: Path, profile: str) -> dict:
    content = page.read_bytes()
    text = content.decode()
    actual_identity = identity()
    expected = check_runtime(actual_identity, profile)
    relative = page.relative_to(ROOT).as_posix()
    entries = [item for item in load_data("examples")["examples"] if item["page"] == relative]
    registrations = {item["id"]: item for item in entries}
    programs = SCAN_EXAMPLES(text, page.suffix)
    legacy = [block[1].strip() for block in BLOCK.finditer(text)]
    declared = [example.name for example in programs] + legacy
    if (len(declared) != len(set(declared)) or len(registrations) != len(entries)
            or set(declared) != set(registrations)):
        raise ValueError(f"{relative}: registered and authored examples differ")
    for example in programs:
        if registrations[example.name].get("format") != "python":
            raise ValueError(f"{relative}: {example.name} must be registered as a Python example")
    groups = standalone_groups(programs, registrations, profile, expected["gil_enabled"])
    old, old_tries, old_failures, transcript = legacy_groups(page, text, registrations, profile)
    failures = [group for group in groups if group["status"] != "pass"]
    if failures:
        transcript += json.dumps(failures, ensure_ascii=False, indent=2)
    return {
        "page": relative,
        "page_sha256": sha(content), "profile": profile,
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "verifier_sha256": sha(Path(__file__).read_bytes()),
        "groups": groups + old, "attempted": len(groups) + old_tries,
        "failures": len(failures) + old_failures,
        "status": "fail" if failures or old_failures else "pass",
        "identity": actual_identity, "transcript": transcript,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs="*", type=Path)
    parser.add_argument("--profile", default="full")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--single", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    pages = [(ROOT / p).resolve() for p in args.pages] or sorted(
        {ROOT / row["page"] for row in load_data("examples")["examples"] if args.profile in row["profiles"]})
    if any(not page.is_relative_to(ROOT) for page in pages):
        parser.error("Examples must come from this documentation tree")
    if args.single:
        assert len(pages) == 1
        result = run_page(pages[0], args.profile)
        dest = args.evidence_dir / (pages[0].relative_to(ROOT).as_posix().replace("/", "--") + ".json")
        dest.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: result[k] for k in ("page", "status", "attempted", "failures", "page_sha256")}))
        if result["failures"]:
            for failure in re.findall(r"\*{20,}\n.*?(?=\nTrying:|\Z)", result["transcript"], re.S):
                print(failure)
            for failure in (group for group in result["groups"] if group.get("status") == "fail"):
                print(json.dumps(failure, ensure_ascii=False))
        return int(result["failures"] > 0)
    failed = 0
    for page in pages:
        command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), str(page), "--profile", args.profile, "--evidence-dir", str(args.evidence_dir.resolve()), "--single"]
        result = subprocess.run(command, check=False, timeout=900)
        failed += int(result.returncode != 0)
    return int(failed > 0)


if __name__ == "__main__":
    if sys.argv[1:] == ["--execute"]:
        print(json.dumps(execute_program(json.load(sys.stdin))))
        raise SystemExit()
    raise SystemExit(main())
