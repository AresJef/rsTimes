"""Download the exact published rsTimes wheel, check SHA, then reuse wheel tests."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import sysconfig
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from distribution_manifest import matrix_key, release_matrix
finally:
    sys.path.pop(0)


def select_position(platform_id: str, python_minor: str, free_threaded: bool):
    """Select one approved physical ABI, never a same-minor ordinary substitute."""
    positions = [row for row in release_matrix()["include"]
                 if row["platform"]["id"] == platform_id
                 and row["python"]["minor"] == python_minor
                 and row["python"]["free_threaded"] is free_threaded]
    if len(positions) != 1:
        raise ValueError(f"Unsupported public verification position: {platform_id}/{python_minor}, free_threaded={free_threaded}")
    return positions[0]


def main():
    """Verify one native position against the original CI manifest, without build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-id", required=True)
    parser.add_argument("--python-minor", required=True)
    parser.add_argument("--free-threaded", action="store_true")
    parser.add_argument("--internal-polars", type=Path,
                        help="Qualified official runtime for internal t integration only; never uploaded.")
    args = parser.parse_args()
    position = select_position(args.platform_id, args.python_minor, args.free_threaded)
    assert f"{sys.version_info.major}.{sys.version_info.minor}" == args.python_minor
    assert bool(sysconfig.get_config_var("Py_GIL_DISABLED")) is args.free_threaded
    assert (args.internal_polars is not None) is args.free_threaded
    if args.internal_polars is not None:
        assert args.internal_polars.is_dir()
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
    assert {matrix_key(tag) for tag in expected["tags"]} == {(position["python"]["abi_tag"], args.platform_id)}
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert digest == expected["sha256"], wheel.name
    evidence = Path("evidence")
    evidence.mkdir(exist_ok=True)
    (evidence / "pypi-download.json").write_text(json.dumps({"filename": wheel.name, "sha256": digest,
        "native_sha256": expected["native_sha256"], "version": manifest["version"],
        "abi_tag": position["python"]["abi_tag"], "free_threaded": args.free_threaded,
        "internal_dependency_role": "development-validation-only" if args.free_threaded else None}, indent=2) + "\n")
    subprocess.run([sys.executable, "-I", "-B", "tools/verify_wheel.py", "--directory", str(directory),
                    "--platform-id", args.platform_id, "--python-minor", args.python_minor,
                    "--mode", "public", *(["--free-threaded", "--internal-polars", str(args.internal_polars)]
                                         if args.free_threaded else [])], check=True)


if __name__ == "__main__":
    main()
