"""Compare frozen cyTimes, current Rust and candidate Rust using isolated workers.

One committed record contains all three adjacent batches. The fixed six orders,
quality rules and logical block boundaries are preserved across continuation.
"""
import argparse
import ast
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
ROLES = ("oracle", "old", "new")
ORDERS = tuple(itertools.permutations(ROLES))
PROTOCOL = "delta-isolated-three-v2-clock-floor"
LABELS = ("current", "original")
REVISION = False
SUITE = "legacy"
FULL_IDS = None
PRECISION_CASES = (
    "relative:zero", "getters:single", "delta-arithmetic:positive:add",
    "date-call:ny-fold:reuse", "dateutil:from:integer:Delta",
    "numpy-datetime:ns:negative:add", "save:child:read", "pydt:month:add",
    "delta-arithmetic:year:both:add", "unary:negative-us:abs",
)
spec = importlib.util.spec_from_file_location("delta_bench", SELF.with_name("bench.py"))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
paired = bench.short_protocol()


def validate_group(group, pids):
    """Reject incomplete/incorrect identities; return quality rejection reasons.

    Worker-local clocks and snapshots must lie inside the controller interval.
    A valid slow group is retained; elapsed speed is never an eligibility rule.
    """
    if set(group["members"]) != set(ROLES) or tuple(group["order"]) not in ORDERS:
        raise ValueError("A complete group requires each frozen role exactly once")
    if type(group["count"]) is not int or group["count"] <= 0:
        raise ValueError("Invalid group invocation count")
    failures = []
    preceding_end = group["start_ns"]
    for role in group["order"]:
        member = group["members"][role]
        if member["before"]["start_ns"] < preceding_end:
            raise ValueError("Recorded execution order differs from the measured boundaries")
        preceding_end = member["after"]["end_ns"]
    for role, member in group["members"].items():
        batch = member["batches"]["engine"]
        if member["pid"] != pids[role] or member["count"] != group["count"] or batch["count"] != group["count"]:
            raise ValueError("Worker identity or work amount differs from the group")
        if not (group["start_ns"] <= member["before"]["start_ns"]
                <= member["before"]["end_ns"] <= member["after"]["start_ns"]
                <= member["after"]["end_ns"] <= group["end_ns"]):
            raise ValueError("Worker monotonic clocks do not share the controller boundary")
        failures.extend(role + ":" + reason for reason in member["reasons"])
        if member["valid"] != (not member["reasons"]):
            raise ValueError("Worker quality verdict contradicts its evidence")
    if group["end_ns"] - group["start_ns"] > paired.RULES["span_ns"]:
        failures.append("group-span")
    return sorted(set(failures))


def validate_resume(previous, identity):
    """Require exact binary/input/rule identity; continuation never resets limits."""
    if previous["identity"] != identity:
        raise ValueError("Resume differs in implementation, input, environment or protocol")


def summarize_case(case, state, block_count, width):
    """Aggregate fixed accepted groups, preserving every valid observation."""
    accepted = state["accepted"]
    blocks = []
    quotas = True
    for start in range(0, len(accepted) - width + 1, width):
        groups = accepted[start:start + width]
        orders = Counter(tuple(group["order"]) for group in groups)
        expected = Counter(ORDERS[index % len(ORDERS)] for index in range(start, start + width))
        quotas = quotas and orders == expected
        batches = {}
        for role in ROLES:
            count = sum(group["members"][role]["batches"]["engine"]["count"] for group in groups)
            elapsed = sum(group["members"][role]["batches"]["engine"]["elapsed_ns"] for group in groups)
            batches[role] = {"count": count, "elapsed_ns": elapsed, "ns_per_call": elapsed / count}
        blocks.append(batches)
    row = {**case, "complete": len(accepted) == block_count * width and quotas,
           "valid_groups": len(accepted), "attempts": state["attempts"], "blocks": blocks,
           "count": state.get("count"), "target_ms": state.get("target_ms")}
    if not blocks:
        return row
    for label, reference in zip(LABELS, ("old", "oracle")):
        ratios = [block[reference]["ns_per_call"] / block["new"]["ns_per_call"] for block in blocks]
        mid = statistics.median(ratios)
        old = statistics.median(block[reference]["ns_per_call"] for block in blocks)
        new = statistics.median(block["new"]["ns_per_call"] for block in blocks)
        row[label] = {"id": case["id"], "group": case["group"], "speed_ratio": old / new,
                      "paired_median_ratio": mid, "conservative_ratio": min(ratios),
                      "conservative_candidate_ratio": 1 / min(ratios),
                      "reference_ns": old, "candidate_ns": new,
                      "max_noise": max(abs(value / mid - 1) for value in ratios)}
    return row


