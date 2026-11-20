# Inherited Polars container and selection behavior

## Gather rows by position

(ref-pldt-native-gather)=
```python
from rstimes import Pldt

events = Pldt([5, None, 9], unit="ns", tz="UTC", name="event")
picked = events.gather([2, 1, 0])
print(picked.to_physical().to_list())
```

**Output**

```text
[9, None, 5]
```

Pldt keeps native Polars Series container behavior. Native methods have their
own return families: direct slicing and several wrapper operations preserve
Pldt, while `gather`, `gather_every` and `get_chunks` return ordinary Series in
the verified calls. Scalar selection and iteration return standard Python
datetime or None, which limits fractions to microseconds. Use date-column
results to retain exact nanoseconds.

The [Polars Series reference](https://docs.pola.rs/api/python/stable/reference/series/index.html)
provides complete native parameters. These examples assert actual Pldt calls,
metadata, physical values and missing values, rather than relying on Series
annotations to predict subclass behavior.

## Metadata and sizes

`len`, `shape` and `len()` include null rows; `count()` counts valid rows.
`estimated_size` reports estimated visible buffer bytes, including validity;
it is not the process's resident memory and does not prove exclusive ownership.
`flags` reports native sortedness metadata.

`set_sorted` declares an existing order; it does not sort values. Only set this
flag after establishing that the data really has the claimed order. Use an
actual sort when the data is unsorted. The displayed byte estimate belongs to
this small sample and its visible validity buffer, not every Series layout.

## Scalars, slices and native gathers

Boolean masks belong to `filter`; native `__getitem__` rejects them.
The 123 ns tail is retained by every date-column result above and is lost only
at the standard Python scalar exit. Native gathers keep unit, timezone, name
and validity even though they return plain Series.

## Clones, chunks and wrapper allocation

`clone`, `rechunk` and `shrink_to_fit` preserve Pldt in the verified default
calls. Cloning is cheap native cloning and can share immutable buffers; it is
not a guarantee of independent allocation. `append` changes the receiver's
Series wrapper and appends chunks. `get_chunks` exposes ordinary Series for
each native chunk. Rechunking combines those chunks in its result.

Normal application code should use `Pldt(data, ...)`. The last three lines make
the inherited allocation protocol explicit: `__new__` allocates the wrapper,
and the rsTimes initializer supplies its date data before use. It is not a
second constructor with different date rules.
