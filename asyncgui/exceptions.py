__all__ = ('CancelledError', 'InvalidStateError', 'MultiError', )
from ._multierror import MultiError


class CancelledError(BaseException):
    """The Task was cancelled."""


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""
