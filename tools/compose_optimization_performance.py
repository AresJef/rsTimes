"""Audit and combine only the optimization contract's declared scene replacements.

Each scene remains one complete actual process cohort. This never mixes groups
or blocks, selects by speed, changes weights, or discards valid slow observations.
"""
import argparse
import importlib.util
import json
import itertools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("optimization", ROOT / "benchmarks/delta/optimization.py")
optimization = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimization)


def compose(original_path, replacement_path, source_path, output_path, revision=False, cumulative_seconds=1200, suite="legacy"):
    """Replace the complete frozen unstable set and recompute every formal gate.

    Requires unchanged artifacts, workloads, measurement code and quality rules.
    Consumed original time/attempts are inherited; every scene is fully audited.
    """
    original = json.loads(Path(original_path).read_text())
    replacement = json.loads(Path(replacement_path).read_text())
    scope = replacement["formal_scope"]
    if revision:
        optimization.REVISION, optimization.SUITE = True, suite
        mapping = json.loads((ROOT / "benchmarks/delta/revision-cases.json").read_text())
        manifest = json.loads((ROOT / "benchmarks/delta/cases.json").read_text())
        if suite == "legacy":
            optimization.FULL_IDS = {x for ids in manifest["groups"].values() for x in ids} - set(mapping["legacy_excluded"])
        else:
            optimization.ROLES, optimization.LABELS = ("old", "new"), ("current",)
            optimization.ORDERS = tuple(itertools.permutations(optimization.ROLES))
            optimization.FULL_IDS = {x for group in mapping["formal_suites"][suite] for x in mapping["groups"][group]}
            optimization.PRECISION_CASES = tuple(x for group in mapping["formal_suites"][suite] for x in mapping["groups"][group])
    optimization.validate_local_formal(original, replacement["identity"], source_path, scope, replacement.get("alignment_source"))
    original_pids = set(original["actual_pids"].values()) if original["actual_pids"] else {
        pid for item in original["case_sources"].values() for pid in item["actual_pids"].values()}
    if original_pids & set(replacement["actual_pids"].values()):
        raise ValueError("Local replacement must use fresh actual worker processes")
    if (replacement.get("cumulative_limit_seconds", 1200) != cumulative_seconds
            or not original["elapsed_seconds"] <= replacement["elapsed_seconds"] <= cumulative_seconds):
        raise ValueError("Original main-cycle collection time was not inherited")
    manifest = json.loads((ROOT / "benchmarks/delta/" / ("revision-cases.json" if revision and suite != "legacy" else "cases.json")).read_text())
    cases = [{"id": identifier, "group": group} for group, ids in manifest["groups"].items() for identifier in ids]
    if revision:
        cases = [case for case in cases if case["id"] in optimization.FULL_IDS]
    if {case["id"]: case["group"] for case in cases} != {row["id"]: row["group"] for row in original["rows"]}:
        raise ValueError("Original scenes or scale-specific groups differ from the frozen manifest")
    states, sources, rows = {}, {}, []
    for case in cases:
        identifier = case["id"]
        changed = identifier in scope
        receipt = replacement if changed else original
        state = receipt["states"][identifier]
        if len(state["accepted"]) != 1440 or not 1440 <= state["attempts"] <= 4320:
            raise ValueError("A scene is missing complete work or exceeded its original attempt cap")
        if changed and state["attempts"] < original["states"][identifier]["attempts"] + 1440:
            raise ValueError("Original scene attempts were reset")
        pids = receipt["actual_pids"] or receipt["case_sources"][identifier]["actual_pids"]
        for group in state["accepted"]:
            reasons = optimization.validate_group(group, pids)
            if reasons or reasons != group["reasons"] or not group["valid"]:
                raise ValueError("An accepted raw group failed audit")
        states[identifier] = state
        sources[identifier] = {"path": str(Path(replacement_path if changed else original_path).resolve()),
                               "actual_pids": pids, "replaced": changed,
                               "earlier_source": original.get("case_sources", {}).get(identifier) if not changed else None}
        rows.append(optimization.summarize_case(case, state, 12, 120))
    result = {"identity": replacement["identity"], "mode": "formal", "actual_pids": None,
              "states": states, "rows": rows, "case_sources": sources,
              "elapsed_seconds": replacement["elapsed_seconds"], "precision": True,
              "source_compatibility": {"archive": str(Path(source_path).resolve()),
                                       "measurement_signature": optimization.measurement_source_signature(source_path)},
              "evaluation": optimization.evaluate(rows, cases, True, True),
              "excluded_slow_valid_groups": 0}
    with Path(output_path).open("x") as output:
        json.dump(result, output, separators=(",", ":"))
        output.write("\n")
    return result["evaluation"]


def main():
    """Audit explicit original/replacement receipts without overwriting evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True)
    parser.add_argument("--replacement", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--revision", action="store_true", help="Use the frozen97-scene third-round legacy contract")
    parser.add_argument("--suite", choices=("legacy", "bulk", "float", "conversion"), default="legacy")
    parser.add_argument("--cumulative-seconds", type=int, default=1200)
    args = parser.parse_args()
    print(json.dumps(compose(args.original, args.replacement, args.source, args.output, args.revision, args.cumulative_seconds, args.suite)))


if __name__ == "__main__":
    main()
