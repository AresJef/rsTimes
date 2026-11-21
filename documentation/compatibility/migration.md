# Upgrade to rsTimes 1.1.0

Upgrade the package within your environment. Keep the extras you use.

```bash
python -m pip install --upgrade "rsTimes[pandas,polars]==1.1.0"
```

The core package now installs packaging. An installed pandas or Polars below
its supported minimum emits {ref}`DependencyWarning <dependency-warning-filter>`
when you first load the corresponding adapter. If a strict warning filter aborts
that import, upgrade the dependency or adjust the filter before trying again.

Polars eager unit-conversion errors identify the first unrepresentable row
and the target unit. Follow the
{ref}`inexact conversion example <pldt-recover-inexact-eager-unit>` to choose
between keeping the source resolution and flooring to the earlier output tick.
See the [1.1.0 release notes](https://github.com/AresJef/rsTimes/releases/tag/v1.1.0)
and the [exact 1.0.0 documentation](https://aresjef.github.io/rsTimes/1.0.0/) as needed.

## Changes included since the beta

Upgrade with the extras your application uses. For a project that uses both
pandas and Polars, run this command.

```bash
python -m pip install --upgrade "rsTimes[pandas,polars]==1.0.0"
```

Update the rsTimes version pin in your project's requirements as well.
The [1.0.0 release notes](https://github.com/AresJef/rsTimes/releases/tag/v1.0.0)
list the release files and supported interpreters.

## Create a configuration when date order changes

The flags you pass to `Configs` set the order for that instance. Use a new
`Configs` if your next source uses another order.

(upgrade-configs-date-order)=
```python
from rstimes import Configs

first = Configs(yearfirst=False, dayfirst=True)
second = Configs(yearfirst=True, dayfirst=False)
print(first.order_hint())
print(second.order_hint())
```

**Output**

```text
D/M/Y
Y/M/D
```

Calling `__init__` again keeps the instance's flags and vocabulary.
`reset_settings()` restores the vocabulary and keeps the flags. See
[how date parsing uses Configs](../guides/configs.md).

Date parsing reads the stored content of a `str` subclass. Apply
`str(value)` yourself when you want its custom conversion before parsing.

## Read a grouped integer

The new `parse_to_integer` and `parse_to_float` functions read numeric text.
Choose integer parsing for a quantity such as `1,250`.

(upgrade-numeric-token)=
```python
from rstimes import parse_to_integer

quantity = parse_to_integer("1,250", allow_grouping=True)
print(quantity)
```

**Output**

```text
1250
```

[Date and epoch parsing](../guides/parsing.md) uses its own input rules.

## Check workday ranges with offsets

Both date column types preserve subsecond workday and work-month offsets.
When you use a normalized workday with an offset, rsTimes applies the
calendar rule and the offset before producing the normalized date.

(upgrade-normalized-workday)=
```python
from datetime import timedelta

from pandas.tseries.offsets import BusinessDay
from rstimes import Pddt

rule = BusinessDay(
    offset=timedelta(hours=2), normalize=True
)
schedule = Pddt.date_range(
    "2024-01-13 23:00", periods=1, freq=rule, unit="us"
)
print(schedule[0].date())
```

**Output**

```text
2024-01-16
```

The Saturday start rolls to a working day. The two-hour offset moves the
clock past midnight before normalization. A custom business-day rule can also
account for holidays. If you depend on a custom calendar with `periods=0`,
check the actual endpoints. A rolled endpoint can appear in the result.
See [pandas ranges](../guides/pddt-ranges.md) and
[Polars ranges](../guides/pldt-ranges.md).

## Preserve the units and time zones your application needs

ISO factories accept supported compact clocks and ISO week dates, including
inputs with negative UTC offsets. An explicit unit must be fine enough for the
result. A typed NumPy `NaT` retains its supported unit when broadcast by
`Pddt.fromdatetime64`. Polars stores null validity separately, including for
columns with a valid minimum integer tick. See
[units and missing dates](../concepts/units-and-missing.md).

With Polars, choose a supported IANA name, named zone object, or standard
fixed offset for the target. A custom or file-backed zone that cannot be
represented as a target raises `ValueError`. A genuine aware input to the
ordinary constructor can use its own offset to determine the instant.
See [Polars timezone conversions](../guides/pldt-timezones.md).

## Check custom copy and state hooks

Test shallow copy, deep copy, and state restoration if your application
subclasses the date or Delta types. 1.0.0 uses the documented custom copy
and reduction choices. Preserve the original records when moving from a
pre-nanosecond Delta state format. See
[Delta protocol and state](../guides/delta-protocols.md) and
[Polars date state](../guides/pldt-state.md).
