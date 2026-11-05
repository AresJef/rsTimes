"""Private Rust boundary types; borrowed inputs retain owners through each call.

Opaque type-only classes describe values returned by native factories, not
additional runtime exports. Workers consume Rust data and never Python objects.
"""
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, tzinfo
from time import struct_time
from types import NotImplementedType
from typing import Literal, SupportsIndex, TypeAlias, TypeVar, type_check_only
import numpy as np
import polars as pl
from .delta import Delta as Delta
from .parser import Configs as Configs, parse as parse, parse_str as parse_str, parse_to_epoch as parse_to_epoch

_DateT = TypeVar("_DateT", bound=datetime)
_SeriesT = TypeVar("_SeriesT", bound=pl.Series)
_Unit: TypeAlias = Literal["s", "ms", "us", "ns"]
_PolarsUnit: TypeAlias = Literal["ms", "us", "ns"]

def _free_threaded_build() -> bool:
    """Report this native binary's compiled free-threaded ABI.

    Returns
    -------
    bool
        True for a free-threaded build. This is independent of the actual runtime
        GIL state, which installed-package checks inspect separately.
    """


class _PydtBase(datetime):
    """Real native datetime base; normal Python constructors retain subclass hooks."""

class _PddtPolicies:
    """Immutable prepared DST policy; masks retain their complete original positions."""

class _PddtTicks:
    """Immutable bytes-owner span captured before later argument callbacks."""

_InputBytes: TypeAlias = bytes | _PddtTicks

@type_check_only
class _PddtIntegers:
    """Owned scalar or row-aligned optional integers produced by native preparation."""

@type_check_only
class _PddtParts:
    """Owned date or clock components retaining prepared source timezone metadata."""

@type_check_only
class _PddtOperand:
    """Prepared arithmetic values and real callback owners for one eager call."""

    @property
    def date(self) -> bool:
        """Whether the prepared operand is a date, rather than a duration."""

@type_check_only
class _PddtRangeEndpoints:
    """Range endpoints with separate local carrier and target-unit constraints."""
    @property
    def start(self) -> int | None:
        """Return the prepared start tick, or None when absent."""
    @property
    def end(self) -> int | None:
        """Return the prepared end tick, or None when absent."""
    @property
    def unit(self) -> _Unit:
        """Return the chosen final date unit."""
    @property
    def carrier_unit(self) -> _Unit:
        """Return the local-wall carrier unit used before final localization."""
    @property
    def zone(self) -> tzinfo | None:
        """Return the resolved timezone owner, independently of range length."""

@type_check_only
class _RangeFrequency:
    """Shared checked frequency plan, independent of pandas DateOffset execution."""
    @property
    def rounding_step(self) -> int | None:
        """Return a fixed rounding step when that frequency has one."""
    @property
    def tick(self) -> int | None:
        """Return a fixed elapsed-time tick; calendar frequencies return None."""

@type_check_only
class _StrptimeFormat:
    """Cached immutable format structure; live vocabulary is supplied separately."""
    @property
    def needs_locale(self) -> bool:
        """Return whether system format-template data is required."""

@type_check_only
class _StrftimeContext:
    """Pure fractional formatting plan without retained user callbacks."""
    def native(self) -> bool:
        """Return whether all requested fields have a native numeric path."""
    def modified(self) -> bool:
        """Return whether the fractional directives require prepared output."""
    def plugin_data(self) -> bytes:
        """Return owned serialized plan bytes for an official Expr plugin."""

class _PldtTextContext:
    """Immutable Rust vocabulary/default snapshot; eager callers may share its Arc."""
    def plugin_kwargs(self) -> dict[str, object]:
        """Return versioned owned values for expression serialization."""

class _PldtFormatContext:
    """Compiled format plus immutable recognition data for one parse operation."""
    @property
    def has_fraction(self) -> bool:
        """Return whether fractional seconds occur in the format."""
    @property
    def has_timezone(self) -> bool:
        """Return whether the format contains timezone directives."""
    def plugin_kwargs(self) -> dict[str, object]:
        """Return owned format and recognition values for expression execution."""

class _PldtPolicyContext:
    """Prepared native DST strategy without a worker-side Python callback."""
    @property
    def infers(self) -> bool:
        """Return whether ordered ambiguity inference is required."""
    def plugin_kwargs(self) -> dict[str, object]:
        """Return versioned policy values, retaining complete mask positions."""

class _PldtZoneContext:
    """Immutable native timezone metadata without a retained Python tzinfo."""
    @property
    def key(self) -> str:
        """Return the normalized zone identifier."""
    @property
    def fixed_seconds(self) -> int | None:
        """Return a constant offset when the zone has one."""
    def plugin_kwargs(self) -> dict[str, object]:
        """Return owned zone data for expression execution."""

@type_check_only
class _PldtOperand:
    """Owned arithmetic values; only eager adapters may retain real callbacks."""
    @property
    def kind(self) -> int:
        """Return the internal duration/date/Delta discriminant."""
    @property
    def scalar(self) -> bool:
        """Return whether the operand is a scalar broadcast."""
    @property
    def scalar_dynamic(self) -> bool:
        """Return whether that scalar uses a real Python arithmetic callback."""
    @property
    def dynamic(self) -> bool:
        """Return whether any row needs a real eager callback."""
    def plugin_column(self) -> pl.Series:
        """Export ordinary row-aligned Delta values as a native binary Series."""
    def plugin_data(self) -> bytes:
        """Serialize ordinary operands; dynamic callbacks cannot enter Expr workers."""

@type_check_only
class _PldtParts:
    """Prepared clock/date values with retained native timezone identities."""
    def expression(self) -> tuple[pl.Series, pl.Series, dict[str, object]]:
        """Export native clock values, zone IDs and owned plugin metadata."""

@type_check_only
class _PldtRangeEndpoints:
    """Prepared range endpoints with explicit timezone and final-unit constraints."""
    @property
    def unit(self) -> _PolarsUnit:
        """Return the chosen final unit."""
    def carrier(self) -> tuple[int | None, int | None, _Unit]:
        """Return exact local ticks and their s/ms/us/ns carrier, separate from storage."""

@type_check_only
class _PldtPeriodContext:
    """Prepared native period definition shared by eager and Expr paths."""
    def plugin_data(self) -> bytes:
        """Return owned serialized plugin arguments for the prepared period."""

@type_check_only
class _PldtOutputContext:
    """Prepared output role and precision, independent of date row count."""
    def plugin_data(self) -> bytes:
        """Return owned serialized output-role and precision arguments."""

_allocation_cache: object

def _bool_option(value: object, entry: str, parameter: str) -> bool:
    """Expose strict preparation to thin Python wrappers; errors stay cold.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _configure_optional(timestamp: object, duration: object, nat: object, series: object, timestamp_replace_needs_tail: bool) -> None:
    """Publish the type objects captured by the shared optional-dependency entry.

# Errors
Rejects an invalid private registration without publishing that type.

    :param timestamp: Prepared timestamp input; native validation and ownership rules apply.
    :param duration: Prepared duration input; native validation and ownership rules apply.
    :param nat: Prepared nat input; native validation and ownership rules apply.
    :param series: Prepared series input; native validation and ownership rules apply.
    :param timestamp_replace_needs_tail: Prepared timestamp_replace_needs_tail input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _integer_arg(value: object, entry: str, parameter: str) -> int:
    """Share integer preparation with thin wrappers without a second conversion.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _local_timezone_name() -> str:
    """Resolve a process system IANA name only when the Python local service asks.

    :returns: str; errors preserve the native or external exception contract.
    """

def _localized_name(value: datetime, locale: object | None, weekday: bool) -> str:
    """Read a true stored month or weekday and return its compiled wide name.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param locale: Prepared locale input; native validation and ownership rules apply.
    :param weekday: Prepared weekday input; native validation and ownership rules apply.
    :returns: str; errors preserve the native or external exception contract.
    """

def _pddt_binary(data: bytes, unit: str, zone: object | None, operand: _PddtOperand, subtract: bool, entry: str) -> tuple[bytes, _Unit, bool, bool]:
    """Execute the checked private native boundary for _pddt_binary.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param operand: Prepared operand input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, bool, bool]; errors preserve the native or external exception contract.
    """

def _pddt_calendar(first: _PddtIntegers, policy: _PddtPolicies, kind: str, second: _PddtIntegers | None = None, third: _PddtIntegers | None = None, size: int | None = None, unit: str | None = None, target: object | None = None, entry: str = 'Pddt') -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_calendar.

    :param first: Prepared first input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param second: Prepared second input; native validation and ownership rules apply.
    :param third: Prepared third input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_check_native_dates(data: object, mask: bytes, entry: str) -> None:
    """The unchanged-coordinate fast path borrows the actual typed buffer only for
