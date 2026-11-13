"""Compare isolated old/new Rust workers and the fixed Cython parser.

This adapter reuses the existing transport, timing, quality, paired collection
and serializers. IPC is outside target timing and inside whole-group timing.
"""
from pathlib import Path
from datetime import date
import argparse
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import math
import os
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import parser_scenarios as base
from benchmarks.parser_quality import quality, clock_bound
from benchmarks.parser_timing import measure, clocks
from benchmarks.delta.bench import measurement_qos
from benchmarks.parser_delta_guard import workloads as delta_workloads, SCENES as DELTA
from tools import parser_threeway_compare as engine
from benchmarks import parser_benchmark as paired

OLD = ROOT / '.local/parser-rust-20261014/final-env'
OLD_SHA = 'bf15d9e7871c6bb377c4c22b0a8b63c9cce5b6ed14aa0d6ba3b828fb7f36ff3e'
CYP_SHA = '4c89e4c8793b1be633868f592e2a29c039194eff65a7ea1c8ac5737bc1b8fb65'
TEXTS = ('  July   4 ,  1976   12:01:02   am  ', '01h02m03', '10h36m28.5s',
         '02 Ağustos 2023 12:01', '02 de agosto de 2023', '02-08-2023 12:01 Uhr',
         '02:17NOV2017', '19970902090807', '2023-08-02 01:01:01.001001+01:01',
         '20230802T120101.001001000-05:30', '31-Dec-00', 'Mon, August 2, 2023 12:01 PM')
USER = tuple(base.Scene(f'U{i+1:02}', text, 'upstream',
    'fn(text, default=ancient, yearfirst=False, cfg=cfg, ignoretz=False)', text,
    config_mode='upstream') for i, text in enumerate(TEXTS))
CORPUS = tuple(base.Scene(f'T{i+1:02}', f'728 strings ISO={iso} ignoretz={ignore} cfg={cfg}', 'corpus',
    f'[fn(t, default=ancient, yearfirst=False, isoformat={iso}, ignoretz={ignore}, cfg={"cfg" if cfg else "None"}) for t in corpus]',
    config_mode='upstream') for i, (iso, ignore, cfg) in enumerate(((True,True,True),
    (True,False,True),(False,True,True),(False,False,True),(True,True,False),(False,True,False))))
SCENES = base.SCENES + USER + CORPUS
assert len(SCENES) == 76
ROLES = 'OCR'  # O=old Rust, C=fixed Cython, R=new Rust
PAIRS = {'old/new': ('O', 'R'), 'cython/new': ('C', 'R'), 'old/cython': ('O', 'C')}
engine.ROLES = ROLES
engine.ORDERS = ('OCR','ORC','COR','CRO','ROC','RCO')
engine.PAIRS = PAIRS
engine.measure = measure
save = engine.save


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def workload(scene, cls, fn):
    env = base.namespace('B', scene)
    env.update(cls=cls, fn=fn, ancient=date(1,1,1))
    cfg = cls(False,True) if scene.config_mode == 'ordering' else cls()
    if scene.config_mode == 'month': cfg.add_month('harvest',10)
    elif scene.config_mode == 'timezone':
        (cfg.add_tzoffset if hasattr(cfg, 'add_tzoffset') else cfg.add_tz)('XYZ',8)
    elif scene.config_mode == 'upstream': cfg = engine.cases.configured(cls)
    elif scene.config_mode == 'subclass':
        class CustomConfigs(cls):
            def get_month(self, token): return super().get_month(token)
        cfg = CustomConfigs()
    env['cfg'] = cfg
    if scene.group == 'corpus': env['corpus'] = [row[0] for row in engine.DATA['rows']]
    expression = scene.expression
    if hasattr(cls, 'tzoffset') and scene.group == 'config':
        expression = expression.replace('remove_', 'del_').replace('replace_', 'set_')
        expression = expression.replace('add_tz(', 'add_tzoffset(').replace('del_tz(', 'del_tzoffset(').replace('set_tz(', 'set_tzoffset(')
        expression = expression.replace("'tz'", "'tzoffset'")
        if scene.id == 'K03':
            assert expression.count('cfg.tz') == 1 and 'cfg.tzoffset' not in expression
            expression = expression.replace('cfg.tz', 'cfg.tzoffset', 1)
    statement = f'result = {expression}\n        del result'
    if scene.catches:
        statement = 'try:\n            '+statement.replace('\n','\n    ')+'\n        except Exception:\n            pass'
    source = f"def run(n, {', '.join(f'{k}={k}' for k in env)}):\n    for _ in range(n):\n        {statement}\n"
    exec(compile(source,'<parser-optimization-'+scene.id+'>','exec'),env)
    observed = engine.capture(lambda: engine.cases.config_state(eval(expression,env))
        if scene.id in ('K01','K02','K16') else eval(expression,env))
    return env['run'], digest_text(source), engine.canonical(observed)


