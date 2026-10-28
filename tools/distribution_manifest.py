"""Verify rsTimes release contents and record the exact tested distributions.

This project-specific check reads archives without executing them. The release
jobs consume its SHA256 manifest and the same wheel/sdist files, without rebuild.
"""
import argparse
from email.parser import BytesParser
import hashlib
import itertools
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tomllib
import zipfile

from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.requirements import Requirement
from packaging.markers import Marker, default_environment
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
LICENSES = ("LICENSE", "NOTICE", "NOTICE-RUST-STDLIB.html", "NOTICE-CPYTHON.txt",
            "NOTICE-UNICODE.txt", "NOTICE-IANA-TIME-ZONE.txt")
PLATFORM_IDS = {
    "macos-arm64", "macos-x86_64", "windows-x86_64", "windows-arm64",
    "linux-x86_64", "linux-musl-x86_64", "linux-arm64", "linux-musl-arm64",
}


def release_matrix(profile="full"):
    """Read the single approved32-position definition, or four new pilot positions."""
    config = json.loads((ROOT / ".github/native-matrix.json").read_text())
    assert [row["minor"] for row in config["pythons"]] == ["3.12", "3.13", "3.14", "3.15"]
    assert len(config["platforms"]) == 8
    assert {row["id"] for row in config["platforms"]} == PLATFORM_IDS
    assert profile in ("full", "pilot"), profile
    return {"include": [
        {"python": py, "platform": platform}
        for py, platform in itertools.product(config["pythons"], config["platforms"])
        if profile == "full" or (py["minor"] == "3.13" and platform["new"])
    ]}


def declared_requirements(project):
    """Add extra markers without corrupting dependencies with existing conditions."""
    requirements = [Requirement(item) for item in project["dependencies"]]
    for extra, values in project.get("optional-dependencies", {}).items():
        for value in values:
            requirement = Requirement(value)
            marker = f'extra == "{extra}"'
            if requirement.marker is not None:
                marker = f"({requirement.marker}) and {marker}"
            requirement.marker = Marker(marker)
            requirements.append(requirement)
    return requirements


def validate_requirements(project, metadata):
    """Compare actual dependency meaning across every supported install environment.

    Maturin normalizes Boolean markers into disjunctive normal form and may use
    python_full_version. Text equality would reject equivalent wheel metadata.
    Dependency identities and every approved platform/Python/extra truth table
    must agree; an omitted or unexpectedly unconditional dependency fails.
    """
    expected = declared_requirements(project)
    actual = [Requirement(item) for item in metadata.get_all("Requires-Dist", [])]

    def key(item):
        return canonicalize_name(item.name), frozenset(item.extras), str(item.specifier), item.url

    assert {key(item) for item in actual} == {key(item) for item in expected}
    extras = set(project.get("optional-dependencies", {}))
    assert set(metadata.get_all("Provides-Extra", [])) == extras
    for row, extra in itertools.product(release_matrix()["include"], ["", *sorted(extras), "unknown"]):
        position = row["platform"]
        system = position["id"].split("-", 1)[0]
        environment = default_environment()
        environment.update(
            python_version=row["python"]["minor"],
            python_full_version=row["python"]["version"],
            sys_platform={"macos": "darwin", "windows": "win32", "linux": "linux"}[system],
            platform_system={"macos": "Darwin", "windows": "Windows", "linux": "Linux"}[system],
            platform_machine=("ARM64" if system == "windows" else "arm64") if position["arch"] == "arm64"
                             else ("AMD64" if system == "windows" else "x86_64"),
            extra=extra,
        )
        selected = lambda values: {key(item) for item in values
                                   if item.marker is None or item.marker.evaluate(environment)}
        assert selected(actual) == selected(expected), (row, extra, actual, expected)


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
        assert not any(part.startswith(".wheel-test") for part in parts), name
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
        validate_requirements(project, metadata)
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
    platforms = [row["platform"] for row in release_matrix()["include"]
                 if row["python"]["minor"] == "3.13"]
    for row in platforms:
        if row.get("wheel_platform") == platform:
            return interpreter, row["id"]
        if row.get("wheel_prefix") and platform.startswith(row["wheel_prefix"]) and platform.endswith(row["wheel_suffix"]):
            return interpreter, row["id"]
    raise AssertionError("Unsupported wheel tag: " + tag)


def validate_matrix(wheel_rows, complete=False):
    """Reject unsupported/duplicate wheels and any incomplete release collection."""
    actual = []
    for wheel in wheel_rows:
        keys = {matrix_key(tag) for tag in wheel["tags"]}
        key, = keys
        actual.append(key)
    assert len(actual) == len(set(actual)), "Duplicate native matrix position"
    if complete or len(actual) != 1:
        expected = {("cp" + row["python"]["minor"].replace(".", ""), row["platform"]["id"])
                    for row in release_matrix()["include"]}
        assert len(actual) == 32 and set(actual) == expected, (actual, expected)


def main():
    """Validate a job's files, the complete32-wheel bundle, or emit its CI matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-matrix", choices=("full", "pilot"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--wheels", type=int)
    parser.add_argument("--sdists", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--complete", action="store_true")
    args = parser.parse_args()
    if args.print_matrix:
        print(json.dumps(release_matrix(args.print_matrix), separators=(",", ":")))
        return
    if any(value is None for value in (args.directory, args.wheels, args.sdists, args.output)):
        parser.error("--directory, --wheels, --sdists and --output are required for archive verification")
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
    validate_matrix(wheel_rows, args.complete)
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
