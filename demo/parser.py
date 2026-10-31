"""Explore Parser behavior using the delivery selected in runtime.json.

Run ``python demo/parser.py`` from any directory. This uses the same selected
environment and binary verification as the Delta demo. The examples show
the string and object entrypoints, their results, and configuration changes.
The examples are interactive demonstrations, not formal performance measurements.
"""
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runtime import use_demo_runtime

use_demo_runtime(__file__, direct=__name__ == "__main__")
from datetime import date, datetime, timezone
from importlib.metadata import version
import copy
import pickle

from cytimes.parser import parse as parse_original, parse_obj as parse_object_original
from rstimes import Configs, parse_str, parse, parse_to_epoch, Pddt, Pydt as PydtR
from rstimes import _native
from rstimes.errors import ParseError, ConfigError


def _display(function, text, **kwargs):
    try:
        return function(text, **kwargs).isoformat()
    except Exception as error:
        cause = error.__cause__ or error
        return f'{type(error).__name__}: {cause}'


def parser_demo():
    """Compare ordinary parsing and the two field-validation modes."""
    print(f'rsTimes {version("rstimes")} | {_native.__file__}')
    examples = [
        ('Minute precision with timezone', '2024-05-07T15:30+08:00', {'ignoretz': False}),
        ('Invalid minute', '2024-01-02 12:99', {}),
        ('Invalid explicit date', '2024-02-30', {}),
        ('Conflicting hours', '2024-01-02 1h 2h', {}),
        ('Weekday conflict', 'Mon 2024-01-02', {}),
        ('Default month-end day', 'February 2024', {'default': date(2024, 1, 31)}),
        ('Two-digit year with reference', '01/01/75', {'default': date(2026, 1, 1), 'yearfirst': False}),
        ('Two-digit year without reference', '01/01/75', {'yearfirst': False}),
        ('Unknown words remain permissive', '2024-01-02 banana', {}),
        ('Corrected Turkish month', '14 haziran 2024', {}),
        ('Written day with leading zeroes', '2024-Jan-001', {}),
        ('Repeated complete named date', '2024-01-02 2025-Feb-03', {}),
        ('Separate AM/PM after a clock', '2024-01-02 12:00 1 PM', {}),
        ('Continue minutes after an hour unit', '2024-01-02 12:00 1h30', {}),
    ]
    for label, text, kwargs in examples:
        print(f'\n{label}: {text!r}')
        print('  Original:     ', _display(parse_original, text, **kwargs))
        print('  Rust default: ', _display(parse_str, text, **kwargs))
        print('  Rust strict:  ', _display(parse_str, text, strict=True, **kwargs))


def configs_demo():
    """Customize words, copy rules independently and restore saved settings."""
    ordering = Configs(yearfirst=False, dayfirst=True)
    print('Read-only date-order flags chosen at construction:',
          ordering.yearfirst, ordering.dayfirst)
    print('Date using those flags:', parse_str('03/04/2024', cfg=ordering))
    original = Configs()
    original.add_month('harvest', 10)
    copied = copy.copy(original)
    copied.add_month('harvest', 11)
    restored = pickle.loads(pickle.dumps(original))
    print('\nIndependent configuration copies:')
    for name, cfg in [('original', original), ('copy', copied), ('restored', restored)]:
        print(f'  {name}: {parse("14 harvest 2026", cfg=cfg).isoformat()}')
    original.add_tzoffset('XYZ', hours=5, minutes=30)
    print('  Custom timezone:', parse('2026-10-14 15:30 XYZ', cfg=original, ignoretz=False).isoformat())
    try:
        original.add_month('floating', 1.9)
    except TypeError as error:
        print('  Float rule rejected:', error)




def parse_object_demo():
    """Compare supported object inputs and show result types and identity."""
    import numpy as np
    from pandas import Timestamp
    from cytimes import Pydt
    examples = [
        ('String', '2024-05-07T15:30'),
        ('Datetime', datetime(2024, 5, 7, 15, 30, tzinfo=timezone.utc, fold=1)),
        ('Date', date(2024, 5, 7)),
        ('Integer seconds', 1),
        ('Fractional seconds', -1.23456789),
        ('NumPy nanoseconds', np.datetime64('2024-05-07T15:30:00.123456789')),
        ('Pydt', Pydt(2024, 5, 7, 15, 30)),
        ('Timestamp', Timestamp('2024-05-07T15:30:00.123456789')),
    ]
    for label, value in examples:
        print(f'\n{label}: {value!r}')
        for name, function in [('Original parse_obj', parse_object_original), ('Rust parse', parse)]:
            result = function(value)
            print(f'  {name}: {result!r}; type={type(result).__name__}; same_object={result is value}')
    print('\nCustom return type:', repr(parse(date(2024, 5, 7), dtclass=Timestamp)))
    print('NaT error:', _display(parse, np.datetime64('NaT', 'ns')))



def region_timezone_demo():
    """Read registered regions, choose a repeated time and keep nanosecond ticks."""
    cfg = Configs()
    cfg.set_tzone({'Asia/Shanghai', 'America/New_York'})
    print('\nRegistered regions:')
    text = '2024-01-02 12:00:00.123456789 Asia/Shanghai'
    print('  Datetime:', parse_str(text, cfg=cfg, ignoretz=False))
    print('  Nanosecond ticks:', parse_to_epoch(text, 'ns', cfg=cfg))
    print('  Pddt:', Pddt([text], unit='ns', cfg=cfg))
    repeated = '2024-11-03 01:30 America/New_York'
    for fold in (0, 1):
        value = parse_str(repeated, cfg=cfg, ignoretz=False, strict=True,
                          default=datetime(2024, 11, 3, fold=fold))
        print(f'  Repeated time fold={fold}:', value.isoformat())
    print('  Parser keeps the supplied gap fields:', _display(parse_str, '2024-03-10 02:30 America/New_York',
                                    cfg=cfg, ignoretz=False, strict=True))
    print('  Pydt target rejects that missing time:', _display(parse_str,
          '2024-03-10 02:30 America/New_York',cfg=cfg,ignoretz=False,dtclass=PydtR))



def errors_demo():
    """Catch text and configuration failures by their specific public classes."""
    print("\nPublic error classes:")
    assert parse_to_epoch(1e-9, unit='ns') == 1
    print('Shared native epoch precision: 1e-9 seconds -> 1 nanosecond')
    try:
        parse_str("2024-01-02 12:99", strict=True)
    except ParseError as error:
        print("  Invalid strict minute:", error)
    try:
        Configs().add_month("harvest", 13)
    except ConfigError as error:
        print("  Invalid month rule:", error)

if __name__ == '__main__':
    parser_demo()
    configs_demo()
    errors_demo()
    parse_object_demo()
    region_timezone_demo()
