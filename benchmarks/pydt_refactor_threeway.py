"""Pydt's two protections from the existing complete-triplet collector."""
from pathlib import Path
from types import SimpleNamespace
from collections import Counter
import argparse, hashlib, itertools, json, math, os, statistics as st, sys, time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmarks import pydt_refactor as a
from tools import parser_threeway_compare as engine
from benchmarks.parser_timing import measure
from benchmarks.parser_quality import clock_bound
ROLES='OPN'
ORDERS=tuple(''.join(v) for v in itertools.permutations(ROLES))
PAIRS={'baseline/new':('O','N'),'best/new':('P','N')}
BASELINE=BEST=None
sha=a.sha

class Pool(a.Pool):
    def __init__(self,candidate,matrix='pydt'):
        self.processes={};a.transport.SELF=Path(__file__).resolve()
        old={k:os.environ.get(k) for k in ('PYTHONHASHSEED','TZ')}
        try:
            os.environ.update(PYTHONHASHSEED='0',TZ='Asia/Shanghai')
            for role,env in zip(ROLES,(BASELINE,BEST,candidate)):
                self.processes[role]=a.transport.Process(env,role,'all',qos_policy='interactive',variant='pydt-refactor')
            self.identity={r:p.metadata for r,p in self.processes.items()}
            for role in ROLES[1:]:
                for field in ('python','dependencies','support','qos','source','entrypoint','observed','runnable','preparation'):
                    assert self.identity['O'][field]==self.identity[role][field],(role,field)
            assert len(self.identity['O']['runnable'])==len(a.ROWS)
        except BaseException:self.close();raise
        finally:
            for k,v in old.items():
                if v is None:os.environ.pop(k,None)
                else:os.environ[k]=v


def install():
    engine.ROLES=ROLES;engine.ORDERS=ORDERS;engine.PAIRS=PAIRS
    engine.measure=measure;engine.quality=a.prepared_quality


def control(pool,ident,cfg,deadline,stream,target):
    runs=pool.runs(ident);n=1
    for run in runs.values():run(200)
    for _ in range(5):
        samples={r:measure(run,n) for r,run in runs.items()}
        fastest=min(min(v['T'],v['CPU']) for v in samples.values())
        if fastest>=target*900000:break
        n=max(n+1,math.ceil(n*target*1e6/max(1,fastest)))
    runs=pool.runs(ident,n)
    span=max(250_000_000,math.ceil(sum(v['T'] for v in samples.values())*4/50_000_000)*50_000_000)
    short=[];long=[]
    for block in range(6):
        short.extend(engine.groups(runs,n,span,2,cfg,deadline,stream,ident+':short',offset=block*2))
        long.extend(engine.groups(runs,n*3,span*3,1,cfg,deadline,stream,ident+':long',offset=block))
    row=dict(n=n,warmup_n=n,span_ns=span,target_ms=target,ready=False,precision=None)
    if len(short)==12 and len(long)==6:
        first,last=engine.summarize(short),engine.summarize(long)
        roles={r:a.b.engine.spread([first['ns'][r],last['ns'][r]]) for r in ROLES}
        pairs={pair:a.b.engine.spread([first['ratios'][pair],last['ratios'][pair]]) for pair in PAIRS}
        precision=max(*roles.values(),*pairs.values())
        row.update(short=first,long=last,role_precision=roles,pair_precision=pairs,precision=precision,ready=precision<=.03)
    return row


def prepare(args):
    args.output.mkdir(parents=True,exist_ok=False);pool=Pool(args.candidate)
    try:
        proof,bound=pool.clocks();a.b.save(args.output/'clock.json',proof)
        programs=(*a.shared.PROGRAMS,ROOT/'benchmarks/pydt_refactor.py',ROOT/'benchmarks/parser_prewarm.py',ROOT/'tools/parser_threeway_compare.py',Path(__file__),a.INPUTS)
        cfg=dict(protocol='pydt-complete-triplet-v1',identity=pool.identity,rows={},clock_uncertainty_ns=max(bound,10000),programs={str(p.relative_to(ROOT)):sha(p) for p in programs},orders=ORDERS,pairs=PAIRS,status='CONTROLS_RECORDED',groups_per_cycle=12,cycles_per_round=9,rounds=['main','independent'])
        deadline=time.monotonic()+args.minutes*60
        with (args.output/'controls.jsonl').open('w') as stream:
            for ident in args.ids or [r['id'] for r in a.ROWS]:
                cfg['rows'][ident]=control(pool,ident,cfg,deadline,stream,args.target_ms)
                a.b.save(args.output/'config.json',cfg)
                print('CONTROL',ident,cfg['rows'][ident]['ready'],cfg['rows'][ident]['precision'],flush=True)
                if time.monotonic()>=deadline:break
    finally:pool.close()


