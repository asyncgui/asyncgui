__all__ = (
    'ExceptionGroup', 'BaseExceptionGroup', 'InvalidStateError', 'StopConcurrentExecution',
    'Aw_or_Task', 'start', 'Task', 'TaskState', 'current_task',
    'aclosing', 'sleep_forever', 'Event', 'disable_cancellation', 'dummy_task', 'check_cancellation',
    'wait_all', 'wait_any', 'run_and_cancelling',
)
import types
import typing as t
from inspect import getcoroutinestate, CORO_CLOSED, CORO_RUNNING, isawaitable
import sys
import itertools
import enum


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------
if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup, ExceptionGroup
else:
    BaseExceptionGroup = BaseExceptionGroup
    ExceptionGroup = ExceptionGroup


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class StopConcurrentExecution(BaseException):
    """(internal) Not an actual error. Used for flow control."""


# -----------------------------------------------------------------------------
# Core (Task Runner)
# -----------------------------------------------------------------------------

class TaskState(enum.Flag):
    CREATED = enum.auto()
    '''CORO_CREATED'''

    STARTED = enum.auto()
    '''CORO_RUNNING or CORO_SUSPENDED'''

    CANCELLED = enum.auto()
    '''CORO_CLOSED by 'coroutine.close()' or an uncaught exception'''

    DONE = enum.auto()
    '''CORO_CLOSED (completed)'''

    ENDED = CANCELLED | DONE


def _do_nothing(*args):
    pass


class Task:
    __slots__ = (
        'name', '_uid', '_root_coro', '_state', '_result', '_on_end',
        '_cancel_called', 'userdata', '_exception', '_suppresses_exception',
        '_disable_cancellation', '_has_children', '__weakref__',
    )

    _uid_iter = itertools.count()

    def __init__(self, awaitable, *, name='', userdata=None):
        if not isawaitable(awaitable):
            raise ValueError(str(awaitable) + " is not awaitable.")
        self._uid = next(self._uid_iter)
        self.name = name
        self.userdata = userdata
        self._disable_cancellation = 0
        self._has_children = False
        self._root_coro = self._wrapper(awaitable)
        self._state = TaskState.CREATED
        self._on_end = _do_nothing
        self._cancel_called = False
        self._exception = None
        self._suppresses_exception = False

    def __str__(self):
        return f'Task(state={self._state.name}, uid={self._uid}, name={self.name!r})'

    @property
    def uid(self) -> int:
        return self._uid

    @property
    def root_coro(self) -> t.Coroutine:
        return self._root_coro

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def done(self) -> bool:
        return self._state is TaskState.DONE

    @property
    def cancelled(self) -> bool:
        return self._state is TaskState.CANCELLED

    @property
    def result(self):
        '''Result of the task. If the task hasn't finished yet,
        InvalidStateError will be raised.
        '''
        state = self._state
        if state is TaskState.DONE:
            return self._result
        elif state is TaskState.CANCELLED:
            raise InvalidStateError(f"{self} was cancelled")
        else:
            raise InvalidStateError(f"Result of {self} is not ready")

    async def _wrapper(self, awaitable):
        try:
            self._state = TaskState.STARTED
            self._result = await awaitable
        except Exception as e:
            self._state = TaskState.CANCELLED
            if self._suppresses_exception:
                self._exception = e
            else:
                raise
        except:  # noqa: E722
            self._state = TaskState.CANCELLED
            raise
        else:
            self._state = TaskState.DONE
        finally:
            self._on_end(self)

    def cancel(self):
        '''Cancel the task as soon as possible'''
        self._cancel_called = True
        if self._is_cancellable:
            self._actual_cancel()

    def _actual_cancel(self):
        coro = self._root_coro
        if self._has_children:
            try:
                coro.throw(StopConcurrentExecution)(self)
            except StopIteration:
                pass
            else:
                if not self._disable_cancellation:
                    coro.close()
        else:
            coro.close()
            if self._state is TaskState.CREATED:
                self._state = TaskState.CANCELLED

    # give 'cancel()' an alias so that we can cancel tasks just like we close
    # coroutines.
    close = cancel

    @property
    def _is_cancellable(self) -> bool:
        '''Whether the task can immediately be cancelled.'''
        return (not self._disable_cancellation) and getcoroutinestate(self._root_coro) != CORO_RUNNING

    def _step(self, *args, **kwargs):
        coro = self._root_coro
        try:
            if getcoroutinestate(coro) != CORO_CLOSED:
                coro.send((args, kwargs, ))(self)
        except StopIteration:
            pass
        else:
            if self._cancel_called and self._is_cancellable:
                self._actual_cancel()

    def _throw_exc(self, exc):
        coro = self._root_coro
        if self._state is not TaskState.STARTED:
            raise InvalidStateError("Throwing an exception to an unstarted/finished/cancelled task is not allowed.")
        try:
            coro.throw(exc)(self)
        except StopIteration:
            pass
        else:
            if self._cancel_called and self._is_cancellable:
                self._actual_cancel()


Aw_or_Task = t.Union[t.Awaitable, Task]


