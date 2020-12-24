# AsyncGui

An async library that works on top of an existing gui event loop.
This is not for application developers, but for async-library developers.

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
