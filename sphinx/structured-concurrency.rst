======================
Structured Concurrency
======================

In this section, I'll add a few notes about `structured concurrency`_ APIs.
However, I won't go into what structured concurrency is or why it matters,
since there is already an `amazing essay`_ explaining it.


List of structured concurrency APIs
-----------------------------------

- :func:`~asyncgui.wait_all`
- :func:`~asyncgui.wait_any`
- :func:`~asyncgui.wait_all_cm`
- :func:`~asyncgui.wait_any_cm`
- :func:`~asyncgui.move_on_when` (alias of ``wait_any_cm``)
- :func:`~asyncgui.run_as_daemon`
- :func:`~asyncgui.run_as_main`
- :func:`~asyncgui.open_nursery`


Ideal
-----

Ideally, a program should have a single root task, with all other tasks as its children or as descendants of other tasks, forming a single task tree.
This is something that :mod:`trio` enforces, but ``asyncgui`` is unable to do due to its architectural limitations [#limitations]_.

In ``asyncgui``. every :class:`asyncgui.Task` instance returned by :func:`asyncgui.start` is a root task.

(editing...)


Nest as you like
----------------

Once you start using structured concurrency APIs,
you'll notice how powerful they are for expressing high-level control flow.

For example, if you want to wait until ``async_fn1`` completes **and** either ``async_fn2`` or ``async_fn3`` completes,
you can implement it like this:

.. code-block::

    tasks = await wait_all(
        async_fn1(),
        wait_any(
            async_fn2(),
            async_fn3(),
        ),
    )

.. figure:: ./figure/nested-tasks.*

The downside of this approach is that it becomes cumbersome to access tasks deeply nested in the hierarchy.

.. code-block::

    flattened_tasks = (tasks[0], *tasks[1].result, )

    for idx, task in enumerate(flattened_tasks, start=1):
        if task.finished:
            print(f"async_fn{idx} completed with a return value of {task.result}.")
        else:
            print(f"async_fn{idx} was cancelled.")

The deeper a task is nested, the longer the expression needed to access it becomes — like ``tasks[i].result[j].result[k]``.
If you don't like writing such lengthy expressions, you can avoid it by creating a :class:`asyncgui.Task` instance yourself
and passing it to the API, like so:

.. code-block::

    await wait_all(
        async_fn1(),
        wait_any(
            task2 := Task(async_fn2()),
            async_fn3(),
        ),
    )
    if task2.finished:
        print(f"async_fn2 completed with a return value of {task2.result}.")
    else:
        print("async_fn2 was cancelled.")


Exception Handling
------------------

All the APIs propagate exceptions in the same way as trio_ with the ``strict_exception_groups`` parameter being True.
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
.. _amazing essay: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/

.. [#limitations] I have no idea how to achieve that without relying on either a main loop or global state.
