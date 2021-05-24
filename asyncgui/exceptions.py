__all__ = (
    'InvalidStateError', 'MultiError', 'EndOfConcurrency',
    'NoChildLeft',
)
from ._multierror import MultiError


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class EndOfConcurrency(BaseException):
    """(internal) Not an actual error. Used for flow control."""


class NoChildLeft(Exception):
    """There is no child to wait for"""
