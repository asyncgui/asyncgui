__all__ = (
    # core (exceptions)
    'ExceptionGroup', 'BaseExceptionGroup', 'InvalidStateError', 'Cancelled',

    # core
    'Aw_or_Task', 'start', 'Task', 'TaskState',
    'dummy_task', 'current_task', 'sleep_forever',

    # structured concurrency
    'wait_all', 'wait_any', 'wait_all_cm', 'wait_any_cm', 'move_on_when',
    'run_as_main', 'run_as_daemon',
    'open_nursery', 'Nursery',

    # synchronization
    'Event', 'ExclusiveEvent', 'StatefulEvent', 'StatelessEvent',
)
from typing import Any, Union, TypeAlias
from collections.abc import (
    Iterable, Coroutine, Awaitable, AsyncIterator, Generator, Callable, Sequence,
)
import types
from inspect import getcoroutinestate, CORO_CREATED, CORO_SUSPENDED, isawaitable
import sys
from functools import cached_property, partial
import enum
from contextlib import asynccontextmanager, contextmanager, AbstractAsyncContextManager

# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------

if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup, ExceptionGroup
else:
    from builtins import BaseExceptionGroup, ExceptionGroup

potential_bug_msg = \
    r"You might have just found a bug in the library. Please create a minimal reproducible " \
    r"example and report it on the GitHub repository: https://github.com/asyncgui/asyncgui."


class InvalidStateError(Exception):
    """Operation is not allowed in the current state."""


class _Cancelled(BaseException):
    @cached_property
    def level(self) -> int:
        return self.args[0]


Cancelled = (_Cancelled, GeneratorExit, )
'''
Exception class that represents cancellation.
See :ref:`dealing-with-cancellation`.

.. warning::

    Actually, this is not an exception class but a tuple of exception classes for now.
    But that's an implementation detail, and it might become an actual class in the future;
    therefore, your code must be compatible in both cases.

:meta hide-value:
'''


class TaskState(enum.Enum):
    '''
    Enum class that represents the Task state.
    '''

    CREATED = enum.auto()
    '''
    Waiting to start execution.

    :meta hide-value:
    '''

    STARTED = enum.auto()
    '''
    Currently running or suspended.

    :meta hide-value:
    '''

    CANCELLED = enum.auto()
    '''
    The execution has been cancelled. The cause of the cancellation is either an explicit or implicit call to
    :meth:`Task.cancel` or an unhandled exception.

    :meta hide-value:
    '''

    FINISHED = enum.auto()
    '''
    The execution has been completed.

    :meta hide-value:
    '''


