"""Resolve an annotated rsTimes tag to one already verified CI bundle.

This gate downloads existing files. It never builds, moves a tag or substitutes
another run. The tag also carries the bounded local performance completion
receipt; full raw measurements remain in the project's audit evidence.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

from distribution_manifest import release_matrix, validate_matrix
from github_release import api, gh

REPOSITORY = "AresJef/rsTimes"


def digest_json(value):
    """Use one canonical encoding for the performance receipt in an annotated tag."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def validate_ci(run, jobs, certificate):
    """Require a full successful attempt from this repository and exact source."""
    assert run["repository"]["full_name"] == REPOSITORY
    assert run["head_repository"]["full_name"] == REPOSITORY
    assert run["path"] == ".github/workflows/ci.yml"
    assert run["event"] in ("push", "workflow_dispatch")
    assert run["head_sha"] == certificate["source_commit"]
    assert run["id"] == certificate["ci_run_id"]
    assert run["run_attempt"] == certificate["ci_attempt"]
    assert run["status"] == "completed" and run["conclusion"] == "success"
    assert jobs["total_count"] == len(jobs["jobs"]), "Incomplete job listing"
    expected = {f"CPython {row['python']['minor']} / {row['platform']['id']}"
                for row in release_matrix()["include"]}
    expected.update({"Select approved native matrix", "Rust quality",
                     "Independent sdist / macos-arm64 / 3.13",
                     "Independent sdist / linux-musl-arm64 / 3.15",
                     "Verify complete32-wheel and sdist bundle"})
    pythons = {row["python"]["minor"]: row["python"]["version"]
               for row in release_matrix()["include"]}
    expected.update(f"Frozen-upstream comparisons / {pythons[minor]} / NumPy 2.5.3"
                    for minor in ("3.12", "3.13"))
    for name in expected:
        matching = [job for job in jobs["jobs"]
                    if job["name"] == name or job["name"].endswith(" / " + name)]
        job, = matching
        assert job["status"] == "completed" and job["conclusion"] == "success", name
    assert all(job["conclusion"] == "success" for job in jobs["jobs"])


def validate_performance(receipt, certificate, manifest):
    """Bind the local strict protection result to the actual CI macOS wheel."""
    assert digest_json(receipt) == certificate["performance_sha256"]
    assert receipt["source_commit"] == manifest["source_commit"]
    assert receipt["version"] == manifest["version"] and receipt["baseline"] == "0.2.0b1"
    wheel, = [row for row in manifest["wheels"]
              if row["filename"].endswith("cp313-cp313-macosx_11_0_arm64.whl")]
    assert receipt["wheel_sha256"] == wheel["sha256"]
    assert receipt["native_sha256"] == wheel["native_sha256"]
    assert len(receipt["case_manifest_sha256"]) == len(receipt["raw_evidence_sha256"]) == 64
    rows = receipt["items"]
    assert rows and len({(row["group"], row["id"]) for row in rows}) == len(rows)
    for row in rows:
        assert row["status"] == "PASS", row
        assert row["pairs"] == 216 and row["workers"] == 36, row
        for field, limit in (("precision_pct", 3), ("stability_pct", 5), ("max_increase_pct", 5)):
            assert math.isfinite(row[field]) and row[field] <= limit, (field, row)


def verify_bundle(bundle, certificate):
    """Reject a changed manifest, payload, source or incomplete matrix."""
    manifest_path = bundle / "release-manifest.json"
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == certificate["manifest_sha256"]
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source_commit"] == certificate["source_commit"]
    assert manifest["version"] == certificate["version"]
    validate_matrix(manifest["wheels"], complete=True)
    assert len(manifest["sdists"]) == 1
    rows = manifest["wheels"] + manifest["sdists"]
    assert {path.name for path in (bundle / "dist").iterdir()} == {row["filename"] for row in rows}
    for row in rows:
        assert hashlib.sha256((bundle / "dist" / row["filename"]).read_bytes()).hexdigest() == row["sha256"]
    expected_sums = "".join(row["sha256"] + "  dist/" + row["filename"] + "\n" for row in rows)
    assert (bundle / "SHA256SUMS").read_text() == expected_sums
    return manifest


def verify_existing_pypi(current, manifest):
    """A resumed upload may fill gaps, but cannot replace any existing version file."""
    expected = {row["filename"]: row["sha256"] for row in manifest["wheels"] + manifest["sdists"]}
    for row in current["urls"]:
        assert row["filename"] in expected and row["digests"]["sha256"] == expected[row["filename"]]


def main():
    """Download and validate the exact previous run authorized by this tag."""
    assert os.environ["GITHUB_REPOSITORY"] == REPOSITORY
    assert os.environ["GITHUB_REF_TYPE"] == "tag"
    tag = os.environ["GITHUB_REF_NAME"]
    ref = api(f"repos/{REPOSITORY}/git/ref/tags/{tag}")["object"]
    assert ref["type"] == "tag", "Release requires an annotated tag"
    annotated = api(f"repos/{REPOSITORY}/git/tags/{ref['sha']}")
    certificate = json.loads(annotated["message"])
    assert certificate["schema"] == "rstimes-verified-release-v1"
    assert annotated["object"]["type"] == "commit"
    assert annotated["object"]["sha"] == certificate["source_commit"]
    assert certificate["source_commit"] == subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert tag == "v" + certificate["version"]
    run_id, attempt = certificate["ci_run_id"], certificate["ci_attempt"]
    assert type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0
    run = api(f"repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}")
    jobs = api(f"repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    validate_ci(run, jobs, certificate)
    bundle = Path("bundle")
    assert not bundle.exists(), "Keep earlier download evidence separate"
    gh("run", "download", str(run_id), "--repo", REPOSITORY,
       "--name", f"release-distributions-{run_id}-{attempt}", "--dir", str(bundle))
    manifest = verify_bundle(bundle, certificate)
    subprocess.run(["python3", "tools/distribution_manifest.py", "--directory", "bundle/dist",
                    "--wheels", "32", "--sdists", "1", "--complete", "--output",
                    "evidence/source-rechecked-manifest.json"], check=True)
    validate_performance(certificate["performance"], certificate, manifest)
    (bundle / "performance-receipt.json").write_text(json.dumps(certificate["performance"], indent=2) + "\n")
    Path("evidence/release-authorization.json").write_text(json.dumps(certificate, indent=2) + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("matrix=" + json.dumps(release_matrix(), separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
