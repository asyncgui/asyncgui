__all__ = ('open_scheduler', )


from contextlib import contextmanager


@contextmanager
def open_scheduler():
    import types
    import sched

    s = sched.scheduler()

    @types.coroutine
    def sleep(duration):
        yield lambda task: s.enter(duration, 10, task._step_coro)

    yield (s, sleep)
    s.run()
