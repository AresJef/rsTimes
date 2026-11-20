# Import a dateutil parser vocabulary

Install the [dateutil extra](../getting-started/install.md) to use
`Configs.from_parserinfo`. Pass a dateutil `parserinfo` instance.

## Use a day-first parserinfo with rsTimes

(parserinfo-import-day-first)=
```python
from dateutil.parser import parserinfo
from rstimes import Configs, parse_str

info = parserinfo(dayfirst=True)
rules = Configs.from_parserinfo(info)
value = parse_str("01/02/2024", cfg=rules)
print(value.date())
```

**Output**

```text
2024-02-01
```

The adapter copies the supported flags and vocabulary. Subsequent edits
to either object have their own effect. rsTimes applies its parsing rules
using the imported terms.

## Match the fields of parserinfo to Configs

| Source attribute | Value shape | Destination |
| --- | --- | --- |
| `JUMP`, `PERTAIN`, `UTCZONE` | List, tuple, or set of words | `jump`, `pertain`, `utc` |
| `TZOFFSET` | Dictionary with offsets in integer seconds | `tzoffset` |
| `MONTHS` | List or tuple of month alias rows | `month`, starting at 1 |
| `WEEKDAYS` | List or tuple of weekday alias rows | `weekday`, starting at Monday as 0 |
| `HMS`, `AMPM` | List or tuple of alias rows | `hms` hour/minute/second, `ampm` AM/PM |

A single string row is one alias. A table set to `None` imports no
entries for that table. The adapter accepts real subclasses of the listed
containers. Invalid shapes or non-boolean flags raise `TypeError`.
Values and vocabulary conflicts follow the [Configs rules](configs.md).
Register exact region names separately with `add_tzone`.
