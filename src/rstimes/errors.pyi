"""Domain errors for text parsing and configuration."""
from typing import NoReturn, TypeVar

_Error = TypeVar("_Error", bound=BaseException)

class RstimesError(Exception):
    """Base class for rsTimes-specific parsing and configuration failures.
    
    Parameters
    ----------
    *args : object
        Details describing the failure, as for a standard exception.
    
    Notes
    -----
    This class does not catch every error raised during a library call.
    TypeError, ValueError, OverflowError and callback exceptions retain their
    usual meanings unless they are one of the domain errors below."""

class ParseError(RstimesError, ValueError):
    """The parser could not interpret text under the requested rules.
    
    Parameters
    ----------
    *args : object
        Details naming the failed call and the known field or input.
    
    Notes
    -----
    Invalid strict fields, conflicting fields and missing required date
    information use this class. A failure inside the chosen result constructor
    retains that constructor's exception instead."""

class ConfigError(RstimesError, ValueError):
    """A configuration token, rule or value cannot be used.
    
    Parameters
    ----------
    *args : object
        Details describing the invalid rule and, when known, how to fix it.
    
    Notes
    -----
    An unsupported object type raises TypeError. Errors inside user callbacks
    keep their original exception; they are not automatically ConfigError."""

__all__: list[str]

def _critical(error: BaseException) -> bool:
    """Return whether error must bypass explanatory work.

    :param error: The original failure.
    :returns: True for cancellation, exit and memory failures.
    """

def _preview(value: object, original_length: int | None = None) -> str:
    """Describe a value without invoking arbitrary display callbacks.

    :param value: The failed input.
    :param original_length: A previously captured length, when available.
    :returns: A bounded safe preview.
    """

def _own_error(error: _Error, parameter: str | None = None, value: object = None) -> _Error:
    """Mark a newly created library failure without changing its identity.

    :param error: A failure whose library origin is known.
    :param parameter: The known field, or None.
    :param value: Its input for a safe failure-only preview.
    :returns: The same exception instance and concrete type.
    """

def _external_error(error: _Error) -> _Error:
    """Preserve an external failure while recording its callback boundary.

    :param error: The original callback exception.
    :returns: The same exception, with its original type and arguments.
    """

def _argument_error(error: _Error, entry: str, parameter: str, value: object,
                    has_value: bool = True, prepared_preview: str | None = None) -> _Error:
    """Finish owned context or add a note to an external exception.

    :param error: The existing failure; it is never reconstructed.
    :param entry: Its public call name.
    :param parameter: The known field or location.
    :param value: The input when has_value is True.
    :param has_value: Whether this boundary has a reliable input value.
    :param prepared_preview: An optional preview captured before callbacks.
    :returns: The same exception instance.
    """

def _raise_argument_context(error: BaseException, entry: str, parameter: str,
                            value: object) -> NoReturn:
    """Raise an existing failure after finishing public-call context.

    :param error: The failure to propagate.
    :param entry: The actual public call name.
    :param parameter: The known argument or location.
    :param value: Its safely previewed input.
    :returns: Never returns; raises the original exception.
    """

def _location_error(error: _Error, entry: str, parameter: str) -> _Error:
    """Add a known location without rereading callback-invalidated data.

    :param error: The original exception.
    :param entry: Its public call name.
    :param parameter: The previously established input location.
    :returns: The same exception instance.
    """

def _binary_error(error: _Error, entry: str, left: object, right: object) -> _Error:
    """Describe failed binary operands without replacing their exception.

    :param error: The original failure.
    :param entry: Its public arithmetic entry.
    :param left: The live left operand.
    :param right: The live right operand.
    :returns: The same exception instance.
    """
