__all__ = (
    'InvalidStateError', 'MultiError', 'EndOfConcurrency',
    'CancelledError',
)
from ._multierror import MultiError


class CancelledError(BaseException):
    """The Task was cancelled."""


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class EndOfConcurrency(BaseException):
    """(internal) Not an actual error. Used for flow control."""
