============
Introduction
============


The problem with existing libraries
===================================

There are couple of async libraries already exist.
One, of course, is :mod:`asyncio` from the standard library.
Another one is Trio_, well-known for its `structured concurrency`_.
And Curio_, which seems to have had a big influence on Trio, though it now only accepts bug fixes.

They may be different each other but all of them have in common is that they are not suitable for GUI programs.
I'm not saying "Having a GUI library and an async library coexist in the same thread is problematic due to their individual event loops".
In fact, Kivy_ and BeeWare_ have adapted themselves to work with async libraries,
PyGame_ doesn't even have an event loop so you could implement it as an async loop,
:mod:`tkinter` and PyQt_ seem to have 3rd party libraries that allow them to work with async libraries.
Even if none of them are your options, Trio has `special mode`_ that makes it run without interfering with other event loop.
Therefore, I think it's safe to say that the coexisting problem has been already solved.

Then why did I say "they are not suitable for GUI programs"?
It's because they cannot *immediately* start/resume tasks.
For instance, :func:`asyncio.create_task` and :meth:`asyncio.TaskGroup.create_task` are the ones that start tasks in
:mod:`asyncio`, but neither of them do it immediately.

Let me clarify what I mean by "immediately" just in case.
It means the following test passes.

.. code-block::

    import asyncio

    flag = False


    async def async_fn():
        global flag; flag = True


    async def main():
        asyncio.create_task(async_fn())
        assert flag


    asyncio.run(main())

This fails because :func:`asyncio.create_task` doesn't start a task immediately.
The same applies to :meth:`asyncio.TaskGroup.create_task`, :meth:`trio.Nursery.start`, and :meth:`trio.Nursery.start_soon`
(the last one has "soon" in its name so it's obvious).

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

Why does the inability to start/resume tasks make async libraries unsuitable for GUI programs?
Let's say you have a piece of code that changes the background color of a button while it is pressed:

.. code-block::

    async def toggle_button_background_color(button):
        while True:
            await button.gets_pressed
            button.background_color = different_color
            await button.gets_released
            button.background_color = original_color

Consider a situation where the task is paused at the ``await button.gets_pressed`` line and the user presses the button.
As I mentioned, neither of :mod:`asyncio` nor :mod:`trio` resumes tasks immediately, so the background color won't change immediately.
Now, what happens if the user releases the button *before* the task resumes?
The task eventually resumes and pauses at the ``await button.gets_released`` line...
**but the user has already released the button**.
The task ends up waiting there until the user presses and releases the button again.
As a result, the background color of the button remains ``different_color`` until that happens.

Reacting to events without missing any occurrences is challenging for async libraries that cannot start/resume tasks immediately.
The only idea I came up with is that, record events using the traditional callback functions,
and supply them to the tasks that resume late a.k.a. buffering.
I'm not sure it's possible or practical, but it certainly has an impact on performance.

If you use ``asyncgui``, that never be a problem.


asyncgui characteristics
========================

Start tasks immediately
-----------------------

The problem mentioned above doesn't occur in ``asyncgui`` because:

* :func:`asyncgui.start` and :meth:`asyncgui.Nursery.start` immediately start tasks.
* :meth:`asyncgui.Event.set` immediately resumes tasks.

All other APIs work that way as well.

No event loop
-------------

The coexistence problem I mentioned earlier doesn't occur in ``asyncgui`` because it doesn't have an event loop in the first place.
Instead, ``asyncgui`` runs by piggybacking on another event loop (e.g. from a GUI library).
To do that, however, you need to make a "glue" that connects ``asyncgui`` and the event loop it piggybacks.
I'll explain it in :doc:`usage`.

.. note::

    "another event loop" can be other async library's.
    Yes, you can run ``asyncgui`` and other async library in the same thread (though there are some limitations).

No global state
---------------

Although it wasn't originally intended, ``asyncgui`` ended up having no global state. All states are represented as:

* local variables inside functions
* instance attributes

not:

* module-level variables
* class-level attributes

.. note::

    Other async libraries have global states.

    Examples: `asyncio.tasks._current_tasks`_, `trio._core.GLOBAL_CONTEXT`_

Cannot sleep by itself
----------------------

It might surprise you, but ``asyncgui`` cannot even ``await sleep(...)`` by itself.
It's because it requires an event loop, and ``asyncgui`` doesn't have one.

However, such a task is possible with the help of a "glue".
In fact, that is the intended usage of this library.
``asyncgui`` itself only provides the features that depend solely on the Python language (or its interpreter),
and doesn't provides the ones that need to interact with the operating system.

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