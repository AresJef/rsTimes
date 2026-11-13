"""Fixed public-call workloads for Config and function-based parse comparison.

Setup, output checks and serialization are outside the business timing loop.
Both implementations execute identical generated loop bodies and release each
result within the loop. Config mutation rows are complete restoring cycles.
"""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import hashlib
import json


@dataclass(frozen=True)
class Scene:
    id: str
    label: str
    group: str
    expression: str
    text: str | None = None
    config_mode: str | None = None
    catches: bool = False


PARSE = (
    Scene('B01', 'ISO calendar date', 'parse', 'fn(text)', '2026-10-14'),
    Scene('B02', 'ISO basic date', 'parse', 'fn(text)', '20261014'),
    Scene('B03', 'ISO datetime with fraction', 'parse', 'fn(text)', '2026-10-14T15:30:45.123456'),
    Scene('B04', 'ISO UTC', 'parse', 'fn(text, ignoretz=False)', '2026-10-14T15:30:45.123456Z'),
    Scene('B05', 'ISO positive offset', 'parse', 'fn(text, ignoretz=False)', '2026-10-14T15:30:45.123456+08:00'),
    Scene('B06', 'ISO negative offset', 'parse', 'fn(text, ignoretz=False)', '2026-10-14T15:30:45.123456-05:30'),
    Scene('B07', 'ISO ordinal date', 'parse', 'fn(text)', '2026-287'),
    Scene('B08', 'ISO week date', 'parse', 'fn(text)', '2026-W42-3'),
    Scene('B09', 'ISO text through general lexer', 'parse', 'fn(text, isoformat=False)', '2026-10-14T15:30:45.123456'),
    Scene('B10', 'Explicit year first', 'parse', 'fn(text, yearfirst=True)', '26/10/14'),
    Scene('B11', 'Explicit day first', 'parse', 'fn(text, yearfirst=False, dayfirst=True)', '14/10/26'),
    *(Scene(f'B{12+i:02}', f'Ambiguous YMD {y}/{d}', 'parse', f'fn(text, yearfirst={y}, dayfirst={d})', '01/05/09')
      for i, (y, d) in enumerate(((False, False), (False, True), (True, False), (True, True)))),
    Scene('B16', 'English abbreviated month', 'parse', 'fn(text)', '14 Oct 2026'),
    Scene('B17', 'English month and AM/PM', 'parse', 'fn(text)', 'October 14, 2026 3:30 pm'),
    Scene('B18', 'Chinese date', 'parse', 'fn(text)', '2026年10月14日'),
    Scene('B19', 'German month', 'parse', 'fn(text)', '14 Oktober 2026'),
    Scene('B20', 'Time with default date', 'parse', 'fn(text, default=start_date)', '15:30'),
    Scene('B21', 'Long fraction with default date', 'parse', 'fn(text, default=start_date)', '15:30:45.123456789'),
    Scene('B22', 'Leap day', 'parse', 'fn(text)', '2024-02-29'),
    Scene('B23', 'Maximum datetime', 'parse', 'fn(text)', '9999-12-31T23:59:59.999999'),
    Scene('B24', 'Missing day clamps default month end', 'parse', 'fn(text, default=month_end)', '2024-02'),
    Scene('B25', 'Weekday shifts across month boundary', 'parse', 'fn(text, default=month_start)', 'Wed Oct 2026'),
    Scene('B26', 'Reuse custom ordering Config', 'parse', 'fn(text, cfg=cfg)', '01/05/09', config_mode='ordering'),
    Scene('B27', 'Override custom ordering Config', 'parse', 'fn(text, cfg=cfg, yearfirst=True, dayfirst=False)', '01/05/09', config_mode='ordering'),
    Scene('B28', 'Custom month vocabulary', 'parse', 'fn(text, cfg=cfg)', '14 harvest 2026', config_mode='month'),
    Scene('B29', 'Custom timezone vocabulary', 'parse', 'fn(text, cfg=cfg, ignoretz=False)', '2026-10-14 15:30 XYZ', config_mode='timezone'),
    Scene('B30', 'Actual Pydt constructor', 'parse', 'fn(text, dtclass=pydt_class)', '2026-10-14T15:30'),
    Scene('B31', 'Empty string error and handling', 'parse', 'fn(text)', '', catches=True),
    Scene('B32', 'Unrecognized text error and handling', 'parse', 'fn(text)', 'no date here; ' * 40, catches=True),
    Scene('B33', 'Unknown timezone label', 'parse', 'fn(text, ignoretz=False)', '2026-10-14T15:30 LCL'),
    Scene('B34', 'Default datetime time is not inherited', 'parse', 'fn(text, default=start_dt)', '15:30'),
    Scene('B35', 'Missing date error and handling', 'parse', 'fn(text)', '15:30', catches=True),
    Scene('B36', 'Preserved invalid-day clamp', 'parse', 'fn(text)', '2024-02-30'),
)

class DemoDatetime(datetime):
    pass


def datetime_factory(**fields):
    return datetime(**fields)


class Truth:
    def __bool__(self):
        return True


NAMES = ('jump', 'pertain', 'utc', 'tz', 'month', 'weekday', 'hms', 'ampm')
LOOKUPS = ('cfg.is_jump("at")', 'cfg.is_pertain("of")', 'cfg.is_utc("UTC")',
           'cfg.get_tz_offset("notalias")', 'cfg.get_month("Oct")',
           'cfg.get_weekday("Wed")', 'cfg.get_hms("h")', 'cfg.get_ampm("pm")')
