"""Thin two-version adapter for the approved Configs internalization contract.

Reuse the existing process transport, target bracket, quality checks and paired
collector. No legacy Configs query or subclass is constructed by this worker.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse, hashlib, json, math, pickle, sys, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks import parser_optimization as base
from benchmarks import parser_benchmark as engine
from benchmarks.parser_quality import quality, clock_bound
from benchmarks.parser_timing import measure
from benchmarks.delta import bench as transport

OLD=ROOT/'.local/parser-optimization-20261015/final-env'
OLD_SHA='f68d86f23ae86cec281ee6badda647d5d9cbc0897d6032ed479d795b2bfc5e8c'
EVIDENCE=ROOT/'tasks/evidence/configs-rust-internal-20261015'
COMMON=tuple(s for s in base.SCENES if s.id not in ('C01','K04','K17'))
EXTRA=tuple(base.base.Scene(f'{prefix}{i:02}',f'{prefix} configuration {mode}','restore',expression,text,config_mode=mode)
 for prefix in ('N','F') for i,(mode,text,expression) in enumerate((
 ('default','14 October 2026','fn(text, cfg=cfg)'),('month','14 harvest 2026','fn(text, cfg=cfg)'),
 ('timezone','2026-10-14 15:30 XYZ','fn(text, cfg=cfg, ignoretz=False)')),1))
SCENES=COMMON+EXTRA
ORIGINAL_WORKLOAD=base.workload

def workload(scene,cls,fn):
    if scene.id[0] not in 'NF':return ORIGINAL_WORKLOAD(scene,cls,fn)
    def factory(*args,**kwargs):
        cfg=cls(*args,**kwargs)
        if scene.config_mode=='month':cfg.add_month('harvest',10)
        if scene.config_mode=='timezone':cfg.add_tz('XYZ',8)
        return pickle.loads(pickle.dumps(cfg)) if scene.id.startswith('N') else cfg
    return ORIGINAL_WORKLOAD(scene,factory,fn)

base.SCENES=SCENES
base.workload=workload
PAIRS={s.id:(('A',s.id),('B',s.id)) for s in COMMON if s.group!='config'}
PAIRS.update({s.id:(('A',s.id),('B',s.id)) for s in base.DELTA})
PAIRS.update({f'N{i:02}':(('A',f'N{i:02}'),('B',f'N{i:02}')) for i in range(1,4)})
PAIRS.update({f'J{i:02}':(('B',f'F{i:02}'),('B',f'N{i:02}')) for i in range(1,4)})
OBSERVATIONS={s.id:(('A',s.id),('B',s.id)) for s in COMMON if s.group=='config'}
assert len(PAIRS)==67 and len(OBSERVATIONS)==15
save=base.save

class Run:
    def __init__(self,process,ident,warmup=0):self.process,self.ident,self.warmup=process,ident,warmup
    def sample(self,n):
        out=self.process.measure(self.ident,n,warmup_count=self.warmup)
        out['immediate_warmup_calls']=self.warmup
        return out
    def __call__(self,n):return self.sample(n)

class Pool:
    def __init__(self,candidate):
        transport.SELF=Path(__file__).resolve();self.processes={}
        try:
            for role,env in [('A',OLD),('B',candidate)]:self.processes[role]=transport.Process(env,'rstimes','all')
            self.identity={r:p.metadata for r,p in self.processes.items()}
            assert self.identity['A']['native_sha256']==OLD_SHA
            for name in ('python','dependencies','support','source','observed','qos'):assert self.identity['A'][name]==self.identity['B'][name],name
            for i in range(1,4):
                for field in ('source','observed'):assert self.identity['B'][field][f'N{i:02}']==self.identity['B'][field][f'F{i:02}']
        except BaseException:self.close();raise
    def runs(self,ident,warmup=0):return {side:Run(self.processes[role],item,warmup) for side,(role,item) in zip('AB',(PAIRS|OBSERVATIONS)[ident])}
    def clocks(self):
        proofs={r:p.short_info() for r,p in self.processes.items()}
        return proofs,max(clock_bound(p) for p in proofs.values())
    def close(self):
        for p in reversed(list(self.processes.values())):p.close()

def control(pool,ident,cfg,deadline,stream,target=10):
    runs=pool.runs(ident);n=1
    for run in runs.values():run(200)
    for _ in range(5):
        samples={k:measure(v,n) for k,v in runs.items()};fastest=min(v['T'] for v in samples.values())
        if fastest>=target*900000:break
        n=max(n+1,math.ceil(n*target*1000000/max(1,fastest)))
    runs=pool.runs(ident,n)
    span=max(250000000,math.ceil(sum(v['T'] for v in samples.values())*4/50000000)*50000000)
    # Interleave control lengths to avoid putting all long controls later.
    # Each cohort retains its original complete AB/BA quota and all raw values.
    short=[];long=[]
    for block in range(6):
        short.extend(engine.pairs(runs,n,span,2,cfg,quality,measure,deadline,stream,ident+':short',slot_offset=block*2))
        long.extend(engine.pairs(runs,n*3,span*3,1,cfg,quality,measure,deadline,stream,ident+':long',slot_offset=block))
    a,z=engine.pair_summary(short),engine.pair_summary(long)
    precision=engine.spread([a['R'],z['R']]) if len(short)==12 and len(long)==6 else None
    return dict(n=n,span_ns=span,target_ms=target,short=a,long=z,precision=precision,ready=precision is not None and precision<=.03,warmup_n=n)

def prepare(candidate,output,ids,minutes):
    output.mkdir(parents=True,exist_ok=True);deadline=time.monotonic()+minutes*60;pool=Pool(candidate)
    try:
        proof,bound=pool.clocks();save(output/'clock.json',proof)
        cfg=dict(protocol='configs-internal-paired-v1',clock_uncertainty_ns=bound,identity=pool.identity,rows={},programs={str(p.relative_to(ROOT)):base.digest(p) for p in [Path(__file__),ROOT/'benchmarks/parser_optimization.py',ROOT/'benchmarks/parser_benchmark.py',ROOT/'benchmarks/parser_quality.py',ROOT/'benchmarks/parser_timing.py',ROOT/'benchmarks/delta/bench.py',ROOT/'benchmarks/parser_scenarios.py',ROOT/'tests/parser/cases.py',ROOT/'tests/parser/data/upstream_datetimes.json']})
        with (output/'controls.jsonl').open('w') as stream:
            for ident in ids:
                cfg['rows'][ident]=control(pool,ident,cfg,deadline,stream,40 if ident in ('B01','D02') else 10)
                save(output/'config.json',cfg);print(ident,cfg['rows'][ident]['ready'],cfg['rows'][ident]['precision'],flush=True)
        return cfg
    finally:pool.close()

def collect(candidate,config,output,deadline,ids=None,count=24):
    cfg=json.loads(config.read_text());assert cfg['status']=='FROZEN_READY'
    for name,sha in cfg['programs'].items():assert base.digest(ROOT/name)==sha,name
    pool=Pool(candidate)
    try:
        for role in 'AB':
            for name in ('native_sha256','version','python','dependencies','source','observed','support','qos'):assert pool.identity[role][name]==cfg['identity'][role][name],(role,name)
        proof,bound=pool.clocks();assert bound<=cfg['clock_uncertainty_ns'];save(output.with_suffix('.clock.json'),proof)
        rows={i:[] for i in (ids or PAIRS)}
        with output.with_suffix('.jsonl').open('w') as stream:
            for sweep in range(2):
                for ident in (list(rows) if sweep==0 else list(reversed(rows))):
                    c=cfg['rows'][ident];runs=pool.runs(ident,c['warmup_n'])
                    values=engine.pairs(runs,c['n'],c['span_ns'],count//2,cfg,quality,measure,deadline,stream,ident,slot_offset=sweep*count//2)
                    rows[ident].extend(values)
                    save(output,dict(identity=pool.identity,config_sha256=base.digest(config),rows=rows,complete=all(len(v)==count for v in rows.values())))
                    if len(values)!=count//2:raise TimeoutError('Incomplete cycle retained')
    finally:pool.close()

if __name__=='__main__':
    if '--worker' in sys.argv:base.worker()
    else:
        p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['proof','prepare']);p.add_argument('--candidate',type=Path,default=OLD);p.add_argument('--output',type=Path,required=True);p.add_argument('--minutes',type=float,default=4);a=p.parse_args()
        prepare(a.candidate,a.output,['B01','B17','B28','T01','D02','N02','J02'] if a.mode=='proof' else list(PAIRS),a.minutes)