def digest_text(text): return hashlib.sha256(text.encode()).hexdigest()


def worker():
    qos = measurement_qos(sys.argv[sys.argv.index('--measurement-qos') + 1] if '--measurement-qos' in sys.argv else 'initiated')
    cython = sys.argv[sys.argv.index('--worker')+1] == 'cytimes'
    if cython:
        from cytimes_rewrite import Config as cls, parse as fn
        import cytimes_rewrite.parser as native
        version = metadata.version('cytimes-rewrite')
    else:
        from rstimes import Configs as cls, parse as fn
        import rstimes._native as native
        version = metadata.version('rstimes')
    built = {s.id:workload(s,cls,fn) for s in SCENES}
    runs = {k:v[0] for k,v in built.items()}
    sources = {k:v[1] for k,v in built.items()}
    observed = {k:v[2] for k,v in built.items()}
    if not cython:
        dr, ds, do = delta_workloads(); runs.update(dr); sources.update(ds); observed.update(do)
    support={}
    for name in ('cytimes.pydt','cytimes.utils','cytimes.errors'):
        module=__import__(name,fromlist=['*']);support[name]=dict(path=str(Path(module.__file__).resolve()),sha256=digest(module.__file__))
    if cython:
        import cytimes_rewrite.config as configs_native
        assert digest(configs_native.__file__)=='26c7876b39387c9d95af50377ec5fd61357a62ee73b41f0f8ed1e5a03062bb1c'
    else: assert native.release_build()
    identity = dict(support=support,pid=os.getpid(), python=sys.version, executable=sys.executable,
        native=str(Path(native.__file__).resolve()), native_sha256=digest(native.__file__),
        version=version, qos=qos, source=sources, observed=observed,
        dependencies={n:metadata.version(n) for n in ('cytimes','numpy','pandas','python-dateutil','six','tzdata','pytz')})
    print(json.dumps(identity),flush=True)
    for line in sys.stdin:
        req=json.loads(line)
        if req.get('op') == 'host': result=clocks()
        else:
            run = runs[req['id']]
            if req.get('warmup_count'): run(req['warmup_count'])
            result=measure(run,req['count']); result['pid']=os.getpid()
        print(json.dumps(result),flush=True)


class Pool:
    def __init__(self, candidate):
        from benchmarks.delta import bench as transport
        transport.SELF=Path(__file__).resolve()
        self.processes={}
        try:
            for role,env,pkg in (('O',OLD,'rstimes'),('C',OLD,'cytimes'),('R',candidate,'rstimes')):
                self.processes[role]=transport.Process(env,pkg,'all')
            self.identity={r:p.metadata for r,p in self.processes.items()}
            assert self.identity['O']['native_sha256']==OLD_SHA
            assert self.identity['C']['native_sha256']==CYP_SHA
            for s in DELTA:
                for k in ('source','observed'):
                    assert self.identity['O'][k][s.id] == self.identity['R'][k][s.id],(s.id,k)
            first=self.identity['O']
            for r in ROLES:
                for k in ('python','dependencies','qos','support'): assert self.identity[r][k]==first[k],(r,k)
                for s in SCENES:
                    assert self.identity[r]['source'][s.id]==first['source'][s.id],(r,s.id,'loop')
                    assert self.identity[r]['observed'][s.id]==first['observed'][s.id],(r,s.id,'output',self.identity[r]['observed'][s.id],first['observed'][s.id])
        except BaseException:
            self.close(); raise
    def close(self):
        for p in reversed(list(self.processes.values())): p.close()
    def runs(self, ident):
        from benchmarks.parser_delta_guard import Remote
        return {r:Remote(p,ident) for r,p in self.processes.items()}
    def delta_runs(self, ident):
        from benchmarks.parser_delta_guard import Remote
        return {k:Remote(self.processes[r],ident) for k,r in (('A','O'),('B','R'))}
    def clock_proof(self):
        proofs={r:p.short_info() for r,p in self.processes.items()}
        return proofs,max(clock_bound(p) for p in proofs.values())


