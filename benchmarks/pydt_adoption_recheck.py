"""Use the existing paired collector for the fixed pre-project and B4 packages."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import pydt_refactor_final as existing

m = existing.a
INPUTS = ROOT / 'tasks/evidence/pydt-44-recheck-20261018/inputs.json'
m.INPUTS = INPUTS
m.ROWS = json.loads(INPUTS.read_text())['rows']
m.__file__ = __file__

if __name__ == '__main__':
    if '--worker' in sys.argv:
        m.worker()
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('mode', choices=['identity', 'prepare', 'pilot', 'collect', 'report', 'extend', 'final-report'])
        parser.add_argument('--reference', type=Path, required=True)
        parser.add_argument('--candidate', type=Path, required=True)
        parser.add_argument('--config', type=Path)
        parser.add_argument('--output', type=Path, required=True)
        parser.add_argument('--ids', nargs='*')
        parser.add_argument('--minutes', type=float, default=10)
        parser.add_argument('--target-ms', type=float, default=10)
        parser.add_argument('--probe', action='store_true')
        args = parser.parse_args()
        m.REFERENCE = args.reference
        m.ALLOW_DIFFERENCES = args.probe and args.mode == 'identity'
        m.b.control = m.length_control
        m.b.quality = m.prepared_quality
        m.shared.ROWS = m.ROWS
        m.shared.Pool = m.Pool
        m.shared.PROGRAMS = (*m.shared.PROGRAMS, ROOT/'benchmarks/pydt_refactor.py', ROOT/'benchmarks/parser_prewarm.py', ROOT/'benchmarks/pydt_refactor_final.py', Path(__file__), INPUTS)
        if args.mode == 'identity':
            pool = m.Pool(args.candidate)
            try:
                args.output.mkdir(parents=True, exist_ok=True)
                m.b.save(args.output/'identity.json', pool.identity)
                print('Verified', len(m.ROWS), 'representatives', flush=True)
            finally:
                pool.close()
        elif args.mode == 'prepare':
            source = ROOT/'tasks/evidence/pydt-refactor-opt-20261017/B4-base-frozen-config.json'
            prior = json.loads(source.read_text())
            initial = args.output.parent/'initial/config.json'
            previous = json.loads(initial.read_text()) if args.output.name == 'confirm' else None
            completed = json.loads(initial.read_text())['rows'] if args.output.name == 'remaining' else {}
            ids = args.ids or [r['id'] for r in m.ROWS if r['id'] not in completed and (previous is None or not previous['rows'][r['id']]['ready'])]
            pool = m.Pool(args.candidate)
            try:
                args.output.mkdir(parents=True, exist_ok=False)
                proof, bound = pool.clocks()
                m.b.save(args.output/'clock.json', proof)
                cfg = dict(protocol='pydt-paired-v1', matrix='pydt', identity=pool.identity, rows={},
                    clock_uncertainty_ns=max(10000,bound), observed_clock_bound_ns=bound,
                    groups_per_cycle=12, cycles_per_round=9, rounds=['main','independent'],
                    programs={str(p.relative_to(ROOT)):m.sha(p) for p in m.shared.PROGRAMS},
                    status='CONTROLS_RECORDED', parameter_source=str(source.relative_to(ROOT)))
                start = time.monotonic()
                deadline = start + args.minutes*60
                with (args.output/'controls.jsonl').open('w') as stream:
                    for ident in ids:
                        original = (previous or prior)['rows'][ident]
                        factor = 2 if previous else 1
                        n = original['n']*factor
                        span = original['span_ns']*factor
                        if original['target_ms']*factor > 40:
                            continue
                        runs = pool.runs(ident,n)
                        duration_probe = {role:m.measure(run,n) for role,run in runs.items()}
                        if not previous and min(v['T'] for v in duration_probe.values()) < 7_000_000 and original['target_ms']*factor*2 <= 40:
                            factor *= 2
                            n *= 2
                            span *= 2
                            runs = pool.runs(ident,n)
                        case_deadline = min(deadline,time.monotonic()+15)
                        short, long = [], []
                        for block in range(6):
                            short.extend(m.b.engine.pairs(runs,n,span,2,cfg,m.prepared_quality,m.measure,case_deadline,stream,ident+':short',slot_offset=block*2))
                            long.extend(m.b.engine.pairs(runs,n*3,span*3,1,cfg,m.prepared_quality,m.measure,case_deadline,stream,ident+':long',slot_offset=block))
                        left, right = m.b.engine.pair_summary(short), m.b.engine.pair_summary(long)
                        complete = len(short)==12 and len(long)==6
                        ratio = m.b.engine.spread([left['R'],right['R']]) if complete else None
                        roles = {r:m.b.engine.spread([left['ns'][r],right['ns'][r]]) if complete else None for r in 'AB'}
                        precision = max(ratio,*roles.values()) if complete else None
                        cfg['rows'][ident] = dict(n=n,span_ns=span,target_ms=original['target_ms']*factor,warmup_n=n,
                            short=left,long=right,ratio_precision=ratio,role_precision=roles,
                            precision=precision,ready=precision is not None and precision<=.03,parameter_multiplier=factor,duration_probe=duration_probe)
                        m.b.save(args.output/'config.json',cfg)
                        print(ident,precision,cfg['rows'][ident]['ready'],flush=True)
                cfg.update(complete=True,seconds=time.monotonic()-start)
                m.b.save(args.output/'config.json',cfg)
            finally:
                pool.close()
        elif args.mode in ('pilot', 'collect'):
            m.shared.collect(args, args.mode == 'pilot')
        elif args.mode == 'report':
            m.report(args)
        elif args.mode == 'extend':
            existing.extend(args)
        else:
            existing.final_report(args)
