# Documentation verification evidence

These receipts describe the rsTimes 1.0.0 documentation and its
actual build and execution context.

- [Full entry, scenario, page, example, environment and evidence table in CSV](https://aresjef.github.io/rsTimes/1.0.0/verification/coverage.csv)
- [The same coverage table in JSON](https://aresjef.github.io/rsTimes/1.0.0/verification/coverage.json)
- [Documented product, documentation commit, wheel identities and deployment run](https://aresjef.github.io/rsTimes/1.0.0/_meta/build.json)
- [Checksums of deployed files](https://aresjef.github.io/rsTimes/_meta/files.json)

The canonical public entries include rsTimes-owned APIs,
registered namespaces and supported documentation for inherited
operations on rsTimes objects. Module re-exports use the
canonical entry's result. Separate profile records show the
actual installed wheel, interpreter, dependencies and example
source. Expr evidence comes from executed queries.
Wrong identities, missing cases and stale page results prevent
a complete gate from passing.

Each evidence row records the checksum of the linked public
report in `report_sha256`. The public copy uses a generic package
path and omits the full transcript. The original Actions report
has the checksum recorded in `ci_report_sha256`.

The public records cover documentation and example execution.
Product distribution qualifications and performance comparisons
are recorded with the [1.0.0 release](https://github.com/AresJef/rsTimes/releases/tag/v1.0.0).
For maintenance, see [verify and publish these docs](documentation.md).
