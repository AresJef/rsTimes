"""Task-specific Pydt inputs on the existing paired collector and quality rules."""
from pathlib import Path
from datetime import date, datetime, time as clock, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo
from collections import Counter
import argparse, copy, hashlib, importlib.metadata as metadata, json, math, os, pickle, statistics as st, sys, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks import pydt_benchmark as shared
from benchmarks import parser_objects as cycles
from benchmarks import parser_behavior as b
from benchmarks.delta import bench as transport
from benchmarks.parser_timing import measure, clocks
from benchmarks.parser_quality import clock_bound
from benchmarks.parser_prewarm import prepare_cpu
HERE=ROOT/'tasks/evidence/pydt-refactor-opt-20261017'
INPUTS=HERE/'performance-inputs.json'
ROWS=json.loads(INPUTS.read_text())['rows']
REFERENCE=None
ALLOW_DIFFERENCES=False
CPU_PREWARM_IDS=frozenset(('F158',))
HASH_SEED=None
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical(value, clock_shape=False):
    if isinstance(value,datetime):
        off=value.utcoffset()
        return dict(type=type(value).__name__,fields=None if clock_shape else [getattr(datetime,k).__get__(value) for k in ('year','month','day','hour','minute','second','microsecond')],fold=datetime.fold.__get__(value),tz=str(datetime.tzinfo.__get__(value)),offset=None if off is None else (off.days*86400+off.seconds)*1000000+off.microseconds)
    if isinstance(value,(tuple,list)):
        return dict(type=type(value).__name__,values=[canonical(v,clock_shape) for v in value])
    if isinstance(value,dict):return {str(k):canonical(v,clock_shape) for k,v in value.items()}
    if value is None or isinstance(value,(str,bool,int,float)):return value
    return dict(type=type(value).__name__,value=repr(value))


def worker():
    qos=transport.measurement_qos(sys.argv[sys.argv.index('--measurement-qos')+1])
    os.environ['TZ']='Asia/Shanghai';time.tzset()
    import rstimes, numpy as np
    from dateutil.relativedelta import relativedelta
    P=rstimes.Pydt
    epoch = getattr(rstimes, "parse_to_epoch", None)
    if epoch is None: epoch = rstimes.parse_epoch
    class Child(P):pass
    cfg=rstimes.Configs();cfg.add_tzone('America/New_York')
    env=dict(P=P,Pydt=P,Configs=rstimes.Configs,Delta=rstimes.Delta,parse=rstimes.parse,parse_str=rstimes.parse_str,parse_epoch=epoch,datetime=datetime,date=date,clock=clock,timedelta=timedelta,timezone=timezone,tzinfo=tzinfo,ZoneInfo=ZoneInfo,np=np,copy=copy,pickle=pickle,relativedelta=relativedelta,NY=ZoneInfo('America/New_York'),UTC=timezone.utc,cfg=cfg)
    env.update(p=P(2024,5,7,15,30,1,123456,fold=0),child=Child(2024,5,7,15,30,1,123456,fold=0),dt=datetime(2024,5,7,15,30,1,123456),delta=rstimes.Delta(months=1,days=3,hours=2),delta2=rstimes.Delta(years=1,days=2))
    env['values']=[env['dt']+timedelta(days=i) for i in range(1024)]
    built={};sources={};observed={};runnable=[];hash_values={}
    for row in ROWS:
        scope=dict(env);exec(row['setup'],scope)
        expression=row['expression']
        source=f"def run(n, {', '.join(f'{k}={k}' for k in scope)}):\n    for _ in range(n):\n        result = {expression}\n        del result\n"
        exec(compile(source,'<pydt-refactor-'+row['id']+'>','exec'),scope)
        built[row['id']]=scope['run'];sources[row['id']]=hashlib.sha256(source.encode()).hexdigest()
        try:
            value=eval(expression,scope)
            if row['api']=='__hash__':hash_values[row['id']]=dict(value=value,bits=abs(value).bit_length())
            observed[row['id']]=dict(type=type(value).__name__,repeat_consistent=value==eval(expression,scope)) if row['api']=='__hash__' else canonical(value,row['output']=='clock_shape')
            runnable.append(row['id'])
        except Exception as error:observed[row['id']]=dict(error=type(error).__name__,message=str(error))
    native=Path(rstimes._native.__file__).resolve()
    identity=dict(pid=os.getpid(),python=sys.version,executable=sys.executable,version=metadata.version('rstimes'),native=str(native),native_sha256=sha(native),entrypoint='rstimes.Pydt and shared guard APIs',dependencies={n:metadata.version(n) for n in ('cytimes','numpy','pandas','python-dateutil','six','tzdata','pytz','Babel')},source=sources,observed=observed,runnable=runnable,qos=qos,support={name:sha(__import__(name,fromlist=['*']).__file__) for name in ('cytimes.pydt','cytimes.utils','cytimes.errors','cytimes.parser')},python_implementation=sha(__import__(P.__module__,fromlist=['*']).__file__),preparation={r['id']:('same_n_then_cpu20ms' if r['id'] in CPU_PREWARM_IDS else 'same_n') for r in ROWS})
    identity['runtime']=dict(hash_seed=os.environ.get('PYTHONHASHSEED'),safe_path=getattr(sys.flags,'safe_path',None),no_user_site=sys.flags.no_user_site,ignore_environment=sys.flags.ignore_environment,isolated=sys.flags.isolated,hash_randomization=sys.flags.hash_randomization)
    identity['hash_values']=hash_values
    assert rstimes._native.release_build()
    print(json.dumps(identity),flush=True)
    for line in sys.stdin:
        req=json.loads(line)
        if req.get('op')=='host':out=clocks()
        else:
            run=built[req['id']]
            if req.get('warmup_count'):run(req['warmup_count'])
            proof=prepare_cpu(run,20_000_000,100_000_000) if req['id'] in CPU_PREWARM_IDS else None
            out=measure(run,req['count']);out.update(pid=os.getpid(),benchmark_case=req['id'])
            if proof is not None:
                out.update(warmup_policy='cpu20ms',warmup_ready=proof['ready'],warmup_cpu=proof)
        print(json.dumps(out),flush=True)


