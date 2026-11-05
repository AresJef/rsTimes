"""Protect complete current-baseline coverage and actual public ABI selection."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

from test_release_candidate import complete_performance_receipt, gate

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
try:
    import download_public
finally:
    sys.path.pop(0)


@pytest.mark.parametrize("change", ["missing-case", "duplicate-case", "wrong-abi", "missing-abi",
                                  "wrong-baseline", "wrong-baseline-native", "wrong-contract",
                                  "wrong-wheel", "inc", "raw-not-audited", "wrong-total-pairs",
                                  "missing-round", "negative-precision", "nonfinite-stability"])
def test_release_gate_rejects_incomplete_or_mixed_six_abi_evidence(change):
    receipt, cert, manifest = complete_performance_receipt()
    if change == "missing-case":
        receipt["items"].pop()
    elif change == "duplicate-case":
        receipt["items"][-1] = deepcopy(receipt["items"][0])
    elif change == "wrong-abi":
        receipt["items"][0]["abi"] = "cp314t"
    elif change == "missing-abi":
        receipt["artifacts"].pop("cp315t")
    elif change == "wrong-baseline":
        receipt["baseline"] = "0.2.0b1"
    elif change == "wrong-baseline-native":
        receipt["baseline_artifacts"]["cp313"]["native_sha256"] = "f" * 64
    elif change == "wrong-contract":
        receipt["contract_sha256"] = "f" * 64
    elif change == "wrong-wheel":
        receipt["artifacts"]["cp314"]["wheel_sha256"] = "f" * 64
    elif change == "inc":
        receipt["items"][0]["status"] = "INCONCLUSIVE"
    elif change == "raw-not-audited":
        receipt["raw_recomputation_passed"] = False
    elif change == "wrong-total-pairs":
        receipt["selected_pairs"] -= 1
    elif change == "missing-round":
        receipt["rounds"] = 1
    elif change == "negative-precision":
        receipt["items"][0]["precision_pct"] = -0.1
    else:
        receipt["items"][0]["stability_pct"] = float("inf")
    if change == "nonfinite-stability":
        with pytest.raises(ValueError):
            gate.digest_json(receipt)
        return
    cert["performance_sha256"] = gate.digest_json(receipt)
    with pytest.raises((AssertionError, ValueError)):
        gate.validate_performance(receipt, cert, manifest)


def test_release_gate_rejects_old_single_case_receipt_even_when_that_case_passed():
    wheel = {"filename": "rstimes-0.2.0b3-cp313-cp313-macosx_11_0_arm64.whl",
             "sha256": "a" * 64, "native_sha256": "b" * 64}
    receipt = {"source_commit": "a" * 40, "version": "0.2.0b3", "baseline": "0.2.0b1",
               "wheel_sha256": "a" * 64, "native_sha256": "b" * 64,
               "case_manifest_sha256": "c" * 64, "raw_evidence_sha256": "d" * 64,
               "items": [{"id": "only-one", "group": "pd3", "status": "PASS", "pairs": 216,
                          "workers": 36, "precision_pct": 1, "stability_pct": 1, "max_increase_pct": 1}]}
    certificate = {"performance_sha256": gate.digest_json(receipt)}
    manifest = {"source_commit": "a" * 40, "version": "0.2.0b3", "wheels": [wheel]}
    with pytest.raises(AssertionError):
        gate.validate_performance(receipt, certificate, manifest)


@pytest.mark.parametrize("platform,minor,free,abi", [
    ("macos-arm64", "3.14", False, "cp314"),
    ("macos-arm64", "3.14", True, "cp314t"),
    ("windows-arm64", "3.15", True, "cp315t"),
    ("linux-musl-arm64", "3.15", True, "cp315t"),
])
def test_public_position_distinguishes_actual_t_and_ordinary_abi(platform, minor, free, abi):
    position = download_public.select_position(platform, minor, free)
    assert position["python"]["abi_tag"] == abi
    assert position["platform"]["id"] == platform


@pytest.mark.parametrize("minor,free", [("3.13", True), ("3.11", False)])
def test_public_position_rejects_unsupported_interpreters(minor, free):
    with pytest.raises(ValueError):
        download_public.select_position("macos-arm64", minor, free)


def test_public_verifier_cli_starts_in_isolated_mode_from_another_directory(tmp_path):
    script = Path(download_public.__file__).resolve()
    result = subprocess.run([sys.executable, "-I", "-B", str(script), "--help"],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "--free-threaded" in result.stdout and "--internal-polars" in result.stdout


@pytest.mark.parametrize("free", [False, True])
def test_public_download_propagates_abi_and_internal_dependency_to_real_verifier_cli(tmp_path, monkeypatch, free):
    minor = "3.14"
    abi = "cp314t" if free else "cp314"
    filename = f"rstimes-0.2.0b3-cp314-{abi}-macosx_11_0_arm64.whl"
    content = b"the exact selected public file"
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "release-manifest.json").write_text(json.dumps({"version": "0.2.0b3",
        "source_commit": "a" * 40, "wheels": [{"filename": filename,
        "tags": [f"cp314-{abi}-macosx_11_0_arm64"],
        "sha256": hashlib.sha256(content).hexdigest(), "native_sha256": "b" * 64}]}))
    runtime = tmp_path / "qualified-internal-runtime"
    if free:
        runtime.mkdir()
    arguments = ["download_public.py", "--platform-id", "macos-arm64", "--python-minor", minor]
    if free:
        arguments.extend(["--free-threaded", "--internal-polars", str(runtime)])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.setattr(download_public, "sys", SimpleNamespace(argv=arguments, executable=sys.executable,
        version_info=SimpleNamespace(major=3, minor=14)))
    monkeypatch.setattr(download_public.sysconfig, "get_config_var", lambda key: free if key == "Py_GIL_DISABLED" else None)
    monkeypatch.setattr(download_public.subprocess, "check_output", lambda *args, **kwargs: "a" * 40)
    calls = []

    def external(command, **kwargs):
        calls.append(command)
        if "download" in command:
            target = Path(command[command.index("--dest") + 1])
            target.mkdir()
            (target / filename).write_bytes(content)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(download_public.subprocess, "run", external)
    download_public.main()
    verification = calls[-1]
    assert verification[verification.index("--mode") + 1] == "public"
    assert ("--free-threaded" in verification) is free
    assert ("--internal-polars" in verification) is free
    if free:
        assert verification[verification.index("--internal-polars") + 1] == str(runtime)
    assert json.loads((tmp_path / "evidence/pypi-download.json").read_text())["abi_tag"] == abi
