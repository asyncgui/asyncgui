__all__ = ('open_scheduler', )


from contextlib import contextmanager


@contextmanager
def open_scheduler():
    import types
    import sched

    s = sched.scheduler()

    @types.coroutine
    def sleep(duration):
        yield lambda step_coro: s.enter(duration, 10, step_coro)

    yield (s, sleep)
    s.run()
