# AsyncGui

...is a minimalistic async library that:

- does not provide features involving system calls, such as I/O.
- has no external dependencies.
- does not own a main loop, but is designed to integrate with an existing one.
- avoids global state.
- focuses on fast responsiveness, allowing immediate task start and resumption.
- offers powerful "structured concurrency" features inspired by [Trio](https://trio.readthedocs.io/en/stable/) and [trio-util](https://trio-util.readthedocs.io/en/latest/).
- has nothing to do with GUIs, even though it has `"gui"` in its name.

[Documentation](https://asyncgui.github.io/asyncgui/)

## Installation

Pin the minor version.

```text
pip install "asyncgui>=0.11,<0.12"
```

## Tested on

- CPython 3.11
- CPython 3.12
- CPython 3.13
- CPython 3.14
- CPython 3.15
- PyPy 3.11

## Dependants

- [asynckivy](https://github.com/asyncgui/asynckivy)
- [asynctkinter2](https://github.com/asyncgui/asynctkinter2)
- [asyncpygame](https://github.com/asyncgui/asyncpygame)
