"""Check installed public stubs against the retained positive/negative samples."""
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    """Require clean positive samples and a diagnostic at every negative call."""
    root = Path(__file__).resolve().parents[1]
    evidence = root / "evidence"
    evidence.mkdir(exist_ok=True)
    fixtures = (
        ("public_valid.py", set()),
        ("astra_configs_valid.py", set()),
        ("pldt_valid.py", set()),
        ("public_invalid.py", set(range(2, 14)) | {15, 16}),
        ("astra_configs_invalid.py", set(range(9, 29))),
        ("pldt_invalid.py", set(range(3, 17))),
    )
    rows = []
    for filename, expected in fixtures:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-incremental", "--cache-dir",
             str(evidence / "mypy-cache"), str(root / "tests/typing" / filename)],
            text=True, capture_output=True, check=False,
        )
        (evidence / (filename + ".mypy.log")).write_text(result.stdout + result.stderr)
        lines = {int(match[1]) for match in re.finditer(r"(?m)^.*?:(\d+): error:", result.stdout)}
        assert result.returncode == (1 if expected else 0), (filename, result.stdout, result.stderr)
        assert lines == expected, (filename, sorted(lines), sorted(expected), result.stdout)
        rows.append({"file": filename, "returncode": result.returncode, "error_lines": sorted(lines)})
    (evidence / "typing.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