this check. PyBuffer owns its exporter and ReadOnlyCell permits Python aliases;
no borrowed Rust slice of immutable i64 is invented over mutable storage.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _pddt_check_policies(policy: _PddtPolicies, length: int) -> None:
    """Execute the checked private native boundary for _pddt_check_policies.

    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param length: Prepared length input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _pddt_combine(date: _PddtParts, time: _PddtParts, policy: _PddtPolicies, local: object, size: int | None = None, unit: str | None = None, target: object | None = None, entry: str = 'Pddt.combine') -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_combine.

    :param date: Prepared date input; native validation and ownership rules apply.
    :param time: Prepared time input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param local: Prepared local input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_component(data: object, column: bool, length: int, entry: str, parameter: str, optional: bool = False, names: int = 0, low: int | None = None, high: int | None = None, buffer: bytes | None = None, kind: str | None = None, mask: bytes | None = None) -> _PddtIntegers:
    """Execute the checked private native boundary for _pddt_component.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param length: Prepared length input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :param optional: Prepared optional input; native validation and ownership rules apply.
    :param names: Prepared names input; native validation and ownership rules apply.
    :param low: Prepared low input; native validation and ownership rules apply.
    :param high: Prepared high input; native validation and ownership rules apply.
    :param buffer: Prepared buffer input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :returns: _PddtIntegers; errors preserve the native or external exception contract.
    """

def _pddt_data(data: object) -> _InputBytes:
    """Borrow only a proved native, contiguous span of an exact bytes root.
Every other source performs its actual old tobytes call here, at the same
evaluation point; read-only flags alone never establish immutability.

    :param data: Prepared data input; native validation and ownership rules apply.
    :returns: _InputBytes; errors preserve the native or external exception contract.
    """

def _pddt_date_buffer(data: bytes, policy: _PddtPolicies, kind: str, source: str, multiplier: int = 1, unit: str | None = None, source_zone: object | None = None, target: object | None = None, entry: str = 'Pddt', mask: bytes | None = None) -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_date_buffer.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param source: Prepared source input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param source_zone: Prepared source_zone input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_date_objects(data: object, policy: _PddtPolicies, kind: str, size: int | None = None, column: bool = False, unit: str | None = None, target: object | None = None, entry: str = 'Pddt') -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_date_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_dates(data: bytes, policy: _PddtPolicies, source: str, multiplier: int = 1, unit: str | None = None, source_zone: object | None = None, target: object | None = None, entry: str = 'Pddt', mask: bytes | None = None) -> tuple[bytes, _Unit, tzinfo | None]:
    """Decode a homogeneous owned date snapshot without creating scalar objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param source: Prepared source input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param source_zone: Prepared source_zone input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_diff(data: bytes, source_unit: str, aware: bool, target: object, column: bool, unit: str, absolute: bool, inclusive: str, buffer: bytes | None = None, storage: str | None = None, date_unit: str | None = None, multiplier: int = 1, target_zone: object | None = None, target_mask: bytes | None = None) -> tuple[bytes, bytes | None]:
    """Execute the checked private native boundary for _pddt_diff.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param source_unit: Prepared source_unit input; native validation and ownership rules apply.
    :param aware: Prepared aware input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param absolute: Prepared absolute input; native validation and ownership rules apply.
    :param inclusive: Prepared inclusive input; native validation and ownership rules apply.
    :param buffer: Prepared buffer input; native validation and ownership rules apply.
    :param storage: Prepared storage input; native validation and ownership rules apply.
    :param date_unit: Prepared date_unit input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :param target_zone: Prepared target_zone input; native validation and ownership rules apply.
    :param target_mask: Prepared target_mask input; native validation and ownership rules apply.
    :returns: tuple[bytes, bytes | None]; errors preserve the native or external exception contract.
    """

def _pddt_export(data: bytes, unit: str, zone: object | None, kind: int, entry: str, utc: bool = False) -> tuple[bytes, bytes | None]:
    """Execute the checked private native boundary for _pddt_export.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param utc: Prepared utc input; native validation and ownership rules apply.
    :returns: tuple[bytes, bytes | None]; errors preserve the native or external exception contract.
    """

def _pddt_frequency(kind: str, n: int, props: dict[str, object]) -> _RangeFrequency:
    """Execute the checked private native boundary for _pddt_frequency.

    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param n: Prepared n input; native validation and ownership rules apply.
    :param props: Prepared props input; native validation and ownership rules apply.
    :returns: _RangeFrequency; errors preserve the native or external exception contract.
    """

def _pddt_fsp(data: bytes, unit: str, zone: object | None, precision: int, entry: str) -> tuple[bytes, bool]:
    """Execute the checked private native boundary for _pddt_fsp.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param precision: Prepared precision input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, bool]; errors preserve the native or external exception contract.
    """

def _pddt_integers(data: object, column: bool, entry: str, parameter: str, buffer: bytes | None = None, kind: str | None = None, mask: bytes | None = None) -> _PddtIntegers:
    """Execute the checked private native boundary for _pddt_integers.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :param buffer: Prepared buffer input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :returns: _PddtIntegers; errors preserve the native or external exception contract.
    """

def _pddt_now(count: int, unit: str, zone: object | None, naive: bool) -> bytes:
    """Read one integer clock value after all parameters and empty-size are known.

    :param count: Prepared count input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param naive: Prepared naive input; native validation and ownership rules apply.
    :returns: bytes; errors preserve the native or external exception contract.
    """

def _pddt_number_buffer(data: bytes, storage: str, mask: bytes | None, policy: _PddtPolicies, kind: str, unit: str | None = None, target: object | None = None, local: object | None = None, entry: str = 'Pddt') -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_number_buffer.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param storage: Prepared storage input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param local: Prepared local input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_numbers(data: object, policy: _PddtPolicies, kind: str, size: int | None = None, column: bool = False, unit: str | None = None, target: object | None = None, local: object | None = None, entry: str = 'Pddt', parameter: str = 'data') -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_numbers.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param local: Prepared local input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_objects(data: bytes, unit: str, zone: object | None, kind: int, entry: str, cls: object | None = None, /, option: object | None = None, timespec: object | None = None) -> list[object]:
    """Execute the checked private native boundary for _pddt_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param cls: Final result constructor, called at the target boundary.
    :param option: Prepared option input; native validation and ownership rules apply.
    :param timespec: Prepared timespec input; native validation and ownership rules apply.
    :returns: list[object]; errors preserve the native or external exception contract.
    """

def _pddt_operand(data: object, column: bool, length: int, entry: str, subtract: bool = False, reflected: bool = False, buffer: bytes | None = None, storage: str | None = None, source: str | None = None, multiplier: int = 1, source_zone: object | None = None, mask: bytes | None = None) -> _PddtOperand | None:
    """Execute the checked private native boundary for _pddt_operand.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param length: Prepared length input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :param reflected: Prepared reflected input; native validation and ownership rules apply.
    :param buffer: Prepared buffer input; native validation and ownership rules apply.
    :param storage: Prepared storage input; native validation and ownership rules apply.
    :param source: Prepared source input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :param source_zone: Prepared source_zone input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :returns: _PddtOperand | None; errors preserve the native or external exception contract.
    """

def _pddt_parts(data: object, resolver: object, clock: bool, column: bool, entry: str, buffer: bytes | None = None, source: str | None = None, multiplier: int = 1, source_zone: object | None = None, time_buffer: bool = False, mask: bytes | None = None) -> _PddtParts:
    """Execute the checked private native boundary for _pddt_parts.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param resolver: Prepared resolver input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param buffer: Prepared buffer input; native validation and ownership rules apply.
    :param source: Prepared source input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :param source_zone: Prepared source_zone input; native validation and ownership rules apply.
    :param time_buffer: Prepared time_buffer input; native validation and ownership rules apply.
    :param mask: Prepared mask input; native validation and ownership rules apply.
    :returns: _PddtParts; errors preserve the native or external exception contract.
    """

def _pddt_period(data: bytes, unit: str, zone: object | None, token: str, mode: int, query: bool, entry: str) -> tuple[bytes, bool]:
    """Execute the checked private native boundary for _pddt_period.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param token: Prepared token input; native validation and ownership rules apply.
    :param mode: Prepared mode input; native validation and ownership rules apply.
    :param query: Prepared query input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, bool]; errors preserve the native or external exception contract.
    """

