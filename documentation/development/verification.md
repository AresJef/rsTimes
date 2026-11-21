# Documentation verification evidence

These receipts describe the rsTimes 1.0.0 documentation and its
actual build and execution context.

- <a href="../verification/coverage.csv">Full entry, scenario, page, example, environment and evidence table in CSV</a>
- <a href="../verification/coverage.json">The same coverage table in JSON</a>
- <a href="../_meta/build.json">Documented product, documentation commit, wheel identities and build context</a>
- <a href="../../_meta/files.json">Checksums of site files</a>

The canonical public entries include rsTimes-owned APIs,
registered namespaces and supported documentation for inherited
operations on rsTimes objects. Module re-exports use the
canonical entry's result. Separate profile records show the
actual installed wheel, interpreter, dependencies and example
source. Expr evidence comes from executed queries.
Wrong identities, missing cases and stale page results prevent
a complete gate from passing.

Use the hash for the bytes you downloaded.

- `report_sha256` verifies the linked report in this site. The
  report uses a generic package path and omits the full transcript.
- `ci_report_sha256` verifies the sanitized report member in the
  Actions producer ZIP. Line endings can make its bytes differ from
  those of the report linked here.
- `original_report_sha256` records the worker report's hash before
  export. It appears in the exported report. Verification of that
  hash requires the original worker bytes.

A preview identifies the local verifier receipts with
`report_origin` and `local_report_sha256`. When it reuses a matching
historical Actions producer receipt, it identifies the historical
origin and retains that producer member's hash.

The public records cover documentation and example execution.
Product distribution qualifications and performance comparisons
are recorded with the [1.0.0 release](https://github.com/AresJef/rsTimes/releases/tag/v1.0.0).
For maintenance, see [verify and publish these docs](documentation.md).
