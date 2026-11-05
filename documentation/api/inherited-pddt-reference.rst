Inherited pandas entry reference
================================

Each path below is an inherited Pddt entry. Callable signatures omit upstream
type annotations so they do not contradict the observed return families. They
retain actual parameter names, defaults and keyword boundaries. ``OMITTED``
means leave the argument out; it is a provider sentinel, not a user value.
Differences between the tested dependency profiles are listed at the entry.
The linked examples explain parameter roles and verify actual Pddt results.

For complete provider parameter details, see the `pandas Index reference
<https://pandas.pydata.org/pandas-docs/stable/reference/indexing.html>`_.
No entry on this page is a product-implementation change.

.. py:property:: rstimes.Pddt.T

   Read the one-dimensional transpose, which is this index itself.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.__abs__()

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__and__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__array__(dtype=None, copy=None)

   Convert through NumPy array protocol; aware dates default to object Timestamp values, while an explicit datetime dtype stores UTC without timezone metadata.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__array_ufunc__(ufunc, method, *inputs, **kwargs)

   Dispatch NumPy ufuncs using the pandas date interface; verified comparison, elapsed addition, date subtraction and unsupported multiplication have distinct result roles.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__bool__()

   Reject a scalar truth value with ValueError, including for an empty date index.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__contains__(key)

   Test membership of a date label and return a Python bool; this is label lookup, not positional selection.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.__divmod__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__eq__(other)

   Compare each date with the supplied date operand and return a NumPy Boolean array. NaT has the explicitly tested equality/inequality/ordering behavior.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__floordiv__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__format__(format_spec, /)

   Support the empty display format; a numeric formatting specification raises TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__ge__(other)

   Compare each date with the supplied date operand and return a NumPy Boolean array. NaT has the explicitly tested equality/inequality/ordering behavior.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__getitem__(key)

   Select by integer position, positional slice, or integer/Boolean gather; a scalar is Timestamp/NaT and date-index selections are Pddt.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.__gt__(other)

   Compare each date with the supplied date operand and return a NumPy Boolean array. NaT has the explicitly tested equality/inequality/ordering behavior.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:attribute:: rstimes.Pddt.__hash__

   Disabled Index hash protocol. hash(value) raises TypeError; this attribute is None and cannot be called.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__iadd__(other)

   Rebind a variable to a new Pddt after a supported date addition; aliases to the original immutable index retain their dates.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__init__(*args, **kwargs)

   The inherited object initializer; Pddt date construction is performed by its public constructor in __new__. Calling the existing object initializer does not replace its dates.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.__invert__()

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__iter__()

   Iterate pandas Timestamp objects and NaT without converting them to Pydt.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.__le__(other)

   Compare each date with the supplied date operand and return a NumPy Boolean array. NaT has the explicitly tested equality/inequality/ordering behavior.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__len__()

   Return the number of date rows, including missing rows.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.__lt__(other)

   Compare each date with the supplied date operand and return a NumPy Boolean array. NaT has the explicitly tested equality/inequality/ordering behavior.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__mod__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__mul__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__ne__(other)

   Compare each date with the supplied date operand and return a NumPy Boolean array. NaT has the explicitly tested equality/inequality/ordering behavior.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__neg__()

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__or__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__pos__()

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__pow__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rand__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rdivmod__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__repr__()

   Return a pandas-style display string identifying Pddt, dates, NaT and date metadata.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rfloordiv__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rmod__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rmul__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__ror__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rpow__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rsub__(other)

   Subtract this date index from a scalar date and return pandas TimedeltaIndex in the result unit.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rtruediv__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__rxor__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__setitem__(key, value)

   Reject item assignment because pandas Index date values are immutable.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.__str__()

   Return the pandas-style Pddt display string.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__truediv__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.__xor__(other)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.all(*args, **kwargs)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.any(*args, **kwargs)

   Unsupported numeric/Boolean operation on date dtype; the documented unary or integer-operand call raises native TypeError.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.append(other)

   Concatenate the supplied date indexes and return ordinary DatetimeIndex for the verified matching date dtype.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.argmax(axis=None, skipna=True, *args, **kwargs)

   Return the integer position of the first maximum, skipping NaT by default.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.argmin(axis=None, skipna=True, *args, **kwargs)

   Return the integer position of the first minimum, skipping NaT by default.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.argsort(*args, **kwargs)

   Return NumPy positions that order the date labels; the verified default places NaT last.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.array

   Expose the pandas DatetimeArray, retaining its date unit, timezone and missing values.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.asi8

   Expose int64 ticks in the actual index unit; int64 minimum is the pandas NaT sentinel.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.asof(label)

   Return the latest valid label at or before the query on a sorted index, or NaT when no label qualifies.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.asof_locs(where, mask)

   Return latest qualifying label positions for sorted queries, honoring an explicit source-validity mask; -1 means no match.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.astype(dtype, copy=True)

   Cast using pandas rules; verified int64 and object outputs are ordinary pandas Index, not Pddt.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:property:: rstimes.Pddt.day

   Read local day of month as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.day_name(locale=None)

   Return English day-name labels by default in ordinary pandas Index; NaT remains missing. Nondefault locale availability depends on the host.

   **Observed dependency signatures:**

   * pandas3.0: ``day_name(locale=None)``.
   * pandas2.3: ``day_name(*args, **kwargs)``.
   * pandas3.1: ``day_name(locale=None)``.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.day_of_week

   Read Monday-zero local weekday as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.day_of_year

   Read one-based local day of year as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.dayofweek

   Read Monday-zero local weekday as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.dayofyear

   Read one-based local day of year as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.days_in_month

   Read calendar days in the local month as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.daysinmonth

   Read calendar days in the local month as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.delete(loc)

   Remove rows by integer position and return Pddt.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.difference(other, sort=None)

   Return Pddt labels present in this index and absent in the other operand.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.drop(labels, errors='raise')

   Remove labels and return Pddt; a missing label raises KeyError unless errors is ignore.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.drop_duplicates(*, keep='first')

   Return Pddt with duplicate occurrences removed according to keep.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.droplevel(level=0)

   Reject removal of the only level because an Index must retain a level.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.dropna(how='any')

   Remove missing date rows and return Pddt.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.dtype

   Read the actual pandas datetime dtype, including unit and aware timezone metadata.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.duplicated(keep='first')

   Return a NumPy Boolean mask identifying duplicate label occurrences under keep.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.empty

   Report whether the index has zero elements.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.equals(other)

   Return scalar value equality, ignoring an index-name difference.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.factorize(sort=False, use_na_sentinel=True)

   Return integer codes and ordinary DatetimeIndex unique labels; the default missing code is -1.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.fillna(value)

   Replace NaT with the supplied date and return ordinary DatetimeIndex when replacement is needed. A no-missing no-op can retain Pddt. Omitted-value/downcast availability is version-dependent.

   **Observed dependency signatures:**

   * pandas3.0: ``fillna(value)``.
   * pandas2.3: ``fillna(value=None, downcast=OMITTED)``.
   * pandas3.1: ``fillna(value)``.

   **Executed examples:** :doc:`inherited-pddt-compatibility`, :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.format(name=False, formatter=None, na_rep='NaT', date_format=None)

   Legacy pandas2.3 display formatter returning list[str] and emitting FutureWarning; absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:property:: rstimes.Pddt.freq

   Read an explicitly validated frequency object, or None when no frequency is attached.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.freqstr

   Read the attached frequency string, or None.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.get_indexer(target, method=None, limit=None, tolerance=None)

   Return target-to-source positions with -1 for missing targets; duplicate source labels are rejected.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.get_indexer_for(target)

   Return all matching positions for target labels, including duplicate source matches.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.get_indexer_non_unique(target)

   Return source match positions and positions of unmatched targets; -1 marks a missing match.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.get_level_values(level)

   Return this single-level date index at a valid level; an out-of-range level is rejected.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.get_loc(key)

   Find a label as a position, duplicate slice or Boolean mask; a missing label raises KeyError.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.get_slice_bound(label, side)

   Return the positional left or right boundary for a label.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.groupby(values)

   Group index labels by supplied keys and return a dict subclass whose date groups are Pddt.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.has_duplicates

   Report whether at least one date label is repeated.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.hasnans

   Report whether at least one NaT is present.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.holds_integer()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:property:: rstimes.Pddt.hour

   Read local hour as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.identical(other)

   Return scalar equality including index metadata such as its name.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.indexer_at_time(time, asof=False)

   Return integer positions matching the requested local time of day.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.indexer_between_time(start_time, end_time, include_start=True, include_end=True)

   Return integer positions in a local-clock interval, with explicit endpoint inclusion choices.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.infer_objects(copy=True)

   Return an inferred index; the verified existing date dtype remains Pddt.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.inferred_freq

   Infer a regular frequency from date values when possible; the verified missing/irregular sample returns None.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.inferred_type

   Read pandas inferred label kind; the verified date index reports datetime64.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.insert(loc, item)

   Insert a date at an integer position and return Pddt for matching date values.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.intersection(other, sort=False)

   Return shared unique date labels as Pddt.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.is_(other)

   Test whether indexes share the pandas index identity token; this is not a date comparison.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.is_boolean()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:method:: rstimes.Pddt.is_categorical()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:method:: rstimes.Pddt.is_floating()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:method:: rstimes.Pddt.is_integer()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:method:: rstimes.Pddt.is_interval()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:property:: rstimes.Pddt.is_leap_year

   Read the local-calendar is leap year predicate as a NumPy Boolean array; NaT is False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_monotonic_decreasing

   Report nonincreasing label order under pandas missing/order rules.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_monotonic_increasing

   Report nondecreasing label order under pandas missing/order rules.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_month_end

   Read the local-calendar is month end predicate as a NumPy Boolean array; NaT is False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_month_start

   Read the local-calendar is month start predicate as a NumPy Boolean array; NaT is False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_normalized

   Report whether all dates are midnight-normalized under pandas rules; the verified sample with NaT returns False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.is_numeric()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:method:: rstimes.Pddt.is_object()

   Legacy pandas2.3 dtype predicate: returns False for this date dtype and emits FutureWarning. Absent in the tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:property:: rstimes.Pddt.is_quarter_end

   Read the local-calendar is quarter end predicate as a NumPy Boolean array; NaT is False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_quarter_start

   Read the local-calendar is quarter start predicate as a NumPy Boolean array; NaT is False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_unique

   Report whether date labels are unique.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_year_end

   Read the local-calendar is year end predicate as a NumPy Boolean array; NaT is False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.is_year_start

   Read the local-calendar is year start predicate as a NumPy Boolean array; NaT is False.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.isin(values, level=None)

   Return a NumPy Boolean membership mask for supplied labels.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.isna()

   Return a NumPy Boolean mask that is True at NaT.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.isnull()

   Return a NumPy Boolean missing-date mask.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.item()

   Return one Timestamp/NaT only when the index contains exactly one item; another length raises ValueError.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.join(other, *, how='left', level=None, return_indexers=False, sort=False)

   Join date labels and optionally return left/right position indexers; -1 marks a missing match.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.map(mapper, na_action=None)

   Apply a mapper to date labels; the result family follows the mapped values. Verified integer values produce ordinary pandas Index.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.max(axis=None, skipna=True, *args, **kwargs)

   Return the latest Timestamp, skipping NaT by default; empty/all-missing or skipna=False with NaT returns NaT.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.mean(*, skipna=True, axis=0)

   Return mean instant as Timestamp, skipping NaT by default.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.memory_usage(deep=False)

   Report estimated memory usage in bytes, which can include a populated pandas lookup engine in addition to the date buffer.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:property:: rstimes.Pddt.microsecond

   Read complete fraction in microseconds as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.min(axis=None, skipna=True, *args, **kwargs)

   Return the earliest Timestamp, skipping NaT by default; empty/all-missing or skipna=False with NaT returns NaT.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:property:: rstimes.Pddt.minute

   Read local minute as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.month

   Read local month number as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.name

   Read or assign the one index-name metadata value.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.names

   Read the one-element list-like collection of index-level names.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.nanosecond

   Read nanosecond remainder after microseconds as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.nbytes

   Read the raw date value buffer size in bytes.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.ndim

   Read the number of dimensions: one for an index.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.nlevels

   Read the number of index levels: one for Pddt.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.notna()

   Return a NumPy Boolean mask that is True at valid dates.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.notnull()

   Return a NumPy Boolean valid-date mask.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.nunique(dropna=True)

   Return an integer unique-label count, excluding NaT by default.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.putmask(mask, value)

   Replace positions where the supplied Boolean mask is True; return Pddt on pandas2.3/3.0 and ordinary DatetimeIndex on pandas3.1 in the tested profiles.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.quarter

   Read local quarter number as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.ravel(order='C')

   Return a flattened Pddt view/result with the same dates and date metadata in the verified call.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.reindex(target, method=None, level=None, limit=None, tolerance=None)

   Return a new index and target-to-source indexer; duplicate source labels raise ValueError.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.rename(name, *, inplace=False)

   Return a Pddt with a new name, or update name metadata and return None with inplace=True.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.repeat(repeats, axis=None)

   Repeat each date by the requested count and return Pddt, retaining missing rows.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.replace(to_replace=None, value=OMITTED, regex=False)

   pandas3.1 whole-value replacement, distinct from pddt.replace field replacement; the verified date result is ordinary DatetimeIndex.

   **Availability in tested profiles:** current.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:property:: rstimes.Pddt.resolution

   Read the finest nonzero calendar/clock field represented by the values; it does not choose an output storage unit.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.searchsorted(value, side='left', sorter=None)

   Find insertion positions in sorted labels; return a NumPy integer or integer array for scalar/vector queries.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.second

   Read whole local second as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.set_names(names, *, level=None, inplace=False)

   Set the one index-level name; return Pddt by default or None with inplace=True.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:property:: rstimes.Pddt.shape

   Read the one-dimensional shape tuple.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.shift(periods=1, freq=None)

   Change date labels by periods of a frequency and return ordinary DatetimeIndex for the verified call. Missing source frequency requires an explicit freq.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.size

   Read the number of elements, including NaT.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.slice_indexer(start=None, end=None, step=None)

   Build a label slice indexer whose date endpoints are inclusive.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.slice_locs(start=None, end=None, step=None)

   Return positional start and stop bounds for an inclusive label slice.

   **Executed examples:** :doc:`inherited-pddt-indexing`.