def selection(ids):
    return [s for s in SCENES if not ids or s.id in ids]


def prepare(args):
    pool=Pool(args.candidate)
    try:
        proof,bound=pool.clock_proof();save(args.output/'clocks.json',proof)
        cfg=dict(protocol='parser-opt-isolated-v1',clock_uncertainty_ns=bound,
            warmup_policy='two-complete-batches-per-sweep', rows={}, delta_rows={}, identity=pool.identity,
            programs={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'benchmarks/parser_scenarios.py',ROOT/'benchmarks/parser_timing.py',ROOT/'benchmarks/parser_quality.py',ROOT/'tools/parser_threeway_compare.py',ROOT/'benchmarks/delta/bench.py',ROOT/'benchmarks/parser_delta_guard.py',ROOT/'tests/parser/cases.py',ROOT/'tests/parser/data/upstream_datetimes.json')})
        with (args.output/'controls.jsonl').open('w') as stream:
            for s in selection(args.ids):
                runs=pool.runs(s.id); n=1
                target_ms = 6 if s.group == 'config' else (20 if s.id in ('B01','B04','B07','B18','B29','B30','B34','U08','U10') else args.target_ms)
                for run in runs.values(): run(2 if s.group=='corpus' else 200)
                for _ in range(4):
                    samples={r:measure(run,n) for r,run in runs.items()}
                    fastest=min(v['T'] for v in samples.values())
                    if fastest>=target_ms*1e6*.9: break
                    n=max(n+1,math.ceil(n*target_ms*1e6/max(fastest,1)))
                total=sum(v['T'] for v in samples.values())
                span=max(250_000_000,math.ceil(total*1.5/50_000_000)*50_000_000)
                for run in runs.values(): run(n*2)
                short=engine.groups(runs,n,span,12,cfg,args.deadline,stream,s.id+':short')
                long=engine.groups(runs,n*3,max(span*3,250_000_000),6,cfg,args.deadline,stream,s.id+':long')
                a=engine.summarize(short) if len(short)==12 else None
                b=engine.summarize(long) if len(long)==6 else None
                precision={k:engine.spread([a['ratios'][k],b['ratios'][k]]) for k in PAIRS} if a and b else {}
                cfg['rows'][s.id]=dict(target_ms=target_ms,n=n,span_ns=span,long_span_ns=max(span*3,250_000_000),short=a,long=b,
                    precision=precision,ready=bool(precision) and precision['old/new']<=.03,
                    scene=vars(s),calibration=samples)
                save(args.output/'config.json',cfg)
                print('CONTROL',s.id,cfg['rows'][s.id]['ready'],precision,flush=True)
                if time.monotonic()>=args.deadline: break
        if not args.ids:
            with (args.output/'delta-controls.jsonl').open('w') as stream:
                for s in DELTA:
                    runs=pool.delta_runs(s.id);n=1
                    for run in runs.values():run(200 if s.id != 'D03' else 2)
                    for _ in range(4):
                        samples={r:measure(run,n) for r,run in runs.items()}
                        fastest=min(v['T'] for v in samples.values())
                        if fastest>=args.target_ms*1e6*.9:break
                        n=max(n+1,math.ceil(n*args.target_ms*1e6/max(fastest,1)))
                    span=max(250_000_000,math.ceil(sum(v['T'] for v in samples.values())*1.5/50_000_000)*50_000_000)
                    for run in runs.values():run(n*2)
                    short=paired.pairs(runs,n,span,12,cfg,quality,measure,args.deadline,stream,s.id+':short')
                    long=paired.pairs(runs,n*3,span*3,6,cfg,quality,measure,args.deadline,stream,s.id+':long')
                    a,b=paired.pair_summary(short),paired.pair_summary(long)
                    precision=paired.spread([a['R'],b['R']]) if a['count']==12 and b['count']==6 else None
                    cfg['delta_rows'][s.id]=dict(n=n,span_ns=span,short=a,long=b,precision=precision,ready=precision is not None and precision<=.03)
                    save(args.output/'config.json',cfg)
                    print('DELTA CONTROL',s.id,cfg['delta_rows'][s.id]['ready'],precision,flush=True)
        save(args.output/'config.json',cfg)
    finally: pool.close()


