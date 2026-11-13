"""Compare three fixed Parser artifacts using local inputs and existing clocks.

This is a bounded comparison tool, not an implementation or optimization path.
Normal datetime values retain type, fields, timezone and fold. Only documented
package/class moves are normalized; other differences remain in the report.
"""
from datetime import date, datetime
from pathlib import Path
import argparse
import collections
import copy
import hashlib
import importlib.metadata as metadata
import importlib.util
import itertools
import json
import math
import os
import pickle
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.local/parser-threeway-20261015/site'))
from benchmarks import parser_scenarios as workloads
from benchmarks.parser_quality import quality, clock_bound
from benchmarks.parser_timing import clocks, measure as target_measure
from benchmarks.parser_prewarm import prepare_cpu
from benchmarks.delta.bench import measurement_qos

SPEC = importlib.util.spec_from_file_location('_threeway_cases', ROOT / 'tests/parser/cases.py')
cases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cases)
DATA = json.loads((ROOT / 'tests/parser/data/upstream_datetimes.json').read_text())
ROLES = 'ORC'
ORDERS = tuple(''.join(x) for x in itertools.permutations(ROLES))
PAIRS = {'official/rust': ('O', 'R'), 'official/cython': ('O', 'C'), 'cython/rust': ('C', 'R')}


def measure(run, n):
    proof = prepare_cpu(run, 20_000_000)
    value = target_measure(run, n)
    value.update(warmup_cpu=proof, warmup_ready=proof['ready'])
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + '\n')


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, str):
        value = value.replace('cytimes_rewrite.errors.', 'cytimes.errors.')
        for old in ('cytimes.parser.Configs', 'rstimes.parser.Configs', 'cytimes_rewrite.config.Config'):
            value = value.replace('expected ' + old + ',', 'expected cytimes.parser.Config,')
        value = value.replace("<'Configs'>", "<'Config'>").replace("<'Configs' (", "<'Config' (")
        for namespace in cases.NAMES:
            value = value.replace("'Configs." + namespace + "'", "'Config." + namespace + "'")
    return value


def capture(call):
    try:
        return {'value': cases.value(call())}
    except BaseException as error:
        return {'error': cases.exception(error)}


def prepare():
    import cytimes.parser as official
    import rstimes.parser as rust
    import rstimes._native as native
    import cytimes_rewrite.parser as cython
    from cytimes_rewrite import Config
    assert metadata.version('cytimes') == '3.1.0'
    assert metadata.version('rstimes') == '0.1.0+parser.1'
    assert metadata.version('cytimes-rewrite') == '0.3.0'
    assert native.release_build()
    assert digest(official.__file__) == 'b507cada977d0e0ea4f22d0f9fd34bbac117ac6c14fc807128418f44ca7b85ca'
    assert digest(native.__file__) == 'bf15d9e7871c6bb377c4c22b0a8b63c9cce5b6ed14aa0d6ba3b828fb7f36ff3e'
    assert digest(cython.__file__) == '4c89e4c8793b1be633868f592e2a29c039194eff65a7ea1c8ac5737bc1b8fb65'
    implementations = {'O': (official.Configs, official.parse), 'R': (rust.Configs, rust.parse), 'C': (Config, cython.parse)}
    identity = dict(pid=os.getpid(), python=sys.version, executable=sys.executable,
                    qos=measurement_qos('initiated'), versions={n: metadata.version(n) for n in ('cytimes', 'rstimes', 'cytimes-rewrite')},
                    modules={r: {'path': str(Path(m.__file__).resolve()), 'sha256': digest(m.__file__)} for r,m in zip(ROLES,(official,native,cython))},
                    dependencies={n: metadata.version(n) for n in ('numpy','pandas','python-dateutil','six','tzdata','pytz')},
                    programs={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__), ROOT/'benchmarks/parser_scenarios.py',ROOT/'benchmarks/parser_quality.py',ROOT/'benchmarks/parser_timing.py',ROOT/'benchmarks/parser_prewarm.py',ROOT/'tests/parser/cases.py',ROOT/'tests/parser/data/upstream_datetimes.json')})
    return implementations, identity


