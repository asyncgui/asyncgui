__all__ = ('CancelledError', 'InvalidStateError', 'CancelRequest', )


class CancelledError(BaseException):
    """The Task was cancelled."""


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class CancelRequest(BaseException):
    """(internal) Not an actual exception. Used for flow control.
    We should not catch this exception.
    """
