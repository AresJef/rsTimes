Inherited Polars Series entry reference
=======================================

These canonical inherited paths describe native behavior on actual Pldt.
Signatures retain native parameter names/defaults and omit upstream type
annotations; actual return roles are stated explicitly. Date-column results
retain the shown unit, timezone, validity and name unless an operation changes
them. Scalar Python datetime exits are limited to microsecond precision.
The linked pages execute each stated operation in the three Polars profiles.

For all provider parameter details, see the `Polars Series reference
<https://docs.pola.rs/api/python/stable/reference/series/index.html>`_.

.. py:method:: rstimes.Pldt.__getitem__(key)

   Return standard Python datetime/None for a scalar position and Pldt for native slice/integer gather. Boolean masks raise TypeError; use filter. Python datetime output has microsecond precision.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.__iter__()

   Iterate standard Python datetime values and None; the scalar exit discards submicrosecond tails.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.__len__()

   Return total row count, including null rows.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.__new__(*args, **kwargs)

   Allocate a Pldt wrapper when the class is supplied; initialize its date data before use. Normal applications call Pldt(data, ...) instead.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.append(other)

   Append chunks to this Series wrapper in place and return the same Pldt. A prior clone can share immutable buffers while retaining independent wrapper state.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.arr

   Read the native Array namespace; the verified date input rejects arr.len with InvalidOperationError.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:property:: rstimes.Pldt.bin

   Read the native Binary namespace; the verified date input rejects bin.size with SchemaError.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:property:: rstimes.Pldt.cat

   Read the native Categorical namespace object. Date storage remains Datetime; use the rsTimes date namespace for date operations.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:method:: rstimes.Pldt.chunk_lengths()

   Return a Python list of the lengths of native chunks.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.clear(n=0)

   Return empty Pldt by default, retaining the native date dtype and name.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.clone()

   Return a cheap native Pldt clone; buffers may be shared rather than deeply allocated.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.count()

   Return the number of non-null rows.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.dtype

   Read the native Datetime dtype including unit and timezone.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.estimated_size(unit='b')

   Estimate visible buffer memory in the selected byte/kilobyte/etc unit, including validity; this does not measure exclusive process memory.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.ext

   Read the generic native extension namespace, which supports date storage without dtype-specific conversion.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:method:: rstimes.Pldt.ext.storage()

   Return ordinary Series containing the storage values. A nonextension date input retains its exact dtype, ticks, validity and name. Polars marks this API unstable.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:method:: rstimes.Pldt.ext.to(dtype)

   Wrap native date storage with an actual Extension dtype having exactly matching storage type. Return ordinary extension Series; wrong storage raises SchemaError, a nonextension dtype raises AssertionError in these profiles. Polars marks this API unstable.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:method:: rstimes.Pldt.filter(predicate)

   Filter by a Boolean mask and return Pldt for the verified date input.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.first(*, ignore_nulls=False)

   Return the first value as standard Python datetime/None; an empty date column returns None.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.flags

   Read native sortedness flags; flags are metadata, not a sorting operation.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.gather(indices, *, null_on_oob=False)

   Gather integer positions and return ordinary Series while retaining native date dtype, validity and name.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.gather_every(n, offset=0)

   Gather every nth row with optional offset and return ordinary Series, retaining native date metadata.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.get_chunks()

   Return a list of ordinary native Series, one per chunk, retaining each chunk date metadata and validity.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.has_nulls()

   Report whether any null row is present.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.head(n=10)

   Return the first n rows as Pldt; negative n excludes the last abs(n) rows.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.is_empty(*, ignore_nulls=False)

   Report whether the Series has no rows.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.is_sorted(*, descending=False, nulls_last=False)

   Test actual value order using native null/order rules.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.item(index=None)

   Return one scalar by position as standard Python datetime/None; the no-index form requires length1.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.last(*, ignore_nulls=False)

   Return the last value as standard Python datetime/None; an empty date column returns None.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.len()

   Return total row count, including null rows.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.limit(n=10)

   Return the first n rows as Pldt in the verified call.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.list

   Read the native List namespace; the verified date input rejects list.len with InvalidOperationError.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:property:: rstimes.Pldt.map

   Read the native Map namespace; the verified date input rejects map.len with InvalidOperationError.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:method:: rstimes.Pldt.n_chunks()

   Return the number of native chunks.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.name

   Read the Series name string.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.new_from_index(index, length)

   Repeat one positional value for the requested length and return Pldt.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.null_count()

   Return the number of null rows.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.pldt

   Read the registered Series date namespace on Pldt without calling a constructor. Its member aliases are documented under polars.Series.pldt.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:method:: rstimes.Pldt.rechunk(*, in_place=False)

   Return Pldt with contiguous storage in the verified default call.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.set_sorted(*, descending=False)

   Declare already-established order metadata and return Pldt in the verified call. It does not sort data.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.shape

   Read the one-dimensional length tuple.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.shrink_to_fit(*, in_place=False)

   Return a native Pldt storage-size adjustment in the verified default call; dates and metadata stay equal.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.slice(offset, length=None)

   Return Pldt from an offset and optional length; negative offsets count from the end.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:property:: rstimes.Pldt.str

   Read the native String namespace; the verified date input rejects str.len_chars with SchemaError.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:property:: rstimes.Pldt.struct

   Read the native Struct namespace; the verified date input rejects struct.fields with SchemaError.

   **Executed examples:** :doc:`/api/inherited-pldt-accessors`.

