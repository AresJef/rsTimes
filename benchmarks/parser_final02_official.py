"""Compare fixed final02 parse with equivalent frozen official entrypoints.

Reuse parser_objects' paired transport, timer, quality checks and statistics.
Only workload selection and the official/Rust targets differ.
"""
from pathlib import Path
import argparse
import importlib.metadata as metadata
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import parser_objects as core

OUT = ROOT / 'tasks/evidence/parser-final02-official-20261016'
SCENES = tuple(s for s in core.b.SCENES
               if s.id[0] in 'BUCTN' and s.group != 'config')
ALL_IDS = tuple(s.id for s in SCENES) + tuple(core.OBJECT_LABELS)


def pairs(matrix):
    path = OUT / 'inventory.json'
    ids = json.loads(path.read_text())['comparable_ids'] if path.exists() else ALL_IDS
    return {i: (('A', i), ('B', i)) for i in ids}


def worker():
    role = sys.argv[sys.argv.index('--worker') + 1]
    qos = core.transport.measurement_qos(
        sys.argv[sys.argv.index('--measurement-qos') + 1])
    if role == 'A':
        import cytimes.parser as native
        cls, string_fn, object_fn = native.Configs, native.parse, native.parse_obj
    else:
        import rstimes
        import rstimes._native as native
        cls, string_fn, object_fn = rstimes.Configs, rstimes.parse, rstimes.parse
    built = {s.id: core.b.workload(s, cls, string_fn) for s in SCENES}
    built.update(core.object_workloads(object_fn))
    support = {}
    for name in ('cytimes.pydt', 'cytimes.utils', 'cytimes.errors', 'cytimes.parser'):
        module = __import__(name, fromlist=['*'])
        support[name] = dict(path=str(Path(module.__file__).resolve()),
                             sha256=core.workloads.digest(module.__file__))
    identity = dict(pid=__import__('os').getpid(), python=sys.version,
        executable=sys.executable, native=str(Path(native.__file__).resolve()),
        native_sha256=core.workloads.digest(native.__file__),
        version=metadata.version('cytimes' if role == 'A' else 'rstimes'),
        entrypoint=string_fn.__module__ + '.' + string_fn.__name__ + ' / ' +
                   object_fn.__module__ + '.' + object_fn.__name__,
        qos=qos, support=support, source={i: v[1] for i, v in built.items()},
        observed={i: v[2] for i, v in built.items()},
        dependencies={n: metadata.version(n) for n in
            ('cytimes', 'numpy', 'pandas', 'python-dateutil', 'six', 'tzdata', 'pytz')})
    print(json.dumps(identity), flush=True)
    for line in sys.stdin:
        req = json.loads(line)
        if req.get('op') == 'host':
            result = core.workloads.clocks()
        else:
            run = built[req['id']][0]
            if req.get('warmup_count'):
                run(req['warmup_count'])
            result = core.b.measure(run, req['count'])
            result['pid'] = identity['pid']
        print(json.dumps(result), flush=True)


class OfficialPool(core.Pool):
    def __init__(self, candidate, matrix):
        self.processes = {}
        self.matrix = matrix
        self.pairs = pairs(matrix)
        core.transport.SELF = Path(__file__).resolve()
        try:
            for role in 'AB':
                self.processes[role] = core.transport.Process(
                    candidate, role, 'all', variant=matrix)
            self.identity = {r: p.metadata for r, p in self.processes.items()}
            assert self.identity['A']['native_sha256'] == 'b507cada977d0e0ea4f22d0f9fd34bbac117ac6c14fc807128418f44ca7b85ca'
            assert self.identity['B']['native_sha256'] == '36068ba66d60d46e24b982c0a1ab0f91773617f7fe78295d5a0b5e284072b447'
            for key in ('python', 'dependencies', 'support', 'qos'):
                assert self.identity['A'][key] == self.identity['B'][key], key
            if (OUT / 'inventory.json').exists():
                for i in self.pairs:
                    for key in ('source', 'observed'):
                        assert self.identity['A'][key][i] == self.identity['B'][key][i], (i, key)
        except BaseException:
            self.close()
            raise


core.Pool = OfficialPool
core.pairs = pairs


def inventory(args):
    OUT.mkdir(parents=True, exist_ok=True)
    pool = OfficialPool(args.candidate, 'official')
    try:
        rows = []
        labels = {s.id: s.label for s in SCENES} | core.OBJECT_LABELS
        for i in ALL_IDS:
            same = all(pool.identity['A'][k][i] == pool.identity['B'][k][i]
                       for k in ('source', 'observed'))
            rows.append(dict(id=i, label=labels[i], comparable=same,
                observed={r: pool.identity[r]['observed'][i] for r in 'AB'}))
        core.b.save(OUT / 'inventory.json', dict(identity=pool.identity, rows=rows,
            comparable_ids=[x['id'] for x in rows if x['comparable']],
            excluded_ids=[x['id'] for x in rows if not x['comparable']]))
        print(json.dumps(dict(total=len(rows), comparable=sum(x['comparable'] for x in rows),
            excluded=[x['id'] for x in rows if not x['comparable']])), flush=True)
    finally:
        pool.close()


if __name__ == '__main__':
    if '--worker' in sys.argv:
        worker()
    else:
        cli = argparse.ArgumentParser(description=__doc__)
        cli.add_argument('action', choices=('inventory', 'prepare', 'screen', 'collect', 'analyze'))
        cli.add_argument('--matrix', default='official')
        cli.add_argument('--candidate', type=Path, required=True)
        cli.add_argument('--output', type=Path, default=OUT)
        cli.add_argument('--config', type=Path)
        cli.add_argument('--ids', nargs='+')
        cli.add_argument('--minutes', type=float, default=10)
        cli.add_argument('--target-ms', type=float, default=5)
        args = cli.parse_args()
        if args.action == 'inventory':
            inventory(args)
        elif args.action == 'prepare':
            core.prepare(args)
            path = args.output / 'config.json'
            cfg = json.loads(path.read_text())
            for item in (Path(__file__).resolve(), OUT / 'inventory.json'):
                cfg['programs'][str(item.relative_to(ROOT))] = core.workloads.digest(item)
            core.b.save(path, cfg)
        elif args.action == 'analyze':
            core.analyze(args)
        else:
            core.collect(args, args.action == 'screen')
