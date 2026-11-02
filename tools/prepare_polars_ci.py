"""Qualify pinned, unmodified official Polars sources for internal t-lane CI.

This prepares build inputs and records source/wheel identities. The existing
Maturin Action builds the official default features. No upstream source is
patched, and no Polars wheel is included in rsTimes distribution artifacts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sysconfig
import tarfile
import urllib.request

from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    """Return the identity of one actual build input or output."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(source: Path) -> dict[str, str]:
    """Hash upstream files, excluding generated Cargo and Python cache trees."""
    result = {}
    for directory, children, names in source.walk():
        children[:] = [name for name in children if name not in ("target", "__pycache__")]
        for name in sorted(names):
            path = directory / name
            if path.suffix != ".pyc":
                result[path.relative_to(source).as_posix()] = digest(path)
    return result


def main() -> None:
    """Prepare once or prove the same official source remained unchanged."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--wheel-directory", type=Path, default=ROOT / ".local/internal-polars-wheels")
    args = parser.parse_args()
    spec = json.loads((ROOT / ".github/polars-upstream.json").read_text())
    work = ROOT / ".local/ci-polars-source"
    source = work / ("polars-" + spec["commit"])
    receipt = ROOT / "evidence/polars-internal-source.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    if args.command == "prepare":
        assert not source.exists() and not receipt.exists(), "Preserve prior evidence; use a fresh CI checkout"
        work.mkdir(parents=True, exist_ok=True)
        archive = work / (spec["commit"] + ".tar.gz")
        urllib.request.urlretrieve(spec["source_url"], archive)
        assert digest(archive) == spec["source_sha256"], "Official source archive identity mismatch"
        with tarfile.open(archive) as tar:
            roots = {Path(name).parts[0] for name in tar.getnames()}
            assert roots == {source.name}, roots
            tar.extractall(work, filter="data")
        toolchain = (source / "rust-toolchain.toml").read_text()
        assert spec["rust_toolchain"] in toolchain, toolchain
        payload = {"started_utc": datetime.now(timezone.utc).isoformat(),
                   "official_source": spec, "source_directory": str(source),
                   "source_sha256": source_files(source), "upstream_patches": [],
                   "default_upstream_features": True, "user_distribution": False,
                   "status": "PREPARED"}
        receipt.write_text(json.dumps(payload, indent=2) + "\n")
    else:
        payload = json.loads(receipt.read_text())
        assert payload["official_source"] == spec
        assert source_files(source) == payload["source_sha256"], "Upstream source changed during the build"
        wheel, = args.wheel_directory.glob("*.whl")
        name, version, _, tags = parse_wheel_filename(wheel.name)
        abi = "cp" + str(sysconfig.get_config_var("py_version_nodot")) + "t"
        assert sysconfig.get_config_var("Py_GIL_DISABLED")
        assert name == "polars-runtime-32" and str(version) == spec["version"]
        assert {tag.abi for tag in tags} == {abi}, tags
        payload.update(status="SOURCE_UNCHANGED", checked_utc=datetime.now(timezone.utc).isoformat(),
                       internal_wheel={"filename": wheel.name, "sha256": digest(wheel),
                                       "tags": sorted(map(str, tags))})
        receipt.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"source": str(source), "receipt": str(receipt), "status": payload["status"]}))


if __name__ == "__main__":
    main()