.. py:method:: rstimes.Pldt.tail(n=10)

   Return the last n rows as Pldt; negative n excludes the first abs(n) rows.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.to_list()

   Return a Python list of standard datetime/None values, limited to microsecond scalar precision.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.

.. py:method:: rstimes.Pldt.to_physical()

   Return ordinary Int64 Series of native date ticks, with independent null validity and the source name. The integer unit is the source Datetime unit.

   **Executed examples:** :doc:`/api/inherited-pldt-container`.


.. py:property:: rstimes.Pldt.plot

   Read the native plotting namespace; compatible Altair is required. Its methods return Altair Chart objects. Missing Altair raises native ModuleUpgradeRequiredError.

   **Executed examples:** :doc:`inherited-pldt-optional`, :doc:`inherited-pldt-optional-dependencies`.

.. py:method:: rstimes.Pldt.plot.line(**kwargs)

   Create an Altair line Chart from actual Pldt data; the verified default date encoding is temporal. Keyword arguments are forwarded to the native Altair encoding interface.

   **Executed examples:** :doc:`inherited-pldt-optional`.

.. py:method:: rstimes.Pldt.plot.hist(**kwargs)

   Create an Altair histogram Chart specification. The native helper requests quantitative binning even on date data; use explicitly labelled numeric elapsed values for numeric histograms.

   **Executed examples:** :doc:`inherited-pldt-optional`.

.. py:method:: rstimes.Pldt.plot.kde(**kwargs)

   Create an Altair density Chart specification with a native density transform. Use explicit numeric values for numeric density measurements; chart creation itself is not an exact date statistic.

   **Executed examples:** :doc:`inherited-pldt-optional`.

.. py:method:: rstimes.Pldt.to_jax(device=None)

   Call the native optional JAX exit. Pldt Datetime is unsupported and ordinary dates raise TypeError; a valid minimum date tick first triggers the protected NumPy OverflowError. Explicit physical int64 ticks and a separate mask are the documented tensor workaround.

   **Executed examples:** :doc:`inherited-pldt-optional`, :doc:`inherited-pldt-optional-dependencies`.

.. py:method:: rstimes.Pldt.to_torch()

   Call the native optional PyTorch exit. Ordinary Pldt Datetime raises TypeError; a valid minimum date tick first triggers the protected NumPy OverflowError. Use explicit physical int64 ticks and a separate Boolean validity tensor.

   **Executed examples:** :doc:`inherited-pldt-optional`, :doc:`inherited-pldt-optional-dependencies`.

