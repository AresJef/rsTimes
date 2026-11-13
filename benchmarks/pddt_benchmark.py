"""Pddt inputs and artifact identities on the existing paired timing collector."""
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from collections import Counter
import argparse,hashlib,importlib.metadata as metadata,json,math,os,statistics as st,sys,time,warnings
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks import parser_objects as existing
from benchmarks import parser_behavior as b
from benchmarks.delta import bench as transport
from benchmarks.parser_timing import measure,clocks
from benchmarks.parser_quality import clock_bound
EVIDENCE=ROOT/'tasks/evidence/pddt-rust-migration-20261017'
INPUTS=EVIDENCE/'performance-inputs.json'
ALL_ROWS=json.loads(INPUTS.read_text())['rows']
ROWS=ALL_ROWS
OLD=ROOT/'.local/pddt-rust-20261017/baseline-guard-env'
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
PROGRAMS=(Path(__file__),ROOT/'benchmarks/parser_objects.py',ROOT/'benchmarks/parser_behavior.py',
 ROOT/'benchmarks/parser_optimization.py',ROOT/'benchmarks/parser_benchmark.py',ROOT/'benchmarks/parser_quality.py',
 ROOT/'benchmarks/parser_timing.py',ROOT/'benchmarks/delta/bench.py',INPUTS)
DEPENDENCIES=('numpy','pandas','polars','polars-runtime-32','python-dateutil','six','pytz','Babel','cytimes')


def canonical(value):
    import numpy as np,pandas as pd
    if isinstance(value,pd.DatetimeIndex):
        return dict(kind='DatetimeIndex',length=len(value),unit=value.unit,tz=str(value.tz),name=repr(value.name),
                    sha256=hashlib.sha256(value.asi8.tobytes()).hexdigest())
    if isinstance(value,pd.Index):
        return dict(kind='Index',length=len(value),dtype=str(value.dtype),name=repr(value.name),
                    sha256=hashlib.sha256(value.to_numpy().tobytes()).hexdigest())
    if isinstance(value,datetime):
        return dict(kind='datetime',iso=value.isoformat(),fold=value.fold,tz=str(value.tzinfo))
    if isinstance(value,list):
        return dict(kind='list',length=len(value),sha256=hashlib.sha256(json.dumps([canonical(v) for v in value],sort_keys=True).encode()).hexdigest())
    if isinstance(value,np.integer):return int(value)
    if value is None or isinstance(value,(str,bool,int,float)):return value
    return repr(value)


def worker():
    role=sys.argv[sys.argv.index('--worker')+1]
    matrix=sys.argv[sys.argv.index('--variant')+1]
    qos=transport.measurement_qos(sys.argv[sys.argv.index('--measurement-qos')+1])
    import numpy as np,pandas as pd,polars as pl,rstimes,rstimes._native as native
    from rstimes import Delta,Pydt,parse,parse_str
    selected=[r for r in ALL_ROWS if r['group']==matrix]
    Pddt=None;parse_epoch=None
    if matrix!='guards':
        from rstimes import Pddt,parse_epoch
    cls=Pddt
    if role=='A' and matrix=='pandas3':cls=pd.DatetimeIndex
    elif role=='A' and matrix=='calendar':
        from cytimes import Pddt as cls
    dt=datetime(2024,5,7,15,30,1,123456)
    datetimes=[dt+timedelta(days=i) for i in range(1024)]
    dates=[value.date() for value in datetimes]
    text=[(dt.replace(microsecond=0)+timedelta(seconds=i)).isoformat() for i in range(1024)]
    nano_text=[value+'.123456789' for value in text]
    base=np.datetime64('2024-05-07T15:30:01','s').astype('i8')
    arrays={unit:(base+np.arange(10000,dtype='i8')).view('datetime64[s]').astype('datetime64['+unit+']') for unit in ('s','ms','us','ns')}
    units={} if matrix=='guards' else {unit:cls(data) for unit,data in arrays.items()}
    x=None if matrix=='guards' else cls(datetimes,**({'as_unit':'us'} if cls is not pd.DatetimeIndex else {}))
    other=None if x is None else x-pd.Timedelta(days=3)
    existing_index=pd.DatetimeIndex(arrays['us'])
    polars_data=pl.Series('time',arrays['us'][:1024])
    p=Pydt(2024,5,7,15,30,1,123456)
    delta=Delta(months=2,days=3,hours=4)
    scope=dict(pd=pd,np=np,Pddt=Pddt,Pydt=Pydt,Delta=Delta,parse=parse,parse_str=parse_str,
               parse_epoch=parse_epoch,dt=dt,datetimes=datetimes,dates=dates,text=text,nano_text=nano_text,
               arrays=arrays,units=units,x=x,other=other,existing=existing_index,polars_data=polars_data,p=p,delta=delta)
    built={};sources={};observed={}
    warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
    for row in selected:
        expression=row['reference' if role=='A' else 'candidate']
        source=f"def run(n, {', '.join(f'{k}={k}' for k in scope)}):\n    for _ in range(n):\n        result = {expression}\n        del result\n"
        local=dict(scope)
        exec(compile(source,'<pddt-'+row['id']+'>','exec'),local)
        built[row['id']]=local['run'];sources[row['id']]=hashlib.sha256(source.encode()).hexdigest()
        observed[row['id']]=canonical(eval(expression,scope))
    support={name:dict(path=str(Path(module.__file__).resolve()),sha256=digest(module.__file__)) for name in (('rstimes.pydt','rstimes.parser','rstimes','rstimes.delta')+(() if matrix=='guards' else ('rstimes.pddt',))) for module in [__import__(name,fromlist=['*'])]}
    identity=dict(pid=os.getpid(),python=sys.version,executable=sys.executable,version=metadata.version('rstimes'),
      native=str(Path(native.__file__).resolve()),native_sha256=digest(native.__file__),matrix=matrix,
      dependencies={name:metadata.version(name) for name in DEPENDENCIES},source=sources,observed=observed,qos=qos,
      entrypoint=matrix+':'+role,support=support,input_sha256=digest(INPUTS),
      input_values_sha256=hashlib.sha256(json.dumps([v.isoformat() for v in datetimes],separators=(',',':')).encode()).hexdigest())
    if matrix=='calendar':
        import cytimes.pddt as original
        identity['official_native']=dict(path=str(Path(original.__file__).resolve()),sha256=digest(original.__file__))
    assert native.release_build()
    print(json.dumps(identity),flush=True)
    for line in sys.stdin:
        req=json.loads(line)
        if req.get('op')=='host':out=clocks()
        else:
            run=built[req['id']]
            if req.get('warmup_count'):run(req['warmup_count'])
            out=measure(run,req['count']);out['pid']=os.getpid()
        print(json.dumps(out),flush=True)