class Task:
    __slots__ = (
        '_root_coro', '_root_coro_send', '_state', '_result', '_on_end',
        '_exc_caught', '_suppresses_exc',
        '_cancel_disabled', '_current_depth', '_requested_cancel_level',
    )

    def __init__(self, aw: Awaitable, /):
        if not isawaitable(aw):
            raise ValueError(str(aw) + " is not awaitable.")
        self._cancel_disabled = False
        self._root_coro = self._wrapper(aw)
        self._root_coro_send = self._root_coro.send
        self._state = TaskState.CREATED
        self._on_end = None
        self._current_depth = 0
        self._requested_cancel_level = None
        self._exc_caught = None
        self._suppresses_exc = False

    def __str__(self):
        return f'Task(state={self._state.name})'

    @property
    def root_coro(self) -> Coroutine:
        '''
        The starting point of the coroutine chain for the task.
        '''
        return self._root_coro

    @property
    def state(self) -> TaskState:
        '''
        The current state of the task.
        '''
        return self._state

    @property
    def finished(self) -> bool:
        '''Whether the task has completed execution.'''
        return self._state is TaskState.FINISHED

    @property
    def cancelled(self) -> bool:
        '''Whether the task has been cancelled.'''
        return self._state is TaskState.CANCELLED

    @property
    def result(self) -> Any:
        '''Result of the task. If the task is not finished, :exc:`InvalidStateError` will be raised. '''
        state = self._state
        if state is TaskState.FINISHED:
            return self._result
        elif state is TaskState.CANCELLED:
            raise InvalidStateError(f"{self} was cancelled")
        else:
            raise InvalidStateError(f"Result of {self} is not ready")

    async def _wrapper(self, aw, /):
        try:
            self._state = TaskState.STARTED
            self._result = await aw
        except _Cancelled as e:
            self._state = TaskState.CANCELLED
            assert e.level == 0, potential_bug_msg
            assert self._requested_cancel_level == 0, potential_bug_msg
        except Exception as e:
            self._state = TaskState.CANCELLED
            self._exc_caught = e
            if not self._suppresses_exc:
                raise
        except:  # noqa: E722
            self._state = TaskState.CANCELLED
            raise
        else:
            self._state = TaskState.FINISHED
        finally:
            assert self._current_depth == 0, potential_bug_msg
            if (on_end := self._on_end) is not None:
                on_end(self)

    def cancel(self, _level=0, /):
        '''Cancel the task as soon as possible.'''
        if self._requested_cancel_level is None:
            self._requested_cancel_level = _level
            state = getcoroutinestate(self._root_coro)
            if state is CORO_SUSPENDED:
                if not self._cancel_disabled:
                    self._actual_cancel()
            elif state is CORO_CREATED:
                self._root_coro.close()
                self._state = TaskState.CANCELLED
        else:
            self._requested_cancel_level = min(self._requested_cancel_level, _level)

    def _actual_cancel(self):
        try:
            self._root_coro.throw(_Cancelled(self._requested_cancel_level))(self)
        except StopIteration:
            pass
        else:
            self._cancel_if_needed()

    close = cancel
    '''An alias of :meth:`cancel`.'''

    @property
    def _cancel_requested(self) -> bool:
        return self._requested_cancel_level is not None

    @property
    def _is_cancellable(self, get_state=getcoroutinestate, CORO_SUSPENDED=CORO_SUSPENDED) -> bool:
        '''Whether the task can be cancelled immediately.'''
        return (not self._cancel_disabled) and get_state(self._root_coro) is CORO_SUSPENDED

    def _cancel_if_needed(self):
        if (self._requested_cancel_level is not None) and self._is_cancellable:
            self._actual_cancel()

    def _step(self, *args, **kwargs):
        try:
            self._root_coro_send((args, kwargs, ))(self)
        except StopIteration:
            pass
        else:
            self._cancel_if_needed()

    def _throw_exc(self, exc):
        '''停止中のTaskへ例外を投げる。Taskが停止中ではない場合は :exc:`InvalidStateError` が起こる。'''
        coro = self._root_coro
        if getcoroutinestate(coro) is not CORO_SUSPENDED:
            raise InvalidStateError("Throwing an exception to an unstarted/running/closed task is not allowed.")
        try:
            coro.throw(exc)(self)
        except StopIteration:
            pass
        else:
            self._cancel_if_needed()

    class CancelScope:
        __slots__ = ('_task', '_depth', 'cancel_called', )

        def __init__(self, task, depth):
            self._task = task
            self._depth = depth
            self.cancel_called = False

        @property
        def closed(self) -> bool:
            return self._task is None

        def cancel(self):
            if self.cancel_called:
                return
            self.cancel_called = True
            if (t := self._task) is not None:
                t.cancel(self._depth)

    @contextmanager
    def _open_cancel_scope(self, CancelScope=CancelScope):
        self._current_depth = depth = self._current_depth + 1
        scope = CancelScope(self, depth)
        try:
            yield scope
        except _Cancelled as exc:
            level = exc.level
            if level != depth:
                assert level < depth, potential_bug_msg
                raise
        finally:
            req_level = self._requested_cancel_level
            scope._task = None
            self._current_depth -= 1
            if req_level is not None:
                if req_level == depth:
                    self._requested_cancel_level = None
                else:
                    assert req_level < depth, potential_bug_msg

    del CancelScope