def evaluate(rows, cases, formal, precision):
    """Report completeness, stability and gates separately; partial cannot pass."""
    complete = {row["id"] for row in rows} == {case["id"] for case in cases}
    complete = complete and all(row["complete"] for row in rows)
    stable = complete and all(row[label]["max_noise"] <= .05 for row in rows for label in LABELS)
    summaries = {}
    for label in LABELS:
        usable = [row[label] for row in rows if label in row]
        summaries[label] = bench.aggregates(usable) if usable else {"groups": {}, "core": None, "thirdparty": None}
    current = summaries["current"]
    original = summaries.get("original", {})
    fields = ("median_ratio", "conservative_ratio")
    gates = {} if REVISION else {
        "G1": bool(current["core"] and all(current["core"][field] >= 1.10 for field in fields)),
        "G2": complete and all(row["current"]["speed_ratio"] >= 1 / 1.10
                               and row["current"]["conservative_ratio"] >= 1 / 1.10 for row in rows),
        "G3": all(group in current["groups"] and all(current["groups"][group][field] >= 1 for field in fields)
                   for group in ("B7", "B8", "B10")),
        "G4": bool(complete and original["core"] and original["thirdparty"]
                   and all(original["core"][field] >= 1.25 and original["thirdparty"][field] >= 1 for field in fields)
                   and all(row["original"]["speed_ratio"] >= 1 / 1.10
                           and row["original"]["conservative_ratio"] >= 1 / 1.10
                           for row in rows if row["group"] != "B10")),
    }
    if REVISION:
        def ratio_pass(summary, minimum):
            return all(summary[field] >= minimum for field in ("speed_ratio", "conservative_ratio"))
        if SUITE == "legacy":
            gates = {"P01": complete and all(ratio_pass(row["current"], 1 / 1.05) for row in rows)
                     and all(all(group[field] >= 1 / 1.05 for field in fields) for group in current["groups"].values()),
                     "P05": bool(complete and original.get("core") and original.get("thirdparty")
                     and all(original["core"][field] >= 1.25 and original["thirdparty"][field] >= 1 for field in fields)
                     and all(ratio_pass(row["original"], 1 / 1.10) for row in rows))}
        elif SUITE == "float":
            gates = {"P02": complete and all(ratio_pass(row["current"], 1 / 1.20) for row in rows)
                     and all(all(group[field] >= 1 / 1.20 for field in fields) for group in current["groups"].values())}
        elif SUITE == "bulk":
            gates = {
                "P03": complete and all(all(group[field] >= 1.50 for field in fields)
                    for key, group in current["groups"].items() if key.startswith(("A1:", "A2:", "A3:"))),
                # Only the three approved foreign groups permit 5% overhead.
                # NumPy retains its original no-regression requirement.
                "P04": complete and all(all(group[field] >= (1.00 if key.startswith("A6:") else 1 / 1.05)
                    for field in fields) for key, group in current["groups"].items()
                    if key.startswith(("A4:", "A5:", "A6:", "A7:"))),
            }
        elif SUITE == "conversion":
            gates = {"report_only": complete}
        else:
            gates = {"template_only": complete}
    manifest = json.loads(SELF.with_name("cases.json").read_text())
    full_ids = {identifier for identifiers in manifest["groups"].values() for identifier in identifiers}
    full_contract = {case["id"] for case in cases} == (FULL_IDS if REVISION else full_ids)
    performance = "INCONCLUSIVE"
    if formal and precision and complete and stable and full_contract and SUITE != "template":
        performance = "PASS" if all(gates.values()) else "FAIL"
    return {"collection": "COMPLETE" if complete else "INCOMPLETE", "quality": "VALID",
            "stability": "PASS" if stable else "INCONCLUSIVE", "precision": bool(precision),
            "performance": performance, "full_contract": full_contract, "gates": gates, "aggregates": summaries}


class Workers:
    """Own three independent installations and validate their shared workload."""
    def __init__(self, args):
        """Start workers with equal thread policy; cleanup any partial startup."""
        self.workers = {}
        try:
            installations = (("oracle", args.oracle_env, "cytimes"),
                             ("old", args.baseline_env, "rstimes"), ("new", args.candidate_env, "rstimes"))
            if REVISION and SUITE != "legacy":
                installations = (("old", args.candidate_env, "rstimes"), ("new", args.candidate_env, "rstimes"))
            for role, env, package in installations:
                variant = "legacy"
                if REVISION and SUITE != "legacy":
                    variant = ("template" if SUITE == "template" else "revision") + ("-reference" if role == "old" else "-candidate")
                self.workers[role] = bench.Process(env, package, args.group, args.case, 0, "interactive", variant)
            self.metadata = {role: worker.metadata for role, worker in self.workers.items()}
            if REVISION and SUITE == "legacy":
                frozen = json.loads((ROOT / "tasks/evidence/delta-revision-20261012/baseline.json").read_text())
                for role, key in (("old", "baseline"), ("oracle", "oracle")):
                    if self.metadata[role]["environment"]["native_sha256"] != frozen[key]["native_sha256"]:
                        raise ValueError(f"Wrong frozen revision baseline: {role}")
            self.host = {role: worker.short_info() for role, worker in self.workers.items()}
            self.pids = {role: info["pid"] for role, info in self.host.items()}
            if len(set(self.pids.values())) != len(ROLES):
                raise ValueError("Independent roles require distinct actual processes")
            if any(self.metadata[role]["loaded_identity"]["pid"] != pid for role, pid in self.pids.items()):
                raise ValueError("Preflight and timing worker identities differ")
            reference = self.metadata[ROLES[0]]
            keys = ("python", "platform", "machine", "measurement_qos", "process_model",
                    "gil_disabled_build", "gil_enabled", "dependencies")
            for role, metadata in self.metadata.items():
                if metadata["cases"] != reference["cases"] or bench.comparable(metadata) != bench.comparable(reference):
                    raise ValueError(f"Unequal workload output: {role}")
                if any(metadata["environment"][key] != reference["environment"][key] for key in keys):
                    raise ValueError(f"Unequal dependency/runtime state: {role}")
            self.cases = reference["cases"]
        except BaseException:
            try:
                self.close()
            except Exception:
                pass  # Preserve the startup failure rather than a secondary EOF.
            raise

    def close(self):
        """Close only this session's owned workers, including unsuccessful ones."""
        first = None
        for worker in self.workers.values():
            try:
                worker.close()
            except Exception as error:
                first = first or error
        self.workers.clear()
        if first is not None:
            raise first

    def group(self, identifier, count, order, warmup):
        """Measure a complete supplied order and retain all local evidence."""
        record = {"count": count, "order": list(order), "members": {}, "start_ns": time.perf_counter_ns()}
        for role in order:
            record["members"][role] = self.workers[role].short_sample(identifier, count, warmup)
        record["end_ns"] = time.perf_counter_ns()
        record["reasons"] = validate_group(record, self.pids)
        record["valid"] = not record["reasons"]
        return record

    def identity(self, config):
        """Bind timings to binaries, inputs, environment and fixed rules, not PIDs."""
        metadata = json.loads(json.dumps(self.metadata))
        for value in metadata.values():
            value["loaded_identity"].pop("pid")
        host = json.loads(json.dumps(self.host))
        for value in host.values():
            value.pop("pid")
            value.pop("clock_read_p99_ns")
        return {"protocol": PROTOCOL, "metadata": metadata, "hardware": host,
                "helper_sha256": bench.digest(SELF.with_name("paired.py")),
                "collector_sha256": bench.digest(SELF), "rules": paired.RULES,
                "sampling": config}


