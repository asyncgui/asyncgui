# AsyncGui

A thin layer that helps to build an async/await-based api using a callback-based api.

## How to use

Despite its name, `asyncgui` has nothing to do with gui.
You can wrap any kind of callback-based api in it.
The simplest example of it would be [sched](https://docs.python.org/3/library/sched.html),
whose the whole feature is a timer.
All you need is just few lines of code:

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
    await sleep(1)  # Now you can sleep in an async-manner
    print('B')
    await sleep(1)
    print('C')

asyncgui.start(main())
s.run()
```

And you already have a structured concurrency api as well:

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
    from asyncgui.structured_concurrency import or_
    # Let print_letters() and print_numbers() race.
    # As soon as one of them finishes, the other one gets cancelled.
    tasks = await or_(print_letters(), print_numbers())
    if tasks[0].done:
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
and can use thier sleep function (`asyncio.sleep` and `trio.sleep`).
But in a read-world situation, that might not be an option:
Kivy required [massive changes](https://github.com/kivy/kivy/pull/6368) in order to adapt to `asyncio` and `Trio`,
[asyncio-tkinter](https://github.com/fluentpython/asyncio-tkinter)'s codebase is quite big as well.

The reason they needed lots of work is that they had to merge two event-loops into one.
One is from the gui libraries. The other one is from async libraries.
You cannot just simply run multiple event-loops simultaneously in one thread...
maybe.

On the other hand, `asyncgui` doesn't require a lot of work as shown above **because it doesn't have an event-loop**.
`asyncgui` and a library who has an event-loop can live in the same thread seemlessly because of it.

## So, is asyncgui superior to asyncio ?

No, it is not.
For `asyncgui`, many features that exist in `asyncio` are either impossible or hard to implement because of the lack of event-loop.
Thus those features need to be specific to each event-loop you are using.
You've already witnessed one, the `sleep`.

## asyncgui is not usefull then.

There is at least one situation where `asyncgui` shines.
When you are creating a gui app, you probably want the app to quickly react to the gui events, like pressing a button.
This is problematic for `asyncio` because it cannot immediately start/resume a task.
It can schedule a task to *eventually* start/resume but not *immediate*,
which causes to [spill gui events](https://github.com/gottadiveintopython/asynckivy/blob/main/examples/misc/why_asyncio_is_not_suitable_for_handling_touch_events.py).
As a result, you need to use callback-based api for that, and thus you cannot fully receive the benefits of async/await.

If you use `asyncgui`, that never happens because:

- `asyncgui.start()` immediately starts a task.
- `asyncgui.Event.set()` immediately resumes the tasks waiting for it to happen.

In summary, if your program needs to react to something immediately, `asyncgui` is for you.
Otherwise, it's probably not worth it.

## Installation

If you use this module, it's recommended to pin the minor version, because if it changed, it means some *important* breaking changes occurred.

```text
poetry add asyncgui@~0.5
pip install "asyncgui>=0.5,<0.6"
```

## Tested on

- CPython 3.7
- CPython 3.8
- CPython 3.9
- CPython 3.10

## Async-libraries who relies on this

- [asynckivy](https://github.com/gottadiveintopython/asynckivy)
- [asynctkinter](https://github.com/gottadiveintopython/asynctkinter)
