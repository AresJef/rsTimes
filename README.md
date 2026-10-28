# rsTimes

**rsTimes 0.2.0b2** is a Python date and time library with a shared Rust core.
It provides calendar deltas, configurable parsing, a real `datetime.datetime`
subclass and a real `pandas.DatetimeIndex` subclass.

- **`Delta`**: relative calendar changes, absolute fields, scalar and bulk arithmetic.
- **`parse_str`, `parse`, `parse_to_epoch`**: shared parsing rules returning a date object or an epoch integer in a chosen unit.
- **`Configs`**: parsing vocabularies, ordering, fixed offsets and explicitly configured regional time zones.
- **`Pydt`**: calendar, boundary, time zone and formatting methods on a standard datetime subclass.
- **`Pddt`**: nanoseconds, explicit units, column operations and pandas index interoperability.

The distribution name is `rsTimes`; import `rstimes`. PLDT has not been implemented.
The optional Polars integration reads supported Series inputs.

## Installation and dependencies

This is a beta release. Select the version explicitly:

```sh
python -m pip install "rsTimes==0.2.0b2"
python -m pip install "rsTimes[dateutil,pandas,polars]==0.2.0b2"
```

| Dependency | Required version | Purpose |
|---|---|---|
| NumPy | >=2.5.3 | Required native scalar/array support |
| tzdata | >=2026.5, Windows only | Required IANA data for standard `ZoneInfo` |
| python-dateutil | >=2.9, optional `dateutil` extra | Import parserinfo and relativedelta rules; actual relativedelta interoperability |
| pandas | >=2.3.3 on CPython 3.12–3.14 except Windows ARM64; >=3.0.6 on CPython 3.15 or Windows ARM64 | Optional `pandas` extra, required for `Pddt` |
| Polars | >=2.0.0 | Optional `polars` extra, supported Series inputs |

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

One source tree supports ordinary GIL-enabled CPython 3.12,3.13,3.14 and3.15:

| Platform | CPU | Wheel baseline | Native verification runner |
|---|---|---|---|
| macOS | ARM64 | macOS11.0+ | macos-14 |
| macOS | x86_64 | macOS11.0+ | macos-15-intel |
| Windows | x86_64 | win_amd64 | windows-2025 |
| Windows | ARM64 | win_arm64 | windows-11-arm |
| Linux glibc | x86_64 | manylinux_2_28 | ubuntu-24.04, matching pinned container |
| Linux glibc | ARM64 | manylinux_2_28 | ubuntu-24.04-arm, matching pinned container |
| Linux musl | x86_64 | musllinux_1_2 | ubuntu-24.04, matching pinned container |
| Linux musl | ARM64 | musllinux_1_2 | ubuntu-24.04-arm, matching pinned container |

The release contains32 wheels and one complete sdist. Linux installation tests
run inside the matching libc, not only on the host. 32-bit, PyPy and free-threaded
CPython are unsupported. Runner testing does not claim physical testing on every
historical OS release permitted by a wheel tag.

Every position verifies real isolated core-only, core+Polars and pandas3
installations. Applicable pandas2 positions use the same wheel. Additional
latest-version representatives are recorded separately. The fixed main versions
are NumPy 2.5.3, pandas 3.0.6 and Polars 2.0.0; pandas2 compatibility uses2.3.3.
The frozen cytimes3.1.0 oracle runs separately with pandas2.3.3 and NumPy2.5.3.
It is a test-only dependency. The 4,588 independent frozen string expectations
remain protected. Shared cloud runners do not establish strict performance ratios.

## Development

The repository pins Rust in `rust-toolchain.toml`. Inside an activated environment:

```sh
python -m pip install --upgrade pip==26.2.2
python -m pip install -r requirements-dev.txt
maturin build --release --locked --interpreter python --out dist
python -m pip install --no-deps dist/*.whl
python -I -B tools/wheel_smoke.py --expect-version 0.2.0b2 --with-dateutil --with-pandas --with-polars
python -I -B tools/run_release_tests.py --junitxml evidence/tests.xml
python -I -B tools/check_public_docs.py
python -I -B tools/check_typing.py
```

Use separate output directories after source changes. Source-tree imports do not
replace installed-wheel verification. On PowerShell, install wheels with
`Get-ChildItem dist\*.whl | ForEach-Object { python -m pip install --no-deps $_.FullName }`.

## Demonstrations

The four `demo/*.py` scripts are interactive demonstrations. Delta, Parser and
Pydt use the separate `requirements-oracle.txt` environment to compare cytimes;
Pddt uses `requirements-test.txt` to compare pandas3. Both install the published
wheel. `demo/runtime.json` selects environments and the GitHub Release manifest;
the launcher checks version, installed location and native SHA256. It never
silently loads another wheel or compiles a temporary replacement. See the
[demo guide](demo/README.md). Do not force cytimes into the pandas3 environment.

## Automated publication

- Branch/PR/manual CI builds and tests, without publication permissions.
- Only a pushed annotated `v*` tag triggers `publish.yml`. The tag binds the exact
  source commit, successful complete CI run/attempt, manifest SHA256 and local
  performance completion receipt.
- Publication downloads that original tested32-wheel/sdist bundle. It does not
  rebuild files. All gates must pass before GitHub Release, followed by PyPI
  Trusted Publishing/OIDC. No long-lived PyPI token is used.
- All32 positions download the published version from PyPI, check the original
  SHA256, install it in clean provider environments and exercise functionality.
- The publisher identity is `AresJef/rsTimes`, `publish.yml`, environment `pypi`.

After a partial publication, retain the tag and original files. Verify remote
hashes before resuming missing uploads. Never move a published tag, overwrite
assets, mix incomplete CI attempts or rebuild substitutes for an existing version.

## Documentation and license

- [Delta API](docs/DeltaAPI.md), [Delta guide](docs/Delta使用说明.md)
- [Parser guide](docs/Parser使用说明.md), [object parsing](docs/Parser对象解析使用说明.md)
- [Pydt guide](docs/Pydt使用说明.md), [Pddt and epoch parsing](docs/Pddt与parse_epoch使用说明.md)
- [Errors](docs/错误处理使用说明.md), [release notes](docs/releases/v0.2.0b2.md)

Wheels include public stubs and `py.typed`, with annotations, docstrings and
examples. rsTimes uses the [MIT license](LICENSE); distributions include the
required third-party notices.