.. py:method:: rstimes.Pddt.sort(*args, **kwargs)

   Legacy pandas2.3 in-place sort entry that raises TypeError and directs callers to sort_values; absent in tested pandas3profiles.

   **Availability in tested profiles:** pandas2.

   **Executed examples:** :doc:`inherited-pddt-compatibility`.

.. py:method:: rstimes.Pddt.sort_values(*, return_indexer=False, ascending=True, na_position='last', key=None)

   Return a sorted Pddt; return_indexer=True also returns its NumPy permutation array.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.sortlevel(level=None, ascending=True, sort_remaining=None, na_position='first')

   Sort the single date level and return Pddt plus a NumPy permutation array.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.std(axis=None, dtype=None, out=None, ddof=1, keepdims=False, skipna=True)

   Return elapsed sample standard deviation as pandas Timedelta, with ddof1 by default and optional missing-value exclusion.

   **Observed dependency signatures:**

   * pandas3.0: ``std(axis=None, dtype=None, out=None, ddof=1, keepdims=False, skipna=True)``.
   * pandas2.3: ``std(*args, **kwargs)``.
   * pandas3.1: ``std(axis=None, dtype=None, out=None, ddof=1, keepdims=False, skipna=True)``.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:property:: rstimes.Pddt.str

   Read the inherited pandas string accessor. A date dtype raises AttributeError; it does not create a string-processing namespace.

   **Executed examples:** :doc:`inherited-pddt-protocols`.

