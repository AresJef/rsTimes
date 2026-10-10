"""Bind a fixed representative timing comparison to the actual Delta runner."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("paired", ROOT/"benchmarks/delta/paired.py")
paired = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paired)
REPRESENTATIVES = {"relative:zero", "getters:single", "delta-arithmetic:positive:add",
                   "date-call:ny-fold:reuse", "dateutil:from:integer:Delta",
                   "numpy-datetime:ns:negative:add", "save:child:read"}


def capture(candidate_env, output, width, selected=(), short_ms=1):
    """Alternate short/control in the same thread; never stitch unmatched times."""
    spec=importlib.util.spec_from_file_location("bench",ROOT/"benchmarks/delta/bench.py")
    bench=importlib.util.module_from_spec(spec);sys.modules["bench"]=bench;spec.loader.exec_module(bench)
    identifiers=sorted(selected or REPRESENTATIVES)
    oracle=bench.Process(ROOT/".local/delta/oracle","cytimes","all",identifiers,0,"interactive")
    worker=None
    directory=ROOT/"benchmarks/delta/results"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();deadline=started+180
    try:
        worker=bench.Process(candidate_env,"paired","all",identifiers,0,"interactive")
        ref,cand=worker.metadata["cytimes"],worker.metadata["rstimes"]
        old,new=dict(oracle.metadata["environment"]),dict(ref["environment"])
        for key in ("package_file","process_model"):
            old.pop(key,None);new.pop(key,None)
        if old!=new or bench.comparable(oracle.metadata)!=bench.comparable(ref) or bench.comparable(ref)!=bench.comparable(cand):
            raise ValueError("Capture must match frozen reference and candidate outputs")
        host=worker.short_info()
        results=[]
        for target in (short_ms,5*short_ms):
            results.append({"protocol":paired.PROTOCOL,"mode":"formal","reference":ref,"candidate":cand,
                "hardware":host,"helper_sha256":bench.digest(ROOT/"benchmarks/delta/paired.py"),
                "sampling":{**paired.RULES,"target_ms":float(target),"required_pairs":12,"pairs_per_block":width,
                    "queue_policy":"finish-case; defer only invalid pairs","max_attempts_per_case":max(120,12*width*3),
                    "session_budget_seconds":180,"process_model":"shared-thread"},
                "states":{},"comparison_order":"short/control alternate; whole four measurements must qualify"})
        rejected=[]
        for case in ref["cases"]:
            pilot=worker.pair(case["id"],2000,["reference","candidate"],2000)
            per_call=min(b["cpu_elapsed_ns"]/b["count"] for b in pilot["batches"].values())
            count=max(1,math.ceil(short_ms*1e6/per_call));warm=max(1,math.ceil(.25e6/per_call))
            for scale,result in zip((1,5),results):
                result["states"][case["id"]]={"count":count*scale,"accepted":[],"attempts":[],"required":12,"pairs_per_block":width}
            index=attempts=0
            while index<12*width and attempts<12*width*3 and time.monotonic()<deadline:
                block,within=divmod(index,width)
                order=["reference","candidate"] if (block+within)%2==0 else ["candidate","reference"]
                sequence=(0,1) if index%2==0 else (1,0)
                unit={}
                for side in sequence:
                    unit[side]=worker.pair(case["id"],count*(1 if side==0 else 5),order,warm)
                attempts+=1
                span=max(p["end_ns"] for p in unit.values())-min(p["start_ns"] for p in unit.values())
                valid=all(p["valid"] for p in unit.values()) and span<=paired.RULES["span_ns"]
                for side,result in enumerate(results):
                    state=result["states"][case["id"]];state["attempts"].append(unit[side])
                    if valid:state["accepted"].append(unit[side])
                if valid:index+=1
                else:
                    rejected.append({"id":case["id"],"span_ns":span,"measurements":unit})
                    time.sleep(min(1,max(0,deadline-time.monotonic())))
            if index<12*width:break
        for result in results:
            cases=[c for c in ref["cases"] if c["id"] in result["states"]]
            result["measurements"]=[paired.row(c,result["states"][c["id"]]) for c in cases]
            result["sampling_counts"]={"accepted":sum(len(s["accepted"]) for s in result["states"].values()),
                "attempted":sum(len(s["attempts"]) for s in result["states"].values()),"rejected":len(rejected)}
            result["elapsed_seconds"]=time.monotonic()-started
        short=directory/"short.json";control=directory/"control.json"
        for result,path in zip(results,(short,control)):path.write_text(json.dumps(result,indent=2)+"\n")
        (directory/"rejected.json").write_text(json.dumps(rejected,indent=2)+"\n")
        return short,control
    finally:
        oracle.close()
        if worker is not None:worker.close()


def validate(short_path, control_path, selected=()):
    short, control = [json.loads(Path(p).read_text()) for p in (short_path, control_path)]
    # CLI durations are floats. Canonicalize older producer integer encodings;
    # this changes no measurement, selected sample or acceptance threshold.
    for result in (short, control):
        result["sampling"]["target_ms"] = float(result["sampling"]["target_ms"])
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    runner = digest(ROOT/"benchmarks/delta/bench.py")
    helper = digest(ROOT/"benchmarks/delta/paired.py")
    for result in (short, control):
        if result["protocol"] != paired.PROTOCOL or result["mode"] != "formal":
            raise ValueError("Both probes must use the formal short protocol")
        if {r["id"] for r in result["measurements"]} != set(selected or REPRESENTATIVES):
            raise ValueError("Use all declared fixed timing representatives")
        if result["helper_sha256"] != helper or result["candidate"]["runner_sha256"] != runner:
            raise ValueError("Probe does not match the current runner/helper")
        if result["sampling"]["required_pairs"] != 12:
            raise ValueError("Precision proof requires 12 statistical blocks")
    for name in ("candidate", "reference"):
        if short[name] != control[name]:
            raise ValueError("Different code/environment/inputs in control")
    left, right = dict(short["sampling"]), dict(control["sampling"])
    left.pop("target_ms"); right.pop("target_ms")
    if left != right or control["sampling"]["target_ms"] < 5*short["sampling"]["target_ms"]:
        raise ValueError("Only target duration may differ; control must be at least five times longer")
    other = {r["id"]:r for r in control["measurements"]}
    comparisons = [{"id":r["id"], "short_ratio":r["speed_ratio"],
                    "control_ratio":other[r["id"]]["speed_ratio"],
                    "relative_difference":abs(r["speed_ratio"]/other[r["id"]]["speed_ratio"]-1),
                    "short_noise":r["max_noise"], "control_noise":other[r["id"]]["max_noise"]}
                   for r in short["measurements"]]
    micro = [p for state in short["states"].values() for p in state["accepted"]]
    width = short["sampling"]["pairs_per_block"]
    complete = all(r["status"] == "measured" for result in (short,control) for r in result["measurements"])
    passed = complete and len(micro) == len(selected or REPRESENTATIVES)*12*width and all(p["valid"] for p in micro)
    passed = passed and all(c["relative_difference"] <= .03 and c["short_noise"] <= .05 for c in comparisons)
    return {"protocol":paired.PROTOCOL, "passed":passed, "target_ms":short["sampling"]["target_ms"],
            "pairs_per_block":width, "short_raw":str(Path(short_path).resolve()),
            "control_raw":str(Path(control_path).resolve()), "runner_sha256":runner,"helper_sha256":helper,
            "native_sha256":short["candidate"]["environment"]["native_sha256"],
            "inputs_sha256":short["candidate"]["inputs_sha256"],
            "binding_sha256":paired.precision_binding(short), "comparisons":comparisons,
            "short_counts":short["sampling_counts"], "control_counts":control["sampling_counts"],
            "clock_read_p99_ns":short["hardware"]["clock_read_p99_ns"],
            "max_boundary_fraction":max(b["boundary_ns"]/b["elapsed_ns"] for p in micro for b in p["batches"].values()),
            "minimum_batch_ns":min(b["elapsed_ns"] for p in micro for b in p["batches"].values()),
            "excluded_slow_valid_samples":0}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--short"); parser.add_argument("--control")
    parser.add_argument("--capture",action="store_true");parser.add_argument("--pairs-per-block",type=int,default=40)
    parser.add_argument("--candidate-env",default=str(ROOT/".local/delta/final-env"))
    parser.add_argument("--case",action="append",default=[]);parser.add_argument("--short-ms",type=float,default=1)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if args.capture:
        if args.short or args.control or args.pairs_per_block not in (20,40):parser.error("Capture requires fixed width20 or40")
        if not 1<=args.short_ms<=5:parser.error("Precision short target must be1..5ms")
        args.short,args.control=capture(args.candidate_env,args.output,args.pairs_per_block,args.case,args.short_ms)
    elif not args.short or not args.control:parser.error("Provide short/control or --capture")
    result=validate(args.short,args.control,args.case)
    result["validation_scope_ids"]=args.case or None
    output=Path(args.output)
    with output.open("x") as file:
        file.write(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"passed":result["passed"],"max_difference":max(c["relative_difference"] for c in result["comparisons"]),
                      "max_noise":max(c["short_noise"] for c in result["comparisons"])}))
    raise SystemExit(0 if result["passed"] else 1)
