"""Reuse the frozen direct Cython–Rust sampler for the current rc04 artifact.

This adapter selects fixed installed artifacts and a separate evidence directory.
It keeps the original public workloads, timers, balanced groups and statistics.
Neither project is built, installed or modified by this script.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
SAMPLER = ROOT / "tools/delta_cross_compare.py"
OUT = ROOT / "tasks/evidence/delta-cross-rc04-20261013"
RUST_SHA = "e4d919cb654d1c554b6ee20b22bc4429537b93dd4049bc45a3a504f36c56273d"


def digest(path):
    """Identify measurement source without modifying it."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    """Run one original comparison phase with explicit current-artifact binding."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("identity", "prepare", "refine", "collect"))
    parser.add_argument("--phase", choices=("main", "independent"))
    parser.add_argument("--cycle", type=int)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("rc04_cross_sampler", SAMPLER)
    sampler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sampler)
    sampler.OUT = OUT
    sampler.EXPECTED = {**sampler.EXPECTED, "R": ("rstimes._native", RUST_SHA)}
    targets, identity = sampler.load_targets()
    cy_dist = next(d for d in importlib.metadata.distributions(path=[str(sampler.CY_SITE)])
                   if d.metadata["Name"].replace("_", "-").lower() == "cytimes-rewrite")
    identity["versions"] = {"R": importlib.metadata.version("rstimes"), "C": cy_dist.version}
    assert identity["versions"] == {"R": "0.1.0+delta.4", "C": "0.2.0"}
    sources = {str(path): digest(path) for path in (
        Path(__file__), SAMPLER, ROOT / "tests/delta/cases.py",
        sampler.CY_ROOT / "benchmarks/round2_scenarios.py",
        sampler.CY_ROOT / "benchmarks/scenarios.py")}
    if args.mode == "identity":
        pairs, metadata, excluded = sampler.workloads(targets)
        sampler.save("identity.json", identity)
        sampler.save("workloads.json", {"selected": {k: metadata[k] for k in pairs},
                                        "excluded": excluded, "sources": sources})
        print(json.dumps({"versions": identity["versions"], "common_scenes": len(pairs),
                          "excluded": len(excluded)}, ensure_ascii=False))
    elif args.mode == "prepare":
        sampler.prepare(targets, identity)
        config = json.loads((OUT / "config.json").read_text())
        config["input_sha256"] = sources
        sampler.save("config.json", config)
    else:
        config = json.loads((OUT / "config.json").read_text())
        assert config["input_sha256"] == sources, "Measurement source changed after freeze"
        expected = config["identity"]
        for name in ("python", "machine", "platform", "dependencies", "versions"):
            assert identity[name] == expected[name], "Environment changed: " + name
        for role in ("R", "C"):
            assert identity[role] == expected[role], "Native target changed: " + role
        if args.mode == "refine":
            sampler.refine_controls(targets)
            config = json.loads((OUT / "config.json").read_text())
            config["input_sha256"] = sources
            sampler.save("config.json", config)
        else:
            sampler.collect(targets, identity, args.phase, args.cycle)


if __name__ == "__main__":
    main()