def collect(args):
    cfg=json.loads(args.config.read_text())
    assert cfg.get('status') == 'FROZEN_READY', 'Freeze and verify all required controls first'
    if args.output.exists(): raise FileExistsError('Formal cycle already exists; preserve it')
    for p,sha in cfg['programs'].items(): assert digest(ROOT/p)==sha,p
    pool=Pool(args.candidate)
    try:
        for r in ROLES:
            for k in ('native_sha256','version','python','dependencies','source','observed','qos','support'):
                assert pool.identity[r][k]==cfg['identity'][r][k],(r,k)
        proof,bound=pool.clock_proof();save(args.output.with_suffix('.clock.json'),proof)
        assert bound<=cfg['clock_uncertainty_ns'],(bound,cfg['clock_uncertainty_ns'])
        scenes=[s for s in selection(args.ids) if s.id in cfg['rows']]
        rows={s.id:[] for s in scenes}
        delta_rows={s.id:[] for s in DELTA}
        with args.output.with_suffix('.jsonl').open('w') as stream:
            for sweep in range(2):
                for s in (scenes if sweep==0 else list(reversed(scenes))):
                    c=cfg['rows'][s.id];runs=pool.runs(s.id)
                    for run in runs.values(): run(c['n']*2)
                    records=engine.groups(runs,c['n'],c['span_ns'],6,cfg,args.deadline,stream,s.id,offset=sweep*6)
                    rows[s.id].extend(records)
                    if len(records)!=6:
                        save(args.output,dict(identity=pool.identity,config_sha256=digest(args.config),results=rows,complete=False))
                        return
                with args.output.with_suffix('.delta.jsonl').open('a') as delta_stream:
                    for s in DELTA:
                        c=cfg['delta_rows'][s.id];runs=pool.delta_runs(s.id)
                        for run in runs.values():run(c['n']*2)
                        values=paired.pairs(runs,c['n'],c['span_ns'],12,cfg,quality,measure,args.deadline,delta_stream,s.id,slot_offset=sweep*12)
                        delta_rows[s.id].extend(values)
                        if len(values)!=12:raise TimeoutError('Incomplete Delta group; raw retained')
                save(args.output,dict(identity=pool.identity,config_sha256=digest(args.config),results=rows,
                    delta_results=delta_rows,complete=all(len(v)==12 for v in rows.values()) and all(len(v)==24 for v in delta_rows.values())))
    finally: pool.close()


def main():
    if '--worker' in sys.argv: worker();return
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('proof','control','collect'))
    p.add_argument('--candidate',type=Path,default=OLD)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path)
    p.add_argument('--ids',type=lambda x:x.split(','),default=[])
    p.add_argument('--minutes',type=float,default=5)
    p.add_argument('--target-ms',type=float,default=10)
    args=p.parse_args();args.deadline=time.monotonic()+args.minutes*60
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.mode in ('proof','control'): args.output.mkdir(exist_ok=True)
    if args.mode=='proof':
        pool=Pool(args.candidate)
        try:
            proof,bound=pool.clock_proof()
            results={s.id:{r:measure(run,1 if s.group=='corpus' else 10000) for r,run in pool.runs(s.id).items()} for s in selection(args.ids)}
            save(args.output/'proof.json',dict(identity=pool.identity,clock_uncertainty_ns=bound,samples=results))
            print('PROOF',len(SCENES),'outputs matched; real worker PIDs',[v['pid'] for v in pool.identity.values()],flush=True)
        finally:pool.close()
    elif args.mode=='control':prepare(args)
    else:collect(args)

if __name__=='__main__':main()
