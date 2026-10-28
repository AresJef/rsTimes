"""Verify rsTimes release contents and record the exact tested distributions.

This project-specific check reads archives without executing them. The release
jobs consume its SHA256 manifest and the same wheel/sdist files, without rebuild.
"""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tomllib
import zipfile

from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
LICENSES = ("LICENSE", "NOTICE", "NOTICE-RUST-STDLIB.html", "NOTICE-CPYTHON.txt",
            "NOTICE-UNICODE.txt", "NOTICE-IANA-TIME-ZONE.txt")


def production_files():
    """Return all source, resource, metadata and license inputs required to rebuild."""
    files = {ROOT / name for name in (*LICENSES, "Cargo.toml", "Cargo.lock", "build.rs",
                                      "rust-toolchain.toml", "pyproject.toml", "README.md")}
    files.update((ROOT / "rust").rglob("*.rs"))
    files.update(path for path in (ROOT / "src/rstimes").iterdir()
                 if path.is_file() and path.suffix not in (".so", ".pyd", ".pyc"))
    return sorted(files)


def archive_paths(names):
    """Reject unsafe paths and directories forbidden in a public distribution."""
    forbidden = {".git", ".local", ".venv", "target", "__pycache__", "experimental", "experiental"}
    for name in names:
        parts = PurePosixPath(name).parts
        assert not name.startswith("/") and ".." not in parts, name
        assert not forbidden.intersection(parts), name
        assert not any(part == ".env" or part.startswith(".env.") for part in parts), name


def check_wheel(path, expected_version):
    """Check native tags, installed Python payload, metadata and license bytes."""
    name, version, _, tags = parse_wheel_filename(path.name)
    assert name == "rstimes" and version == expected_version, path.name
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        archive_paths(names)
        metadata_path, = [name for name in names if name.endswith(".dist-info/METADATA")]
        metadata_bytes = archive.read(metadata_path)
        metadata = BytesParser().parsebytes(metadata_bytes)
        assert canonicalize_name(metadata["Name"]) == "rstimes"
        assert Version(metadata["Version"]) == expected_version
        assert metadata["Requires-Python"] == ">=3.12"
        description = metadata_bytes.replace(b"\r\n", b"\n").split(b"\n\n", 1)[1].decode("utf-8")
        assert description.strip() == (ROOT / "README.md").read_text(encoding='utf-8').strip()
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding='utf-8'))["project"]
        expected_requirements = {str(Requirement(item)) for item in project["dependencies"]}
        for extra, requirements in project.get("optional-dependencies", {}).items():
            expected_requirements.update(str(Requirement(item + '; extra == "' + extra + '"'))
                                         for item in requirements)
        assert {str(Requirement(item)) for item in metadata.get_all("Requires-Dist", [])} == expected_requirements
        for source in (ROOT / "src/rstimes").iterdir():
            if source.is_file() and source.suffix not in (".so", ".pyd", ".pyc"):
                assert archive.read("rstimes/" + source.name) == source.read_bytes(), source.name
        for filename in LICENSES:
            member, = [name for name in names if name.endswith("/licenses/" + filename)]
            assert archive.read(member) == (ROOT / filename).read_bytes(), filename
        native, = [name for name in names if name.startswith("rstimes/_native")
                   and name.endswith((".so", ".pyd"))]
        native_sha = hashlib.sha256(archive.read(native)).hexdigest()
    return {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size, "tags": sorted(map(str, tags)),
            "native": native, "native_sha256": native_sha}


def check_sdist(path, sources):
    """Require every production input to match the fixed source tree exactly."""
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
        archive_paths(names)
        roots = {PurePosixPath(name).parts[0] for name in names}
        prefix, = roots
        for source in sources:
            name = prefix + "/" + source.relative_to(ROOT).as_posix()
            stream = archive.extractfile(name)
            assert stream is not None and stream.read() == source.read_bytes(), name
    return {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size, "production_inputs_checked": len(sources)}


def matrix_key(tag):
    """Reduce a supported native wheel tag to its single approved matrix position."""
    interpreter, abi, platform = tag.split("-", 2)
    assert interpreter in {"cp312", "cp313", "cp314", "cp315"} and abi == interpreter, tag
    if platform.startswith("macosx_"):
        assert platform.endswith(("_arm64", "_x86_64")), tag
        system = "macos-arm64" if platform.endswith("_arm64") else "macos-x86_64"
    elif platform == "win_amd64":
        system = "windows-x86_64"
    else:
        assert platform == "manylinux_2_28_x86_64", tag
        system = "linux-x86_64"
    return interpreter, system


def main():
    """Validate one job's artifacts or the complete16-wheel release bundle."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--wheels", type=int, required=True)
    parser.add_argument("--sdists", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding='utf-8'))["project"]
    version = Version(project["version"])
    cargo = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding='utf-8'))["package"]
    assert version.local is None and Version(cargo["version"]) == version
    wheels = sorted(args.directory.glob("*.whl"))
    sdists = sorted(args.directory.glob("*.tar.gz"))
    assert len(wheels) == args.wheels and len(sdists) == args.sdists, (wheels, sdists)
    assert set(args.directory.iterdir()) == set(wheels + sdists), "Unexpected file in upload directory"
    sources = production_files()
    wheel_rows = [check_wheel(path, version) for path in wheels]
    if args.wheels == 16:
        actual = []
        for wheel in wheel_rows:
            keys = {matrix_key(tag) for tag in wheel["tags"]}
            key, = keys
            actual.append(key)
        expected = {(py, system) for py in ("cp312", "cp313", "cp314", "cp315")
                    for system in ("macos-arm64", "macos-x86_64", "windows-x86_64", "linux-x86_64")}
        assert len(set(actual)) == 16 and set(actual) == expected, actual
    result = {"version": str(version), "cargo_version": cargo["version"],
              "is_prerelease": version.is_prerelease,
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "rust_toolchain": tomllib.loads((ROOT / "rust-toolchain.toml").read_text(encoding='utf-8'))["toolchain"],
              "sources_sha256": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sources},
              "wheels": wheel_rows, "sdists": [check_sdist(path, sources) for path in sdists]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    checksums = "".join(row["sha256"] + "  dist/" + row["filename"] + "\n"
                        for row in result["wheels"] + result["sdists"])
    args.output.with_name("SHA256SUMS").write_text(checksums)
    print(json.dumps({"version": str(version), "wheels": len(wheels), "sdists": len(sdists),
                      "production_inputs": len(sources), "manifest": str(args.output)}))


if __name__ == "__main__":
    main()
