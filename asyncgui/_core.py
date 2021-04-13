__all__ = (
    'start', 'sleep_forever', 'Event', 'Task', 'TaskState',
    'get_current_task', 'get_step_coro', 'aclosing', 'Awaitable_or_Task',
    'unstructured_or', 'unstructured_and', 'raw_start',
)

import itertools
import types
import typing
from inspect import (
    getcoroutinestate, CORO_CLOSED, CORO_RUNNING, isawaitable,
)
import enum
from contextlib import asynccontextmanager

from asyncgui.exceptions import InvalidStateError


class TaskState(enum.Flag):
    CREATED = enum.auto()
    '''CORO_CREATED'''

    STARTED = enum.auto()
    '''CORO_RUNNING or CORO_SUSPENDED'''

    CANCELLED = enum.auto()
    '''CORO_CLOSED by 'Task.cancel()' or an uncaught exception'''

    DONE = enum.auto()
    '''CORO_CLOSED (coroutine was completed)'''

    ENDED = CANCELLED | DONE


class Task:
    '''
    Task
    ====

    (experimental)
    Similar to `asyncio.Task`. The main difference is that this one is not
    awaitable.

    .. code-block:: python

       import asyncgui as ag

       async def async_fn():
           task = ag.Task(some_awaitable, name='my_sub_task')
           ag.start(task)
           ...
           ...
           ...

           # case #1 wait for the completion of the task.
           await task.wait(ag.TaskState.DONE)
           print(task.result)

           # case #2 wait for the cancellation of the task.
           await task.wait(ag.TaskState.CANCELLED)

           # case #3 wait for either of completion or cancellation of the
           # task.
           await task.wait(ag.TaskState.ENDED)
           if task.done:
               print(task.result)

    Cancellation
    ------------

    Since coroutines aren't always cancellable, ``Task.cancel()`` may or may
    not fail depending on the internal state. If you don't have any specific
    reason to use it, use ``Task.safe_cancel()`` instead.
    '''

    __slots__ = ('name', '_uid', '_root_coro', '_state', '_result', '_event')

    _uid_iter = itertools.count()

    def __init__(self, awaitable, *, name=''):
        if not isawaitable(awaitable):
            raise ValueError(str(awaitable) + " is not awaitable.")
        self._uid = next(self._uid_iter)
        self.name: str = name
        self._root_coro = self._wrapper(awaitable)
        self._state = TaskState.CREATED
        self._event = Event()

    def __str__(self):
        return f'Task(uid={self._uid}, name={self.name!r})'

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
        '''Equivalent of asyncio.Future.result()'''
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
        except:  # noqa: E722
            self._state = TaskState.CANCELLED
            raise
        else:
            self._state = TaskState.DONE
        finally:
            self._event.set(self)

    def cancel(self):
        '''Cancel the task immediately'''
        self._root_coro.close()

    def safe_cancel(self):
        '''Cancel the task immediately if possible, otherwise cancel soon'''
        if self.is_cancellable:
            self.cancel()
        else:
            _close_soon(self._root_coro)

    # give 'cancel()' an alias so that we can cancel a Task like we close a
    # coroutine.
    close = cancel

    @property
    def is_cancellable(self) -> bool:
        return getcoroutinestate(self._root_coro) != CORO_RUNNING

    async def wait(self, wait_for: TaskState=TaskState.ENDED):
        '''Wait for the Task to be cancelled or done.

        'wait_for' must be one of the following:

            TaskState.DONE
            TaskState.CANCELLED
            TaskState.ENDED (default)
        '''
        if wait_for & (~TaskState.ENDED):
            raise ValueError("'wait_for' is incorrect:", wait_for)
        await self._event.wait()
        if self.state & wait_for:
            return
        await sleep_forever()


Awaitable_or_Task = typing.Union[typing.Awaitable, Task]


def _default_close_soon(coro: typing.Coroutine):
    raise NotImplementedError


_close_soon = _default_close_soon


def install(*, close_soon):
    '''(internal)'''
    global _close_soon
    if _close_soon is not _default_close_soon:
        raise InvalidStateError("There is already one installed")
    if not callable(close_soon):
        raise ValueError(f"{close_soon!r} must be callable")
    _close_soon = close_soon


