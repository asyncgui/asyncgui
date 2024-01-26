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

-------------------------
xxx ignored GeneratorExit
-------------------------

If this type of error occurs in your program, try explicitly canceling the corresponding 'root' task.
All instances of :class:`asyncgui.Task` returned by :func:`asyncgui.start` are considered 'root' tasks.
You should identify the relevant one from the error message and then use :meth:`asyncgui.Task.cancel` to terminate it.

もしこのようなエラーが起きるようなら根タスクを明示的に中断してください。
根タスクとは :func:`asyncgui.start` が返すタスクの事です。
エラーメッセージを頼りに該当する根タスクを探して明示的に :meth:`asyncgui.Task.cancel` してください。
