"""Measure the fixed Delta maintenance comparisons through existing isolated workers.

Timing, snapshots, actual Python calls and transport come from bench.py/paired.py.
This controller only selects the approved inputs, balances pairs and saves results.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import statistics
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("correction_bench", ROOT / "benchmarks/delta/bench.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)
MANIFEST = ROOT / "benchmarks/delta/correction-cases.json"


def digest(path):
    """Identify a saved file without changing it."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    """Atomically save one task receipt outside the selected packages."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def workers(args):
    """Start baseline, candidate and an independent equivalent-integer worker."""
    result = {}
    try:
        for role, env in (("old", args.old_env), ("new", args.new_env), ("integer", args.new_env)):
            result[role] = bench.Process(env, "rstimes", "all", variant="correction", qos_policy=args.qos)
            result[role].short_info()
        return result
    except BaseException:
        for worker in result.values():
            worker.close()
        raise


def relations(manifest):
    """Keep protection and fractional-input comparisons separate and predeclared."""
    rows = [{"id": key, "group": group, "left_role": "old", "right_role": "new",
             "left_id": key, "right_id": key, "limit": 1.05}
            for group, keys in manifest["groups"].items() for key in keys]
    rows += [{"id": "fraction:" + floating, "group": "fraction",
              "left_role": "integer", "right_role": "new", "left_id": integer,
              "right_id": floating, "limit": 1.20} for floating, integer in manifest["float_pairs"]]
    return rows


def identity(pool):
    """Bind actual loaded binaries and require common interpreter/dependency conditions."""
    result = {role: worker.metadata for role, worker in pool.items()}
    for name in ("python", "platform", "machine", "dependencies", "measurement_qos"):
        if len({json.dumps(meta["environment"][name], sort_keys=True) for meta in result.values()}) != 1:
            raise ValueError("Worker environments differ: " + name)
    return result


def outputs_match(row, pool):
    """Verify complete output values and types before comparing elapsed time."""
    outputs = []
    for role, identifier in ((row["left_role"], row["left_id"]), (row["right_role"], row["right_id"])):
        observed = next(item for item in pool[role].metadata["observations"] if item["case"] == identifier)
        if "error" in observed:
            raise ValueError("Benchmark input failed: " + identifier)
        outputs.append(observed["result"])
    if outputs[0] != outputs[1]:
        raise ValueError("Comparison outputs differ: " + row["id"])


def pair(row, pool, count, slot, journal, factor=1):
    """Commit all members together; an invalid pair remains in its original order slot."""
    order = "AB" if slot % 2 == 0 else "BA"
    roles = {"A": (row["left_role"], row["left_id"]), "B": (row["right_role"], row["right_id"])}
    members = {}
    started = time.perf_counter_ns()
    for position in order:
        role, identifier = roles[position]
        member = pool[role].short_sample(identifier, count * factor,
                                        warmup_count=count * row.get("warmup_factor", 0))
        batch = member["batches"]["engine"]
        member["valid"] = member["valid"] and batch["elapsed_ns"] >= 5_000_000
        if batch["elapsed_ns"] < 5_000_000:
            member["reasons"].append("maintenance-minimum-batch")
        members[position] = member
    span = time.perf_counter_ns() - started
    accepted = all(member["valid"] for member in members.values()) and span <= 250_000_000 * factor
    record = {"id": row["id"], "order": order, "slot": slot, "count": count * factor,
              "factor": factor, "members": members, "span_ns": span, "valid": accepted}
    if accepted:
        record["ratio"] = members["A"]["batches"]["engine"]["elapsed_ns"] / members["B"]["batches"]["engine"]["elapsed_ns"]
    journal.write(json.dumps(record) + "\n")
    return record


def accepted_pair(row, pool, count, slot, journal, deadline, factor=1):
    """Fill one declared slot within the original deadline, retaining rejected attempts."""
    while time.monotonic() + 1 < deadline:
        record = pair(row, pool, count, slot, journal, factor)
        if record["valid"]:
            return record
        time.sleep(1)
    raise TimeoutError("Collection budget reached while filling " + row["id"])