Aw_or_Task = Union[Awaitable, Task]
YieldType = Callable[[Task], None]
SendType = tuple[tuple, dict]


def start(aw: Aw_or_Task, /) -> Task:
    '''
    *Immediately* start a Task.

    .. code-block::

        async def async_func():
            ...

        task = start(async_func())

    .. warning::

        Tasks started with this function are root tasks.
        You must ensure they aren't garbage-collected while still running
        --for example, by explicitly calling :meth:`Task.cancel` before the program exits.
    '''
    if isawaitable(aw):
        task = Task(aw)
    elif isinstance(aw, Task):
        task = aw
        if task._state is not TaskState.CREATED:
            raise ValueError(f"{task} has already started")
    else:
        raise ValueError("Argument must be either a Task or an Awaitable.")

    try:
        task._root_coro_send(None)(task)
    except StopIteration:
        pass
    else:
        task._cancel_if_needed()

    return task


def _current_task(task):
    task._step(task)


@types.coroutine
def current_task(_f=_current_task) -> Generator[YieldType, SendType, Task]:
    '''Returns the Task instance corresponding to the caller.

    .. code-block::

        task = await current_task()
    '''
    return (yield _f)[0][0]


def _sleep_forever(task):
    pass


@types.coroutine
def sleep_forever(_f=_sleep_forever):
    '''
    .. code-block::

        await sleep_forever()
    '''
    yield _f


@types.coroutine
def _wait_args(_f=_sleep_forever):
    return (yield _f)[0]


@types.coroutine
def _wait_args_0(_f=_sleep_forever):
    return (yield _f)[0][0]


dummy_task = Task(sleep_forever())
'''
An already closed task.
This can be utilized to prevent the need for the common null validation mentioned below.

*Before:*

.. code-block::
    :emphasize-lines: 3, 6,7

    class MyClass:
        def __init__(self):
            self._task = None

        def restart(self):
            if self._task is not None:
                self._task.cancel()
            self._task = asyncgui.start(self.main())

        async def main(self):
            ...

*After:*

.. code-block::
    :emphasize-lines: 3, 6

    class MyClass:
        def __init__(self):
            self._task = asyncgui.dummy_task

        def restart(self):
            self._task.cancel()
            self._task = asyncgui.start(self.main())

        async def main(self):
            ...
'''
dummy_task.cancel()

# -----------------------------------------------------------------------------
# Synchronization
# -----------------------------------------------------------------------------


class ExclusiveEvent:
    '''
    Similar to :class:`Event`, but this version does not allow multiple tasks to :meth:`wait` simultaneously.
    As a result, it operates faster.
    '''
    __slots__ = ('_waiting_task', )

    def __init__(self):
        self._waiting_task = None

    def fire(self, *args, **kwargs):
        if (t := self._waiting_task) is not None:
            t._step(*args, **kwargs)

    @types.coroutine
    def wait(self) -> Generator[YieldType, SendType, SendType]:
        try:
            return (yield self._attach_task)
        finally:
            self._waiting_task = None

    def _attach_task(self, task):
        if self._waiting_task is not None:
            raise InvalidStateError("There's already a task waiting for the event to fire.")
        self._waiting_task = task

    @types.coroutine
    def wait_args(self) -> Generator[YieldType, SendType, tuple]:
        '''
        (experimental)

        ``await event.wait_args()`` is equivalent to ``(await event.wait())[0]``.

        :meta private:
        '''
        try:
            return (yield self._attach_task)[0]
        finally:
            self._waiting_task = None

    @types.coroutine
    def wait_args_0(self) -> Generator[YieldType, SendType, Any]:
        '''
        (experimental)

        ``await event.wait_args_0()`` is equivalent to ``(await event.wait())[0][0]``.

        :meta private:
        '''
        try:
            return (yield self._attach_task)[0][0]
        finally:
            self._waiting_task = None


