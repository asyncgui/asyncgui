'''
Structured Concurrency
======================


.. warning::

    **User-defined BaseException is not supported.**
    The structured concurrency api assumes all the user-defined exceptions are
    Exception (or subclass thereof). If you violate this, the api won't work
    properly.
'''

__all__ = ('and_from_iterable', 'and_', 'or_from_iterable', 'or_', )

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


async def or_from_iterable(aws: Iterable[Awaitable_or_Task]) \
        -> Awaitable[List[Task]]:
    '''
    or_from_iterable
    ================

    Run multiple tasks concurrently, and wait for one of them to complete.
    As soon as that happens, the rest will be cancelled, and the function will
    return.

    .. code-block::

       e = asyncgui.Event()

       async def async_fn():
           ...

       tasks = await or_(async_fn(), e.wait())
       if tasks[0].done:
           print("async_fn() was completed")
       else:
           print("The event was set")

    When one of the tasks raises an exception, the rest will be cancelled, and
    the exception will be propagated to the caller, like Trio's Nursery does.

    Fair Start
    ----------

    Like ``and_from_iterable()``, when one of the tasks:
    A) raises an exception
    B) completes
    while there are still ones that haven't started yet, they still will
    start, (and will be cancelled soon).

    Chance of zero tasks to complete
    --------------------------------

    When all the tasks are cancelled, and there are no exceptions to
    propagate, it would happen.

    .. code-block::

       def test_cancel_all_children():
           import asyncgui as ag
           from asyncgui.structured_concurrency import or_

           async def main():
               tasks = await or_(child1, child2)
               for task in tasks:
                   assert task.cancelled  # NO TASKS HAVE COMPLETED

           child1 = ag.Task(ag.sleep_forever())
           child2 = ag.Task(ag.sleep_forever())
           main_task = ag.start(main())
           child1.cancel()
           child2.cancel()
           assert main_task.done

    Chance of multiple tasks to complete
    ------------------------------------

    .. warning::

        ``or_from_iterable()``が正常に終了した時に常に一つだけ子taskが完了しているとは
        限らない事に注意されたし。例えば次のように即座に完了する子が複数ある場合はその全てが
        完了する。

        .. code-blobk::

           async def f():
               pass

           tasks = await or_from_iterable([f(), f(), ])
           assert tasks[0].done
           assert tasks[1].done

        また次の例も両方の子が完了する。

        .. code-blobk::

           async def f_1(e):
               await e.wait()

           async def f_2(e):
               e.set()

           e = asyncgui.Event()
           tasks = await or_from_iterable([f_1(e), f_2(e), ])
           assert tasks[0].done
           assert tasks[1].done

        これは``e.set()``が呼ばれた事で``f_1()``が完了するが、その後``f_2()``が中断可能
        な状態にならないまま完了するためでる。中断可能な状態とは何かと言うと

        * 中断に対する保護がかかっていない(保護は`async with cancel_protection()`でか
          かる)
        * Taskが停まっている(await式の地点で基本的に停まる。停まらない例としては
          ``await get_current_task()``, ``await get_step_coro()``,
          ``await set済のEvent.wait()`` がある)

        の両方を満たしている状態の事で、上のcodeでは``f_2``が``e.set()``を呼んだ後に停止
        する事が無かったため中断される事なく完了する事になった。
    '''
    from ._core import start, get_current_task, Task, sleep_forever
    from .exceptions import MultiError, EndOfConcurrency

    children = [v if isinstance(v, Task) else Task(v) for v in aws]
    if not children:
        return children
    child_exceptions = []
    n_left = len(children)
    at_least_one_child_has_done = False
    resume_parent = do_nothing

    def on_child_end(child):
        nonlocal n_left, at_least_one_child_has_done
        n_left -= 1
        if child._exception is not None:
            child_exceptions.append(child._exception)
        elif child.done:
            at_least_one_child_has_done = True
        resume_parent()

    parent = await get_current_task()

    try:
        parent._has_children = True
        for child in children:
            child._suppresses_exception = True
            child._event.add_callback(on_child_end)
            start(child)
        if child_exceptions or at_least_one_child_has_done or \
                parent._cancel_called:
            raise EndOfConcurrency
        resume_parent = parent._step_coro
        while n_left:
            await sleep_forever()
            if child_exceptions or at_least_one_child_has_done:
                raise EndOfConcurrency
        # ここに辿り着いたという事は
        #
        # (1) 全ての子が中断された
        # (2) 親には中断はかけられていない
        # (3) 例外が全く起こらなかった
        #
        # の３つを同時に満たした事を意味する。この場合は一つも子taskが完了していな
        # い状態で関数が返る。
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
            raise MultiError(child_exceptions)
        if parent._cancel_called:
            parent._has_children = False
            await sleep_forever()
            assert False, f"{parent} was not cancelled"
        assert at_least_one_child_has_done
        return children
    finally:
        parent._has_children = False
        resume_parent = do_nothing


def or_(*aws: Iterable[Awaitable_or_Task]) -> Awaitable[List[Task]]:
    """See ``or_from_iterable``'s doc"""
    return or_from_iterable(aws)