.. py:method:: rstimes.Pddt.symmetric_difference(other, result_name=None, sort=None)

   Return labels present in exactly one operand as ordinary DatetimeIndex for the verified matching date dtype.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.take(indices, axis=0, allow_fill=True, fill_value=None, **kwargs)

   Select requested integer positions; negative-index and explicit missing-fill roles depend on allow_fill/fill_value.

   **Observed dependency signatures:**

   * pandas3.0: ``take(indices, axis=0, allow_fill=True, fill_value=None, **kwargs)``.
   * pandas2.3: ``take(indices, axis=0, allow_fill=True, fill_value=None, **kwargs)``.
   * pandas3.1: ``take(indices, axis=0, allow_fill=OMITTED, fill_value=OMITTED, **kwargs)``.

   **Executed examples:** :doc:`inherited-pddt-compatibility`, :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.to_flat_index()

   Return this already flat index itself.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.to_frame(index=True, name=OMITTED)

   Return pandas DataFrame containing the date values; index=False uses an ordinary RangeIndex.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.to_julian_date()

   Return ordinary floating pandas Index of Julian day numbers, with NaN at NaT and noon as the integer boundary.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.to_list()

   Return a Python list of pandas Timestamp values and NaT, preserving Timestamp nanoseconds.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.to_numpy(dtype=None, copy=False, na_value=OMITTED, **kwargs)

   Export a NumPy array with pandas dtype/copy rules; aware default object output differs from explicit timezone-free datetime dtype output.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.to_period(freq=None)

   Return pandas PeriodIndex at the requested frequency; an aware source emits UserWarning because periods discard timezone information.

   **Observed dependency signatures:**

   * pandas3.0: ``to_period(freq=None)``.
   * pandas2.3: ``to_period(*args, **kwargs)``.
   * pandas3.1: ``to_period(freq=None)``.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.to_pydatetime()

   Return an object NumPy array of standard Python datetime values and NaT; submicrosecond tails are discarded.

   **Observed dependency signatures:**

   * pandas3.0: ``to_pydatetime()``.
   * pandas2.3: ``to_pydatetime(*args, **kwargs)``.
   * pandas3.1: ``to_pydatetime()``.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.to_series(index=None, name=None)

   Return pandas Series with the original dates as labels by default; date values retain unit, timezone, ns and NaT.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.tolist()

   Return a Python list of pandas Timestamp values and NaT, preserving Timestamp nanoseconds.

   **Executed examples:** :doc:`inherited-pddt-output`.

