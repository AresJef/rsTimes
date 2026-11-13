"""Add four targeted guards and one prospectively bounded stability extension."""
from pathlib import Path
from collections import Counter
import argparse, copy, json, math, statistics as st, sys, time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmarks import pydt_refactor as a
PRIMARY=a.INPUTS
SUPPLEMENT=a.HERE/'astimezone-supplemental-inputs.json'
a.INPUTS=a.HERE/'performance-inputs-with-astimezone.json'
a.ROWS=json.loads(a.INPUTS.read_text())['rows'];a.__file__=__file__
a.HASH_SEED=0
a.CPU_PREWARM_IDS=frozenset(('F158','F078','F082'))
GROUPS27=((0,1,2,9,10,11,12,13,14),(3,4,5,15,16,17,18,19,20),(6,7,8,21,22,23,24,25,26))
FIELDS=('native_sha256','version','python_implementation','python','dependencies','support','source','observed','qos','preparation','runtime','hash_values')

def levels(values):
 groups=GROUPS27 if len(values)==27 else ((0,1,2),(3,4,5),(6,7,8))
 assert len(values) in (9,27)
 result=[st.median(values[i] for i in group) for group in groups]
 return result,st.median(result)

def selected(args,cfg):
 original=json.loads((args.output/'report.json').read_text())
 assert original['config_sha256']==a.sha(args.config)
 ids=[i for i,r in original['rows'].items() if next(v['required'] for v in a.ROWS if v['id']==i) and r['status']=='INCONCLUSIVE' and not r['stable'] and cfg['rows'][i]['ready']]
 index=dict(ids=ids,initial_report_sha256=a.sha(args.output/'report.json'),config_sha256=a.sha(args.config),groups=[list(g) for g in GROUPS27],additional_cycles_per_round=18,additional_complete_pairs_per_item=432)
 path=args.output/'extension-index.json'
 if path.exists():assert json.loads(path.read_text())==index
 else:a.b.save(path,index)
 return ids

def extend(args):
 cfg=json.loads(args.config.read_text());assert cfg['status']=='FROZEN_READY'
 assert cfg['stability_extension']['groups']==[list(g) for g in GROUPS27]
 for path,digest in cfg['programs'].items():assert a.sha(ROOT/path)==digest,path
 ids=selected(args,cfg)
 if not ids:return
 deadline=time.monotonic()+args.minutes*60;a.cycles.Pool=a.Pool;args.matrix='pydt'
 for name in ('main','independent'):
  folder=args.output/'extension'/name;folder.mkdir(parents=True,exist_ok=True)
  for cycle in range(9,27):
   path=folder/f'cycle-{cycle}.json'
   if path.exists():assert json.loads(path.read_text())['complete'];continue
   start=time.monotonic();a.cycles.collect_cycle(args,cfg,path,deadline,12,ids)
   print(name,cycle,round(time.monotonic()-start,3),'seconds',flush=True)

