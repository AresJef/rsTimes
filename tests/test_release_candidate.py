"""Negative checks for the exact-source, exact-artifact publication gate."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
try:
    import release_candidate as gate
finally:
    sys.path.pop(0)


def certificate():
    return {"source_commit": "a" * 40, "version": "0.2.0b2", "ci_run_id": 123, "ci_attempt": 1}


def successful_ci():
    run = {"repository": {"full_name": gate.REPOSITORY}, "head_repository": {"full_name": gate.REPOSITORY},
           "path": ".github/workflows/ci.yml", "event": "push", "head_sha": "a" * 40,
           "id": 123, "run_attempt": 1, "status": "completed", "conclusion": "success"}
    names = [f"CPython {row['python']['minor']} / {row['platform']['id']}"
             for row in gate.release_matrix()["include"]]
    names += ["Select approved native matrix", "Rust quality",
              "Independent sdist / macos-arm64 / 3.13", "Independent sdist / linux-musl-arm64 / 3.15",
              "Verify complete32-wheel and sdist bundle",
              "Frozen-upstream comparisons / 3.12.10 / NumPy 2.5.3",
              "Frozen-upstream comparisons / 3.13.17 / NumPy 2.5.3"]
    return run, {"total_count": len(names), "jobs": [
        {"name": "verify / " + name, "status": "completed", "conclusion": "success"} for name in names]}


@pytest.mark.parametrize("change", [None, "failed-run", "wrong-source", "fork", "wrong-workflow",
                                          "wrong-attempt", "failed-job", "missing-job"])
def test_ci_gate_requires_same_successful_complete_attempt(change):
    run, jobs = successful_ci()
    if change == "failed-run":
        run["conclusion"] = "failure"
    elif change == "wrong-source":
        run["head_sha"] = "b" * 40
    elif change == "fork":
        run["head_repository"]["full_name"] = "someone/rsTimes"
    elif change == "wrong-workflow":
        run["path"] = ".github/workflows/publish.yml"
    elif change == "wrong-attempt":
        run["run_attempt"] = 2
    elif change == "failed-job":
        jobs["jobs"][4]["conclusion"] = "failure"
    elif change == "missing-job":
        jobs["jobs"].pop()
        jobs["total_count"] -= 1
    if change is None:
        gate.validate_ci(run, jobs, certificate())
    else:
        with pytest.raises((AssertionError, ValueError)):
            gate.validate_ci(run, jobs, certificate())


@pytest.mark.parametrize("change", [None, "wrong-manifest", "wrong-source", "missing-wheel", "wrong-abi"])
def test_payload_gate_rejects_mixed_source_or_missing_files(tmp_path, change):
    dist = tmp_path / "dist"
    dist.mkdir()
    rows = []
    for position in gate.release_matrix()["include"]:
        py = "cp" + position["python"]["minor"].replace(".", "")
        platform = position["platform"]
        tag = platform.get("wheel_platform", "macosx_11_0" + platform.get("wheel_suffix", ""))
        name = f"rstimes-0.2.0b2-{py}-{py}-{tag}.whl"
        content = name.encode()
        (dist / name).write_bytes(content)
        rows.append({"filename": name, "tags": [f"{py}-{py}-{tag}"],
                     "sha256": hashlib.sha256(content).hexdigest()})
    sdist = {"filename": "rstimes-0.2.0b2.tar.gz", "sha256": hashlib.sha256(b"sdist").hexdigest()}
    (dist / sdist["filename"]).write_bytes(b"sdist")
    manifest = {"version": "0.2.0b2", "source_commit": "a" * 40, "wheels": rows, "sdists": [sdist]}
    if change == "wrong-source":
        manifest["source_commit"] = "b" * 40
    elif change == "missing-wheel":
        (dist / rows[0]["filename"]).unlink()
    elif change == "wrong-abi":
        rows[0]["tags"] = ["cp312-cp312t-win_amd64"]
    original = tmp_path / "release-manifest.json"
    original.write_text(json.dumps(manifest))
    cert = certificate()
    cert["manifest_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text("".join(
        row["sha256"] + "  dist/" + row["filename"] + "\n" for row in rows + [sdist]))
    if change == "wrong-manifest":
        original.write_text(original.read_text() + " ")
    if change is None:
        assert gate.verify_bundle(tmp_path, cert) == manifest
    else:
        with pytest.raises(AssertionError):
            gate.verify_bundle(tmp_path, cert)


def test_occupied_pypi_version_must_contain_only_identical_files():
    manifest = {"wheels": [{"filename": "wheel.whl", "sha256": "a" * 64}], "sdists": []}
    gate.verify_existing_pypi({"urls": [{"filename": "wheel.whl", "digests": {"sha256": "a" * 64}}]}, manifest)
    for name, sha in (("wheel.whl", "b" * 64), ("other.whl", "a" * 64)):
        with pytest.raises(AssertionError):
            gate.verify_existing_pypi({"urls": [{"filename": name, "digests": {"sha256": sha}}]}, manifest)


@pytest.mark.parametrize("change", [None, "speed", "precision", "stability", "samples", "identity", "receipt"])
def test_performance_completion_is_same_final_wheel_and_original_gates(change):
    wheel = {"filename": "rstimes-0.2.0b2-cp313-cp313-macosx_11_0_arm64.whl",
             "sha256": "a" * 64, "native_sha256": "b" * 64}
    receipt = {"source_commit": "a" * 40, "version": "0.2.0b2", "baseline": "0.2.0b1",
               "wheel_sha256": "a" * 64, "native_sha256": "b" * 64,
               "case_manifest_sha256": "c" * 64, "raw_evidence_sha256": "d" * 64,
               "items": [{"id": "case", "group": "pd3", "status": "PASS", "pairs": 216, "workers": 36,
                          "precision_pct": 2.9, "stability_pct": 4.9, "max_increase_pct": 4.9}]}
    if change in ("speed", "precision", "stability"):
        receipt["items"][0][{"speed": "max_increase_pct", "precision": "precision_pct", "stability": "stability_pct"}[change]] = 5.1
    elif change == "samples":
        receipt["items"][0]["pairs"] = 215
    elif change == "identity":
        receipt["native_sha256"] = "e" * 64
    cert = {"performance_sha256": gate.digest_json(receipt)}
    if change == "receipt":
        receipt["items"][0]["precision_pct"] = 2.8
    manifest = {"source_commit": "a" * 40, "version": "0.2.0b2", "wheels": [wheel]}
    if change is None:
        gate.validate_performance(receipt, cert, manifest)
    else:
        with pytest.raises(AssertionError):
            gate.validate_performance(receipt, cert, manifest)
