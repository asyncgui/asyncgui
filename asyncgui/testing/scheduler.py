__all__ = ('open_scheduler', )


from contextlib import contextmanager


@contextmanager
def open_scheduler():
    import types
    import sched
    import asyncgui

    s = sched.scheduler()

    @types.coroutine
    def sleep(duration):
        yield lambda step_coro: s.enter(duration, 10, step_coro)

    def close_soon(coro):
        s.enter(0, 0, coro.close)

    try:
        asyncgui._core.install(close_soon=close_soon)
        yield (s, sleep)
        s.run()
    finally:
        asyncgui._core.uninstall(close_soon=close_soon)
