# Upgrade to rsTimes 1.1.1

Upgrade the package within your environment. The command includes both optional
adapters. Keep the extras your project uses and update its version pin and lock
file to 1.1.1.

```bash
python -m pip install --upgrade "rsTimes[pandas,polars]==1.1.1"
```

In the pandas table and Polars Struct returned by `isocalendar()`, the
`year` field now uses `Int64` and can be negative. If you declare the
result schema yourself, change `year` to `Int64`. The `week` and
`day` fields still use `UInt32`. See the
{ref}`Pddt example <pddt-iso-week-year>` and the
{ref}`Polars example <pldt-extract-iso-week-struct>`.

With 1.1.1, semi-month-start ranges require an anchor from day 2 through 27.
Semi-month-end still accepts days 1 through 27. See the
{ref}`Polars range guide <pldt-choose-range-frequency>` to choose the right
frequency. Wide integer inputs that exceed the datetime tick capacity
now report the first bad position. The
{ref}`Polars factory guide <pldt-locate-wide-tick>` shows an eager call
and its error.

The core package installs packaging. An installed pandas or Polars below
its supported minimum emits {ref}`DependencyWarning <dependency-warning-filter>`
when you first load the corresponding adapter. If a strict warning filter aborts
that import, upgrade the dependency or adjust the filter before trying again.

Polars eager unit-conversion errors identify the first unrepresentable row
and the target unit. Follow the
{ref}`inexact conversion example <pldt-recover-inexact-eager-unit>` to choose
between keeping the source resolution and flooring to the earlier output tick.
See the [1.1.1 release notes](https://github.com/AresJef/rsTimes/releases/tag/v1.1.1).
For an older installation, consult the
[exact 1.1.0 documentation](https://aresjef.github.io/rsTimes/1.1.0/)
or the [exact 1.0.0 documentation](https://aresjef.github.io/rsTimes/1.0.0/).

## Changes included since the beta

For the earlier beta-to-1.0.0 upgrade and its installation steps, see the
[1.0.0 migration guide](https://aresjef.github.io/rsTimes/1.0.0/compatibility/migration.html).

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

`parse_to_integer` and `parse_to_float` read numeric text.
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
subclasses the date or Delta types. The library uses the documented custom
copy and reduction choices. Preserve the original records when moving from a
pre-nanosecond Delta state format. See
[Delta protocol and state](../guides/delta-protocols.md) and
[Polars date state](../guides/pldt-state.md).
