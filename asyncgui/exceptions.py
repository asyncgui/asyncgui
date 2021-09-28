__all__ = (
    'InvalidStateError', 'MultiError', 'EndOfConcurrency',
    'NoChildLeft', 'WouldBlock', 'BusyResourceError',
    'ClosedResourceError', 'BrokenResourceError', 'EndOfChannel',
)
from ._multierror import MultiError


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class EndOfConcurrency(BaseException):
    """(internal) Not an actual error. Used for flow control."""


class NoChildLeft(Exception):
    """(no longer used)"""


class WouldBlock(Exception):
    """(took from trio)
    Raised by X_nowait functions if X would block.
    """


class BusyResourceError(Exception):
    """(took from trio)
    """


class ClosedResourceError(Exception):
    """(took from trio)
    Raised when attempting to use a resource after it has been closed.

    Note that "closed" here means that *your* code closed the resource,
    generally by calling a method with a name like ``close`` or ``aclose``, or
    by exiting a context manager. If a problem arises elsewhere – for example,
    because of a network failure, or because a remote peer closed their end of
    a connection – then that should be indicated by a different exception
    class, like :exc:`BrokenResourceError` or an :exc:`OSError` subclass.
    """


class BrokenResourceError(Exception):
    """(took from trio)
    Raised when an attempt to use a resource fails due to external
    circumstances.

    For example, you might get this if you try to send data on a stream where
    the remote side has already closed the connection.

    You *don't* get this error if *you* closed the resource – in that case you
    get :class:`ClosedResourceError`.

    This exception's ``__cause__`` attribute will often contain more
    information about the underlying error.
    """


class EndOfChannel(Exception):
    """(took from trio)
    This is analogous to an "end-of-file" condition, but for channels.
    """
