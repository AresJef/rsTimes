"""Entry selection and object workloads using the existing paired collector.

The old Parser/Delta matrix, timing brackets, quality checks and balanced pair
collection are reused. This adapter only supplies the new public entrances.
"""
from pathlib import Path
from datetime import date, datetime, timezone
from collections import Counter
from dataclasses import replace
import argparse
import hashlib
import importlib.metadata as metadata
import json
import math
import os
import statistics as st
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import parser_behavior as b
from benchmarks import parser_optimization as workloads
from benchmarks.delta import bench as transport
from benchmarks.parser_scenarios import Scene

EVIDENCE = ROOT / 'tasks/evidence/parser-objects-20261016'
OLD = ROOT / '.local/parser-behavior-20261015/rc02-final-env'
F0 = ROOT / '.local/parser-objects-20261016/f0-env'
OLD_SHA = '4275aa83f3048641f2993ca6124b96d485512ac967139256410a25f45faa6007'
GROUPS = ((0, 1, 2), (3, 4, 5), (6, 7, 8))
DISPATCH = ('B01', 'B05', 'B09', 'B12', 'B16', 'B18', 'B20', 'B28',
            'B30', 'B31', 'Q01', 'C04')
OBJECTS = (
    ('O01', 'Builtin datetime identity', 'builtin'),
    ('O02', 'Date at midnight', 'date'),
    ('O03', 'Integer epoch seconds', 'integer'),
    ('O04', 'Negative integer epoch seconds', 'negative_integer'),
    ('O05', 'Fractional epoch seconds', 'fraction'),
    ('O06', 'Negative fractional epoch seconds', 'negative_fraction'),
    ('O07', 'NumPy microseconds', 'numpy_us'),
    ('O08', 'NumPy nanoseconds', 'numpy_ns'),
    ('O09', 'NumPy calendar months', 'numpy_month'),
    ('O10', 'Datetime subclass to builtin', 'child'),
    ('O11', 'Callable datetime constructor', 'factory'),
    ('O12', 'Pandas Timestamp to builtin', 'timestamp'),
)
OBJECT_LABELS = {ident: label for ident, label, _ in OBJECTS}
ISO = ('B01','B02','B03','B04','B05','B06','B07','B08','B22','B23',
       'B36','U08','U09','U10')


def pairs(matrix):
    if matrix == 'old':
        return b.PAIRS
    ids = DISPATCH if matrix == 'dispatch' else tuple(OBJECT_LABELS)
    return {i: (('A', i), ('B', i)) for i in ids}


def object_workloads(function):
    import numpy as np
    from pandas import Timestamp
    class Child(datetime):
        pass
    def factory(**fields):
        return datetime(**fields)
    values = dict(builtin=datetime(2024,5,7,15,30,1,123456,tzinfo=timezone.utc,fold=1),
        date=date(2024,5,7),integer=1730000000,negative_integer=-123456789,
        fraction=1730000000.1234567,negative_fraction=-1.23456789,
        numpy_us=np.datetime64('2024-05-07T15:30:01.123456','us'),
        numpy_ns=np.datetime64('2024-05-07T15:30:01.123456789','ns'),
        numpy_month=np.datetime64('2024-05','M'),
        child=Child(2024,5,7,15,30,1,123456,tzinfo=timezone.utc,fold=1),
        factory=datetime(2024,5,7,15,30,1,123456),
        timestamp=Timestamp('2024-05-07T15:30:01.123456789'))
    output = {}
    for ident, label, key in OBJECTS:
        expression = 'fn(value, dtclass=factory)' if key == 'factory' else 'fn(value)'
        env = dict(fn=function,value=values[key],factory=factory)
        source = ('def run(n, fn=fn, value=value, factory=factory):\n'
                  '    for _ in range(n):\n'
                  f'        result = {expression}\n        del result\n')
        exec(compile(source, '<parser-object-'+ident+'>', 'exec'), env)
        observed = b.base.engine.canonical(b.base.engine.capture(lambda: eval(expression,env)))
        output[ident] = (env['run'], workloads.digest_text(source), observed)
    return output


