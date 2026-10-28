"""Domain errors for text parsing and configuration."""

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
