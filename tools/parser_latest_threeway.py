"""Compare the current three fixed Parser deliveries without changing them.

The existing three-way collector supplies complete order slots and raw records.
This adapter adds current artifact identities and an explicit common-input map.
"""
from pathlib import Path
from dataclasses import replace
from datetime import date
import argparse
import copy
import hashlib
import importlib.metadata as metadata
import itertools
import json
import math
import os
import pickle
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import parser_optimization as source
from tools import parser_threeway_compare as engine
from benchmarks.parser_timing import measure as target_measure, clocks
from benchmarks.parser_quality import clock_bound, quality
from benchmarks.delta.bench import measurement_qos

OUT = ROOT / 'tasks/evidence/parser-latest-threeway-20261015'
ROLES = 'OCR'
engine.ROLES = ROLES
engine.ORDERS = tuple(''.join(x) for x in itertools.permutations(ROLES))
engine.PAIRS = {'official/rust': ('O', 'R'), 'official/cython': ('O', 'C'), 'cython/rust': ('C', 'R')}
FULL_YEARS = {'B10':'2026/10/14','B11':'14/10/2026','B12':'01/05/2009',
    'B13':'01/05/2009','B14':'2009/01/05','B15':'2009/01/05',
    'B26':'01/05/2009','B27':'2009/01/05','C04':'2026/10/14','U11':'31-Dec-2000'}
SCENES = tuple(replace(s, text=FULL_YEARS[s.id], label=s.label+' (explicit century)')
    if s.id in FULL_YEARS else s for s in source.SCENES if s.id not in ('C01','K04','K17'))
SCENES += tuple(source.base.Scene(f'N{i:02}', 'Parse with restored '+mode+' configuration',
    'restored', expression, text, config_mode=mode) for i,(mode,text,expression) in enumerate((
    ('default','14 October 2026','fn(text, cfg=cfg)'),
    ('month','14 harvest 2026','fn(text, cfg=cfg)'),
    ('timezone','2026-10-14 15:30 XYZ','fn(text, cfg=cfg, ignoretz=False)')),1))
SCENES += tuple(source.base.Scene(f'K{i:02}', label, 'config', expression) for i,label,expression in (
    (18,'Independent shallow copy','copy.copy(cfg)'),
    (19,'Independent deep copy','copy.deepcopy(cfg)'),
    (20,'Pickle save and restore','pickle.loads(pickle.dumps(cfg))')))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    import cytimes.parser as official
    import rstimes.parser as rust
    import rstimes._native as native
    import cytimes_rewrite.parser as cython
    import cytimes_rewrite.config as config
    from cytimes_rewrite import Config
    versions = {n:metadata.version(n) for n in ('cytimes','rstimes','cytimes-rewrite')}
    assert versions == {'cytimes':'3.1.0','rstimes':'0.1.0+parser.4','cytimes-rewrite':'0.3.0'}
    expected = {'O':'b507cada977d0e0ea4f22d0f9fd34bbac117ac6c14fc807128418f44ca7b85ca',
        'R':'4275aa83f3048641f2993ca6124b96d485512ac967139256410a25f45faa6007',
        'C':'4c89e4c8793b1be633868f592e2a29c039194eff65a7ea1c8ac5737bc1b8fb65'}
    modules={r:dict(path=str(Path(m.__file__).resolve()),sha256=digest(m.__file__))
        for r,m in (('O',official),('R',native),('C',cython))}
    assert {r:v['sha256'] for r,v in modules.items()} == expected
    assert digest(config.__file__) == '26c7876b39387c9d95af50377ec5fd61357a62ee73b41f0f8ed1e5a03062bb1c'
    assert native.release_build()
    files=[Path(__file__), ROOT/'tools/parser_threeway_compare.py',ROOT/'benchmarks/parser_optimization.py',
        ROOT/'benchmarks/parser_scenarios.py',ROOT/'benchmarks/parser_quality.py',
        ROOT/'benchmarks/parser_timing.py',ROOT/'tests/parser/cases.py',
        ROOT/'tests/parser/data/upstream_datetimes.json']
    identity=dict(pid=os.getpid(),python=sys.version,executable=sys.executable,versions=versions,
        modules=modules,cython_config=dict(path=config.__file__,sha256=digest(config.__file__)),
        qos=measurement_qos('initiated'),dependencies={n:metadata.version(n) for n in
        ('numpy','pandas','python-dateutil','six','tzdata','pytz')},
        support={n:digest(__import__(n,fromlist=['*']).__file__) for n in
        ('cytimes.pydt','cytimes.utils','cytimes.errors')},
        programs={str(p.relative_to(ROOT)):digest(p) for p in files})
    return {'O':(official.Configs,official.parse),'C':(Config,cython.parse),'R':(rust.Configs,rust.parse)}, identity