class Pool:
    """Existing transport, with same-environment reference/candidate pairs."""
    def __init__(self,candidate,matrix):
        self.processes={};transport.SELF=Path(__file__).resolve()
        try:
            for role,env in (('A',OLD if matrix=='guards' else candidate),('B',candidate)):
                self.processes[role]=transport.Process(env,role,'all',variant=matrix,qos_policy='interactive')
            self.identity={r:p.metadata for r,p in self.processes.items()}
            for name in ('python','dependencies','qos','input_sha256','input_values_sha256'):
                assert self.identity['A'][name]==self.identity['B'][name],name
            if matrix=='guards':assert self.identity['A']['native_sha256']=='22e58cbbea3121c38c3f183b96df8442b41244b99ddc18e9bae0bbd4a220a987'
            for row in ALL_ROWS:
                if row['group']==matrix:
                    ident=row['id']
                    assert self.identity['A']['observed'][ident]==self.identity['B']['observed'][ident],(ident,self.identity['A']['observed'][ident],self.identity['B']['observed'][ident])
        except BaseException:self.close();raise
    def runs(self,ident,warmup=0):return {r:b.Run(p,ident,warmup) for r,p in self.processes.items()}
    def clocks(self):
        proof={r:p.short_info() for r,p in self.processes.items()}
        return proof,max(clock_bound(v) for v in proof.values())
    def close(self):
        for p in reversed(list(self.processes.values())):p.close()


def prepare(args):
 args.output.mkdir(parents=True,exist_ok=True);pool=Pool(args.candidate,args.matrix)
 try:
  proof,bound=pool.clocks();b.save(args.output/'clock.json',proof)
  cfg=dict(protocol='pddt-paired-v1',matrix=args.matrix,identity=pool.identity,rows={},
   clock_uncertainty_ns=max(bound,10000),observed_clock_bound_ns=bound,
   groups_per_cycle=12,cycles_per_round=9,rounds=['main','independent'],
   programs={str(p.relative_to(ROOT)):digest(p) for p in PROGRAMS})
  deadline=time.monotonic()+args.minutes*60
  selected=args.ids or [r['id'] for r in ROWS]
  with (args.output/'controls.jsonl').open('w') as stream:
   for ident in selected:
    cfg['rows'][ident]=b.control(pool,ident,cfg,deadline,stream,args.target_ms)
    b.save(args.output/'config.json',cfg)
    row=cfg['rows'][ident]
    print('CONTROL',ident,'R',round(row['short']['R'],5),'precision',row['precision'],'ready',row['ready'],flush=True)
  cfg['status']='CONTROLS_RECORDED';b.save(args.output/'config.json',cfg)
 finally:pool.close()


