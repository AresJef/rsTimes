# rsTimes

rsTimes 0.2.0b3 is a beta Python date and time library with a shared Rust core.
It combines scalar calendars, pandas indexes and native Polars columns/expressions.

- **`Delta`**: exact nanosecond relative changes, absolute fields and scalar/bulk arithmetic.
- **`parse_str`, `parse`, `parse_to_epoch`**: shared configurable parsing returning date objects or integer epoch ticks.
- **`Configs`**: vocabularies, ordering, fixed offsets and explicitly configured regional zones.
- **`Pydt`**: a real `datetime.datetime` subclass with calendar, boundary, zone and formatting operations.
- **`Pddt`**: a real `pandas.DatetimeIndex` subclass with explicit units, nanoseconds and column operations.
- **`Pldt`**: a real `polars.Series` subclass, with Series/Expr `.pldt` namespaces and shared Rust date kernels.

The distribution name is `rsTimes`; import `rstimes`. The four core class names
are **Delta, Pydt, Pddt and Pldt**. Date-field replacement uses
`x.pddt.replace(...)` or `x.pldt.replace(...)`; native host replacement methods
retain their own meaning. See the [b3 release notes](docs/releases/v0.2.0b3.md)
for upgrade details and explicitly deferred custom-protocol cases.

## Installation and dependencies

This is a beta release. Select the version explicitly:

```sh
python -m pip install "rsTimes==0.2.0b3"
python -m pip install "rsTimes[dateutil,pandas,polars]==0.2.0b3"
```

| Dependency | Required version | Purpose |
|---|---|---|
| NumPy | >=2.5.3 | Required native scalar/array support |
| tzdata | >=2026.5, Windows only | Required IANA data for standard `ZoneInfo` |
| python-dateutil | >=2.9, optional `dateutil` extra | Import parserinfo and relativedelta rules; actual relativedelta interoperability |
| pandas | >=2.3.3 on CPython 3.12–3.14 except Windows ARM64; >=3.0.6 on CPython 3.15 or Windows ARM64 | Optional `pandas` extra, required for `Pddt` |
| Polars | >=2.0.0 ordinary profile | Optional `polars` extra, required for `Pldt`; t requires a compatible upstream runtime |

Core `Delta`, `Configs`, parsing and `Pydt` work without dateutil, pandas or Polars.
Without python-dateutil, `Configs.from_parserinfo()` and
`Delta.from_relativedelta()` raise `ImportError` with an installation hint;
ordinary parsing does not fall back to dateutil. Install integrations before
starting Python. Adding a dependency to an already running interpreter requires
a restart. Broken installed dependencies propagate their actual import errors.
Installing pandas also installs its own dependencies, which can include dateutil.
The runtime does not require Babel, cytimes or Cython.

## Usage

```python
from datetime import datetime
from rstimes import Configs, Delta, Pydt, parse, parse_str, parse_to_epoch

assert datetime(2024, 1, 31) + Delta(months=1) == datetime(2024, 2, 29)
assert Pydt(2024, 1, 31).add(months=1) == datetime(2024, 2, 29)
assert parse(datetime(2024, 5, 7)) == datetime(2024, 5, 7)
assert parse_str("2024-01-02T12:34+08:00", ignoretz=False).isoformat() == "2024-01-02T12:34:00+08:00"
assert parse_to_epoch(1e-9, unit="ns") == 1

cfg = Configs()
cfg.add_month("custommonth", 2)
assert parse_str("29 custommonth 2024", cfg=cfg) == datetime(2024, 2, 29)
```

`Pddt` accepts collections. Choose a unit during construction and use
`as_unit()` explicitly to convert an existing object:

```python
from rstimes import Delta, Pddt, parse_to_epoch

x = Pddt(["2024-01-31T12:30:00.123456789", None], unit="ns", name="events")
y = x + Delta(months=1)
assert y[0].isoformat() == "2024-02-29T12:30:00.123456789"
assert y.isna().tolist() == [False, True]

# Bare Pddt numbers are ticks in the chosen unit; parser numbers are seconds.
assert Pddt([1], unit="ms").asi8.tolist() == [1]
assert parse_to_epoch(1, unit="ms") == 1000
```

The default ordering is `yearfirst=True, dayfirst=False`, overridable by Configs
and explicit options. `strict=False`; `isoformat=True` tries ISO first and may
fall back to general parsing. The default `ignoretz=True` discards textual time
zones; pass `False` to retain them. Parser interprets fields; the chosen result
class controls capacity and the existence of regional local times.

`Pydt` retains microsecond precision and years1–9999. `Pddt` supports `s/ms/us/ns`
and zero, negative and wide years within the selected unit's capacity. Operations
on an existing `Pddt` preserve its unit: insufficient precision or capacity raises
an error and requires explicit `as_unit()`. It never silently changes unit or
turns an ordinary failure into NaT. `None` preserves optional fields; zero is a
real numeric value.

`to_unix_ms` and `from_unix_ms` convert aware dates and Unix milliseconds.
The former floors submillisecond values; the latter returns a UTC-aware datetime.
Type errors are `TypeError`, naive inputs are `ValueError`, and capacity failures
are `OverflowError`.

## Native support and verification

One source tree supports ordinary CPython 3.12–3.15 and free-threaded CPython
3.14t/3.15t. The native release matrix is:

