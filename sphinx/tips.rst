====
Tips
====

.. _dealing-with-cancellation:

-------------------------
Dealing with Cancellation
-------------------------

When the execution of a :class:`asyncgui.Task` instance is cancelled, a :exc:`asyncgui.Cancelled` exception is raised within it.
You can take advantage of this opportunity as follows:

.. code-block::

    async def async_func():
        try:
            ...
        except Cancelled:
            something_you_want_to_do_only_when_cancelled()
            raise  # You must re-raise !!
        finally:
            cleanup_resources()

You are not allowed to ``await`` anything inside the except-Cancelled-clause and the finally-clause
if you want the task to be cancellable because cancellations always must be done immediately.

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

This, of course, includes ``async for`` and ``async with`` as they await ``__aiter__()``,
``__anext__()``, ``__aenter__()`` and ``__aexit__()``.

-------------------------
xxx ignored GeneratorExit
-------------------------

If this type of error occurs in your program, try explicitly canceling the corresponding 'root' task.
All instances of :class:`asyncgui.Task` returned by :func:`asyncgui.start` are considered 'root' tasks.
You should identify the relevant one from the error message and then use :meth:`asyncgui.Task.cancel` to terminate it.
