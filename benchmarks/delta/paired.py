"""Bounded, atomic pairs for the fixed Delta workload; no third implementation."""
from collections import Counter, deque
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

PROTOCOL = "paired-short-v2"
RULES = {"minimum_ns": 200_000, "cpu_gap": .10, "boundary_fraction": .01,
         "clock_fraction": .005, "span_ns": 250_000_000, "load_per_cpu": .8,
         "memory_fraction": .03, "cpu_min_ticks": 10, "busy_fraction": .75,
         "max_attempts_per_case": 120, "max_cumulative_seconds": 600,
         "pair_noise": .05, "backoff_seconds": 1, "warmup_target_ms": .25}


class Host:
    """Read-only Mach counters, SDK constants; heavy identity reads happen once."""
    def __init__(self):
        if sys.platform != "darwin" or platform.machine() != "arm64":
            raise ValueError("Short first-release acceptance requires macOS arm64")
        self.lib = ctypes.CDLL(None)
        self.lib.mach_host_self.argtypes = []
        self.lib.mach_host_self.restype = ctypes.c_uint
        for name in ("host_statistics", "host_statistics64"):
            fn = getattr(self.lib, name)
            fn.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_void_p,
                           ctypes.POINTER(ctypes.c_uint)]
            fn.restype = ctypes.c_int
        self.port = self.lib.mach_host_self()
        identity = subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", "hw.memsize", "hw.model", "machdep.cpu.brand_string"],
            text=True, timeout=5).splitlines()
        self.memory = int(identity[0])
        self.cpus = os.cpu_count()
        self.page = os.sysconf("SC_PAGE_SIZE")
        overhead = []
        for _ in range(500):
            start = time.perf_counter_ns()
            time.thread_time_ns()
            overhead.append(time.perf_counter_ns()-start)
        self.info = {"memory_bytes": self.memory, "model": identity[1], "cpu": identity[2],
                     "logical_cpus": self.cpus, "page_bytes": self.page,
                     "wall_clock": vars(time.get_clock_info("perf_counter")),
                     "thread_clock": vars(time.get_clock_info("thread_time")),
                     "clock_read_p99_ns": sorted(overhead)[494],
                     "memory_definition": "free+inactive pages; speculative already included in free"}
        self.cached = None
        self.refresh_at = 0

    def stats(self, flavor, size, wide=False):
        buf = (ctypes.c_uint * size)()
        count = ctypes.c_uint(size)
        fn = self.lib.host_statistics64 if wide else self.lib.host_statistics
        status = fn(self.port, flavor, buf, ctypes.byref(count))
        if status or count.value < 4:
            raise RuntimeError(f"Mach snapshot failed: {flavor}/{status}/{count.value}")
        return list(buf)[:count.value]

    def snapshot(self):
        start = time.perf_counter_ns()
        if start >= self.refresh_at:
            vm = self.stats(4, 256, True)  # SDK HOST_VM_INFO64; prefix is four uint32.
            self.cached = {"memory_fraction": (vm[0]+vm[2])*self.page/self.memory,
                           "load_per_cpu": os.getloadavg()[0]/self.cpus,
                           "refresh_ns": start}
            self.refresh_at = start + 1_000_000_000
        ticks = self.stats(3, 4)  # SDK HOST_CPU_LOAD_INFO: user, system, idle, nice.
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {**self.cached, "ticks": ticks, "start_ns": start,
                "end_ns": time.perf_counter_ns(), "involuntary_switches": usage.ru_nivcsw}


def sample(fn, count, warmup):
    start = time.perf_counter_ns()
    for _ in range(warmup):
        fn()
    warm_elapsed = time.perf_counter_ns()-start
    outer_start = time.perf_counter_ns()
    cpu_start = time.thread_time_ns()
    start = time.perf_counter_ns()
    for _ in range(count):
        fn()
    end = time.perf_counter_ns()
    cpu_end = time.thread_time_ns()
    outer_end = time.perf_counter_ns()
    elapsed = end-start
    return {"count": count, "elapsed_ns": elapsed, "cpu_elapsed_ns": cpu_end-cpu_start,
            "ns_per_call": elapsed/count, "boundary_ns": start-outer_start+outer_end-end,
            "start_ns": start, "end_ns": end, "warmup_count": warmup,
            "warmup_elapsed_ns": warm_elapsed}


