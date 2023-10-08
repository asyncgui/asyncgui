======================
Structured Concurrency
======================

I'm going to talk about APIs related to `structured concurrency`_ here.
However, I'm not going to talk about what is structured concurrency nor why it's important,
since there is already an `amazing article`_ explaining it.


wait_any
--------

.. autofunction:: asyncgui.wait_any

This may be the most in-demand feature of all the structured concurrency APIs.
It runs multiple tasks simultaneously and waits for any one of them to finish.
Once that happens, it will cancel the remaining tasks.

.. code-block::

    await wait_any(async_fn1(), async_fn2(), async_fn3())

You can tell which task finished or got cancelled, and what their return values are,
from the return value of this function.

.. code-block::

    tasks = await wait_any(async_fn1(), async_fn2(), async_fn3())

    for t, idx in zip(tasks, "123"):
        if t.finished:
            print(f"The return value of async_fn{idx}() :", t.result)
        else:
            print(f"async_fn{idx}() was cancelled")

Note that there is no guarantee that only one task will finish.
There is a possibility that all tasks are cancelled.
There is also a possibility that multiple tasks finish.
The reasons for this could be due to :func:`asyncgui.disable_cancellation` or tasks that finish before
they have a chance to be cancelled.
However, in most cases, you don't need to worry about it.


wait_all
--------

.. autofunction:: asyncgui.wait_all

Run multiple tasks simultaneously and wait for all of them to finish/be-cancelled.

.. code-block::

    tasks = await wait_all(async_fn1(), async_fn2(), async_fn3())


Nest as you want
----------------

Since ``wait_all`` and ``wait_any`` return an :class:`typing.Awaitable`,
they can be an argument of themselves.

.. code-block::

    # Wait until 'async_fn1' finishes and either 'async_fn2' or 'async_fn3' finishes.
    tasks = await wait_all(
        async_fn1(),
        wait_any(
            async_fn2(),
            async_fn3(),
        ),
    )

.. figure:: ./figure/nested-tasks.*

The downside of doing this is that it becomes cumbersome to access to tasks nested deeply in the hierarchy.

.. code-block::

    flattened_tasks = (tasks[0], *tasks[1].result, )

    while t, idx in zip(flattened_tasks, "123"):
        if t.finished:
            print(f"The return value of async_fn{idx}() :", t.result)
        else:
            print(f"async_fn{idx}() was cancelled")

The deeper a task is nested, the longer the expression to access to it becomes, like ``tasks[i].result[j].result[k]``.
If you don't like lengthy expressions, you can avoid that by creating a :class:`asyncgui.Task` instance by yourself,
and passing it to the api as follows.

.. code-block::

    await wait_all(
        async_fn1(),
        wait_any(
            task2 := Task(async_fn2()),
            async_fn3(),
        ),
    )
    if tasks2.finished:
        print("The return value of async_fn2() : ", tasks2.result)
    else:
        print("async_fn2() was cancelled")


wait_any_cm, wait_all_cm
------------------------

.. autofunction:: asyncgui.wait_any_cm

.. autofunction:: asyncgui.wait_all_cm

``wait_any`` and ``wait_all`` have an async context manager form.
The following code

.. code-block::

    async def async_fn1():
        # content of async_fn1

    async def main():
        await wait_any(async_fn1(), async_fn2())

can be written as follows.

.. code-block::

    async def main():
        async with wait_any_cm(async_fn2()):
            # content of async_fn1

This form has a great advantage.
Read trio-util_'s documentation for details.


run_as_secondary, run_as_daemon
-------------------------------

.. autofunction:: asyncgui.run_as_secondary

.. autofunction:: asyncgui.run_as_daemon

All the APIs explained so far treat tasks equally.
Taking ``wait_any_cm`` as an example, when either the code within the with-block or the awaitable passed to the API
completes, it will cause the other one to be cancelled.
What if you want only one of them to cause the other one to be cancelled, but not the other way around?
That's exactly where ``run_as_daemon`` comes into play.

.. code-block::

    async with run_as_daemon(async_fn()):
        ...

In this code, if the code within the with-block finishes first, it will cause the ``async_fn()`` to be cancelled.
But if ``async_fn()`` finishes first, it will cause nothing, and just waits for the code within the with-block to
finish.
You can think of this as the relation between a non-daemon thread and a daemon thread.


run_as_primary
--------------

.. autofunction:: asyncgui.run_as_primary

The opposite of ``run_as_daemon``.

.. code-block::

    async with run_as_primary(async_fn()):
        ...

If ``async_fn()`` finishes first, it will cause the code within the with-block to be cancelled.


open_nursery
------------

.. autofunction:: asyncgui.open_nursery


Exception Handling
------------------

All the APIs explained here propagate exceptions in the same way as trio_ with the ``strict_exception_groups``
parameter being True.
In other words, they *always* wrap the exception(s) occurred in their child tasks in an :exc:`ExceptionGroup`.

.. tabs::

    .. group-tab:: 3.11 or newer

        .. code-block::

            try:
                await wait_any(...)
            except* Exception as excgroup:
                for exc in excgroup.exceptions:
                    print('Exception caught:', type(exc))
                

    .. group-tab:: 3.10 or older

        .. code-block::

            import exceptiongroup

            def error_handler(excgroup):
                for exc in excgroup.exceptions:
                    print('Exception caught:', type(exc))

            with exceptiongroup.catch({Exception: error_handler, }):
                await wait_any(...)


.. _structured concurrency: https://en.wikipedia.org/wiki/Structured_concurrency
.. _trio: https://trio.readthedocs.io/
.. _trio-util: https://trio-util.readthedocs.io/
.. _amazing article: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
