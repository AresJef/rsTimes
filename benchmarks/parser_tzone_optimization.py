"""Add the twelve approved regional/strict calls to the existing paired runner.

Configuration and default objects are prepared outside timing. The timed loop
still calls the public parse function directly. Unsupported regional calls are
explicit metadata only for parser.4 and are never part of its comparison set.
"""
from datetime import datetime
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import parser_tzone as b

INPUT_FILE = ROOT / 'benchmarks/parser_tzone_inputs.json'
INPUTS = {row['id']: row for row in json.loads(INPUT_FILE.read_text())['rows']}
CORE = dict(b.PAIRS)
EXTRA = {ident: (('A', ident), ('B', ident)) for ident in INPUTS}
_namespace = b.base.base.namespace
_workload = b.base.workload


def namespace(role, scene):
    result = _namespace(role, scene)
    if scene.id in INPUTS:
        value = INPUTS[scene.id]['default']
        result['regional_default'] = None if value is None else datetime(*value[:7], fold=value[7])
    return result


def fields(value):
    offset = value.utcoffset()
    return dict(fields=[getattr(value, key) for key in
                       ('year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond')],
                fold=value.fold, zone_key=getattr(value.tzinfo, 'key', None),
                offset_seconds=None if offset is None else int(offset.total_seconds()))


def workload(scene, cls, fn):
    if scene.id not in INPUTS:
        return _workload(scene, cls, fn)
    item = INPUTS[scene.id]
    if item['regions'] and not hasattr(cls, 'set_tzone'):
        def unsupported(n):
            raise RuntimeError('This reference has no registered-region API')
        return unsupported, b.base.digest_text('UNSUPPORTED:' + scene.id), {'unsupported': True}
    configured = []

    def factory(*args, **kwargs):
        cfg = cls(*args, **kwargs)
        if item['regions']:
            cfg.set_tzone(set(item['regions']))
        configured.append(cfg)
        return cfg

    run, source, observed = _workload(scene, factory, fn)
    kwargs = dict(item['kwargs'], cfg=configured[-1])
    default = item['default']
    if default is not None:
        kwargs['default'] = datetime(*default[:7], fold=default[7])
    actual = fields(fn(item['text'], **kwargs))
    assert actual == item['expected'], (scene.id, actual, item['expected'])
    return run, source, dict(observed, regional_fields=actual)


scenes = []
for ident, item in INPUTS.items():
    arguments = ['cfg=cfg'] + [f'{key}={value!r}' for key, value in item['kwargs'].items()]
    if item['default'] is not None:
        arguments.append('default=regional_default')
    scenes.append(b.base.base.Scene(ident, item['label'], 'regional' if ident.startswith('Z') else 'strict',
                                    'fn(text, ' + ', '.join(arguments) + ')', item['text']))
b.base.base.namespace = namespace
b.base.workload = workload
b.SCENES = b.SCENES + tuple(scenes)
b.base.SCENES = b.SCENES
# The earlier S01..S04 observations compare lenient/strict costs. Keep those
# observations distinct from the approved S01..S04 final protection inputs.
b.OBSERVATIONS = {('O' + key if key.startswith('S') else key): value
                  for key, value in b.OBSERVATIONS.items()}
b.WORKER_FILE = Path(__file__)


def reference(environment, native_sha256, *, include_regions):
    """Select one complete matrix without combining samples across references."""
    b.OLD = Path(environment)
    b.OLD_SHA = native_sha256
    b.PAIRS = CORE | EXTRA if include_regions else dict(CORE)
    assert len(b.PAIRS) == (79 if include_regions else 67)
    return b


_prepare = b.prepare


def prepare(candidate, output, ids, minutes):
    cfg = _prepare(candidate, output, ids, minutes)
    for source in (Path(__file__), INPUT_FILE):
        cfg['programs'][str(source.relative_to(ROOT))] = b.base.digest(source)
    b.save(output / 'config.json', cfg)
    return cfg


b.prepare = prepare


if __name__ == '__main__':
    assert '--worker' in sys.argv
    b.base.worker()
