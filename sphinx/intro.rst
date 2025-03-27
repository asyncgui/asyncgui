============
Introduction
============


The problem with existing libraries
===================================

There are a couple of async libraries for Python.
One, of course, is :mod:`asyncio` from the standard library.
Another one is Trio_, well-known for its `structured concurrency`_.
And Curio_, which seems to have had a big influence on Trio, though it now only accepts bug fixes.

They may differ from each other but all of them have in common is that they are not suitable for GUI programs.
I'm not saying "Having a GUI library and an async library coexist in the same thread is problematic due to their individual main loops".
In fact, Kivy_ and BeeWare_ have adapted themselves to work with async libraries;
PyGame_ doesn't even own a main loop and expects the user to implement one,
so you could do that by putting an ``await asyncio.sleep()`` inside a main loop [#pygame_with_asyncio]_;
:mod:`tkinter` and PyQt_ seem to have 3rd party libraries that allow them to work with async libraries.
Even if none of them are your options, Trio has `special mode`_ that makes it run without interfering with other main loop.
Therefore, I think it's safe to say that the coexisting problem has been already solved.

Then why do I say "they are not suitable for GUI programs"?
It's because they cannot *immediately* start/resume tasks.
For instance, :func:`asyncio.create_task` and :meth:`asyncio.TaskGroup.create_task` are the ones that start tasks in
:mod:`asyncio`, but neither of them does it immediately.

Let me clarify what I mean by "immediately" just in case.
It means the following test should pass:

.. code-block::

    import asyncio

    flag = False


    async def async_fn():
        global flag; flag = True


    async def main():
        asyncio.create_task(async_fn())
        assert flag


    asyncio.run(main())

which does not.
The same applies to :meth:`trio.Nursery.start` and :meth:`trio.Nursery.start_soon`
(This has "soon" in its name so it's obvious).

The same issue arises when they resume tasks.
:meth:`asyncio.Event.set` and :meth:`trio.Event.set` don't immediately resume the tasks waiting for it to happen.
They schedule the tasks to *eventually* resume, thus, the following test fails.

.. code-block::

    import asyncio

    flag = False


    async def async_fn(e):
        e.set()
        assert flag


    async def main():
        e = asyncio.Event()
        asyncio.create_task(async_fn(e))
        await e.wait()
        global flag; flag = True


    asyncio.run(main())

Why does the inability to immediately start/resume tasks make async libraries unsuitable for GUI programs?
Take a look at the following pseudo code that changes the background color of a button while it is pressed.

.. code-block::

    async def toggle_button_background_color(button):
        while True:
            await button.to_be_pressed()
            button.background_color = different_color
            await button.to_be_released()
            button.background_color = original_color

Consider a situation where the task is paused at the ``await button.to_be_pressed()`` line and the user presses the button.
As I mentioned, neither of :mod:`asyncio` nor :mod:`trio` resumes tasks immediately, so the background color won't change immediately.
Now, what happens if the user releases the button *before* the task resumes?
The task eventually resumes and pauses at the ``await button.to_be_released()`` line...
**but the user has already released the button**.
The task ends up waiting there until the user presses and releases the button again.
As a result, the background color of the button remains the ``different_color`` until that happens.

.. note::

    The situation is worse in Kivy_. In Kivy, touch events are stateful objects.
    If you fail to handle them promptly, their state might undergo changes,
    leaving no time to wait for tasks to resume.

Responding to events without missing any occurrences is challenging for async libraries that cannot start or resume tasks immediately.
The only solution I came up with is recording events using traditional callback APIs,
and supplying them to tasks that resume late a.k.a. buffering.
I'm not sure if it's possible or practical, but it certainly adds huge complexity into your program.

If you use ``asyncgui``, that never be a problem.


asyncgui
========

Immediacy
---------

The problem mentioned above doesn't occur in ``asyncgui`` because:

* :func:`asyncgui.start` and :meth:`asyncgui.Nursery.start` immediately start a task.
* :meth:`asyncgui.Event.fire` immediately resumes the tasks waiting for it to happen.

All other APIs work that way as well.

No main loop
-------------

The coexistence problem I mentioned earlier doesn't occur in ``asyncgui`` because it doesn't own a main loop.
Instead, ``asyncgui`` runs by piggybacking on another main loop, such as one from a GUI library.
To achieve this, however, you need to wrap the callback-style APIs associated with the main loop it piggybacks.
I'll explain this further in the :doc:`usage` section.

.. note::

    "another main loop" can be other async library's.
    Yes, you can even run ``asyncgui`` and other async library in the same thread.
    However, there is a major caveat: :ref:`coexistence-with-other-async-libraries`.

No global state
---------------

Although it wasn't originally intended, ``asyncgui`` ended up having no global state. All states are represented as:

* free variables
* local variables inside coroutines/generators
* instance attributes

not:

* module-level variables
* class-level attributes

.. note::

    Other async libraries have global states.

    `asyncio.tasks._current_tasks`_, `trio._core.GLOBAL_CONTEXT`_

Cannot sleep by itself
----------------------

It might surprise you, but ``asyncgui`` cannot ``await sleep(...)`` by itself.
This is because it requires a main loop, which ``asyncgui`` lacks.

However, you can achieve this by wrapping the timer APIs of the main loop it piggybacks on, as I mentioned earlier.
In fact, that is the intended usage of this library.
``asyncgui`` itself only provides the features that depend solely on the Python language (or maybe some CPython-specific behavior),
and doesn't provides the ones that need to interact with the operating system [#timer_requires_system_call]_.

.. figure:: ./figure/core-concept-en.*


.. _Trio: https://trio.readthedocs.io/
.. _special mode: https://trio.readthedocs.io/en/stable/reference-lowlevel.html#using-guest-mode-to-run-trio-on-top-of-other-event-loops
.. _structured concurrency: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
.. _Curio: https://curio.readthedocs.io/
.. _PyGame: https://www.pygame.org/
.. _Kivy: https://kivy.org/
.. _BeeWare: https://beeware.org/
.. _PyQt: https://www.riverbankcomputing.com/software/pyqt/

.. _asyncio.tasks._current_tasks: https://github.com/python/cpython/blob/4890bfe1f906202ef521ffd327cae36e1afa0873/Lib/asyncio/tasks.py#L970-L972
.. _trio._core.GLOBAL_CONTEXT: https://github.com/python-trio/trio/blob/722f1b577d4753de5ea1ca5b5b9f2f1a7c6cb56d/trio/_core/_run.py#L1356

.. [#pygame_with_asyncio]
    .. code-block::

        # NOTE: I haven't tested whether this code actually works.

        async def main_loop():
            while True:
                for event in pygame.event.get():
                    ...
                await asyncio.sleep(...)
                ...

        asyncio.create_task(main_loop())

.. [#timer_requires_system_call]
    To implement timer APIs, you need to use functions that provide the current time, such as :func:`time.time` or :func:`time.perf_counter`, which probably involves a system call.
