"""Exceptions raised when Delta rejects dateutil conversion inputs.

These names preserve the public exception hierarchy of the frozen reference;
they do not provide old module paths or Cython compatibility. Ordinary argument
and numeric failures still use builtin TypeError, ValueError and OverflowError.
"""

class cyTimesError(Exception):
    """Base exception for the retained cyTimes-style error names."""

class cyTimesTypeError(cyTimesError, TypeError):
    """Type error catchable as both cyTimesError and builtin TypeError."""

class DeltaError(cyTimesError):
    """Base exception for Delta-specific conversion errors."""

class InvalidRelativeDelta(DeltaError, cyTimesTypeError):
    """Raised by Delta.from_relativedelta when rd has an unsupported type.

    Instances are catchable as DeltaError, cyTimesError and builtin TypeError.
    This exception concerns the input type; failures in a valid object's
    normalized() method or numeric attributes propagate their original errors.
    """

__all__ = ["cyTimesError", "cyTimesTypeError", "DeltaError", "InvalidRelativeDelta"]
