"""Execute the actual MyST doctest blocks, retaining page and package identities.

Each page runs in a fresh interpreter. Expected values are authored in the page;
the runner never records current output as a new expected answer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import doctest
import hashlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"^```\{doctest\}(?:[ \t]+([^\n]*))?\n(.*?)^```[ \t]*$", re.M | re.S)


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def identity() -> dict:
    import rstimes

    package = Path(rstimes.__file__).resolve().parent
    return {
        "version": importlib.metadata.version("rstimes"),
        "python": sys.version,
        "package_path": str(package),
        "native": {p.name: sha(p.read_bytes()) for p in package.iterdir() if p.suffix in ('.so', '.pyd')},
        "stubs": {p.name: sha(p.read_bytes()) for p in package.glob("*.pyi")},
        "payload": {p.relative_to(package).as_posix(): sha(p.read_bytes()) for p in package.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'},
        "dependencies": {d: importlib.metadata.version(d) for d in ("numpy", "pandas", "polars", "pyarrow", "python-dateutil") if importlib.util.find_spec({"python-dateutil": "dateutil"}.get(d, d))},
        "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
    }


def run_page(page: Path, profile: str) -> dict:
    content = page.read_bytes()
    text = content.decode()
    namespace = {"__name__": "__rstimes_documentation_example__"}
    output = io.StringIO()
    runner = doctest.DocTestRunner(verbose=True, optionflags=0)
    groups = []
    for index, match in enumerate(BLOCK.finditer(text), 1):
        name = (match[1] or f"example-{index}").strip()
        source = match[2]
        # No skips, global ellipsis, or regenerated expectations.
        if re.search(r"doctest:.*\b(?:SKIP|ELLIPSIS)\b", source):
            raise ValueError(f"{page}: skipped or loose examples are not accepted")
        test = doctest.DocTestParser().get_doctest(source, namespace, name, str(page), text[:match.start()].count("\n"))
        runner.run(test, out=output.write, clear_globs=False)
        namespace.update(test.globs)
        groups.append({"id": name, "sha256": sha(source.encode()), "assertions": len(test.examples)})
    if re.search(r"^```(?:python|py|\{testcode\})\b", text, re.M):
        raise ValueError(f"{page}: Python examples must use executable doctest directives")
    return {
        "page": page.relative_to(ROOT).as_posix(),
        "page_sha256": sha(content), "profile": profile,
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "verifier_sha256": sha(Path(__file__).read_bytes()),
        "groups": groups, "attempted": runner.tries, "failures": runner.failures,
        "status": "pass" if runner.failures == 0 else "fail",
        "identity": identity(), "transcript": output.getvalue(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs="*", type=Path)
    parser.add_argument("--profile", default="full")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--single", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    pages = [p if p.is_absolute() else ROOT / p for p in args.pages] or sorted(p for p in ROOT.rglob("*.md") if not any(x.startswith("_") for x in p.relative_to(ROOT).parts))
    if args.single:
        assert len(pages) == 1
        result = run_page(pages[0], args.profile)
        dest = args.evidence_dir / (pages[0].relative_to(ROOT).as_posix().replace("/", "--") + ".json")
        dest.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: result[k] for k in ("page", "status", "attempted", "failures", "page_sha256")}))
        if result["failures"]:
            for failure in re.findall(r"\*{20,}\n.*?(?=\nTrying:|\Z)", result["transcript"], re.S):
                print(failure)
        return int(result["failures"] > 0)
    failed = 0
    for page in pages:
        command = [sys.executable, "-I", str(Path(__file__).resolve()), str(page), "--profile", args.profile, "--evidence-dir", str(args.evidence_dir.resolve()), "--single"]
        result = subprocess.run(command, check=False, timeout=90)
        failed += int(result.returncode != 0)
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