def identity_key(identity):
    return {k:v for k,v in identity.items() if k not in ('pid','executable')}


def functional(output):
    impl, identity = prepare()
    records = []
    configured = {r: cases.configured(cls) for r,(cls,fn) in impl.items()}
    def record(ident, category, values, text=None, options=None):
        normalized = {r: canonical(v) for r,v in values.items()}
        records.append(dict(id=ident, category=category, text=text, options=options, outputs=values,
                            rust_matches=normalized['R']==normalized['O'],cython_matches=normalized['C']==normalized['O'], rewrites_equal=normalized['R']==normalized['C']))
    for index,row in enumerate(DATA['rows']):
        for position,(iso,ignore,use_cfg) in enumerate(DATA['matrix']):
            kwargs=dict(default=date(1,1,1),yearfirst=False,isoformat=iso,ignoretz=ignore)
            results={r:capture(lambda fn=fn,r=r:fn(row[0],cfg=configured[r] if use_cfg else None,**kwargs)) for r,(cls,fn) in impl.items()}
            record(f'upstream:{index}:{position}','upstream',results,row[0],dict(isoformat=iso,ignoretz=ignore,configured=use_cfg))
    for index,case in enumerate(cases.parse_cases()):
        results={r:cases.parse_outcome(fn,cls,case) for r,(cls,fn) in impl.items()}
        record(f'extended:{index}',case['category'],results,case['text'],case['kwargs'])
    transcripts={r:cases.config_transcript(cls) for r,(cls,fn) in impl.items()}
    assert len({len(v) for v in transcripts.values()})==1
    for index in range(len(transcripts['O'])):
        record(f'config:{index}','config',{r:v[index] for r,v in transcripts.items()})
    class DateChild(datetime):
        pass
    class Text(str):
        pass
    class Truth:
        def __bool__(self):raise RuntimeError('truth callback')
    from pandas import Timestamp
    constructors=[('datetime',datetime),('subclass',DateChild),('Timestamp',Timestamp),('callable',lambda **k:datetime(**k)),('returns_none',lambda **k:None),('wrong_return',lambda **k:()),('int',int),('date',date)]
    for name,constructor in constructors:
        for ignore in (True,False):
            text='August 2, 2023 12:01 UTC'
            record('constructor:'+name+':'+str(ignore),'constructor',{r:capture(lambda fn=fn:fn(text,dtclass=constructor,ignoretz=ignore)) for r,(cls,fn) in impl.items()},text,{'constructor':name,'ignoretz':ignore})
    for text in (None,3,b'2024-01-01',Text('2024-01-01'),'\ud800','\ud800 12:34'):
        record('input:'+repr(text),'input-type',{r:capture(lambda fn=fn:fn(text)) for r,(cls,fn) in impl.items()},repr(text))
    for flag in ('yearfirst','dayfirst'):
        record('truth:'+flag,'dynamic',{r:capture(lambda fn=fn:fn('2024-01-01',**{flag:Truth()})) for r,(cls,fn) in impl.items()})
    for mode in ('instance','getattribute','int'):
        results={}
        for r,(base,fn) in impl.items():
            class IntOnly:
                def __int__(self):return 12
            class Custom(base):
                def __getattribute__(self,name):
                    if mode=='getattribute' and name=='get_month':return lambda token:12 if token=='drift' else -1
                    return super().__getattribute__(name)
                def get_month(self,token):
                    if mode=='int' and token=='drift':return IntOnly()
                    return super().get_month(token)
            cfg=Custom()
            if mode=='instance':cfg.get_month=lambda token:12 if token=='drift' else -1
            results[r]=capture(lambda:fn('15 drift 2024',cfg=cfg,isoformat=False))
        record('dynamic:'+mode,'dynamic',results,'15 drift 2024')
    for method in ('copy','deepcopy','pickle'):
        results={}
        for r,(cls,fn) in impl.items():
            def scenario(cls=cls):
                cfg=cls(False,True);cfg.add_month('harvest',10)
                restored=copy.copy(cfg) if method=='copy' else copy.deepcopy(cfg) if method=='deepcopy' else pickle.loads(pickle.dumps(cfg))
                cfg.add_month('aftercopy',11)
                return dict(month=restored.month,yearfirst=restored.yearfirst,dayfirst=restored.dayfirst)
            results[r]=capture(scenario)
        record('restore:'+method,'restore',results)
    results={}
    for r,(cls,fn) in impl.items():
        def scenario(fn=fn):
            events=[]
            def factory(**kwargs):
                events.append((list(kwargs),type(kwargs['fold']).__name__))
                return datetime(**kwargs)
            result=fn('2024-01-01',dtclass=factory)
            return [cases.value(result),events]
        results[r]=capture(scenario)
    record('constructor:keywords','dynamic',results)
    safety=[]
    for ident,call in [('long-year',lambda cls,fn:fn('9'*40)),('long-fraction',lambda cls,fn:fn('12.'+'9'*40+'h',default=date(2024,1,1))),('timezone-overflow',lambda cls,fn:cls().add_tz('huge',hours=2**30)),('empty-state',lambda cls,fn:cls().__setstate__(())),('none-state',lambda cls,fn:cls().__setstate__(None)),('wide-minute',lambda cls,fn:fn('1:4294967297',default=date(2024,1,1)))]:
        safety.append(dict(id=ident,official='Not executed: known unsafe arithmetic/state input; documented approved safety boundary.',outputs={r:capture(lambda cls=cls,fn=fn:call(cls,fn)) for r,(cls,fn) in impl.items() if r!='O'}))
    differences=[v for v in records if not v['rust_matches'] or not v['cython_matches']]
    api={r:dict(configuration=cls.__module__+'.'+cls.__name__,parse_module=fn.__module__,members=sorted(x for x in dir(cls) if not x.startswith('_')),parser_helpers={n:hasattr(sys.modules[fn.__module__],n) for n in ('Parser','timelex','parse_obj')}) for r,(cls,fn) in impl.items()}
    summary={category:{'count':sum(x['category']==category for x in records),'rust_different':sum(x['category']==category and not x['rust_matches'] for x in records),'cython_different':sum(x['category']==category and not x['cython_matches'] for x in records)} for category in sorted({x['category'] for x in records})}
    save(output/'functional.json',dict(identity=identity,calls=len(records),groups=summary,differences=differences,records=records,safety=safety,api=api,normalization='Only approved package-error paths and Cython Config rename; actual datetime type and all other messages/causes remain compared.'))
    print('FUNCTIONAL',len(records),'differences',len(differences),summary,flush=True)


