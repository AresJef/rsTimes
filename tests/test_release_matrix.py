"""Release-gate negatives and dependency policy, independent of candidate speed."""
from email.message import Message
import importlib.util
from pathlib import Path
import sys
import tomllib

from packaging.requirements import Requirement
import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_release_manifest_tests", ROOT / "tools/distribution_manifest.py")
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def wheel_rows():
    """Build tags from the explicitly approved ABI/platform definition."""
    result = []
    for row in manifest.release_matrix()["include"]:
        py = row["python"]["interpreter_tag"]
        abi = row["python"]["abi_tag"]
        platform = row["platform"]
        tag = platform.get("wheel_platform")
        if tag is None:
            tag = "macosx_" + row["macos_deployment_target"].replace(".", "_") + platform["wheel_suffix"]
        result.append({"tags": [f"{py}-{abi}-{tag}"]})
    return result


def test_full_matrix_has_all_32_positions_and_four_new_pilots():
    # The ordinary32 contract remains; Q02 adds16 distinct t ABI positions.
    rows = wheel_rows()
    assert len(rows) == 48
    selected = manifest.release_matrix()["include"]
    assert sum(not row["python"]["free_threaded"] for row in selected) == 32
    assert sum(row["python"]["free_threaded"] for row in selected) == 16
    pilots = manifest.release_matrix("pilot")["include"]
    assert len(pilots) == 8
    assert sum(not row["python"]["free_threaded"] for row in pilots) == 4
    manifest.validate_matrix(rows, complete=True)


@pytest.mark.parametrize("tag", [
    "cp311-cp311-win_amd64", "cp313-cp313-win32",
    "cp313-cp313t-win_amd64", "cp315-cp315-linux_aarch64",
    "cp314-cp314t-macosx_11_0_x86_64",
    "cp313-cp313-manylinux_2_17_x86_64", "cp313-cp313-macosx_11_0_universal2",
])
def test_unsupported_release_tags_are_rejected(tag):
    with pytest.raises(AssertionError):
        manifest.matrix_key(tag)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "old16", "empty"])
def test_incomplete_or_duplicate_bundle_cannot_pass_by_count(kind):
    rows = wheel_rows()
    rows = {"missing": rows[:-1], "duplicate": rows[:-1] + rows[:1],
            "old16": rows[:16], "empty": []}[kind]
    with pytest.raises(AssertionError):
        manifest.validate_matrix(rows, complete=True)
    with pytest.raises(AssertionError):
        manifest.validate_matrix(rows)


def test_free_threaded_wheels_are_distinct_from_same_minor_ordinary_wheels():
    assert manifest.matrix_key("cp314-cp314-win_amd64") == ("cp314", "windows-x86_64")
    assert manifest.matrix_key("cp314-cp314t-win_amd64") == ("cp314t", "windows-x86_64")
    assert manifest.matrix_key("cp315-cp315t-musllinux_1_2_aarch64") == ("cp315t", "linux-musl-arm64")
    ordinary = [row for row in wheel_rows() if "t-" not in row["tags"][0]]
    with pytest.raises(AssertionError):
        manifest.validate_matrix(ordinary, complete=True)


def test_free_threaded_interpreters_keep_actual_abi_and_dependency_floor():
    rows = manifest.release_matrix()["include"]
    for row in rows:
        py = row["python"]
        assert py["linux_python"] == f"/opt/python/{py['interpreter_tag']}-{py['abi_tag']}/bin/python"
        assert py["free_threaded"] is py["label"].endswith("t")
        assert py["linux_interpreter"] == "python" + py["label"]
        if py["free_threaded"] and row["platform"]["id"] == "macos-x86_64":
            assert row["macos_deployment_target"] == "14.0"


def test_dependency_policy_matches_approved_platform_boundaries():
    from rstimes._optional import _minimum_dependency_version

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == [
        "numpy>=2.5.3", "packaging>=22.0", "tzdata>=2026.5; sys_platform == 'win32'",
    ]
    assert project["optional-dependencies"]["dateutil"] == ["python-dateutil>=2.9"]
    assert project["optional-dependencies"]["polars"] == ["polars>=2.0.0"]
    assert len(dependency_warning_matrix(
        manifest.declared_requirements(project), _minimum_dependency_version,
    )) == 48


def test_dependency_policy_rejects_a_unix_intel_only_conflict():
    from rstimes._optional import _minimum_dependency_version

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = manifest.declared_requirements(project)
    conflict = Requirement('pandas>=9.9; extra == "pandas" and platform_machine == "x86_64"')
    unix_intel = {"macos-x86_64", "linux-x86_64", "linux-musl-x86_64"}

    with pytest.raises(AssertionError, match=r">=9\.9"):
        dependency_warning_matrix([*requirements, conflict], _minimum_dependency_version)

    rows = dependency_warning_matrix(requirements, _minimum_dependency_version)
    matches = {(row["platform"], row["abi"]) for row in rows
               if conflict.marker.evaluate(dict(row["environment"], extra="pandas"))}
    abis = ("cp312", "cp313", "cp314", "cp314t", "cp315", "cp315t")
    assert matches == {(platform, abi) for platform in unix_intel for abi in abis}
    assert len(matches) == 18 and len(rows) - len(matches) == 30


