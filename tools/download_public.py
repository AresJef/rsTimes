"""Download the exact published rsTimes wheel, check SHA, then reuse wheel tests."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    """Verify one native position against the original CI manifest, without build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-id", required=True)
    parser.add_argument("--python-minor", required=True)
    args = parser.parse_args()
    manifest = json.loads(Path("bundle/release-manifest.json").read_text())
    assert manifest["source_commit"] == subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    directory = Path("pypi-wheel")
    assert not directory.exists()
    command = [sys.executable, "-m", "pip", "download", "--index-url", "https://pypi.org/simple",
               "--no-cache-dir", "--only-binary=:all:", "--no-deps", "--dest", str(directory),
               "rsTimes==" + manifest["version"]]
    for attempt in range(5):
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            break
        if attempt == 4:
            raise SystemExit(result.returncode)
        time.sleep(15)
    wheel, = directory.glob("*.whl")
    expected, = [row for row in manifest["wheels"] if row["filename"] == wheel.name]
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert digest == expected["sha256"], wheel.name
    evidence = Path("evidence")
    evidence.mkdir(exist_ok=True)
    (evidence / "pypi-download.json").write_text(json.dumps({"filename": wheel.name, "sha256": digest,
        "native_sha256": expected["native_sha256"], "version": manifest["version"]}, indent=2) + "\n")
    subprocess.run([sys.executable, "-I", "-B", "tools/verify_wheel.py", "--directory", str(directory),
                    "--platform-id", args.platform_id, "--python-minor", args.python_minor,
                    "--mode", "public"], check=True)


if __name__ == "__main__":
    main()