def worker():
    role = sys.argv[sys.argv.index('--worker')+1]
    matrix = sys.argv[sys.argv.index('--variant')+1]
    qos = transport.measurement_qos(sys.argv[sys.argv.index('--measurement-qos')+1])
    from rstimes import Configs
    import rstimes
    import rstimes._native as native
    target = rstimes.parse_str if hasattr(rstimes,'parse_str') else rstimes.parse
    if matrix in ('objects','official') or (matrix=='dispatch' and role=='B'):
        target = rstimes.parse
    if matrix=='official' and role=='A':
        from cytimes.parser import parse_obj as target
        import cytimes.parser as native
    if matrix in ('objects','official'):
        built = object_workloads(target)
    else:
        scenes = b.SCENES if matrix=='old' else tuple(s for s in b.SCENES if s.id in DISPATCH)
        built = {s.id:b.workload(s,Configs,target) for s in scenes}
        if matrix=='old':
            dr,ds,do=workloads.delta_workloads()
            built.update({i:(dr[i],ds[i],do[i]) for i in dr})
    support={}
    for name in ('cytimes.pydt','cytimes.utils','cytimes.errors','cytimes.parser'):
        module=__import__(name,fromlist=['*'])
        support[name]=dict(path=str(Path(module.__file__).resolve()),sha256=workloads.digest(module.__file__))
    identity=dict(pid=os.getpid(),python=sys.version,executable=sys.executable,
        native=str(Path(native.__file__).resolve()),native_sha256=workloads.digest(native.__file__),
        version=metadata.version('cytimes' if matrix=='official' and role=='A' else 'rstimes'),
        entrypoint=target.__module__+'.'+target.__name__,qos=qos,support=support,
        source={i:v[1] for i,v in built.items()},observed={i:v[2] for i,v in built.items()},
        dependencies={n:metadata.version(n) for n in ('cytimes','numpy','pandas','python-dateutil','six','tzdata','pytz')})
    print(json.dumps(identity),flush=True)
    for line in sys.stdin:
        req=json.loads(line)
        if req.get('op')=='host':
            result=workloads.clocks()
        else:
            run=built[req['id']][0]
            if req.get('warmup_count'):run(req['warmup_count'])
            result=b.measure(run,req['count']);result['pid']=os.getpid()
        print(json.dumps(result),flush=True)


class Pool:
    def __init__(self,candidate,matrix):
        self.processes={};self.matrix=matrix;self.pairs=pairs(matrix)
        reference=OLD if matrix=='old' else candidate if matrix=='dispatch' else F0
        transport.SELF=Path(__file__).resolve()
        try:
            for role,env in (('A',reference),('B',candidate)):
                self.processes[role]=transport.Process(env,role,'all',variant=matrix)
            self.identity={r:p.metadata for r,p in self.processes.items()}
            if matrix=='old':assert self.identity['A']['native_sha256']==OLD_SHA
            if matrix=='objects':
                assert self.identity['A']['native_sha256']==json.loads((EVIDENCE/'f0-identity.json').read_text())['native_sha256']
            for name in ('python','dependencies','support','qos'):
                assert self.identity['A'][name]==self.identity['B'][name],name
            for ident,(left,right) in self.pairs.items():
                for field in ('source','observed'):
                    assert self.identity[left[0]][field][left[1]]==self.identity[right[0]][field][right[1]],(ident,field)
        except BaseException:
            self.close();raise
    def runs(self,ident,warmup=0):
        return {side:b.Run(self.processes[role],item,warmup)
                for side,(role,item) in zip('AB',self.pairs[ident])}
    def clocks(self):
        proofs={r:p.short_info() for r,p in self.processes.items()}
        return proofs,max(b.clock_bound(p) for p in proofs.values())
    def close(self):
        for p in reversed(list(self.processes.values())):p.close()


def prepare(args):
    args.output.mkdir(parents=True,exist_ok=True);pool=Pool(args.candidate,args.matrix)
    try:
        proof,bound=pool.clocks();b.save(args.output/'clock.json',proof)
        cfg=dict(protocol='parser-objects-paired-v1',clock_uncertainty_ns=max(bound,10_000),
            observed_clock_bound_ns=bound,
            identity=pool.identity,rows={},matrix=args.matrix,
            programs={str(p.relative_to(ROOT)):workloads.digest(p) for p in
                (Path(__file__),ROOT/'benchmarks/parser_behavior.py',ROOT/'benchmarks/parser_optimization.py',
                 ROOT/'benchmarks/parser_timing.py',ROOT/'benchmarks/parser_quality.py',
                 ROOT/'benchmarks/parser_benchmark.py',ROOT/'benchmarks/delta/bench.py',
                 ROOT/'benchmarks/parser_scenarios.py',ROOT/'tests/parser/cases.py',
                 ROOT/'tests/parser/data/upstream_datetimes.json',
                 ROOT/'tests/parser/data/behavior_revision_common.json')})
        start=time.monotonic();deadline=start+args.minutes*60
        with (args.output/'controls.jsonl').open('w') as stream:
            for ident in (args.ids or list(pairs(args.matrix))):
                cfg['rows'][ident]=b.control(pool,ident,cfg,deadline,stream,args.target_ms)
                b.save(args.output/'config.json',cfg)
                print('CONTROL',ident,cfg['rows'][ident]['ready'],cfg['rows'][ident]['precision'],flush=True)
        cfg.update(status='CONTROLS_RECORDED',seconds=time.monotonic()-start)
        b.save(args.output/'config.json',cfg)
    finally:pool.close()


