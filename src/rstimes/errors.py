"""Exception hierarchy used by Delta conversion."""

class cyTimesError(Exception):
    """Base error name retained by the Delta Python interface."""

class cyTimesTypeError(cyTimesError, TypeError):
    """Base type error."""

class DeltaError(cyTimesError):
    """Base Delta error."""

class InvalidRelativeDelta(DeltaError, cyTimesTypeError):
    """Invalid dateutil.relativedelta input."""

__all__ = ["cyTimesError", "cyTimesTypeError", "DeltaError", "InvalidRelativeDelta"]
