# Parsing numeric text

`parse_to_integer` and `parse_to_float` are independent Rust utilities. They do not
parse dates, use Configs, select a locale, or change the input accepted by Delta or
the datetime classes. Import them from `rstimes.parser` or package root:

```python
from rstimes.parser import parse_to_integer, parse_to_float

assert parse_to_integer("9223372036854775808") == 9223372036854775808
assert parse_to_float("0.3") == 0.3
```

## Whole tokens and extraction

Both functions default to `strict=True`. The complete string must be a number;
whitespace is not stripped. `strict=False` finds the first contiguous number and
permits surrounding text. Signs must be adjacent to the numeric part.

```python
assert parse_to_integer("quantity -123 items", strict=False) == -123
assert parse_to_float("price -12,50 EUR", strict=False) == -12.5
assert parse_to_float("prefix - abc 12 EUR", strict=False) == 12.0
assert parse_to_float("12abc34", strict=False) == 12.0
```

Integer extraction reads digits; it never converts a float and truncates it.
Without grouping, `parse_to_integer("12.5", strict=False)` extracts the text `12`.
Likewise, `.5` contains an extractable integer `5`, while float parsing returns 0.5.

Floats accept ASCII decimal and scientific syntax, including `12`, `.5`, `1.`,
`1,25` and `1.25e-3`. Dot and comma are alternative decimal marks. Without grouping,
a second mark ends a loose fragment: `12.5.6` gives 12.5. A complete exponent is
consumed; loose `1e+` gives 1.0, whereas strict mode rejects the incomplete exponent.
NaN, infinity, hexadecimal, underscores and non-ASCII digits are not numeric syntax.

## Explicit grouping and type priority

Set `allow_grouping=True` to recognize three-digit grouping. The first integer group
has one to three digits and subsequent groups have exactly three. Separators must
be consistent, and occur only in the mantissa's integer part.

| Token | Float with grouping | Integer with grouping |
|---|---:|---:|
| `1.234` | 1.234 | 1234 |
| `1,234` | 1.234 | 1234 |
| `12,345` | 12.345 | 12345 |
| `1,234,567` | 1234567.0 | 1234567 |
| `1.234.567` | 1234567.0 | 1234567 |
| `1.234,56` | 1234.56 | ValueError |
| `1,234.56` | 1234.56 | ValueError |
| `12,34` | 12.34 | ValueError |
| `1,23,456` | ValueError | ValueError |

These are deterministic type rules, not a guess about the writer's locale. A float
with one mark prefers a decimal, even if grouping is also possible. Repeated
identical marks mean integer grouping. With both mark types, the last is decimal
and every preceding group is validated. An integer never accepts a decimal part.

```python
assert parse_to_float("EUR 1.234,56", strict=False, allow_grouping=True) == 1234.56
assert parse_to_integer("quantity 1.234 items", strict=False, allow_grouping=True) == 1234
assert parse_to_float("1,234", allow_grouping=True) == 1.234
```

Malformed grouped candidates raise in loose mode too; `12,34` cannot silently become
integer 1234, and `1,23,456` cannot be chopped into a smaller successful number.
Grouping disabled means grouping is not recognized: strict input containing such
extra marks is rejected, while loose input ends at the next disallowed character.
For example, non-grouped loose float `1.234,56` extracts 1.234.

## Types, limits and errors

* Input is str or a real str subclass. Stored Unicode is read directly; custom
  `__str__`, indexing and numeric conversion methods are not used.
* `strict` and `allow_grouping` are keyword-only, accepting Python bool and NumPy
  bool_. Numbers, None and arbitrary truth objects are rejected as options.
* Integer results are Python int, bounded to `-2**127 .. 2**127-1`. A value outside
  this interval raises OverflowError in both modes; it is never wrapped or clipped.
* Float results use correctly rounded binary64 conversion. Signed zero and ordinary
  underflow are preserved; text above finite float capacity raises OverflowError.
  Large integer text is converted as float directly, without a 64/128-bit integer
  accumulator that could wrap first.
  A validated decimal without an exponent and with at most 15 mantissa digits can
  use an exact integer divided once by an exactly representable power of ten.
  Longer mantissas and exponents use Rust's standard conversion. Both paths retain
  the same rounding rule; neither repeatedly multiplies fractional digits by 0.1.
* Empty or digit-free input raises ValueError; absence of a number is not zero.
  Unsupported input types, including None and bytes, raise TypeError.
* Failures include the public entry, argument and a bounded safe preview. Reliable
  numeric positions are Unicode code-point indices, not UTF-8 byte offsets.

These functions add no required or optional Python dependency beyond the package's
existing dependency contract. Currency symbols are only surrounding text in loose
mode; no exchange-rate, locale or currency-rounding operations are performed.