def start(aw: Aw_or_Task) -> Task:
    '''Starts an asyncgui-flavored awaitable or a Task.

    If the argument is a Task, itself will be returned. If it's an awaitable,
    it will be wrapped in a Task, and the Task will be returned.
    '''
    if isawaitable(aw):
        task = Task(aw)
    elif isinstance(aw, Task):
        task = aw
        if task._state is not TaskState.CREATED:
            raise ValueError(f"{task} was already started")
    else:
        raise ValueError("Argument must be either a Task or an awaitable.")

    try:
        task._root_coro.send(None)(task)
    except StopIteration:
        pass
    else:
        if task._cancel_called and task._is_cancellable:
            task._actual_cancel()

    return task


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

@types.coroutine
def current_task() -> t.Awaitable[Task]:
    '''Returns the Task instance corresponding to the caller.'''
    return (yield lambda task: task._step(task))[0][0]


class disable_cancellation:
    '''
    (experimental)
    Async context manager that protects its code-block from cancellation.

    .. code-block::

        await something      # <- might get cancelled
        async with disable_cancellation():
            await something  # <- never gets cancelled
            await something  # <- never gets cancelled
        await something      # <- might get cancelled
    '''

    __slots__ = ('_task', )

    async def __aenter__(self):
        self._task = task = await current_task()
        task._disable_cancellation += 1

    async def __aexit__(self, *__):
        self._task._disable_cancellation -= 1


async def check_cancellation():
    '''
    (experimental) If the ``.cancel()`` method of the current task has been
    called and the task is not protected from cancellation, cancels the task
    immediately. Otherwise, does nothing.
    '''
    task = await current_task()
    if task._cancel_called and not task._disable_cancellation:
        await sleep_forever()


@types.coroutine
def sleep_forever():
    return (yield lambda task: None)


class Event:
    '''Similar to 'trio.Event'. The difference is this one allows the user to
    pass value:

    .. code-block::

        import asyncgui as ag

        e = ag.Event()
        async def task():
            assert await e.wait() == 'A'
        ag.start(task())
        e.set('A')
    '''
    __slots__ = ('_value', '_flag', '_waiting_tasks', '__weakref__', )

    def __init__(self):
        self._value = None
        self._flag = False
        self._waiting_tasks = []

    def is_set(self):
        return self._flag

    def set(self, value=None):
        if self._flag:
            return
        self._flag = True
        self._value = value
        waiting_tasks = self._waiting_tasks
        self._waiting_tasks = []
        for task in waiting_tasks:
            task._step(value)

    def clear(self):
        self._flag = False

    @types.coroutine
    def wait(self):
        if self._flag:
            return self._value
        else:
            return (yield self._waiting_tasks.append)[0][0]


class aclosing:
    '''(experimental)
    async version of 'contextlib.closing()'.
    '''

    __slots__ = ('_agen', )

    def __init__(self, agen):
        self._agen = agen

    async def __aenter__(self):
        return self._agen

    async def __aexit__(self, *__):
        await self._agen.aclose()


dummy_task = Task(sleep_forever(), name='asyncgui.dummy_task')
dummy_task.cancel()


class _raw_disable_cancellation:
    '''
    (internal)
    taskが実行中である時のみ使える非async版の ``asyncgui.disable_cancellation()``。
    少し速くなることを期待しているが その成果は不明。
    '''

    __slots__ = ('_task', )

    def __init__(self, task):
        self._task = task

    def __enter__(self):
        self._task._disable_cancellation += 1

    def __exit__(self, *__):
        self._task._disable_cancellation -= 1


# -----------------------------------------------------------------------------
# Utilities (Structured Concurrency)
# -----------------------------------------------------------------------------


async def wait_all(*aws: t.Iterable[Aw_or_Task]) -> t.Awaitable[t.List[Task]]:  # noqa: C901
    '''
    Run multiple tasks concurrently, and wait for all of their completion
    or cancellation. When one of the tasks raises an exception, the others will
    be cancelled, and the exception will be propagated to the caller, like
    Trio's Nursery does.

    Fair Start
    ----------

    Even if one of the tasks raises an exception while there are still ones
    that haven't started yet, they still will start (and will be cancelled
    soon).
    '''
    children = [v if isinstance(v, Task) else Task(v) for v in aws]
    if not children:
        return children
    child_exceptions = []
    n_left = len(children)
    resume_parent = _do_nothing

    def on_child_end(child):
        nonlocal n_left
        n_left -= 1
        if child._exception is not None:
            child_exceptions.append(child._exception)
        resume_parent()

    parent = await current_task()

    try:
        parent._has_children = True
        for child in children:
            child._suppresses_exception = True
            child._on_end = on_child_end
            start(child)
        if child_exceptions or parent._cancel_called:
            raise StopConcurrentExecution
        resume_parent = parent._step
        while n_left:
            await sleep_forever()
            if child_exceptions:
                raise StopConcurrentExecution
        return children
    except StopConcurrentExecution:
        resume_parent = _do_nothing
        for child in children:
            child.cancel()
        if n_left:
            resume_parent = parent._step
            with _raw_disable_cancellation(parent):
                while n_left:
                    await sleep_forever()
        if child_exceptions:
            # ここに辿り着いたという事は
            # (A) 自身に明示的な中断がかけられて全ての子を中断した所、その際に子で例外が起きた
            # (B) 自身に明示的な中断はかけられていないが子で例外が自然発生した
            # のどちらかを意味する。どちらの場合も例外を外側へ運ぶ。
            raise ExceptionGroup("One or more exceptions occurred in child tasks.", child_exceptions)
        else:
            # ここに辿り着いたという事は、自身に明示的な中断がかけられて全ての子を中断
            # したものの、その際に子で全く例外が起こらなかった事を意味する。この場合は
            # 自身を中断させる。
            parent._has_children = False
            await sleep_forever()
    finally:
        parent._has_children = False
        resume_parent = _do_nothing


