"""Check source documentation, installed docstrings and executable examples.

Run with the documented wheel environment's Python -I. This is a documentation
check, not a replacement for the existing functionality or performance gates.
"""

import argparse
import ast
from datetime import date, datetime, timezone
import doctest
import hashlib
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROPERTIES = (
    "years", "months", "days", "hours", "minutes", "seconds", "microseconds",
    "year", "month", "day", "weekday", "hour", "minute", "second", "microsecond",
)
DIRECT_METHODS = ("__add__", "__radd__", "__sub__", "__rsub__")
SLOT_METHODS = (
    "__new__", "__init__", "__bool__", "__eq__", "__ne__", "__hash__",
    "__repr__", "__neg__", "__abs__",
)


def preceding_doc(source, position):
    """Read the Rust item docs before position, skipping attached attributes."""
    lines = []
    for line in reversed(source[:position].splitlines()):
        stripped = line.lstrip()
        if stripped.startswith("#["):
            continue
        if not stripped.startswith("///"):
            break
        lines.append(stripped[3:].removeprefix(" "))
    return "\n".join(reversed(lines))


def rust_coverage():
    """Count all production functions with item docs and all module docs.

    Test-only functions and macro-generated callback bodies are excluded.
    Returns per-file counts and the canonical Python-method documentation.
    """
    rows = []
    methods = {}
    pattern = re.compile(
        r'(?m)^ *(?:pub(?:\([^)]*\))? )?(?:unsafe )?'
        r'(?:extern "C" )?(?:const )?fn (?P<name>\w+)(?=[(<])'
    )
    for path in sorted((ROOT / "rust").glob("*.rs")):
        source = path.read_text().split("#[cfg(test)]", 1)[0]
        functions = list(pattern.finditer(source))
        missing = [m["name"] for m in functions if not preceding_doc(source, m.start())]
        assert not missing, (path.name, missing)
        assert source.startswith("//!"), path.name
        rows.append({"file": str(path.relative_to(ROOT)), "functions": len(functions),
                     "documented": len(functions), "module_documented": True})
        if path.name == "delta.rs":
            start = source.index("#[pymethods]")
            methods = {m["name"]: preceding_doc(source, m.start())
                       for m in functions if m.start() > start}
            assert preceding_doc(source, source.index("pub struct Delta"))
    return rows, methods


def stripped_ast(source):
    """Return the executable AST with module, class and function docs removed."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                value = node.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    node.body = node.body[1:]
    return ast.dump(tree, include_attributes=False)


def python_coverage(allow_implementation_changes=False):
    """Check source docs and report executable changes against the Git baseline.

    Nested test cases and unittest test methods are excluded. Stub overloads
    are counted separately because each editor-visible signature has docs.
    """
    paths = sorted((ROOT / "src/rstimes").glob("*.py*"))
    paths += sorted((ROOT / "tools").glob("*.py"))
    paths += sorted((ROOT / "benchmarks/delta").glob("*.py"))
    paths += [ROOT / "tests/delta/cases.py"]
    rows = []
    for path in paths:
        if path.suffix not in (".py", ".pyi"):
            continue
        source = path.read_text()
        tree = ast.parse(source)
        assert ast.get_docstring(tree), str(path)
        items = []
        for item in tree.body:
            if isinstance(item, (ast.FunctionDef, ast.ClassDef)):
                items.append(item)
            if isinstance(item, ast.ClassDef) and item.name != "Validity":
                items.extend(n for n in item.body if isinstance(n, ast.FunctionDef))
        missing = [n.name for n in items if not ast.get_docstring(n)]
        assert not missing, (path.name, missing)
        relative = str(path.relative_to(ROOT))
        old = subprocess.run(["git", "show", "HEAD:" + relative], cwd=ROOT,
                             text=True, capture_output=True, check=False)
        unchanged = None if old.returncode != 0 else stripped_ast(old.stdout) == stripped_ast(source)
        if not allow_implementation_changes:
            assert unchanged is not False, relative
        rows.append({"file": relative, "items": len(items), "documented": len(items),
                     "executable_ast_unchanged": unchanged,
                     "new_validation_tool": old.returncode != 0})
    return rows


def runtime_checks(methods):
    """Verify installed docs and execute every prompt-style API example.

    The package must load from this interpreter's environment. Static C
    descriptor docs must match their Rust source text exactly. CPython slot
    wrapper text is listed explicitly rather than counted as custom docs.
    """
    import rstimes
    import rstimes.delta
    import rstimes.errors
    import rstimes._native as native

    assert Path(rstimes.__file__).is_relative_to(Path(sys.prefix)), rstimes.__file__
    assert native.release_build()
    Delta = rstimes.Delta
    for name in PROPERTIES + DIRECT_METHODS:
        assert getattr(Delta, name).__doc__ == methods[name], name
    detailed = [name for name in methods if name != "new" and name not in SLOT_METHODS]
    for name in detailed:
        assert getattr(Delta, name).__doc__, name
    for name in ("to_unix_ms", "from_unix_ms"):
        assert inspect.getdoc(getattr(rstimes, name)), name
    assert native.runtime_info.__doc__ and native.release_build.__doc__
    documents = {"rstimes": rstimes.__doc__, "rstimes.delta": rstimes.delta.__doc__,
                 "Delta": Delta.__doc__, "to_unix_ms": rstimes.to_unix_ms.__doc__,
                 "from_unix_ms": rstimes.from_unix_ms.__doc__}
    documents.update({"Delta." + name: getattr(Delta, name).__doc__ for name in detailed})
    runner = doctest.DocTestRunner()
    globs = {**vars(rstimes), "date": date, "datetime": datetime,
             "timezone": timezone, "Delta": Delta}
    parser = doctest.DocTestParser()
    for name, doc in documents.items():
        assert doc is not None, f"Missing installed docstring: {name}"
        test = parser.get_doctest(doc, dict(globs), name, rstimes.__file__, 0)
        runner.run(test)
    summary = runner.summarize()
    assert summary.failed == 0
    return {"package": rstimes.__file__, "native": native.__file__,
            "native_sha256": hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
            "detailed_delta_members": len(detailed), "properties": len(PROPERTIES),
            "examples_attempted": summary.attempted, "examples_failed": summary.failed,
            "generic_cpython_slots": {n: getattr(Delta, n).__doc__ for n in SLOT_METHODS}}


def main():
    """Run documentation checks and optionally create a new JSON evidence file.

    Raises FileExistsError if the output path would overwrite previous evidence.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report")
    parser.add_argument("--allow-implementation-changes", action="store_true",
                        help="Check docs for an authorized implementation task; retain actual AST change reporting")
    args = parser.parse_args()
    rust, methods = rust_coverage()
    result = {"status": "passed", "rust": rust, "python": python_coverage(args.allow_implementation_changes),
              "runtime": runtime_checks(methods)}
    if args.report:
        with Path(args.report).open("x") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
