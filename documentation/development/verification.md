# Documentation verification evidence

This website describes the public **rsTimes 0.2.0b3 beta** package. Its
documentation checks cover descriptions and actual example behavior; a
reproduction of a disclosed rsTimes defect is not a product conformance pass.
The [known issues](../compatibility/known-issues.md) retain those distinctions.

The published site includes these machine-readable receipts from the workflow
that built it:

- [Complete entry–scenario–page–example–environment–evidence table (CSV)](https://aresjef.github.io/rsTimes/0.2.0b3/verification/coverage.csv)
- [The same complete coverage table (JSON)](https://aresjef.github.io/rsTimes/0.2.0b3/verification/coverage.json)
- [Product and documentation identities, actual ABI-specific package hashes, build tools and verification summary](https://aresjef.github.io/rsTimes/0.2.0b3/_meta/build.json)
- [Checksums of public website files](https://aresjef.github.io/rsTimes/_meta/files.json)

The table contains canonical rsTimes paths, including inherited operations on
rsTimes objects and the registered Series/Expr date namespaces. Module
re-exports and `Pldt.pldt` are aliases rather than extra entry counts. Generic
Python class-authoring infrastructure and unrelated dtype APIs are outside
this date/time documentation scope.

Each evidence link identifies the actual page and code hashes, tested
interpreter/profile, package bytes and observed pass status. Expr examples
execute both eager selection and lazy collection. The required environments
include core without optional integrations, frozen baseline/full,
pandas 2, current pandas/Polars comparisons, Polars-only, optional exports,
public-install smoke, actual Windows and actual free-threaded interpreters.
The declared profiles and package bytes are checked before evidence is
accepted. Results for a changed page or a different verifier are stale.

The public receipts omit local account paths, credentials, raw environment
directories and internal dependency binaries. For updates and recovery, see
[the documentation maintenance workflow](documentation.md).
