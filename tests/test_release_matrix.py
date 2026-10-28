"""Release-gate negatives and dependency policy, independent of candidate speed."""
from email.message import Message
import importlib.util
from pathlib import Path
import sys
import tomllib

from packaging.markers import default_environment
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
        py = "cp" + row["python"]["minor"].replace(".", "")
        platform = row["platform"]
        tag = platform.get("wheel_platform")
        if tag is None:
            tag = "macosx_11_0" + platform["wheel_suffix"]
        result.append({"tags": [f"{py}-{py}-{tag}"]})
    return result


def test_full_matrix_has_all_32_positions_and_four_new_pilots():
    rows = wheel_rows()
    assert len(rows) == 32
    assert len(manifest.release_matrix("pilot")["include"]) == 4
    manifest.validate_matrix(rows, complete=True)


@pytest.mark.parametrize("tag", [
    "cp311-cp311-win_amd64", "cp313-cp313-win32",
    "cp314-cp314t-win_amd64", "cp315-cp315-linux_aarch64",
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


def test_dependency_policy_matches_approved_platform_boundaries():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == [
        "numpy>=2.5.3", "tzdata>=2026.5; sys_platform == 'win32'",
    ]
    assert project["optional-dependencies"]["dateutil"] == ["python-dateutil>=2.9"]
    assert project["optional-dependencies"]["polars"] == ["polars>=2.0.0"]
    rules = [Requirement(value) for value in project["optional-dependencies"]["pandas"]]
    for row in manifest.release_matrix()["include"]:
        platform = row["platform"]
        system = platform["id"].split("-", 1)[0]
        environment = default_environment()
        environment.update(
            python_version=row["python"]["minor"],
            python_full_version=row["python"]["version"],
            sys_platform={"windows": "win32", "macos": "darwin", "linux": "linux"}[system],
            platform_machine="ARM64" if system == "windows" and platform["arch"] == "arm64"
                             else "arm64" if platform["arch"] == "arm64" else "x86_64",
        )
        chosen = [str(rule.specifier) for rule in rules if rule.marker.evaluate(environment)]
        pandas3 = row["python"]["minor"] == "3.15" or platform["id"] == "windows-arm64"
        assert chosen == [">=3.0.6" if pandas3 else ">=2.3.3"], row


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