class Event:
    '''
    .. code-block::

        async def async_fn(e):
            args, kwargs = await e.wait()
            assert args == (2, )
            assert kwargs == {'crow': 'raven', }

            args, kwargs = await e.wait()
            assert args == (3, )
            assert kwargs == {'toad': 'frog', }

        e = Event()
        e.fire(1, crocodile='alligator')
        task = start(async_fn(e))
        e.fire(2, crow='raven')
        e.fire(3, toad='frog')
        assert task.finished

    .. warning::

        This differs from :class:`asyncio.Event`, as it does not have a "set" state. ``await e.wait()`` will
        always block the caller until someone else calls :meth:`fire` *after* the wait has started.
        Use :class:`StatefulEvent` if you want something closer to :class:`asyncio.Event`.

    .. versionchanged:: 0.7.0

        This is now completely different from the previous version's.
    '''

    __slots__ = ('_waiting_tasks', )

    def __init__(self):
        self._waiting_tasks = []

    def fire(self, *args, **kwargs):
        tasks = self._waiting_tasks
        if not tasks:
            return
        self._waiting_tasks = []
        for t in tasks:
            if t is not None:
                t._step(*args, **kwargs)

    @types.coroutine
    def wait(self) -> Generator[YieldType, SendType, SendType]:
        '''
        Waits for the event to be fired.
        '''
        try:
            tasks = self._waiting_tasks
            idx = len(tasks)
            return (yield tasks.append)
        finally:
            tasks[idx] = None


StatelessEvent = Event
'''
An alias of :class:`Event`.

.. versionadded:: 0.7.2
'''


class StatefulEvent:
    '''
    The closest thing to :class:`asyncio.Event` in this library.

    .. csv-table::
        :header-rows: 1

        StatefulEvent, asyncio.Event
        .fire(), .set()
        .wait(), .wait()
        .clear(), .clear()
        .is_fired, .is_set()
        .params, --

    .. code-block::

        async def async_fn(e):
            args, kwargs = await e.wait()
            assert args == (1, )
            assert kwargs == {'crow': 'raven', }

        e = StatefulEvent()
        task = start(async_fn(e))
        assert not task.finished
        e.fire(1, crow='raven')
        assert task.finished

    .. versionadded:: 0.7.2

    .. versionchanged:: 0.9.0
        The ``.refire()`` and ``.fire_or_refire()`` methods have been removed.
    '''
    __slots__ = ('_params', '_waiting_tasks', )

    def __init__(self):
        self._params = None
        self._waiting_tasks = []

    @property
    def is_fired(self) -> bool:
        return self._params is not None

    def fire(self, *args, **kwargs):
        '''Fires the event if it's not in a fired state.'''
        if self._params is not None:
            return
        self._params = (args, kwargs, )
        tasks = self._waiting_tasks
        if not tasks:
            return
        self._waiting_tasks = []
        for t in tasks:
            if t is not None:
                t._step(*args, **kwargs)

    def clear(self):
        '''Sets the event to a non-fired state.'''
        self._params = None

    @types.coroutine
    def wait(self) -> Generator[YieldType, SendType, SendType]:
        if self._params is not None:
            return self._params
        tasks = self._waiting_tasks
        idx = len(tasks)
        try:
            return (yield tasks.append)
        finally:
            tasks[idx] = None

    @property
    def params(self) -> tuple:
        '''
        The parameters passed to the last fire. Raises :exc:`InvalidStateError` if the event is not in a "fired" state.
        This is a convenient way to access the parameters from synchronous code.

        .. code-block::

            e = StatefulEvent()

            e.fire(1, crow='raven')
            args, kwargs = e.params
            assert args == (1, )
            assert kwargs == {'crow': 'raven', }

            e.clear()
            e.fire(2, parasol='umbrella')
            args, kwargs = e.params
            assert args == (2, )
            assert kwargs == {'parasol': 'umbrella', }
        '''
        p = self._params
        if p is None:
            raise InvalidStateError("The event is not in a 'fired' state.")
        return p


