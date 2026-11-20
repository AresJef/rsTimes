# Copy or save a parsing configuration

Create an independent copy when two inputs use different vocabularies.
Use ordinary Python copy and pickle operations.

## Try a new month mapping in a copy

(configs-copy-month-mapping)=
```python
from copy import copy

from rstimes import Configs, parse_str

source = Configs()
source.add_month("harvest", 10)
trial = copy(source)
trial.add_month("harvest", 2)
print(parse_str("7 harvest 2024", cfg=source).date())
print(parse_str("7 harvest 2024", cfg=trial).date())
```

**Output**

```text
2024-10-07
2024-02-07
```

Both shallow and deep copy produce editable configurations. Editing either
copy leaves the other configuration's vocabulary and flags intact.

## Restore a saved configuration

(configs-restore-rules)=
```python
import pickle

from rstimes import Configs

rules = Configs(yearfirst=False, dayfirst=True)
rules.add_month("harvest", 10)
saved = pickle.dumps(rules)
restored = pickle.loads(saved)
print(restored.order_hint())
print(restored.month["harvest"])
```

**Output**

```text
D/M/Y
10
```

Load only trusted pickle data. The reduction holds a versioned snapshot
with the two flags, eight word tables, and region names. The supported
version 1 form restores the flags and word tables. Version 2 also
restores region names. Malformed or unsupported snapshots raise an error.

Use the ordinary pickle interface to persist the reduction. The inherited
`__getstate__()` returns `None`. A returned table snapshot is independent
of the configuration. See [edit the vocabulary](configs.md).
