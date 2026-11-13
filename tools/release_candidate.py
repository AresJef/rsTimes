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
    assert run["head_branch"] == "main", "Release qualification must use the frozen main commit"
    assert run["head_sha"] == certificate["source_commit"]
    assert run["id"] == certificate["ci_run_id"]
    assert run["run_attempt"] == certificate["ci_attempt"]
    assert run["status"] == "completed" and run["conclusion"] == "success"
    assert jobs["total_count"] == len(jobs["jobs"]), "Incomplete job listing"
    expected = {f"CPython {row['python']['label']} / {row['platform']['id']}"
                for row in release_matrix()["include"]}
    expected.update({"Select approved native matrix", "Rust quality",
                     "Independent sdist / macos-arm64 / 3.13",
                     "Independent sdist / macos-arm64 / 3.14t",
                     "Independent sdist / linux-musl-arm64 / 3.15",
                     "Verify complete48-wheel and sdist bundle"})
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
    """Require the complete frozen contract on every actual measured CI ABI.

    A signed-off receipt summarizes independently recomputed raw measurements;
    it is not a replacement for that retained raw evidence. Historical tags
    use the verifier frozen at their own source commit.
    """
    assert digest_json(receipt) == certificate["performance_sha256"]
    contract = json.loads((Path(__file__).resolve().parents[1] /
                           ".github/release-performance-contract.json").read_text())
    assert contract["schema"] == "rstimes-release-performance-contract-v1"
    assert contract["limits_pct"] == {"precision_pct": 3, "stability_pct": 5, "max_increase_pct": 5}
    assert contract["pairs_per_case"] == 216 and contract["workers_per_case"] == 36
    assert contract["rounds"] == 2
    assert receipt.get("schema") == "rstimes-performance-completion-v2"
    assert receipt["source_commit"] == manifest["source_commit"]
    assert receipt["version"] == manifest["version"] == contract["version"]
    assert receipt["baseline"] == contract["baseline"]
    assert receipt["baseline_artifacts"] == contract["baseline_artifacts"]
    assert receipt["contract_sha256"] == digest_json(contract)
    assert receipt["raw_recomputation_passed"] is True
    assert receipt["rounds"] == contract["rounds"]
    for name in ("case_manifest_sha256", "raw_evidence_sha256", "raw_audit_sha256"):
        value = receipt[name]
        assert isinstance(value, str) and len(value) == 64
        assert set(value) <= set("0123456789abcdef"), name
    actual = {}
    for wheel in manifest["wheels"]:
        matching = [tag.split("-")[1] for tag in wheel["tags"]
                    if tag.split("-")[2].startswith("macosx_") and tag.endswith("_arm64")]
        if matching:
            abi, = matching
            assert abi not in actual, abi
            actual[abi] = {"filename": wheel["filename"], "wheel_sha256": wheel["sha256"],
                           "native_sha256": wheel["native_sha256"]}
    assert set(actual) == set(contract["baseline_artifacts"])
    assert receipt["artifacts"] == actual
    rows = receipt["items"]
    expected = {(row["group"], row["id"]): row["abi"] for row in contract["required_cases"]}
    assert expected and len(expected) == len(contract["required_cases"])
    assert len(rows) == len(expected)
    assert {(row["group"], row["id"]): row["abi"] for row in rows} == expected
    assert receipt["selected_pairs"] == len(expected) * contract["pairs_per_case"]
    for row in rows:
        assert row["status"] == "PASS", row
        assert row["pairs"] == 216 and row["workers"] == 36, row
        for field, limit in contract["limits_pct"].items():
            value = row[field]
            assert type(value) in (int, float) and math.isfinite(value) and value <= limit, (field, row)
            if field != "max_increase_pct":
                assert value >= 0, (field, row)


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
    reference = api(f"repos/{REPOSITORY}/git/ref/tags/{tag}")
    assert reference is not None  # Only explicit missing_ok calls can returnNone.
    ref = reference["object"]
    assert ref["type"] == "tag", "Release requires an annotated tag"
    annotated = api(f"repos/{REPOSITORY}/git/tags/{ref['sha']}")
    assert annotated is not None
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
                    "--wheels", str(len(release_matrix()["include"])), "--sdists", "1", "--complete", "--output",
                    "evidence/source-rechecked-manifest.json"], check=True)
    validate_performance(certificate["performance"], certificate, manifest)
    (bundle / "performance-receipt.json").write_text(json.dumps(certificate["performance"], indent=2) + "\n")
    Path("evidence/release-authorization.json").write_text(json.dumps(certificate, indent=2) + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("matrix=" + json.dumps(release_matrix(), separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
