# Calendar fields, elapsed time and timezones

A calendar month is not a fixed duration. Adding one month to January 31 can
clamp to the last day of February; subtracting a month from that new date
starts at its new day and need not reverse the first operation. A day-based
calendar change and an elapsed-time difference also answer different questions
around timezone transitions. Choose the date operation and difference unit
that match the question.

Delta's plural arguments describe relative amounts. Its singular arguments
select absolute fields. Relative years/months remain calendar quantities;
fixed relative amounts normalize into days and an ns clock remainder. See
[all Delta fields](../guides/delta.md) and the executed
[calendar recipe](../recipes/calendar-across-containers.md).

Timezone work has three distinct roles:

1. **Interpret local fields.** A naive local clock time can have two possible
   instants at a repeated hour or no instant inside a clock gap. The container's
   ambiguous/nonexistent policy decides how that input is handled.
2. **Convert an aware instant.** A timezone conversion changes its local
   display while retaining the instant.
3. **Remove timezone metadata.** Keeping local wall fields and keeping a UTC
   instant are different operations. Choose the documented method explicitly.

Do not assume repeated-time choices can always be inferred from a DST flag.
The guides include actual historical candidates with different offsets and
the same DST status. Array masks, inference and rejection rules also differ
by container and input role.

Use the [Pydt](../guides/pydt-timezones.md),
[Pddt](../guides/pddt-timezones.md),
[Pldt](../guides/pldt-timezones.md), or
[Expr](../guides/expressions-timezones.md) timezone guide for concrete results.
The Pydt guide also explains the accepted external datetime-protocol boundary.
The [known rsTimes issues](../compatibility/known-issues.md) disclose the
remaining business ZoneInfo target case; a successful defect reproduction is
not a claim that the intended contract is met.

Date differences have separate elapsed and calendar choices. Read the
[Pddt calendar/difference guide](../guides/pddt-calendar.md) or
[Pldt difference guide](../guides/pldt-differences.md) before replacing an
explicit date comparison with native subtraction or a statistical operation.
