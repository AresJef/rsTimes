"""Audit fixed three-way cycle evidence and apply the planned estimators."""
from collections import Counter
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
import statistics as st
from benchmarks.parser_optimization import SCENES, ROLES, PAIRS, DELTA, engine

GROUPS=((0,1,2),(3,4,5),(6,7,8))
ISO=('B01','B02','B03','B04','B05','B06','B07','B08','B22','B23','B36','U08','U09','U10')
def spread(v): return max(v)/min(v)-1

def three_level(values):
    groups=[st.median(values[i] for i in g) for g in GROUPS]
    return groups,st.median(groups)


def analyze(root, config):
    cfg=json.loads(config.read_text()); sha=hashlib.sha256(config.read_bytes()).hexdigest()
    rows={s.id:dict(scene=vars(s),rounds={}) for s in SCENES}
    pids=[]; audit=Counter(); cycles_by_round={}
    for name in ('main','independent'):
        cycles=[json.loads((root/name/f'cycle-{i}.json').read_text()) for i in range(9)]
        cycles_by_round[name]=cycles
        for index,c in enumerate(cycles):
            assert c['complete'] and c['config_sha256']==sha,(name,index)
            pids.extend(c['identity'][r]['pid'] for r in ROLES)
            for ident,recs in c['results'].items():
                assert len(recs)==12 and Counter(v['order'] for v in recs)==Counter({o:2 for o in engine.ORDERS})
                for rec in recs:
                    assert rec['valid'] and rec['n']==cfg['rows'][ident]['n']
                    for role in ROLES:
                        assert rec['members'][role]['pid']==c['identity'][role]['pid']
                        assert rec['checks'][role]['status']=='VALID'
                        warmup=cfg.get('immediate_warmup_counts',{}).get(ident)
                        if warmup is not None: assert rec['members'][role]['immediate_warmup_calls']==warmup
                    audit['accepted_triads']+=1
        for path in [root/name/f'cycle-{i}.jsonl' for i in range(9)]:
            for line in path.read_text().splitlines():
                rec=json.loads(line);audit['attempts']+=1
                if not rec['valid']:audit['rejected_triads']+=1
        for s in SCENES:
            detail={}
            for pair in PAIRS:
                vals=[st.median(r['ratios'][pair] for r in c['results'][s.id]) for c in cycles]
                grouped,ratio=three_level(vals)
                order_ratios=[]
                for order in engine.ORDERS:
                    values=[st.median(r['ratios'][pair] for r in c['results'][s.id] if r['order']==order) for c in cycles]
                    order_ratios.append(three_level(values)[1])
                precision=cfg['rows'][s.id]['precision'].get(pair)
                sufficient=precision is not None and precision<=.03
                stable=spread(grouped)<=.05 and spread(order_ratios)<=.05
                detail[pair]=dict(median=ratio,conservative=min([ratio,*grouped]),groups=grouped,
                    group_spread=spread(grouped),order_spread=spread(order_ratios),precision=precision,
                    sufficient=sufficient,stable=stable)
            ns={r:three_level([st.median(x['members'][r]['T']/x['n'] for x in c['results'][s.id]) for c in cycles])[1] for r in ROLES}
            rows[s.id]['rounds'][name]=dict(pairs=detail,ns=ns)
    assert len(pids)==54 and len(set(pids))==54,'Use new real measuring workers'
    assert audit['accepted_triads']==16416
    for ident,row in rows.items():
        row['comparisons']={}
        for pair in PAIRS:
            a,b=[row['rounds'][name]['pairs'][pair] for name in ('main','independent')]
            cross=spread([a['median'],b['median']])
            stable=a['stable'] and b['stable'] and cross<=.05
            sufficient=a['sufficient'] and b['sufficient']
            protected=row['scene']['group']!='config'
            status='INCONCLUSIVE' if not stable or not sufficient else ('PASS' if min(a['median'],b['median'],a['conservative'],b['conservative'])>=1/1.05 else 'FAIL')
            if (pair != 'old/new' or not protected) and stable and sufficient: status='MEASURED'
            row['comparisons'][pair]=dict(status=status,stable=stable,sufficient=sufficient,cross_spread=cross,required=protected and pair=='old/new')
    combos={}
    for title,ids,threshold in (('ISO14',ISO,1.10),('core36',[f'B{i:02}' for i in range(1,37)],1.05)):
        values={}
        for name in ('main','independent'):
            results=[rows[i]['rounds'][name]['pairs']['old/new'] for i in ids]
            median=math.exp(sum(math.log(v['median']) for v in results)/len(ids))
            grouped=[math.exp(sum(math.log(v['groups'][i]) for v in results)/len(ids)) for i in range(3)]
            values[name]=dict(median=median,groups=grouped,conservative=min([median,*grouped]))
        valid=all(rows[i]['comparisons']['old/new']['stable'] and rows[i]['comparisons']['old/new']['sufficient'] for i in ids)
        status='INCONCLUSIVE' if not valid else ('PASS' if all(v['median']>=threshold and v['conservative']>=1 for v in values.values()) else 'FAIL')
        combos[title]=dict(rounds=values,threshold=threshold,status=status)
    delta={s.id:dict(scene=vars(s),rounds={}) for s in DELTA}
    for name,cycles in cycles_by_round.items():
        for s in DELTA:
            all_recs=[]
            for c in cycles:
                recs=c['delta_results'][s.id]
                assert len(recs)==24 and Counter(x['order'] for x in recs)==Counter(AB=12,BA=12)
                for rec in recs:
                    assert rec['valid'] and rec['n']==cfg['delta_rows'][s.id]['n']
                    for side,role in (('A','O'),('B','R')):
                        assert rec['checks'][side]['status']=='VALID'
                        assert rec['members'][side]['pid']==c['identity'][role]['pid']
                all_recs.append(recs);audit['accepted_delta_pairs']+=len(recs)
            vals=[st.median(x['R'] for x in recs) for recs in all_recs]
            grouped,ratio=three_level(vals)
            order_values=[three_level([st.median(x['R'] for x in recs if x['order']==o) for recs in all_recs])[1] for o in ('AB','BA')]
            precision=cfg['delta_rows'][s.id]['precision']
            ns={role:three_level([st.median(x['members'][side]['T']/x['n'] for x in recs) for recs in all_recs])[1] for side,role in (('A','O'),('B','R'))}
            delta[s.id]['rounds'][name]=dict(median=ratio,conservative=min([ratio,*grouped]),groups=grouped,
                group_spread=spread(grouped),order_spread=spread(order_values),precision=precision,
                sufficient=precision is not None and precision<=.03,
                stable=spread(grouped)<=.05 and spread(order_values)<=.05,ns=ns)
        for path in [root/name/f'cycle-{i}.delta.jsonl' for i in range(9)]:
            for line in path.read_text().splitlines():
                rec=json.loads(line);audit['delta_attempts']+=1
                if not rec['valid']:audit['rejected_delta_pairs']+=1
    for ident,row in delta.items():
        a,b=[row['rounds'][name] for name in ('main','independent')]
        cross=spread([a['median'],b['median']]);stable=a['stable'] and b['stable'] and cross<=.05
        sufficient=a['sufficient'] and b['sufficient']
        row['status']='INCONCLUSIVE' if not stable or not sufficient else ('PASS' if min(a['median'],b['median'],a['conservative'],b['conservative'])>=1/1.05 else 'FAIL')
        row['cross_spread']=cross
    assert audit['accepted_delta_pairs']==1296
    required=Counter(row['comparisons']['old/new']['status'] for row in rows.values() if row['scene']['group']!='config')
    return dict(rows=rows,delta=delta,combinations=combos,protection=dict(required),delta_protection=dict(Counter(row['status'] for row in delta.values())),audit=dict(audit),real_worker_pids=pids,
        config_sha256=sha,report_program_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--config',type=Path,required=True);args=p.parse_args()
    result=analyze(args.root,args.config)
    (args.root/'performance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (args.root/'performance.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['ID','Scenario','Group','Old ns','New ns','Cython ns','Old/New main','Old/New independent','Cython/New main','Cython/New independent','Protection','Cython comparison'])
        for ident,row in result['rows'].items():
            a,b=[row['rounds'][n] for n in ('main','independent')]
            writer.writerow([ident,re.sub(r'\bConfig\b','Configs',row['scene']['label']),row['scene']['group'],a['ns']['O'],a['ns']['R'],a['ns']['C'],a['pairs']['old/new']['median'],b['pairs']['old/new']['median'],a['pairs']['cython/new']['median'],b['pairs']['cython/new']['median'],row['comparisons']['old/new']['status'],row['comparisons']['cython/new']['status']])
        for ident,row in result['delta'].items():
            a,b=[row['rounds'][n] for n in ('main','independent')]
            writer.writerow([ident,row['scene']['label'],'delta',a['ns']['O'],a['ns']['R'],'',a['median'],b['median'],'','',row['status'],'NOT_APPLICABLE'])
    print(json.dumps(dict(combinations=result['combinations'],protection=result['protection'],delta_protection=result['delta_protection'],audit=result['audit']),indent=2))

if __name__=='__main__':main()
