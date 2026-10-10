"""Replace all unstable cases once; never choose the best among timing runs."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("bench",ROOT/"benchmarks/delta/bench.py")
bench=importlib.util.module_from_spec(spec);sys.modules["bench"]=bench;spec.loader.exec_module(bench)
paired=bench.short_protocol()


def combine(base, replacement):
    if base["protocol"]!=paired.PROTOCOL or replacement["protocol"]!=paired.PROTOCOL:
        raise ValueError("Cannot mix protocols")
    if base["mode"]!=replacement["mode"] or base["mode"]!="formal":
        raise ValueError("Only formal records may be combined")
    allowed=set(base["acceptance"]["unstable"])
    selected={r["id"] for r in replacement["measurements"]}
    if not allowed or selected!=allowed:
        raise ValueError("Replace every unstable case exactly once; no stable cases or omissions")
    if base["acceptance"]["incomplete"] or replacement["acceptance"]["incomplete"]:
        raise ValueError("Incomplete rows cannot be used")
    for name in ("reference","candidate"):
        for key in ("environment","inputs_sha256","manifest_sha256","runner_sha256"):
            if base[name][key]!=replacement[name][key]:
                raise ValueError(f"Different {name}/{key}")
        observations={o["case"]:o for o in bench.comparable(base[name])}
        if any(observations[o["case"]]!=o for o in bench.comparable(replacement[name])):
            raise ValueError("Different declared case outputs")
    if base["helper_sha256"]!=replacement["helper_sha256"]:
        raise ValueError("Different timing helper")
    hardware=[dict(r["hardware"]) for r in (base,replacement)]
    for h in hardware:h.pop("clock_read_p99_ns",None)
    if hardware[0]!=hardware[1]:raise ValueError("Different hardware/clocks")
    sampling=[dict(r["sampling"]) for r in (base,replacement)]
    for s in sampling:s.pop("target_ms")
    if sampling[0]!=sampling[1]:raise ValueError("Different sampling rules/amount")
    if replacement["sampling"]["target_ms"]!=5 or base["sampling"]["target_ms"]!=1:
        raise ValueError("This one declared retry must use1ms→5ms")
    result=copy.deepcopy(base)
    by_id={r["id"]:r for r in replacement["measurements"]}
    result["measurements"]=[by_id.get(r["id"],r) for r in base["measurements"]]
    for identifier in selected:result["states"][identifier]=replacement["states"][identifier]
    expected=[c["id"] for c in base["reference"]["cases"]]
    result["aggregates"]=bench.aggregates(result["measurements"])
    result["acceptance"]=paired.evaluate(result["measurements"],result["aggregates"],expected,"formal",
                                        base["precision_verified"] and replacement["precision_verified"])
    result["sampling"]["target_ms_by_case"]={identifier:5 if identifier in selected else 1 for identifier in expected}
    result["composition"]={"policy":"Replace all declared unstable rows, regardless of new scores; no best-of selection",
                           "replaced_ids":sorted(selected),"unchanged_ids":sorted(set(expected)-selected)}
    result["elapsed_seconds"]=base["elapsed_seconds"]+replacement["elapsed_seconds"]
    result["precision_evidences"]=[base["precision_evidence"],replacement["precision_evidence"]]
    attempts=[p for state in result["states"].values() for p in state["attempts"]]
    result["sampling_counts"]={"attempted":len(attempts),"accepted":sum(p["valid"] for p in attempts),
                               "rejected":sum(not p["valid"] for p in attempts)}
    result["rejected_reasons"]=dict(Counter(reason for p in attempts for reason in p["reasons"]))
    result["side_rejections"]={name:sum(any(reason.startswith(name+":") for reason in p["reasons"]) for p in attempts)
                               for name in ("reference","candidate")}
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",required=True);parser.add_argument("--replacement",required=True)
    parser.add_argument("--output",default=str(ROOT/"benchmarks/delta/results"))
    args=parser.parse_args()
    paths=[Path(args.base).resolve(),Path(args.replacement).resolve()]
    result=combine(*(json.loads(p.read_text()) for p in paths))
    result["source_runs"]=[{"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    directory=Path(args.output)/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory.mkdir(parents=True,exist_ok=False)
    (directory/"raw.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    bench.save(result,args.output,existing_directory=directory)
    print(json.dumps({"directory":str(directory),"core":result["aggregates"]["core"],
                      "thirdparty":result["aggregates"]["thirdparty"],"acceptance":result["acceptance"]}))
