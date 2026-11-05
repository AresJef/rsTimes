# Choose the date representation for your work

rsTimes uses four public classes. Delta describes a change; the other three
hold dates in the container that fits your application.

| Representation | Use it for | Result to expect |
|---|---|---|
| `Delta` | Relative calendar amounts and optional absolute field settings | A change to apply to a date; it is not a timestamp or timezone |
| `Pydt` | One scalar date with Python datetime interoperability | A datetime subclass with microsecond destination resolution |
| `Pddt` | pandas index workflows | A DatetimeIndex subclass with explicit unit and NaT behavior |
| `Pldt` | Polars Series workflows | A Series subclass with native date unit and independent null validity |
| `polars.Expr.pldt` | Date work inside eager or lazy queries | A native Expr; execute it with select or collect |

Start with the container you already use. Pddt does not require Polars; Pldt's
core date work does not require pandas, PyArrow or dateutil. Optional
interoperability paths can require those packages. Install an integration
before starting the interpreter, and check its documented input/output rules.

The shared calendar rules do not make every interface interchangeable. A
numeric argument can be an epoch tick, a calendar coordinate, a duration
amount, a row count or a rounding multiple. None can mean missing data, a
default, an unchanged field or an explicitly absent option depending on the
entry. Read the stated parameter role rather than applying one global rule.

```{toctree}
:maxdepth: 1

units-and-missing
time-and-calendars
returns-and-protocols
```

For an executed comparison across the four classes, use
[the calendar recipe](../recipes/calendar-across-containers.md).
