# Version-specific inherited pandas entries

## Insert a missing date at a gather position

(ref-pddt-take-missing)=
```python
import pandas as pd
from rstimes import Pddt

events = Pddt(["2024-01-01", "2024-01-03"], unit="ns", tz="UTC")
selected = events.take([0, -1], allow_fill=True, fill_value=pd.NaT)
print(selected.isna().tolist())
```

**Output**

```text
[False, True]
```

Inherited method availability follows the installed pandas version. This page
covers every entry found only in a compatibility profile. The tested profiles
are pandas 2.3.3, 3.0.6 and 3.1.0; it does not predict method availability in
unreleased dependency versions. The public coverage table records the actual
profile required for each entry.

## Legacy type predicates, formatting and sorting

With pandas 2.3, the eight legacy dtype predicates below return False on Pddt
and emit FutureWarning. They describe the date dtype, not its integer storage.
`format` returns a list of display strings and also emits FutureWarning.
`sort` raises TypeError because an Index cannot sort its values in place; use
`sort_values` to obtain a new index. These ten entries are absent from the two
tested pandas 3 profiles.

Use pandas' current dtype inspection interfaces for new applications, and use
rsTimes strftime when a date format rather than a debug representation is
wanted. The [pandas Index reference](https://pandas.pydata.org/pandas-docs/stable/reference/indexing.html)
tracks the provider's current replacement interfaces.

## pandas 3.1 whole-value replacement

The tested pandas 3.1 Index adds a direct `replace` method. It replaces matching
whole values and returns ordinary DatetimeIndex for the date example below.
It is distinct from the rsTimes field replacement at `value.pddt.replace(...)`.
The direct method is absent in pandas 2.3 and 3.0, so use the namespace path for
rsTimes date-field changes across all supported profiles.

## Changed defaults and explicit missing-fill markers

The callable signatures also differ at `fillna` and `take`. With pandas 2.3,
omitting `fillna`'s value is allowed; pandas 3 requires that argument. The
legacy `downcast` argument exists only in pandas 2.3 and is deprecated. For
portable calls, pass the date value explicitly and omit `downcast`.

For `take`, an ordinary negative position selects from the end. To insert a
missing date at -1, pass `allow_fill=True, fill_value=pd.NaT` explicitly. The
older `fill_value=True` marker works in the tested pandas 2.3/3.0 profiles but
is a TypeError in pandas 3.1, which validates the supplied date fill value.
`OMITTED` in the per-entry signature means leave the argument out; it is a
provider sentinel and is distinct from passing None.
