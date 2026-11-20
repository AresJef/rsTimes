# Parse numbers from text

Use `parse_to_integer` for counts and other integers. Use `parse_to_float`
for decimal numbers. Both accept real strings and string subclasses.
The results are standard Python `int` and `float` values.
Import the functions from `rstimes` or `rstimes.parser`.

## Read an integer with grouping marks

(numeric-grouped-integer)=
```python
from rstimes import parse_to_integer

quantity = parse_to_integer(
    "1,234,567", allow_grouping=True
)
print(quantity)
```

**Output**

```text
1234567
```

With grouping enabled, start with one to three ASCII digits. Each following
group has three digits and uses the same separator, either a comma or a dot.

## Extract a decimal amount from a label

(numeric-extract-decimal-amount)=
```python
from rstimes import parse_to_float

amount = parse_to_float(
    "EUR 1.234,56", strict=False,
    allow_grouping=True,
)
print(amount)
```

**Output**

```text
1234.56
```

`strict=True` is the default and requires a complete numeric token.
Leading or trailing whitespace raises `ValueError`. `strict=False`
scans through a prefix and reads the
first contiguous numeric part. Signs belong next to the digits or decimal
mark. With grouping disabled, loose integer parsing of `"12.5"` reads
the integer fragment `12`.

## Choose the interpretation for a single separator

(numeric-float-single-decimal)=
```python
from rstimes.parser import parse_to_float

value = parse_to_float(
    "1,234", allow_grouping=True
)
print(value)
```

**Output**

```text
1.234
```

Floats prefer a decimal when there is one separator. Repeated identical marks
are grouping, and with both comma and dot the last mark is decimal. For an
integer with grouping enabled, `"1,234"` means `1234`. These rules are fixed.

| Token | `parse_to_integer` | `parse_to_float` |
| --- | --- | --- |
| `1,234` | `1234` | `1.234` |
| `1,234,567` | `1234567` | `1234567.0` |
| `1.234,56` | `ValueError` | `1234.56` |

The table uses `allow_grouping=True` in both columns. Float tokens can also use
an exponent, as in `1.25e-3`. A loose float can stop before an incomplete
exponent. A strict float requires a complete exponent.

## Repair invalid grouping

(numeric-invalid-integer-groups)=
```python
from rstimes import parse_to_integer

try:
    parse_to_integer(
        "1,23,456", strict=False,
        allow_grouping=True,
    )
except ValueError as error:
    print(type(error).__name__)
```

**Output**

```text
ValueError
```

Use `"123456"` or `"123,456"`. Both modes reject malformed grouping when
grouping is enabled. The options accept Python bool and NumPy bool scalars.

Integer output ranges from `-2**127` through `2**127 - 1`. Float output is
rounded to binary64 and preserves signed zero. A value beyond either finite
range raises `OverflowError`. Empty or digit-free input raises
`ValueError`. Use [date parsing](parsing.md) for date strings or epochs.
