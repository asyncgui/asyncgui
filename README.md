# AsyncGui

...is a minimalistic async library that:

- does not provide features involving system calls, such as I/O, time retrieval, thread suspension, or thread spawning.
- has no external dependencies when using Python 3.11 or later.
- does not own a main loop, but is designed to integrate with an existing one.
- avoids global state.
- focuses on fast responsiveness, allowing immediate task start and resumption.
- offers powerful structured concurrency APIs inspired by [Trio](https://trio.readthedocs.io/en/stable/) and [trio-util](https://trio-util.readthedocs.io/en/latest/).
- has nothing to do with GUIs, even though it has 'gui' in its name. (Yes, I should rename it at some point.)

[Documentation](https://asyncgui.github.io/asyncgui/)

## Installation

Pin the minor version.

```text
poetry add asyncgui@~0.7
pip install "asyncgui>=0.7,<0.8"
```

## Tested on

- CPython 3.9
- CPython 3.10
- CPython 3.11
- CPython 3.12 (3.12.1 or later)
- CPython 3.13
- PyPy 3.10

## Async libraries that rely on this

- [asynckivy](https://github.com/asyncgui/asynckivy)
- [asynctkinter](https://github.com/asyncgui/asynctkinter)
- [asyncpygame](https://github.com/asyncgui/asyncpygame)