# -----------------------------------------------------------------------------
# Structured concurrency
# -----------------------------------------------------------------------------


class Counter:
    '''
    (internal)
    A numeric counter that notifies when its value reaches zero.
    Used by a parent task to wait for its child tasks to complete or be cancelled.

    .. warning::
        Only one task can wait for the counter to reach zero at a time — if multiple tasks
        attempt to wait, the program would silently break.
    '''

    __slots__ = ('_waiting_task', '_value', )

    def __init__(self, initial_value=0, /):
        self._value = initial_value
        self._waiting_task = None

    def increase(self):
        self._value += 1

    def decrease(self):
        n = self._value - 1
        assert n >= 0, potential_bug_msg
        self._value = n
        if (not n) and (t := self._waiting_task) is not None:
            t._step()

    @types.coroutine
    def wait_for_zero(self):
        if not self._value:
            return
        try:
            yield self._attach_task
        finally:
            self._waiting_task = None

    def _attach_task(self, task):
        self._waiting_task = task

    @property
    def is_not_zero(self, bool=bool):
        return bool(self._value)

    def __bool__(self):
        raise NotImplementedError("'Counter' can no longer be converted to a boolean value.")


async def _wait_xxx(debug_msg, on_child_end, *aws: Iterable[Aw_or_Task]) -> Awaitable[Sequence[Task]]:
    children = [v if isinstance(v, Task) else Task(v) for v in aws]
    if not children:
        return children
    counter = Counter(len(children))
    parent = await current_task()

    try:
        with parent._open_cancel_scope() as scope:
            on_child_end = partial(on_child_end, scope, counter)
            for c in children:
                c._suppresses_exc = True
                c._on_end = on_child_end
                start(c)
            await counter.wait_for_zero()
    finally:
        if counter.is_not_zero:
            for c in children:
                c.cancel()
            if counter.is_not_zero:
                try:
                    parent._cancel_disabled = True
                    await counter.wait_for_zero()
                finally:
                    parent._cancel_disabled = False
        exceptions = [e for c in children if (e := c._exc_caught) is not None]
        if exceptions:
            raise ExceptionGroup(debug_msg, exceptions)
        if parent._requested_cancel_level is not None:
            await sleep_forever()
            assert False, potential_bug_msg
    return children


def _on_child_end__ver_all(scope, counter, child):
    counter.decrease()
    if child._exc_caught is not None:
        scope.cancel()


def _on_child_end__ver_any(scope, counter, child):
    counter.decrease()
    if child._exc_caught is not None or child.finished:
        scope.cancel()


def _on_child_end__ver_run_as_main(scope, counter, child):
    counter.decrease()
    if child._exc_caught is not None or counter.is_not_zero is False:
        scope.cancel()


_wait_xxx_type: TypeAlias = Callable[..., Awaitable[Sequence[Task]]]
wait_all: _wait_xxx_type = partial(_wait_xxx, "wait_all()", _on_child_end__ver_all)
'''
Runs multiple tasks concurrently, then waits for all of them to either complete or be cancelled.

.. code-block::

    tasks = await wait_any(async_fn0(), async_fn1(), async_fn2())
    for i, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{i} completed with a return value of {task.result}.")
        else:
            print(f"async_fn{i} was cancelled.")
'''

wait_any: _wait_xxx_type = partial(_wait_xxx, "wait_any()", _on_child_end__ver_any)
'''
Runs multiple tasks concurrently, then waits until either one completes or all are cancelled.
As soon as one completes, the others will be cancelled.

.. code-block::

    tasks = await wait_any(async_fn0(), async_fn1(), async_fn2())
    for i, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{i} completed with a return value of {task.result}.")
        else:
            print(f"async_fn{i} was cancelled.")
'''


