# AsyncGui

...is a minimalistic async library that:

- does not provide features involving system calls, such as I/O.
- has no external dependencies when using Python 3.11 or later.
- does not own a main loop, but is designed to integrate with an existing one.
- avoids global state.
- focuses on fast responsiveness, allowing immediate task start and resumption.
- offers powerful "structured concurrency" features inspired by [Trio](https://trio.readthedocs.io/en/stable/) and [trio-util](https://trio-util.readthedocs.io/en/latest/).
- has nothing to do with GUIs, even though it has 'gui' in its name. (I should rename it at some point.)

[Documentation](https://asyncgui.github.io/asyncgui/)

## Installation

Pin the minor version.

```text
poetry add asyncgui@~0.9
pip install "asyncgui>=0.9,<0.10"
```

## Tested on

- CPython 3.10
- CPython 3.11
- CPython 3.12
- CPython 3.13
- CPython 3.14
- PyPy 3.10

## Dependants

- [asynckivy](https://github.com/asyncgui/asynckivy)
- [asynctkinter](https://github.com/asyncgui/asynctkinter)
- [asynctkinter-minimum](https://github.com/asyncgui/asynctkinter-minimum)
- [asyncpygame](https://github.com/asyncgui/asyncpygame)
