"""Publish only the exact rsTimes bundle that passed the release workflow.

An interrupted upload can add missing original files. Existing release files,
notes and tags are verified and never overwritten or moved.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def gh(*args):
    """Run the authenticated GitHub CLI without exposing its credentials."""
    return subprocess.check_output(["gh", *args], text=True)


def api(path, missing_ok=False):
    """Read GitHub JSON; only a real404 may mean an absent release."""
    result = subprocess.run(["gh", "api", path], text=True, capture_output=True, check=False)
    if result.returncode:
        if missing_ok and "HTTP 404" in result.stderr:
            return None
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def verify_remote_files(repository, tag, expected, names):
    """Download existing uploaded assets and compare their actual SHA256 bytes."""
    if not names:
        return
    with tempfile.TemporaryDirectory() as temporary:
        gh("release", "download", tag, "--repo", repository, "--dir", temporary)
        actual = {path.name for path in Path(temporary).iterdir()}
        assert actual == names, (actual, names)
        for name in names:
            assert hashlib.sha256((Path(temporary) / name).read_bytes()).hexdigest() == expected[name], name


def main():
    """Create or finish the approved tag release, preserving the tested bundle."""
    assert os.environ["GITHUB_REF_TYPE"] == "tag"
    repository = os.environ["GITHUB_REPOSITORY"]
    assert repository == "AresJef/rsTimes"
    bundle = Path("bundle")
    manifest = json.loads((bundle / "release-manifest.json").read_text())
    assert len(manifest["wheels"]) == 16 and len(manifest["sdists"]) == 1
    assert manifest["source_commit"] == os.environ["GITHUB_SHA"]
    version = manifest["version"]
    tag = "v" + version
    assert os.environ["GITHUB_REF_NAME"] == tag
    notes_file = Path("docs/releases") / (tag + ".md")
    notes = notes_file.read_text()
    files = {row["filename"]: bundle / "dist" / row["filename"]
             for row in manifest["wheels"] + manifest["sdists"]}
    expected = {row["filename"]: row["sha256"] for row in manifest["wheels"] + manifest["sdists"]}
    for name, path in files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[name], name
    for name in ("release-manifest.json", "SHA256SUMS"):
        files[name] = bundle / name
        expected[name] = hashlib.sha256(files[name].read_bytes()).hexdigest()
    ref = api(f"repos/{repository}/git/ref/tags/{tag}")["object"]
    if ref["type"] == "tag":
        ref = api(f"repos/{repository}/git/tags/{ref['sha']}")["object"]
    assert ref["type"] == "commit" and ref["sha"] == manifest["source_commit"]
    endpoint = f"repos/{repository}/releases/tags/{tag}"
    release = api(endpoint, missing_ok=True)
    if release is None:
        arguments = ["release", "create", tag, "--repo", repository, "--verify-tag",
                     "--target", manifest["source_commit"], "--title", "rsTimes " + version,
                     "--notes-file", str(notes_file)]
        if manifest["is_prerelease"]:
            arguments.append("--prerelease")
        gh(*arguments, *(str(path) for path in files.values()))
    else:
        assert not release["draft"] and release["body"].strip() == notes.strip()
        assert release["prerelease"] == manifest["is_prerelease"]
        present = {asset["name"] for asset in release["assets"]}
        assert present <= files.keys(), present
        verify_remote_files(repository, tag, expected, present)
        missing = files.keys() - present
        if missing:
            gh("release", "upload", tag, "--repo", repository, *(str(files[name]) for name in sorted(missing)))
    release = api(endpoint)
    present = {asset["name"] for asset in release["assets"]}
    assert present == files.keys(), present
    verify_remote_files(repository, tag, expected, present)
    receipt = {"url": release["html_url"], "tag": tag, "source_commit": manifest["source_commit"],
               "files_sha256": expected}
    evidence = Path("evidence")
    evidence.mkdir(exist_ok=True)
    (evidence / "github-release.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