def dependency_warning_matrix(requirements, minimum):
    """Compare installer and adapter floors in every approved release position."""
    rows = []
    for row in manifest.release_matrix()["include"]:
        platform = row["platform"]
        environment = manifest.marker_environment(row)
        default_dependencies = {
            rule.name: str(rule.specifier) for rule in requirements
            if rule.marker is None or rule.marker.evaluate(environment)
        }
        assert "pandas" not in default_dependencies and "polars" not in default_dependencies
        assert default_dependencies["packaging"] == ">=22.0"

        position = {"abi": row["python"]["abi_tag"], "platform": platform["id"]}
        floors = {}
        pandas3 = environment["python_version"] == "3.15" or platform["id"] == "windows-arm64"
        python_version = tuple(map(int, environment["python_version"].split(".")))
        for package, expected in (("pandas", "3.0.6" if pandas3 else "2.3.3"), ("polars", "2.0.0")):
            environment["extra"] = package
            chosen = [
                str(rule.specifier) for rule in requirements if rule.name == package
                and (rule.marker is None or rule.marker.evaluate(environment))
            ]
            actual = minimum(package, python_version, environment["sys_platform"], environment["platform_machine"])
            assert chosen == [f">={expected}"] and actual == expected, {
                **position, "dependency": package, "metadata": chosen,
                "runtime": actual, "expected": expected,
            }
            floors[package] = {"metadata": chosen[0], "runtime": actual}
        rows.append({**position, "environment": dict(environment, extra=""), "floors": floors})
    return rows


def test_normalized_markers_are_compared_by_meaning_and_not_text():
    project = {
        "dependencies": ["numpy>=2.5.3"],
        "optional-dependencies": {
            "pandas": ["pandas>=3.0.6; python_version >= '3.15' or sys_platform == 'win32'"],
        },
    }
    metadata = Message()
    metadata["Provides-Extra"] = "pandas"
    metadata["Requires-Dist"] = "numpy>=2.5.3"
    metadata["Requires-Dist"] = (
        "pandas>=3.0.6; (extra == 'pandas' and python_full_version >= '3.15')"
        " or (sys_platform == 'win32' and extra == 'pandas')"
    )
    manifest.validate_requirements(project, metadata)
    del metadata["Requires-Dist"]
    metadata["Requires-Dist"] = "numpy>=2.5.3"
    metadata["Requires-Dist"] = "pandas>=3.0.6"
    with pytest.raises(AssertionError):
        manifest.validate_requirements(project, metadata)


@pytest.mark.parametrize("machine,should_reject", [("aarch64", True), ("arm64", False)])
def test_release_checker_uses_linux_arm64_marker_spelling(machine, should_reject):
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    metadata = Message()
    for extra in project["optional-dependencies"]:
        metadata["Provides-Extra"] = extra
    for rule in manifest.declared_requirements(project):
        metadata["Requires-Dist"] = str(rule)
    manifest.validate_requirements(project, metadata)
    metadata["Requires-Dist"] = (
        'polars>=2.0.0; sys_platform == "linux" and '
        f'platform_machine == "{machine}" and extra == ""'
    )
    if should_reject:
        with pytest.raises(AssertionError):
            manifest.validate_requirements(project, metadata)
    else:
        manifest.validate_requirements(project, metadata)


def test_release_marker_environment_covers_approved_platform_identities():
    expected = {
        "linux-arm64": ("linux", "aarch64"),
        "linux-musl-arm64": ("linux", "aarch64"),
        "linux-x86_64": ("linux", "x86_64"),
        "linux-musl-x86_64": ("linux", "x86_64"),
        "macos-arm64": ("darwin", "arm64"),
        "macos-x86_64": ("darwin", "x86_64"),
        "windows-arm64": ("win32", "ARM64"),
        "windows-x86_64": ("win32", "AMD64"),
    }
    positions = {}
    for row in manifest.release_matrix()["include"]:
        label = row["platform"]["id"], row["python"]["abi_tag"]
        environment = manifest.marker_environment(row)
        assert label not in positions
        positions[label] = environment["sys_platform"], environment["platform_machine"]
    abis = ("cp312", "cp313", "cp314", "cp314t", "cp315", "cp315t")
    assert positions == {(platform, abi): identity for platform, identity in expected.items() for abi in abis}


def test_1_1_1_release_note_limits_the_fsp_no_scan_path():
    notes = (ROOT / "docs/releases/v1.1.1.md").read_text(encoding="utf-8")
    bullet, = (line for line in notes.splitlines() if line.startswith("- `Pddt.fsp`"))
    assert bullet == (
        "- `Pddt.fsp` can return the input without scanning when all three conditions hold: "
        "the instance's type is `Pddt` itself, it has no time zone, "
        "and its storage unit already satisfies the requested precision. "
        "Subclasses and timezone-aware indexes use the existing path at lower precisions. "
        "The separate, existing direct return for any valid `precision >= 9` also applies "
        "to subclasses and timezone-aware indexes."
    )