def reasons(pair, info):
    failed = []
    resolution = max(info[clock]["resolution"]*1e9 for clock in ("wall_clock", "thread_clock"))
    for name, batch in pair["batches"].items():
        wall, cpu = batch["elapsed_ns"], batch["cpu_elapsed_ns"]
        if wall < RULES["minimum_ns"]:
            failed.append(name+":short")
        if wall <= 0 or cpu <= 0 or not math.isfinite(batch["ns_per_call"]):
            failed.append(name+":clock")
            continue
        if abs(wall-cpu)/wall > RULES["cpu_gap"]:
            failed.append(name+":cpu-gap")
        if batch["boundary_ns"]/wall > RULES["boundary_fraction"]:
            failed.append(name+":boundary")
        if max(resolution, info["clock_read_p99_ns"])/wall > RULES["clock_fraction"]:
            failed.append(name+":clock-precision")
        if batch["count"] != pair["count"]:
            failed.append(name+":count")
    before, after = pair["before"], pair["after"]
    if not (before["start_ns"] <= before["end_ns"] <= pair["start_ns"] <= pair["end_ns"]
            <= after["start_ns"] <= after["end_ns"]):
        failed.append("snapshot-boundary")
    if pair["end_ns"]-pair["start_ns"] > RULES["span_ns"]:
        failed.append("pair-span")
    for snap in (before, after):
        if snap["load_per_cpu"] > RULES["load_per_cpu"]:
            failed.append("load")
        if snap["memory_fraction"] < RULES["memory_fraction"]:
            failed.append("memory")
    delta = [(b-a) & 0xffffffff for a,b in zip(before["ticks"], after["ticks"])]
    ticks = sum(delta)
    pair["host_cpu"] = {"ticks": ticks, "busy_fraction": (ticks-delta[2])/ticks if ticks else None,
                        "used_as_gate": ticks >= RULES["cpu_min_ticks"]}
    if ticks >= RULES["cpu_min_ticks"] and pair["host_cpu"]["busy_fraction"] > RULES["busy_fraction"]:
        failed.append("host-busy")
    return sorted(set(failed))


def measure_pair(contexts, request, host):
    count, warmup = request["count"], request["warmup_count"]
    if type(count) is not int or not 1 <= count <= 100_000_000:
        raise ValueError("Invalid shared invocation count")
    if type(warmup) is not int or not 0 <= warmup <= 100_000_000:
        raise ValueError("Invalid warmup count")
    order = request["order"]
    if order not in (["reference", "candidate"], ["candidate", "reference"]):
        raise ValueError("A pair must contain both engines exactly once")
    before = host.snapshot()
    start = time.perf_counter_ns()
    batches = {}
    for name in order:
        package = "cytimes" if name == "reference" else "rstimes"
        shared, cases, _ = contexts[package]
        sys.modules["delta_cases"] = shared
        batches[name] = sample(cases[request["id"]].run, count, warmup)
    end = time.perf_counter_ns()
    after = host.snapshot()
    pair = {"count": count, "order": order, "start_ns": start, "end_ns": end,
            "before": before, "after": after, "batches": batches}
    pair["reasons"] = reasons(pair, host.info)
    pair["valid"] = not pair["reasons"]
    return pair


def blocks(state):
    width = state.get("pairs_per_block", 1)
    accepted = state["accepted"]
    groups = []
    for start in range(0, len(accepted)-width+1, width):
        micro = accepted[start:start+width]
        batch = {}
        for name in ("reference", "candidate"):
            count = sum(p["batches"][name]["count"] for p in micro)
            elapsed = sum(p["batches"][name]["elapsed_ns"] for p in micro)
            batch[name] = {"count": count, "elapsed_ns": elapsed, "ns_per_call": elapsed/count,
                           "cpu_elapsed_ns": sum(p["batches"][name]["cpu_elapsed_ns"] for p in micro)}
        groups.append({"batches": batch, "valid": all(p["valid"] for p in micro),
                       "order": micro[0]["order"], "micro_pairs": micro})
    return groups