def uninstall(*, close_soon):
    '''(internal)'''
    global _close_soon
    if _close_soon is _default_close_soon:
        raise InvalidStateError("Nothing is installed")
    if _close_soon is not close_soon:
        raise ValueError(f"{close_soon!r} is not installed")
    _close_soon = _default_close_soon


def start(awaitable_or_task: Awaitable_or_Task) -> Task:
    '''Starts a asyncgui-flavored awaitable or a Task.

    If the argument is a Task, itself will be returned. If it's an awaitable,
    it will be wrapped in a Task, and the Task will be returned.
    '''
    def step_coro(*args, **kwargs):
        try:
            if getcoroutinestate(coro) != CORO_CLOSED:
                coro.send((args, kwargs, ))(step_coro)
        except StopIteration:
            pass

    if isawaitable(awaitable_or_task):
        task = Task(awaitable_or_task)
    elif isinstance(awaitable_or_task, Task):
        task = awaitable_or_task
        if task._state is not TaskState.CREATED:
            raise ValueError(f"{task} was already started")
    else:
        raise ValueError("Argument must be either of a Task or an awaitable.")
    step_coro._task = task
    coro = task.root_coro

    try:
        coro.send(None)(step_coro)
    except StopIteration:
        pass

    return task


def raw_start(coro: typing.Coroutine) -> typing.Coroutine:
    '''Starts a asyncgui-flavored coroutine.

    Unlike ``start()``, the argument will not be wrapped in a Task, and will
    not be validated at all.
    '''
    def step_coro(*args, **kwargs):
        try:
            if getcoroutinestate(coro) != CORO_CLOSED:
                coro.send((args, kwargs, ))(step_coro)
        except StopIteration:
            pass

    step_coro._task = None

    try:
        coro.send(None)(step_coro)
    except StopIteration:
        pass

    return coro


@types.coroutine
def sleep_forever():
    yield lambda step_coro: None


@types.coroutine
def _gather(aws_and_tasks: typing.Iterable[Awaitable_or_Task], *, n: int=None) \
        -> typing.List[Task]:
    '''(internal)'''
    tasks = [v if isinstance(v, Task) else Task(v) for v in aws_and_tasks]
    n_tasks = len(tasks)
    n_left = n_tasks if n is None else min(n, n_tasks)

    def step_coro():
        pass

    def done_callback(*args, **kwargs):
        nonlocal n_left
        n_left -= 1
        if n_left == 0:
            step_coro()

    for task in tasks:
        task._event.add_callback(done_callback)
        start(task)

    if n_left <= 0:
        return tasks

    def callback(step_coro_):
        nonlocal step_coro
        step_coro = step_coro_
    yield callback

    return tasks


async def unstructured_or(*aws_and_tasks):
    return await _gather(aws_and_tasks, n=1)


async def unstructured_and(*aws_and_tasks):
    return await _gather(aws_and_tasks)


class Event:
    '''
    Event
    =====

    Similar to 'trio.Event'.
    '''
    __slots__ = ('_value', '_flag', '_step_coro_list', )

    def __init__(self):
        self._value = None
        self._flag = False
        self._step_coro_list = []

    def is_set(self):
        return self._flag

    def set(self, *args, **kwargs):
        if self._flag:
            return
        self._flag = True
        self._value = (args, kwargs)
        step_coro_list = self._step_coro_list
        self._step_coro_list = []
        for step_coro in step_coro_list:
            step_coro(*args, **kwargs)

    def clear(self, *args, **kwargs):
        self._flag = False

    @types.coroutine
    def wait(self):
        if self._flag:
            yield lambda step_coro: step_coro()
            return self._value
        else:
            return (yield self._step_coro_list.append)

    def add_callback(self, callback):
        '''(internal)'''
        if self._flag:
            args, kwargs = self._value
            callback(*args, **kwargs)
        else:
            self._step_coro_list.append(callback)


@types.coroutine
def get_step_coro():
    '''Returns the task-runner'''
    return (yield lambda step_coro: step_coro(step_coro))[0][0]


@types.coroutine
def get_current_task() -> typing.Optional[Task]:
    '''Returns the task currently running. None if no Task is associated.'''
    return (yield lambda step_coro: step_coro(step_coro._task))[0][0]


@asynccontextmanager
async def aclosing(aiter):
    '''async version of 'contextlib.closing()'
    '''
    try:
        yield aiter
    finally:
        await aiter.aclose()