def prepare(args, selected):
    """Calibrate shared counts and short/long precision without creating formal scores."""
    deadline = time.monotonic() + args.seconds
    pool = workers(args)
    output = {"protocol": "delta-maintenance-paired-v1", "identity": identity(pool),
              "source": {str(path.relative_to(ROOT)): digest(path) for path in
                         (Path(__file__), bench.SELF, bench.SELF.with_name("paired.py"), bench.SHARED, MANIFEST)},
              "relations": [], "target_ms": args.target_ms, "cycles_per_phase": 3,
              "pairs_per_cycle": 48, "blocks_per_cycle": 6, "stability_limit": .05,
              "controls_per_length": args.controls,
              "calibration_margin": {"minimum_multiplier": 1.5, "proposed_multiplier": 1.8},
              "quality": dict(bench.short_protocol().RULES), "formal": False}
    output["qos_policy"] = args.qos
    output["state_policy"] = {"warmup_calls_per_member": f"{args.warmup_factor} times base n, same for both lengths",
                              "gc": "ordinary interpreter policy, common to all workers",
                              "input": "fixed reused input", "results": "created and released normally"}
    started = time.monotonic()
    try:
        with (args.out / "prepare-raw.jsonl").open("w") as journal:
            for index, row in enumerate(selected):
                row = dict(row, warmup_factor=args.warmup_factor)
                outputs_match(row, pool)
                count = 1
                for _ in range(5):
                    elapsed = [pool[role].measure(identifier, count)["elapsed_ns"]
                               for role, identifier in ((row["left_role"], row["left_id"]), (row["right_role"], row["right_id"]))]
                    fastest = min(elapsed)
                    if fastest >= args.target_ms * 1_000_000 * 1.5:
                        break
                    count = max(count + 1, math.ceil(count * args.target_ms * 1_000_000 * 1.8 / max(1, fastest)))
                controls = []
                for slot in range(args.controls):
                    for factor in ((1, 2) if slot % 2 == 0 else (2, 1)):
                        controls.append(accepted_pair(row, pool, count, slot, journal, deadline, factor))
                short = statistics.median(item["ratio"] for item in controls if item["factor"] == 1)
                long = statistics.median(item["ratio"] for item in controls if item["factor"] == 2)
                spread = max(short, long) / min(short, long) - 1
                output["relations"].append({**row, "n": count, "precision_spread": spread,
                                            "precision_ready": spread <= .03,
                                            "median_pair_ns": statistics.median(item["span_ns"] for item in controls if item["factor"] == 1)})
                if (index + 1) % 12 == 0:
                    print(json.dumps({"prepared": index + 1, "total": len(selected)}), flush=True)
        output["elapsed_seconds"] = time.monotonic() - started
        output["estimated_collection_seconds"] = sum(row["median_pair_ns"] for row in output["relations"]) * 288 / 1e9
        output["ready"] = all(row["precision_ready"] for row in output["relations"])
        save(args.out / "config.json", output)
        print(json.dumps({"ready": output["ready"], "seconds": output["elapsed_seconds"],
                          "estimated_collection_seconds": output["estimated_collection_seconds"],
                          "precision_failures": [row["id"] for row in output["relations"] if not row["precision_ready"]]}), flush=True)
    finally:
        for worker in pool.values():
            worker.close()