def _pddt_policies(ambiguous: object, nonexistent: object) -> _PddtPolicies:
    """Execute the checked private native boundary for _pddt_policies.

    :param ambiguous: Prepared ambiguous input; native validation and ownership rules apply.
    :param nonexistent: Prepared nonexistent input; native validation and ownership rules apply.
    :returns: _PddtPolicies; errors preserve the native or external exception contract.
    """

def _pddt_prepare(data: object, policy: _PddtPolicies, unit: str | None = None, base_unit: str | None = None, default: object | None = None, yearfirst: bool | None = None, dayfirst: bool | None = None, isoformat: bool = True, strict: bool = False, cfg: object | None = None, target: object | None = None, entry: str = 'Pddt') -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_prepare.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param base_unit: Prepared base_unit input; native validation and ownership rules apply.
    :param default: Prepared default input; native validation and ownership rules apply.
    :param yearfirst: Prepared yearfirst input; native validation and ownership rules apply.
    :param dayfirst: Prepared dayfirst input; native validation and ownership rules apply.
    :param isoformat: Prepared isoformat input; native validation and ownership rules apply.
    :param strict: Prepared strict input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_query(data: _InputBytes, unit: str, zone: object | None, query: int, entry: str, target: _PddtIntegers | None = None) -> tuple[bytes, bytes | None]:
    """Execute the checked private native boundary for _pddt_query.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param query: Prepared query input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: tuple[bytes, bytes | None]; errors preserve the native or external exception contract.
    """

def _pddt_range(start: object | None, end: object | None, periods: int | None, plan: _RangeFrequency | None, policy: _PddtPolicies, unit: str | None = None, target: object | None = None, inclusive: str = 'both', normalize: bool = False, default: object | None = None, yearfirst: bool | None = None, dayfirst: bool | None = None, isoformat: bool = True, strict: bool = False, cfg: object | None = None) -> tuple[bytes, _Unit, tzinfo | None, int, int]:
    """Execute the checked private native boundary for _pddt_range.

    :param start: Prepared start input; native validation and ownership rules apply.
    :param end: Prepared end input; native validation and ownership rules apply.
    :param periods: Prepared periods input; native validation and ownership rules apply.
    :param plan: Prepared plan input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param inclusive: Prepared inclusive input; native validation and ownership rules apply.
    :param normalize: Prepared normalize input; native validation and ownership rules apply.
    :param default: Prepared default input; native validation and ownership rules apply.
    :param yearfirst: Prepared yearfirst input; native validation and ownership rules apply.
    :param dayfirst: Prepared dayfirst input; native validation and ownership rules apply.
    :param isoformat: Prepared isoformat input; native validation and ownership rules apply.
    :param strict: Prepared strict input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None, int, int]; errors preserve the native or external exception contract.
    """

def _pddt_range_endpoints(start: object | None, end: object | None, policy: _PddtPolicies, unit: str | None = None, target: object | None = None, normalize: bool = False, default: object | None = None, yearfirst: bool | None = None, dayfirst: bool | None = None, isoformat: bool = True, strict: bool = False, cfg: object | None = None) -> _PddtRangeEndpoints:
    """Execute the checked private native boundary for _pddt_range_endpoints.

    :param start: Prepared start input; native validation and ownership rules apply.
    :param end: Prepared end input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param normalize: Prepared normalize input; native validation and ownership rules apply.
    :param default: Prepared default input; native validation and ownership rules apply.
    :param yearfirst: Prepared yearfirst input; native validation and ownership rules apply.
    :param dayfirst: Prepared dayfirst input; native validation and ownership rules apply.
    :param isoformat: Prepared isoformat input; native validation and ownership rules apply.
    :param strict: Prepared strict input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :returns: _PddtRangeEndpoints; errors preserve the native or external exception contract.
    """

def _pddt_range_external(inputs: _PddtRangeEndpoints, data: bytes, source: str, policy: _PddtPolicies, inclusive: str, unit: str | None = None, infer: bool = False) -> tuple[bytes, _Unit, tzinfo | None, int, int]:
    """Execute the checked private native boundary for _pddt_range_external.

    :param inputs: Prepared inputs input; native validation and ownership rules apply.
    :param data: Prepared data input; native validation and ownership rules apply.
    :param source: Prepared source input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param inclusive: Prepared inclusive input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param infer: Prepared infer input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None, int, int]; errors preserve the native or external exception contract.
    """

def _pddt_range_sequence(start: int | None, end: int | None, periods: int | None, plan: _RangeFrequency | None, policy: _PddtPolicies, unit: str | None = None, target: object | None = None, inclusive: str = 'both', known_start: int | None = None, known_end: int | None = None) -> tuple[bytes, _Unit, tzinfo | None, int, int]:
    """Execute the checked private native boundary for _pddt_range_sequence.

    :param start: Prepared start input; native validation and ownership rules apply.
    :param end: Prepared end input; native validation and ownership rules apply.
    :param periods: Prepared periods input; native validation and ownership rules apply.
    :param plan: Prepared plan input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param inclusive: Prepared inclusive input; native validation and ownership rules apply.
    :param known_start: Prepared known_start input; native validation and ownership rules apply.
    :param known_end: Prepared known_end input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None, int, int]; errors preserve the native or external exception contract.
    """

def _pddt_register(na: object, nat: object, resolver: object) -> None:
    """Execute the checked private native boundary for _pddt_register.

    :param na: Prepared na input; native validation and ownership rules apply.
    :param nat: Prepared nat input; native validation and ownership rules apply.
    :param resolver: Prepared resolver input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _pddt_rescale(data: _InputBytes, source_unit: str, target_unit: str, round_ok: bool, entry: str, multiplier: int = 1) -> bytes:
    """Change an immutable tick snapshot without Python scalars in the loop.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param source_unit: Prepared source_unit input; native validation and ownership rules apply.
    :param target_unit: Prepared target_unit input; native validation and ownership rules apply.
    :param round_ok: Prepared round_ok input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :returns: bytes; errors preserve the native or external exception contract.
    """

def _pddt_result_type(value: object, cls: type[object], /, base: type[object]) -> bool:
    """New date results require real ancestry, never a displayed class or ABC hook.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param cls: Final result constructor, called at the target boundary.
    :param base: Prepared base input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pddt_round(data: bytes, unit: str, zone: object | None, step: int, mode: int, entry: str) -> tuple[bytes, bool]:
    """Execute the checked private native boundary for _pddt_round.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param step: Prepared step input; native validation and ownership rules apply.
    :param mode: Prepared mode input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, bool]; errors preserve the native or external exception contract.
    """

def _pddt_snap(data: bytes, unit: str, zone: object | None, token: str, entry: str) -> tuple[bytes, bool]:
    """Execute the checked private native boundary for _pddt_snap.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param token: Prepared token input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, bool]; errors preserve the native or external exception contract.
    """

def _pddt_strftime(data: bytes, unit: str, zone: object, context: _StrftimeContext) -> list[str | None]:
    """Ordinary numeric fractional output shares the native plan. Every system
extension, dynamic zone and small/wide year retains mature pandas formatting.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param context: Prepared context input; native validation and ownership rules apply.
    :returns: list[str | None]; errors preserve the native or external exception contract.
    """

def _pddt_strings(data: object, policy: _PddtPolicies, unit: str | None = None, default: object | None = None, yearfirst: bool | None = None, dayfirst: bool | None = None, isoformat: bool = True, strict: bool = False, cfg: object | None = None, target: object | None = None, entry: str = 'Pddt') -> tuple[bytes, _Unit, tzinfo | None] | None:
    """Execute the checked private native boundary for _pddt_strings.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param default: Prepared default input; native validation and ownership rules apply.
    :param yearfirst: Prepared yearfirst input; native validation and ownership rules apply.
    :param dayfirst: Prepared dayfirst input; native validation and ownership rules apply.
    :param isoformat: Prepared isoformat input; native validation and ownership rules apply.
    :param strict: Prepared strict input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None] | None; errors preserve the native or external exception contract.
    """

def _pddt_strptime(data: object, format: _StrptimeFormat, policy: _PddtPolicies, cfg: object | None = None, size: int | None = None, column: bool = False, unit: str | None = None, entry: str = 'Pddt.strptime', target: object | None = None) -> tuple[bytes, _Unit, tzinfo | None]:
    """Execute the checked private native boundary for _pddt_strptime.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param format: Prepared format input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None]; errors preserve the native or external exception contract.
    """