def collect_cycle(args,cfg,path,deadline,ids):
    pool=Pool(args.candidate)
    try:
        for role in ROLES:
            for field in ('native_sha256','version','python','dependencies','support','qos','source','observed','entrypoint','python_implementation','preparation'):
                assert pool.identity[role][field]==cfg['identity'][role][field],(role,field)
        proof,bound=pool.clocks();a.b.save(path.with_suffix('.clock.json'),dict(proof=proof,bound=bound));assert bound<=cfg['clock_uncertainty_ns']
        rows={i:[] for i in ids}
        def snapshot(complete=False):
            a.b.save(path,dict(identity=pool.identity,config_sha256=sha(args.config),rows=rows,complete=complete))
        snapshot()
        try:
            with path.with_suffix('.jsonl').open('w') as stream:
                for sweep in range(2):
                    for ident in list(rows) if sweep==0 else reversed(rows):
                        c=cfg['rows'][ident]
                        values=engine.groups(pool.runs(ident,c['warmup_n']),c['n'],c['span_ns'],6,cfg,deadline,stream,ident,offset=sweep*6)
                        rows[ident].extend(values)
                        if len(values)!=6:raise TimeoutError('Incomplete triplet cycle preserved')
                    snapshot()
            counts={i:Counter() for i in ids}
            with path.with_suffix('.jsonl').open() as stream:
                for line in stream:
                    value=json.loads(line)
                    if value['valid']:counts[value['tag']][value['order']]+=1
            assert all(counts[i]==Counter(v['order'] for v in rows[i])==Counter({order:2 for order in ORDERS}) for i in ids)
            snapshot(True)
        except BaseException:
            try:snapshot(False)
            except BaseException:pass  # Preserve the original failure if saving also fails.
            raise
    finally:pool.close()


def collect(args):
    cfg=json.loads(args.config.read_text());assert cfg['status']=='FROZEN_READY'
    for name,digest in cfg['programs'].items():assert sha(ROOT/name)==digest,name
    ids=args.ids or list(cfg['rows']);args.output.mkdir(parents=True,exist_ok=True)
    limit=args.output/'collection-deadline.json'
    if not limit.exists():a.b.save(limit,dict(wall_deadline=time.time()+args.minutes*60))
    deadline=time.monotonic()+max(0,json.loads(limit.read_text())['wall_deadline']-time.time())
    for name in ('main','independent'):
        folder=args.output/name;folder.mkdir(exist_ok=True)
        for i in range(9):
            path=folder/f'cycle-{i}.json'
            if path.exists():assert json.loads(path.read_text())['complete'];continue
            start=time.monotonic();collect_cycle(args,cfg,path,deadline,ids)
            print(name,i,time.monotonic()-start,flush=True)


