__all__ = (
    'start', 'sleep_forever', 'Event', 'Task', 'TaskState',
    'get_current_task', 'aclosing', 'Awaitable_or_Task',
    'cancel_protection', 'dummy_task', 'checkpoint',
)

import itertools
import types
import typing
from inspect import (
    getcoroutinestate, CORO_CLOSED, CORO_RUNNING, isawaitable,
)
import enum

from asyncgui.exceptions import (
    InvalidStateError, EndOfConcurrency,
)


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
    '''
    Task
    ====
    '''

    __slots__ = (
        'name', '_uid', '_root_coro', '_state', '_result', '_on_end',
        '_cancel_called', 'userdata', '_exception', '_suppresses_exception',
        '_cancel_protection', '_has_children', '__weakref__',
    )

    _uid_iter = itertools.count()

    def __init__(self, awaitable, *, name='', userdata=None):
        if not isawaitable(awaitable):
            raise ValueError(str(awaitable) + " is not awaitable.")
        self._uid = next(self._uid_iter)
        self.name = name
        self.userdata = userdata
        self._cancel_protection = 0
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
    def root_coro(self) -> typing.Coroutine:
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
                coro.throw(EndOfConcurrency)(self)
            except StopIteration:
                pass
            else:
                if not self._cancel_protection:
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
        return (not self._cancel_protection) and getcoroutinestate(self._root_coro) != CORO_RUNNING

    def _step_coro(self, *args, **kwargs):
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


class cancel_protection:
    '''
    (experimental) Async context manager that protects the code-block from
    cancellation even if it contains 'await'.

    .. code-block:: python

       async with asyncgui.cancel_protection():
           await something1()
           await something2()
    '''

    __slots__ = ('_task', )

    async def __aenter__(self):
        self._task = task = await get_current_task()
        task._cancel_protection += 1

    async def __aexit__(self, *__):
        self._task._cancel_protection -= 1


async def checkpoint():
    '''
    (experimental) If the ``.cancel()`` method of the current task has been
    called and the task is not protected from cancellation, cancels the task
    immediately. Otherwise, does nothing.
    '''
    task = await get_current_task()
    if task._cancel_called and not task._cancel_protection:
        await sleep_forever()


Awaitable_or_Task = typing.Union[typing.Awaitable, Task]


def start(awaitable_or_task: Awaitable_or_Task) -> Task:
    '''Starts an asyncgui-flavored awaitable or a Task.

    If the argument is a Task, itself will be returned. If it's an awaitable,
    it will be wrapped in a Task, and the Task will be returned.
    '''
    if isawaitable(awaitable_or_task):
        task = Task(awaitable_or_task)
    elif isinstance(awaitable_or_task, Task):
        task = awaitable_or_task
        if task._state is not TaskState.CREATED:
            raise ValueError(f"{task} was already started")
    else:
        raise ValueError("Argument must be either of a Task or an awaitable.")

    try:
        task._root_coro.send(None)(task)
    except StopIteration:
        pass
    else:
        if task._cancel_called and task._is_cancellable:
            task._actual_cancel()

    return task


@types.coroutine
def sleep_forever():
    return (yield lambda task: None)


class Event:
    '''Similar to 'trio.Event'. The difference is this one allows the user to
    pass value:

    .. code-block:: python

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
            task._step_coro(value)

    def clear(self):
        self._flag = False

    @types.coroutine
    def wait(self):
        if self._flag:
            return self._value
        else:
            return (yield self._waiting_tasks.append)[0][0]


@types.coroutine
def get_current_task() -> Task:
    '''Returns the current task.'''
    return (yield lambda task: task._step_coro(task))[0][0]


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