def calibrate(workers, identifier, target, minimum_count=1):
    """Choose common counts that satisfy duration and each worker's clock precision.

    Measured startup clock cost/resolution fixes a per-role minimum duration.
    A frozen 25% margin protects that bound; speeds only choose invocation count,
    never eligibility or which accepted timing is retained. Pilots are not scores.
    """
    count = max(minimum_count, 1 if identifier.startswith("bulk:") else 2000)
    pilots = []
    for _ in range(5):
        pilot = workers.group(identifier, count, ROLES, count)
        pilots.append(pilot)
        fastest = min(member["batches"]["engine"]["ns_per_call"] for member in pilot["members"].values())
        floor = max(math.ceil(1.25 * max(info["clock_read_p99_ns"],
                                             *(info[clock]["resolution"] * 1e9 for clock in ("wall_clock", "thread_clock")))
                              / paired.RULES["clock_fraction"]
                              / pilot["members"][role]["batches"]["engine"]["ns_per_call"])
                    for role, info in workers.host.items())
        proposed = min(100_000_000, max(minimum_count, floor, math.ceil(target * 1e6 / fastest)))
        if .8 * proposed <= count <= 1.25 * proposed:
            break
        count = proposed
    return proposed, max(1, math.ceil(.25e6 / fastest)), pilots