def observed(call, config=False):
    return engine.canonical(engine.capture(lambda:engine.cases.config_state(call()) if config else call()))


def build(impl,role,scene):
    cls,fn=impl[role]
    env=source.base.namespace('B',scene)
    env.update(cls=cls,fn=fn,ancient=date(1,1,1),copy=copy,pickle=pickle)
    cfg=cls(False,True) if scene.config_mode=='ordering' else cls()
    if scene.config_mode=='month':cfg.add_month('harvest',10)
    elif scene.config_mode=='timezone':cfg.add_tz('XYZ',8)
    elif scene.config_mode=='upstream':cfg=engine.cases.configured(cls)
    if scene.id.startswith('N'):cfg=pickle.loads(pickle.dumps(cfg))
    env['cfg']=cfg
    if scene.group=='corpus':env['corpus']=[engine.DATA['rows'][i][0] for i in json.loads((OUT/'mapping.json').read_text())['indices']]
    statement=f'result = {scene.expression}\n        del result'
    if scene.catches:statement='try:\n            '+statement.replace('\n','\n    ')+'\n        except Exception:\n            pass'
    text=f"def run(n, {', '.join(f'{k}={k}' for k in env)}):\n    for _ in range(n):\n        {statement}\n"
    exec(compile(text,'<latest-threeway-'+scene.id+'>','exec'),env)
    value=observed(lambda:eval(scene.expression,env),scene.id in ('K01','K02','K16','K18','K19','K20'))
    return env['run'],hashlib.sha256(text.encode()).hexdigest(),value


def warmed_measure(run,n):
    # Same prospective complete-batch warm-up for every role. It is outside T.
    run(n)
    result=target_measure(run,n)
    result['warmup_calls']=n
    return result


engine.measure=warmed_measure


def inventory():
    impl,identity=prepare();configs={r:engine.cases.configured(cls) for r,(cls,fn) in impl.items()}
    records=[];indices=[]
    for i,row in enumerate(engine.DATA['rows']):
        equal=True
        for j,(iso,ignore,use_cfg) in enumerate(engine.DATA['matrix']):
            outputs={r:observed(lambda r=r,fn=fn:fn(row[0],default=date(1,1,1),yearfirst=False,
                isoformat=iso,ignoretz=ignore,cfg=configs[r] if use_cfg else None)) for r,(cls,fn) in impl.items()}
            match=len({json.dumps(v,sort_keys=True) for v in outputs.values()})==1
            equal &= match
            records.append(dict(index=i,matrix=j,text=row[0],outputs=outputs,equal=match))
        if equal:indices.append(i)
    engine.save(OUT/'mapping.json',dict(indices=indices,count=len(indices),original_count=len(engine.DATA['rows']),
        source_sha256=digest(ROOT/'tests/parser/data/upstream_datetimes.json'),records=records))
    rows=[]
    for s in SCENES:
        built={r:build(impl,r,s) for r in ROLES}
        same=len({json.dumps(v[2],sort_keys=True) for v in built.values()})==1
        rows.append(dict(scene=vars(s),same=same,comparable=same or s.group=='config',
            qualification=None if same else 'Configuration operation cost only; rule contents / copy semantics differ' if s.group=='config' else 'Different result; excluded from common performance',
            outputs={r:v[2] for r,v in built.items()},sources={r:v[1] for r,v in built.items()}))
        assert len({v[1] for v in built.values()})==1
    engine.save(OUT/'inventory.json',dict(identity=identity,scenes=rows,
        unsupported=['C01: Configs subclass is intentionally unsupported in Rust','K04/K17: Rust query methods are private'],
        mapping=dict(total=len(records),equal=sum(r['equal'] for r in records),common_strings=len(indices))))
    print('INVENTORY',len(rows),'comparable',sum(r['comparable'] for r in rows),'common strings',len(indices),flush=True)


