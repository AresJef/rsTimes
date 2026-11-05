# Distribution, Python and optional dependencies

The public **0.2.0b3** distribution contains 48 native wheels and one complete
source archive. This table describes that release's distribution matrix; a
wheel tag alone is not proof of execution on every older operating system.

| Platform category | Ordinary CPython | Free-threaded CPython |
|---|---|---|
| macOS ARM64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |
| macOS Intel x86_64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |
| Windows x86_64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |
| Windows ARM64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |
| Linux glibc 2.28 x86_64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |
| Linux glibc 2.28 ARM64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |
| Linux musl 1.2 x86_64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |
| Linux musl 1.2 ARM64 | 3.12, 3.13, 3.14, 3.15 | 3.14t, 3.15t |

The supported matrix is 64-bit. It does not promise 32-bit, PyPy, universal2 or
CPython 3.13t support. The metadata's Python lower bound is 3.12; it does not
establish support for every future ABI.

## Dependency roles and tested versions

| Dependency | Declared role / minimum | Release or documentation qualification |
|---|---|---|
| NumPy | Required, >=2.5.3 | 2.5.3 |
| tzdata | Required on Windows, >=2026.5 | 2026.5 in the release matrix |
| python-dateutil | Optional `dateutil` extra, >=2.9 | 2.9.0.post0; parserinfo/relativedelta adapters |
| pandas | Optional `pandas` extra | 3.0.6 release baseline; ordinary 2.3.3 compatibility where applicable |
| Polars | Optional `polars` extra, >=2.0.0 for ordinary Python | 2.0.0 ordinary baseline; 2.1.0 representative and internal t qualification |
| PyArrow | Optional interchange dependency, separate from the three extras | 23.0.1 in ordinary documentation interchange examples |

Pandas 2.3.3 compatibility applies to ordinary CPython 3.12–3.14 except
Windows ARM64. Python 3.15 and Windows ARM64 require pandas >=3.0.6 according
to the extra's environment markers. Free-threaded qualification uses pandas 3.
The documentation also executes a separate representative pandas/Polars profile
with pandas 3.1.0 and Polars 2.1.0; that is separate from the frozen release
baseline and is not an arbitrary-future-version guarantee.

NumPy/Python/native dependencies can raise the complete environment's OS
floor. In particular, the qualified Intel macOS t profile requires macOS 14
or later. With NumPy 2.5.3, ARM64 CPython 3.14/3.15 ordinary and t profiles also
require macOS 14 or later. Use operating systems supported by the selected
Python and native dependencies; the rsTimes wheel's deployment tag does not
override them.

Pldt's core operations use Polars and NumPy. Pddt uses pandas. dateutil and
PyArrow are needed only for their corresponding adapters/interchange paths;
the package does not silently download them. Node, Pyright, Sphinx, Babel and
cytimes are not rsTimes runtime dependencies. The latter comparison tools are
kept in separate development/oracle environments.

## Free-threaded Polars is a dependency condition

The [free-threaded guide](free-threaded.md) explains the actual ABI/GIL checks
and the fixed official Polars source used internally. rsTimes does not provide
a fork or an installation channel for that runtime. Internal qualification
does not establish that official t wheels exist for every platform.

## Release identity and evidence boundaries

The [GitHub b3 release](https://github.com/AresJef/rsTimes/releases/tag/v0.2.0b3)
and [PyPI b3 files](https://pypi.org/project/rsTimes/0.2.0b3/#files) identify the
public distribution. The release assets include a source/wheel/native manifest
and checksums. The [release's free-threaded source guide](https://github.com/AresJef/rsTimes/blob/v0.2.0b3/docs/free-threaded-python.md)
records the qualified dependency conditions.

Documentation examples have their own declared profiles and execution evidence.
A macOS example run does not establish a Windows/Linux result. A static HTML
build also does not replace a successful import and real work. See
[the documentation verification workflow](../development/documentation.md)
for the mapping and maintenance rules.
