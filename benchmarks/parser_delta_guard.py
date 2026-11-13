"""Reuse the existing worker transport for three old/new Delta protection calls."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BASELINE = ROOT / ".local/delta/sql-light-20261014/final-env"
BASE_SHA = "111cea05ec5499e66fff2ad8b95a9bb3059beacfe4fcb79d41bd2b0a35a788a7"
from benchmarks.parser_scenarios import Scene
SCENES = (
    Scene("D01","Integer Delta construction","delta","Delta(days=1, hours=2)"),
    Scene("D02","Datetime plus Delta","delta","start + delta"),
    Scene("D03","1024 datetime apply_many","delta","delta.apply_many(values)"),
)


def workloads():
    from datetime import datetime
    from rstimes import Delta
    from benchmarks.parser_scenarios import build as unused
    env=dict(Delta=Delta,delta=Delta(days=1,hours=2),start=datetime(2024,2,29,12,34,56),
             values=[datetime(2024,2,29,12,34,56)]*1024)
    runs={}
    source={}
    for scene in SCENES:
        bindings=", ".join(f"{key}={key}" for key in env)
        text=f"def run(n, {bindings}):\n    for _ in range(n):\n        result = {scene.expression}\n        del result\n"
        exec(compile(text,"<delta-protection-"+scene.id+">","exec"),env)
        runs[scene.id]=env["run"]
        source[scene.id]=hashlib.sha256(text.encode()).hexdigest()
    observed={}
    for scene in SCENES:
        value=eval(scene.expression,env)
        if scene.id=="D01":value=[value.days,value.hours]
        elif scene.id=="D02":value=value.isoformat()
        else:value=[item.isoformat() for item in value]
        observed[scene.id]=hashlib.sha256(json.dumps(value).encode()).hexdigest()
    return runs,source,observed


def worker():
    from benchmarks.parser_timing import measure,clocks
    from benchmarks.delta.bench import measurement_qos
    qos=measurement_qos("initiated")
    import rstimes._native as native
    import importlib.metadata as metadata
    runs,source,observed=workloads()
    identity=dict(pid=os.getpid(),python=sys.version,executable=sys.executable,measurement_qos=qos,
                  native=str(Path(native.__file__).resolve()),
                  native_sha256=hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
                  version=metadata.version("rstimes"),source=source,observed=observed,
                  dependencies={n:metadata.version(n) for n in ("cytimes","numpy","pandas","python-dateutil","six","tzdata","pytz")})
    print(json.dumps(identity),flush=True)
    for line in sys.stdin:
        request=json.loads(line)
        if request.get("op")=="host":result=clocks()
        else:
            run=runs[request["id"]]
            if request.get("warmup_count",0):run(request["warmup_count"])
            result=measure(run,request["count"])
            result["pid"]=os.getpid()
        print(json.dumps(result),flush=True)


POOL=[]
class Remote:
    def __init__(self,process,ident):
        self.process,self.ident=process,ident
    def __call__(self,n):
        self.sample(n)
    def sample(self,n):
        return self.process.measure(self.ident,n)


def prepare(installed):
    from benchmarks import parser_benchmark as engine
    from benchmarks import parser_quality,parser_timing
    spec=importlib.util.spec_from_file_location("_delta_transport",ROOT/"benchmarks/delta/bench.py")
    transport=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    transport.SELF=Path(__file__).resolve()
    candidate=installed.resolve().parents[2]
    for environment in (BASELINE,candidate):
        POOL.append(transport.Process(environment,"rstimes","all"))
    old,new=POOL[-2:]
    assert old.metadata["native_sha256"]==BASE_SHA
    for name in ("python","source","observed","dependencies","measurement_qos"):
        assert old.metadata[name]==new.metadata[name],name
    identity=dict(pid=os.getpid(),python=sys.version,original_version=old.metadata["version"],
                  new_version=new.metadata["version"],modules={role:dict(path=p.metadata["native"],sha256=p.metadata["native_sha256"])
                                                            for role,p in zip("AB",(old,new))},
                  dependencies=old.metadata["dependencies"],measurement_qos=old.metadata["measurement_qos"],
                  programs={name:engine.digest(ROOT/name) for name in
                            ("benchmarks/parser_delta_guard.py","benchmarks/parser_benchmark.py",
                             "benchmarks/parser_quality.py","benchmarks/parser_timing.py","benchmarks/delta/bench.py")},
                  matrix_sha256=hashlib.sha256(json.dumps(old.metadata["source"],sort_keys=True).encode()).hexdigest(),
                  measuring_processes=[old.metadata,new.metadata])
    def build(role,scene):
        return Remote(old if role=="A" else new,scene.id),None
    def clocks():
        proofs=[p.short_info() for p in (old,new)]
        return max(proofs,key=parser_quality.clock_bound)
    return SCENES,build,parser_quality.quality,parser_quality.clock_bound,clocks,parser_timing.measure,identity


if __name__=="__main__":
    if "--worker" in sys.argv:worker()
    else:
        from benchmarks import parser_benchmark as engine
        engine.prepare=prepare
        engine.__file__=str(Path(__file__).resolve())
        engine.REPRESENTATIVES=("D01","D02","D03")
        try:engine.main()
        finally:
            for process in reversed(POOL):process.close()