def control(output, deadline, ids=None, target=10):
    impl,identity=prepare();proof=clocks();engine.save(output/'clock.json',proof)
    cfg=dict(identity=engine.identity_key(identity),clock_config=dict(clock_uncertainty_ns=max(1000,clock_bound(proof))),
        rows={},orders=engine.ORDERS,groups_per_process=12,pids_per_round=3,rounds=2,
        warmup='one complete identical batch immediately before each timed batch')
    inventory=json.loads((OUT/'inventory.json').read_text())
    selected={r['scene']['id'] for r in inventory['scenes'] if r['comparable']}
    with (output/'controls.jsonl').open('w') as stream:
        for s in SCENES:
            if s.id not in selected or ids and s.id not in ids:continue
            runs={r:build(impl,r,s)[0] for r in ROLES};n=1
            for _ in range(6):
                values={r:target_measure(run,n) for r,run in runs.items()}
                fastest=min(min(v['T'],v['CPU']) for v in values.values())
                if fastest>=target*900000:break
                n=max(n+1,math.ceil(n*target*1000000/max(1,fastest)))
            span=max(250000000,math.ceil(sum(v['T'] for v in values.values())*3/50000000)*50000000)
            short=[];long=[]
            for block in range(6):
                short+=engine.groups(runs,n,span,2,cfg['clock_config'],deadline,stream,s.id+':short',offset=2*block)
                long+=engine.groups(runs,n*3,span*3,1,cfg['clock_config'],deadline,stream,s.id+':long',offset=block)
            a=engine.summarize(short) if len(short)==12 else None
            b=engine.summarize(long) if len(long)==6 else None
            precision={k:engine.spread([a['ratios'][k],b['ratios'][k]]) for k in engine.PAIRS} if a and b else {}
            cfg['rows'][s.id]=dict(n=n,span_ns=span,target_ms=target,short=a,long=b,precision=precision,
                ready=bool(precision) and max(precision.values())<=.03,scene=vars(s))
            engine.save(output/'config.json',cfg)
            print('CONTROL',s.id,cfg['rows'][s.id]['ready'],precision,flush=True)
            if time.monotonic()>=deadline:break


def collect(config,output,index,deadline):
    cfg=json.loads(config.read_text());impl,identity=prepare()
    assert engine.identity_key(identity)==cfg['identity']
    proof=clocks();engine.save(output.with_suffix('.clock.json'),proof)
    assert clock_bound(proof)<=cfg['clock_config']['clock_uncertainty_ns']
    selected=[s for s in SCENES if s.id in cfg['rows']]
    offset=(index*13)%len(selected);selected=selected[offset:]+selected[:offset]
    runs={s.id:{r:build(impl,r,s)[0] for r in ROLES} for s in selected};rows={s.id:[] for s in selected}
    with output.with_suffix('.jsonl').open('w') as stream:
        for sweep in range(2):
            for s in (selected if sweep==0 else list(reversed(selected))):
                c=cfg['rows'][s.id]
                rows[s.id]+=engine.groups(runs[s.id],c['n'],c['span_ns'],6,cfg['clock_config'],deadline,stream,s.id,offset=sweep*6)
                engine.save(output,dict(identity=identity,config_sha256=digest(config),rows=rows,
                    complete=all(len(v)==12 for v in rows.values())))
                if len(rows[s.id])!=(sweep+1)*6:raise TimeoutError('Original order slots incomplete')
    print('COMPLETE',index,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['inventory','control','collect'])
    p.add_argument('--output',type=Path,default=OUT);p.add_argument('--config',type=Path)
    p.add_argument('--ids',nargs='*');p.add_argument('--target',type=float,default=10)
    p.add_argument('--index',type=int,default=0);p.add_argument('--seconds',type=float,default=900)
    a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True);deadline=time.monotonic()+a.seconds
    if a.mode=='inventory':OUT.mkdir(exist_ok=True);inventory()
    elif a.mode=='control':a.output.mkdir(exist_ok=True);control(a.output,deadline,a.ids,a.target)
    else:collect(a.config,a.output,a.index,deadline)
