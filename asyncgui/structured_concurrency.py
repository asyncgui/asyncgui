'''
Structured Concurrency
======================


.. warning::

    **User-defined BaseException is not supported.**
    The structured concurrency api assumes all the user-defined exceptions are
    Exception (or subclass thereof). If you violate this, the api won't work
    properly.
'''

__all__ = ('and_from_iterable', 'and_', )

from typing import Iterable, List, Awaitable
from contextlib import contextmanager
from ._core import Task, Awaitable_or_Task


def do_nothing():
    pass


@contextmanager
def _raw_cancel_protection(task):
    '''
    taskが実行中である時のみ使える非async版の ``asyncgui.cancel_protection()``。
    少し速くなることを期待しているが その成果は不明。
    '''
    task._cancel_protection += 1
    try:
        yield
    finally:
        task._cancel_protection -= 1


async def and_from_iterable(aws: Iterable[Awaitable_or_Task]) \
        -> Awaitable[List[Task]]:
    '''
    and_from_iterable
    =================

    Run multiple tasks concurrently, and wait for all of their completion
    or cancellation. When one of the tasks raises an exception, the rest will
    be cancelled, and the exception will be propagated to the caller, like
    Trio's Nursery does.

    Fair Start
    ----------

    Even if one of the tasks raises an exception while there are still ones
    that haven't started yet, they still will start (and will be cancelled
    soon).
    '''
    from ._core import start, get_current_task, Task, sleep_forever
    from .exceptions import MultiError, EndOfConcurrency

    children = [v if isinstance(v, Task) else Task(v) for v in aws]
    if not children:
        return children
    child_exceptions = []
    n_left = len(children)
    resume_parent = do_nothing

    def on_child_end(child):
        nonlocal n_left
        n_left -= 1
        if child._exception is not None:
            child_exceptions.append(child._exception)
        resume_parent()

    parent = await get_current_task()

    try:
        parent._has_children = True
        for child in children:
            child._suppresses_exception = True
            child._event.add_callback(on_child_end)
            start(child)
        if child_exceptions or parent._cancel_called:
            raise EndOfConcurrency
        resume_parent = parent._step_coro
        while n_left:
            await sleep_forever()
            if child_exceptions:
                raise EndOfConcurrency
        return children
    except EndOfConcurrency:
        resume_parent = do_nothing
        for child in children:
            child.cancel()
        if n_left:
            resume_parent = parent._step_coro
            with _raw_cancel_protection(parent):
                while n_left:
                    await sleep_forever()
        if child_exceptions:
            # ここに辿り着いたという事は
            # (A) 自身に明示的な中断がかけられて全ての子を中断した所、その際に子で例外
            # が起きた
            # (B) 自身に明示的な中断はかけられていないが子で例外が自然発生した
            # のどちらかを意味する。
            # どちらの場合も例外を外側へ運ぶ。
            raise MultiError(child_exceptions)
        else:
            # ここに辿り着いたという事は、自身に明示的な中断がかけられて全ての子を中断
            # したものの、その際に子で全く例外が起こらなかった事を意味する。この場合は
            # 自身を中断させる。
            parent._has_children = False
            await sleep_forever()
    finally:
        parent._has_children = False
        resume_parent = do_nothing


def and_(*aws: Iterable[Awaitable_or_Task]) -> Awaitable[List[Task]]:
    """See ``and_from_iterable``'s doc"""
    return and_from_iterable(aws)
