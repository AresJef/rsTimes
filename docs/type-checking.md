# Python type checks

rsTimes uses **Pyright 1.1.414** as its only Python type checker. The checked
development profile uses Node 26.7.0, NumPy 2.5.3, pandas 3.0.6 with the matching
3.0 family of pandas stubs, and Polars 2.1.0. This analysis profile is separate
from the supported runtime minimum and compatibility test environments.

Install `requirements-typing.txt` in an isolated Python environment, install the
actual rsTimes wheel to be checked, and prepare the pinned checker:

```sh
npm --prefix tools/typing ci --ignore-scripts --omit=optional
python -I tools/check_typing.py
```

The installed check retains the original three positive files and all 48
negative locations. It also checks private native-boundary positive examples
and four additional rejected calls. `verifytypes --ignoreexternal` must resolve
the package inside that Python environment and report no unknown or ambiguous
exported types. Source-directory resolution is disabled for these checks.

To check all active implementation files, tools, and four demos, use the same
checker with the existing frozen cyTimes 3.1.0 oracle package directory:

```sh
python -I tools/check_typing.py --full \
  --oracle-package /absolute/path/to/oracle/site-packages/cytimes \
  --evidence-dir /absolute/path/to/new/type-check-evidence
```

Full mode makes a read-only typing view of that oracle's own files. It does not
install cyTimes into the pandas 3 environment, import its binary there, or
replace the official stubs. The active source scope is explicit in
`pyrightconfig.json`.

The gate also accepts `--python-version 3.14` and `--python-version 3.15` for
the two added language configurations. These are static language checks; they
do not prove the runtime GIL state or replace installed t-wheel tests. CI runs
the 3.12, 3.14, and 3.15 configurations separately against the installed package.

The demos deliberately include rejected inputs, `NotImplemented` negotiation,
and real external behavior that a third-party stub cannot express. Their exact
diagnostics remain visible and are checked against
`tests/typing/demo_diagnostics.json`; additional or missing diagnostics fail the
gate. A successful full gate means **zero unexpected errors**, rather than
claiming that those deliberately retained diagnostics vanished.

Approved inheritance differences and narrowly proved dynamic boundaries are
recorded individually in `tests/typing/pyright_exceptions.json`. Each record
identifies its statement, rule, reason, and applicable runtime tests. The gate
rejects unrecorded line suppressions, legacy Mypy ignores, and file-wide Pyright
suppression. Unnecessary line ignores also fail. Genuine external callback
behavior and the established public signatures remain intact.

`_native.pyi` describes the real Rust boundary, including opaque prepared
contexts and precise result constructors. `_backend_types.pyi` supplies only
structural facts about real pandas storage omitted by some upstream stub
versions. Runtime dispatch still uses the actual pandas classes; these type
files add no container wrappers or per-row conversions.

Raw checker JSON, stderr, fixture hashes, installed payload hashes, oracle
symbol identities, and the final gate result are saved in the requested
evidence directory. Static checks complement the runtime, concurrency, build,
and performance gates; they do not replace them.
