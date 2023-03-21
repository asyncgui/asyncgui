# AsyncGui

A thin layer that helps to build async/await-based apis using callback-based apis.

## How to use

Despite its name, the application of `asyncgui` is **not** limited to gui programs.
You can wrap any kind of callback-based apis in it.
The simplest example of it would be [sched](https://docs.python.org/3/library/sched.html),
whose the whole feature is a timer.
All you need is just few lines of code:

```python
import types
import sched
import asyncgui

s = sched.scheduler()

# Wrapping 'scheduler.enter()' only takes three lines of code
@types.coroutine
def sleep(duration, *, priority=10):
    yield lambda task: s.enter(duration, priority, task._step)


async def main():
    print('A')
    await sleep(1)  # Now you can sleep in an async-manner
    print('B')
    await sleep(1)
    print('C')

asyncgui.start(main())
s.run()
```

And you already have structured concurrency apis as well:

```python
async def print_numbers():
    for i in range(10):
        await sleep(.1)
        print(i)


async def print_letters():
    for c in "ABCDE":
        await sleep(.1)
        print(c)


async def main():
    # Let print_letters() and print_numbers() race.
    # As soon as any of them finishes, the other one gets cancelled.
    tasks = await asyncgui.wait_any(print_letters(), print_numbers())
    if tasks[0].finished:
        print("print_letters() won")
    else:
        print("print_numbers() won")
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
print_letters() won
main end
```

## Why not asyncio ?

The above example may not attract you because you can just replace `sched` with [asyncio](https://docs.python.org/3/library/asyncio.html) or [Trio](https://trio.readthedocs.io/en/stable/),
and can use thier respective sleep function (`asyncio.sleep` and `trio.sleep`).
But in a read-world situation, that might not be an option:
Kivy required [massive changes](https://github.com/kivy/kivy/pull/6368) in order to adapt to `asyncio` and `Trio`,
[asyncio-tkinter](https://github.com/fluentpython/asyncio-tkinter)'s codebase is quite big as well.

The reason they needed lots of work is that they had to merge two event-loops into one.
One is from the gui libraries. The other one is from async libraries.
You cannot just simply run multiple event-loops simultaneously in one thread.

On the other hand, `asyncgui` doesn't require a lot of work as shown above **because it doesn't have an event-loop**.
`asyncgui` and a library that has an event-loop can live in the same thread seamlessly because of it.

## So, is asyncgui superior to asyncio ?

No, it is not.
For `asyncgui`, many features that exist in `asyncio` are either impossible or hard to implement because of the lack of event-loop.
The implementation of those features needs to be specific to each event-loop.
You've already witnessed one, the `sleep`.

## asyncgui is not usefull then.

There is at least one situation that `asyncgui` shines.
When you are creating a gui app, you probably want the app to quickly react to its gui events, like pressing a button.
This is problematic for `asyncio` because it cannot immediately start/resume a task.
It can schedule a task to *eventually* start/resume but not *immediate*,
which causes to [spill gui events](https://github.com/gottadiveintopython/asynckivy/blob/main/examples/misc/why_asyncio_is_not_suitable_for_handling_touch_events.py).
As a result, you need to use callback-based apis for that, and thus you cannot fully receive the benefits of async/await.

If you use `asyncgui`, that never happens because:

- `asyncgui.start()` immediately starts a task.
- `asyncgui.Event.set()` immediately resumes the tasks waiting for it to happen.

In summary, if your program needs to react to something immediately, `asyncgui` is for you.
Otherwise, it's probably not worth it.

## Installation

It's recommended to pin the minor version, because if it changed, it means some *important* breaking changes occurred.

```text
poetry add asyncgui@~0.5
pip install "asyncgui>=0.5,<0.6"
```

## Tested on

- CPython 3.8
- CPython 3.9
- CPython 3.10
- CPython 3.11

## Async-libraries who relies on this

- [asynckivy](https://github.com/gottadiveintopython/asynckivy)
- [asynctkinter](https://github.com/gottadiveintopython/asynctkinter)
