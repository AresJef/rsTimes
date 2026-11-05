# Inherited Polars container and selection behavior

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

```{doctest} inherited-pldt-container-metadata
>>> from datetime import datetime
>>> import polars as pl
>>> from rstimes import Pldt
>>> ticks = [1704067200000000123, None, 1704240000000000000]
>>> value = Pldt(pl.Series('event', ticks, dtype=pl.Datetime('ns', 'UTC')))
>>> (value.name, value.dtype, value.shape, len(value), value.len(), value.count(), value.null_count(), value.has_nulls(), value.is_empty())
('event', Datetime(time_unit='ns', time_zone='UTC'), (3,), 3, 3, 2, 1, True, False)
>>> physical = value.to_physical()
>>> (type(physical) is pl.Series, physical.dtype, physical.name, physical.to_list() == ticks)
(True, Int64, 'event', True)
>>> value.flags
{'SORTED_ASC': False, 'SORTED_DESC': False}
>>> (value.n_chunks(), value.chunk_lengths(), value.estimated_size(), value.estimated_size('kb'))
(1, [3], 25, 0.0244140625)
>>> value.clear().is_empty()
True
>>> sorted_dates = Pldt(pl.Series('event', [ticks[0], ticks[2]], dtype=value.dtype))
>>> declared_sorted = sorted_dates.set_sorted()
>>> (type(declared_sorted) is Pldt, declared_sorted.flags, declared_sorted.is_sorted())
(True, {'SORTED_ASC': True, 'SORTED_DESC': False}, True)
```

`set_sorted` declares an existing order; it does not sort values. Only set this
flag after establishing that the data really has the claimed order. Use an
actual sort when the data is unsorted. The displayed byte estimate belongs to
this small sample and its visible validity buffer, not every Series layout.

## Scalars, slices and native gathers

```{doctest} inherited-pldt-container-selection
>>> scalar = value[0]
>>> (type(scalar) is datetime, scalar.isoformat(), scalar.microsecond, value[1] is None)
(True, '2024-01-01T00:00:00+00:00', 0, True)
>>> def check(result, expected, cls=Pldt):
...     assert type(result) is cls and result.dtype == pl.Datetime('ns', 'UTC') and result.name == 'event'
...     assert result.to_physical().to_list() == expected
>>> check(value[1:3], [None, ticks[2]])
>>> check(value[[2, 0]], [ticks[2], ticks[0]])
>>> mask = pl.Series([True, False, True])
>>> try:
...     value[mask]
... except TypeError as error:
...     assert 'filter' in str(error)
... else:
...     raise AssertionError('native getitem must reject a Boolean mask')
>>> check(value.filter(mask), [ticks[0], ticks[2]])
>>> check(value.head(-1), [ticks[0], None])
>>> check(value.tail(-1), [None, ticks[2]])
>>> check(value.slice(-2, 1), [None])
>>> check(value.head(1), [ticks[0]])
>>> check(value.limit(1), [ticks[0]])
>>> check(value.tail(1), [ticks[2]])
>>> check(value.slice(1, 2), [None, ticks[2]])
>>> check(value.gather([2, 0]), [ticks[2], ticks[0]], pl.Series)
>>> check(value.gather_every(2), [ticks[0], ticks[2]], pl.Series)
>>> check(value.new_from_index(0, 2), [ticks[0], ticks[0]])
>>> check(value.clear(), [])
>>> exported = value.to_list()
>>> (type(exported) is list, type(exported[0]) is datetime, exported[0].microsecond, exported[1] is None)
(True, True, 0, True)
>>> (type(value.first()) is datetime, value.first().isoformat(), type(value.last()) is datetime, value.last().isoformat(), value.item(1) is None)
(True, '2024-01-01T00:00:00+00:00', True, '2024-01-03T00:00:00+00:00', True)
>>> (value.item(0).isoformat(), value.clear().first(), value.clear().last())
('2024-01-01T00:00:00+00:00', None, None)
>>> rows = list(value)
>>> (type(rows[0]) is datetime, rows[0].microsecond, rows[1] is None, rows[2].isoformat())
(True, 0, True, '2024-01-03T00:00:00+00:00')
>>> value.to_physical().to_list() == ticks
True
```

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

```{doctest} inherited-pldt-container-chunks
>>> check(value.clone(), ticks)
>>> check(value.rechunk(), ticks)
>>> check(value.shrink_to_fit(), ticks)
>>> appended = value.clone()
>>> appended.append(value) is appended
True
>>> (appended.n_chunks(), appended.chunk_lengths())
(2, [3, 3])
>>> chunks = appended.get_chunks()
>>> (type(chunks) is list, len(chunks))
(True, 2)
>>> for chunk in chunks:
...     check(chunk, ticks, pl.Series)
>>> contiguous = appended.rechunk()
>>> (type(contiguous) is Pldt, contiguous.n_chunks(), contiguous.to_physical().to_list())
(True, 1, [1704067200000000123, None, 1704240000000000000, 1704067200000000123, None, 1704240000000000000])
>>> value.to_physical().to_list() == ticks
True
>>> shell = Pldt.__new__(Pldt)
>>> shell.__init__(value) is None
True
>>> check(shell, ticks)
```

Normal application code should use `Pldt(data, ...)`. The last three lines make
the inherited allocation protocol explicit: `__new__` allocates the wrapper,
and the rsTimes initializer supplies its date data before use. It is not a
second constructor with different date rules.
