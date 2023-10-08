====
Tips
====

.. _dealing-with-cancellation:

-------------------------
Dealing with Cancellation
-------------------------

:func:`asyncgui.start` returns a :class:`asyncgui.Task` instance, which can be used to cancel its execution.

.. code-block::

    task = asyncgui.start(async_func())
    ...
    task.cancel()

When ``task.cancel()`` is called, :exc:`asyncgui.Cancelled` exception will occur inside the task,
which means you can prepare for a cancellation as follows:

.. code-block::

    async def async_func():
        try:
            ...
        except Cancelled:
            print('cancelled')
            raise  # You must re-raise !!
        finally:
            print('cleanup resources here')

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
