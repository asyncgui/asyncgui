# AsyncGui

Async library that works on top of an existing event loop.
This is not for application developers, but for async-library developers.

## Pin the minor version

If you use this module, it's recommended to pin the minor version, because if it changed, it usually means some breaking changes occurred.

## Test Environment

- CPython 3.7
- CPython 3.8
- CPython 3.9

## Async-libraries who use this

- [asynckivy](https://github.com/gottadiveintopython/asynckivy)
- [asynctkinter](https://github.com/gottadiveintopython/asynctkinter)

## TODO

- `Trio` -> `asyncgui` 方向へのadaptor
- implement `asyncio.Queue` equivalent
- implement `trio.Semaphore` equivalent`
