# Inherited pandas date fields and metadata

## Read a calendar field and its missing positions

(ref-pddt-native-field)=
```python
from rstimes import Pddt

events = Pddt(["2024-01-01", "2024-07-01", None], unit="us", tz="UTC")
quarters = events.quarter
print(quarters[:2].tolist())
print(quarters.isna().tolist())
```

**Output**

```text
[1.0, 3.0]
[False, False, True]
```

Pddt is a real `pandas.DatetimeIndex` subclass. The entries on this page use
pandas' container rules. Numeric calendar fields return ordinary pandas Index
objects; Boolean date predicates return NumPy arrays. They do not become Pddt.
Missing numeric fields are floating NaN, and date predicates are False at NaT.
`nanosecond` is the remainder after microseconds, from 0 through 999.

The table is executable: every named property is read from an actual Pddt,
including its missing row. These aliases are all exercised rather than inferred
from spelling. See the [pandas DatetimeIndex reference](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DatetimeIndex.html)
for the provider's complete reference.

## Calendar fields and aliases

`day_name(locale=None)` uses the provider's default English day names in these
profiles. A nondefault locale depends on installed operating-system locales;
this page makes no promise that arbitrary locale identifiers are available.
For the rsTimes component conversion methods with explicit output choices, see
[the Pddt calendar guide](../guides/pddt-calendar.md).

## Storage, shape and identity metadata

The UTC integer ticks below are exact nanoseconds. `asi8` and `array.asi8` use
the index's actual `unit`, rather than always meaning nanoseconds. NaT is the
pandas int64 minimum sentinel. `values` is a NumPy datetime array in UTC without
timezone metadata; `array` retains the timezone. Use documented export methods
when a copy or an explicit output unit is required.

Metadata such as `freq` describes an actual validated regular grid; construction
without an explicit frequency does not guarantee it is populated. Missing rows
prevent the sample from being monotonic and normalized under pandas' rules.

## One-dimensional views and initialization

`T`, `transpose` and `to_flat_index` preserve the index because it is already
one-dimensional and flat. `ravel`, `infer_objects` and `view` return Pddt in the
verified no-argument calls. These operations are container operations, not the
rsTimes copy protocol: this page does not promise deep ownership isolation.
Pddt construction occurs in `__new__`; the inherited object `__init__` does not
replace data when it is called on an existing object.