def _pddt_transform(data: bytes, unit: str, zone: object | None, kind: str, components: list[_PddtIntegers], entry: str, policy: _PddtPolicies | None = None, target: object | None = None, replace_zone: bool = False) -> tuple[bytes, _Unit, tzinfo | None, bool]:
    """Execute the checked private native boundary for _pddt_transform.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param components: Prepared components input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param replace_zone: Prepared replace_zone input; native validation and ownership rules apply.
    :returns: tuple[bytes, _Unit, tzinfo | None, bool]; errors preserve the native or external exception contract.
    """

def _pddt_wall(data: bytes, unit: str, zone: object, entry: str) -> bytes:
    """Decode actual UTC instants to local fields; pure fixed offsets avoid carriers.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: bytes; errors preserve the native or external exception contract.
    """

def _pldt_available_zones() -> list[str]:
    """Execute the checked private native boundary for _pldt_available_zones.

    :returns: list[str]; errors preserve the native or external exception contract.
    """

def _pldt_binary(source: pl.Series, operand: _PldtOperand, target: type[_SeriesT], subtract: bool, entry: str, return_only: bool = False, carrier: object | None = None, reader: object | None = None) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_binary.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param operand: Prepared operand input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param return_only: Prepared return_only input; native validation and ownership rules apply.
    :param carrier: Prepared carrier input; native validation and ownership rules apply.
    :param reader: Prepared reader input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_calendar(sources: list[pl.Series], scalars: list[bool], target: type[_SeriesT], kind: str, unit: str, tz: _PldtZoneContext | None, policy: _PldtPolicyContext, size: int | None = None) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_calendar.

    :param sources: Prepared sources input; native validation and ownership rules apply.
    :param scalars: Prepared scalars input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_check_numpy(source: pl.Series, target: pl.Series, numpy: tuple[int, int] | None) -> None:
    """Validate an explicitly requested NumPy dtype against real source values.
Native dtype conversion has already run; this does not replace its protocol.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param numpy: Prepared numpy input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _pldt_check_temporal(source: pl.Series, target: pl.Series, allow: bool | np.bool_) -> None:
    """Validate actual Arrow/pandas temporal metadata and its independent validity.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param allow: Prepared allow input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _pldt_combine(date: _PldtParts, time: _PldtParts, target: type[_SeriesT], local: object, size: int | None, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext, name: str) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_combine.

    :param date: Prepared date input; native validation and ownership rules apply.
    :param time: Prepared time input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param local: Prepared local input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_component_column(source: pl.Series, role: tuple[bool, int, int | None, int | None], entry: str, parameter: str) -> pl.Series:
    """Execute the checked private native boundary for _pldt_component_column.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param role: Prepared role input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :returns: pl.Series; errors preserve the native or external exception contract.
    """

def _pldt_component_objects(data: object, column: bool, role: tuple[bool, int, int | None, int | None], entry: str, parameter: str) -> tuple[pl.Series, bool]:
    """Execute the checked private native boundary for _pldt_component_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param role: Prepared role input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :returns: tuple[pl.Series, bool]; errors preserve the native or external exception contract.
    """

def _pldt_copy_core(source: pl.Series, deep: bool | np.bool_, sorted: int, target: type[_SeriesT]) -> tuple[_SeriesT, int]:
    """Execute the checked private native boundary for _pldt_copy_core.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param deep: Prepared deep input; native validation and ownership rules apply.
    :param sorted: Prepared sorted input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: tuple[_SeriesT, int]; errors preserve the native or external exception contract.
    """

def _pldt_core(source: pl.Series, sorted: int) -> tuple[bytes, bytes, _PolarsUnit, str | None, str, int]:
    """Execute the checked private native boundary for _pldt_core.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param sorted: Prepared sorted input; native validation and ownership rules apply.
    :returns: tuple[bytes, bytes, _PolarsUnit, str | None, str, int]; errors preserve the native or external exception contract.
    """

def _pldt_date_buffer(source: pl.Series, target: type[_SeriesT], kind: str, code: int, source_zone: _PldtZoneContext | None, offset_us: int | None, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext) -> _SeriesT:
    """A pandas datetime buffer is an instant/sentinel source, not a Polars dtype.
Transform local fields in i128 before choosing the final output capacity.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param code: Prepared code input; native validation and ownership rules apply.
    :param source_zone: Prepared source_zone input; native validation and ownership rules apply.
    :param offset_us: Prepared offset_us input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_date_column(source: pl.Series, target: type[_SeriesT], kind: str, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_date_column.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_date_objects(data: object, target: type[_SeriesT], kind: str, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext, size: int | None = None, name: str = '', column: bool = False) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_date_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_diff(source: pl.Series, target: pl.Series, unit: str, absolute: bool, inclusive: str, scalar: bool, storage: int, numpy: tuple[int, int] | None, aware: bool) -> pl.Series:
    """Execute the checked private native boundary for _pldt_diff.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param absolute: Prepared absolute input; native validation and ownership rules apply.
    :param inclusive: Prepared inclusive input; native validation and ownership rules apply.
    :param scalar: Prepared scalar input; native validation and ownership rules apply.
    :param storage: Prepared storage input; native validation and ownership rules apply.
    :param numpy: Prepared numpy input; native validation and ownership rules apply.
    :param aware: Prepared aware input; native validation and ownership rules apply.
    :returns: pl.Series; errors preserve the native or external exception contract.
    """

def _pldt_diff_objects(value: object, column: bool, count: int | None = None) -> tuple[pl.Series, bool]:
    """Execute the checked private native boundary for _pldt_diff_objects.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param count: Prepared count input; native validation and ownership rules apply.
    :returns: tuple[pl.Series, bool]; errors preserve the native or external exception contract.
    """

def _pldt_format_objects(data: object, target: type[_SeriesT], format: _StrptimeFormat, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext, cfg: object | None = None, size: int | None = None, name: str = '') -> _SeriesT:
    """Mixed Python text keeps real str-subclass/iterator protocols at one boundary.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param format: Prepared format input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_frequency(value: object) -> _RangeFrequency | None:
    """Execute the checked private native boundary for _pldt_frequency.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: _RangeFrequency | None; errors preserve the native or external exception contract.
    """

def _pldt_integer_column(source: pl.Series) -> pl.Series:
    """Execute the checked private native boundary for _pldt_integer_column.

    :param source: Prepared source input; native validation and ownership rules apply.
    :returns: pl.Series; errors preserve the native or external exception contract.
    """

def _pldt_integer_objects(data: object, column: bool, entry: str, parameter: str) -> tuple[pl.Series, bool]:
    """Execute the checked private native boundary for _pldt_integer_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param parameter: Prepared parameter input; native validation and ownership rules apply.
    :returns: tuple[pl.Series, bool]; errors preserve the native or external exception contract.
    """

