# Check Python and platform support

The rsTimes 1.1.0 release provides 48 wheels and a source distribution.
Choose the wheel that matches your CPython ABI, operating system, and
architecture.

| Operating system | 64-bit architectures | Wheel system targets |
| --- | --- | --- |
| macOS | ARM64 and Intel x86-64 | macOS 11 or later. Free-threaded Intel requires macOS 14 or later. |
| Windows | ARM64 and x86-64 | Windows wheel for the matching architecture. |
| Linux | ARM64 and x86-64 | glibc 2.28+ or musl 1.2+, with distinct wheel tags. |

The release has wheels for standard CPython 3.12, 3.13, 3.14, and 3.15,
plus free-threaded 3.14t and 3.15t. Dependencies can raise the effective
OS requirement. See the [release file list](https://pypi.org/project/rsTimes/1.1.0/#files).

## Match dependency requirements

The core package requires packaging 22.0 or newer to compare the versions of
optional integrations. See {ref}`the warning policy <dependency-warning-filter>`
if a manually installed pandas or Polars falls below the applicable minimum.

NumPy 2.5.3 or newer is required. On Windows, rsTimes also requires
tzdata 2026.5 or newer.

Pddt requires pandas. The pandas extra requires at least 2.3.3 on ordinary
configurations where pandas 2 is supported. On Python 3.15 and on Windows
ARM64, the extra requires pandas 3.0.6 or newer. The free-threaded
pandas qualification uses pandas 3.0.6.

Pldt requires Polars 2.0.0 or newer. Free-threaded Pldt use also requires
a compatible Polars runtime. Read [the free-threaded setup](free-threaded.md)
for the qualified dependency paths.

See [optional dependencies](optional-dependencies.md) for integration-specific
installation commands.
