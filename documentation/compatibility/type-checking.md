# Type-check rsTimes in your application

Check against the installed release in your application environment.
The rsTimes 1.1.1 development check uses Pyright 1.1.414. Select
the same interpreter for runtime and checker resolution.

## Describe an expression accessor to the checker

rsTimes registers a date namespace on native Series and Expr when
the integration loads. A checker can still see a plain
`polars.Expr` without the dynamically registered `.pldt`
attribute. Give your application a structural type for the methods
it uses, then keep using the actual Polars expression at runtime.

(type-check-registered-expr)=
```python
from typing import Protocol, cast

import polars as pl
import rstimes.pldt

class DateMethods(Protocol):
    def floor(self, freq: str) -> pl.Expr: ...

class DateExpression(Protocol):
    @property
    def pldt(self) -> DateMethods: ...

frame = pl.DataFrame({
    "event": pl.Series([4, None], dtype=pl.Datetime("ns")),
})
source = cast(DateExpression, pl.col("event"))
expr = source.pldt.floor("3ns")
print(frame.lazy().select(expr).collect()["event"].to_physical().to_list())
```

**Output**

```text
[3, None]
```

The local Protocol describes the string-frequency usage above.
The cast supplies type information, while importing the integration
registers the actual accessor. An eager `Pldt` already has its
declared `.pldt` interface.

## Check fixed frequencies in a Polars-only environment

Date `floor`, `round`, and `ceil` accept fixed-frequency
strings and standard `datetime.timedelta`. Supported pandas
fixed offsets and Timedelta are available when pandas is installed.
A plain `int` or a NumPy `timedelta64` raises `TypeError` for
these methods.

Pyright needs the matching pandas type information to check the full
declared frequency union. With no pandas or pandas stubs, Pyright
1.1.414 can miss those invalid argument types. To check the full
signature without adding pandas to the runtime, install
`pandas-stubs==3.0.5.260914` into a separate static-only directory
and set Pyright's `extraPaths` to that directory. Keep it out
of your application's runtime import path.

## Check units and shared array metadata

`Pddt.as_unit()` accepts a string at the type boundary. The four
runtime choices are `"s"`, `"ms"`, `"us"` and `"ns"`. An unknown
unit raises `ValueError`. `Pldt.as_unit()` and the two Polars
accessors use the three supported Polars unit literals.

`Delta.__array_priority__` is a float class attribute used by NumPy
when choosing which operand handles an operation. It can be read
through the class or an instance and has the value `1000.0`.

Use `rstimes.pydt.DatetimeLike` in type annotations. A consumer can
import the alias under `if TYPE_CHECKING` and postpone annotation
evaluation. At runtime pass a supported date, string or numeric value
to the actual date API.

See the [type-checking guide from the release source](https://github.com/AresJef/rsTimes/blob/v1.1.1/docs/type-checking.md)
for the pinned analyzer installation and full project gate.
