# AsyncGui

A thin layer that helps to wrap a callback-style API in an async/await-style API.

## How to use

Despite its name, the application of `asyncgui` is **not** limited to gui programs.
You can wrap any kind of callback-based APIs in it.
The simplest example of it would be [sched](https://docs.python.org/3/library/sched.html),
whose the whole feature is timer.
All you need is just few lines of code:

```python
import sched
import asyncgui

s = sched.scheduler()

# Wrapping 'scheduler.enter()'
async def sleep(duration, *, priority=10):
    sig = asyncgui.ISignal()
    event = s.enter(duration, priority, sig.set)
    try:
        await sig.wait()
    except asyncgui.Cancelled:
        s.cancel(event)
        raise


async def main():
    print('A')
    await sleep(1)  # Now you can sleep in an async-manner
    print('B')
    await sleep(1)
    print('C')


asyncgui.start(main())
s.run()
```

And you already have structured concurrency APIs as well:

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

## Installation

It's recommended to pin the minor version, because if it changed, it means some *important* breaking changes occurred.

```text
poetry add asyncgui@~0.6
pip install "asyncgui>=0.6,<0.7"
```

## Tested on

- CPython 3.8
- CPython 3.9
- CPython 3.10
- CPython 3.11
- CPython 3.12 (3.12.1 or later)

## Async-libraries who relies on this

- [asyncsched](https://github.com/asyncgui/asyncsched)
- [asynckivy](https://github.com/asyncgui/asynckivy)
- [asynctkinter](https://github.com/asyncgui/asynctkinter)
- [asyncpygame](https://github.com/asyncgui/asyncpygame)