class Pool:
    def __init__(self,candidate,matrix='pydt'):
        self.processes={};transport.SELF=Path(__file__).resolve()
        previous={key:os.environ.get(key) for key in ('PYTHONHASHSEED','TZ')} if HASH_SEED is None else {}
        try:
            if HASH_SEED is None:os.environ.update(PYTHONHASHSEED='0',TZ='Asia/Shanghai')
            for role,env in (('A',REFERENCE),('B',candidate)):
                self.processes[role]=transport.Process(env,role,'all',qos_policy='interactive',variant='pydt-refactor',hash_seed=HASH_SEED)
            self.identity={r:p.metadata for r,p in self.processes.items()}
            if HASH_SEED is not None:
                assert self.identity['A']['runtime']==self.identity['B']['runtime']
                assert self.identity['A']['hash_values']==self.identity['B']['hash_values']
                runtime=self.identity['A']['runtime']
                assert runtime['safe_path'] is True and runtime['no_user_site']==1 and runtime['ignore_environment']==0 and runtime['hash_seed']==str(HASH_SEED)
            for name in ('python','dependencies','support','qos','source','entrypoint'):
                assert self.identity['A'][name]==self.identity['B'][name],name
            if not ALLOW_DIFFERENCES:
                assert self.identity['A']['observed']==self.identity['B']['observed'],'behavior differs'
                assert len(self.identity['A']['runnable'])==len(ROWS),'invalid B0 representative'
        except BaseException:self.close();raise
        finally:
            for key,value in previous.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
    def runs(self,ident,warmup=0):return {r:b.Run(p,ident,warmup) for r,p in self.processes.items()}
    def clocks(self):
        proof={r:p.short_info() for r,p in self.processes.items()}
        return proof,max(clock_bound(v) for v in proof.values())
    def close(self):
        for p in reversed(list(self.processes.values())):p.close()


_original_control = b.control
_original_quality = b.quality


def prepared_quality(value, config):
    """Require the existing bounded CPU preparation proof on its selected case."""
    if value.get('benchmark_case') in CPU_PREWARM_IDS:
        return _original_quality(value, dict(config, warmup_policy='cpu20ms'))
    return _original_quality(value, config)


def length_control(*args, **kwargs):
    """Check each implementation's T/n as well as the paired speed ratio."""
    row = _original_control(*args, **kwargs)
    row['ratio_precision'] = row['precision']
    row['role_precision'] = {
        role: b.engine.spread([row['short']['ns'][role], row['long']['ns'][role]])
        if row['precision'] is not None else None
        for role in ('A', 'B')
    }
    if row['precision'] is not None:
        row['precision'] = max(row['precision'], *row['role_precision'].values())
    row['ready'] = row['precision'] is not None and row['precision'] <= .03
    return row


