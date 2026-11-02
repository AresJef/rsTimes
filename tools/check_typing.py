"""Check installed contracts and active Python code with pinned Pyright only.

The original three positive and 48 negative locations are unchanged. Full mode
also reads every active source/tool/demo file, preserving deliberate rejected
examples and individually documented external-type limitations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tokenize
from typing import NotRequired, TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
PYRIGHT_VERSION = "1.1.414"
NODE_VERSION = "v26.7.0"
FIXTURES = (
    ("public_valid.py", set()),
    ("astra_configs_valid.py", set()),
    ("pldt_valid.py", set()),
    ("public_invalid.py", set(range(2, 14)) | {15, 16}),
    ("astra_configs_invalid.py", set(range(9, 29))),
    ("pldt_invalid.py", set(range(3, 17))),
    ("native_boundary_valid.py", set()),
    ("native_boundary_invalid.py", set(range(5, 9))),
)


class _Position(TypedDict):
    """A zero-based position emitted by the pinned checker."""

    line: int
    character: int


class _Range(TypedDict):
    """The source span of one located diagnostic."""

    start: _Position
    end: _Position


class _Diagnostic(TypedDict):
    """One raw diagnostic; startup errors need not have a source position."""

    file: str
    severity: str
    message: str
    rule: NotRequired[str]
    range: NotRequired[_Range]


class _TypeCompleteness(TypedDict):
    """The installed package identity and public completeness evidence."""

    packageRootDirectory: str
    exportedSymbolCounts: dict[str, int]
    completenessScore: float


class _Report(TypedDict):
    """The JSON boundary of a completed Pyright invocation."""

    version: str
    generalDiagnostics: list[_Diagnostic]
    summary: dict[str, int | float]
    typeCompleteness: NotRequired[_TypeCompleteness]


def _digest(path: Path) -> str:
    """Identify the exact checked source or installed payload."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: Sequence[str], output: Path, env: dict[str, str]) -> tuple[int, _Report]:
    """Retain raw diagnostics from the pinned executable, including failures."""
    result = subprocess.run(command, cwd=tempfile.gettempdir(), env=env,
                            text=True, capture_output=True, check=False)
    output.with_suffix(".stderr.txt").write_text(result.stderr)
    output.write_text(result.stdout)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Pyright could not complete: {result.returncode}: {result.stderr}")
    report = cast(_Report, json.loads(result.stdout))
    assert report["version"] == PYRIGHT_VERSION, report.get("version")
    return result.returncode, report


def _errors(report: _Report) -> list[_Diagnostic]:
    """Keep the engine's actual error diagnostics; warnings remain in raw JSON."""
    return [item for item in report["generalDiagnostics"] if item["severity"] == "error"]


def _installed(command: list[str], output: Path, env: dict[str, str], language: str) -> dict[str, object]:
    """Require every original/new positive and negative location and known exports."""
    config = output / "installed.pyright.json"
    config.write_text(json.dumps({
        "typeCheckingMode": "standard", "pythonVersion": language,
        "autoSearchPaths": False, "extraPaths": [], "include": [],
        "enableTypeIgnoreComments": False,
        "reportUnnecessaryTypeIgnoreComment": "error",
    }, indent=2) + "\n")
    rows = []
    for filename, expected in FIXTURES:
        source = ROOT / "tests/typing" / filename
        status, report = _run(command + ["--project", str(config), "--outputjson", str(source)],
                              output / (filename + ".pyright.json"), env)
        errors = _errors(report)
        actual = set()
        for item in errors:
            assert "range" in item, (filename, item)
            actual.add(item["range"]["start"]["line"] + 1)
        assert status == (1 if expected else 0), (filename, status, errors)
        assert actual == expected, (filename, sorted(actual), sorted(expected), errors)
        rows.append({"file": filename, "source_sha256": _digest(source),
                     "error_lines": sorted(actual), "engine_exit": status})
    status, report = _run(command + ["--project", str(config), "--verifytypes", "rstimes",
                                     "--ignoreexternal", "--outputjson"],
                          output / "verifytypes.json", env)
    assert "typeCompleteness" in report, report
    completeness = report["typeCompleteness"]
    package = Path(completeness["packageRootDirectory"]).resolve()
    assert package.is_relative_to(Path(sys.prefix).resolve()), package
    assert status == 0 and not _errors(report), report["generalDiagnostics"]
    assert completeness["exportedSymbolCounts"]["withUnknownType"] == 0, completeness
    assert completeness["exportedSymbolCounts"]["withAmbiguousType"] == 0, completeness
    assert completeness["completenessScore"] == 1, completeness
    return {"fixtures": rows, "original_negative_locations": 48,
            "new_negative_locations": 4, "package": str(package),
            "public_types": completeness["exportedSymbolCounts"],
            "installed_payload": {p.name: _digest(p) for p in package.iterdir()
                                  if p.suffix in (".py", ".pyi", ".so", ".pyd") or p.name == "py.typed"}}


def _statement_lines(path: Path, statement: str) -> list[int]:
    """Locate an unchanged reviewed statement without freezing incidental line numbers."""
    return [index + 1 for index, line in enumerate(path.read_text().splitlines())
            if line.split("# pyright:", 1)[0].strip() == statement]