@asynccontextmanager
async def _wait_xxx_cm(debug_msg, on_child_end, wait_bg, *aws: Iterable[Aw_or_Task]):
    fg_task = await current_task()
    bg_tasks = [v if isinstance(v, Task) else Task(v) for v in aws]
    counter = Counter(len(bg_tasks))

    fg_exc = None

    try:
        with fg_task._open_cancel_scope() as scope:
            for task in bg_tasks:
                task._on_end = partial(on_child_end, scope, counter)
                task._suppresses_exc = True
                start(task)
            yield bg_tasks
            if wait_bg:
                await counter.wait_for_zero()
    except Exception as e:
        fg_exc = e
    finally:
        for task in bg_tasks:
            task.cancel()
        if counter.is_not_zero:
            try:
                fg_task._cancel_disabled = True
                await counter.wait_for_zero()
            finally:
                fg_task._cancel_disabled = False
        excs = [e for task in bg_tasks if (e := task._exc_caught) is not None]
        if fg_exc is not None:
            excs.append(fg_exc)
        if excs:
            raise ExceptionGroup(debug_msg, excs)
        if fg_task._requested_cancel_level is not None:
            await sleep_forever()
            assert False, potential_bug_msg


_wait_xxx_cm_type: TypeAlias = Callable[..., AbstractAsyncContextManager[list[Task]]]
wait_all_cm: _wait_xxx_cm_type = partial(_wait_xxx_cm, "wait_all_cm()", _on_child_end__ver_all, True)
'''
Returns an async context manager that runs all given tasks concurrently with each other and alongside the code inside
the with-block, then waits until the code inside the with-block completes and all tasks have either completed or been
cancelled.

.. code-block::

    async with wait_all_cm(async_fn0(), async_fn1()) as tasks:
        ...
    for i, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{i} completed with a return value of {task.result}.")
        else:
            print(f"async_fn{i} was cancelled.")

.. versionchanged:: 0.10.0
    Now accepts multiple tasks. The object bound in the as-clause is a list of Task instances instead of a single one.
'''

wait_any_cm: _wait_xxx_cm_type = partial(_wait_xxx_cm, "wait_any_cm()", _on_child_end__ver_any, False)
'''
Returns an async context manager that runs all given tasks concurrently with each other and alongside the code inside
the with-block, then waits until either the code inside the with-block completes or any of the tasks completes.
As soon as that happens, any remaining tasks and the code inside the with-block (if still running) will be cancelled.

.. code-block::

    async with wait_any_cm(async_fn0(), async_fn1()) as tasks:
        ...
    for i, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{i} completed with a return value of {task.result}.")
        else:
            print(f"async_fn{i} was cancelled.")

.. versionchanged:: 0.10.0
    Now accepts multiple tasks. The object bound in the as-clause is a list of Task instances instead of a single one.
'''

run_as_main: _wait_xxx_cm_type = partial(_wait_xxx_cm, "run_as_main()", _on_child_end__ver_run_as_main, True)
'''
Returns an async context manager that runs all given tasks concurrently with each other and alongside the code inside
the with-block, then waits for all tasks to either complete or be cancelled. As soon as all tasks have done so,
the code inside the with-block will be cancelled if it is still running.

.. code-block::

    async with run_as_main(async_fn0(), async_fn1()) as tasks:
        ...
    for i, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{i} completed with a return value of {task.result}.")
        else:
            print(f"async_fn{i} was cancelled.")

If no tasks are given, it simply runs the code inside the with-block.

.. versionchanged:: 0.10.0
    Now accepts multiple tasks. The object bound in the as-clause is a list of Task instances instead of a single one.
'''

