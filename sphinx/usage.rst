=====
Usage
=====

In this section, I'll explain how to wrap a callback-style API in an async/await-style API, using :mod:`sched` as an example.
Let's start by writing code that does the following, and remember how to use the module:

#. Waits for 1 second
#. Prints "A"
#. Waits for 2 seconds
#. Prints "B"
#. Waits for 3 seconds
#. Prints "C"

Our code would look like this:

.. code-block::

    import sched

    PRIORITY = 0
    s = sched.scheduler()

    def task():
        def step1():
            print('A')
            s.enter(2, PRIORITY, step2)

        def step2():
            print('B')
            s.enter(3, PRIORITY, step3)

        def step3():
            print('C')

        s.enter(1, PRIORITY, step1)

    task()
    s.run()

:mod:`sched` provides callback-style APIs, and the code that uses them is not easy to understand.
You might wonder, "Why not just use :func:`time.sleep`?" So let me address that first.

Counter to 'Why not just use ``time.sleep``?'
=============================================

Indeed, if you use ``time.sleep``, it'll be easier to understand.

.. code-block::

    from time import sleep

    def task():
        sleep(1)
        print('A')
        sleep(2)
        print('B')
        sleep(3)
        print('C')

    task()

However, this approach works only when there's a single task.
If there are multiple ones, the story changes.
With the ``time.sleep`` method, you need multiple threads to run multiple tasks simultaneously, whereas with the ``sched`` method, one thread is sufficient.
For example, you can just call the ``task()`` multiple times at the end of the code:

.. code-block::

    task()
    task()
    s.run()

Therefore, ``sched`` cannot be replaced with ``time.sleep``.

API Design
==========

We want to wrap the API, but first, we need to imagine how we want to use it from ``asyncgui``.
Remember the ``time.sleep`` example we saw earlier:

.. code-block::

    from time import sleep

    def task():
        sleep(1)
        print('A')
        sleep(2)
        print('B')
        sleep(3)
        print('C')

This approach has the disadvantage of occupying a thread, but in return, it's quite easy to read.
If we successfully design our API to be as readable as this, we'd have the best of both worlds [#get_cancellation]_.
So, let's aim for it.

.. code-block::

    # our ideal
    async def task():
        await sleep(1)
        print('A')
        await sleep(2)
        print('B')
        await sleep(3)
        print('C')

In order for our API to be used like  ``await sleep(1)``, ``sleep`` must be a :class:`~collections.abc.Callable` that returns an :class:`~collections.abc.Awaitable`.
There are several options that meet this condition, and we choose an async function [#async_func_mitasu]_.

.. code-block::

    async def sleep(duration):
        ...

But hold on, since :meth:`sched.scheduler.enter` is an instance method, our API needs to take a :class:`sched.scheduler` instance.
And since it has a ``priority`` parameter, our API might better have one as well in order not to lose any functionality of the original API.

.. code-block::

    async def sleep(scheduler, priority, duration):
        ...

Let's start implementing it with this goal in mind.

Implementation
==============

To wrap a callback-style API in an async/await-style API,
we need to set up execution to resume when a callback function is called, and then pause it.
This might sound unclear, but if you've ever used :class:`asyncio.Event` or :class:`trio.Event`, you already know it.

.. code-block::

    import asyncio

    async def wrapper():
        e = asyncio.Event()

        # Set up the execution to resume when this callback function is called
        register_callback(lambda *args, **kwargs: e.set())

        # Pause the execution
        await e.wait()

    async def user():
        print('A')
        await wrapper()
        print('B')

By introducing a wrapper like this, the ``user`` side code can use a callback-style API without losing readability.
And ``asyncgui`` has an API specifically designed for this purpose.

.. code-block::

    import asyncgui as ag

    async def wrapper():
        e = ag.ExclusiveEvent()
        register_callback(e.fire)  # A
        args, kwargs = await e.wait()  # B

:class:`asyncgui.ExclusiveEvent` has two advantages over :class:`asyncio.Event`.
One, you don't need to use a lambda because :meth:`asyncgui.ExclusiveEvent.fire` can take any arguments (line A).
Two, you can receive the arguments passed to it (line B).

Let's implement our API with this.

.. code-block::

    import asyncgui as ag

    async def sleep(scheduler, priority, duration):
        e = ag.ExclusiveEvent()
        scheduler.enter(duration, priority, e.fire)
        await e.wait()

Now we can use it like this:

.. code-block::

    import functools
    import sched
    import asyncgui as ag

    async def sleep(...):
        ...

    def main():
        s = sched.scheduler()
        slp = functools.partial(sleep, s, 0)
        ag.start(task(slp))
        s.run()

    async def task(slp):
        await slp(1)
        print('A')
        await slp(2)
        print('B')
        await slp(3)
        print('C')

    main()

We successfully achieved the best of both worlds; our API doesn't occupy a thread, and the user side code is as readable as the :func:`time.sleep` example.

However, there's one more thing to address: :ref:`dealing-with-cancellation`.
It is not strictly necessary in this case because ``ExclusiveEvent`` handles it to a certain extent,
but it's better to handle it within ``sleep`` itself to cover some edge cases.

.. code-block::

    import asyncgui as ag

    async def sleep(scheduler, priority, duration):
        e = ag.ExclusiveEvent()
        event = scheduler.enter(duration, priority, e.fire)
        try:
            await e.wait()
        except ag.Cancelled:
            scheduler.cancel(event)
            raise

This is the complete version of our API.
We successfully connected the :mod:`sched` module to the :mod:`asyncgui` module.
Once connected, we can benefit from the powerful :doc:`structured-concurrency` APIs.

.. code-block::

    import functools
    import sched
    import asyncgui as ag
    import string

    async def sleep(scheduler, priority, duration):
        ...

    def main():
        s = sched.scheduler()
        slp = functools.partial(sleep, s, 0)
        ag.start(async_main(slp))
        s.run()

    async def async_main(slp):
        # Print digits from 0 to 9 at 0.3-second intervals, with a 2-second time limit
        async with ag.move_on_when(slp(2)) as timeout_tracker:
            for c in string.digits:
                print(c, end=' ')
                await slp(0.3)
        print('')

        if timeout_tracker.finished:
            print("Timeout")
        else:
            print("Printed all digits in time")

    main()

::

    0 1 2 3 4 5 6
    Timeout

.. [#get_cancellation] Additionally, we will get a powerful cancellation mechanism.
.. [#async_func_mitasu] Async function is a function, so it's obviously a ``Callable``, and it returns a coroutine, which is one of the ``Awaitable`` objects.
