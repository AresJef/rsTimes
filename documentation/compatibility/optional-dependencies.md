# Install the optional features you use

The core package installs NumPy and supports scalar dates, calendar arithmetic,
`Configs`, and parsing. Install an extra when you use the corresponding
integration.

| Task | Package or extra |
| --- | --- |
| Build a pandas date index with `Pddt` | `rsTimes[pandas]` |
| Use `Pldt` or `.pldt` on a Polars column or expression | `rsTimes[polars]` |
| Import a dateutil offset or parser vocabulary | `rsTimes[dateutil]` |
| Export an Arrow object | Install `pyarrow` for the interchange method that requires it. |

The [installation page](../getting-started/install.md) has the pip commands.
Restart the interpreter after adding an optional adapter. This lets the new
process discover the installed dependency.

## Read the error for a missing extra

In an environment with only the core package, importing `Pddt` identifies
the missing pandas extra.

(optional-missing-pandas)=
```python
from rstimes import Pddt
```

**Output**

```text
ImportError: Pddt requires pandas; install rstimes[pandas].
```

Install the pandas extra before using `Pddt`. To use Polars without pandas,
install the Polars extra and [load the Polars namespace](../getting-started/polars-query.md).
