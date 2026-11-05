Inherited Polars temporal entry reference
=========================================

.. py:property:: rstimes.Pldt.dt

   The original native Polars temporal accessor on Pldt. Read it without arguments.

   These entries use native Polars defaults and results. All visible date methods
   and the indexing protocol are executed on real Pldt in
   :doc:`inherited-polars-datetime`.

   Runtime signatures are checked in the three dependency profiles. The native
   provider is Polars; rsTimes date-field and localization rules use ``.pldt``.

.. py:method:: rstimes.Pldt.dt.__getitem__(item)

   Select a standard Python datetime/None for a scalar index, or an exact native Series for a slice/integer gather.

   **Parameters:** native integer, slice or integer-gather selector. Scalar
   datetime output truncates to microseconds. Series output keeps its original
   unit, timezone and validity. Unsupported selectors raise native TypeError.

   The upstream int-only annotation does not describe every observed runtime
   selection branch; the canonical signature above leaves that annotation open.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.add_business_days(n: 'int | IntoExpr', *, week_mask: 'Iterable[bool]' = (True, True, True, True, True, False, False), holidays: 'Iterable[dt.date] | Expr | Series' = (), roll: 'Roll' = 'raise') -> 'Series'

   Move by business-day count, with a week mask, holiday dates and an explicit roll rule.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.base_utc_offset() -> 'Series'

   Return the native timezone base offset as Duration(ms).

   **Verified return role:** ordinary Polars Series with dtype ``Duration(time_unit='ms')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.cast_time_unit(time_unit: 'TimeUnit') -> 'Series'

   Cast native date storage to ms/us/ns; coarser output can discard precision.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='us', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.century() -> 'Series'

   Return the calendar century number.

   **Verified return role:** ordinary Polars Series with dtype ``Int32``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.combine(time: 'dt.time | Series', time_unit: 'TimeUnit' = 'us') -> 'Series'

   Combine local date fields with a clock; an aware source retains its native timezone in the verified API.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.convert_time_zone(time_zone: 'str') -> 'Series'

   Keep each instant and change native timezone metadata.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='UTC')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.date() -> 'Series'

   Extract a native Date column from local calendar dates.

   **Verified return role:** ordinary Polars Series with dtype ``Date``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.day() -> 'Series'

   Extract day of month.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.days_in_month() -> 'Series'

   Count days in the local calendar month.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.dst_offset() -> 'Series'

   Return the native DST adjustment as Duration(ms).

   **Verified return role:** ordinary Polars Series with dtype ``Duration(time_unit='ms')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.epoch(time_unit: 'EpochTimeUnit' = 'us') -> 'Series'

   Export integer epoch coordinates in the selected native epoch unit; default us.

   **Verified return role:** ordinary Polars Series with dtype ``Int64``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.hour() -> 'Series'

   Extract local hour.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.is_business_day(*, week_mask: 'Iterable[bool]' = (True, True, True, True, True, False, False), holidays: 'Iterable[dt.date] | Expr | Series' = ()) -> 'Series'

   Query the native week mask and holiday calendar.

   **Verified return role:** ordinary Polars Series with dtype ``Boolean``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.is_leap_year() -> 'Series'

   Query the Gregorian leap-year flag.

   **Verified return role:** ordinary Polars Series with dtype ``Boolean``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.iso_year() -> 'Series'

   Extract ISO week year.

   **Verified return role:** ordinary Polars Series with dtype ``Int32``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.max() -> 'dt.date | dt.datetime | dt.timedelta | None'

   Return the maximum as standard Python datetime, or None for no valid dates.

   **Verified return role:** standard Python datetime or None.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.microsecond() -> 'Series'

   Extract the complete fractional microseconds since the second.

   **Verified return role:** ordinary Polars Series with dtype ``Int32``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.millennium() -> 'Series'

   Return the calendar millennium number.

   **Verified return role:** ordinary Polars Series with dtype ``Int32``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.millisecond() -> 'Series'

   Extract fractional milliseconds since the second.

   **Verified return role:** ordinary Polars Series with dtype ``Int32``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.min() -> 'dt.date | dt.datetime | dt.timedelta | None'

   Return the minimum as standard Python datetime, or None for no valid dates.

   **Verified return role:** standard Python datetime or None.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.minute() -> 'Series'

   Extract local minute.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.month() -> 'Series'

   Extract calendar month 1–12.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.month_end() -> 'Series'

   Move to the month end while retaining the native clock.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.month_start() -> 'Series'

   Move to the month start while retaining the native clock.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.nanosecond() -> 'Series'

   Extract the full fractional nanoseconds since the second, rather than the rsTimes 0–999 tail.

   **Verified return role:** ordinary Polars Series with dtype ``Int32``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.offset_by(by: 'str | IntoExprColumn') -> 'Series'

   Apply native relative offset syntax such as 1mo, with native scalar/column argument rules.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.ordinal_day() -> 'Series'

   Extract day of year.

   **Verified return role:** ordinary Polars Series with dtype ``Int16``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.quarter() -> 'Series'

   Extract calendar quarter.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.replace(*, year: 'int | Series | None' = None, month: 'int | Series | None' = None, day: 'int | Series | None' = None, hour: 'int | Series | None' = None, minute: 'int | Series | None' = None, second: 'int | Series | None' = None, microsecond: 'int | Series | None' = None, ambiguous: 'Ambiguous | Series' = 'raise') -> 'Series'

   Replace native calendar and clock fields; this operation does not select the date storage unit.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.replace_time_zone(time_zone: 'str | None', *, ambiguous: 'Ambiguous | Series' = 'raise', non_existent: 'NonExistent' = 'raise') -> 'Series'

   Reinterpret local clock coordinates in a target zone. Native keywords include ambiguous and non_existent.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='UTC')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.round(every: 'str | dt.timedelta | IntoExprColumn') -> 'Series'

   Round on the native date bucket grid.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.second(*, fractional: 'bool' = False) -> 'Series'

   Extract integer seconds, or Float64 seconds with fractional=True.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.strftime(format: 'str') -> 'Series'

   Format with native Polars date directives and fraction rules.

   **Verified return role:** ordinary Polars Series with dtype ``String``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.time() -> 'Series'

   Extract native Time retaining time-of-day nanoseconds.

   **Verified return role:** ordinary Polars Series with dtype ``Time``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.timestamp(time_unit: 'TimeUnit' = 'us') -> 'Series'

   Export an integer timestamp in ms/us/ns; default us.

   **Verified return role:** ordinary Polars Series with dtype ``Int64``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.to_string(format: 'str | None' = None) -> 'Series'

   Render native date text using an explicit format or the provider default.

   **Verified return role:** ordinary Polars Series with dtype ``String``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.total_days(*, fractional: 'bool' = False) -> 'Series'

   Extract this total from a Duration column; a Pldt Datetime receiver raises native SchemaError.

   **Pldt receiver:** native SchemaError. **Duration receiver:** native Int64
   for the integer total; the selected fractional output follows the native
   ``fractional`` parameter. No Duration storage is claimed for Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.total_hours(*, fractional: 'bool' = False) -> 'Series'

   Extract this total from a Duration column; a Pldt Datetime receiver raises native SchemaError.

   **Pldt receiver:** native SchemaError. **Duration receiver:** native Int64
   for the integer total; the selected fractional output follows the native
   ``fractional`` parameter. No Duration storage is claimed for Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.total_microseconds(*, fractional: 'bool' = False) -> 'Series'

   Extract this total from a Duration column; a Pldt Datetime receiver raises native SchemaError.

   **Pldt receiver:** native SchemaError. **Duration receiver:** native Int64
   for the integer total; the selected fractional output follows the native
   ``fractional`` parameter. No Duration storage is claimed for Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.total_milliseconds(*, fractional: 'bool' = False) -> 'Series'

   Extract this total from a Duration column; a Pldt Datetime receiver raises native SchemaError.

   **Pldt receiver:** native SchemaError. **Duration receiver:** native Int64
   for the integer total; the selected fractional output follows the native
   ``fractional`` parameter. No Duration storage is claimed for Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.total_minutes(*, fractional: 'bool' = False) -> 'Series'

   Extract this total from a Duration column; a Pldt Datetime receiver raises native SchemaError.

   **Pldt receiver:** native SchemaError. **Duration receiver:** native Int64
   for the integer total; the selected fractional output follows the native
   ``fractional`` parameter. No Duration storage is claimed for Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.total_nanoseconds(*, fractional: 'bool' = False) -> 'Series'

   Extract this total from a Duration column; a Pldt Datetime receiver raises native SchemaError.

   **Pldt receiver:** native SchemaError. **Duration receiver:** native Int64
   for the integer total; the selected fractional output follows the native
   ``fractional`` parameter. No Duration storage is claimed for Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.total_seconds(*, fractional: 'bool' = False) -> 'Series'

   Extract this total from a Duration column; a Pldt Datetime receiver raises native SchemaError.

   **Pldt receiver:** native SchemaError. **Duration receiver:** native Int64
   for the integer total; the selected fractional output follows the native
   ``fractional`` parameter. No Duration storage is claimed for Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.truncate(every: 'str | dt.timedelta | IntoExprColumn') -> 'Series'

   Select the beginning of the native date bucket.

   **Verified return role:** ordinary Polars Series with dtype ``Datetime(time_unit='ns', time_zone='Asia/Shanghai')``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.week() -> 'Series'

   Extract ISO week number.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.weekday() -> 'Series'

   Extract ISO weekday, Monday=1.

   **Verified return role:** ordinary Polars Series with dtype ``Int8``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

.. py:method:: rstimes.Pldt.dt.year() -> 'Series'

   Extract calendar year.

   **Verified return role:** ordinary Polars Series with dtype ``Int32``.

   Native source nulls remain null. Date outputs retain the native metadata
   described by this operation; these results are not wrapped as Pldt.

   **Executed examples:** :doc:`inherited-polars-datetime`.