def row(case, state):
    pairs = blocks(state)
    if not pairs:
        return {**case, "count": state.get("count"), "status": "inconclusive",
                "attempts": len(state["attempts"]), "pairs": []}
    batches = {name: [p["batches"][name] for p in pairs] for name in ("reference", "candidate")}
    med = {name: statistics.median(b["ns_per_call"] for b in values) for name,values in batches.items()}
    ratios = [p["batches"]["reference"]["ns_per_call"]/p["batches"]["candidate"]["ns_per_call"] for p in pairs]
    ratio = statistics.median(ratios)
    noise = max(abs(r/ratio-1) for r in ratios)
    return {**case, "count": state["count"], "reference_ns": med["reference"], "candidate_ns": med["candidate"],
            "speed_ratio": med["reference"]/med["candidate"], "paired_median_ratio": ratio,
            "conservative_ratio": min(ratios), "conservative_candidate_ratio": 1/min(ratios),
            "max_noise": noise, "batches": batches, "pairs": pairs, "attempts": len(state["attempts"]),
            "status": "measured" if len(pairs) == state["required"] else "inconclusive"}


def evaluate(rows, summary, expected, mode, precision):
    complete = {r["id"] for r in rows} == set(expected) and all(r["status"] == "measured" for r in rows)
    core, third = summary.get("core"), summary.get("thirdparty")
    formal = mode == "formal"
    gates = {"P1": bool(core and core["median_ratio"] >= 1.25),
             "P2": complete and all(r["candidate_ns"] <= 1.1*r["reference_ns"] for r in rows),
             "P3": bool(third and third["median_ratio"] >= 1), "P4": True,
             "P5": formal and complete and precision and all(len(r["pairs"]) == 12
                    and sum(p["order"][0] == "reference" for p in r["pairs"]) == 6
                    and all(p["valid"] for p in r["pairs"]) for r in rows),
             "P6": complete and all(r["max_noise"] <= .05 and r["conservative_candidate_ratio"] <= 1.1 for r in rows)
                    and bool(core and core["conservative_ratio"] >= 1.25)
                    and bool(third and third["conservative_ratio"] >= 1)}
    all_inputs = len(expected) == 93 and {r["group"] for r in rows} == {f"B{i}" for i in range(1,10)}
    return {"formal_acceptance": formal and all_inputs and all(gates.values()), "all_groups": all_inputs,
            "gates": gates, "incomplete": [r["id"] for r in rows if r["status"] != "measured"],
            "unstable": [r["id"] for r in rows if r.get("max_noise", 0) > .05],
            "regressions": [r["id"] for r in rows if r.get("candidate_ns", 0) > 1.1*r.get("reference_ns", math.inf)]}


def fingerprint(result):
    keys = ("protocol", "reference", "candidate", "hardware", "sampling", "helper_sha256")
    return hashlib.sha256(json.dumps({k:result[k] for k in keys}, sort_keys=True).encode()).hexdigest()


def precision_binding(result):
    hardware = dict(result["hardware"])
    hardware.pop("clock_read_p99_ns", None)
    value = {"hardware": hardware, "helper_sha256": result["helper_sha256"],
             "target_ms": result["sampling"]["target_ms"], "rules": RULES}
    for name in ("reference", "candidate"):
        value[name] = {k:result[name][k] for k in ("environment", "inputs_sha256", "manifest_sha256", "runner_sha256")}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def checkpoint(result, states, cases, bench, directory, started, inherited):
    rows = [row(case, states[case["id"]]) for case in cases]
    measured = [r for r in rows if r.get("reference_ns")]
    summary = bench.aggregates(measured) if measured else {"groups": {}, "core": None, "thirdparty": None}
    result.update(states=states, measurements=rows, aggregates=summary,
                  elapsed_seconds=inherited+time.monotonic()-started)
    result["acceptance"] = evaluate(rows, summary, [c["id"] for c in cases], result["mode"], result["precision_verified"])
    result["rejected_reasons"] = dict(Counter(reason for state in states.values() for p in state["attempts"]
                                              for reason in p["reasons"]))
    attempts = [p for s in states.values() for p in s["attempts"]]
    result["sampling_counts"] = {"attempted": len(attempts), "accepted": sum(p["valid"] for p in attempts),
                                  "rejected": sum(not p["valid"] for p in attempts)}
    result["side_rejections"] = {name: sum(any(r.startswith(name+":") for r in p["reasons"]) for p in attempts)
                                 for name in ("reference", "candidate")}
    temp = directory/"raw.tmp"
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    temp.replace(directory/"raw.json")


