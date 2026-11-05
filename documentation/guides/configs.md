# Customize parsing with Configs

Configs holds token tables and numeric date-order preferences for the shared
parser. Pass it as `cfg=` to the parsing call or date factory. It does not
replace the parser with a different grammar.

## Choose an order

Create Configs with real Python or NumPy boolean flags. `yearfirst` and
`dayfirst` are read-only properties; a parsing call can override either flag.
`order_hint()` describes both preferences. Calling `__init__` explicitly again
replaces the preferences and resets all token rules.

```{doctest} configs-order-flags
>>> import numpy as np
>>> from rstimes import Configs, parse_str
>>> expected_orders = {(True, True): 'Y/D/M', (True, False): 'Y/M/D', (False, True): 'D/M/Y', (False, False): 'M/D/Y'}
>>> for flags, expected in expected_orders.items():
...     config = Configs(*flags)
...     assert (config.yearfirst, config.dayfirst) == flags
...     assert type(config.yearfirst) is bool and type(config.dayfirst) is bool
...     assert config.order_hint() == expected
>>> Configs(np.bool_(False), np.bool_(True)).order_hint()
'D/M/Y'
>>> try:
...     config.dayfirst = True
... except AttributeError as error:
...     print(type(error).__name__)
AttributeError
>>> for flag in (1, None, 'yes'):
...     try:
...         Configs(yearfirst=flag)
...     except TypeError:
...         continue
...     raise AssertionError(flag)
>>> allocated = Configs.__new__(Configs)
>>> allocated.__init__(yearfirst=False, dayfirst=True) is None
True
>>> (allocated.yearfirst, allocated.dayfirst)
(False, True)
```

The two-step allocation above documents the constructor protocol. Ordinary
application code should use `Configs(...)` so initialization is complete before
the object is used.

## Edit token tables

Each table has a snapshot property and `add_*`, `del_*`, and `set_*` methods.
Adding or setting a valid rule returns `True`. Deletion returns `True` for a
removed rule and `False` when it was absent. `set_*(None)` restores that table's
defaults; an empty set or dictionary clears it.

| Table | Snapshot / `set_*` input | Meaning of a mapped value |
|---|---|---|
| `jump` | set of words | Words that may be skipped. |
| `pertain` | set of words | Linking words, such as “of”. |
| `utc` | set of words | Names for UTC. |
| `tzoffset` | word → integer seconds | Fixed UTC offset; `add_tzoffset` takes hours/minutes/seconds. |
| `tzone` | set of exact region keys | IANA region names, validated and loaded when registered. |
| `month` | word → integer | January=1 through December=12. |
| `weekday` | word → integer | Monday=0 through Sunday=6. |
| `hms` | word → integer | Hour=0, minute=1, second=2. |
| `ampm` | word → integer | AM=0, PM=1. |

Returned sets and dictionaries are independent snapshots. Edit the Configs
itself using its methods; editing a displayed snapshot does not alter parsing.
Ordinary words are recognized in their stored lowercase, uppercase, and
titlecase forms. Region keys use exact, case-sensitive ZoneInfo names.

```{doctest} configs-snapshot-ownership
>>> for namespace in ('jump', 'pertain', 'utc', 'tzoffset', 'tzone', 'month', 'weekday', 'hms', 'ampm'):
...     config = Configs()
...     assert config.add_tzoffset('desktime', hours=1) is True
...     assert config.add_tzone('Asia/Shanghai') is True
...     displayed = getattr(config, namespace)
...     expected = displayed.copy()
...     displayed.clear()
...     assert getattr(config, namespace) == expected
```

```{doctest} configs-word-set-lifecycle
>>> for namespace in ('jump', 'pertain', 'utc'):
...     config = Configs()
...     token = 'custom' + namespace
...     assert getattr(config, 'add_' + namespace)(token) is True
...     snapshot = getattr(config, namespace)
...     assert type(snapshot) is set and token in snapshot
...     snapshot.clear()
...     assert token in getattr(config, namespace)
...     assert getattr(config, 'del_' + namespace)(token) is True
...     assert getattr(config, 'del_' + namespace)(token) is False
...     assert getattr(config, 'set_' + namespace)({token}) is True
...     assert token in getattr(config, namespace)
...     assert getattr(config, 'set_' + namespace)(set()) is True
...     assert getattr(config, namespace) == set()
...     assert getattr(config, 'set_' + namespace)(None) is True
```

Mapped tables follow the same edit lifecycle, while checking their own integer
value ranges. Integers and the integer index protocol are accepted; booleans,
floats, and numeric strings are not integer codes.

```{doctest} configs-mapping-lifecycle
>>> for namespace, value in (('month', 2), ('weekday', 3), ('hms', 1), ('ampm', 1)):
...     config = Configs()
...     token = 'custom' + namespace
...     assert getattr(config, 'add_' + namespace)(token, np.int64(value)) is True
...     snapshot = getattr(config, namespace)
...     assert type(snapshot) is dict and snapshot[token] == value
...     snapshot.clear()
...     assert getattr(config, namespace)[token] == value
...     assert getattr(config, 'del_' + namespace)(token) is True
...     assert getattr(config, 'del_' + namespace)(token) is False
...     assert getattr(config, 'set_' + namespace)({token: value}) is True
...     assert getattr(config, namespace)[token] == value
...     assert getattr(config, 'set_' + namespace)({}) is True
...     assert getattr(config, namespace) == {}
...     assert getattr(config, 'set_' + namespace)(None) is True
```

