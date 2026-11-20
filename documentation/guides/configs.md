# Set the rules for parsing your dates

Use `Configs` when date order, vocabulary, or zone names depend on the source.

## Choose day before month

(configs-use-day-first)=
```python
from rstimes import Configs, parse_str

rules = Configs(yearfirst=False, dayfirst=True)
value = parse_str("01/02/2024", cfg=rules)
print(value.date())
```

**Output**

```text
2024-02-01
```

Choose `yearfirst` and `dayfirst` when creating a configuration. Both
flags are read-only. Pass an explicit `yearfirst` or `dayfirst` on a
parse call to override its configured value for that call.

## Recognize a month name from your data

(configs-add-month-word)=
```python
from rstimes import Configs, parse_str

rules = Configs()
rules.add_month("harvest", 10)
value = parse_str("7 harvest 2024", cfg=rules)
print(value.date())
```

**Output**

```text
2024-10-07
```

An `add_*` method adds or updates one rule. A `del_*` method returns
whether it removed the rule. Each `set_*` replaces the whole table.
Use an empty dictionary or set to clear that table. Pass `None` to restore
its defaults.

| Table | What its values mean |
| --- | --- |
| `jump` | Words that can be skipped. |
| `pertain` | Linking words such as `of`. |
| `utc` | Names for UTC. |
| `tzoffset` | A fixed UTC offset in integer seconds. `add_tzoffset` takes hours, minutes, and seconds. |
| `tzone` | Exact named IANA zones. |
| `month` | January is 1 and December is 12. |
| `weekday` | Monday is 0 and Sunday is 6. |
| `hms` | Hour is 0, minute is 1, and second is 2. |
| `ampm` | AM is 0 and PM is 1. |

Read a table property for an independent snapshot. Edit the configuration
through its methods. Ordinary vocabulary recognizes stored lower, upper,
and title case forms. Named zones use their exact IANA names. Mapped
values use integer codes and exclude booleans.

## Interpret an office's timezone label

(configs-fixed-offset-alias)=
```python
from rstimes import Configs, parse_str

rules = Configs()
rules.add_tzoffset("desktime", hours=8, minutes=30)
value = parse_str(
    "2024-01-01 09:00 desktime",
    cfg=rules, ignoretz=False,
)
print(value.isoformat())
```

**Output**

```text
2024-01-01T09:00:00+08:30
```

A fixed offset applies throughout the year. For a regional rule with
daylight-saving changes, register an exact IANA name with `add_tzone`.
When the parser recognizes both a region and a fixed offset in one input,
the region supplies the zone. For an explicit format, `%Z` reads names
from the effective configuration and `%z` reads numeric offsets.

## Reset the vocabulary and keep the date order

(configs-reset-vocabulary)=
```python
from rstimes import Configs

rules = Configs(yearfirst=False, dayfirst=True)
rules.add_month("harvest", 10)
rules.reset_settings()
print(rules.order_hint())
print(rules.month.get("harvest"))
```

**Output**

```text
D/M/Y
None
```

`clear_settings()` empties the vocabulary and `reset_settings()` restores
it. Both keep the order flags. Repeated `__init__` also keeps the existing
configuration. Create another `Configs` to change the flags.

Conflicting vocabulary in distinct semantic tables raises `ConfigError`.
Jump words may overlap. A rejected replacement leaves the previous
table in place. Finish edits before sharing a configuration for
concurrent parsing. See [copy and save settings](configs-state.md) and
[configuration in Polars queries](expressions-execution.md).