def atomic_save(path, value):
    """Replace one complete checkpoint; journal stores only complete attempts."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")) + "\n")
    temporary.replace(path)


def replay_journal(states, path, inherited, pids):
    """Restore reserved attempts and complete commits without resetting limits.

    A reserved attempt whose worker died counts toward the limit but contributes
    no accepted sample. Only an incomplete final line can be ignored after a crash.
    """
    if not path.exists():
        return inherited
    contents = path.read_text()
    lines = contents.splitlines()
    for index, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1 and not contents.endswith("\n"):
                break
            raise
        state = states[entry["id"]]
        inherited = max(inherited, entry["elapsed_seconds"])
        if entry["kind"] == "begin":
            if entry["attempt"] <= state["attempts"]:
                continue
            if entry["attempt"] != state["attempts"] + 1:
                raise ValueError("Gapped continuation journal")
            state["attempts"] = entry["attempt"]
            state.update(entry["calibration"])
            state["pending_attempt"] = entry["attempt"]
        elif entry["kind"] == "commit":
            if state.get("pending_attempt") != entry["attempt"]:
                continue  # Already contained in the saved checkpoint.
            group = entry["group"]
            reasons = validate_group(group, pids)
            if reasons != group["reasons"] or group["valid"] != (not reasons):
                raise ValueError("Journal group verdict differs from its evidence")
            if group["valid"]:
                state["accepted"].append(group)
            state.pop("pending_attempt")
        else:
            raise ValueError("Unknown journal entry")
    return inherited


def sampling_config(args, mode=None):
    """Describe the exact collection configuration used by a precision receipt."""
    mode = mode or args.mode
    return {"mode": mode, "blocks": 12 if mode == "formal" else 6,
            "width": 120 if mode == "formal" else (args.width or 20),
            "short_ms": args.short_ms, "session_seconds": args.session_seconds,
            "attempt_cap": 4320, "group": args.group, "cases": args.case,
            "case_targets_ms": args.case_targets,
            "case_minimum_calls": getattr(args, "case_min_counts", {}),
            "extra_precision_cases": list(getattr(args, "extra_cases", [])),
            "clock_count_floor_margin": 1.25, "revision": REVISION, "suite": SUITE, "control_multiplier": getattr(args, "control_multiplier", 5)}


def target_ms(args, identifier):
    """Use the declared case duration; never change it in response to a speed."""
    default = max(args.short_ms, 5) if identifier in PRECISION_CASES[-2:] else args.short_ms
    return args.case_targets.get(identifier, default)


def precision_passed(comparisons):
    """Apply the frozen completeness, 3% precision and 5% noise requirements."""
    return all(item["complete"] and all(item[label]["relative_difference"] <= .03
                                       and item[label]["short_noise"] <= .05
                                       and item[label]["long_noise"] <= .05
                                       for label in LABELS) for item in comparisons)


def measurement_source_signature(path):
    """Hash the unchanged timing, eligibility, workload selection and statistics.

    Scoped control orchestration may add selection and provenance only. Its exact
    measurement loop, all worker code and statistical calculations must match the
    archived source before any earlier case evidence is reused.
    """
    tree = ast.parse(Path(path).read_text())
    names = {"Workers", "validate_group", "summarize_case", "evaluate", "calibrate",
             "sampling_config", "target_ms"}
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    nodes += [node for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(name, ast.Name) and name.id in {"ROLES", "ORDERS", "PRECISION_CASES", "PROTOCOL"}
                      for name in node.targets)]
    control = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "precision_control")
    nodes += [node for node in ast.walk(control) if isinstance(node, ast.While)]
    return hashlib.sha256("\n".join(ast.dump(node, include_attributes=False) for node in nodes).encode()).hexdigest()


def compatible_controls(primary, current, archived_source, selected, prior_path=None, formal_failure=None):
    """Prove only declared durations changed and only failed cases are replaced."""
    if bench.digest(Path(archived_source)) != primary["identity"]["collector_sha256"]:
        raise ValueError("Archived collector does not match the original receipt")
    if measurement_source_signature(archived_source) != measurement_source_signature(SELF):
        raise ValueError("Public timing, eligibility or statistics changed; earlier controls cannot be reused")
    left, right = json.loads(json.dumps(primary["identity"])), json.loads(json.dumps(current))
    left.pop("collector_sha256"); right.pop("collector_sha256")
    old_extra = set(left["sampling"].pop("extra_precision_cases"))
    new_extra = set(right["sampling"].pop("extra_precision_cases"))
    added = new_extra - old_extra
    if not old_extra <= new_extra or not added <= set(selected):
        raise ValueError("Only the declared new failed controls may extend the control scope")
    old_targets = left["sampling"].pop("case_targets_ms")
    new_targets = right["sampling"].pop("case_targets_ms")
    old_minimum = left["sampling"].pop("case_minimum_calls", {})
    new_minimum = right["sampling"].pop("case_minimum_calls", {})
    minimum_changed = {key for key in old_minimum.keys() | new_minimum.keys()
                       if old_minimum.get(key, 1) != new_minimum.get(key, 1)}
    if left != right:
        raise ValueError("Control binary/input/environment/rule identity changed")
    changed = {key for key in old_targets.keys() | new_targets.keys()
               if old_targets.get(key, 1) != new_targets.get(key, 1)}
    failed = {item["id"] for item in primary["comparisons"] if not precision_passed([item])}
    formal_failed = set()
    if formal_failure is not None:
        formal = json.loads(Path(formal_failure).read_text())
        original_identity = json.loads(json.dumps(primary["identity"]))
        formal_identity = json.loads(json.dumps(formal["identity"]))
        original_identity.pop("collector_sha256"); formal_identity.pop("collector_sha256")
        if (original_identity != formal_identity or formal["evaluation"]["collection"] != "COMPLETE"
                or formal["evaluation"]["quality"] != "VALID"
                or not all(formal["evaluation"]["gates"].values())):
            raise ValueError("Formal noise justification differs or includes a performance failure")
        formal_failed = {row["id"] for row in formal["rows"]
                         if row["complete"] and any(row[label]["max_noise"] > .05 for label in LABELS)}
        for key in formal_failed:
            row = next(item for item in formal["rows"] if item["id"] == key)
            state = formal["states"][key]
            pids = formal["actual_pids"] or formal["case_sources"][key]["actual_pids"]
            if (len(state["accepted"]) != 1440 or any(validate_group(group, pids) for group in state["accepted"])
                    or summarize_case({"id": key, "group": row["group"]}, state, 12, 120) != row):
                raise ValueError("Formal noise justification lacks complete audited raw evidence")
        if not formal_failed:
            raise ValueError("Formal receipt contains no declared unstable scenes")
        failed |= formal_failed
    if set(selected) != failed | added or not changed <= set(selected):
        raise ValueError("Scoped control must replace the complete predeclared failed set")
    if minimum_changed:
        # Only a complete failed bulk control may adjust common repetitions.
        # Full calls, 12x40 units and all public quality boundaries stay intact.
        if SUITE != "bulk" or not minimum_changed <= failed & set(selected) or prior_path is None:
            raise ValueError("Only declared failed bulk controls may increase common calls")
        for key in minimum_changed:
            old_count, new_count = old_minimum.get(key, 1), new_minimum[key]
            item = next(row for row in primary["comparisons"] if row["id"] == key)
            if not item["complete"]:
                raise ValueError("Minimum adjustment requires complete original evidence")
            source = primary.get("case_sources", {}).get(key, {}).get("path", prior_path)
            spans = []
            with Path(source).with_name("units.jsonl").open() as journal:
                for line in journal:
                    unit = json.loads(line)
                    if unit["id"] == key and unit["valid"]:
                        spans.append(unit["span_ns"])
            if len(spans) != 480:
                raise ValueError("Common repetition adjustment lacks complete raw spans")
            if new_count > old_count:
                if (new_count > old_count * 2 or statistics.median(spans) * new_count
                        / old_count > .8 * paired.RULES["span_ns"]):
                    raise ValueError("Longer complete calls do not fit the frozen joint span")
            else:
                # A too-close joint boundary can make an increase unmeasurable.
                # Pick the largest count fitting 80% of the hard span, using
                # timestamps only. Calibrate still enforces every clock floor.
                measured_count = primary["states"][key][0]["accepted"][0]["count"]
                safe_count = math.floor(old_count * .8 * paired.RULES["span_ns"] / max(spans))
                if (old_count != measured_count or max(spans) <= .8 * paired.RULES["span_ns"]
                        or not 1 <= new_count < old_count or new_count != safe_count):
                    raise ValueError("Shorter repetition count lacks a measured joint-margin reason")
    for key in changed:
        old = old_targets.get(key, 5 if key in PRECISION_CASES[-2:] else 1)
        new = new_targets.get(key)
        if key in added and old == 1 and 1 < new <= 5:
            # Newly observed unstable formal scenes get controls before use.
            # A smaller window can be sufficient and preserves collection time.
            continue
        if (old, new) in {(1, 5), (5, 10)}:
            continue
        item = next(row for row in primary["comparisons"] if row["id"] == key)
        if (prior_path is not None and item["complete"]
                and (not precision_passed([item]) or key in formal_failed) and old < new <= 10):
            # A smaller, evidence-bounded increase avoids forcing a 10ms window
            # beyond the hard joint limit. Only a complete failed case qualifies;
            # every original valid unit remains, and actual quality is unchanged.
            source = primary.get("case_sources", {}).get(key, {}).get("path", prior_path)
            spans = []
            with Path(source).with_name("units.jsonl").open() as journal:
                for line in journal:
                    unit = json.loads(line)
                    if unit["id"] == key and unit["valid"]:
                        spans.append(unit["span_ns"])
            if len(spans) != 480 or new / old * max(spans) > .9 * paired.RULES["span_ns"]:
                raise ValueError("Bounded increase lacks complete safe joint-span evidence")
            continue
        # A requested/projected 10ms window may be unmeasurable with its full
        # control. A bounded frozen target is allowed only by raw span evidence,
        # before a performance verdict, with the original quality rules intact.
        allowed = ((old == 10 and not item["complete"])
                   or (old == 5 and not precision_passed([item])))
        if prior_path is None or not allowed or not 5 <= new < 10:
            raise ValueError("Scoped duration changes must follow the declared bounded adjustment")
        source = primary.get("case_sources", {}).get(key, {}).get("path", prior_path)
        spans = []
        with Path(source).with_name("units.jsonl").open() as journal:
            for line in journal:
                unit = json.loads(line)
                if unit["id"] == key and all(group["valid"] for group in unit["unit"].values()):
                    spans.append(unit["span_ns"])
        if (len(spans) < 12 or 10 / old * statistics.median(spans) <= paired.RULES["span_ns"]
                or new / old * max(spans) > .8 * paired.RULES["span_ns"]):
            raise ValueError("Reduced control duration lacks complete joint-span evidence")


def precision_control(args):
    """Validate the fixed controls and explicitly declared exceptions in twelve blocks.

    All six measurements in a short/long unit must qualify. Length order alternates,
    the three implementation orders are balanced, and every valid slow unit stays.
    The receipt binds to the full formal matrix, not merely the control subset.
    """
    if (args.case and not REVISION) or args.group != "all" or args.width:
        raise ValueError("Precision control requires the unmodified full workload")
    control_cases = PRECISION_CASES + tuple(args.extra_cases)
    selected = tuple(args.control_case or args.partition_cases or control_cases)
    if not set(selected) <= set(control_cases) or len(set(selected)) != len(selected):
        raise ValueError("Invalid declared control scope")
    if args.control_case and not (args.reuse_control and args.reuse_source):
        raise ValueError("Scoped control requires its unchanged source and original receipt")
    workers = Workers(args)
    started = time.monotonic()
    deadline = started + (args.control_seconds or (600 if args.extra_cases else 300))
    directory = Path(args.output) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory.mkdir(parents=True)
    states = {identifier: [{"accepted": [], "attempts": 0} for _ in range(2)]
              for identifier in selected}
    targets, counts, ready = {}, {}, {}
    queue = deque(selected)
    width, blocks, needed = 40, 12, 480
    try:
        identity = workers.identity(sampling_config(args, "formal"))
        # Save provenance before measuring, including actual process identities.
        atomic_save(directory / "control-start.json", {
            "identity": identity, "actual_pids": workers.pids,
            "cases": workers.cases, "selected": selected,
            "clock_calibration": workers.host, "started_utc": datetime.now(timezone.utc).isoformat(),
        })
        primary = json.loads(Path(args.reuse_control).read_text()) if args.reuse_control else None
        if primary:
            compatible_controls(primary, identity, args.reuse_source, selected, args.reuse_control,
                                getattr(args, "control_failure_source", None))
        with (directory / "units.jsonl").open("x") as journal:
            next_report = time.monotonic() + 30
            while queue and time.monotonic() < deadline - 1:
                identifier = queue.popleft()
                left, right = states[identifier]
                if left["attempts"] >= needed * 3:
                    continue
                if time.monotonic() < ready.get(identifier, 0):
                    queue.append(identifier)
                    time.sleep(.01)
                    continue
                if identifier not in counts:
                    target = target_ms(args, identifier)
                    count, warm, pilots = calibrate(workers, identifier, target, getattr(args, "case_min_counts", {}).get(identifier, 1))
                    counts[identifier] = count, warm
                    targets[identifier] = {"target_ms": target, "pilots": pilots}
                count, warm = counts[identifier]
                index = len(left["accepted"])
                order = ORDERS[index % len(ORDERS)]
                sequence = (0, 1) if index % 2 == 0 else (1, 0)
                unit = {side: workers.group(identifier, count * (1 if side == 0 else args.control_multiplier), order, warm)
                        for side in sequence}
                span = max(group["end_ns"] for group in unit.values()) - min(group["start_ns"] for group in unit.values())
                valid = all(group["valid"] for group in unit.values()) and span <= paired.RULES["span_ns"]
                left["attempts"] += 1; right["attempts"] += 1
                journal.write(json.dumps({"id": identifier, "attempt": left["attempts"],
                                          "valid": valid, "span_ns": span, "unit": unit}, separators=(",", ":")) + "\n")
                journal.flush()
                if valid:
                    left["accepted"].append(unit[0]); right["accepted"].append(unit[1])
                    if index + 1 < needed:
                        queue.appendleft(identifier)
                else:
                    ready[identifier] = time.monotonic() + 1
                    queue.append(identifier)
                if time.monotonic() >= next_report:
                    print(json.dumps({"control_valid_units": sum(len(pair[0]["accepted"]) for pair in states.values()),
                                      "remaining_cases": len(queue), "elapsed_seconds": time.monotonic() - started}), flush=True)
                    next_report = time.monotonic() + 30
        cases = {case["id"]: case for case in workers.cases}
        comparisons = []
        for identifier, pair in states.items():
            short, long = [summarize_case(cases[identifier], state, blocks, width) for state in pair]
            item = {"id": identifier, "complete": short["complete"] and long["complete"]}
            if item["complete"]:
                for label in LABELS:
                    item[label] = {"relative_difference": abs(short[label]["speed_ratio"] / long[label]["speed_ratio"] - 1),
                                   "short_noise": short[label]["max_noise"], "long_noise": long[label]["max_noise"]}
            comparisons.append(item)
        passed = precision_passed(comparisons)
        result = {"identity": identity, "passed": passed,
                  "actual_pids": workers.pids, "comparisons": comparisons, "targets": targets,
                  "states": states, "blocks": blocks, "width": width,
                  "elapsed_seconds": time.monotonic() - started, "excluded_slow_valid_units": 0,
                  "clock_calibration": workers.host, "planned_partition": args.partition_cases}
        if primary:
            partial = directory / "scoped-precision.json"
            atomic_save(partial, result)
            changed = set(selected)
            original_path = str(Path(args.reuse_control).resolve())
            result["case_sources"] = {identifier: {"path": str(partial.resolve()) if identifier in changed else original_path,
                                                   "actual_pids": workers.pids if identifier in changed else (primary.get("case_sources", {}).get(identifier, {}).get("actual_pids") or primary["actual_pids"])}
                                      for identifier in control_cases}
            result["states"] = {identifier: states[identifier] if identifier in changed else primary["states"][identifier]
                                 for identifier in control_cases}
            result["comparisons"] = [next(item for item in (comparisons if identifier in changed else primary["comparisons"])
                                                 if item["id"] == identifier) for identifier in control_cases]
            result["targets"] = {identifier: targets[identifier] if identifier in changed else primary["targets"][identifier]
                                 for identifier in control_cases}
            result["passed"] = precision_passed(result["comparisons"])
            result["actual_pids"] = None  # Composite controls retain per-case actual cycles.
            result["source_compatibility"] = {"archived_source": str(Path(args.reuse_source).resolve()),
                                               "measurement_signature": measurement_source_signature(SELF),
                                               "reused_cases": sorted(set(control_cases) - changed),
                                               "replaced_cases": sorted(changed)}
        atomic_save(directory / "precision.json", result)
        print(json.dumps({"precision": str(directory / "precision.json"), "passed": result["passed"],
                          "comparisons": result["comparisons"]}), flush=True)
        return directory / "precision.json"
    finally:
        workers.close()


def validate_precision(proof, identity, cases, control_cases, archived_source=None):
    """Require complete raw controls from a real cycle bound to this final artifact.

    Recompute fixed blocks and all precision verdicts instead of trusting a saved
    passed flag. Every short/long pair keeps the same count, order and actual PIDs.
    """
    bound_identity = json.loads(json.dumps(proof["identity"]))
    current_identity = json.loads(json.dumps(identity))
    if bound_identity.get("collector_sha256") != current_identity.get("collector_sha256"):
        # Validation/orchestration edits may reuse measured data only when the
        # saved original source proves the exact public measurement AST unchanged.
        provenance = proof.get("source_compatibility", {})
        archived = archived_source or provenance.get("archived_source")
        if (not archived or bench.digest(Path(archived)) != bound_identity["collector_sha256"]
                or measurement_source_signature(archived) != measurement_source_signature(SELF)):
            raise ValueError("Collector change lacks unchanged measurement source proof")
        bound_identity["collector_sha256"] = current_identity["collector_sha256"]
    if (bound_identity != current_identity or not proof["passed"]
            or {item["id"] for item in proof["comparisons"]} != set(control_cases)
            or set(proof["states"]) != set(control_cases)
            or proof["blocks"] != 12 or proof["width"] != 40):
        raise ValueError("Precision evidence is not bound to this candidate/configuration")
    common_pids = proof["actual_pids"]
    case_map = {case["id"]: case for case in cases}
    recomputed = []
    for identifier in control_cases:
        pids = common_pids or proof["case_sources"][identifier]["actual_pids"]
        if not isinstance(pids, dict) or set(pids) != set(ROLES) or len(set(pids.values())) != len(ROLES):
            raise ValueError("Each complete precision case requires three distinct actual worker processes")
        pair = proof["states"][identifier]
        if len(pair) != 2 or any(len(state["accepted"]) != 480 for state in pair):
            raise ValueError("Incomplete raw precision evidence")
        preceding_end = 0
        fixed_count = pair[0]["accepted"][0]["count"]
        for index, (short, long) in enumerate(zip(pair[0]["accepted"], pair[1]["accepted"])):
            for group in (short, long):
                reasons = validate_group(group, pids)
                if reasons or group["reasons"] != reasons or not group["valid"]:
                    raise ValueError("Invalid group in accepted precision evidence")
            if (tuple(short["order"]) != ORDERS[index % len(ORDERS)] or short["order"] != long["order"]
                    or short["count"] != fixed_count or long["count"] != short["count"] * identity["sampling"].get("control_multiplier", 5)):
                raise ValueError("Precision order or short/long work amount differs")
            first, second = (short, long) if index % 2 == 0 else (long, short)
            if first["start_ns"] < preceding_end or first["end_ns"] > second["start_ns"]:
                raise ValueError("Precision length order or chronological evidence differs")
            preceding_end = second["end_ns"]
            span = preceding_end - first["start_ns"]
            if span > paired.RULES["span_ns"]:
                raise ValueError("Precision short/long pair exceeds the joint boundary")
        short, long = [summarize_case(case_map[identifier], state, 12, 40) for state in pair]
        item = {"id": identifier, "complete": short["complete"] and long["complete"]}
        for label in LABELS:
            item[label] = {"relative_difference": abs(short[label]["speed_ratio"] / long[label]["speed_ratio"] - 1),
                           "short_noise": short[label]["max_noise"], "long_noise": long[label]["max_noise"]}
        recomputed.append(item)
    if recomputed != proof["comparisons"] or not precision_passed(recomputed):
        raise ValueError("Precision verdict differs from its complete raw evidence")


def validate_local_formal(primary, identity, archived_source, selected, align_path=None):
    """Allow only declared unstable scenes to replace complete original scene results.

    The actual artifact, all input/quality/work/timing/statistical code and environment
    must match. Only failed scene durations may change; consumed limits are inherited.
    """
    if bench.digest(Path(archived_source)) != primary["identity"]["collector_sha256"]:
        raise ValueError("Original formal collector archive differs")
    if measurement_source_signature(archived_source) != measurement_source_signature(SELF):
        raise ValueError("Formal measurement functions changed")
    old_tree, new_tree = [ast.parse(Path(path).read_text()) for path in (archived_source, SELF)]
    loops = []
    for tree in (old_tree, new_tree):
        collect_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "collect")
        loops.append([ast.dump(node, include_attributes=False) for node in ast.walk(collect_node) if isinstance(node, ast.While)])
    if loops[0] != loops[1]:
        raise ValueError("Formal target timing or collection loop changed")
    left, right = json.loads(json.dumps(primary["identity"])), json.loads(json.dumps(identity))
    left.pop("collector_sha256"); right.pop("collector_sha256")
    old_extra = set(left["sampling"].pop("extra_precision_cases")); new_extra = set(right["sampling"].pop("extra_precision_cases"))
    old_targets = left["sampling"].pop("case_targets_ms"); new_targets = right["sampling"].pop("case_targets_ms")
    required_new_controls = set(selected) - set(PRECISION_CASES) - old_extra
    if left != right or new_extra - old_extra != required_new_controls or not old_extra <= new_extra:
        raise ValueError("Formal input/artifact/environment or declared control scope differs")
    failed = {row["id"] for row in primary["rows"] if not row["complete"] or any(row[label]["max_noise"] > .05 for label in LABELS)}
    if align_path:
        counterpart = json.loads(Path(align_path).read_text())
        if counterpart["identity"] != primary["identity"]:
            raise ValueError("Alignment counterpart differs in artifact/input/environment/configuration")
        failed |= {row["id"] for row in counterpart["rows"] if not row["complete"] or any(row[label]["max_noise"] > .05 for label in LABELS)}
    changed = {key for key in old_targets.keys() | new_targets.keys() if old_targets.get(key, 1) != new_targets.get(key, 1)}
    # Only complete noise failures whose numerical gates already pass qualify.
    # The caller has already validated new raw precision controls for every
    # selected scene; durations remain within the public1..10ms envelope.
    evaluation = primary["evaluation"]
    if (evaluation["collection"] != "COMPLETE" or evaluation["quality"] != "VALID"
            or not all(evaluation["gates"].values())):
        raise ValueError("Scoped replacement requires complete numerically passing formal evidence")
    if (set(selected) != failed or changed != failed
            or any(not old_targets.get(key, 5 if key in PRECISION_CASES[-2:] else 1)
                   < new_targets[key] <= 10 for key in changed)):
        raise ValueError("Only the complete frozen unstable set may receive verified bounded duration replacement")


def collect(args):
    """Collect finite fixed-order groups, restoring committed evidence and limits."""
    started = time.monotonic()
    required = 12 if args.mode == "formal" else 6
    width = args.width if args.width else (120 if args.mode == "formal" else 20)
    if args.mode == "formal" and width != 120:
        raise ValueError("Formal collection requires 120 complete groups per block")
    if width <= 0 or (required * width) % len(ORDERS):
        raise ValueError("Complete collection must balance every declared order")
    config = sampling_config(args)
    workers = Workers(args)
    try:
        identity = workers.identity(config)
        precision = False
        if args.precision:
            proof = json.loads(Path(args.precision).read_text())
            validate_precision(proof, identity, workers.cases, PRECISION_CASES + tuple(args.extra_cases), args.precision_source)
            precision = True
        directory = Path(args.output) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        directory.mkdir(parents=True)
        states = {case["id"]: {"accepted": [], "attempts": 0, "calibration": []} for case in workers.cases}
        inherited = 0
        sources = []
        if args.formal_case:
            primary = json.loads(Path(args.reuse_formal).read_text())
            validate_local_formal(primary, identity, args.reuse_source, args.formal_case, args.align_to)
            inherited = primary["elapsed_seconds"]
            for identifier in args.formal_case:
                states[identifier]["attempts"] = primary["states"][identifier]["attempts"]
            sources = [str(Path(args.reuse_formal).resolve())]
        if args.resume:
            previous = json.loads(Path(args.resume).read_text())
            validate_resume(previous, identity)
            states, inherited = previous["states"], previous["elapsed_seconds"]
            sources = previous.get("sources", []) + [str(Path(args.resume).resolve())]
            journal = Path(args.resume).with_name("attempts.jsonl")
            inherited = replay_journal(states, journal, inherited, previous["actual_pids"])
            if args.mode == "formal":
                # Formal acceptance requires a complete actual process cycle.
                # Keep earlier raw files as fragments and inherit consumed limits.
                for state in states.values():
                    state["accepted"] = []
                    state.pop("pending_attempt", None)
        cumulative_limit = args.cumulative_seconds or args.session_seconds
        deadline = started + min(args.session_seconds, cumulative_limit - inherited)
        needed = required * width
        queue = deque(case["id"] for case in workers.cases
                      if len(states[case["id"]]["accepted"]) < needed
                      and (not args.partition_cases or case["id"] in args.partition_cases)
                      and (not args.formal_case or case["id"] in args.formal_case))
        result = {"identity": identity, "actual_pids": workers.pids, "mode": args.mode,
                  "cycle_started_utc": datetime.now(timezone.utc).isoformat(), "sources": sources,
                  "clock_calibration": workers.host, "formal_scope": args.formal_case, "alignment_source": args.align_to,
                  "precision": precision, "states": states, "configuration": config,
                  "planned_partition": args.partition_cases}
        result["elapsed_seconds"] = inherited + time.monotonic() - started
        result["cumulative_limit_seconds"] = cumulative_limit
        result["process_segments"] = (previous.get("process_segments", [previous["actual_pids"]])
                                       if args.resume and args.mode == "quick" else []) + [workers.pids]
        atomic_save(directory / "raw.json", result)
        ready = {}
        next_report = time.monotonic() + 30
        with (directory / "attempts.jsonl").open("a") as journal:
            while queue and time.monotonic() < deadline - 1:
                identifier = queue.popleft(); state = states[identifier]
                if state["attempts"] >= 4320:
                    continue
                if time.monotonic() < ready.get(identifier, 0):
                    queue.append(identifier)
                    time.sleep(min(.01, max(0, deadline - time.monotonic())))
                    continue
                if "count" not in state:
                    target = target_ms(args, identifier)
                    state["target_ms"] = target
                    state["count"], state["warmup"], state["calibration"] = calibrate(workers, identifier, target, getattr(args, "case_min_counts", {}).get(identifier, 1))
                index = len(state["accepted"])
                order = ORDERS[index % len(ORDERS)]
                state["attempts"] += 1
                state["pending_attempt"] = state["attempts"]
                entry = {"kind": "begin", "id": identifier, "attempt": state["attempts"],
                         "calibration": {key: state[key] for key in ("count", "warmup", "target_ms")},
                         "elapsed_seconds": inherited + time.monotonic() - started}
                journal.write(json.dumps(entry, separators=(",", ":")) + "\n")
                journal.flush()
                group = workers.group(identifier, state["count"], order, state["warmup"])
                entry = {"kind": "commit", "id": identifier, "attempt": state["attempts"],
                         "group": group, "elapsed_seconds": inherited + time.monotonic() - started}
                journal.write(json.dumps(entry, separators=(",", ":")) + "\n")
                journal.flush()
                state.pop("pending_attempt")
                if group["valid"]:
                    state["accepted"].append(group)
                    if len(state["accepted"]) < needed:
                        queue.appendleft(identifier)
                else:
                    ready[identifier] = time.monotonic() + 1
                    queue.append(identifier)
                if time.monotonic() >= next_report:
                    print(json.dumps({"valid_groups": sum(len(value["accepted"]) for value in states.values()),
                                      "attempts": sum(value["attempts"] for value in states.values()),
                                      "remaining_cases": len(queue), "elapsed_seconds": entry["elapsed_seconds"]}), flush=True)
                    next_report = time.monotonic() + 30
            rows = [summarize_case(case, states[case["id"]], required, width) for case in workers.cases]
            result.update(rows=rows, elapsed_seconds=inherited + time.monotonic() - started,
                          evaluation=evaluate(rows, workers.cases, args.mode == "formal", precision))
            atomic_save(directory / "raw.json", result)
            print(json.dumps({"raw": str(directory / "raw.json"), "evaluation": result["evaluation"]}), flush=True)
        return directory / "raw.json"
    except BaseException as error:
        if "result" in locals():
            result.update(elapsed_seconds=inherited + time.monotonic() - started,
                          error={"type": type(error).__name__, "message": str(error)})
            atomic_save(directory / "raw.json", result)
        raise
    finally:
        failing = sys.exc_info()[0] is not None
        try:
            workers.close()
        except Exception:
            if not failing:
                raise


def main():
    """Run a current-version comparison with explicit environments and bounds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", action="store_true", help="Use the third-round contract, never the old gates")
    parser.add_argument("--suite", choices=("legacy", "template", "float", "bulk", "conversion"), default="legacy")
    parser.add_argument("--control-multiplier", type=int, choices=(2, 5), default=5)
    parser.add_argument("--oracle-env", default=str(ROOT / ".local/delta/oracle"))
    parser.add_argument("--baseline-env", help="Explicit baseline installation; revision defaults to the frozen delta.2 environment")
    parser.add_argument("--candidate-env", default=str(ROOT / ".local/delta/optimization-20261011/candidate-env"))
    parser.add_argument("--group", default="all")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--mode", choices=("quick", "formal"), default="quick")
    parser.add_argument("--width", type=int)
    parser.add_argument("--short-ms", type=float, default=1)
    parser.add_argument("--session-seconds", type=int, default=1200)
    parser.add_argument("--cumulative-seconds", type=int, help="Declared original-plus-local-replacement allowance; each session still respects session-seconds")
    parser.add_argument("--output", default=str(ROOT / "benchmarks/delta/results"))
    parser.add_argument("--formal-case", action="append", default=[])
    parser.add_argument("--reuse-formal")
    parser.add_argument("--align-to", help="Independent-cycle failure receipt fixing both cycles to the same declared scene configuration")
    parser.add_argument("--resume")
    parser.add_argument("--precision")
    parser.add_argument("--precision-source", help="Exact archived collector for unchanged-measurement proof validation")
    parser.add_argument("--control", action="store_true", help="Capture the fixed precision controls; no performance verdict")
    parser.add_argument("--control-seconds", type=int, help="Bounded control time within the original project budget")
    parser.add_argument("--control-case", action="append", default=[], help="Predeclared failed control to replace")
    parser.add_argument("--reuse-control", help="Prior controls with identical measurement code and unaffected cases")
    parser.add_argument("--reuse-source", help="Archived collector whose digest matches the prior receipt")
    parser.add_argument("--control-failure-source", help="Complete same-identity formal noise receipt justifying scoped recalibration")
    parser.add_argument("--extra-controls", help="Frozen JSON list of explicitly authorized additional control cases")
    parser.add_argument("--targets", help="Frozen JSON map of declared case durations in milliseconds")
    parser.add_argument("--minimum-calls", help="Frozen common minimum invocations for full-work GC-sensitive cases")
    parser.add_argument("--partition", help="Predeclared JSON scene partition; each scene retains its complete actual process cohort")
    args = parser.parse_args()
    explicit_cases = bool(args.case)
    if args.baseline_env is None:
        args.baseline_env = str(ROOT / (".local/delta/optimization-20261011/candidate-env" if args.revision
                                       else ".local/delta/documentation-env"))
    global REVISION, SUITE, ROLES, ORDERS, LABELS, PRECISION_CASES, PROTOCOL, FULL_IDS
    REVISION, SUITE = args.revision, args.suite
    if SUITE != "legacy" and not REVISION:
        raise ValueError("New suites require the revision contract")
    if REVISION:
        PROTOCOL = "delta-revision-three-v1" if SUITE == "legacy" else "delta-revision-two-v1"
        mapping = json.loads(SELF.with_name("revision-cases.json").read_text())
        if SUITE == "legacy":
            groups = json.loads(SELF.with_name("cases.json").read_text())["groups"]
            FULL_IDS = {x for values in groups.values() for x in values} - set(mapping["legacy_excluded"])
        else:
            ROLES, LABELS = ("old", "new"), ("current",)
            selected_groups = ["T1"] if SUITE == "template" else mapping["formal_suites"][SUITE]
            FULL_IDS = {x for group in selected_groups for x in mapping["groups"][group]}
            PRECISION_CASES = tuple(x for group in selected_groups for x in mapping["groups"][group])
        ORDERS = tuple(itertools.permutations(ROLES))
        if not args.case:
            if SUITE == "legacy" and args.group != "all":
                selected = {x for group in args.group.split(",") for x in groups.get(group, [])}
                args.case = sorted(selected & FULL_IDS)
                if not args.case:
                    raise ValueError("Unknown or empty revision workload group")
            else:
                args.case = sorted(FULL_IDS)
        elif not set(args.case) <= FULL_IDS:
            raise ValueError("Cases differ from this revision suite")
        if args.control_multiplier == 2 and SUITE != "bulk":
            raise ValueError("Only predeclared full bulk work may use twofold control")
    if not 1 <= args.session_seconds <= 1200 or not 1 <= args.short_ms <= 10:
        raise ValueError("Out-of-contract session or short-batch target")
    args.case_targets = json.loads(Path(args.targets).read_text()) if args.targets else {}
    all_ids = FULL_IDS if REVISION else {identifier for identifiers in json.loads(SELF.with_name("cases.json").read_text())["groups"].values() for identifier in identifiers}
    if not isinstance(args.case_targets, dict) or any(identifier not in all_ids or type(value) not in (int, float)
                                                     or not 1 <= value <= 10 for identifier, value in args.case_targets.items()):
        raise ValueError("Invalid declared case duration map")
    args.extra_cases = json.loads(Path(args.extra_controls).read_text()) if args.extra_controls else []
    args.case_min_counts = json.loads(Path(args.minimum_calls).read_text()) if args.minimum_calls else {}
    if not isinstance(args.case_min_counts, dict) or any(key not in all_ids or type(value) is not int or not 1 <= value <= 100_000_000 for key, value in args.case_min_counts.items()):
        raise ValueError("Invalid frozen common invocation minimum")
    allowed_extra = all_ids - set(PRECISION_CASES)
    if (not isinstance(args.extra_cases, list) or len(set(args.extra_cases)) != len(args.extra_cases)
            or not set(args.extra_cases) <= allowed_extra):
        raise ValueError("Additional controls differ from the approved bounded scope")
    if args.control_seconds is not None and not 1 <= args.control_seconds <= 1200:
        raise ValueError("Out-of-contract control session bound")
    args.partition_cases = json.loads(Path(args.partition).read_text()) if args.partition else []
    if args.partition_cases:
        scope = set(PRECISION_CASES) | set(args.extra_cases) if args.control else all_ids
        if (args.mode != "formal" or explicit_cases or args.group != "all" or args.resume
                or args.reuse_formal or args.reuse_control or args.formal_case or args.control_case
                or args.width or not isinstance(args.partition_cases, list)
                or len(set(args.partition_cases)) != len(args.partition_cases)
                or not set(args.partition_cases) <= scope):
            raise ValueError("Planned partition must preserve full identity, bounds and complete scene cohorts")
    if args.formal_case and (args.mode != "formal" or args.control or explicit_cases or args.group != "all"
                             or not args.precision or not args.reuse_formal or not args.reuse_source or args.resume):
        raise ValueError("Local formal replacement requires full identity and its original source/receipt")
    # A scoped remainder may be shorter than the physical session ceiling.
    # collect still subtracts actual inherited elapsed time and uses the smaller
    # deadline, so this permits a tighter budget rather than extending one.
    if args.cumulative_seconds is not None and (not args.formal_case or not 1 <= args.cumulative_seconds <= 2700):
        raise ValueError("Cumulative bound requires a declared scoped formal replacement")
    if args.control_failure_source and not (args.control and args.control_case and args.reuse_control and args.reuse_source):
        raise ValueError("Formal noise justification requires a scoped control with original provenance")
    precision_control(args) if args.control else collect(args)


if __name__ == "__main__":
    main()
