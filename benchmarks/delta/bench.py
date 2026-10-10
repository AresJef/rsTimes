"""Fixed Python-call workloads, reusable quick baselines and fresh formal pairs."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import platform
import selectors
import statistics
import subprocess
import sys
import sysconfig
import time

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "tests/delta/cases.py"
MANIFEST = Path(__file__).with_name("cases.json")
SELF = Path(__file__).resolve()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases():
    spec = importlib.util.spec_from_file_location("delta_cases", SHARED)
    module = importlib.util.module_from_spec(spec)
    sys.modules["delta_cases"] = module
    spec.loader.exec_module(module)
    return module


def measurement_qos(policy="initiated"):
    """Give only our paired worker threads the same macOS scheduling class."""
    if sys.platform != "darwin":
        return {"policy": "platform default"}
    import ctypes
    library = ctypes.CDLL(None)
    library.pthread_self.argtypes = []
    library.pthread_self.restype = ctypes.c_void_p
    library.pthread_set_qos_class_self_np.argtypes = [ctypes.c_uint, ctypes.c_int]
    library.pthread_set_qos_class_self_np.restype = ctypes.c_int
    library.pthread_get_qos_class_np.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_int)]
    library.pthread_get_qos_class_np.restype = ctypes.c_int
    # Verified in this SDK's sys/qos.h. Apple's API changes only this thread;
    # unrelated processes are neither suspended nor reprioritized.
    expected = 0x21 if policy == "interactive" else 0x19  # SDK sys/qos.h values
    status = library.pthread_set_qos_class_self_np(expected, 0)
    actual = ctypes.c_uint()
    relative = ctypes.c_int()
    read_status = library.pthread_get_qos_class_np(library.pthread_self(), ctypes.byref(actual), ctypes.byref(relative))
    if status or read_status or actual.value != expected or relative.value != 0:
        raise RuntimeError(f"Cannot apply identical measurement QoS: {status}, {read_status}, {actual.value}, {relative.value}")
    return {"policy": "QOS_CLASS_USER_INTERACTIVE" if policy == "interactive" else "QOS_CLASS_USER_INITIATED",
            "class": actual.value, "relative_priority": relative.value}


def observe(shared, case, Delta):
    # D2 permits different pickle bytes. Validate the restored object and its
    # dictionary before timing the original write/read/copy callable.
    if case.group != "B9":
        return shared.observe(case, Delta)
    import pickle
    value = case.run()
    size = len(value) if isinstance(value, bytes) else None
    if isinstance(value, bytes):
        value = pickle.loads(value)
    return {"case": case.id, "requirements": case.requirements, "difference": None,
            "result": {"object": shared.pack(value, Delta), "dictionary": getattr(value, "__dict__", None)},
            "pickle_size": size}


def workloads(package, groups, selected_ids, qos, process_model, warmup_ms):
    manifest = json.loads(MANIFEST.read_text())
    known = manifest["groups"]
    chosen = list(known) if groups == "all" else groups.split(",")
    if not set(chosen) <= known.keys() or len(set(chosen)) != len(chosen):
        raise ValueError("Unknown or repeated benchmark groups")
    identifiers = [identifier for group in chosen for identifier in known[group]]
    if selected_ids:
        if len(set(selected_ids)) != len(selected_ids) or not set(selected_ids) <= set(identifiers):
            raise ValueError("Unknown or repeated selected workload")
        identifiers = [identifier for identifier in identifiers if identifier in selected_ids]
    shared = load_cases()
    Delta, cases = shared.benchmark_cases(package)
    lookup = {case.id: case for case in cases}
    if len(lookup) != len(cases) or any(identifier not in lookup for identifier in identifiers):
        raise ValueError("Duplicate or missing fixed workload")
    selected = [lookup[identifier] for identifier in identifiers]
    if any(case.group != group for group in chosen for case in selected if case.id in known[group]):
        raise ValueError("Workload group differs from the locked manifest")
    dependencies = ("numpy", "pandas", "cytimes", "python-dateutil", "tzdata", "pendulum", "babel", "typing-extensions")
    env = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
           "measurement_qos": qos, "process_model": process_model, "warmup_ms": warmup_ms,
           "gil_disabled_build": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
           "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
           "dependencies": {name: importlib.metadata.version(name) for name in dependencies},
           "package_file": sys.modules[package].__file__}
    native = sys.modules["rstimes._native"] if package == "rstimes" else sys.modules["cytimes.delta"]
    env["native_sha256"] = digest(native.__file__)
    if package == "rstimes":
        env["release_build"] = native.release_build()
        if not env["release_build"]:
            raise ValueError("Performance must use an installed release extension")
    metadata = {"environment": env, "inputs_sha256": digest(SHARED), "manifest_sha256": digest(MANIFEST),
                "runner_sha256": digest(SELF), "cases": [{"id": c.id, "group": c.group} for c in selected],
                "observations": [observe(shared, case, Delta) for case in selected]}
    return shared, lookup, metadata


def worker(package, groups, selected_ids, warmup_ms, qos_policy):
    qos = measurement_qos(qos_policy)
    names = ("cytimes", "rstimes") if package == "paired" else (package,)
    model = "shared-thread" if package == "paired" else "separate-process"
    contexts = {name: workloads(name, groups, selected_ids, qos, model, warmup_ms) for name in names}
    metadata = {name: context[2] for name, context in contexts.items()}
    print(json.dumps(metadata if package == "paired" else metadata[package]), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        count = request["count"]
        if not isinstance(count, int) or not 1 <= count <= 100_000_000:
            raise ValueError("Invalid benchmark invocation count")
        active = request.get("package", package)
        shared, lookup, _ = contexts[active]
        # Both case modules retain their own globals but use the original
        # pickle path. Switch it outside the timed loop so Child never resolves
        # to the other engine's class. The callable and input remain unchanged.
        sys.modules["delta_cases"] = shared
        fn = lookup[request["id"]].run
        warmup_count = request.get("warmup_count", 0)
        if not isinstance(warmup_count, int) or not 0 <= warmup_count <= 100_000_000:
            raise ValueError("Invalid benchmark warmup count")
        warmup_start = time.perf_counter_ns()
        for _ in range(warmup_count):
            fn()
        warmup_elapsed = time.perf_counter_ns() - warmup_start
        cpu_start = time.thread_time_ns()
        start = time.perf_counter_ns()
        for _ in range(count):
            fn()
        elapsed = time.perf_counter_ns() - start
        cpu_elapsed = time.thread_time_ns() - cpu_start
        # CPU time diagnoses interruptions only. Acceptance still uses complete
        # wall time; no pauses or loop overhead are subtracted from results.
        print(json.dumps({"elapsed_ns": elapsed, "cpu_elapsed_ns": cpu_elapsed,
                          "count": count, "ns_per_call": elapsed/count,
                          "warmup_count": warmup_count, "warmup_elapsed_ns": warmup_elapsed}), flush=True)


class Process:
    def __init__(self, env, package, groups, selected_ids=(), warmup_ms=0, qos_policy="initiated"):
        interpreter = Path(env).resolve() / "bin/python"
        command = [str(interpreter), "-I", str(SELF), "--worker", package, "--group", groups,
                   "--warmup-ms", str(warmup_ms), "--measurement-qos", qos_policy]
        for identifier in selected_ids:
            command.extend(("--case", identifier))
        self.process = subprocess.Popen(command,
                                        text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            self.metadata = self.read()
        except BaseException:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=10)
            self.selector.close()
            raise

    def read(self):
        if not self.selector.select(timeout=30):
            self.process.kill()
            raise TimeoutError("Benchmark worker did not answer within 30 seconds")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(self.process.stderr.read())
        return json.loads(line)

    def measure(self, identifier, count, warmup_count=0, package=None):
        request = {"id": identifier, "count": count, "warmup_count": warmup_count}
        if package is not None:
            request["package"] = package
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        return self.read()

    def close(self):
        self.selector.close()
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.process.returncode:
            raise RuntimeError(self.process.stderr.read())



class PairedSide:
    """Two engine views of one isolated worker and its one measuring thread."""
    def __init__(self, process, package):
        self.transport = process
        self.package = package
        self.metadata = process.metadata[package]

    def measure(self, identifier, count, warmup_count=0):
        return self.transport.measure(identifier, count, warmup_count, self.package)

    def close(self):
        pass  # The shared transport is closed once by main's finally block.


def comparable(metadata):
    copy = json.loads(json.dumps(metadata))
    # Byte representations differ under D2; restored fields/dictionaries must match.
    for observation in copy["observations"]:
        observation.pop("pickle_size", None)
    return copy["observations"]


def reference_key(metadata):
    return {key: metadata[key] for key in ("environment", "inputs_sha256", "manifest_sha256", "runner_sha256", "cases")}


def same_workload(previous, current):
    for key in ("inputs_sha256", "manifest_sha256", "runner_sha256", "cases"):
        if previous["reference"].get(key) != current["reference"].get(key):
            raise ValueError(f"Previous run differs in {key}; cannot compare")
    if previous["reference"]["environment"] != current["reference"]["environment"]:
        raise ValueError("Previous reference environment differs")
    old = dict(previous["candidate"]["environment"])
    new = dict(current["candidate"]["environment"])
    old.pop("native_sha256", None)
    new.pop("native_sha256", None)
    if old != new:
        raise ValueError("Previous candidate interpreter/dependencies differ")


def aggregates(rows):
    def geometric(values):
        return math.exp(statistics.mean(math.log(value) for value in values))
    groups = {}
    for group in sorted({r["group"] for r in rows}):
        selected = [r for r in rows if r["group"] == group]
        groups[group] = {"median_ratio": geometric([r["speed_ratio"] for r in selected]),
                         "conservative_ratio": geometric([r["conservative_ratio"] for r in selected])}
    core = [f"B{i}" for i in range(1, 7)]
    third = ["B7", "B8"]
    result = {"groups": groups}
    for label, selected in (("core", core), ("thirdparty", third)):
        result[label] = {field: geometric([groups[g][field] for g in selected]) for field in
                         ("median_ratio", "conservative_ratio")} if set(selected) <= groups.keys() else None
    return result


def acceptance(rows, summary, mode):
    if mode != "formal":
        return {"formal_acceptance": False, "reason": "quick development comparison"}
    complete = set(summary["groups"]) == {f"B{i}" for i in range(1, 10)}
    core, third = summary["core"], summary["thirdparty"]
    gates = {"P1": bool(core and core["median_ratio"] >= 1.25),
             "P2": all(r["candidate_ns"] <= r["reference_ns"]*1.10 for r in rows),
             "P3": bool(third and third["median_ratio"] >= 1.00),
             "P4": True,
             "P5": all(len(r["batches"]["reference"]) == len(r["batches"]["candidate"]) == 7
                       and all(b["elapsed_ns"] >= 100_000_000 and b["count"] == r["count"]
                               for batch in r["batches"].values() for b in batch) for r in rows),
             "P6": all(r["max_noise"] <= 0.05 and r["conservative_candidate_ratio"] <= 1.10 for r in rows)
                       and bool(core and core["conservative_ratio"] >= 1.25)
                       and bool(third and third["conservative_ratio"] >= 1.00)}
    return {"formal_acceptance": complete and all(gates.values()), "all_groups": complete, "gates": gates,
            "unstable": [r["id"] for r in rows if r["max_noise"] > 0.05],
            "regressions": [r["id"] for r in rows if r["candidate_ns"] > r["reference_ns"]*1.10]}


def save(result, output):
    directory = Path(output) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory.mkdir(parents=True, exist_ok=False)
    (directory/"raw.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    summary = ["# Delta 调用性能比较", "", "正式验收："+str(result["acceptance"]["formal_acceptance"]), "",
               "快速结果仅供开发比较；正式结果按原门槛判断。", "",
               "| 输入 | 原版ns | 上次候选ns | 当前候选ns | 当前速度比 | 保守速度比 | 最大波动 |",
               "| --- | --- | --- | --- | --- | --- | --- |"]
    csv = ["case,group,reference_ns,previous_candidate_ns,candidate_ns,speed_ratio,conservative_ratio,max_noise"]
    for row in result["measurements"]:
        old = row.get("previous_candidate_ns")
        summary.append(f"| {row['id']} | {row['reference_ns']:.1f} | {f'{old:.1f}' if old else '—'} | {row['candidate_ns']:.1f} | {row['speed_ratio']:.3f} | {row['conservative_ratio']:.3f} | {row['max_noise']:.1%} |")
        csv.append(f"{row['id']},{row['group']},{row['reference_ns']},{old or ''},{row['candidate_ns']},{row['speed_ratio']},{row['conservative_ratio']},{row['max_noise']}")
    summary += ["", "组合结果：", "", "```json", json.dumps(result["aggregates"], indent=2), "```", "",
                "缓存参考："+str(result["cached_reference"])+"；正式模式每次重新进行同次数交替采样。"]
    (directory/"summary.md").write_text("\n".join(summary)+"\n")
    (directory/"summary.csv").write_text("\n".join(csv)+"\n")
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("cytimes", "rstimes", "paired"))
    parser.add_argument("--mode", choices=("quick", "formal"), default="quick")
    parser.add_argument("--group", default="all")
    parser.add_argument("--case", action="append", default=[], help="Only these fixed IDs; partial runs cannot pass all-group acceptance")
    parser.add_argument("--measurement-qos", choices=("initiated", "interactive"), default="initiated", help="Same QoS for our own worker threads only")
    parser.add_argument("--paired-process", action="store_true", help="Measure both engines on one isolated thread with identical dependencies")
    parser.add_argument("--warmup-ms", type=int, help="Prewarm before each batch (0..1000ms), outside measured wall time")
    parser.add_argument("--batch-ms", type=int,
                        help="Formal target batch duration (100..5000ms); both versions share counts")
    parser.add_argument("--oracle-env", default=str(ROOT/".local/delta/oracle"))
    parser.add_argument("--candidate-env", default=str(ROOT/".local/delta/candidate"))
    parser.add_argument("--output", default=str(ROOT/"benchmarks/delta/results"))
    parser.add_argument("--previous")
    parser.add_argument("--fresh-reference", action="store_true")
    parser.add_argument("--retry-noise", help="Prior formal raw.json; one retry of unstable rows with longer batches")
    args = parser.parse_args()
    warmup_ms = args.warmup_ms if args.warmup_ms is not None else (150 if args.paired_process else 0)
    if not 0 <= warmup_ms <= 1000:
        parser.error("--warmup-ms must be 0..1000")
    if args.worker:
        worker(args.worker, args.group, args.case, warmup_ms, args.measurement_qos)
        return
    if args.batch_ms is not None and (args.mode != "formal" or not 100 <= args.batch_ms <= 5000):
        parser.error("--batch-ms requires formal mode and 100..5000ms")
    target_ms = (args.batch_ms or 160) if args.mode == "formal" else 70
    pilot_count = 20_000 if args.mode == "formal" else 2000
    started = time.monotonic()
    reference = Process(args.oracle_env, "cytimes", args.group, args.case, warmup_ms, args.measurement_qos)
    candidate = None
    paired = None
    frozen_verification = None
    try:
        if args.paired_process:
            paired = Process(args.candidate_env, "paired", args.group, args.case, warmup_ms, args.measurement_qos)
            actual_reference = PairedSide(paired, "cytimes")
            old_env, new_env = dict(reference.metadata["environment"]), dict(actual_reference.metadata["environment"])
            for key in ("package_file", "process_model"):
                old_env.pop(key, None)
                new_env.pop(key, None)
            if old_env != new_env or comparable(reference.metadata) != comparable(actual_reference.metadata):
                raise ValueError("Shared-thread reference differs from frozen oracle build/environment/results")
            frozen_verification = {"environment": reference.metadata["environment"],
                                   "inputs_sha256": reference.metadata["inputs_sha256"],
                                   "manifest_sha256": reference.metadata["manifest_sha256"],
                                   "native_matches": True, "environment_matches": True,
                                   "selected_outputs_match": True}
            reference.close()
            reference = actual_reference
            candidate = PairedSide(paired, "rstimes")
        else:
            candidate = Process(args.candidate_env, "rstimes", args.group, args.case, warmup_ms, args.measurement_qos)
        if reference.metadata["cases"] != candidate.metadata["cases"] or comparable(reference.metadata) != comparable(candidate.metadata):
            raise ValueError("Different fixed inputs/results; do not time wrong behavior")
        if reference.metadata["inputs_sha256"] != candidate.metadata["inputs_sha256"]:
            raise ValueError("Different input source fingerprints")
        key = reference_key(reference.metadata)
        key_digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
        cache = ROOT/".local/delta/benchmark-reference"/(key_digest+".json")
        cached = None
        if args.mode == "quick" and not args.fresh_reference and cache.is_file():
            stored = json.loads(cache.read_text())
            if stored["key"] != key:
                raise ValueError("Reference cache does not match; refusing reuse")
            cached = {r["id"]: r for r in stored["measurements"]}
            if any(max(abs(b["ns_per_call"]/r["reference_ns"]-1) for b in r["batches"]["reference"]) > 0.05
                   for r in cached.values()):
                cached = None  # An unstable quick baseline cannot guide an optimization.

        result = {"mode": args.mode, "reference": reference.metadata, "candidate": candidate.metadata,
                  "cached_reference": cached is not None, "reference_cache": str(cache), "noise_retry_count": 0,
                  "sampling": {"target_batch_ms": target_ms, "pilot_count": pilot_count, "warmup_ms": warmup_ms,
                               "process_model": "shared-thread" if args.paired_process else "separate-process",
                               "cpu_time": "diagnostic only; acceptance uses full wall time"}}
        if frozen_verification is not None:
            result["frozen_oracle_verification"] = frozen_verification
        previous_rows = None
        if args.previous:
            previous = json.loads(Path(args.previous).read_text())
            same_workload(previous, result)
            previous_rows = {r["id"]: r for r in previous["measurements"]}
            result["previous_run"] = str(Path(args.previous).resolve())
        retry_rows = None
        unstable = set()
        if args.retry_noise:
            prior = json.loads(Path(args.retry_noise).read_text())
            same_workload(prior, result)
            if args.mode != "formal" or prior["mode"] != "formal" or prior.get("noise_retry_count", 0) != 0:
                raise ValueError("Noise may be retried once, for formal samples only")
            if prior["candidate"]["environment"] != result["candidate"]["environment"]:
                raise ValueError("Noise retry requires the identical native build and environment")
            unstable = set(prior["acceptance"]["unstable"])
            unstable.update(r["id"] for r in prior["measurements"] if any(b["elapsed_ns"] < 100_000_000 for batches in r["batches"].values() for b in batches))
            if not unstable:
                raise ValueError("There are no unstable or short samples to retry")
            retry_rows = {r["id"]: r for r in prior["measurements"]}
            result["noise_retry_count"] = 1
            result["noise_retry"] = {"previous": str(Path(args.retry_noise).resolve()),
                                     "condition_adjustment": "Double invocation counts for unstable/short rows; reuse other valid pairs"}
        rows = []
        repeats, target = (7 if args.mode == "formal" else 3), target_ms * 1_000_000
        for case in reference.metadata["cases"]:
            identifier = case["id"]
            if retry_rows is not None and identifier not in unstable:
                rows.append(retry_rows[identifier])
                continue
            first = reference.measure(identifier, pilot_count)
            second = candidate.measure(identifier, pilot_count)
            count = max(2000, math.ceil(target/min(first["ns_per_call"], second["ns_per_call"])))
            if retry_rows is not None:
                count = max(count, retry_rows[identifier]["count"]*2)
            warmup_count = math.ceil(warmup_ms * 1_000_000 / min(first["ns_per_call"], second["ns_per_call"]))
            batches = {"reference": [], "candidate": []}
            for batch in range(repeats):
                order = (("reference", reference), ("candidate", candidate)) if batch % 2 == 0 else (("candidate", candidate), ("reference", reference))
                for name, process in order:
                    if name == "reference" and cached is not None:
                        continue
                    batches[name].append(process.measure(identifier, count, warmup_count))
            if cached is not None:
                batches["reference"] = cached[identifier]["batches"]["reference"]
            medians = {name: statistics.median(b["ns_per_call"] for b in samples) for name, samples in batches.items()}
            noise = max(abs(b["ns_per_call"]/medians[name]-1) for name, samples in batches.items() for b in samples)
            old_fast = min(b["ns_per_call"] for b in batches["reference"])
            new_slow = max(b["ns_per_call"] for b in batches["candidate"])
            row = {**case, "count": count, "reference_ns": medians["reference"], "candidate_ns": medians["candidate"],
                   "speed_ratio": medians["reference"]/medians["candidate"], "conservative_ratio": old_fast/new_slow,
                   "conservative_candidate_ratio": new_slow/old_fast, "max_noise": noise, "batches": batches}
            if previous_rows is not None:
                row["previous_candidate_ns"] = previous_rows[identifier]["candidate_ns"]
            rows.append(row)
        result.update(measurements=rows, aggregates=aggregates(rows), elapsed_seconds=time.monotonic()-started)
        result["acceptance"] = acceptance(rows, result["aggregates"], args.mode)
        reference_stable = all(max(abs(b["ns_per_call"]/r["reference_ns"]-1) for b in r["batches"]["reference"]) <= 0.05 for r in rows)
        if args.mode == "quick" and reference_stable and not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"key": key, "measurements": rows}, indent=2)+"\n")
        directory = save(result, args.output)
        print(json.dumps({"directory": str(directory), "elapsed_seconds": result["elapsed_seconds"],
                          "core": result["aggregates"]["core"], "thirdparty": result["aggregates"]["thirdparty"],
                          "acceptance": result["acceptance"]}, ensure_ascii=False))
    finally:
        reference.close()
        if candidate is not None:
            candidate.close()
        if paired is not None:
            paired.close()


if __name__ == "__main__":
    main()