async def wait_any(*aws: t.Iterable[Aw_or_Task]) -> t.Awaitable[t.List[Task]]:  # noqa: C901
    '''
    Run multiple tasks concurrently, and wait for any of them to complete.
    As soon as that happens, the others will be cancelled, and the function will
    return.

    .. code-block::

        e = asyncgui.Event()

        async def async_fn():
            ...

        tasks = await wait_any(async_fn(), e.wait())
        if tasks[0].done:
            print("async_fn() was completed")
        else:
            print("The event was set")

    When one of the tasks raises an exception, the rest will be cancelled, and
    the exception will be propagated to the caller, like Trio's Nursery does.

    Fair Start
    ----------

    Like ``wait_all()``, when one of the tasks:
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

            async def main():
                tasks = await ag.wait_any(child1, child2)
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

        ``wait_any()``が正常に終了した時に常に一つだけ子taskが完了しているとは限らない事に注意されたし。
        例えば次のように即座に完了する子が複数ある場合はその全てが完了する。

        .. code-blobk::

            async def f():
                pass

            tasks = await wait_any(f(), f())
            assert tasks[0].done
            assert tasks[1].done

        また次の例も両方の子が完了する。

        .. code-blobk::

            async def f_1(e):
                await e.wait()

            async def f_2(e):
                e.set()

            e = asyncgui.Event()
            tasks = await wait_any([f_1(e), f_2(e))
            assert tasks[0].done
            assert tasks[1].done

        これは``e.set()``が呼ばれた事で``f_1()``が完了するが、その後``f_2()``が中断可能
        な状態にならないまま完了するためでる。中断可能な状態とは何かと言うと

        * 中断に対する保護がかかっていない(保護は`async with disable_cancellation()`でかかる)
        * Taskが停まっている(await式の地点で基本的に停まるが、停まらない例外としては ``await current_task()`` , ``await set済のEvent.wait()`` がある)

        の両方を満たしている状態の事で、上のcodeでは``f_2``が``e.set()``を呼んだ後に停止
        する事が無かったため中断される事なく完了する事になった。
    '''
    children = [v if isinstance(v, Task) else Task(v) for v in aws]
    if not children:
        return children
    child_exceptions = []
    n_left = len(children)
    at_least_one_child_has_done = False
    resume_parent = _do_nothing

    def on_child_end(child):
        nonlocal n_left, at_least_one_child_has_done
        n_left -= 1
        if child._exception is not None:
            child_exceptions.append(child._exception)
        elif child.done:
            at_least_one_child_has_done = True
        resume_parent()

    parent = await current_task()

    try:
        parent._has_children = True
        for child in children:
            child._suppresses_exception = True
            child._on_end = on_child_end
            start(child)
        if child_exceptions or at_least_one_child_has_done or parent._cancel_called:
            raise StopConcurrentExecution
        resume_parent = parent._step
        while n_left:
            await sleep_forever()
            if child_exceptions or at_least_one_child_has_done:
                raise StopConcurrentExecution
        # ここに辿り着いたという事は
        #
        # (1) 全ての子が中断された
        # (2) 親には中断はかけられていない
        # (3) 例外が全く起こらなかった
        #
        # の３つを同時に満たした事を意味する。この場合は一つも子taskが完了していない状態で関数が返る。
        return children
    except StopConcurrentExecution:
        resume_parent = _do_nothing
        for child in children:
            child.cancel()
        if n_left:
            resume_parent = parent._step
            with _raw_disable_cancellation(parent):
                while n_left:
                    await sleep_forever()
        if child_exceptions:
            raise ExceptionGroup("One or more exceptions occurred in child tasks.", child_exceptions)
        if parent._cancel_called:
            parent._has_children = False
            await sleep_forever()
            assert False, f"{parent} was not cancelled"
        assert at_least_one_child_has_done
        return children
    finally:
        parent._has_children = False
        resume_parent = _do_nothing


class run_and_cancelling:
    '''
    Almost same as :func:`trio_util.run_and_cancelling`.
    The difference is that this one is a regular context manager not an async one.
    '''

    __slots__ = ('_aw', '_task', )

    def __init__(self, aw: Aw_or_Task):
        self._aw = aw

    def __enter__(self):
        self._task = start(self._aw)

    def __exit__(self, *__):
        self._task.cancel()
