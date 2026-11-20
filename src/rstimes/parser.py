"""Date/time parsing and standalone numeric text utilities implemented in Rust.

Use parse_str for text and parse for supported date/time objects or text.
Configs provides vocabulary and date ordering for string parsing.
parse_to_integer and parse_to_float use independent numeric grammars, with
whole-token validation or first-fragment extraction and optional grouping.

Date text inputs and string defaults accept real str subclasses and read
their native stored content, without calling __str__ or overridden sequence
methods. Call str(value) explicitly when conversion is intended.
"""
# Prepare shared optional type identities once, including scalar Timestamp and
# Polars inputs. Native reads need this registration, not an export adapter.
from . import _optional as _optional
from ._native import Configs, parse_str, parse, parse_to_epoch, parse_to_integer, parse_to_float, _restore_configs

__all__ = ["Configs", "parse_str", "parse", "parse_to_epoch", "parse_to_integer", "parse_to_float"]
