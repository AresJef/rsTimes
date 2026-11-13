"""Measure the fixed Config/parse matrix with complete paired Python calls.

Calibration is excluded from acceptance. Collect main and independent rounds
only after freezing the installed artifact, programs, inputs and row parameters.
Raw rejected groups remain in the evidence files. This is a scoped collector,
not an application benchmark framework.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROGRAMS = ("benchmarks/parser_benchmark.py", "benchmarks/parser_scenarios.py",
            "benchmarks/parser_timing.py", "benchmarks/parser_quality.py", "tests/parser/cases.py", "benchmarks/delta/bench.py")
REPRESENTATIVES = ("B03", "B12", "B17", "B28", "B31", "K01", "K05", "C01", "C05")
EVIDENCE = ROOT / "tasks/evidence/parser-rust-rewrite-20261014"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n")
    temporary.replace(path)


def prepare(installed):
    """Identify the actual packages and verify every timed public result."""
    sys.path.insert(0, str(installed.resolve()))
    from benchmarks.parser_scenarios import SCENES, build, check_outputs
    from benchmarks.parser_quality import quality, clock_bound
    from benchmarks.parser_timing import clocks, measure
    from benchmarks.delta.bench import measurement_qos
    qos=measurement_qos("initiated")
    import rstimes
    import rstimes._native as native
    import cytimes.parser as original
    assert native.release_build()
    support=json.loads((EVIDENCE/"support-identity.json").read_text())
    support_actual={}
    for name,expected in support.items():
        module=__import__(name,fromlist=["*"])
        path=Path(module.__file__).resolve()
        actual=dict(path=str(path),sha256=digest(path))
        assert actual==expected, "Frozen support module changed: "+name
        support_actual[name]=actual
    assert metadata.version("cytimes") == "3.1.0"
    identity = dict(pid=os.getpid(), executable=sys.executable, python=sys.version,
                    original_version=metadata.version("cytimes"), new_version=metadata.version("rstimes"),
                    modules={}, dependencies={name:metadata.version(name) for name in
                                             ("numpy", "pandas", "python-dateutil", "six", "tzdata", "pytz")})
    for role, module in (("A",original),("B",native)):
        path=Path(module.__file__).resolve()
        assert path.suffix == ".so"
        if role == "B": assert path.is_relative_to(installed.resolve())
        identity["modules"][role] = dict(path=str(path),sha256=digest(path))
    assert identity["modules"]["A"]["sha256"] == "b507cada977d0e0ea4f22d0f9fd34bbac117ac6c14fc807128418f44ca7b85ca"
    identity["measurement_qos"]=qos
    identity["support_modules"]=support_actual
    identity["programs"] = {name:digest(ROOT/name) for name in PROGRAMS}
    outputs=check_outputs()
    frozen=EVIDENCE/"benchmark-matrix.json"
    if frozen.exists(): assert outputs == json.loads(frozen.read_text())["scenes"]
    identity["matrix_sha256"] = hashlib.sha256(json.dumps(outputs,ensure_ascii=True,sort_keys=True).encode()).hexdigest()
    return SCENES,build,quality,clock_bound,clocks,measure,identity


def identity_key(identity):
    result = {key: identity[key] for key in
              ("python", "original_version", "new_version", "modules", "dependencies", "programs", "matrix_sha256")}
    # The isolated same-package comparison also measures the shared native
    # Pydt dependency. Keep it frozen without changing old identity schemas.
    for key in ("support_modules", "reference_dependency_version", "comparison", "measurement_qos"):
        if key in identity:
            result[key] = identity[key]
    return result


def spread(values):
    return max(values) / min(values) - 1 if values else None


def report_limits(config):
    """Read frozen statistical limits, preserving historical 3% defaults."""
    limits = dict(parse_geometry=1.50, max_time_ratio=1.05, max_spread=0.05)
    limits.update(config.get("limits", {}))
    for name, value in limits.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid frozen limit: {name}")
    return limits


def pairs(runs, n, span, count, cfg, quality, measure, deadline, stream, tag, attempt_limit=None, slot_offset=0):
    """Retry the whole pair in its original order slot, retaining slow values."""
    accepted = []
    attempt = 0
    while (len(accepted) < count and time.monotonic() < deadline
           and (attempt_limit is None or attempt < attempt_limit)):
        slot = slot_offset + len(accepted)
        order = "AB" if slot % 2 == 0 else "BA"
        start = time.perf_counter_ns()
        members = {role: measure(runs[role], n) for role in order}
        checks = {role: quality(value, cfg) for role, value in members.items()}
        duration = time.perf_counter_ns() - start
        valid = all(check["status"] == "VALID" for check in checks.values()) and duration <= span
        row = dict(tag=tag, pid=os.getpid(), slot=slot, attempt=attempt, order=order, n=n,
                   members=members, checks=checks, span_ns=duration, max_span_ns=span, valid=valid)
        if valid:
            row["R"] = members["A"]["T"] / members["B"]["T"]
            accepted.append(row)
        stream.write(json.dumps(row) + "\n")
        stream.flush()
        attempt += 1
        if any(check["status"] == "ERROR" for check in checks.values()):
            raise RuntimeError("Clock counter error; raw evidence retained")
    return accepted


def pair_summary(groups):
    if not groups:
        return dict(count=0, R=None, order_spread=None)
    order_values = {order: statistics.median(row["R"] for row in groups if row["order"] == order)
                    for order in ("AB", "BA") if any(row["order"] == order for row in groups)}
    return dict(count=len(groups), R=statistics.median(row["R"] for row in groups),
                order_spread=spread(list(order_values.values())), order_R=order_values,
                ns={role: statistics.median(row["members"][role]["T"] / row["n"] for row in groups)
                    for role in ("A", "B")})


def calibrate(args):
    limits = report_limits({})
    max_spread = 0.03
    scenes, build, quality, bound, clocks, measure, identity = prepare(args.installed)
    proof = clocks()
    cfg = {"clock_uncertainty_ns": bound(proof), "warmup_calls": 2000}
    deadline = time.monotonic() + args.minutes * 60
    rows = {}
    overrides = json.loads(args.counts.read_text()) if args.counts else {}
    args.output.mkdir(parents=True, exist_ok=True)
    write(args.output / "clock.json", proof)
    with (args.output / "calibration-groups.jsonl").open("a") as stream:
        for scene in scenes:
            runs = {role: build(role, scene)[0] for role in "AB"}
            for run in runs.values():
                run(cfg["warmup_calls"])
            n = 200
            for _ in range(4):
                preliminary = {role: measure(run, n) for role, run in runs.items()}
                fastest = min(value["T"] for value in preliminary.values())
                if fastest >= 8_000_000:
                    break
                n = max(n + 1, math.ceil(n * 10_000_000 / max(fastest, 1)))
            preliminary = {role: measure(run, n) for role, run in runs.items()}
            fastest = min(value["T"] for value in preliminary.values())
            total = sum(value["T"] for value in preliminary.values())
            # Prefer a smaller common count within the original span before
            # any extension. The 5 ms floor remains checked on both members.
            if total > 225_000_000:
                n = max(1, math.ceil(n * 7_500_000 / fastest))
            if scene.id in overrides:
                n = overrides[scene.id]
                if type(n) is not int or n < 1:
                    raise ValueError("Preflight call counts must be positive integers")
            chosen = None
            attempts = []
            tested_parameters = set()
            for scale in (1, 2, 3):
                trial_n = n * scale
                preliminary = {role: measure(run, trial_n) for role, run in runs.items()}
                total = sum(value["T"] for value in preliminary.values())
                short_span = 250_000_000
                floor_proof = None
                if total > 250_000_000:
                    fastest = min(value["T"] for value in preliminary.values())
                    floor_n = max(1, math.ceil(trial_n * 5_000_000 / fastest))
                    floor_values = {role: measure(run, floor_n) for role, run in runs.items()}
                    floor_checks = {role: quality(value, cfg) for role, value in floor_values.items()}
                    floor_proof = dict(n=floor_n, members=floor_values, checks=floor_checks)
                    floor_total = sum(value["T"] for value in floor_values.values())
                    if all(check["status"] == "VALID" for check in floor_checks.values()) and floor_total > 250_000_000:
                        short_span = max(250_000_000, math.ceil(total * 1.15 / 50_000_000) * 50_000_000)
                    else:
                        # A common-count floor that fits is tested directly;
                        # insufficient clock evidence never authorizes extension.
                        if floor_total <= 250_000_000:
                            trial_n = max(floor_n, math.floor(trial_n * 225_000_000 / max(total, 1)))
                            preliminary = {role: measure(run, trial_n) for role, run in runs.items()}
                            total = sum(value["T"] for value in preliminary.values())
                        else:
                            trial_n = floor_n
                            preliminary = floor_values
                            total = floor_total
                long_span = max(250_000_000, math.ceil(total * 3.45 / 50_000_000) * 50_000_000)
                if short_span > 1_500_000_000:
                    attempts.append(dict(scale=scale, reason="No allowed common-count pair span"))
                    continue
                parameters_key = (trial_n, short_span, long_span)
                if parameters_key in tested_parameters:
                    attempts.append(dict(scale=scale, reason="Duplicate parameters; hypothesis not repeated"))
                    continue
                tested_parameters.add(parameters_key)
                short = pairs(runs, trial_n, short_span, 12, cfg, quality, measure, deadline,
                              stream, scene.id + ":short", attempt_limit=120)
                long = pairs(runs, trial_n * 3, long_span, 6, cfg, quality, measure, deadline,
                             stream, scene.id + ":long", attempt_limit=60)
                short_result, long_result = pair_summary(short), pair_summary(long)
                difference = spread([short_result["R"], long_result["R"]]) if short and long else None
                ready = (len(short) == 12 and len(long) == 6 and difference <= max_spread
                         and short_result["order_spread"] <= max_spread and long_result["order_spread"] <= max_spread)
                trial = dict(n=trial_n, max_pair_ns=short_span, max_long_pair_ns=long_span,
                             scale=scale, short=short_result, long=long_result,
                             short_long_spread=difference, ready=ready, floor_proof=floor_proof)
                attempts.append(trial)
                if ready or (scene.group=="config" and len(short)==12 and len(long)==6):
                    # Setting speed is observational by the user's decision.
                    # Keep its precision/stability evidence even when uncertain.
                    chosen = trial
                    break
            rows[scene.id] = dict(chosen=chosen, attempts=attempts, group=scene.group)
            print("CAL", scene.id, "READY" if chosen else "INSUFFICIENT", flush=True)
            write(args.output / "provisional.json",
                  dict(identity=identity_key(identity), clock_config=cfg, rows=rows,
                       groups_per_pid=24, sweeps_per_pid=2, groups_per_sweep=12,
                       pids_per_round=9, warmup_calls=2000,
                       limits=limits,
                       purpose="Calibration only; not acceptance"))
            if time.monotonic() >= deadline:
                break
    if len(rows) != len(scenes) or any(row["chosen"] is None for row in rows.values()):
        raise RuntimeError("Preflight incomplete; do not collect formal results")
    provisional = args.output / "provisional.json"
    pilots = []
    for index in (1, 2):
        path = args.output / ("pilot-" + str(index) + ".json")
        subprocess.run([sys.executable, "-s", "-P", str(Path(__file__).resolve()),
                        "pilot", "--installed", str(args.installed), "--output", str(path),
                        "--config", str(provisional), "--minutes", "2"], check=True)
        pilots.append(json.loads(path.read_text()))
    cfg["clock_uncertainty_ns"] = max([cfg["clock_uncertainty_ns"]] +
                                      [pilot["clock_bound_ns"] for pilot in pilots])
    # Earlier controls must still qualify under the final frozen uncertainty.
    invalid_controls = []
    chosen_tags = {ident + ":" + phase: row["chosen"]["n"] * (3 if phase == "long" else 1)
                   for ident, row in rows.items() for phase in ("short", "long")}
    for line in (args.output / "calibration-groups.jsonl").read_text().splitlines():
        group = json.loads(line)
        if group["valid"] and chosen_tags.get(group["tag"]) == group["n"]:
            if any(quality(value, cfg)["status"] != "VALID" for value in group["members"].values()):
                invalid_controls.append(dict(tag=group["tag"], slot=group["slot"], attempt=group["attempt"]))
    for index in (1, 2):
        for line in (args.output / ("pilot-" + str(index) + ".jsonl")).read_text().splitlines():
            group = json.loads(line)
            if group["valid"] and any(quality(value, cfg)["status"] != "VALID"
                                      for value in group["members"].values()):
                invalid_controls.append(dict(pilot=index, tag=group["tag"], slot=group["slot"]))
    for ident, row in rows.items():
        proof = row["chosen"].get("floor_proof")
        if row["chosen"]["max_pair_ns"] > 250_000_000 and proof is not None:
            if any(quality(value, cfg)["status"] != "VALID" for value in proof["members"].values()):
                invalid_controls.append(dict(floor_proof=ident))
    issues = []
    for ident in REPRESENTATIVES:
        ratios = [rows[ident]["chosen"]["short"]["R"]] + [p["rows"][ident]["R"] for p in pilots]
        orders = [p["rows"][ident]["order_spread"] for p in pilots]
        if spread(ratios) > limits["max_spread"] or max(orders) > limits["max_spread"]:
            issues.append(dict(id=ident, process_spread=spread(ratios), pilot_order_spread=max(orders)))
    proposal = json.loads(provisional.read_text())
    proposal["clock_config"] = cfg
    proposal["pilots"] = pilots
    proposal["preflight_process_issues"] = issues
    proposal["invalid_controls_after_clock_freeze"] = invalid_controls
    # Representative pilots describe readiness and cost. Formal stability is
    # tested on the fixed three-process rounds, never inferred from pilots.
    proposal["status"] = "FROZEN_READY" if not invalid_controls and not issues else "PREFLIGHT_INSUFFICIENT"
    proposal["row_orders"] = [[scene.id for scene in scenes][offset:] +
                             [scene.id for scene in scenes][:offset] for offset in range(0, 9 * 7, 7)]
    proposal["expected_groups_per_row"] = 216
    proposal["pid_groups"] = [[0,1,2],[3,4,5],[6,7,8]]
    proposal["limits"] = limits
    proposal["preflight_identity"] = identity
    write(args.output / "frozen.json", proposal)
    if invalid_controls or issues:
        raise RuntimeError("Preflight clock or representative process stability is insufficient")


def pilot(args):
    scenes, build, quality, bound, clocks, measure, identity = prepare(args.installed)
    cfg = json.loads(args.config.read_text())
    assert identity_key(identity) == cfg["identity"]
    proof = clocks()
    quality_config = dict(cfg["clock_config"], clock_uncertainty_ns=max(bound(proof), cfg["clock_config"]["clock_uncertainty_ns"]))
    rows = {}
    deadline = time.monotonic() + args.minutes * 60
    selected = [scene for scene in scenes if scene.id in REPRESENTATIVES]
    runs_by_id = {scene.id: {role: build(role, scene)[0] for role in "AB"} for scene in selected}
    accepted = {scene.id: [] for scene in selected}
    with args.output.with_suffix(".jsonl").open("a") as stream:
        for sweep in range(2):
            for scene in (selected if sweep == 0 else reversed(selected)):
                runs = runs_by_id[scene.id]
                for run in runs.values():
                    run(cfg["warmup_calls"])
                parameters = cfg["rows"][scene.id]["chosen"]
                groups = pairs(runs, parameters["n"], parameters["max_pair_ns"], 3, quality_config,
                               quality, measure, deadline, stream, scene.id, slot_offset=sweep * 3)
                accepted[scene.id].extend(groups)
                rows[scene.id] = pair_summary(accepted[scene.id])
                assert len(groups) == 3, scene.id
    write(args.output, dict(identity=identity, clock_bound_ns=bound(proof), rows=rows))


def collect(args):
    cfg = json.loads(args.config.read_text())
    assert cfg["status"] == "FROZEN_READY"
    # All processes consume one round budget. A noisy process may use more
    # than an equal share, but no child can refresh the shared deadline.
    round_deadline = time.monotonic() + args.minutes * 60
    if args.deadline_monotonic is not None:
        round_deadline = min(round_deadline, args.deadline_monotonic)
    if args.pid_index is None:
        if args.output.exists() and any(args.output.glob("pid-*")):
            raise FileExistsError("Formal output already exists; accepted slots must not be replaced")
        args.output.mkdir(parents=True, exist_ok=True)
        process_count = cfg["pids_per_round"]
        for index in range(process_count):
            remaining = round_deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Round deadline reached; retain complete processes and gaps")
            subprocess.run([sys.executable, "-s", "-P", str(Path(__file__).resolve()),
                            "collect", "--installed", str(args.installed), "--config", str(args.config),
                            "--output", str(args.output / ("pid-" + str(index) + ".json")),
                            "--pid-index", str(index), "--minutes", str(remaining / 60),
                            "--deadline-monotonic", str(round_deadline)], check=True, timeout=remaining)
            if time.monotonic() > round_deadline:
                raise RuntimeError("Round deadline exceeded; retain completed data as incomplete")
        return
    if any(path.exists() for path in (args.output, args.output.with_suffix(".jsonl"),
                                     args.output.with_suffix(".clock.json"))):
        raise FileExistsError("Formal process output already exists; do not overwrite accepted slots")
    scenes, build, quality, bound, clocks, measure, identity = prepare(args.installed)
    assert identity_key(identity) == cfg["identity"], "Frozen identity mismatch"
    proof = clocks()
    write(args.output.with_suffix(".clock.json"), proof)
    if bound(proof) > cfg["clock_config"]["clock_uncertainty_ns"]:
        raise RuntimeError("New process clock bound exceeds frozen calibration")
    deadline = round_deadline
    rows = {}
    by_id = {scene.id: scene for scene in scenes}
    # Reuse each scene's functions and restoring Config state across sweeps.
    # Separate complete passes distribute samples over the process lifetime.
    runs_by_id = {ident: {role: build(role, by_id[ident])[0] for role in "AB"}
                  for ident in cfg["row_orders"][args.pid_index]}
    accepted = {ident: [] for ident in runs_by_id}
    target = cfg["groups_per_pid"]
    sweep_count = cfg.get("sweeps_per_pid", 1)
    per_sweep = target // sweep_count
    assert target % sweep_count == 0 and per_sweep % 2 == 0
    with args.output.with_suffix(".jsonl").open("a") as stream:
        for sweep in range(sweep_count):
            order = cfg["row_orders"][args.pid_index]
            if sweep % 2:
                order = list(reversed(order))
            for ident in order:
                runs = runs_by_id[ident]
                for run in runs.values():
                    run(cfg["warmup_calls"])
                parameters = cfg["rows"][ident]["chosen"]
                groups = pairs(runs, parameters["n"], parameters["max_pair_ns"], per_sweep,
                               cfg["clock_config"], quality, measure, deadline, stream, ident,
                               slot_offset=sweep * per_sweep)
                accepted[ident].extend(groups)
                rows[ident] = pair_summary(accepted[ident])
                write(args.output, dict(identity=identity, config_sha256=digest(args.config), rows=rows,
                                        complete=len(rows) == len(scenes) and all(row["count"] == target for row in rows.values())))
                print("COLLECT", os.getpid(), sweep, ident, len(accepted[ident]), flush=True)
                if len(groups) != per_sweep:
                    raise RuntimeError("Incomplete row; retain raw groups and report the missing coverage")


def report(args):
    cfg = json.loads(args.config.read_text())
    limits = report_limits(cfg)
    rounds = {}
    all_pids = []
    unit_failures = []
    all_unit_protection = cfg.get("require_all_pid_group_protection", False)
    for name in ("main", "independent"):
        processes = [json.loads(path.read_text()) for path in sorted((args.output / name).glob("pid-?.json"))]
        if len(processes) != cfg["pids_per_round"] or not all(process["complete"] for process in processes):
            write(args.output / "report.json", dict(status="INCONCLUSIVE", reason="Missing complete process coverage",
                                                   round=name, config_sha256=digest(args.config)))
            print("INCONCLUSIVE: missing complete process coverage in", name)
            return
        for process in processes:
            assert process["config_sha256"] == digest(args.config)
            assert identity_key(process["identity"]) == cfg["identity"]
            if all_unit_protection and (set(process["rows"]) != set(cfg["rows"]) or any(
                    row["count"] != cfg["groups_per_pid"] for row in process["rows"].values())):
                write(args.output / "report.json", dict(status="INCONCLUSIVE",
                      reason="Missing complete scene or pair quota", round=name,
                      config_sha256=digest(args.config)))
                return
        pids = [process["identity"]["pid"] for process in processes]
        all_pids += pids
        rows = {}
        for ident, calibration in cfg["rows"].items():
            observations = [process["rows"][ident] for process in processes]
            pid_spread = spread([row["R"] for row in observations])
            individual_order = max(row["order_spread"] for row in observations)
            grouped = []
            for indices in cfg.get("pid_groups", []):
                selected = [observations[index] for index in indices]
                orders = {order: statistics.median(row["order_R"][order] for row in selected)
                          for order in ("AB", "BA")}
                grouped.append(dict(pids=[pids[index] for index in indices],
                                    R=statistics.median(row["R"] for row in selected),
                                    order_R=orders, order_spread=spread(list(orders.values())),
                                    ns={role: statistics.median(row["ns"][role] for row in selected)
                                        for role in "AB"}))
            effective = grouped or observations
            ratio = statistics.median(row["R"] for row in effective)
            stability = spread([row["R"] for row in effective])
            order_spread = max(row["order_spread"] for row in effective)
            rows[ident] = dict(R=ratio, time_ratio=1 / ratio, pid_spread=pid_spread,
                               pid_order_spread=individual_order, group_spread=stability,
                               order_spread=order_spread, group=calibration["group"],
                               process_groups=grouped,
                               stable=stability <= limits["max_spread"] and order_spread <= limits["max_spread"],
                               protected=1 / min([ratio] + [row["R"] for row in grouped]) <= limits["max_time_ratio"],
                               conservative_R=min([ratio] + [row["R"] for row in grouped]),
                               ns={role: statistics.median(row["ns"][role] for row in effective)
                                   for role in "AB"})
        parse = [row["R"] for row in rows.values() if row["group"] == "parse"]
        geometry = math.exp(statistics.mean(math.log(ratio) for ratio in parse))
        units = []
        if all_unit_protection:
            partitions = cfg.get("pid_groups", [])
            assert sorted(index for group in partitions for index in group) == list(range(len(processes)))
            for index, process in enumerate(processes):
                parse_values = [process["rows"][ident]["R"] for ident, calibration in cfg["rows"].items()
                                if calibration["group"] == "parse"]
                value = math.exp(statistics.mean(math.log(ratio) for ratio in parse_values))
                units.append(dict(unit="pid", index=index, pid=pids[index], parse_geometry=value))
                if value < limits["parse_geometry"]:
                    unit_failures.append(dict(round=name, unit="pid_geometry", pid=pids[index], value=value))
                for ident, row in process["rows"].items():
                    if 1 / row["R"] > limits["max_time_ratio"]:
                        unit_failures.append(dict(round=name, unit="pid_scene", pid=pids[index],
                                                  id=ident, time_ratio=1 / row["R"]))
            for index in range(len(partitions)):
                parse_values = [row["process_groups"][index]["R"] for row in rows.values() if row["group"] == "parse"]
                value = math.exp(statistics.mean(math.log(ratio) for ratio in parse_values))
                units.append(dict(unit="group", index=index, parse_geometry=value))
                if value < limits["parse_geometry"]:
                    unit_failures.append(dict(round=name, unit="group_geometry", index=index, value=value))
                for ident, row in rows.items():
                    ratio = row["process_groups"][index]["R"]
                    if 1 / ratio > limits["max_time_ratio"]:
                        unit_failures.append(dict(round=name, unit="group_scene", index=index,
                                                  id=ident, time_ratio=1 / ratio))
        rounds[name] = dict(pids=pids, rows=rows, parse_geometry=geometry)
        if all_unit_protection:
            rounds[name]["protected_units"] = units
    assert len(set(all_pids)) == cfg["pids_per_round"] * 2
    cross = {ident: spread([rounds[name]["rows"][ident]["R"] for name in rounds])
             for ident in cfg["rows"]}
    insufficient = sorted({ident for name in rounds for ident, row in rounds[name]["rows"].items()
                           if row["group"] != "config" and not row["stable"]} |
                          {ident for ident, value in cross.items()
                           if cfg["rows"][ident]["group"] != "config" and value > limits["max_spread"]})
    failures = sorted({ident for name in rounds for ident, row in rounds[name]["rows"].items()
                       if row["group"] != "config" and row["stable"] and not row["protected"]})
    status = ("INCONCLUSIVE" if insufficient else
              "FAIL" if failures or unit_failures or any(r["parse_geometry"] < limits["parse_geometry"] for r in rounds.values()) else "PASS")
    result = dict(status=status, rounds=rounds, cross_round_spread=cross,
                                          insufficient_rows=insufficient, failed_rows=failures,
                                          config_sha256=digest(args.config),
                  observation_rows={name:{ident:row for ident,row in value["rows"].items() if row["group"]=="config"} for name,value in rounds.items()},
                  protected_rows=[ident for ident,row in cfg["rows"].items() if row["group"]!="config"])
    if all_unit_protection:
        result["unit_protection_failures"] = unit_failures
    write(args.output / "report.json", result)
    print(status, {name: round(value["parse_geometry"], 4) for name, value in rounds.items()},
          "inconclusive", insufficient, "failures", failures)


def clock_check(args):
    """Save an identified fresh-process clock proof before final freezing."""
    _, _, _, bound, clocks, _, identity = prepare(args.installed)
    proof = clocks()
    write(args.output, dict(identity=identity, proof=proof, clock_bound_ns=bound(proof)))


def quick(args):
    """Bounded development screen, never a formal acceptance result."""
    scenes, build, quality, bound, clocks, measure, identity = prepare(args.installed)
    cfg=dict(clock_uncertainty_ns=bound(clocks()))
    deadline=time.monotonic()+args.minutes*60
    args.output.mkdir(parents=True,exist_ok=True)
    rows={}
    with (args.output/"raw.jsonl").open("a") as stream:
        for scene in scenes:
            runs={role:build(role,scene)[0] for role in "AB"}
            for run in runs.values():run(200)
            n=200
            for _ in range(4):
                values=[measure(run,n)["T"] for run in runs.values()]
                fastest=min(values)
                if fastest>=10_000_000:break
                n=max(n+1,math.ceil(n*15_000_000/max(fastest,1)))
            groups=pairs(runs,n,1_500_000_000,6,cfg,quality,measure,deadline,stream,scene.id,attempt_limit=40)
            rows[scene.id]=dict(pair_summary(groups),group=scene.group,label=scene.label)
            print("QUICK",scene.id,round(rows[scene.id]["R"],3) if groups else None,flush=True)
            write(args.output/"summary.json",dict(identity=identity,rows=rows,purpose="Development only"))
            if time.monotonic()>=deadline:break


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("mode", choices=("calibrate", "pilot", "collect", "report", "clock_check", "quick"))
    cli.add_argument("--installed", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--config", type=Path)
    cli.add_argument("--counts", type=Path, help="Prospective preflight counts; never applied during collection")
    cli.add_argument("--pid-index", type=int, choices=range(9))
    cli.add_argument("--minutes", type=float, default=15)
    cli.add_argument("--max-spread", type=float, default=0.03,
                     help="Prospective calibration precision limit; frozen reports read their config")
    cli.add_argument("--deadline-monotonic", type=float,
                     help="Shared absolute collect deadline; children cannot extend it")
    args = cli.parse_args()
    if args.mode not in ("calibrate", "clock_check", "quick") and args.config is None:
        cli.error("--config is required outside calibration")
    globals()[args.mode](args)


if __name__ == "__main__":
    main()
