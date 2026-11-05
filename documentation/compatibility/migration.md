# Moving to beta 0.2.0b3

The public b3 release brings Pldt, exact Delta ns state and distinct
free-threaded wheels into the published package. Earlier local builds could
share a version string while containing different code. Use the actual public
wheel/source identity when comparing a result with these docs.

## Choose explicit date namespaces

Pddt uses `.pddt.replace` for strict date-field replacement. Pldt and Polars
Series/Expr use `.pldt.replace`. Where the host supplies a native `replace`,
that remains a separate whole-value replacement operation. See
[Pddt calendar operations](../guides/pddt-calendar.md),
[Pldt calendar operations](../guides/pldt-calendar.md), and
[native date transformations](../api/inherited-pldt-transformations.md).

Import Pldt to register `.pldt` on Polars Series/Expr. An expression is not a
materialized Pldt: execute it with select or LazyFrame collect. The
[event-feed recipe](../recipes/ingest-and-query.md) shows the complete flow.

## Preserve serialized data before changing beta state formats

Delta's versioned ns state does not automatically migrate the older
microsecond-only state format. Preserve the original serialized data and
explicitly recreate values when moving between these beta formats. The
[Delta state/protocol guide](../guides/delta-protocols.md) executes current
state behavior and rejected states. Do not assume a successful new pickle
round-trip proves an older format is accepted.

## Keep units and validity explicit

Explicit fixed-unit construction and checked output do not silently choose a
coarser unit or drop precision to make values fit. Use a documented intentional
conversion when needed. Pldt null validity and a valid signed-int64 minimum
are distinct; NumPy/pandas NaT conventions do not apply to every native Polars
value. See [units and missingness](../concepts/units-and-missing.md).

## Match the free-threaded ABI and dependencies

Install the actual 3.14t/3.15t rsTimes wheel and compatible native dependencies.
Restart Python after installing an optional integration. Verify GIL state
after imports and actual work, as shown in the
[free-threaded guide](free-threaded.md). No separate rsTimes mode or forced
GIL-off flag is required.

The [public release notes](https://github.com/AresJef/rsTimes/releases/tag/v0.2.0b3)
describe the release scope. The [known rsTimes cases](known-issues.md) remain
disclosed and are not reported as repaired by migration.