def collect(args, config):
    """Run two actual independent cohorts using only the frozen configuration."""
    if not config["ready"]:
        raise ValueError("Precision controls did not pass")
    args.qos = config["qos_policy"]
    for name, expected in config["source"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Measurement source changed after freeze: " + name)
    deadline = time.monotonic() + args.seconds
    results = []
    started = time.monotonic()
    for phase in ("main", "independent"):
        for cycle in range(3):
            pool = workers(args)
            current = identity(pool)
            for role in current:
                expected = config["identity"][role]
                if current[role]["environment"] != expected["environment"]:
                    raise ValueError("Loaded artifact or environment changed after freeze: " + role)
                for name in ("inputs_sha256", "observations"):
                    if current[role][name] != expected[name]:
                        raise ValueError("Inputs or complete results changed after freeze: " + role)
                for name in ("native_file", "package_version"):
                    if current[role]["loaded_identity"][name] != expected["loaded_identity"][name]:
                        raise ValueError("Loaded package identity changed: " + name)
            try:
                with (args.out / f"{phase}-{cycle}.jsonl").open("w") as journal:
                    for row in config["relations"]:
                        outputs_match(row, pool)
                        data = [accepted_pair(row, pool, row["n"], slot, journal, deadline) for slot in range(48)]
                        blocks = []
                        for start in range(0, 48, 8):
                            block = data[start:start + 8]
                            left = sum(item["members"]["A"]["batches"]["engine"]["elapsed_ns"] for item in block)
                            right = sum(item["members"]["B"]["batches"]["engine"]["elapsed_ns"] for item in block)
                            blocks.append(left / right)
                        results.append({"id": row["id"], "phase": phase, "cycle": cycle,
                                        "blocks": blocks, "pids": {role: meta["loaded_identity"]["pid"] for role, meta in current.items()}})
                save(args.out / "campaign.json", {"rows": results, "elapsed_seconds": time.monotonic()-started,
                                                   "config_sha256": digest(args.out / "config.json")})
                print(json.dumps({"phase": phase, "cycle": cycle, "rows": len(results)}), flush=True)
            finally:
                for worker in pool.values():
                    worker.close()
    summaries = []
    for row in config["relations"]:
        phases = {}
        for phase in ("main", "independent"):
            blocks = [value for result in results if result["id"] == row["id"] and result["phase"] == phase for value in result["blocks"]]
            mid = statistics.median(blocks)
            phases[phase] = {"median": mid, "conservative": min(blocks),
                             "noise": max(abs(value/mid-1) for value in blocks), "blocks": blocks}
        phase_spread = max(value["median"] for value in phases.values()) / min(value["median"] for value in phases.values()) - 1
        stable = phase_spread <= .05 and all(value["noise"] <= .05 for value in phases.values())
        meets = all(value["median"] >= 1/row["limit"] and value["conservative"] >= 1/row["limit"] for value in phases.values())
        summaries.append({**row, "phases": phases, "phase_spread": phase_spread,
                          "status": "INCONCLUSIVE" if not stable else "PASS" if meets else "FAIL"})
    groups = {}
    for group in {row["group"] for row in summaries}:
        selected = [row for row in summaries if row["group"] == group]
        groups[group] = {phase: {metric: math.exp(statistics.mean(math.log(row["phases"][phase][metric])
                           for row in selected)) for metric in ("median", "conservative")}
                         for phase in ("main", "independent")}
    full_scope = {row["id"] for row in summaries} == {
        row["id"] for row in relations(json.loads(MANIFEST.read_text()))}
    report = {"complete": True, "scope": "full" if full_scope else "limited",
              "full_acceptance": full_scope and all(row["status"] == "PASS" for row in summaries),
              "passed": all(row["status"] == "PASS" for row in summaries), "groups": groups,
              "relations": summaries, "elapsed_seconds": time.monotonic()-started,
              "config_sha256": digest(args.out / "config.json")}
    save(args.out / "performance-summary.json", report)
    print(json.dumps({"passed": report["passed"], "seconds": report["elapsed_seconds"],
                      "failures": [(row["id"], row["status"]) for row in summaries if row["status"] != "PASS"]}), flush=True)


def main():
    """Dispatch scoped controls or a complete fixed maintenance campaign."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "collect"))
    parser.add_argument("--old-env", required=True)
    parser.add_argument("--new-env", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=720)
    parser.add_argument("--target-ms", type=float, default=5)
    parser.add_argument("--controls", type=int, default=12)
    parser.add_argument("--warmup-factor", type=int, choices=(0, 2), default=0)
    parser.add_argument("--qos", choices=("initiated", "interactive"), default="initiated")
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    if args.controls < 4 or args.controls % 2:
        raise ValueError("Controls must be balanced and include at least four pairs per length")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = relations(json.loads(MANIFEST.read_text()))
    if args.case:
        rows = [row for row in rows if row["id"] in args.case]
        if {row["id"] for row in rows} != set(args.case):
            raise ValueError("Unknown comparison selection")
    if args.mode == "prepare":
        prepare(args, rows)
    else:
        collect(args, json.loads((args.out / "config.json").read_text()))


if __name__ == "__main__":
    main()
