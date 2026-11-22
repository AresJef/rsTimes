# Install rsTimes

Use a supported 64-bit CPython interpreter. Install the core package for
`Delta`, `Pydt`, `Configs`, and the parsing functions. The core install brings
NumPy and packaging. On Windows it also installs tzdata.

```bash
python -m pip install "rsTimes==1.1.1"
```

## Check the installed version

(install-check-distribution-version)=
```python
from importlib.metadata import version

installed = version("rsTimes")
print(installed)
```

**Output**

```text
1.1.1
```

Run this snippet with the same Python interpreter you used to install rsTimes.

## Add the integration you use

For pandas date indexes, install the `pandas` extra.

```bash
python -m pip install "rsTimes[pandas]==1.1.1"
```

For Polars date columns or expressions, install the `polars` extra.

```bash
python -m pip install "rsTimes[polars]==1.1.1"
```

For adapters that accept a dateutil rule or vocabulary, install the
`dateutil` extra.

```bash
python -m pip install "rsTimes[dateutil]==1.1.1"
```

An installed pandas or Polars below the supported minimum emits
{ref}`DependencyWarning <dependency-warning-filter>` when you load its adapter.

Combine extras in one specification, such as `"rsTimes[pandas,polars]==1.1.1"`.
See [installation requirements](../compatibility/platforms.md) for operating
systems and Python ABIs. If you use a free-threaded interpreter, check
[the required dependencies](../compatibility/free-threaded.md).

[Move a billing date by one calendar month](index.md#add-one-month-to-a-billing-date)
to try the core package.