def _exceptions() -> int:
    """Reject unrecorded line suppressions and all legacy/file-wide ignore switches."""
    manifest = json.loads((ROOT / "tests/typing/pyright_exceptions.json").read_text())
    expected = set()
    for item in manifest["entries"]:
        path = ROOT / item["file"]
        # Identical calls can occur in different, independently narrowed branches.
        # Match the single reviewed ID, rather than suppressing every equal line.
        lines = [index + 1 for index, line in enumerate(path.read_text().splitlines())
                 if line.split("# pyright:", 1)[0].strip() == item["statement"]
                 and f"-- {item['id']};" in line]
        assert len(lines) == 1, item
        expected.add((item["file"], lines[0], tuple(sorted(set(item["rules"])))))
    actual = set()
    scope = json.loads((ROOT / "pyrightconfig.json").read_text())["include"]
    paths = []
    for name in scope:
        path = ROOT / name
        paths.extend([*path.rglob("*.py"), *path.rglob("*.pyi")] if path.is_dir() else [path])
    for path in paths:
        text = path.read_text()
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type != tokenize.COMMENT:
                continue
            comment = token.string
            assert not comment.startswith("# type: ignore"), (path, token.start)
            if not comment.startswith("# pyright:"):
                continue
            assert comment.startswith("# pyright: ignore["), (path, token.start, comment)
            rules = comment.split("[", 1)[1].split("]", 1)[0]
            actual.add((path.relative_to(ROOT).as_posix(), token.start[0],
                        tuple(sorted(rule.strip() for rule in rules.split(",")))))
    assert actual == expected, {"unrecorded": sorted(actual - expected),
                               "stale": sorted(expected - actual)}
    return len(actual)


def _full(command: list[str], output: Path, env: dict[str, str], oracle: Path,
          language: str) -> dict[str, object]:
    """Check all active code with original upstream symbols and exact demo diagnostics."""
    assert oracle.is_dir() and (oracle / "delta.pyi").is_file(), oracle
    symbols = output / "oracle-symbols/cytimes"
    symbols.mkdir(parents=True, exist_ok=True)
    inputs = {}
    # This is a read-only typing view, not an oracle install in the pandas3 lane.
    for source in oracle.iterdir():
        if source.suffix == ".pyi" or source.name in ("__init__.py", "errors.py"):
            shutil.copyfile(source, symbols / source.name)
            inputs[source.name] = _digest(source)
    config = output / "full.pyright.json"
    config.write_text(json.dumps({"extends": str(ROOT / "pyrightconfig.json"),
        "pythonVersion": language,
        "extraPaths": [str(ROOT / "src"), str(ROOT / "demo"), str(ROOT / "tools"), str(symbols.parent)]}, indent=2) + "\n")
    status, report = _run(command + ["--project", str(config), "--outputjson"],
                          output / "full-source.json", env)
    expected: Counter[tuple[str, int, str]] = Counter()
    items = json.loads((ROOT / "tests/typing/demo_diagnostics.json").read_text())["entries"]
    for item in items:
        lines = _statement_lines(ROOT / item["file"], item["statement"])
        line = lines[item["occurrence"]]
        for rule, count in item["expected_rules"].items():
            expected[(item["file"], line, rule)] += count
    actual: Counter[tuple[str, int, str]] = Counter()
    for item in _errors(report):
        assert "range" in item, item
        key = (Path(item["file"]).resolve().relative_to(ROOT).as_posix(),
               item["range"]["start"]["line"] + 1, item.get("rule", ""))
        actual[key] += 1
    assert actual == expected, {"unexpected": list((actual - expected).items()),
                               "missing": list((expected - actual).items())}
    assert status == (1 if expected else 0), status
    return {"files_analyzed": report["summary"]["filesAnalyzed"],
            "expected_demo_diagnostics": sum(expected.values()), "unexpected_errors": 0,
            "engine_exit": status, "documented_line_exceptions": _exceptions(),
            "oracle_symbol_source": str(oracle), "oracle_symbol_sha256": inputs}


def main() -> None:
    """Run installed parity by default; full mode adds every active implementation/tool/demo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--oracle-package", type=Path)
    parser.add_argument("--python-version", choices=("3.12", "3.14", "3.15"), default="3.12")
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "evidence/typing-pyright")
    args = parser.parse_args()
    output = args.evidence_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    executable = ROOT / "tools/typing/node_modules/pyright/index.js"
    assert executable.is_file(), "Install the pinned checker: npm --prefix tools/typing ci --ignore-scripts --omit=optional"
    node = shutil.which("node")
    assert node is not None, f"Install Node {NODE_VERSION}"
    version = subprocess.check_output([node, "--version"], text=True).strip()
    assert version == NODE_VERSION, (version, NODE_VERSION)
    env = dict(os.environ, VIRTUAL_ENV=sys.prefix)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    command = [node, str(executable), "--pythonpath", sys.executable]
    result = {"checker": PYRIGHT_VERSION, "node": version, "python_version": args.python_version,
              "installed": _installed(command, output, env, args.python_version)}
    if args.full:
        assert args.oracle_package is not None, "Full mode needs the existing frozen cyTimes oracle package directory"
        result["full"] = _full(command, output, env, args.oracle_package.resolve(), args.python_version)
    (output / "typing.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