## Parse using the rules you installed

```{doctest} configs-semantic-tokens
>>> from datetime import timedelta
>>> config = Configs()
>>> config.add_month('harvest', 2)
True
>>> [parse_str('29 ' + token + ' 2024', cfg=config).isoformat() for token in ('harvest', 'Harvest', 'HARVEST')]
['2024-02-29T00:00:00', '2024-02-29T00:00:00', '2024-02-29T00:00:00']
>>> config.add_weekday('cycle', 3)
True
>>> parse_str('cycle 2024-01-04', cfg=config, strict=True).weekday()
3
>>> for flag, expected in ((0, (3, 0, 0)), (1, (0, 3, 0)), (2, (0, 0, 3))):
...     assert config.set_hms({'shiftunit': flag}) is True
...     value = parse_str('2024-01-02 3shiftunit', cfg=config)
...     assert (value.hour, value.minute, value.second) == expected
>>> for flag, expected in ((0, 3), (1, 15)):
...     assert config.set_ampm({'daypart': flag}) is True
...     assert parse_str('2024-01-02 3 daypart', cfg=config).hour == expected
>>> config.add_utc('universal')
True
>>> parse_str('1970-01-01 00:00 universal', cfg=config, ignoretz=False).utcoffset() == timedelta(0)
True
```

## Fixed offsets and region names

Offset components combine into a fixed offset strictly between −24 and +24
hours. A region has changing calendar rules; it is not a fixed abbreviation.
Names such as CST do not acquire an assumed host-local meaning. Configure an
explicit alias or register a full region name for the meaning you intend.

```{doctest} configs-fixed-offset
>>> config = Configs()
>>> config.add_tzoffset('desktime', hours=8, minutes=30, seconds=15)
True
>>> (type(config.tzoffset) is dict, config.tzoffset['desktime'])
(True, 30615)
>>> parse_str('1970-01-01 08:30:15 desktime', cfg=config, ignoretz=False).utcoffset().total_seconds()
30615.0
>>> config.del_tzoffset('desktime'), config.del_tzoffset('desktime')
(True, False)
>>> config.set_tzoffset({'desktime': 3600})
True
>>> config.tzoffset['desktime']
3600
>>> config.set_tzoffset({}), config.tzoffset, config.set_tzoffset(None)
(True, {}, True)
```

```{doctest} configs-region-lifecycle
>>> config = Configs()
>>> config.add_tzone('Asia/Shanghai')
True
>>> snapshot = config.tzone
>>> (type(snapshot) is set, 'Asia/Shanghai' in snapshot)
(True, True)
>>> snapshot.clear()
>>> 'Asia/Shanghai' in config.tzone
True
>>> regional = parse_str('1970-01-01 08:00 Asia/Shanghai', cfg=config, ignoretz=False)
>>> (regional.tzinfo.key, regional.utcoffset().total_seconds())
('Asia/Shanghai', 28800.0)
>>> config.del_tzone('Asia/Shanghai'), config.del_tzone('Asia/Shanghai')
(True, False)
>>> config.set_tzone({'Asia/Shanghai'}), 'Asia/Shanghai' in config.tzone
(True, True)
>>> config.set_tzone(set()), config.tzone, config.set_tzone(None)
(True, set(), True)
```

## Validation, reset, and reinitialization

Conflicting words in distinct semantic tables raise `ConfigError`; jump words
are the explicit overlap exception. A failed replacement leaves that table's
previous rules intact. `clear_settings()` clears the token tables, while
`reset_settings()` restores them; both preserve the two date-order flags.

```{doctest} configs-errors-and-reset
>>> from rstimes.errors import ConfigError
>>> config = Configs(yearfirst=False, dayfirst=True)
>>> before = config.month
>>> try:
...     config.add_month('monday', 2)
... except ConfigError as error:
...     print(type(error).__name__, config.month == before)
ConfigError True
>>> config.add_jump('monday')
True
>>> for method, value in (('add_month', True), ('add_weekday', 1.0), ('add_hms', '1'), ('add_ampm', np.bool_(False))):
...     try:
...         getattr(config, method)('customtoken', value)
...     except TypeError:
...         continue
...     raise AssertionError(method)
>>> namespaces = ('jump', 'pertain', 'utc', 'tzoffset', 'tzone', 'month', 'weekday', 'hms', 'ampm')
>>> config.clear_settings()
True
>>> (all(not getattr(config, namespace) for namespace in namespaces), config.yearfirst, config.dayfirst)
(True, False, True)
>>> config.reset_settings()
True
>>> (config.month['jan'], config.yearfirst, config.dayfirst)
(1, False, True)
>>> config.add_month('harvest', 10)
True
>>> config.__init__(yearfirst=True, dayfirst=False)
>>> ('harvest' in config.month, config.yearfirst, config.dayfirst)
(False, True, False)
>>> try:
...     class CustomConfigs(Configs):
...         pass
... except TypeError as error:
...     print(type(error).__name__)
TypeError
```

Use [configuration copying and imports](configs-state.md) to adapt a dateutil
parserinfo or save an independent snapshot. Finish business edits before
sharing one Configs for concurrent parsing. Read-only use can share its lookup
cache; overlapping edits or edit/read operations on one instance can raise
`RuntimeError`. Edits on separate configurations are independent.