def collect(args,pilot=False):
 cfg=json.loads(args.config.read_text());assert cfg['matrix']==args.matrix
 for name,sha in cfg['programs'].items():assert digest(ROOT/name)==sha,name
 if not pilot:assert cfg['status']=='FROZEN_READY'
 existing.Pool=Pool
 ids=args.ids or [r['id'] for r in ROWS if r['id'] in cfg['rows']]
 deadline=time.monotonic()+args.minutes*60
 for round_name in (('pilot',) if pilot else ('main','independent')):
  folder=args.output/round_name;folder.mkdir(parents=True,exist_ok=True)
  for cycle in range(3 if pilot else 9):
   path=folder/f'cycle-{cycle}.json'
   if path.exists():
    assert json.loads(path.read_text())['complete'];continue
   start=time.monotonic()
   existing.collect_cycle(args,cfg,path,deadline,6 if pilot else 12,ids)
   print(round_name,cycle,round(time.monotonic()-start,3),'seconds',flush=True)


def report(args):
 cfg=json.loads(args.config.read_text());ids=[r['id'] for r in ROWS if r['id'] in cfg['rows']]
 result={i:dict(rounds={}) for i in ids};pids=[];audit=Counter()
 for name in ('main','independent'):
  cycles=[json.loads((args.output/name/f'cycle-{i}.json').read_text()) for i in range(9)]
  for cycle in cycles:
   assert cycle['complete'] and cycle['config_sha256']==digest(args.config)
   pids.extend(cycle['identity'][r]['pid'] for r in 'AB')
   for ident in ids:
    values=cycle['rows'][ident]
    assert len(values)==12 and Counter(v['order'] for v in values)==Counter(AB=6,BA=6)
    for v in values:
     assert v['valid'] and v['n']==cfg['rows'][ident]['n']
     assert all(v['checks'][r]['status']=='VALID' and v['members'][r]['pid']==cycle['identity'][r]['pid'] for r in 'AB')
     audit['accepted_pairs']+=1
  for ident in ids:
   values=[st.median(v['R'] for v in c['rows'][ident]) for c in cycles]
   groups,median=existing.levels(values)
   orders=[existing.levels([st.median(v['R'] for v in c['rows'][ident] if v['order']==order) for c in cycles])[1] for order in ('AB','BA')]
   result[ident]['rounds'][name]=dict(median=median,groups=groups,conservative=min(median,*groups),
    group_spread=b.engine.spread(groups),order_spread=b.engine.spread(orders),cycles=values,
    ns={role:existing.levels([st.median(v['members'][role]['T']/v['n'] for v in c['rows'][ident]) for c in cycles])[1] for role in 'AB'})
 assert len(pids)==len(set(pids))==36
 for ident,row in result.items():
  a,z=row['rounds'].values();cross=b.engine.spread([a['median'],z['median']])
  stable=max(a['group_spread'],z['group_spread'],a['order_spread'],z['order_spread'],cross)<=.05
  minimum=1/1.05
  row.update(precision=cfg['rows'][ident]['precision'],cross_spread=cross,stable=stable,minimum_ratio=minimum)
  row['status']='INCONCLUSIVE' if not stable or not cfg['rows'][ident]['ready'] else 'OBSERVATION' if ident.startswith('X') else 'PASS' if min(v['conservative'] for v in row['rounds'].values())>=minimum else 'FAIL'
 combinations={}
 if args.matrix=='calendar':
  for name in ('main','independent'):
   values=[result[f'K{i:02}']['rounds'][name] for i in range(1,7)]
   geo=lambda x:math.exp(st.mean(math.log(v) for v in x))
   median=geo([v['median'] for v in values]);groups=[geo([v['groups'][i] for v in values]) for i in range(3)]
   combinations[name]=dict(median=median,groups=groups,conservative=min(median,*groups))
 for name in ('main','independent'):
  for raw in (args.output/name).glob('*.jsonl'):
   for line in raw.read_text().splitlines():
    v=json.loads(line);audit['attempts']+=1
    if not v['valid']:audit['rejected_pairs']+=1
 status='PASS' if all(r['status']=='PASS' for i,r in result.items() if not i.startswith('X')) and all(r['conservative']>=1.50 for r in combinations.values()) else 'NOT_PASSED'
 b.save(args.output/'report.json',dict(rows=result,core=combinations,status=status,audit=dict(audit),real_worker_pids=pids,config_sha256=digest(args.config)))
 print(json.dumps(dict(status=status,core=combinations,rows=Counter(r['status'] for r in result.values()),audit=dict(audit))),flush=True)


if __name__=='__main__':
 if '--worker' in sys.argv:worker()
 else:
  cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('mode',choices=['prepare','pilot','collect','report']);cli.add_argument('--matrix',choices=['pandas3','calendar','guards'],required=True);cli.add_argument('--candidate',type=Path,required=True);cli.add_argument('--config',type=Path);cli.add_argument('--output',type=Path,required=True);cli.add_argument('--ids',nargs='*');cli.add_argument('--minutes',type=float,default=10);cli.add_argument('--target-ms',type=float,default=10)
  args=cli.parse_args();ROWS=[r for r in ALL_ROWS if r['group']==args.matrix]
  if args.mode=='prepare':prepare(args)
  elif args.mode=='pilot':collect(args,True)
  elif args.mode=='collect':collect(args)
  else:report(args)