.. py:method:: rstimes.Pddt.transpose(*args, **kwargs)

   Return this one-dimensional index as its transpose.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.tz

   Read timezone metadata, or None for a naive index.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.union(other, sort=None)

   Return a Pddt union; duplicate multiplicity can be preserved rather than reduced to a unique set.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:method:: rstimes.Pddt.unique(level=None)

   Return first-occurrence unique date labels as Pddt, including NaT.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.unit

   Read the actual stored date unit.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.value_counts(normalize=False, sort=True, ascending=False, bins=None, dropna=True)

   Return a pandas Series of label counts; dropna=False includes the missing label.

   **Executed examples:** :doc:`inherited-pddt-containers`.

.. py:property:: rstimes.Pddt.values

   Expose NumPy datetime values in the index unit. Aware instants become UTC values without timezone metadata.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.view(cls=None)

   Return a Pddt view in the verified no-argument call; this is not a deep-copy guarantee.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:property:: rstimes.Pddt.weekday

   Read Monday-zero local weekday as ordinary numeric pandas Index; the verified sample with NaT has float64 dtype and NaN at the missing row.

   **Executed examples:** :doc:`inherited-pddt-fields`.

.. py:method:: rstimes.Pddt.where(cond, other=None)

   Keep True positions and replace False positions; return Pddt on pandas2.3/3.0 and ordinary DatetimeIndex on pandas3.1 in the tested profiles.

   **Executed examples:** :doc:`inherited-pddt-containers`.