CONFIG = (
    Scene('K01', 'Default Config construction', 'config', 'cls()'),
    Scene('K02', 'Explicit ordering Config construction', 'config', 'cls(False, True)'),
    Scene('K03', 'All vocabulary property copies', 'config', '(' + ', '.join('cfg.' + n for n in NAMES) + ')'),
    Scene('K04', 'All namespace queries', 'config', '(' + ', '.join(LOOKUPS) + ')'),
    *(Scene(f'K{5+i:02}', f'{name} real add/remove cycle', 'config',
            f'(cfg.add_{name}("benchalias"' + ('' if i < 3 else ', 1') + f'), cfg.remove_{name}("benchalias"))')
      for i, name in enumerate(NAMES)),
    Scene('K13', 'Clear/reset cycle', 'config', '(cfg.clear_settings(), cfg.reset_settings())'),
    Scene('K14', 'Jump replacement round trip', 'config', '(cfg.replace_jump(jump_a), cfg.replace_jump(jump_b))'),
    Scene('K15', 'Month replacement round trip', 'config', '(cfg.replace_month(month_a), cfg.replace_month(month_b))'),
    Scene('K16', 'Full parserinfo conversion', 'config', 'cls.from_parserinfo(info)'),
    Scene('K17', 'All eight queries with a configured timezone alias', 'config',
          '(' + ', '.join(item.replace('"notalias"', '"XYZ"') for item in LOOKUPS) + ')',
          config_mode='timezone'),
)
COMPAT = (
    Scene('C01', 'Configuration subclass query', 'compat', 'fn(text, cfg=cfg)', '14 Oct 2026', config_mode='subclass'),
    Scene('C02', 'Datetime subclass constructor', 'compat', 'fn(text, dtclass=child_class)', '2026-10-14T15:30'),
    Scene('C03', 'Callable datetime constructor', 'compat', 'fn(text, dtclass=factory)', '2026-10-14T15:30'),
    Scene('C04', 'Custom truth value for yearfirst', 'compat', 'fn(text, yearfirst=truth)', '26/10/14'),
    Scene('C05', 'Non-ASCII French month', 'compat', 'fn(text)', '14 août 2026'),
)
SCENES = PARSE + CONFIG + COMPAT
assert len(PARSE) == 36 and len(CONFIG) == 17


def namespace(role, scene):
    """Prepare independent inputs and Config state for one implementation."""
    from dateutil.parser import parserinfo
    from cytimes import Pydt
    if role == 'A':
        from cytimes.parser import Configs as cls, parse as fn
    elif role == 'B':
        from rstimes.parser import Configs as cls, parse as fn
    else:
        raise ValueError('Role must be A (frozen original) or B (Rust)')
    cfg = cls(False, True) if scene.config_mode == 'ordering' else cls()
    if scene.config_mode == 'month':
        cfg.add_month('harvest', 10)
    elif scene.config_mode == 'timezone':
        (cfg.add_tzoffset if hasattr(cfg, 'add_tzoffset') else cfg.add_tz)('XYZ', 8)
    if scene.config_mode == 'subclass':
        class CustomConfigs(cls):
            def get_month(self, token):
                return super().get_month(token)
        cfg = CustomConfigs()
    return dict(fn=fn, cls=cls, cfg=cfg, text=scene.text,
                start_date=date(2026, 10, 14), month_end=date(2024, 1, 31),
                month_start=date(2026, 10, 1), start_dt=datetime(2026, 10, 14, 11, 22, 33, 4444),
                pydt_class=Pydt, info=parserinfo(),
                jump_a={' ', '.', 'benchjumpa'}, jump_b={' ', '.', 'benchjumpb'},
                month_a={'benchmontha': 1}, month_b={'benchmonthb': 2},
                child_class=DemoDatetime, factory=datetime_factory, truth=Truth())


def build(role, scene):
    """Create a direct public-call loop; no additional per-call wrapper."""
    env = namespace(role, scene)
    statement = f'result = {scene.expression}\n        del result'
    if scene.catches:
        statement = ('try:\n            ' + statement.replace('\n', '\n    ')
                     + '\n        except Exception:\n            pass')
    # Keep all hot inputs local in the same way on both sides.
    bindings = ', '.join(f'{k}={k}' for k in env)
    source = f'def run(n, {bindings}):\n    for _ in range(n):\n        {statement}\n'
    exec(compile(source, '<parser-workload-' + scene.id + '>', 'exec'), env)
    return env['run'], source


def check_outputs():
    """Check all outputs before timing, retaining the full logical value."""
    from tests.parser.cases import outcome, config_state
    rows = []
    for scene in SCENES:
        results = {}
        for role in ('A', 'B'):
            env = namespace(role, scene)
            if scene.id in ('K01', 'K02', 'K16'):
                results[role] = outcome(lambda: config_state(eval(scene.expression, env)))
            else:
                results[role] = outcome(lambda: eval(scene.expression, env))
        if results['A'] != results['B']:
            raise AssertionError((scene.id, results))
        if scene.catches != ('error' in results['A']):
            raise AssertionError((scene.id, 'exception workload mismatch', results))
        rows.append(dict(id=scene.id, group=scene.group, label=scene.label,
                         expression=scene.expression, text=scene.text,
                         config_mode=scene.config_mode, catches=scene.catches,
                         weight=1 if scene.group == 'parse' else None,
                         output=results['A'], loop_sha256=hashlib.sha256(build('A', scene)[1].encode()).hexdigest()))
    return rows


if __name__ == '__main__':
    import argparse
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    rows = check_outputs()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(scenes=rows, parse_rows=len(PARSE), config_rows=len(CONFIG)),
                                      ensure_ascii=False, indent=2))
    print(f'Validated and froze {len(rows)} identical workloads: 36 parse, 17 Config')
