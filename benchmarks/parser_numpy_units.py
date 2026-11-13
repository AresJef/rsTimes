"""Measure the seven datetime64 units missing from the retained final02 report.

Reuse the official adapter, public-call loops, paired collector and statistics.
No product code or measurement rule is changed.
"""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import parser_final02_official as adapter

UNITS = {'NY': 'Y', 'NW': 'W', 'ND': 'D', 'Nh': 'h', 'Nm': 'm',
         'Ns': 's', 'Nms': 'ms'}
OUTPUT = ROOT / 'tasks/evidence/parser-numpy-unit-cost-20261016'


def workloads(function):
    import numpy as np
    built = {}
    for ident, unit in UNITS.items():
        value = np.datetime64('2024-05-07T15:30:01.123456789', unit)
        source = (f'# input: {value!r}; dtype: {value.dtype}\n'
                  'def run(n, fn=fn, value=value, factory=factory):\n'
                  '    for _ in range(n):\n'
                  '        result = fn(value)\n'
                  '        del result\n')
        env = dict(fn=function, value=value, factory=None)
        exec(compile(source, '<numpy-unit-'+unit+'>', 'exec'), env)
        observed = adapter.core.b.base.engine.canonical(
            adapter.core.b.base.engine.capture(lambda: function(value)))
        built[ident] = (env['run'], adapter.core.workloads.digest_text(source), observed)
    return built


adapter.OUT = OUTPUT
adapter.SCENES = ()
adapter.ALL_IDS = tuple(UNITS)
adapter.__file__ = __file__
adapter.core.OBJECT_LABELS = {i: 'NumPy datetime64 '+u for i, u in UNITS.items()}
adapter.core.object_workloads = workloads
MAPPING = {i: (('A', i), ('B', i)) for i in UNITS}
adapter.pairs = lambda matrix: MAPPING
adapter.core.pairs = adapter.pairs


if __name__ == '__main__':
    if '--worker' in sys.argv:
        adapter.worker()
    else:
        cli = argparse.ArgumentParser(description=__doc__)
        cli.add_argument('action', choices=('inventory', 'prepare', 'screen', 'collect', 'analyze'))
        cli.add_argument('--matrix', default='official')
        cli.add_argument('--candidate', type=Path, required=True)
        cli.add_argument('--output', type=Path, default=OUTPUT)
        cli.add_argument('--config', type=Path)
        cli.add_argument('--ids', nargs='+')
        cli.add_argument('--minutes', type=float, default=10)
        cli.add_argument('--target-ms', type=float, default=10)
        args = cli.parse_args()
        if args.action == 'inventory':
            adapter.inventory(args)
        elif args.action == 'prepare':
            adapter.core.prepare(args)
            import json
            path = args.output/'config.json'
            cfg = json.loads(path.read_text())
            for file in (Path(__file__).resolve(), ROOT/'benchmarks/parser_final02_official.py', OUTPUT/'inventory.json'):
                cfg['programs'][str(file.relative_to(ROOT))] = adapter.core.workloads.digest(file)
            adapter.core.b.save(path, cfg)
        elif args.action == 'analyze':
            adapter.core.analyze(args)
        else:
            adapter.core.collect(args, args.action == 'screen')