def collect_cycle(args,cfg,path,deadline,count,ids):
    pool=Pool(args.candidate,args.matrix)
    try:
        for role in 'AB':
            for name in ('native_sha256','version','python','dependencies','support','qos','source','observed','entrypoint')+tuple(k for k in ('runtime','hash_values') if k in cfg['identity'][role]):
                assert pool.identity[role][name]==cfg['identity'][role][name],(role,name)
        proof,bound=pool.clocks()
        b.save(path.with_suffix('.clock.json'),dict(proofs=proof,
            observed_bound_ns=bound,frozen_bound_ns=cfg['clock_uncertainty_ns']))
        assert bound<=cfg['clock_uncertainty_ns'],(bound,cfg['clock_uncertainty_ns'])
        rows={i:[] for i in ids}
        with path.with_suffix('.jsonl').open('w') as stream:
            for sweep in range(2):
                for ident in (list(rows) if sweep==0 else list(reversed(rows))):
                    c=cfg['rows'][ident]
                    values=b.engine.pairs(pool.runs(ident,c['warmup_n']),c['n'],c['span_ns'],count//2,
                        cfg,b.quality,b.measure,deadline,stream,ident,slot_offset=sweep*count//2)
                    rows[ident].extend(values)
                    b.save(path,dict(identity=pool.identity,config_sha256=workloads.digest(args.config),rows=rows,
                        complete=all(len(v)==count for v in rows.values())))
                    if len(values)!=count//2:raise TimeoutError('Incomplete cycle retained')
    finally:pool.close()


def collect(args,screen=False):
    cfg=json.loads(args.config.read_text());assert cfg['matrix']==args.matrix
    for name,sha in cfg['programs'].items():assert workloads.digest(ROOT/name)==sha,name
    ids=args.ids or list(cfg['rows']);args.output.mkdir(parents=True,exist_ok=True)
    limit=args.output/'collection-deadline.json'
    if not limit.exists():b.save(limit,dict(wall_deadline=time.time()+args.minutes*60,original_minutes=args.minutes))
    deadline=time.monotonic()+max(0,json.loads(limit.read_text())['wall_deadline']-time.time())
    if screen:
        for cycle in range(3):
            path=args.output/f'cycle-{cycle}.json'
            collect_cycle(args,cfg,path,deadline,12,ids)
        result={i:dict(ratios=[st.median(v['R'] for v in json.loads((args.output/f'cycle-{c}.json').read_text())['rows'][i]) for c in range(3)],control_ready=cfg['rows'][i]['ready']) for i in ids}
        for row in result.values():row.update(median=st.median(row['ratios']),spread=b.engine.spread(row['ratios']))
        b.save(args.output/'screen.json',result);print(json.dumps(result),flush=True);return
    for name in ('main','independent'):
        (args.output/name).mkdir(exist_ok=True)
        for cycle in range(9):
            path=args.output/name/f'cycle-{cycle}.json'
            if path.exists() and json.loads(path.read_text())['complete']:continue
            start=time.monotonic();collect_cycle(args,cfg,path,deadline,24,ids)
            print(name,cycle,round(time.monotonic()-start,2),'seconds',flush=True)


def levels(values):
    groups=[st.median(values[i] for i in g) for g in GROUPS]
    return groups,st.median(groups)


def analyze(args):
    cfg=json.loads(args.config.read_text());ids=args.ids or list(cfg['rows'])
    rows={i:dict(rounds={}) for i in ids};audit=Counter();pids=[]
    for name in ('main','independent'):
        cycles=[json.loads((args.output/name/f'cycle-{i}.json').read_text()) for i in range(9)]
        for cycle in cycles:
            assert cycle['complete'] and cycle['config_sha256']==workloads.digest(args.config)
            pids.extend(cycle['identity'][r]['pid'] for r in 'AB')
            for ident in ids:
                values=cycle['rows'][ident]
                assert len(values)==24 and Counter(v['order'] for v in values)==Counter(AB=12,BA=12)
                for value in values:
                    assert value['valid'] and value['n']==cfg['rows'][ident]['n']
                    for side,(role,item) in zip('AB',pairs(args.matrix)[ident]):
                        assert value['checks'][side]['status']=='VALID'
                        assert value['members'][side]['pid']==cycle['identity'][role]['pid']
                    audit['accepted_pairs']+=1
        for raw in (args.output/name).glob('cycle-*.jsonl'):
            for line in raw.read_text().splitlines():
                record=json.loads(line);audit['attempts']+=1
                if not record['valid']:audit['rejected_pairs']+=1
        for ident,row in rows.items():
            values=[st.median(v['R'] for v in c['rows'][ident]) for c in cycles]
            groups,median=levels(values)
            orders=[levels([st.median(v['R'] for v in c['rows'][ident] if v['order']==order) for c in cycles])[1] for order in ('AB','BA')]
            ns={side:levels([st.median(v['members'][side]['T']/v['n'] for v in c['rows'][ident]) for c in cycles])[1] for side in 'AB'}
            row['rounds'][name]=dict(median=median,groups=groups,conservative=min(median,*groups),
                group_spread=b.engine.spread(groups),order_spread=b.engine.spread(orders),cycles=values,ns=ns)
    assert len(pids)==len(set(pids))==36
    for ident,row in rows.items():
        a,z=row['rounds'].values();cross=b.engine.spread([a['median'],z['median']])
        stable=max(a['group_spread'],z['group_spread'],a['order_spread'],z['order_spread'],cross)<=.05
        row.update(precision=cfg['rows'][ident]['precision'],cross_spread=cross,stable=stable)
        row['status']='INCONCLUSIVE' if not stable or not cfg['rows'][ident]['ready'] else 'PASS' if min(a['median'],z['median'],a['conservative'],z['conservative'])>=1/1.05 else 'FAIL'
    groups={'all':ids} if args.matrix!='old' else {'common36':[f'B{i:02}' for i in range(1,37)],'ISO14':ISO,'common-corpus6':[f'T{i:02}' for i in range(1,7)]}
    combinations={}
    for title,selection in groups.items():
        if not all(i in rows for i in selection):continue
        rounds={}
        for name in ('main','independent'):
            values=[rows[i]['rounds'][name] for i in selection]
            geo=lambda vals:math.exp(st.mean(math.log(v) for v in vals))
            median=geo([v['median'] for v in values]);gs=[geo([v['groups'][g] for v in values]) for g in range(3)]
            rounds[name]=dict(median=median,groups=gs,conservative=min(median,*gs))
        status='INCONCLUSIVE' if any(rows[i]['status']=='INCONCLUSIVE' for i in selection) else 'PASS' if min(v[k] for v in rounds.values() for k in ('median','conservative'))>=1/1.05 else 'FAIL'
        combinations[title]=dict(rounds=rounds,status=status)
    result=dict(rows=rows,combinations=combinations,protection=dict(Counter(r['status'] for r in rows.values())),
        audit=dict(audit),real_worker_pids=pids,config_sha256=workloads.digest(args.config),matrix=args.matrix)
    b.save(args.output/'performance.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','real_worker_pids')},indent=2),flush=True)


if __name__=='__main__':
    if '--worker' in sys.argv:worker()
    else:
        cli=argparse.ArgumentParser(description=__doc__)
        cli.add_argument('action',choices=('prepare','screen','collect','analyze'))
        cli.add_argument('--matrix',choices=('old','dispatch','objects','official'),required=True)
        cli.add_argument('--candidate',type=Path,required=True)
        cli.add_argument('--output',type=Path,required=True)
        cli.add_argument('--config',type=Path)
        cli.add_argument('--ids',nargs='+')
        cli.add_argument('--minutes',type=float,default=10)
        cli.add_argument('--target-ms',type=float,default=10)
        args=cli.parse_args()
        if args.action=='prepare':prepare(args)
        elif args.action=='analyze':analyze(args)
        else:collect(args,args.action=='screen')
