class MultiError(Exception):
    """An exception that contains other exceptions; also known as an "inception".

    It's main use is to represent the situation when multiple child tasks all raise errors "in parallel".

    Args:
      exceptions (sequence): The exceptions

    Returns:
      If ``len(exceptions) == 1``, returns that exception. This means that a call to ``MultiError(...)`` is not
      guaranteed to return a `MultiError` object! Otherwise, returns a new `MultiError` object.

    Raises:
      TypeError: if any of the passed in objects are not instances of `Exception`.
    """

    def __init__(self, exceptions):
        # Avoid recursion when exceptions[0] returned by __new__() happens
        # to be a MultiError and subsequently __init__() is called.
        if hasattr(self, "exceptions"):
            # __init__ was already called on this object
            assert len(exceptions) == 1 and exceptions[0] is self
            return
        self.exceptions = exceptions

    def __new__(cls, exceptions):
        exceptions = tuple(exceptions)
        for exc in exceptions:
            if not isinstance(exc, Exception):
                raise TypeError("Expected an exception object, not {!r}".format(exc))
        if len(exceptions) == 1:
            # If this lone object happens to itself be a MultiError, then
            # Python will implicitly call our __init__ on it again.  See
            # special handling in __init__.
            return exceptions[0]
        else:
            # The base class __new__() implicitly invokes our __init__, which
            # is what we want.
            #
            # In an earlier version of the code, we didn't define __init__ and
            # simply set the `exceptions` attribute directly on the new object.
            # However, linters expect attributes to be initialized in __init__.
            return Exception.__new__(cls, exceptions)

    def __str__(self):
        return ", ".join(repr(exc) for exc in self.exceptions)

    def __repr__(self):
        return "<MultiError: {}>".format(self)