| Platform | CPU | Wheel/libc policy | Ordinary Python | Free-threaded Python |
|---|---|---|---|---|
| macOS | ARM64 | macOS 11.0 wheel tag; dependency OS floor also applies | 3.12–3.15 | 3.14t, 3.15t |
| macOS | Intel x86_64 | macOS 11.0 ordinary tag; t requires 14.0+ | 3.12–3.15 | 3.14t, 3.15t |
| Windows | x86_64 | win_amd64 | 3.12–3.15 | 3.14t, 3.15t |
| Windows | ARM64 | win_arm64 | 3.12–3.15 | 3.14t, 3.15t |
| Linux glibc | x86_64 | manylinux_2_28 | 3.12–3.15 | 3.14t, 3.15t |
| Linux glibc | ARM64 | manylinux_2_28 | 3.12–3.15 | 3.14t, 3.15t |
| Linux musl | x86_64 | musllinux_1_2 | 3.12–3.15 | 3.14t, 3.15t |
| Linux musl | ARM64 | musllinux_1_2 | 3.12–3.15 | 3.14t, 3.15t |

This is 32 ordinary plus16 t wheels and one canonical sdist. 32-bit, PyPy,
universal2 and 3.13t are outside the matrix. Linux installation tests use the
matching libc container. Wheel tags and hosted-runner tests do not prove
physical execution on every historical OS release allowed by a tag.

The complete dependency set determines the usable OS floor. In particular,
NumPy 2.5.3 requires macOS 14.0+ on ARM64 Python 3.14/3.15, including t builds;
Intel t integration also requires macOS 14.0+. Use the
[free-threaded guide](docs/free-threaded-python.md) for exact conditions.

**NoGIL support requires matching upstream dependencies.** The t qualification
uses pandas 3 and fixed, unmodified official Polars 2.1.0 sources when a
suitable official wheel is unavailable. Internal CI builds are not a runtime
supply channel. rsTimes does not ship, download or maintain a Polars fork or
custom user runtime. Users obtain a compatible upstream Polars build; this
matrix does not promise that every dependency has a public t wheel everywhere.

Every release position tests actual isolated installed wheels, with core-only,
Polars-only and pandas3 configurations as applicable. Ordinary pandas2 and
latest-version representatives are separate profiles. The frozen cytimes oracle
is test-only and isolated from pandas3 product environments. Shared cloud
runners are not used as strict performance proof; measured results name the
actual artifact, ABI, workload and baseline.

## Development

The repository pins Rust in `rust-toolchain.toml`. Inside an activated environment:

```sh
python -m pip install --upgrade pip==26.2.2
python -m pip install -r requirements-dev.txt
maturin build --release --locked --interpreter python --out dist
python -m pip install --no-deps dist/*.whl
python -I -B tools/wheel_smoke.py --expect-version 0.2.0b3 --with-dateutil --with-pandas --with-polars
python -I -B tools/run_release_tests.py --junitxml evidence/tests.xml
python -I -B tools/check_public_docs.py
```

Use separate output directories after source changes. Source-tree imports do not
replace installed-wheel verification. On PowerShell, install wheels with
`Get-ChildItem dist\*.whl | ForEach-Object { python -m pip install --no-deps $_.FullName }`.

For Python type checks, prepare the separate analysis environment and pinned
Node/Pyright toolchain described in the [type-checking guide](docs/type-checking.md).

## Demonstrations

The four `demo/*.py` scripts are interactive demonstrations. Delta, Parser and
Pydt use the separate `requirements-oracle.txt` environment to compare cytimes;
Pddt uses `requirements-test.txt` to compare pandas3. In this development checkout,
`demo/runtime.json` selects the verified local wheel and separate oracle
environments. Public-release checkouts select their published wheel and manifest.
The launcher checks version, installed location and native SHA256. It never
silently loads another wheel or compiles a temporary replacement. See the
[demo guide](demo/README.md). Do not force cytimes into the pandas3 environment.

## Automated publication

- PRs run representative pilot checks; a fixed main commit runs the full48 matrix.
  Manual verification cannot publish. Documentation-only follow-ups have their
  recorded documentation/demo checks without rebuilding a frozen release.
- Only a pushed annotated `v*` tag triggers `publish.yml`. The tag binds the exact
  source commit, successful complete CI run/attempt, manifest SHA256 and local
  performance completion receipt.
- Publication downloads that original tested wheel/sdist bundle. It does not
  rebuild files. All gates must pass before GitHub Release, followed by PyPI
  Trusted Publishing/OIDC. No long-lived PyPI token is used.
- Every release-matrix position downloads the published version from PyPI,
  checks the original SHA256, installs it in clean provider environments and
  exercises functionality.
- The publisher identity is `AresJef/rsTimes`, `publish.yml`, environment `pypi`.

After a partial publication, retain the tag and original files. Verify remote
hashes before resuming missing uploads. Never move a published tag, overwrite
assets, mix incomplete CI attempts or rebuild substitutes for an existing version.

## Documentation and license

- [Delta API](docs/DeltaAPI.md), [Delta guide](docs/Delta使用说明.md)
- [Parser guide](docs/Parser使用说明.md), [object parsing](docs/Parser对象解析使用说明.md)
- [Pydt guide](docs/Pydt使用说明.md), [Pddt and epoch parsing](docs/Pddt与parse_epoch使用说明.md)
- [Pldt guide](docs/Pldt使用说明.md), [NoGIL](docs/free-threaded-python.md), [type checking](docs/type-checking.md)
- [Errors](docs/错误处理使用说明.md), [release notes](docs/releases/v0.2.0b3.md)

Wheels include public stubs and `py.typed`, with annotations, docstrings and
examples. rsTimes uses the [MIT license](LICENSE); distributions include the
required third-party notices.