.. py:method:: rstimes.Pldt.__abs__()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__and__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__floordiv__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__invert__()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__matmul__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__mod__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__mul__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__neg__()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__or__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__pos__()

   Return Pldt with unchanged dates, unit, timezone, name and validity in the verified unary-plus call.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__pow__(exponent)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__rand__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises SchemaError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__rfloordiv__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__rmod__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__rmul__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__ror__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises SchemaError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__rpow__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__rtruediv__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__rxor__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises SchemaError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__truediv__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises TypeError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__xor__(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.abs()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.all(*, ignore_nulls=True)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises SchemaError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.any(*, ignore_nulls=True)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises SchemaError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.arccos()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.arccosh()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.arcsin()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.arcsinh()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.arctan()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.arctanh()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_and()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_count_ones()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_count_zeros()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_leading_ones()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_leading_zeros()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_or()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_trailing_ones()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_trailing_zeros()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.bitwise_xor()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cbrt()

   Return ordinary Float64 cube roots of physical date ticks; unit and timezone metadata are not attached to the numerical result.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.ceil()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cos()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cosh()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cot()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cum_max(*, reverse=False)

   Return ordinary Datetime Series of cumulative maxima; state crosses null rows while their outputs remain null.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cum_min(*, reverse=False)

   Return ordinary Datetime Series of cumulative minima; state crosses null rows while their outputs remain null.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cum_prod(*, reverse=False)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.cum_sum(*, reverse=False)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.degrees()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.dot(other)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.entropy(base=2.718281828459045, *, normalize=True)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.erf()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.erfc()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.ewm_mean(*, com=None, span=None, half_life=None, alpha=None, adjust=True, min_samples=1, ignore_nulls=False)

   Return ordinary Float64 exponentially weighted mean of physical date ticks. Alpha, adjustment and gap weighting have numerical roles, not calendar-frequency roles.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.ewm_mean_by(by, *, half_life)

   Reject a Datetime value Series with native InvalidOperationError even when by is a valid Datetime time index; native numerical values are required.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.ewm_std(*, com=None, span=None, half_life=None, alpha=None, adjust=True, bias=False, min_samples=1, ignore_nulls=False)

   Return ordinary Float64 exponentially weighted tick deviation, not a Datetime or a Duration.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.ewm_sum(*, com=None, span=None, half_life=None, alpha=None, min_samples=1, ignore_nulls=False)

   Return ordinary Float64 exponentially weighted sum of physical date ticks; the verified alpha1/2 values produce 1 then8.5.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.ewm_sum_by(by, *, half_life)

   Reject a Datetime value Series with native InvalidOperationError even when by is a valid Datetime time index; native numerical values are required.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.ewm_var(*, com=None, span=None, half_life=None, alpha=None, adjust=True, bias=False, min_samples=1, ignore_nulls=False)

   Return ordinary Float64 exponentially weighted tick variance; default unbiased output begins null in the verified two-observation case.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.exp()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.floor()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.is_finite()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.is_infinite()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.is_nan()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.is_not_nan()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.kurtosis(*, fisher=True, bias=True)

   Return native floating kurtosis of physical date tick numbers; the verified two-value excess kurtosis is -2.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.log(base=2.718281828459045)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.log10()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.log1p()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.lower_bound()

   Return one-element ordinary Int64 Series containing the physical storage lower bound; the result is not a Datetime.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.nan_max()

   Return the maximum as standard Python datetime, skipping source null; scalar output is limited to microseconds.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.nan_min()

   Return the minimum as standard Python datetime, skipping source null; scalar output is limited to microseconds.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.not_()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.pct_change(n=1)

   Return ordinary Float64 ratios of successive physical date tick changes; first/missing rows retain the verified native null behavior.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.peak_max()

   Return ordinary nullable Boolean Series of native local-maximum flags; native endpoint and missing-data behavior are executed.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.peak_min()

   Return ordinary nullable Boolean Series of native local-minimum flags; endpoint rules differ from assuming a missing neighbor. Literal valley and missing-data cases are executed.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.pow(exponent)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.product()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.radians()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.reinterpret(*, signed=None, dtype=None)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.round(decimals=0, mode='half_to_even')

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.round_sig_figs(digits)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.shrink_dtype()

   Return ordinary Series with unchanged Datetime dtype/data in the verified call; this is native dtype-size selection, not rsTimes as_unit.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.sign()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.sin()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.sinh()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.skew(*, bias=True)

   Return native floating skewness of physical date tick numbers, rather than a date or timedelta result.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.sqrt()

   Return ordinary Float64 Series computed from physical date ticks. This is not a calendar transformation and the numerical result depends on stored tick units.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.std(ddof=1)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.sum()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.tan()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.tanh()

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.truncate(decimals=0)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.upper_bound()

   Return one-element ordinary Int64 Series containing the physical storage upper bound; the result is not a Datetime.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.var(ddof=1)

   Native numerical/Boolean operation on Datetime is unsupported in the executed valid-parameter call and raises InvalidOperationError. This is distinct from rsTimes date transformations.

   **Executed examples:** :doc:`inherited-pldt-numeric`.

.. py:method:: rstimes.Pldt.__bool__()

   Reject a scalar truth value with native TypeError, including for an empty Series.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__contains__(item)

   Return Python bool for scalar date-label membership; None is present when a source null exists. This differs from the nullable is_in row mask.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__eq__(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__format__(format_spec, /)

   Support the empty native display format; a numeric formatting specification raises TypeError.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__ge__(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__gt__(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:attribute:: rstimes.Pldt.__hash__

   Disabled Python container hash protocol: hash(value) raises TypeError. The separate hash method computes row hashes.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__le__(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__lt__(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__ne__(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__repr__()

   Return native-style display identifying Pldt, its name, date dtype, values and nulls.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__rsub__(other)

   Inherited reflected subtraction returns a native Duration Series. The executed whole-second example checks the unit and nulls; use rsTimes forward subtraction or diff for explicit date-difference semantics.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.__str__()

   Return native Pldt display text in the verified call.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.arg_true()

   Require Boolean input and reject Datetime with native SchemaError.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.arg_unique()

   Return ordinary Series of native index dtype containing first-distinct positions, including first null.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.eq(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.eq_missing(other)

   Return missing-aware Boolean equality; two nulls match and one null versus one date does not.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.equals(other, *, check_dtypes=False, check_names=False, null_equal=True)

   Return Python bool for whole-Series equality, with optional name/dtype checks and explicit null-equality policy.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.ge(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.gt(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.hash(seed=0)

   Return ordinary UInt64 Series of row hashes, including a non-null hash for a null. Equal values hash equally in one call; uniqueness/persistence across dependency versions is not promised.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_between(lower_bound, upper_bound, closed='both')

   Return nullable native Boolean interval mask with explicit closed-endpoint choice and date operands.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_close(other, *, abs_tol=0.0, rel_tol=1e-09, nans_equal=False)

   Reject Datetime with native InvalidOperationError; this numerical tolerance entry is not rsTimes date difference.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_duplicated()

   Return native Boolean flags for every occurrence of a duplicated value.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_first_distinct()

   Return native Boolean flags at each value first occurrence, including null.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_in(other, *, nulls_equal=False)

   Return native Boolean membership Series for a collection. An explicit List-Series operand avoids flat-Series ambiguity; nulls_equal controls null matching.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_last_distinct()

   Return native Boolean flags at each value last occurrence, including null.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_not_null()

   Return non-null Boolean flags marking valid source rows.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_null()

   Return non-null Boolean flags marking source null rows.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.is_unique()

   Return native Boolean flags for values occurring once, including a single null.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.le(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.lt(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.ne(other)

   Compare date values elementwise and return ordinary nullable Boolean Series. A null input produces null; missing-aware equality is separate.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.ne_missing(other)

   Return missing-aware Boolean inequality; two nulls do not differ and one null versus one date does.

   **Executed examples:** :doc:`inherited-pldt-comparisons`.

.. py:method:: rstimes.Pldt.fill_null(value=None, strategy=None, limit=None)

   Inherited fill_null returns an ordinary Series. The executed date example uses an explicit scalar expression with the complete source dtype and checks exact ns ticks, UTC metadata and nulls.

   **Executed examples:** :doc:`/api/inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.shift(n=1, *, fill_value=None)

   Inherited shift returns an ordinary Series. The executed date example uses an explicit scalar expression with the complete source dtype and checks exact ns ticks, UTC metadata and nulls.

   **Executed examples:** :doc:`/api/inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.to_frame(name=None)

   Return native Polars DataFrame retaining the date column unit, timezone, exact ticks and validity. An explicit name changes the returned column name, not the source.

   **Executed examples:** :doc:`inherited-pldt-representations`.

.. py:method:: rstimes.Pldt.to_dummies(*, separator='_', drop_first=False, drop_nulls=False)

   Return native DataFrame of UInt8 categorical indicators; default date labels retain their displayed ns and null has its own category. drop_nulls excludes that null category.

   **Executed examples:** :doc:`inherited-pldt-representations`.

.. py:method:: rstimes.Pldt.to_init_repr(n=1000)

   Return native Series initialization text. The executed microsecond example reconstructs a native Series; explicit integer ticks, validity and the complete dtype provide exact ns reconstruction for rsTimes date data.

   **Executed examples:** :doc:`inherited-pldt-representations`.

.. py:method:: rstimes.Pldt.__setitem__(key, value)

   Mutate a selected row. The executed example clears rows with None and checks the None return from the direct protocol call.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.alias(name)

   Return a named Pldt with unchanged date dtype and data; the original name is unchanged.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.backward_fill(limit=None)

   Return native Series, carrying later valid dates into null rows without changing the date dtype.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.cast(dtype, *, strict=True, wrap_numerical=False)

   Perform an explicit native dtype conversion. Matching Datetime returns Pldt; numeric and Date results are native Series. Unit conversion can discard fractions.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.clip(lower_bound=None, upper_bound=None)

   Return native Series with date bounds applied; explicitly typed date bounds retain ns metadata and missing rows.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.cum_count(*, reverse=False)

   Return native UInt32 cumulative counts of non-null rows, including a count at each null position; reverse direction is executed.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.drop_nans()

   Return native Series; Datetime has nulls rather than floating NaN values, so this date example is unchanged.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.drop_nulls()

   Return native Series with missing date rows removed.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.explode(*, empty_as_null=True, keep_nulls=True)

   Return native flat Series for the executed already-flat date input.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.extend(other)

   Extend and return the same Pldt wrapper in the executed matching-dtype call; this mutates the selected receiver.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.extend_constant(value, n)

   Return native Series with repeated scalar date values appended; leave the original Pldt unchanged.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.fill_nan(value)

   Require a suitable numerical dtype; a Datetime receiver raises InvalidOperationError. Use date-null filling for missing dates.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.forward_fill(limit=None)

   Return native Series, carrying previous valid dates into null rows without changing the date dtype.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.implode()

   Return a native one-row List(Datetime) Series containing the date rows and nulls.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.interpolate(method='linear')

   Return a native date Series with linear or nearest missing-value interpolation. The executed intervals check exact ns results.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.interpolate_by(by)

   Require supported numerical value data; the date receiver raises InvalidOperationError in the executed example.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.rename(name)

   Return a renamed Pldt with unchanged date dtype and data; the original name is unchanged.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.repeat_by(by)

   Return a native List(Datetime) Series with repeated date values and inner missing validity.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.replace(old, new=OMITTED)

   Return native Series after whole-date value replacement; this is separate from the rsTimes date-field replacement method.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.replace_strict(old, new=OMITTED, *, default=OMITTED, return_dtype=None)

   Return native Series after complete whole-value mapping, or raise InvalidOperationError for unmapped data unless a default is supplied. None is a missing default.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.reshape(dimensions)

   Return native nested Array(Datetime) Series for a two-dimensional shape, preserving date ticks and nulls.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.reverse()

   Return native Series with row order reversed, preserving exact ticks and nulls.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.sample(n=None, *, fraction=None, with_replacement=False, shuffle=None, seed=None)

   Return sampled native Series with explicit size, replacement and seed. Exact multisets or membership are checked without promising cross-version random order.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.scatter(indices, values)

   Mutate and return the same Pldt wrapper. Use a matching date Series operand for explicit exact date values.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.set(filter, value)

   Return native Series with masked scalar date replacements; leave the original Pldt unchanged.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.shuffle(seed=None)

   Return a shuffled native Series. The executed fixed-seed call checks repeatability, metadata and the exact multiset within each tested runtime.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.sort(*, descending=False, nulls_last=False, multithreaded=True, in_place=False)

   Return Pldt with explicit ascending/descending and null-placement choices.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.zip_with(mask, other)

   Return Pldt for matching date operands. The receiver is selected at True mask rows and the other column at False or null rows in the executed example.

   **Executed examples:** :doc:`inherited-pldt-transformations`.

.. py:method:: rstimes.Pldt.__arrow_c_stream__(requested_schema=None)

   Actual PyArrow TimestampArray and PyCapsule-stream consumption, ns/UTC, valid i64 MIN versus null, empty data and unchanged source.

   **Executed examples:** :doc:`/api/inherited-pldt-arrow`.

.. py:method:: rstimes.Pldt.approx_n_unique()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.approx_quantile(quantile, *, method='auto', error=0.001, error_tightness='empirical')

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.arg_max()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.arg_min()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.arg_sort(*, descending=False, nulls_last=False)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.bin_intervals(intervals, *, labels, include_intervals=False, right_closed=False)

   Actual date breakpoints versus sorted ranks and physical-us compatibility cuts; category dtype/nulls; numeric-only rejections.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.bin_quantiles(quantiles, *, labels, include_intervals=False, right_closed=False)

   Actual date breakpoints versus sorted ranks and physical-us compatibility cuts; category dtype/nulls; numeric-only rejections.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.bin_ranks(ranks, *, labels, include_intervals=False)

   Actual date breakpoints versus sorted ranks and physical-us compatibility cuts; category dtype/nulls; numeric-only rejections.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.bottom_k(k=5)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.bottom_k_by(by, k=5, *, reverse=False)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.cumulative_eval(expr, *, min_samples=1, parallel=False)

   Numerical-kernel dtype rejection on actual date receiver; cumulative Expr actually evaluated to native date Series with exact ticks.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.cut(breaks, *, labels=None, left_closed=False, include_breaks=False)

   Actual date breakpoints versus sorted ranks and physical-us compatibility cuts; category dtype/nulls; numeric-only rejections.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.describe(percentiles=(0.25, 0.5, 0.75), interpolation='nearest')

   Exact nested date run storage and nulls; Duration(ns) row differences, shortened shape; Python business callback Int64; readable String summary table.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.diff(n=1, null_behavior='ignore')

   Exact nested date run storage and nulls; Duration(ns) row differences, shortened shape; Python business callback Int64; readable String summary table.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.hist(bins=None, *, bin_count=None, include_category=True, include_breakpoint=True)

   Actual date breakpoints versus sorted ranks and physical-us compatibility cuts; category dtype/nulls; numeric-only rejections.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.index_of(element)

   Actual scalar datetime lookup on explicit us dtype, absent result None, scalar index versus vector native index Series.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.map_elements(function, return_dtype=None, *, skip_nulls=True, _disable_inefficient_map_warning=False)

   Exact nested date run storage and nulls; Duration(ns) row differences, shortened shape; Python business callback Int64; readable String summary table.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.max()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.max_by(by)

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.mean()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.median()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.min()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.min_by(by)

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.mode(*, maintain_order=False)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.n_unique()

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.qcut(quantiles, *, labels=None, left_closed=False, allow_duplicates=False, include_breaks=False)

   Actual date breakpoints versus sorted ranks and physical-us compatibility cuts; category dtype/nulls; numeric-only rejections.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.quantile(quantile, interpolation='nearest')

   Python datetime scalar UTC/microsecond return versus int counts/positions; nulls and empty reductions; explicit by-column selection.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.rank(method='average', *, descending=False, seed=None)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.rle()

   Exact nested date run storage and nulls; Duration(ns) row differences, shortened shape; Python business callback Int64; readable String summary table.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.rle_id()

   Exact nested date run storage and nulls; Duration(ns) row differences, shortened shape; Python business callback Int64; readable String summary table.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.rolling_kurtosis(window_size, *, fisher=True, bias=True, min_samples=None, center=False)

   Numerical-kernel dtype rejection on actual date receiver; cumulative Expr actually evaluated to native date Series with exact ticks.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_map(function, window_size, weights=None, *, min_samples=None, center=False)

   Numerical-kernel dtype rejection on actual date receiver; cumulative Expr actually evaluated to native date Series with exact ticks.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_max(window_size, weights=None, *, min_samples=None, center=False)

   Two-row window, min_samples, explicit epoch-second mathematical answers; date dtype versus Float64 rank; null/empty source.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_max_by(by, window_size, *, min_samples=1, closed='right')

   Separate sorted UTC date by-axis and 3-second right-closed windows; date metadata, values and native rank output.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_mean(window_size, weights=None, *, min_samples=None, center=False)

   Two-row window, min_samples, explicit epoch-second mathematical answers; date dtype versus Float64 rank; null/empty source.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_mean_by(by, window_size, *, min_samples=1, closed='right')

   Separate sorted UTC date by-axis and 3-second right-closed windows; date metadata, values and native rank output.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_median(window_size, weights=None, *, min_samples=None, center=False)

   Two-row window, min_samples, explicit epoch-second mathematical answers; date dtype versus Float64 rank; null/empty source.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_median_by(by, window_size, *, min_samples=1, closed='right')

   Separate sorted UTC date by-axis and 3-second right-closed windows; date metadata, values and native rank output.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_min(window_size, weights=None, *, min_samples=None, center=False)

   Two-row window, min_samples, explicit epoch-second mathematical answers; date dtype versus Float64 rank; null/empty source.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_min_by(by, window_size, *, min_samples=1, closed='right')

   Separate sorted UTC date by-axis and 3-second right-closed windows; date metadata, values and native rank output.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_quantile(quantile, interpolation='nearest', window_size=2, weights=None, *, min_samples=None, center=False)

   Two-row window, min_samples, explicit epoch-second mathematical answers; date dtype versus Float64 rank; null/empty source.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_quantile_by(by, window_size, *, quantile, interpolation='nearest', min_samples=1, closed='right')

   Separate sorted UTC date by-axis and 3-second right-closed windows; date metadata, values and native rank output.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_rank(window_size, method='average', *, seed=None, min_samples=None, center=False)

   Two-row window, min_samples, explicit epoch-second mathematical answers; date dtype versus Float64 rank; null/empty source.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_rank_by(by, window_size, method='average', *, seed=None, min_samples=1, closed='right')

   Separate sorted UTC date by-axis and 3-second right-closed windows; date metadata, values and native rank output.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_skew(window_size, *, bias=True, min_samples=None, center=False)

   Numerical-kernel dtype rejection on actual date receiver; cumulative Expr actually evaluated to native date Series with exact ticks.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_std(window_size, weights=None, *, min_samples=None, center=False, ddof=1)

   Sample ddof1 Float64 standard deviation in physical ns and variance in ns squared; one-row null and explicit mathematical tolerance.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_std_by(by, window_size, *, min_samples=1, closed='right', ddof=1)

   Sample ddof1 Float64 standard deviation in physical ns and variance in ns squared; one-row null and explicit mathematical tolerance.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_sum(window_size, weights=None, *, min_samples=None, center=False)

   Numerical-kernel dtype rejection on actual date receiver; cumulative Expr actually evaluated to native date Series with exact ticks.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_sum_by(by, window_size, *, min_samples=0, closed='right')

   Numerical-kernel dtype rejection on actual date receiver; cumulative Expr actually evaluated to native date Series with exact ticks.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_var(window_size, weights=None, *, min_samples=None, center=False, ddof=1)

   Sample ddof1 Float64 standard deviation in physical ns and variance in ns squared; one-row null and explicit mathematical tolerance.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.rolling_var_by(by, window_size, *, min_samples=1, closed='right', ddof=1)

   Sample ddof1 Float64 standard deviation in physical ns and variance in ns squared; one-row null and explicit mathematical tolerance.

   **Executed examples:** :doc:`/api/inherited-pldt-windows`.

.. py:method:: rstimes.Pldt.search_sorted(element, side='any', *, descending=False)

   Actual scalar datetime lookup on explicit us dtype, absent result None, scalar index versus vector native index Series.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.sql(query, *, table_name='self')

   Actually executed native SQL DataFrame with exact ns/UTC column, selected null rows, explicit table name and unchanged source.

   **Executed examples:** :doc:`/api/inherited-pldt-sql`.

.. py:method:: rstimes.Pldt.to_arrow(*, compat_level=None)

   Actual PyArrow TimestampArray and PyCapsule-stream consumption, ns/UTC, valid i64 MIN versus null, empty data and unchanged source.

   **Executed examples:** :doc:`/api/inherited-pldt-arrow`.

.. py:method:: rstimes.Pldt.top_k(k=5)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.top_k_by(by, k=5, *, reverse=False)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.unique(*, maintain_order=False)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.unique_counts()

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.

.. py:method:: rstimes.Pldt.value_counts(*, sort=False, parallel=False, name=None, normalize=False)

   Native date Series preserves ns/UTC; native numeric rank/index/count and DataFrame return roles; null, duplicate, order and multiset checks.

   **Executed examples:** :doc:`/api/inherited-pldt-analysis`.
