"""Reuse Delta's frozen paired sampler and isolated-worker transport.

This task adapter selects artifacts and workloads. Timers, quality checks,
calibration, balanced collection and statistics remain in the existing sampler.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import pickle
import platform
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.local/delta/correction-20261013/final-env4d'
FROZEN = ROOT / 'tasks/evidence/delta-cross-rc04-20261013'
CY_SHA = '3ef0ec227fe995ebb0c289f28d59ff69faa8847dcfd13b0755eaaf71fb289aba'
BASE_SHA = 'e4d919cb654d1c554b6ee20b22bc4429537b93dd4049bc45a3a504f36c56273d'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cross = load('fast_cross_sampler', ROOT / 'tools/delta_cross_compare.py')
bench = load('fast_worker_transport', ROOT / 'benchmarks/delta/bench.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guard_workloads():
    """Build the frozen 200 common calls and 66 existing protection inputs."""
    from rstimes import Delta
    package = types.ModuleType('benchmarks')
    package.__path__ = [str(cross.CY_ROOT / 'benchmarks')]
    sys.modules['benchmarks'] = package
    import benchmarks.round2_scenarios as cy_work
    selected = json.loads((FROZEN / 'performance-summary.json').read_text())['rows']
    expected_ids = {r['id'] for r in selected}
    calls = {'C:' + key: pair for key, pair in cy_work.workloads(Delta).items()}
    cases = cross.load_source('cross_perf_R', ROOT / 'tests/delta/cases.py')
    _, legacy = cases.benchmark_cases('rstimes')
    _, revision = cases.revision_benchmark_cases('rstimes', 'revision-candidate')
    for case in legacy + [c for c in revision if not c.id.startswith('float:')]:
        calls['R:' + case.id] = (cross.loop_for(case.run), case.run)
    for label in ('repr-first-fresh', 'repr-alternating', 'repr-subclass'):
        class Child(Delta):
            pass
        if label == 'repr-first-fresh':
            call = lambda: repr(Delta(days=1))
        elif label == 'repr-subclass':
            child = Child(days=1)
            call = lambda child=child: repr(child)
        else:
            values, position = [Delta(days=1), Delta(days=2)], [0]
            def call(values=values, position=position):
                position[0] ^= 1
                return repr(values[position[0]])
        calls['direct:' + label] = (cross.loop_for(call), call)
    assert expected_ids <= calls.keys(), 'Missing frozen common workload'
    calls = {key: calls[key] for key in [r['id'] for r in selected]}
    _, protection, _ = cases.correction_performance_cases('rstimes')
    manifest = json.loads((ROOT / 'benchmarks/delta/correction-cases.json').read_text())
    fixed_protection = {key for group in manifest['groups'].values() for key in group}
    lookup = {c.id: c for c in protection}
    assert len(fixed_protection) == 66 and fixed_protection <= lookup.keys()
    for group in manifest['groups'].values():
        for key in group:
            call = lookup[key].run
            calls['P:' + key] = (cross.loop_for(call), call)
    assert len(calls) == 266
    return Delta, calls


def worker(args):
    """Normally import one native image; never alias competing Rust modules."""
    import rstimes
    import rstimes._native as native
    qos = bench.measurement_qos(args.measurement_qos)
    Delta, calls = guard_workloads()
    if 'supplement:apply-empty' in args.case:
        delta, values = Delta(days=1), []
        call = lambda: delta.apply_many(values)
        calls['supplement:apply-empty'] = (cross.loop_for(call), call)
    if args.case:
        calls = {key: calls[key] for key in args.case}
    observed = {}
    for key, (_, one) in calls.items():
        value = one()
        if isinstance(value, bytes):
            value = pickle.loads(value)
        encoded = cross.canonical(value, {'R': Delta, 'C': Delta})
        observed[key] = hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest()
    metadata = {'native': str(Path(native.__file__).resolve()), 'sha256': digest(native.__file__),
                'version': importlib.metadata.version('rstimes'), 'pid': os.getpid(),
                'python': sys.version, 'machine': platform.machine(), 'platform': platform.platform(),
                'dependencies': {name: importlib.metadata.version(name) for name in
                    ('cytimes','numpy','pandas','python-dateutil','tzdata','pendulum')},
                'observations': observed, 'release': native.release_build(), 'measurement_qos': qos}
    assert metadata['release']
    print(json.dumps(metadata), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        if request.get('op') == 'host':
            reply = cross.clocks()
        else:
            run = calls[request['id']][0]
            warmup = request.get('warmup_count', 0)
            if warmup:
                run(warmup)
            reply = cross.measure(run, request['count'])
        print(json.dumps(reply), flush=True)


class RemoteRun:
    """Expose worker-local timing to the existing four-batch sampler."""
    def __init__(self, process, identifier):
        self.process, self.identifier = process, identifier

    def __call__(self, n):
        self.sample(n)

    def sample(self, n):
        return self.process.short_sample(self.identifier, n)


def main(args):
    cross.OUT = args.out
    qos = bench.measurement_qos(args.measurement_qos)
    pool = []
    original_workloads, original_measure = cross.workloads, cross.measure
    try:
        if args.backend == 'cross':
            import rstimes._native as native
            actual = digest(native.__file__)
            assert actual == args.candidate_sha
            cross.EXPECTED = {'R': ('rstimes._native', actual), 'C': ('cytimes_rewrite.delta', CY_SHA)}
            targets, identity = cross.load_targets()
            identity['measurement_qos'] = qos
            pairs, metadata, excluded = original_workloads(targets)
            fixed_ids = {r['id'] for r in json.loads((FROZEN / 'performance-summary.json').read_text())['rows']}
            assert fixed_ids <= pairs.keys(), 'Candidate changed common behavior'
            pairs = {key: pair for key, pair in pairs.items() if key in fixed_ids}
        else:
            bench.SELF = Path(__file__).resolve()
            for env in (args.baseline_env, args.candidate_env):
                pool.append(bench.Process(env, 'rstimes', 'all', selected_ids=args.case, variant='fast'))
            A, B = pool
            assert A.metadata['sha256'] == args.baseline_sha and B.metadata['sha256'] == args.candidate_sha
            for key in ('python','machine','platform','dependencies','observations','measurement_qos'):
                assert A.metadata[key] == B.metadata[key], 'Worker identity/output mismatch: ' + key
            identity = {**{key: A.metadata[key] for key in ('python','machine','platform','dependencies','measurement_qos')},
                        'C': A.metadata, 'R': B.metadata, 'comparison': 'baseline/candidate'}
            pairs = {key: {'C': (RemoteRun(A,key), None), 'R': (RemoteRun(B,key), None)}
                     for key in A.metadata['observations']}
            metadata = {key: {'group': key.split(':',1)[0], 'input': key, 'source': 'frozen existing calls'} for key in pairs}
            excluded, targets = {}, {}
            cross.measure = lambda run,n: run.sample(n) if isinstance(run,RemoteRun) else original_measure(run,n)
        if args.case:
            pairs = {key: pairs[key] for key in args.case}
        cross.workloads = lambda targets: (pairs, metadata, excluded)
        if args.mode == 'identity':
            cross.save('identity.json', identity)
            cross.save('workloads.json', {'selected': {key: metadata[key] for key in pairs}, 'excluded': excluded})
            print(json.dumps({'cases':len(pairs),'identity':identity}, ensure_ascii=False))
        elif args.mode == 'prepare':
            cross.prepare(targets, identity)
            config = json.loads((args.out/'config.json').read_text())
            config['input_sha256'] = {str(path):digest(path) for path in
                (Path(__file__), cross.ROOT/'tools/delta_cross_compare.py', bench.SELF,
                 ROOT/'tests/delta/cases.py', ROOT/'benchmarks/delta/correction-cases.json')}
            if args.groups:
                config.update(groups_per_cycle=args.groups, order_quota={'CRRC':args.groups//2,'RCCR':args.groups//2})
            cross.save('config.json', config)
        else:
            config = json.loads((args.out/'config.json').read_text())
            assert all(digest(path)==sha for path,sha in config['input_sha256'].items())
            expected = config['identity']
            for role in ('C','R'):
                assert identity[role]['sha256'] == expected[role]['sha256']
            for name in ('python','machine','platform','dependencies'):
                assert identity[name] == expected[name]
            if args.mode == 'refine':
                cross.refine_controls(targets)
            elif args.groups and args.groups != 24:
                # Development screening uses the planned six groups. Formal
                # collection still calls the unchanged 24-group collector.
                import time
                campaign = json.loads((args.out/'campaign.json').read_text())
                log = args.out / f'{args.phase}-{args.cycle}.jsonl'
                if log.exists():
                    raise FileExistsError(log)
                with log.open('w') as stream:
                    for key, scene in config['scenes'].items():
                        roles, n = pairs[key], scene['n']
                        for role in ('C','R'):
                            roles[role][0](n)
                        for slot in range(args.groups):
                            attempt = 0
                            undersized = 0
                            while time.time() < campaign['deadline_epoch']:
                                row = cross.quad(roles,n,slot,config['clock'])
                                row.update(scene=key,phase=args.phase,cycle=args.cycle,
                                           slot=slot,pid=os.getpid(),attempt=attempt)
                                stream.write(json.dumps(row,separators=(',',':'))+'\n')
                                if row['valid']:
                                    break
                                # A sustained clean undersized role proves that
                                # frozen n cannot meet the minimum in this run.
                                # Stop to recalibrate; never relax or accept it.
                                too_short = any(all(m['T'] < config['minimum_batch_ns']
                                    and m['CPU'] > 0
                                    and abs(m['T']-m['CPU'])/m['T'] <= .10
                                    for m in row['members'] if m['role'] == role)
                                    for role in ('C','R'))
                                undersized = undersized + 1 if too_short else 0
                                if undersized >= 16:
                                    stream.flush()
                                    raise RuntimeError('Frozen batch consistently too short: ' + key)
                                attempt += 1
                            else:
                                raise TimeoutError('Development screening budget reached')
                        stream.flush()
                cross.save(f'{args.phase}-{args.cycle}-identity.json',identity)
                print(json.dumps({'complete_scenes':len(config['scenes']),'groups_per_scene':args.groups}))
            else:
                cross.collect(targets, identity, args.phase, args.cycle)
    finally:
        for process in pool:
            process.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker')
    parser.add_argument('--group', default='all')
    parser.add_argument('--warmup-ms', type=float, default=0)
    parser.add_argument('--measurement-qos', default='initiated')
    parser.add_argument('--variant', default='fast')
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--backend', choices=('cross','guard'), default='cross')
    parser.add_argument('--mode', choices=('identity','prepare','refine','collect'), default='identity')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--baseline-env', type=Path, default=BASE)
    parser.add_argument('--baseline-sha', default=BASE_SHA)
    parser.add_argument('--candidate-env', type=Path, default=BASE)
    parser.add_argument('--candidate-sha', default=BASE_SHA)
    parser.add_argument('--groups', type=int)
    parser.add_argument('--phase', choices=('main','independent'))
    parser.add_argument('--cycle', type=int)
    arguments = parser.parse_args()
    worker(arguments) if arguments.worker else main(arguments)
