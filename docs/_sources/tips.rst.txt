====
Tips
====

.. _dealing-with-cancellation:

-------------------------
Dealing with Cancellation
-------------------------

When an :class:`asyncgui.Task` instance is being cancelled, a :exc:`asyncgui.Cancelled` exception is raised inside it.
You can take advantage of this to perform cleanup or other actions, like so:

.. code-block::

    async def async_func():
        try:
            ...
        except Cancelled:
            something_you_want_to_do_only_when_cancelled()
            raise  # You must re-raise !!
        finally:
            cleanup_resources()

You are not allowed to 'await' anything inside an except-Cancelled-clause and a finally-clause
because cancellations always must be handled immediately in ``asyncgui``.

.. code-block::

    async def async_func():
        try:
            await something  # <-- ALLOWED
        except Exception:
            await something  # <-- ALLOWED
        except Cancelled:
            await something  # <-- NOT ALLOWED
            raise
        finally:
            await something  # <-- NOT ALLOWED

This includes ``async for`` and ``async with`` as they 'await' ``__aiter__()``,
``__anext__()``, ``__aenter__()`` and ``__aexit__()``.

-------------------------
xxx ignored GeneratorExit
-------------------------

This error likely means that you forgot to cancel a root task,
and it ended up being garbage-collected while still running—
which is not desirable in ``asyncgui``.

Make sure to explicitly cancel the task to avoid this!

.. _coexistence-with-other-async-libraries:

--------------------------------------
Coexistence with other async libraries
--------------------------------------

:mod:`asyncio` and :mod:`trio` do some hacky stuff, :func:`sys.set_asyncgen_hooks` and :func:`sys.get_asyncgen_hooks`,
which likely delays the cleanup of async generators when either of these libraries is running.
You can see its details `here <https://peps.python.org/pep-0525/#finalization>`__.

Because of this, you have to explicitly close async generators when you are done with them.