def _pldt_iso_column(source: pl.Series, target: type[_SeriesT], unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_iso_column.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_iso_objects(data: object, target: type[_SeriesT], unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext, size: int | None, name: str, column: bool) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_iso_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_named_zone_context(key: str) -> _PldtZoneContext:
    """Execute the checked private native boundary for _pldt_named_zone_context.

    :param key: Prepared key input; native validation and ownership rules apply.
    :returns: _PldtZoneContext; errors preserve the native or external exception contract.
    """

def _pldt_nat_collision(source: pl.Series) -> int | None:
    """Execute the checked private native boundary for _pldt_nat_collision.

    :param source: Prepared source input; native validation and ownership rules apply.
    :returns: int | None; errors preserve the native or external exception contract.
    """

def _pldt_native(source: pl.Series, target: type[_SeriesT], unit: str | None = None, copy: bool | np.bool_ = ..., round_ok: bool | np.bool_ = ..., numpy_date: tuple[int, int] | None = None, numpy_zone: str | None = None, tz: _PldtZoneContext | None = None, policy: _PldtPolicyContext | None = None) -> _SeriesT:
    """Read known native dtype and metadata once, without Python scalar dates.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param copy: Prepared copy input; native validation and ownership rules apply.
    :param round_ok: Prepared round_ok input; native validation and ownership rules apply.
    :param numpy_date: Prepared numpy_date input; native validation and ownership rules apply.
    :param numpy_zone: Prepared numpy_zone input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_now(target: type[_SeriesT], count: int, unit: str, name: str, zone: _PldtZoneContext | None, naive: bool) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_now.

    :param target: Prepared target input; native validation and ownership rules apply.
    :param count: Prepared count input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param naive: Prepared naive input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_number_column(source: pl.Series, target: type[_SeriesT], kind: str, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext, local: object | None = None) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_number_column.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param local: Prepared local input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_number_objects(data: object, target: type[_SeriesT], kind: str, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext, size: int | None = None, name: str = '', local: object | None = None, column: bool = False) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_number_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param size: Prepared size input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :param local: Prepared local input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_objects(data: object, target: type[_SeriesT], unit: str | None = None, base_unit: str | None = None, name: str = '', default: object | None = None, yearfirst: bool | np.bool_ | None = None, dayfirst: bool | np.bool_ | None = None, isoformat: bool | np.bool_ = ..., strict: bool | np.bool_ = ..., cfg: object | None = None, tz: _PldtZoneContext | None = None, policy: _PldtPolicyContext | None = None) -> _SeriesT:
    """Once-prepared object protocol path. Native String columns use W13's worker.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param base_unit: Prepared base_unit input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :param default: Prepared default input; native validation and ownership rules apply.
    :param yearfirst: Prepared yearfirst input; native validation and ownership rules apply.
    :param dayfirst: Prepared dayfirst input; native validation and ownership rules apply.
    :param isoformat: Prepared isoformat input; native validation and ownership rules apply.
    :param strict: Prepared strict input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_operand_column(source: pl.Series) -> _PldtOperand:
    """Execute the checked private native boundary for _pldt_operand_column.

    :param source: Prepared source input; native validation and ownership rules apply.
    :returns: _PldtOperand; errors preserve the native or external exception contract.
    """

def _pldt_operand_objects(data: object, column: bool, subtract: bool, reflected: bool, named: bool, entry: str) -> _PldtOperand | None:
    """Execute the checked private native boundary for _pldt_operand_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :param reflected: Prepared reflected input; native validation and ownership rules apply.
    :param named: Prepared named input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: _PldtOperand | None; errors preserve the native or external exception contract.
    """

def _pldt_operand_ticks(source: pl.Series, storage: str, code: int, multiplier: int, aware: bool, sentinel: bool) -> _PldtOperand:
    """Execute the checked private native boundary for _pldt_operand_ticks.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param storage: Prepared storage input; native validation and ownership rules apply.
    :param code: Prepared code input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :param aware: Prepared aware input; native validation and ownership rules apply.
    :param sentinel: Prepared sentinel input; native validation and ownership rules apply.
    :returns: _PldtOperand; errors preserve the native or external exception contract.
    """

def _pldt_output(source: pl.Series, context: _PldtOutputContext, target: type[_SeriesT]) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_output.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param context: Prepared context input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_output_prepare(code: int, utc: bool | np.bool_, sep: object, timespec: object, locale: object | None, entry: str) -> _PldtOutputContext:
    """Execute the checked private native boundary for _pldt_output_prepare.

    :param code: Prepared code input; native validation and ownership rules apply.
    :param utc: Prepared utc input; native validation and ownership rules apply.
    :param sep: Prepared sep input; native validation and ownership rules apply.
    :param timespec: Prepared timespec input; native validation and ownership rules apply.
    :param locale: Prepared locale input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: _PldtOutputContext; errors preserve the native or external exception contract.
    """

def _pldt_parts_buffer(source: pl.Series, clock: bool, code: int, multiplier: int, source_zone: _PldtZoneContext | None, offset_us: int | None, keep_zone: bool) -> _PldtParts:
    """Execute the checked private native boundary for _pldt_parts_buffer.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :param code: Prepared code input; native validation and ownership rules apply.
    :param multiplier: Prepared multiplier input; native validation and ownership rules apply.
    :param source_zone: Prepared source_zone input; native validation and ownership rules apply.
    :param offset_us: Prepared offset_us input; native validation and ownership rules apply.
    :param keep_zone: Prepared keep_zone input; native validation and ownership rules apply.
    :returns: _PldtParts; errors preserve the native or external exception contract.
    """

def _pldt_parts_column(source: pl.Series, clock: bool, keep_zone: bool) -> _PldtParts:
    """Execute the checked private native boundary for _pldt_parts_column.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :param keep_zone: Prepared keep_zone input; native validation and ownership rules apply.
    :returns: _PldtParts; errors preserve the native or external exception contract.
    """

def _pldt_parts_objects(data: object, resolver: object, clock: bool, column: bool, keep_zone: bool) -> _PldtParts:
    """Execute the checked private native boundary for _pldt_parts_objects.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param resolver: Prepared resolver input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :param column: Prepared column input; native validation and ownership rules apply.
    :param keep_zone: Prepared keep_zone input; native validation and ownership rules apply.
    :returns: _PldtParts; errors preserve the native or external exception contract.
    """

def _pldt_parts_time(physical: pl.Series) -> _PldtParts:
    """Execute the checked private native boundary for _pldt_parts_time.

    :param physical: Prepared physical input; native validation and ownership rules apply.
    :returns: _PldtParts; errors preserve the native or external exception contract.
    """

def _pldt_period(source: pl.Series, context: _PldtPeriodContext, target: type[_SeriesT]) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_period.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param context: Prepared context input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_period_prepare(kind: str, token: str | None, value: int, mode: int, query: bool, entry: str) -> _PldtPeriodContext:
    """Execute the checked private native boundary for _pldt_period_prepare.

    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param token: Prepared token input; native validation and ownership rules apply.
    :param value: Prepared value input; native validation and ownership rules apply.
    :param mode: Prepared mode input; native validation and ownership rules apply.
    :param query: Prepared query input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :returns: _PldtPeriodContext; errors preserve the native or external exception contract.
    """

def _pldt_policies(ambiguous: object, nonexistent: object, expression_mask: bool | np.bool_ = ...) -> _PldtPolicyContext:
    """Execute the checked private native boundary for _pldt_policies.

    :param ambiguous: Prepared ambiguous input; native validation and ownership rules apply.
    :param nonexistent: Prepared nonexistent input; native validation and ownership rules apply.
    :param expression_mask: Prepared expression_mask input; native validation and ownership rules apply.
    :returns: _PldtPolicyContext; errors preserve the native or external exception contract.
    """

def _pldt_prepare_format(format: _StrptimeFormat, cfg: object | None = None) -> _PldtFormatContext:
    """Execute the checked private native boundary for _pldt_prepare_format.

    :param format: Prepared format input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :returns: _PldtFormatContext; errors preserve the native or external exception contract.
    """

def _pldt_prepare_text(*, cfg: object | None = None, default: object | None = None, yearfirst: bool | np.bool_ | None = None, dayfirst: bool | np.bool_ | None = None, isoformat: bool | np.bool_ = ..., strict: bool | np.bool_ = ..., expression: bool | np.bool_ = ...) -> _PldtTextContext:
    """Expressions freeze cfg first, then resolve the independent default against
that snapshot. Immediate native-string callers resolve real default callbacks
first and snapshot the resulting live cfg, preserving the eager contract.

    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :param default: Prepared default input; native validation and ownership rules apply.
    :param yearfirst: Prepared yearfirst input; native validation and ownership rules apply.
    :param dayfirst: Prepared dayfirst input; native validation and ownership rules apply.
    :param isoformat: Prepared isoformat input; native validation and ownership rules apply.
    :param strict: Prepared strict input; native validation and ownership rules apply.
    :param expression: Prepared expression input; native validation and ownership rules apply.
    :returns: _PldtTextContext; errors preserve the native or external exception contract.
    """

def _pldt_python_output(source: pl.Series, cls: object, /, zone: object, clock: bool) -> list[object]:
    """Explicit host-only outputs. Dynamic timezone carriers preserve the actual
UTC instant against the host's timezone database; workers never use them.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param cls: Final result constructor, called at the target boundary.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :returns: list[object]; errors preserve the native or external exception contract.
    """

def _pldt_query(source: pl.Series, code: int, entry: str, target: pl.Series | None = None, scalar: bool = False, reference: tuple[int, int] | None = None) -> pl.Series:
    """Execute the checked private native boundary for _pldt_query.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param code: Prepared code input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param scalar: Prepared scalar input; native validation and ownership rules apply.
    :param reference: Prepared reference input; native validation and ownership rules apply.
    :returns: pl.Series; errors preserve the native or external exception contract.
    """

def _pldt_query_clock() -> tuple[int, int]:
    """Execute the checked private native boundary for _pldt_query_clock.

    :returns: tuple[int, int]; errors preserve the native or external exception contract.
    """

def _pldt_range(target: type[_SeriesT], inputs: _PldtRangeEndpoints, periods: int | None, plan: _RangeFrequency | None, policy: _PldtPolicyContext, closed: str, name: str) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_range.

    :param target: Prepared target input; native validation and ownership rules apply.
    :param inputs: Prepared inputs input; native validation and ownership rules apply.
    :param periods: Prepared periods input; native validation and ownership rules apply.
    :param plan: Prepared plan input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param closed: Prepared closed input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_range_endpoints(start: object | None, end: object | None, policy: _PldtPolicyContext, plan: _RangeFrequency | None, unit: str | None, tz: _PldtZoneContext | None, normalize: bool, default: object | None, yearfirst: bool | None, dayfirst: bool | None, isoformat: bool, strict: bool, cfg: object | None, calendar: bool = False) -> _PldtRangeEndpoints:
    """Execute the checked private native boundary for _pldt_range_endpoints.

    :param start: Prepared start input; native validation and ownership rules apply.
    :param end: Prepared end input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param plan: Prepared plan input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param normalize: Prepared normalize input; native validation and ownership rules apply.
    :param default: Prepared default input; native validation and ownership rules apply.
    :param yearfirst: Prepared yearfirst input; native validation and ownership rules apply.
    :param dayfirst: Prepared dayfirst input; native validation and ownership rules apply.
    :param isoformat: Prepared isoformat input; native validation and ownership rules apply.
    :param strict: Prepared strict input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :param calendar: Prepared calendar input; native validation and ownership rules apply.
    :returns: _PldtRangeEndpoints; errors preserve the native or external exception contract.
    """

def _pldt_range_external(target: type[_SeriesT], inputs: _PldtRangeEndpoints, source: pl.Series, source_unit: str, policy: _PldtPolicyContext, closed: str, unit: str | None, infer: bool, name: str) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_range_external.

    :param target: Prepared target input; native validation and ownership rules apply.
    :param inputs: Prepared inputs input; native validation and ownership rules apply.
    :param source: Prepared source input; native validation and ownership rules apply.
    :param source_unit: Prepared source_unit input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param closed: Prepared closed input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param infer: Prepared infer input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_register_missing(na: object, nat: object) -> None:
    """Execute the checked private native boundary for _pldt_register_missing.

    :param na: Prepared na input; native validation and ownership rules apply.
    :param nat: Prepared nat input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _pldt_restore_core(data: bytes, validity: bytes, unit: str, zone: str | None, name: str, sorted: int, target: type[_SeriesT]) -> tuple[_SeriesT, int]:
    """Execute the checked private native boundary for _pldt_restore_core.

    :param data: Prepared data input; native validation and ownership rules apply.
    :param validity: Prepared validity input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param name: Prepared name input; native validation and ownership rules apply.
    :param sorted: Prepared sorted input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: tuple[_SeriesT, int]; errors preserve the native or external exception contract.
    """

def _pldt_scalar_callback(operand: _PldtOperand, source: object) -> object:
    """Execute the checked private native boundary for _pldt_scalar_callback.

    :param operand: Prepared operand input; native validation and ownership rules apply.
    :param source: Prepared source input; native validation and ownership rules apply.
    :returns: object; errors preserve the native or external exception contract.
    """

def _pldt_snapshot(source: pl.Series, target: type[_SeriesT]) -> _SeriesT:
    """Official SDK handle export avoids an unrelated business clone/new callback.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_strftime(source: pl.Series, context: _StrftimeContext, zone: object, target: type[_SeriesT]) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_strftime.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param context: Prepared context input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_text(source: pl.Series, target: type[_SeriesT], prepared: _PldtTextContext | None, format: _PldtFormatContext | None, unit: str | None, tz: _PldtZoneContext | None, policy: _PldtPolicyContext) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_text.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param prepared: Prepared prepared input; native validation and ownership rules apply.
    :param format: Prepared format input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_text_needed(source: pl.Series) -> bool:
    """Execute the checked private native boundary for _pldt_text_needed.

    :param source: Prepared source input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pldt_timezone(source: pl.Series, target_type: type[_SeriesT], operation: str, target: _PldtZoneContext | None, base: _PldtZoneContext | None, policy: _PldtPolicyContext, naive: bool) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_timezone.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param target_type: Final result constructor, called at the target boundary.
    :param operation: Prepared operation input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param base: Prepared base input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param naive: Prepared naive input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_transform(source: pl.Series, components: list[pl.Series], scalars: list[bool], target: type[_SeriesT], kind: str, entry: str, tz: _PldtZoneContext | None, replace_zone: bool, policy: _PldtPolicyContext | None) -> _SeriesT:
    """Execute the checked private native boundary for _pldt_transform.

    :param source: Prepared source input; native validation and ownership rules apply.
    :param components: Prepared components input; native validation and ownership rules apply.
    :param scalars: Prepared scalars input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param entry: Prepared entry input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param replace_zone: Prepared replace_zone input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :returns: _SeriesT; errors preserve the native or external exception contract.
    """

def _pldt_tzdb_info() -> tuple[str, str, int]:
    """Execute the checked private native boundary for _pldt_tzdb_info.

    :returns: tuple[str, str, int]; errors preserve the native or external exception contract.
    """

def _pldt_zone_context(key: str, data: bytes, fixed_seconds: int | None) -> _PldtZoneContext:
    """Execute the checked private native boundary for _pldt_zone_context.

    :param key: Prepared key input; native validation and ownership rules apply.
    :param data: Prepared data input; native validation and ownership rules apply.
    :param fixed_seconds: Prepared fixed_seconds input; native validation and ownership rules apply.
    :returns: _PldtZoneContext; errors preserve the native or external exception contract.
    """

def _pldt_zone_probe(walls: list[int | None], zone: _PldtZoneContext, policy: _PldtPolicyContext, unit: str) -> list[int | None]:
    """Minimal private candidate proof path; public column wiring shares this data.

    :param walls: Prepared walls input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param policy: Prepared policy input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :returns: list[int | None]; errors preserve the native or external exception contract.
    """

def _pydt_add(value: _DateT, subtract: bool, years: SupportsIndex, quarters: SupportsIndex, months: SupportsIndex, weeks: SupportsIndex, days: SupportsIndex, hours: SupportsIndex, minutes: SupportsIndex, seconds: SupportsIndex, milliseconds: SupportsIndex, microseconds: SupportsIndex) -> _DateT:
    """Normalize relative integers before sharing Delta's checked calendar algorithm.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :param years: Prepared years input; native validation and ownership rules apply.
    :param quarters: Prepared quarters input; native validation and ownership rules apply.
    :param months: Prepared months input; native validation and ownership rules apply.
    :param weeks: Prepared weeks input; native validation and ownership rules apply.
    :param days: Prepared days input; native validation and ownership rules apply.
    :param hours: Prepared hours input; native validation and ownership rules apply.
    :param minutes: Prepared minutes input; native validation and ownership rules apply.
    :param seconds: Prepared seconds input; native validation and ownership rules apply.
    :param milliseconds: Prepared milliseconds input; native validation and ownership rules apply.
    :param microseconds: Prepared microseconds input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_adjust(value: _DateT, year: SupportsIndex | None = None, month: SupportsIndex | None = None, day: SupportsIndex | None = None, hour: SupportsIndex | None = None, minute: SupportsIndex | None = None, second: SupportsIndex | None = None, microsecond: SupportsIndex | None = None) -> _DateT:
    """Set optional fields and clamp only a valid requested day to the target month.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param year: Prepared year input; native validation and ownership rules apply.
    :param month: Prepared month input; native validation and ownership rules apply.
    :param day: Prepared day input; native validation and ownership rules apply.
    :param hour: Prepared hour input; native validation and ownership rules apply.
    :param minute: Prepared minute input; native validation and ownership rules apply.
    :param second: Prepared second input; native validation and ownership rules apply.
    :param microsecond: Prepared microsecond input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_binary(value: datetime, operand: object, subtract: bool) -> object:
    """Dispatch public Pydt arithmetic by real types in the existing native call.

# Errors
Preserves arithmetic and callback errors; unsupported operands negotiate via
NotImplemented instead of trusting an object's displayed __class__.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param operand: Prepared operand input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :returns: object; errors preserve the native or external exception contract.
    """

def _pydt_boundary(value: _DateT, unit: str, end: bool, clock: bool) -> _DateT:
    """Build the same native period definition used by the boundary predicates.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param end: Prepared end input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_calendar(value: datetime, query: int) -> int:
    """Read calendar facts from the same Gregorian helpers used by Delta and Parser.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param query: Prepared query input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_calendar_date(value: date) -> list[int]:
    """Supply actual date fields to the Python child combine path; never construct a date.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: list[int]; errors preserve the native or external exception contract.
    """

def _pydt_carrier(value: datetime) -> datetime:
    """Create a builtin carrier directly; never invoke a public child constructor.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: datetime; errors preserve the native or external exception contract.
    """

def _pydt_clock(value: datetime) -> time:
    """Extract a real datetime's clock only after rejecting a missing pandas value.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: time; errors preserve the native or external exception contract.
    """

def _pydt_combine(cls: type[_DateT], /, date: date, time: object, zone: object | None = None, preserve_instant: bool = False) -> _DateT | None:
    """Combine stored date and clock fields after the wrapper resolves the timezone.

    :param cls: Final result constructor, called at the target boundary.
    :param date: Prepared date input; native validation and ownership rules apply.
    :param time: Prepared time input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param preserve_instant: Prepared preserve_instant input; native validation and ownership rules apply.
    :returns: _DateT | None; errors preserve the native or external exception contract.
    """

def _pydt_compare_now(value: datetime, clock: object, future: bool) -> bool:
    """Compare with one clock reading, keeping ordinary timezone rules in native code.
Dynamic offsets are read once; queries never require their fromutc protocol.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :param future: Prepared future input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_convert(value: _DateT, target: object, offset: object | None = None, strip_timezone: bool = False, astimezone: bool = False, output_class: type[_DateT] | None = None) -> _DateT | None:
    """Convert Pydt values with standard timezones, keeping UTC work raw.
Children retain their public constructor; dynamic timezone protocols keep
the Python carrier path used by datetime.astimezone.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :param offset: Prepared offset input; native validation and ownership rules apply.
    :param strip_timezone: Prepared strip_timezone input; native validation and ownership rules apply.
    :param astimezone: Prepared astimezone input; native validation and ownership rules apply.
    :param output_class: Prepared output_class input; native validation and ownership rules apply.
    :returns: _DateT | None; errors preserve the native or external exception contract.
    """

def _pydt_copy_date(cls: type[_DateT], /, value: date, tz: object) -> _DateT:
    """Copy a date's stored fields at midnight, retaining child constructor hooks.

    :param cls: Final result constructor, called at the target boundary.
    :param value: Prepared value input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_copy_datetime(cls: type[_DateT], /, value: datetime, tz: object | None = None, preserve_instant: bool = False) -> _DateT:
    """Copy stored datetime fields without creating seven Python integers first.

    :param cls: Final result constructor, called at the target boundary.
    :param value: Prepared value input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :param preserve_instant: Prepared preserve_instant input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_copy_fold(value: datetime, zone: object) -> int:
    """Supply the same copied-fold rule to the Python child combine boundary.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_create(cls: type[_DateT], /, year: object, month: object, day: object, hour: object, minute: object, second: object, microsecond: object, zone: object, fold: object) -> _DateT:
    """Prepare public integer fields once; subclasses retain datetime's allocator.

    :param cls: Final result constructor, called at the target boundary.
    :param year: Prepared year input; native validation and ownership rules apply.
    :param month: Prepared month input; native validation and ownership rules apply.
    :param day: Prepared day input; native validation and ownership rules apply.
    :param hour: Prepared hour input; native validation and ownership rules apply.
    :param minute: Prepared minute input; native validation and ownership rules apply.
    :param second: Prepared second input; native validation and ownership rules apply.
    :param microsecond: Prepared microsecond input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param fold: Prepared fold input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_datetime_sub(left: datetime, right: datetime) -> timedelta:
    """Subtract datetimes without narrowing a Timestamp to its base-class carrier.

    :param left: Prepared left input; native validation and ownership rules apply.
    :param right: Prepared right input; native validation and ownership rules apply.
    :returns: timedelta; errors preserve the native or external exception contract.
    """

def _pydt_day_of_year(value: object) -> int:
    """Read the year position directly for the readonly Python property.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_days_in_month(value: object) -> int:
    """Read month capacity without a Python property function frame.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_diff(value: datetime, other: datetime, unit: str, absolute: bool, inclusive: str) -> int:
    """Apply the frozen boundary-count inclusive rule without datetime subtraction.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param other: Prepared other input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param absolute: Prepared absolute input; native validation and ownership rules apply.
    :param inclusive: Prepared inclusive input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_dst(value: datetime) -> timedelta | None:
    """Return the same legal duration after checking its actual value once.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: timedelta | None; errors preserve the native or external exception contract.
    """

def _pydt_flag(value: datetime, query: int) -> bool:
    """Return calendar predicates directly without an intermediate Python integer.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param query: Prepared query input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_from_calendar(original: _DateT, target: datetime) -> _DateT:
    """Finish an external calendar computation without reparsing its native fields.

    :param original: Prepared original input; native validation and ownership rules apply.
    :param target: Prepared target input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_doy(cls: type[_DateT], /, year: SupportsIndex, doy: SupportsIndex, tz: object) -> _DateT:
    """Clamp a day-of-year only after validating the requested calendar year.

    :param cls: Final result constructor, called at the target boundary.
    :param year: Prepared year input; native validation and ownership rules apply.
    :param doy: Prepared doy input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_instant(value: _DateT) -> _DateT:
    """Copy the result of a standard instant factory without wall-time repair.
The Python wrapper selects only the exact base Pydt and standard factory
sources; user subclasses and custom timezone protocols retain their hooks.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_iso(cls: type[_DateT], /, year: SupportsIndex, week: SupportsIndex, weekday: SupportsIndex, tz: object) -> _DateT:
    """Select the final ISO week/day for high convenience inputs; reject low values.

    :param cls: Final result constructor, called at the target boundary.
    :param year: Prepared year input; native validation and ownership rules apply.
    :param week: Prepared week input; native validation and ownership rules apply.
    :param weekday: Prepared weekday input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_numpy(cls: type[_DateT], /, value: object) -> _DateT:
    """Reuse NumPy's checked scalar decoder and Parser's established constructor shape.

    :param cls: Final result constructor, called at the target boundary.
    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_numpy_zoned(cls: type[_DateT], /, value: object, tz: object) -> _DateT:
    """Apply an explicit timezone without adding arguments to the ordinary NumPy entry.

    :param cls: Final result constructor, called at the target boundary.
    :param value: Prepared value input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_ordinal(cls: type[_DateT], /, ordinal: SupportsIndex, tz: object) -> _DateT:
    """Create midnight from an ordinal, keeping the original integer conversion.

    :param cls: Final result constructor, called at the target boundary.
    :param ordinal: Prepared ordinal input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_seconds(cls: type[_DateT], /, value: object, tz: object) -> _DateT:
    """Build ordinary numeric factories directly; child classes keep the parser route.

    :param cls: Final result constructor, called at the target boundary.
    :param value: Prepared value input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_from_us(cls: type[_DateT], /, us: SupportsIndex, tz: object) -> _DateT:
    """Create an epoch-wall-clock value without floating point or a Python timedelta.

    :param cls: Final result constructor, called at the target boundary.
    :param us: Prepared us input; native validation and ownership rules apply.
    :param tz: Prepared tz input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_fsp(value: _DateT, precision: SupportsIndex) -> _DateT:
    """Trim fractional second digits directly, retaining date/timezone/fold.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param precision: Prepared precision input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_is_boundary(value: datetime, unit: str, end: bool, clock: bool) -> bool:
    """Inspect native fields directly; regional boundaries additionally confirm validity.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param end: Prepared end input; native validation and ownership rules apply.
    :param clock: Prepared clock input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_is_dst(value: datetime) -> bool:
    """Ignore user-defined truthiness of timedelta subclasses.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_is_leap_year(value: object) -> bool:
    """Read leap status without a Python property function frame.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_is_local(value: datetime, local: object) -> bool:
    """Only resolve the local zone when a stored timezone can actually match it.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param local: Prepared local input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_is_utc(value: datetime) -> bool:
    """Compare the stored zone directly with the standard UTC singleton.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_iso(value: datetime, year_field: bool) -> int:
    """Read one ISO calendar field without allocating the complete Python result.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param year_field: Prepared year_field input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_leaps(value: datetime, year: SupportsIndex) -> int:
    """Count Gregorian leap years in the half-open interval between two years.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param year: Prepared year input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_lookup(token: object, weekday: bool) -> int:
    """Query immutable default month/weekday vocabulary, without Python Configs.

    :param token: Prepared token input; native validation and ownership rules apply.
    :param weekday: Prepared weekday input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_lookup_optional(token: str, weekday: bool) -> int | None:
    """Let an internal caller try a name without using exceptions as control flow.

    :param token: Prepared token input; native validation and ownership rules apply.
    :param weekday: Prepared weekday input; native validation and ownership rules apply.
    :returns: int | None; errors preserve the native or external exception contract.
    """

def _pydt_matches(value: datetime, query: int, expected: SupportsIndex) -> bool:
    """Test integer calendar fields with the frozen convenience conversion.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param query: Prepared query input; native validation and ownership rules apply.
    :param expected: Prepared expected input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_millisecond(value: datetime) -> int:
    """Read and divide the stored microseconds in one native call.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _pydt_move(value: _DateT, kind: int, offset: SupportsIndex, selection: object | None = None, day: SupportsIndex | None = None) -> _DateT:
    """Apply a year, quarter, month, week or day movement in one native operation.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param kind: Prepared kind input; native validation and ownership rules apply.
    :param offset: Prepared offset input; native validation and ownership rules apply.
    :param selection: Prepared selection input; native validation and ownership rules apply.
    :param day: Prepared day input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_name_matches(value: datetime, token: object, weekday: bool) -> bool:
    """Match a real Unicode name or integer selector against stored calendar fields.
Native dispatch avoids a second Python type test; fake displayed classes
never authorize name handling or change the existing integer protocol.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param token: Prepared token input; native validation and ownership rules apply.
    :param weekday: Prepared weekday input; native validation and ownership rules apply.
    :returns: bool; errors preserve the native or external exception contract.
    """

def _pydt_normalize(value: _DateT) -> _DateT:
    """Apply the local-time policy to an explicitly localized convenience value.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_numpy(value: datetime, operand: object, subtract: bool) -> object:
    """Adapt NumPy operands through the same checked native decoder as Delta/Parser.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param operand: Prepared operand input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :returns: object; errors preserve the native or external exception contract.
    """

def _pydt_offset_seconds(value: datetime) -> int | None:
    """Read a validated complete offset before flooring to whole seconds.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: int | None; errors preserve the native or external exception contract.
    """

def _pydt_reduce(value: datetime, restore: object, check_reduce: bool) -> str | tuple[object, ...]:
    """Build one date-first recipe using live definitions and normal user callbacks.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param restore: Prepared restore input; native validation and ownership rules apply.
    :param check_reduce: Prepared check_reduce input; native validation and ownership rules apply.
    :returns: str | tuple[object, ...]; errors preserve the native or external exception contract.
    """

def _pydt_register(cls: type[object], /, resolve_timezone: object) -> None:
    """Register the ordinary Python subclass; no PyO3 object tail is allocated.

    :param cls: Final result constructor, called at the target boundary.
    :param resolve_timezone: Prepared resolve_timezone input; native validation and ownership rules apply.
    :returns: None; errors preserve the native or external exception contract.
    """

def _pydt_replace(value: _DateT, supplied: tuple[object, ...], zone: object, fold: object, unset: object) -> _DateT:
    """Replace base Pydt fields in one native entry, sharing the stored field snapshot.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param supplied: Prepared supplied input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param fold: Prepared fold input; native validation and ownership rules apply.
    :param unset: Prepared unset input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_replace_general(value: _DateT, supplied: tuple[object, ...], zone: object, fold: object, unset: object, resolve_timezone: object) -> _DateT:
    """Prepare replacement fields natively while preserving dynamic constructor hooks.
Index values remain Python integers until construction so timezone and fold
validation retain their established precedence over calendar range errors.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param supplied: Prepared supplied input; native validation and ownership rules apply.
    :param zone: Prepared zone input; native validation and ownership rules apply.
    :param fold: Prepared fold input; native validation and ownership rules apply.
    :param unset: Prepared unset input; native validation and ownership rules apply.
    :param resolve_timezone: Prepared resolve_timezone input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_repr_fields(value: datetime) -> str:
    """Format only stored numeric fields; Python retains timezone and class hooks.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: str; errors preserve the native or external exception contract.
    """

def _pydt_round(value: _DateT, unit: str, mode: int) -> _DateT:
    """Round wall-clock epoch microseconds with integer half-to-even arithmetic.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :param mode: Prepared mode input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_shift(value: _DateT, month_delta: SupportsIndex = ..., day_delta: SupportsIndex = ..., month: SupportsIndex | None = None, day: SupportsIndex | None = None) -> _DateT:
    """Shift calendar months/days, clamping the final day only after selecting the month.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param month_delta: Prepared month_delta input; native validation and ownership rules apply.
    :param day_delta: Prepared day_delta input; native validation and ownership rules apply.
    :param month: Prepared month input; native validation and ownership rules apply.
    :param day: Prepared day input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_snap(value: _DateT, unit: str = 's') -> _DateT:
    """Snap to an adjacent valid calendar start; an equal distance selects the later one.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param unit: Prepared unit input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_stored_timezone(value: datetime) -> tzinfo | None:
    """Borrow the stored timezone without invoking a subclass's visible properties.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: tzinfo | None; errors preserve the native or external exception contract.
    """

def _pydt_strftime(value: datetime, format: object) -> str:
    """Execute the checked private native boundary for _pydt_strftime.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param format: Prepared format input; native validation and ownership rules apply.
    :returns: str; errors preserve the native or external exception contract.
    """

def _pydt_strptime(cls: type[_DateT], /, text: object, format: _StrptimeFormat, cfg: object | None = None) -> _DateT:
    """Parse native fields, then preserve the existing final child fromdatetime hook.

    :param cls: Final result constructor, called at the target boundary.
    :param text: Prepared text input; native validation and ownership rules apply.
    :param format: Prepared format input; native validation and ownership rules apply.
    :param cfg: Prepared cfg input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_timedelta(value: _DateT, duration: timedelta, subtract: bool) -> _DateT:
    """Read timedelta's native fields, preserving the input datetime's fold.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param duration: Prepared duration input; native validation and ownership rules apply.
    :param subtract: Prepared subtract input; native validation and ownership rules apply.
    :returns: _DateT; errors preserve the native or external exception contract.
    """

def _pydt_timedict(value: datetime, utc: bool) -> dict[str, int]:
    """Assemble a calendar dictionary without an intermediate time tuple.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param utc: Prepared utc input; native validation and ownership rules apply.
    :returns: dict[str, int]; errors preserve the native or external exception contract.
    """

def _pydt_timetuple(value: datetime) -> struct_time:
    """Build the standard tuple without reading datetime's foreign carrier duration.

    :param value: Prepared value input; native validation and ownership rules apply.
    :returns: struct_time; errors preserve the native or external exception contract.
    """

def _pydt_to_seconds(value: datetime, utc: bool | np.bool_ = False) -> float:
    """Return floating-point seconds without an intermediate Python integer.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param utc: Prepared utc input; native validation and ownership rules apply.
    :returns: float; errors preserve the native or external exception contract.
    """

def _pydt_to_us(value: datetime, utc: bool | np.bool_ = False) -> int:
    """Return exact epoch microseconds, consulting timezone callbacks only when requested.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param utc: Prepared utc input; native validation and ownership rules apply.
    :returns: int; errors preserve the native or external exception contract.
    """

def _resolve_optional_timezone(value: tzinfo, named: object) -> tzinfo | None:
    """Adapt only genuine, already loaded pytz types; absence is not cached.

    :param value: Prepared value input; native validation and ownership rules apply.
    :param named: Prepared named input; native validation and ownership rules apply.
    :returns: tzinfo | None; errors preserve the native or external exception contract.
    """

def _restore_configs(*args: object) -> Configs:
    """Allocate the fixed configuration type for the versioned pickle protocol.

    :param args: Versioned native restore arguments.
    :returns: Configs; errors preserve the native or external exception contract.
    """

def _restore_delta(cls: type[object], /, data: object) -> Delta:
    """Reconstruct a complete immutable Delta from this package's trusted pickle.

# Errors
Rejects non-Delta classes and malformed fields; cached hashes never replace field-derived values.

    :param cls: Final result constructor, called at the target boundary.
    :param data: Prepared data input; native validation and ownership rules apply.
    :returns: Delta; errors preserve the native or external exception contract.
    """

def _strftime_prepare(format: object) -> _StrftimeContext:
    """Execute the checked private native boundary for _strftime_prepare.

    :param format: Prepared format input; native validation and ownership rules apply.
    :returns: _StrftimeContext; errors preserve the native or external exception contract.
    """

def _strptime_compile(fmt: str, templates: dict[str, str] | None = None, words: dict[str, list[tuple[str, int]]] | None = None) -> _StrptimeFormat:
    """Execute the checked private native boundary for _strptime_compile.

    :param fmt: Prepared fmt input; native validation and ownership rules apply.
    :param templates: Prepared templates input; native validation and ownership rules apply.
    :param words: Prepared words input; native validation and ownership rules apply.
    :returns: _StrptimeFormat; errors preserve the native or external exception contract.
    """

def release_build() -> bool:
    """Report whether this extension was compiled without debug assertions.

Use this flag to reject debug wheels before release performance measurements.

    :returns: bool; errors preserve the native or external exception contract.
    """

def runtime_info() -> str:
    """Return the native implementation label for installation diagnostics.

    :returns: str; errors preserve the native or external exception contract.
    """