def build(impl,role,scene):
    env=workloads.namespace('A' if role=='O' else 'B',scene)
    cls,fn=impl[role];env['cls'],env['fn']=cls,fn
    cfg=cls(False,True) if scene.config_mode=='ordering' else cls()
    if scene.config_mode=='month':cfg.add_month('harvest',10)
    elif scene.config_mode=='timezone':cfg.add_tz('XYZ',8)
    elif scene.config_mode=='subclass':
        class Custom(cls):
            def get_month(self,token):return super().get_month(token)
        cfg=Custom()
    env['cfg']=cfg
    statement=f'result = {scene.expression}\n        del result'
    if scene.catches:statement='try:\n            '+statement.replace('\n','\n    ')+'\n        except Exception:\n            pass'
    text=f"def run(n, {', '.join(f'{k}={k}' for k in env)}):\n    for _ in range(n):\n        {statement}\n"
    exec(compile(text,'<threeway-'+scene.id+'>','exec'),env)
    value=capture(lambda:cases.config_state(eval(scene.expression,env)) if scene.id in ('K01','K02','K16') else eval(scene.expression,env))
    return env['run'],text,canonical(value)


def spread(values):return max(values)/min(values)-1


def summarize(rows):
    values={k:statistics.median(x['ratios'][k] for x in rows) for k in PAIRS}
    orders={o:{k:statistics.median(x['ratios'][k] for x in rows if x['order']==o) for k in PAIRS} for o in ORDERS if any(x['order']==o for x in rows)}
    return dict(count=len(rows),ratios=values,order_spread={k:spread([v[k] for v in orders.values()]) for k in PAIRS},orders=orders,ns={r:statistics.median(x['members'][r]['T']/x['n'] for x in rows) for r in ROLES})


