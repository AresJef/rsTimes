# Troubleshooting rsTimes date workflows

Start from the input role, destination and actual result type. An exception
can be the intended rejection of a lossy conversion or unsupported input.
The linked guides show the calls and their observed results.

| Symptom | Check | Next step |
|---|---|---|
| An optional integration is unavailable | Was its package installed before this interpreter started? | Install the matching extra and restart Python; see [optional dependencies](compatibility/optional-dependencies.md) |
| `.pldt` is missing on a Polars Series/Expr | Has the rsTimes Pldt namespace been registered in this process? | Import Pldt from rstimes; see [expressions](guides/expressions.md) |
| A type checker cannot find the registered Expr accessor | Registration occurs when the integration loads | [Describe the accessor for static analysis](compatibility/type-checking.md) |
| An Expr exists but no rows were computed | Expression construction is deferred work | Execute select or LazyFrame collect; see [execution and errors](guides/expressions-execution.md) |
| An Expr still uses an earlier configuration | Its configuration can be a construction-time snapshot | Rebuild the expression after editing configuration; see [Expr inputs](guides/expressions-inputs.md) |
| A recognizable date field was fitted to its valid range | Was generic parsing permissive? | Use {ref}`strict parsing <parse-reject-impossible-day>` to reject invalid explicit fields |
| A date conversion rejects a finer fraction | The requested destination may not represent it exactly | Keep the finer unit or deliberately choose as_unit; see [checked output](guides/pldt-output.md) |
| A valid minimum tick cannot be exported to NumPy | NumPy reserves that tick for NaT | Use separate validity/Arrow, or explicitly accept the collision; see [exact interchange](recipes/precise-exchange.md) |
| A timezone input is ambiguous or nonexistent | Local fields do not uniquely identify an instant | Choose the documented scalar/mask/inference/rejection policy in the [timezone concepts](concepts/time-and-calendars.md) |
| Adding a month and subtracting it does not recover the original day | Month-end clamping changed the starting day for the second operation | See [the calendar recipe](recipes/calendar-across-containers.md) |
| A result is a native Series, Index or scalar | Inherited and field operations have their own return rules | See [return types and protocols](concepts/returns-and-protocols.md) |
| A native numeric operation rejects Datetime | The inherited entry requires a different dtype | Choose an explicit date difference or numerical representation; see [date analysis](api/inherited-pldt-analysis.md) |
| Date-field replace is unavailable or means something else | Native value replacement is a separate operation | Use Pddt `.pddt.replace` or Polars `.pldt.replace`; see the [API reference](api/index.md) |
| A copy hook returns another type | Real application hooks can choose their result | Check the specific [copy/state guarantees](guides/pldt-state.md) and deferred cases below |

## Check the documented rsTimes protocol cases

For a custom target zone, choose a representable timezone or convert the
genuinely aware source. Named copies use available application reduction
hooks. External datetime conversions of a Pydt at a repeated clock may
require a standard datetime carrier. See
[timezone, copy, and error protocols](compatibility/known-issues.md)
for actual 1.0.0 behavior and the old beta changes.

## Report an rsTimes problem with enough context

Include the exact rsTimes version, Python/ABI, relevant optional package
versions, a minimal input, the method and arguments, and the actual versus
expected result. For date results include dtype/unit, timezone, null/NaT
positions and the return type. For expressions include an executed select or
collect and the relevant input schema. Preserve the original exception and
traceback when relevant.

Check whether the actual operation belongs to rsTimes or an inherited
provider, and whether rsTimes adds a wrapper or an extra promise. Report
rsTimes implementation, conversion, validation or contract failures through
[the repository issue tracker](https://github.com/AresJef/rsTimes/issues).
