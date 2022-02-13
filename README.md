# AsyncGui

Thin layer that helps to build a async/await-based api on top of a callback-based api.

## How to use

Despite its name, `asyncgui` has nothing to do with gui.
You can build an async/await-based api on top of any kind of callback-based api.
The simplest example of that would be [sched](https://docs.python.org/3/library/sched.html),
whose the whole functionality is just a timer.
You can wrap it with just few lines of code:

```python
import types
import sched
import asyncgui

s = sched.scheduler()

# wrapping the timer api takes only three lines
@types.coroutine
def sleep(duration):
    yield lambda step_coro: s.enter(duration, 10, step_coro)


async def main():
    print('A')
    await sleep(1)  # You can sleep like 'asyncio.sleep'
    print('B')
    await sleep(1)
    print('C')

asyncgui.start(main())
s.run()
```

And you already can run multiple tasks concurrently in a structured way:

```python
async def print_numbers():
    try:
        for i in range(10):
            await sleep(.1)
            print(i)
    except GeneratorExit:
        print('cancelled (numbers)')
        raise


async def print_letters():
    try:
        for c in "ABCDE":
            await sleep(.1)
            print(c)
    except GeneratorExit:
        print('cancelled (letters)')
        raise


async def main():
    from asyncgui.structured_concurrency import or_
    # Race print_letters() and print_numbers().
    # As soon as one of them finishes, the other one will be cancelled.
    await or_(print_letters(), print_numbers())
    print('main end')
```

```
A
0
B
1
C
2
D
3
E
cancelled (numbers)
main end
```

## Why not asyncio ?

The above example may not attract you because you can use `asyncio` instead of `sched`.
But in a read-world situation, that might not be an option:
Kivy required [massive changes](https://github.com/kivy/kivy/pull/6368) in order to support asyncio and Trio for instance.

<!--
Kivy has an event-loop. asyncio has one as well.
You cannot just put multiple event-loop in the same thread, which is why the massive changes were required.
On the other hand, asyncgui doesn't have one.
Async library that doesn't have an event loop.
Because of that, this can live with other event loop **in the same thread**.
That means libraries that does have event loop but doesn't provide async/await-style api (e.g. tkinter) can adopt async/await syntax without modifying the library itself.
This is not for application developers, but for async-library developers.
-->

## Pin the minor version

If you use this module, it's recommended to pin the minor version, because if it changed, it means some *important* breaking changes occurred.

```
# example of pinning the minor version using poetry
asynckivy@~0.5

# example of pinning the minor version using pip
asynckivy>=0.5,<0.6
```

## Tested on

- CPython 3.7
- CPython 3.8
- CPython 3.9
- CPython 3.10

## Async-libraries who use this

- [asynckivy](https://github.com/gottadiveintopython/asynckivy)
- [asynctkinter](https://github.com/gottadiveintopython/asynctkinter)