run_as_daemon: _wait_xxx_cm_type = partial(_wait_xxx_cm, "run_as_daemon()", _on_child_end__ver_all, False)
'''
Returns an async context manager that runs all given tasks concurrently with each other and alongside the code inside
the with-block, then waits until the code inside the with-block completes. As soon as that happens, the tasks will be
cancelled if they are still running.

This is equivalent to :func:`trio_util.run_and_cancelling`.

.. code-block::

    async with run_as_daemon(async_fn0(), async_fn1()) as tasks:
        ...
    for i, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{i} completed with a return value of {task.result}.")
        else:
            print(f"async_fn{i} was cancelled.")

.. versionchanged:: 0.10.0
    Now accepts multiple tasks. The object bound in the as-clause is a list of Task instances instead of a single one.
'''


class Nursery:
    '''
    An equivalent of :class:`trio.Nursery`.
    You should not directly instantiate this, use :func:`open_nursery`.
    '''

    __slots__ = ('_closed', '_children', '_scope', '_counters', '_callbacks', '_gc_in_every', '_n_until_gc', )

    def __init__(self, scope, counter, daemon_counter, gc_in_every):
        self._gc_in_every = self._n_until_gc = gc_in_every
        self._closed = False
        self._children = []
        self._scope = scope
        self._counters = (daemon_counter, counter, )
        self._callbacks = (
            partial(_on_child_end__ver_all, scope, daemon_counter),
            partial(_on_child_end__ver_all, scope, counter),
        )

    def start(self, aw: Aw_or_Task, /, *, daemon=False) -> Task:
        '''
        *Immediately* start a Task under the supervision of the nursery.

        The ``daemon`` parameter acts like the one in the :mod:`threading` module.
        When only daemon tasks are left, they get cancelled, and the nursery closes.
        '''
        if self._closed:
            raise InvalidStateError("Nursery has been already closed")
        if not self._n_until_gc:
            self._collect_garbage()
            self._n_until_gc = self._gc_in_every
        self._n_until_gc -= 1
        child = aw if isinstance(aw, Task) else Task(aw)
        child._suppresses_exc = True
        child._on_end = self._callbacks[not daemon]
        self._counters[not daemon].increase()
        self._children.append(child)
        return start(child)

    def _collect_garbage(self, STARTED=TaskState.STARTED):
        self._children = [
            c for c in self._children
            if c.state is STARTED or c._exc_caught is not None
        ]

    def close(self):
        '''Cancel all the child tasks in the nursery as soon as possible. '''
        self._closed = True
        self._scope.cancel()

    @property
    def closed(self) -> bool:
        return self._closed


@asynccontextmanager
async def open_nursery(*, _gc_in_every=1000) -> AsyncIterator[Nursery]:
    '''
    An equivalent of :func:`trio.open_nursery`.

    .. code-block::

        async with open_nursery() as nursery:
            nursery.start(async_fn1())
            nursery.start(async_fn2(), daemon=True)
    '''
    exc = None
    parent = await current_task()
    counter = Counter()
    daemon_counter = Counter()

    try:
        with parent._open_cancel_scope() as scope:
            nursery = Nursery(scope, counter, daemon_counter, _gc_in_every)
            yield nursery
            await counter.wait_for_zero()
    except Exception as e:
        exc = e
    finally:
        nursery._closed = True
        children = nursery._children
        for c in children:
            c.cancel()
        try:
            parent._cancel_disabled = True
            await daemon_counter.wait_for_zero()
            await counter.wait_for_zero()
        finally:
            parent._cancel_disabled = False
        excs = [e for c in children if (e := c._exc_caught) is not None]
        if exc is not None:
            excs.append(exc)
        if excs:
            raise ExceptionGroup("Nursery", excs)
        if parent._requested_cancel_level is not None:
            await sleep_forever()
            assert False, potential_bug_msg


# -----------------------------------------------------------------------------
# Aliases
# -----------------------------------------------------------------------------

move_on_when = wait_any_cm
'''
Alias for :func:`wait_any_cm`. The name is borrowed from :func:`trio_util.move_on_when`.
'''
