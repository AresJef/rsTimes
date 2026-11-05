"""Qualify pinned, unmodified official Polars sources for internal t-lane CI.

This prepares build inputs and records source/wheel identities. The existing
Maturin Action builds the official default features. No upstream source is
patched, and no Polars wheel is included in rsTimes distribution artifacts.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sysconfig
import tarfile
import urllib.request
import zipfile

from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
GENERATED_FLAGS = Path("py-polars/runtime/polars-runtime-32/_polars_runtime_32/build_feature_flags.py")


def digest(path: Path) -> str:
    """Return the identity of one actual build input or output."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(source: Path) -> dict[str, str]:
    """Hash source inputs, separating the one official build.rs Python output."""
    result = {}
    for directory, children, names in source.walk():
        children[:] = [name for name in children if name not in ("target", "__pycache__")]
        for name in sorted(names):
            path = directory / name
            if path.suffix != ".pyc" and path.relative_to(source) != GENERATED_FLAGS:
                value = digest(path)
                if path.is_symlink():
                    value = "symlink:" + path.readlink().as_posix() + ":sha256:" + value
                result[path.relative_to(source).as_posix()] = value
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
                   "generated_build_output": GENERATED_FLAGS.as_posix(),
                   "default_upstream_features": True, "user_distribution": False,
                   "status": "PREPARED"}
        receipt.write_text(json.dumps(payload, indent=2) + "\n")
    else:
        payload = json.loads(receipt.read_text())
        assert payload["official_source"] == spec
        current = source_files(source)
        before = payload["source_sha256"]
        differences = {"added": sorted(current.keys() - before.keys()),
                       "removed": sorted(before.keys() - current.keys()),
                       "changed": sorted(key for key in before.keys() & current.keys() if before[key] != current[key])}
        payload["source_readback"] = differences
        if any(differences.values()):
            payload["status"] = "SOURCE_CHANGED"
            receipt.write_text(json.dumps(payload, indent=2) + "\n")
            raise AssertionError(f"Upstream source changed during the build: {differences}")
        wheel, = args.wheel_directory.glob("*.whl")
        name, version, _, tags = parse_wheel_filename(wheel.name)
        abi = "cp" + str(sysconfig.get_config_var("py_version_nodot")) + "t"
        assert sysconfig.get_config_var("Py_GIL_DISABLED")
        assert name == "polars-runtime-32" and str(version) == spec["version"]
        assert {tag.abi for tag in tags} == {abi}, tags
        with zipfile.ZipFile(wheel) as archive:
            generated = archive.read("_polars_runtime_32/build_feature_flags.py")
        statement, = ast.parse(generated).body
        assert isinstance(statement, ast.Assign) and len(statement.targets) == 1
        target, = statement.targets
        assert isinstance(target, ast.Name) and target.id == "BUILD_FEATURE_FLAGS"
        assert isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str)
        generated_output = {"path": GENERATED_FLAGS.as_posix(),
                            "sha256": hashlib.sha256(generated).hexdigest(),
                            "build_feature_flags": statement.value.value}
        proof = args.wheel_directory / "build-proof.json"
        internal_wheel = {"filename": wheel.name, "sha256": digest(wheel), "tags": sorted(map(str, tags))}
        cached = proof.is_file()
        if cached:
            original = json.loads(proof.read_text())
            assert original["official_source"] == spec
            assert original["source_sha256"] == payload["source_sha256"]
            assert original["internal_wheel"] == internal_wheel
            assert original["upstream_patches"] == [] and original["default_upstream_features"] is True
            assert original["generated_output"] == generated_output
        else:
            assert (source / GENERATED_FLAGS).read_bytes() == generated, "Generated source/wheel flags differ"
        payload.update(status="SOURCE_UNCHANGED", checked_utc=datetime.now(timezone.utc).isoformat(),
                       internal_wheel=internal_wheel, exact_internal_cache_reused=cached,
                       generated_output=generated_output)
        if not cached:
            proof.write_text(json.dumps(payload, indent=2) + "\n")
        receipt.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"source": str(source), "receipt": str(receipt), "status": payload["status"]}))


if __name__ == "__main__":
    main()