def report(args):
    cfg=json.loads(args.config.read_text());ids=args.ids or list(cfg['rows']);result={i:dict(rounds={}) for i in ids};pids=[];audit=Counter()
    for name in ('main','independent'):
        data=[json.loads((args.output/name/f'cycle-{i}.json').read_text()) for i in range(9)]
        for cycle in data:
            assert cycle['complete'] and cycle['config_sha256']==sha(args.config)
            for role in 'AB':
                for field in ('native_sha256', 'version', 'python_implementation', 'dependencies', 'source', 'observed', 'qos', 'preparation')+tuple(f for f in ('runtime','hash_values') if f in cfg['identity'][role]):
                    assert cycle['identity'][role][field] == cfg['identity'][role][field], (role, field)
            pids.extend(cycle['identity'][r]['pid'] for r in 'AB')
            for ident in ids:
                values=cycle['rows'][ident]
                assert len(values)==12 and Counter(v['order'] for v in values)==Counter(AB=6,BA=6)
                for v in values:
                    assert v['valid'] and v['n']==cfg['rows'][ident]['n']
                    assert all(v['checks'][r]['status']=='VALID' and v['members'][r]['pid']==cycle['identity'][r]['pid'] for r in 'AB')
                    audit['accepted_pairs']+=1
        for ident in ids:
            values=[st.median(v['R'] for v in c['rows'][ident]) for c in data]
            groups,median=cycles.levels(values)
            orders=[cycles.levels([st.median(v['R'] for v in c['rows'][ident] if v['order']==o) for c in data])[1] for o in ('AB','BA')]
            result[ident]['rounds'][name]=dict(median=median,groups=groups,conservative=min(median,*groups),group_spread=b.engine.spread(groups),order_spread=b.engine.spread(orders),cycles=values,ns={r:cycles.levels([st.median(v['members'][r]['T']/v['n'] for v in c['rows'][ident]) for c in data])[1] for r in 'AB'})
    assert len(pids)==len(set(pids))==36
    by_id={r['id']:r for r in ROWS}
    for ident,row in result.items():
        a,z=row['rounds'].values();cross=b.engine.spread([a['median'],z['median']]);stable=max(a['group_spread'],z['group_spread'],a['order_spread'],z['order_spread'],cross)<=.05
        row.update(precision=cfg['rows'][ident]['precision'],cross_spread=cross,stable=stable,minimum_ratio=1/1.05)
        row['status']='INCONCLUSIVE' if not stable or not cfg['rows'][ident]['ready'] else 'OBSERVATION' if not by_id[ident]['required'] else 'PASS' if min(v['conservative'] for v in row['rounds'].values())>=1/1.05 else 'FAIL'
    geo=lambda values:math.exp(st.mean(math.log(v) for v in values))
    combinations={}
    for name in ('main','independent'):
        families={family:[r for r in ROWS if r['id'] in result and r['family']==family] for family in sorted({r['family'] for r in ROWS})}
        summary={}
        for family,members in families.items():
            if not members:continue
            values=[result[r['id']]['rounds'][name] for r in members]
            median=geo([v['median'] for v in values]);groups=[geo([v['groups'][i] for v in values]) for i in range(3)]
            summary[family]=dict(median=median,groups=groups,conservative=min(median,*groups),count=len(members))
        values=[v for f,v in summary.items() if f.startswith('B') and len(f)==3]
        combinations[name]=dict(families=summary,broad=dict(median=geo([v['median'] for v in values]),groups=[geo([v['groups'][i] for v in values]) for i in range(3)])) if values else dict(families=summary)
        if values:
            v=combinations[name]['broad'];v['conservative']=min(v['median'],*v['groups'])
        for raw in (args.output/name).glob('*.jsonl'):
            for line in raw.read_text().splitlines():
                v=json.loads(line);audit['attempts']+=1
                if not v['valid']:audit['rejected_pairs']+=1
    b.save(args.output/'report.json',dict(rows=result,combinations=combinations,audit=dict(audit),real_worker_pids=pids,config_sha256=sha(args.config),status='PROTECTION_PASS' if all(r['status'] in ('PASS','OBSERVATION') for r in result.values()) else 'NOT_PASSED'))
    print(json.dumps(dict(rows=Counter(r['status'] for r in result.values()),combinations=combinations,audit=dict(audit))),flush=True)


if __name__=='__main__':
    if '--worker' in sys.argv:worker()
    else:
        p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['identity','prepare','pilot','collect','report']);p.add_argument('--reference',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--ids',nargs='*');p.add_argument('--minutes',type=float,default=10);p.add_argument('--target-ms',type=float,default=10);p.add_argument('--allow-behavior-differences',action='store_true')
        args=p.parse_args();REFERENCE=args.reference;ALLOW_DIFFERENCES=args.allow_behavior_differences
        b.control=length_control
        b.quality=prepared_quality
        shared.PROGRAMS=(*shared.PROGRAMS,ROOT/'benchmarks/parser_prewarm.py')
        shared.ROWS=ROWS;shared.Pool=Pool;shared.PROGRAMS=(*shared.PROGRAMS,Path(__file__),INPUTS)
        if args.mode=='identity':
            pool=Pool(args.candidate)
            try:args.output.mkdir(parents=True,exist_ok=True);b.save(args.output/'identity.json',pool.identity);print('Identities and',len(ROWS),'representatives verified')
            finally:pool.close()
        elif args.mode=='prepare':shared.prepare(args)
        elif args.mode in ('pilot','collect'):shared.collect(args,args.mode=='pilot')
        else:report(args)