def final_report(args):
 cfg=json.loads(args.config.read_text());original=json.loads((args.output/'report.json').read_text());result=copy.deepcopy(original);ids=selected(args,cfg);pids=[];audit=Counter()
 assert set(original['rows'])=={r['id'] for r in a.ROWS}==set(cfg['rows'])
 assert cfg['stability_extension']['groups']==[list(g) for g in GROUPS27]
 for name in ('main','independent'):
  files=[args.output/name/f'cycle-{i}.json' for i in range(9)]
  if ids:files += [args.output/'extension'/name/f'cycle-{i}.json' for i in range(9,27)]
  entries=[]
  for number,path in enumerate(files):
   cycle=json.loads(path.read_text());assert cycle['complete'] and cycle['config_sha256']==a.sha(args.config)
   for role in 'AB':
    assert all(cycle['identity'][role][f]==cfg['identity'][role][f] for f in FIELDS)
    pids.append(cycle['identity'][role]['pid'])
   wanted=list(original['rows']) if number<9 else ids
   assert set(cycle['rows'])==set(wanted)
   for ident in wanted:
    values=cycle['rows'][ident];assert len(values)==12 and Counter(v['order'] for v in values)==Counter(AB=6,BA=6)
    for value in values:
     assert value['valid'] and value['n']==cfg['rows'][ident]['n']
     assert all(value['members'][r]['pid']==cycle['identity'][r]['pid'] and a.prepared_quality(value['members'][r],cfg)['status']=='VALID' for r in 'AB')
     audit['accepted_pairs']+=1
   for line in path.with_suffix('.jsonl').read_text().splitlines():
    raw=json.loads(line);audit['attempts']+=1;audit['rejected_pairs']+=not raw['valid']
   entries.append(cycle)
  for ident in ids:
   values=[st.median(v['R'] for v in c['rows'][ident]) for c in entries]
   groups,median=levels(values);orders=[levels([st.median(v['R'] for v in c['rows'][ident] if v['order']==o) for c in entries])[1] for o in ('AB','BA')]
   result['rows'][ident]['rounds'][name]=dict(median=median,groups=groups,conservative=min(median,*groups),group_spread=a.b.engine.spread(groups),order_spread=a.b.engine.spread(orders),cycles=values,ns={r:levels([st.median(v['members'][r]['T']/v['n'] for v in c['rows'][ident]) for c in entries])[1] for r in 'AB'})
 for ident in ids:
  row=result['rows'][ident];left,right=row['rounds'].values();cross=a.b.engine.spread([left['median'],right['median']]);stable=max(cross,left['group_spread'],right['group_spread'],left['order_spread'],right['order_spread'])<=.05
  row.update(cross_spread=cross,stable=stable,status='INCONCLUSIVE' if not stable else 'PASS' if min(v['conservative'] for v in row['rounds'].values())>=1/1.05 else 'FAIL',actual_cycles_per_round=27,complete_pairs=648)
 geo=lambda v:math.exp(st.mean(math.log(x) for x in v))
 for name in ('main','independent'):
  families={}
  for family in sorted({r['family'] for r in a.ROWS}):
   members=[result['rows'][r['id']]['rounds'][name] for r in a.ROWS if r['family']==family and r['id'] in result['rows']]
   if not members:continue
   median=geo([v['median'] for v in members]);groups=[geo([v['groups'][i] for v in members]) for i in range(3)]
   families[family]=dict(median=median,groups=groups,conservative=min(median,*groups),count=len(members))
  broad=[v for f,v in families.items() if f.startswith('B') and len(f)==3];median=geo([v['median'] for v in broad]);groups=[geo([v['groups'][i] for v in broad]) for i in range(3)]
  result['combinations'][name]=dict(families=families,broad=dict(median=median,groups=groups,conservative=min(median,*groups)))
 expected=36+(72 if ids else 0);assert len(pids)==len(set(pids))==expected
 assert audit['accepted_pairs']==len(original['rows'])*216+len(ids)*432
 assert audit['attempts']-audit['rejected_pairs']==audit['accepted_pairs']
 required=[result['rows'][r['id']] for r in a.ROWS if r['required']]
 optimized=all(r['status']=='PASS' for r in required) and all(v['broad']['conservative']>1 for v in result['combinations'].values())
 result.update(audit=dict(audit),real_worker_pids=pids,extension_ids=ids,initial_report_sha256=a.sha(args.output/'report.json'),status='OPTIMIZED_PASS' if optimized else 'NOT_PASSED')
 a.b.save(args.output/'final-report.json',result);print(json.dumps(dict(status=result['status'],required=Counter(r['status'] for r in required),audit=dict(audit),extension_ids=ids,combinations=result['combinations'])),flush=True)

if __name__=='__main__':
 if '--worker' in sys.argv:a.worker()
 else:
  p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['identity','prepare','pilot','collect','report','extend','final-report']);p.add_argument('--reference',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--ids',nargs='*');p.add_argument('--minutes',type=float,default=10);p.add_argument('--target-ms',type=float,default=10);args=p.parse_args()
  a.REFERENCE=args.reference;a.b.control=a.length_control;a.b.quality=a.prepared_quality;a.shared.ROWS=a.ROWS;a.shared.Pool=a.Pool
  a.shared.PROGRAMS=(*a.shared.PROGRAMS,ROOT/'benchmarks/pydt_refactor.py',ROOT/'benchmarks/parser_prewarm.py',Path(__file__),PRIMARY,SUPPLEMENT,a.INPUTS)
  if args.mode=='prepare':a.shared.prepare(args)
  elif args.mode in ('pilot','collect'):a.shared.collect(args,args.mode=='pilot')
  elif args.mode=='report':a.report(args)
  elif args.mode=='extend':extend(args)
  elif args.mode=='final-report':final_report(args)
  else:
   pool=a.Pool(args.candidate)
   try:args.output.mkdir(parents=True,exist_ok=True);a.b.save(args.output/'identity.json',pool.identity)
   finally:pool.close()
