# Configuration object protocols

## Set order flags at allocation

(ref-configs-allocate-order)=
```python
from rstimes import Configs

config = Configs.__new__(Configs, yearfirst=False, dayfirst=True)
config.__init__(yearfirst=True, dayfirst=False)
print(config.order_hint())
```

**Output**

```text
D/M/Y
```

These additional public protocols complement the declared
[Configs reference](reference/rstimes/parser/index.rst). Normal construction is
`Configs(yearfirst=True, dayfirst=False)`. Allocation installs the
chosen read-only flags and default token tables. The initializer is a no-op.

| Entry | Parameters and result |
|---|---|
| <span id="rstimes.Configs.__new__"></span>`Configs(yearfirst=True, dayfirst=False)` | Construct a configuration with its default vocabulary and the chosen date-order preferences. |
| <span id="rstimes.Configs.__getstate__"></span>`Configs.__getstate__()` | No arguments; returns None. Pickle uses `__reduce__` / `__reduce_ex__` for the configuration snapshot. |
| <span id="rstimes.Configs.__eq__"></span><span id="rstimes.Configs.__ne__"></span>`Configs.__eq__(other)` / `Configs.__ne__(other)` | Identity comparison with ordinary reflected negotiation; equal table contents do not define equality. |
| <span id="rstimes.Configs.__hash__"></span>`Configs.__hash__()` | Return a builtin integer object hash. |
| <span id="rstimes.Configs.__str__"></span>`Configs.__str__()` | Return the configuration representation as a string. |
| <span id="rstimes.Configs.__format__"></span>`Configs.__format__(spec)` | Empty string returns its string representation; a nonempty numeric spec raises TypeError. |
| <span id="rstimes.Configs.__lt__"></span><span id="rstimes.Configs.__le__"></span><span id="rstimes.Configs.__gt__"></span><span id="rstimes.Configs.__ge__"></span>`Configs.__lt__(other)` / `Configs.__le__(other)` / `Configs.__gt__(other)` / `Configs.__ge__(other)` | Direct comparisons between ordinary configurations return NotImplemented; their rules have no value ordering. |

The [configuration state guide](../guides/configs-state.md) executes copying,
pickle, state validation, format errors, and identity comparisons. Python's
[data model](https://docs.python.org/3/reference/datamodel.html) explains the
underlying object protocols.