def groups(runs,n,span,count,cfg,deadline,stream,tag,offset=0,max_attempts=None):
    result=[];attempt=0
    while len(result)<count and time.monotonic()<deadline and (max_attempts is None or attempt<max_attempts):
        slot=offset+len(result);order=ORDERS[slot%6];begin=time.perf_counter_ns();members={r:measure(runs[r],n) for r in order};checks={r:quality(x,cfg) for r,x in members.items()};elapsed=time.perf_counter_ns()-begin;valid=all(x['status']=='VALID' for x in checks.values()) and elapsed<=span
        row=dict(pid=os.getpid(),tag=tag,slot=slot,attempt=attempt,order=order,n=n,members=members,checks=checks,span_ns=elapsed,max_span_ns=span,valid=valid)
        if valid:
            row['ratios']={k:members[a]['T']/members[b]['T'] for k,(a,b) in PAIRS.items()};result.append(row)
        stream.write(json.dumps(row)+'\n');stream.flush();attempt+=1
        if any(x['status']=='ERROR' for x in checks.values()):raise RuntimeError('Clock ERROR; retain data')
    return result


def calibrate(output,deadline):
    impl,identity=prepare();proof=clocks();cfg=dict(clock_uncertainty_ns=max(166,clock_bound(proof)),warmup_policy='cpu20ms');save(output/'clock.json',proof);rows={};excluded=[]
    with (output/'controls.jsonl').open('w') as stream:
        for scene in workloads.SCENES:
            built={r:build(impl,r,scene) for r in ROLES};outputs=[x[2] for x in built.values()]
            if outputs[1:]!=outputs[:-1]:
                excluded.append(dict(id=scene.id,reason='Output differs; not a common workload',outputs={r:x[2] for r,x in built.items()}));continue
            runs={r:x[0] for r,x in built.items()}
            for run in runs.values():run(2000)
            n=200
            for _ in range(4):
                preliminary={r:measure(run,n) for r,run in runs.items()};fast=min(x['T'] for x in preliminary.values())
                if fast>=8_000_000:break
                n=max(n+1,math.ceil(n*10_000_000/max(fast,1)))
            attempts=[];chosen=None
            for factor in (1,2):
                count=n*factor;pre={r:measure(run,count) for r,run in runs.items()};total=sum(x['T'] for x in pre.values());warm=sum(x['warmup_cpu']['T'] for x in pre.values());span=max(250_000_000,math.ceil((total+warm)*1.15/50_000_000)*50_000_000);long_span=max(250_000_000,math.ceil((total*3+warm)*1.15/50_000_000)*50_000_000)
                if span>1_500_000_000:continue
                a=groups(runs,count,span,12,cfg,deadline,stream,scene.id+':short',max_attempts=120);b=groups(runs,count*3,long_span,6,cfg,deadline,stream,scene.id+':long',max_attempts=60)
                if len(a)!=12 or len(b)!=6:continue
                short,long=summarize(a),summarize(b);diff={k:spread([short['ratios'][k],long['ratios'][k]]) for k in PAIRS};ready=max(diff.values())<=.03 and max([*short['order_spread'].values(),*long['order_spread'].values()])<=.03
                trial=dict(n=count,span_ns=span,long_span_ns=long_span,short=short,long=long,precision=diff,ready=ready);attempts.append(trial)
                if ready:chosen=trial;break
            rows[scene.id]=dict(chosen=chosen,attempts=attempts,group=scene.group,label=scene.label,expression=scene.expression,text=scene.text,loop_sha256=hashlib.sha256(built['O'][1].encode()).hexdigest())
            print('CAL',scene.id,bool(chosen),flush=True)
            save(output/'provisional.json',dict(identity=identity_key(identity),clock_config=cfg,rows=rows,excluded=excluded,orders=ORDERS,groups_per_process=12,pids_per_round=3,rounds=2,warmup_calls=2000,purpose='New direct comparison, not replacement of either project acceptance.'))
            if time.monotonic()>=deadline:break
    frozen=json.loads((output/'provisional.json').read_text());frozen['rows']={k:v for k,v in rows.items() if v['chosen']};frozen['unready']={k:v for k,v in rows.items() if not v['chosen']};frozen['status']='READY' if frozen['rows'] else 'INSUFFICIENT';save(output/'frozen.json',frozen)