def run(args, bench):
    started = time.monotonic()
    required = 12 if args.mode == "formal" else 6
    directory = Path(args.output)/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory.mkdir(parents=True, exist_ok=False)
    oracle = bench.Process(args.oracle_env, "cytimes", args.group, args.case, 0, args.measurement_qos)
    paired = None
    try:
        paired = bench.Process(args.candidate_env, "paired", args.group, args.case, 0, args.measurement_qos)
        ref, cand = paired.metadata["cytimes"], paired.metadata["rstimes"]
        old, new = dict(oracle.metadata["environment"]), dict(ref["environment"])
        for key in ("package_file", "process_model"):
            old.pop(key, None); new.pop(key, None)
        if old != new or bench.comparable(oracle.metadata) != bench.comparable(ref):
            raise ValueError("Shared reference does not match frozen oracle")
        if ref["cases"] != cand["cases"] or bench.comparable(ref) != bench.comparable(cand):
            raise ValueError("Refusing to time unequal workload outputs")
        oracle.close()
        hardware = paired.short_info()
        result = {"protocol": PROTOCOL, "mode": args.mode, "reference": ref, "candidate": cand,
                  "hardware": hardware, "helper_sha256": bench.digest(__file__), "cached_reference": False,
                  "sampling": {**RULES, "target_ms": args.short_ms, "required_pairs": required,
                               "pairs_per_block": args.pairs_per_block,
                               "queue_policy": "finish-case; defer only invalid pairs",
                               "max_attempts_per_case": max(120, required*args.pairs_per_block*3),
                               "session_budget_seconds": args.session_seconds, "process_model": "shared-thread"},
                  "frozen_oracle_verification": {"native_matches": True, "environment_matches": True,
                                                 "selected_outputs_match": True}, "precision_verified": False}
        # Timing overhead is diagnostic and changes at process startup; hardware
        # identity and configured clocks remain strict continuation requirements.
        result["hardware"]["clock_read_p99_ns"] = hardware["clock_read_p99_ns"]
        states = {c["id"]: {"accepted": [], "attempts": [], "calibration": [], "required": required,
                           "pairs_per_block": args.pairs_per_block} for c in ref["cases"]}
        inherited = 0
        if args.resume:
            previous = json.loads(Path(args.resume).read_text())
            lhs, rhs = json.loads(json.dumps(previous)), json.loads(json.dumps(result))
            for obj in (lhs, rhs):
                obj["hardware"].pop("clock_read_p99_ns", None)
            if fingerprint(lhs) != fingerprint(rhs):
                raise ValueError("Resume differs in code, inputs, environment, hardware or sampling configuration")
            states, inherited = previous["states"], previous["elapsed_seconds"]
            journal = Path(args.resume).parent/"attempts.jsonl"
            if journal.is_file():
                for line in journal.read_text().splitlines():
                    record = json.loads(line)
                    state = states[record["id"]]
                    if record["index"] > len(state["attempts"]):
                        if "count" not in state:
                            state.update(record["calibration_state"])
                        state["attempts"].append(record["pair"])
                        if record["pair"]["valid"]:
                            state["accepted"].append(record["pair"])
                    inherited = max(inherited, record["elapsed_seconds"])
            result["resumed_from"] = str(Path(args.resume).resolve())
        if args.precision_evidence:
            evidence = json.loads(Path(args.precision_evidence).read_text())
            result["precision_verified"] = bool(evidence.get("passed") and evidence.get("protocol") == PROTOCOL
                and evidence.get("target_ms") == args.short_ms and evidence.get("runner_sha256") == bench.digest(bench.SELF)
                and evidence.get("helper_sha256") == bench.digest(__file__)
                and evidence.get("native_sha256") == cand["environment"]["native_sha256"]
                and evidence.get("inputs_sha256") == cand["inputs_sha256"]
                and evidence.get("binding_sha256") == precision_binding(result))
            if not result["precision_verified"]:
                raise ValueError("Precision evidence does not match this build/protocol")
            result["precision_evidence"] = str(Path(args.precision_evidence).resolve())
        deadline = started+args.session_seconds-inherited
        needed = required*args.pairs_per_block
        queue = deque(c["id"] for c in ref["cases"] if len(states[c["id"]]["accepted"]) < needed)
        next_ready = {}
        checkpoint(result, states, ref["cases"], bench, directory, started, inherited)
        next_progress = time.monotonic()+30
        while queue and time.monotonic() < deadline:
            identifier = queue.popleft()
            state = states[identifier]
            if len(state["attempts"]) >= result["sampling"]["max_attempts_per_case"]:
                continue
            if time.monotonic() < next_ready.get(identifier, 0):
                queue.append(identifier)
                time.sleep(min(.01, max(0, deadline-time.monotonic())))
                continue
            if "count" not in state:
                count = 2000
                for _ in range(4):
                    pilot = paired.pair(identifier, count, ["reference", "candidate"], count)
                    state["calibration"].append(pilot)
                    per_call = min(b["cpu_elapsed_ns"]/b["count"] for b in pilot["batches"].values())
                    proposed = max(1, math.ceil(args.short_ms*1e6/per_call))
                    if count >= proposed*.8:
                        break
                    count = min(100_000_000, proposed)
                state["count"] = min(100_000_000, proposed)
                state["warmup_count"] = max(1, math.ceil(RULES["warmup_target_ms"]*1e6/per_call))
            index = len(state["accepted"])
            block_index, within_block = divmod(index, args.pairs_per_block)
            order = ["reference", "candidate"] if (block_index+within_block)%2 == 0 else ["candidate", "reference"]
            attempt = paired.pair(identifier, state["count"], order, state["warmup_count"])
            state["attempts"].append(attempt)
            with (directory/"attempts.jsonl").open("a") as journal:
                journal.write(json.dumps({"id": identifier, "index": len(state["attempts"]), "pair": attempt,
                    "elapsed_seconds": inherited+time.monotonic()-started,
                    "calibration_state": {k:state[k] for k in ("count", "warmup_count", "calibration")}
                    if len(state["attempts"]) == 1 else {}})+"\n")
            if attempt["valid"]:
                state["accepted"].append(attempt)
            else:
                next_ready[identifier] = time.monotonic()+RULES["backoff_seconds"]
            if len(state["accepted"]) < needed:
                if attempt["valid"]:
                    queue.appendleft(identifier)
                else:
                    queue.append(identifier)
            if time.monotonic() >= next_progress:
                print(json.dumps({"sampling_progress": {"accepted": sum(len(s["accepted"]) for s in states.values()),
                    "required": len(states)*needed, "elapsed_seconds": inherited+time.monotonic()-started}}), flush=True)
                next_progress = time.monotonic()+30
        result["stop_reason"] = ("complete" if all(len(s["accepted"]) >= needed for s in states.values())
                                 else "attempt-cap" if not queue else "budget")
        checkpoint(result, states, ref["cases"], bench, directory, started, inherited)
        # Reuse the common human/CSV report; keep the incremental raw receipt.
        bench.save(result, args.output, existing_directory=directory)
        print(json.dumps({"directory": str(directory), "elapsed_seconds": result["elapsed_seconds"],
                          "core": result["aggregates"]["core"], "thirdparty": result["aggregates"]["thirdparty"],
                          "acceptance": result["acceptance"], "rejected": result["rejected_reasons"]}, ensure_ascii=False))
    finally:
        original_error = sys.exc_info()[0]
        for process in (oracle, paired):
            if process is not None:
                try:
                    process.close()
                except Exception:
                    if original_error is None:
                        raise
