"""Check the exact-source, exact-artifact publication gate."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
from textwrap import dedent
from urllib.error import HTTPError
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
try:
    from github_release import verify_release_metadata
    import release_candidate as gate
finally:
    sys.path.pop(0)


CONTRACT = json.loads((ROOT / ".github/release-performance-contract.json").read_text())
VERSION = CONTRACT["version"]


def certificate():
    return {"source_commit": "a" * 40, "version": VERSION, "ci_run_id": 123, "ci_attempt": 1}


def successful_ci():
    run = {"repository": {"full_name": gate.REPOSITORY}, "head_repository": {"full_name": gate.REPOSITORY},
           "path": ".github/workflows/ci.yml", "event": "push", "head_branch": "main", "head_sha": "a" * 40,
           "id": 123, "run_attempt": 1, "status": "completed", "conclusion": "success"}
    names = [f"CPython {row['python']['label']} / {row['platform']['id']}"
             for row in gate.release_matrix()["include"]]
    names += ["Select approved native matrix", "Rust quality",
              "Independent sdist / macos-arm64 / 3.13", "Independent sdist / linux-musl-arm64 / 3.15",
              "Independent sdist / macos-arm64 / 3.14t",
              "Verify complete48-wheel and sdist bundle",
              "Frozen-upstream comparisons / 3.12.10 / NumPy 2.5.3",
              "Frozen-upstream comparisons / 3.13.17 / NumPy 2.5.3"]
    return run, {"total_count": len(names), "jobs": [
        {"name": "verify / " + name, "status": "completed", "conclusion": "success"} for name in names]}


@pytest.mark.parametrize("change", [None, "failed-run", "wrong-source", "wrong-branch", "fork", "wrong-workflow",
                                          "wrong-attempt", "failed-job", "missing-job"])
def test_ci_gate_requires_same_successful_complete_attempt(change):
    run, jobs = successful_ci()
    if change == "failed-run":
        run["conclusion"] = "failure"
    elif change == "wrong-source":
        run["head_sha"] = "b" * 40
    elif change == "wrong-branch":
        run["head_branch"] = "unmerged-research"
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


@pytest.mark.parametrize("minor", ["3.14t", "3.15t"])
def test_ci_gate_does_not_substitute_an_ordinary_job_for_a_t_job(minor):
    run, jobs = successful_ci()
    name = f"verify / CPython {minor} / windows-x86_64"
    jobs["jobs"] = [job for job in jobs["jobs"] if job["name"] != name]
    jobs["total_count"] -= 1
    with pytest.raises((AssertionError, ValueError)):
        gate.validate_ci(run, jobs, certificate())


@pytest.mark.parametrize("change", [
    None, "wrong-manifest", "wrong-source", "missing-wheel", "wrong-abi",
    "wrong-version", "marked-prerelease", "missing-stability",
])
def test_payload_gate_rejects_mixed_source_or_missing_files(tmp_path, change):
    dist = tmp_path / "dist"
    dist.mkdir()
    rows = []
    for position in gate.release_matrix()["include"]:
        py = position["python"]["interpreter_tag"]
        abi = position["python"]["abi_tag"]
        platform = position["platform"]
        macos = "macosx_" + position["macos_deployment_target"].replace(".", "_")
        tag = platform.get("wheel_platform", macos + platform.get("wheel_suffix", ""))
        name = f"rstimes-{VERSION}-{py}-{abi}-{tag}.whl"
        content = name.encode()
        (dist / name).write_bytes(content)
        rows.append({"filename": name, "tags": [f"{py}-{abi}-{tag}"],
                     "sha256": hashlib.sha256(content).hexdigest()})
    sdist = {"filename": f"rstimes-{VERSION}.tar.gz", "sha256": hashlib.sha256(b"sdist").hexdigest()}
    (dist / sdist["filename"]).write_bytes(b"sdist")
    manifest = {"version": VERSION, "is_prerelease": False, "source_commit": "a" * 40,
                "wheels": rows, "sdists": [sdist]}
    if change == "wrong-source":
        manifest["source_commit"] = "b" * 40
    elif change == "missing-wheel":
        (dist / rows[0]["filename"]).unlink()
    elif change == "wrong-abi":
        rows[0]["tags"] = ["cp312-cp312t-win_amd64"]
    elif change == "wrong-version":
        manifest["version"] = "0.2.0b3"
    elif change == "marked-prerelease":
        manifest["is_prerelease"] = True
    elif change == "missing-stability":
        del manifest["is_prerelease"]
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


def test_occupied_pypi_version_must_contain_only_identical_files(tmp_path, monkeypatch):
    workflow = ROOT / ".github/workflows/publish.yml"
    step = "      - name: Verify downloaded and any existing PyPI files\n"
    source = workflow.read_text()
    assert source.count(step) == 1, "Find the verification step in the actual workflow"
    shell = source.split(step, 1)[1].split("\n      - ", 1)[0] + "\n"
    start = "          python3 - <<'PYCODE'\n"
    finish = "          PYCODE\n"
    assert shell.count(start) == shell.count(finish) == 1
    assert shell.index("sha256sum --check SHA256SUMS") < shell.index(start)
    body = dedent(shell.split(start, 1)[1].split(finish, 1)[0])
    program = compile(body, str(workflow), "exec")

    manifest = {"version": VERSION,
                "wheels": [{"filename": "wheel.whl", "sha256": "a" * 64}],
                "sdists": [{"filename": "sdist.tar.gz", "sha256": "b" * 64}]}
    monkeypatch.chdir(tmp_path)
    (tmp_path / "release-manifest.json").write_text(json.dumps(manifest))
    url = "https://pypi.org/pypi/rsTimes/" + VERSION + "/json"

    def verify(files=(), status=None):
        def respond(request):
            assert request == url
            if status:
                raise HTTPError(request, status, "offline test", None, None)
            content = {"urls": [{"filename": name, "digests": {"sha256": sha}}
                                for name, sha in files]}
            return io.BytesIO(json.dumps(content).encode())

        monkeypatch.setattr(urllib.request, "urlopen", respond)
        exec(program, {})

    verify((("wheel.whl", "a" * 64), ("sdist.tar.gz", "b" * 64)))
    verify((("wheel.whl", "a" * 64),))
    verify(status=404)
    for name, sha in (("wheel.whl", "b" * 64), ("other.whl", "a" * 64)):
        with pytest.raises(AssertionError, match=name):
            verify(((name, sha),))
    with pytest.raises(HTTPError) as observed:
        verify(status=500)
    assert observed.value.code == 500


def complete_performance_receipt():
    """Independent complete fixture for the explicitly frozen release contract."""
    contract = deepcopy(CONTRACT)
    wheels = [{"filename": f"rstimes-{VERSION}-{abi.rstrip('t')}-{abi}-macosx_11_0_arm64.whl",
               "tags": [f"{abi.rstrip('t')}-{abi}-macosx_11_0_arm64"],
               "sha256": hashlib.sha256((abi + "wheel").encode()).hexdigest(),
               "native_sha256": hashlib.sha256((abi + "native").encode()).hexdigest()}
              for abi in contract["baseline_artifacts"]]
    artifacts = {row["tags"][0].split("-")[1]: {
        "filename": row["filename"], "wheel_sha256": row["sha256"],
        "native_sha256": row["native_sha256"]} for row in wheels}
    receipt = {"schema": "rstimes-performance-completion-v2", "source_commit": "a" * 40,
               "version": VERSION, "baseline": contract["baseline"],
               "contract_sha256": gate.digest_json(contract),
               "baseline_artifacts": contract["baseline_artifacts"], "artifacts": artifacts,
               "case_manifest_sha256": "c" * 64, "raw_evidence_sha256": "d" * 64,
               "raw_audit_sha256": "e" * 64, "raw_recomputation_passed": True,
               "selected_pairs": len(contract["required_cases"]) * 216, "rounds": 2,
               "items": [{"id": row["id"], "group": row["group"], "abi": row["abi"],
                          "status": "PASS", "pairs": 216, "workers": 36,
                          "precision_pct": 2.9, "stability_pct": 4.9, "max_increase_pct": 4.9}
                         for row in contract["required_cases"]]}
    cert = {"performance_sha256": gate.digest_json(receipt)}
    manifest = {"source_commit": "a" * 40, "version": VERSION, "wheels": wheels}
    return receipt, cert, manifest


@pytest.mark.parametrize("change", [
    None, "speed", "precision", "stability", "samples", "identity", "receipt",
    "missing-workday", "inconclusive", "old-version",
])
def test_performance_completion_is_same_final_wheel_and_original_gates(change):
    receipt, cert, manifest = complete_performance_receipt()
    if change in ("speed", "precision", "stability"):
        receipt["items"][0][{"speed": "max_increase_pct", "precision": "precision_pct", "stability": "stability_pct"}[change]] = 5.1
    elif change == "samples":
        receipt["items"][0]["pairs"] = 215
    elif change == "identity":
        receipt["artifacts"]["cp313"]["native_sha256"] = "f" * 64
    elif change == "missing-workday":
        missing = next(row for row in receipt["items"] if row["group"].startswith("workday-forward-"))
        receipt["items"].remove(missing)
        receipt["selected_pairs"] -= 216
    elif change == "inconclusive":
        receipt["items"][0]["status"] = "INCONCLUSIVE"
    elif change == "old-version":
        receipt["version"] = "0.2.0b3"
    cert = {"performance_sha256": gate.digest_json(receipt)}
    if change == "receipt":
        receipt["items"][0]["precision_pct"] = 2.8
    if change is None:
        gate.validate_performance(receipt, cert, manifest)
    else:
        with pytest.raises(AssertionError):
            gate.validate_performance(receipt, cert, manifest)


@pytest.mark.parametrize("change", [None, "draft", "prerelease", "body", "tag_name", "name"])
def test_github_stable_release_metadata_matches_committed_notes(change):
    tag = "v" + VERSION
    notes = "# Release notes\n\nCalendar changes.\n"
    release = {"tag_name": tag, "name": "rsTimes " + VERSION, "body": notes,
               "draft": False, "prerelease": False}
    if change is None:
        verify_release_metadata(release, tag, VERSION, False, notes)
    else:
        release[change] = True if change in {"draft", "prerelease"} else "different"
        with pytest.raises(AssertionError):
            verify_release_metadata(release, tag, VERSION, False, notes)