def collect(args):
    cfg=json.loads(args.config.read_text());impl,identity=prepare();assert identity_key(identity)==cfg['identity'];proof=clocks();save(args.output.with_suffix('.clock.json'),proof)
    if clock_bound(proof)>cfg['clock_config']['clock_uncertainty_ns']:raise RuntimeError('Clock bound exceeds frozen proof')
    selected=[s for s in workloads.SCENES if s.id in cfg['rows']];offset=(args.index*7)%len(selected);selected=selected[offset:]+selected[:offset];rows={};raw={s.id:[] for s in selected};runs={s.id:{r:build(impl,r,s)[0] for r in ROLES} for s in selected}
    with args.output.with_suffix('.jsonl').open('w') as stream:
        for sweep in range(2):
            for s in (selected if sweep==0 else list(reversed(selected))):
                for run in runs[s.id].values():run(cfg['warmup_calls'])
                trial=cfg['rows'][s.id]['chosen'];result=groups(runs[s.id],trial['n'],trial['span_ns'],6,cfg['clock_config'],args.deadline,stream,s.id,offset=sweep*6);raw[s.id]+=result;rows[s.id]=summarize(raw[s.id]) if raw[s.id] else {'count':0}
                save(args.output,dict(identity=identity,config_sha256=digest(args.config),rows=rows,complete=len(rows)==len(selected) and all(x['count']==12 for x in rows.values())))
                if len(result)!=6:raise RuntimeError('Incomplete original slots; retain evidence')
    print('COLLECT DONE',args.index,flush=True)


def preview(args):
    cfg=json.loads(args.config.read_text());impl,identity=prepare();assert identity_key(identity)==cfg['identity'];proof=clocks();rows={};qc=dict(cfg['clock_config'],clock_uncertainty_ns=max(clock_bound(proof),cfg['clock_config']['clock_uncertainty_ns']))
    with args.output.with_suffix('.jsonl').open('w') as stream:
        for s in workloads.SCENES:
            if s.id not in ('B03','B12','B17','B31','K01','K05','C01','C05') or s.id not in cfg['rows']:continue
            runs={r:build(impl,r,s)[0] for r in ROLES}
            for run in runs.values():run(2000)
            trial=cfg['rows'][s.id]['chosen'];values=groups(runs,trial['n'],trial['span_ns'],6,qc,args.deadline,stream,s.id,max_attempts=120)
            rows[s.id]=summarize(values) if len(values)==6 else {'count':len(values)}
    save(args.output,dict(identity=identity,clock_bound_ns=clock_bound(proof),rows=rows,purpose='Readiness/cost preview only, never formal evidence.'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('functional','calibrate','collect','preview'));parser.add_argument('--output',type=Path,required=True);parser.add_argument('--config',type=Path);parser.add_argument('--index',type=int);parser.add_argument('--deadline',type=float,required=True);args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.mode in ('functional','calibrate'):args.output.mkdir(exist_ok=True)
    if args.mode=='functional':functional(args.output)
    elif args.mode=='calibrate':calibrate(args.output,args.deadline)
    elif args.mode=='collect':collect(args)
    else:preview(args)


if __name__=='__main__':main()