def report(args):
    cfg=json.loads(args.config.read_text());ids=list(cfg['rows']);pids=[];original={}
    for name in ('main','independent'):
        original[name]=[json.loads((args.output/name/f'cycle-{i}.json').read_text()) for i in range(9)]
        for cycle in original[name]:
            assert cycle['complete'] and cycle['config_sha256']==sha(args.config)
            for role in ROLES:
                for field in ('native_sha256','version','python_implementation','dependencies','source','observed','qos','preparation'):
                    assert cycle['identity'][role][field]==cfg['identity'][role][field],(role,field)
                pids.append(cycle['identity'][role]['pid'])
            for ident in ids:
                values=cycle['rows'][ident];assert len(values)==12 and Counter(v['order'] for v in values)==Counter({o:2 for o in ORDERS})
                for v in values:
                    assert v['valid'] and v['n']==cfg['rows'][ident]['n']
                    assert all(v['checks'][r]['status']=='VALID' and v['members'][r]['pid']==cycle['identity'][r]['pid'] for r in ROLES)
    assert len(pids)==len(set(pids))==54
    summaries={};required={r['id'] for r in a.ROWS if r['required'] and r['id'] in ids}
    for label,(ref,new) in PAIRS.items():
        folder=args.output/('view-'+label.replace('/','-'));folder.mkdir(exist_ok=False)
        view=dict(cfg,identity={side:cfg['identity'][role] for side,role in (('A',ref),('B',new))},source_triplet_config=str(args.config),source_triplet_config_sha256=sha(args.config))
        config=folder/'config.json';a.b.save(config,view)
        for name,data in original.items():
            out=folder/name;out.mkdir()
            for i,cycle in enumerate(data):
                rows={}
                for ident,values in cycle['rows'].items():
                    rows[ident]=[dict(v,R=v['ratios'][label],threeway_order=v['order'],order='AB' if v['order'].index(ref)<v['order'].index(new) else 'BA',members={'A':v['members'][ref],'B':v['members'][new]},checks={'A':v['checks'][ref],'B':v['checks'][new]}) for v in values]
                a.b.save(out/f'cycle-{i}.json',dict(identity={'A':cycle['identity'][ref],'B':cycle['identity'][new]},rows=rows,complete=True,config_sha256=sha(config)))
        a.report(SimpleNamespace(config=config,output=folder,ids=ids))
        result=json.loads((folder/'report.json').read_text())
        for ident,row in result['rows'].items():
            row['six_order_spread']={name:a.b.engine.spread([a.cycles.levels([st.median(v['ratios'][label] for v in cycle['rows'][ident] if v['order']==order) for cycle in data])[1] for order in ORDERS]) for name,data in original.items()}
            if max(row['six_order_spread'].values())>.05:row['status']='INCONCLUSIVE';row['stable']=False
        passed=all(result['rows'][i]['status']=='PASS' for i in required) and all(v['broad']['conservative']>1 for v in result['combinations'].values())
        result['projection_only_status']=result['status']
        result['status']='PROTECTION_PASS' if passed else 'NOT_PASSED'
        result['required_status']='PASS' if passed else 'NOT_PASSED';a.b.save(folder/'report.json',result)
        summaries[label]=dict(status=result['required_status'],counts=dict(Counter(v['status'] for v in result['rows'].values())),combinations=result['combinations'])
    audit=Counter()
    for name in ('main','independent'):
        for path in (args.output/name).glob('*.jsonl'):
            for line in path.read_text().splitlines():
                value=json.loads(line);audit['attempts']+=1
                audit['accepted_triplets' if value['valid'] else 'rejected_triplets']+=1
                for role in value['members']:audit['executed_'+role]+=1
    assert audit['accepted_triplets']==len(ids)*216
    shared_audit=args.output/'shared-triplet-audit.json'
    a.b.save(shared_audit,dict(audit))
    for label in PAIRS:
        path=args.output/('view-'+label.replace('/','-'))/'report.json'
        result=json.loads(path.read_text())
        result['audit']=dict(accepted_projected_pairs=len(ids)*216,source_triplet_audit=str(shared_audit),source_sha256=sha(shared_audit),counting='Shared complete-triplet attempts; not additional measurements.')
        a.b.save(path,result)
    a.b.save(args.output/'threeway-report.json',dict(status='PASS' if all(v['status']=='PASS' for v in summaries.values()) else 'NOT_PASSED',scope_ids=ids,full_coverage=len(ids)==len(a.ROWS),comparisons=summaries,real_worker_pids=pids,audit=dict(audit),source_config_sha256=sha(args.config),note='Two views share the same complete, valid triplets; observation-only rows do not veto. Subset reports are not full acceptance.'))

if __name__=='__main__':
    install()
    if '--worker' in sys.argv:a.worker()
    else:
        p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','collect','report']);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--best',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--ids',nargs='*');p.add_argument('--minutes',type=float,default=10);p.add_argument('--target-ms',type=float,default=10)
        args=p.parse_args();BASELINE=args.baseline;BEST=args.best
        globals()[args.mode](args)
