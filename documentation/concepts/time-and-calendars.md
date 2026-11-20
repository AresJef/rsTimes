# Calendar fields, elapsed time and timezones

Choose a calendar operation to describe a local date change such as
the next month. January 31 can fit to February 29. Subtracting a
month from February 29 starts with day 29. The
[calendar recipe](../recipes/calendar-across-containers.md) shows
the result for the three date classes.

Choose elapsed-time arithmetic to move by a fixed duration. Around
a daylight-saving transition, 24 elapsed hours can land on a
different local clock than one calendar day. Use the
[calendar and elapsed example](../guides/pldt-arithmetic.md)
for the actual date values. Subtracting two dates returns a
duration at the container's supported precision. The date
namespace diff can count chosen calendar or fixed-unit boundaries.

## Choose a timezone operation

| Task | Operation |
| --- | --- |
| Interpret naive local fields | Attach a zone with an explicit policy for repeated or missing clocks when needed. |
| Display an aware instant in another zone | Convert to the target zone while keeping the instant. |
| Drop a zone | Choose local clock fields or UTC fields before removing time zone information. |

In a gap, the nearest boundary and an explicit timedelta shift
have different results. At a repeated clock, the available
candidates depend on the actual transition rules. Set a policy
that suits the input's container and order.

Use the [Pydt](../guides/pydt-timezones.md),
[Pddt](../guides/pddt-timezones.md),
[Pldt](../guides/pldt-timezones.md) and
[Expr](../guides/expressions-timezones.md) timezone guides
for their argument forms and results.
A custom aware source can supply a genuine instant. A Polars
column must use a target timezone representable in its dtype.
