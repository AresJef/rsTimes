# Configuration object protocols

These additional public protocols complement the declared
[Configs reference](reference/rstimes/parser/index.rst). Normal construction is
`Configs(yearfirst=True, dayfirst=False)`. The low-level allocator creates an
empty native object; its initializer installs the flags and default tables.

| Entry | Parameters and result |
|---|---|
| <span id="rstimes.Configs.__new__"></span>`Configs.__new__(Configs, *args, **kwargs)` | Allocate Configs. Complete initialization before parsing with it. |
| <span id="rstimes.Configs.__getstate__"></span>`Configs.__getstate__()` | No arguments; returns None. Pickle uses `__reduce__` / `__reduce_ex__` for the configuration snapshot. |
| <span id="rstimes.Configs.__eq__"></span><span id="rstimes.Configs.__ne__"></span>`Configs.__eq__(other)` / `Configs.__ne__(other)` | Identity comparison with ordinary reflected negotiation; equal table contents do not define equality. |
| <span id="rstimes.Configs.__hash__"></span>`Configs.__hash__()` | Return a builtin integer object hash. |
| <span id="rstimes.Configs.__str__"></span>`Configs.__str__()` | Return the configuration representation as a string. |
| <span id="rstimes.Configs.__format__"></span>`Configs.__format__(spec)` | Empty string returns its string representation; a nonempty numeric spec raises TypeError. |
| <span id="rstimes.Configs.__lt__"></span><span id="rstimes.Configs.__le__"></span><span id="rstimes.Configs.__gt__"></span><span id="rstimes.Configs.__ge__"></span>`Configs.__lt__(other)` / `Configs.__le__(other)` / `Configs.__gt__(other)` / `Configs.__ge__(other)` | Direct comparisons between ordinary configurations return NotImplemented; their rules have no value ordering. |

```{doctest} configs-additional-protocols
>>> from rstimes import Configs
>>> config = Configs.__new__(Configs)
>>> config.__init__(yearfirst=False, dayfirst=True)
>>> (config.order_hint(), config.__getstate__(), type(config.__hash__()) is int)
('D/M/Y', None, True)
>>> other = Configs(False, True)
>>> (config == other, config.__eq__(other) is NotImplemented, config.__ne__(config))
(False, True, False)
>>> (type(config.__str__()) is str, config.__format__('') == config.__str__())
(True, True)
>>> all(getattr(config, method)(other) is NotImplemented for method in ('__lt__', '__le__', '__gt__', '__ge__'))
True
```

The [configuration state guide](../guides/configs-state.md) executes copying,
pickle, state validation, format errors, and identity comparisons. Python's
[data model](https://docs.python.org/3/reference/datamodel.html) explains the
underlying object protocols.
