__all__ = (
    # core (exceptions)
    'ExceptionGroup', 'BaseExceptionGroup', 'InvalidStateError', 'Cancelled',

    # core
    'Aw_or_Task', 'start', 'Task', 'TaskState', 'current_task', 'open_cancel_scope', 'CancelScope',
    'sleep_forever', 'disable_cancellation', 'dummy_task', 'check_cancellation',

    # utils
    'Event',

    # utils (structured concurrency)
    'wait_all', 'wait_any', 'wait_all_cm', 'wait_any_cm', 'run_as_secondary', 'run_as_primary',
    'open_nursery', 'Nursery',

    # utils (for async library developer)
    'IBox', 'ISignal', '_current_task', '_sleep_forever',

    # aliases
    'run_as_daemon', 'TaskGroup', 'and_', 'or_',
)
import types
import typing as T
from inspect import getcoroutinestate, CORO_CREATED, CORO_SUSPENDED, isawaitable
import sys
import itertools
from functools import cached_property, partial
import enum
from contextlib import asynccontextmanager

# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------

if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup, ExceptionGroup
else:
    BaseExceptionGroup = BaseExceptionGroup  #: :meta private:
    ExceptionGroup = ExceptionGroup  #: :meta private:

potential_bug_msg = \
    r"This may be a bug of this library. Please make a minimal code that reproduces the bug, and open an issue at " \
    r"the GitHub repository, then post the code there. (https://github.com/gottadiveintopython/asyncgui)."


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class _Cancelled(BaseException):
    @cached_property
    def level(self) -> int:
        return self.args[0]


Cancelled = (_Cancelled, GeneratorExit, )
'''
Exception class that represents cancellation.
See dealing-with-cancellation_ .

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
    The execution has been cancelled.
    The cause of cancellation can be either :meth:`Task.cancel` or an unhandled exception.

    :meta hide-value:
    '''

    FINISHED = enum.auto()
    '''
    The execution has been completed.

    :meta hide-value:
    '''


class Task:
    __slots__ = (
        'name', '_uid', '_root_coro', '_state', '_result', '_on_end',
        '_exc_caught', '_suppresses_exc',
        '_cancel_disabled', '_cancel_depth', '_cancel_level',
    )

    _uid_iter = itertools.count()

    def __init__(self, aw: T.Awaitable, /):
        if not isawaitable(aw):
            raise ValueError(str(aw) + " is not awaitable.")
        self._uid = next(self._uid_iter)
        self.name = ""  #: :meta private:
        self._cancel_disabled = 0
        self._root_coro = self._wrapper(aw)
        self._state = TaskState.CREATED
        self._on_end = None
        self._cancel_depth = 0
        self._cancel_level = None
        self._exc_caught = None
        self._suppresses_exc = False

    def __str__(self):
        return f'Task(state={self._state.name}, uid={self._uid}, name={self.name!r})'

    @property
    def uid(self) -> int:
        '''
        An unique integer assigned to the task.
        This exists solely for inspection purposes.
        '''
        return self._uid

    @property
    def root_coro(self) -> T.Coroutine:
        '''
        The starting point of the coroutine chain for the task.
        This exists solely for inspection purposes.
        '''
        return self._root_coro

    @property
    def state(self) -> TaskState:
        '''
        The current state of the task.
        This exists solely for inspection purposes.
        '''
        return self._state

    @property
    def finished(self) -> bool:
        '''Whether the task has been completed..'''
        return self._state is TaskState.FINISHED

    @property
    def cancelled(self) -> bool:
        '''Whether the task has been cancelled.'''
        return self._state is TaskState.CANCELLED

    @property
    def result(self) -> T.Any:
        '''Result of the task. If the task is not finished, :exc:`InvalidStateError` will be raised. '''
        state = self._state
        if state is TaskState.FINISHED:
            return self._result
        elif state is TaskState.CANCELLED:
            raise InvalidStateError(f"{self} was cancelled")
        else:
            raise InvalidStateError(f"Result of {self} is not ready")

    async def _wrapper(self, awaitable, /):
        try:
            self._state = TaskState.STARTED
            self._result = await awaitable
        except _Cancelled as e:
            self._state = TaskState.CANCELLED
            assert e.level == 0, potential_bug_msg
            assert self._cancel_level == 0, potential_bug_msg
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
            assert self._cancel_depth == 0, potential_bug_msg
            if (on_end := self._on_end) is not None:
                on_end(self)

    def cancel(self, _level=0, /):
        '''Cancel the task as soon as possible.'''
        if self._cancel_level is None:
            self._cancel_level = _level
            state = getcoroutinestate(self._root_coro)
            if state is CORO_SUSPENDED:
                if not self._cancel_disabled:
                    self._actual_cancel()
            elif state is CORO_CREATED:
                self._root_coro.close()
                self._state = TaskState.CANCELLED
        else:
            self._cancel_level = min(self._cancel_level, _level)

    def _actual_cancel(self):
        try:
            # NOTE: _cancel_levelが0の時は末尾の関数呼び出し (self) は省いても良いかもしれない
            self._root_coro.throw(_Cancelled(self._cancel_level))(self)
        except StopIteration:
            pass
        else:
            self._cancel_if_needed()

    close = cancel
    '''An alias for :meth:`cancel`.'''

    @property
    def _cancel_requested(self) -> bool:
        return self._cancel_level is not None

    @property
    def _is_cancellable(self) -> bool:
        '''Whether the task can be cancelled immediately.'''
        return (not self._cancel_disabled) and getcoroutinestate(self._root_coro) is CORO_SUSPENDED

    def _cancel_if_needed(self, getcoroutinestate=getcoroutinestate, CORO_SUSPENDED=CORO_SUSPENDED):
        if (self._cancel_level is None) or self._cancel_disabled or \
                (getcoroutinestate(self._root_coro) is not CORO_SUSPENDED):
            pass
        else:
            self._actual_cancel()

    def _step(self, *args, **kwargs):
        coro = self._root_coro
        if getcoroutinestate(coro) is not CORO_SUSPENDED:
            return
        try:
            coro.send((args, kwargs, ))(self)
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


Aw_or_Task = T.Union[T.Awaitable, Task]


def start(aw: Aw_or_Task, /) -> Task:
    '''*Immediately* start a Task/Awaitable.

    If the argument is a :class:`Task`, itself will be returned. If it's a :class:`typing.Awaitable`,
    it will be wrapped in a Task, and that Task will be returned.

    .. code-block::

        async def async_func():
            ...

        task = start(async_func())
    '''
    if isawaitable(aw):
        task = Task(aw)
    elif isinstance(aw, Task):
        task = aw
        if task._state is not TaskState.CREATED:
            raise ValueError(f"{task} has already started")
    else:
        raise ValueError("Argument must be either a Task or an awaitable.")

    try:
        task._root_coro.send(None)(task)
    except StopIteration:
        pass
    else:
        task._cancel_if_needed()

    return task


class CancelScope:
    '''
    Equivalent of :class:`trio.CancelScope`.
    You should not directly instantiate this, use :func:`open_cancel_scope`.
    '''
    __slots__ = ('_task', '_depth', 'cancelled_caught', 'cancel_called', )

    def __init__(self, task: Task, /):
        self._task = task
        self.cancelled_caught = False  #: Whether the scope caught a corresponding :class:`Cancelled` instance.
        self.cancel_called = False  #: Whether the :meth:`cancel` has been called.

    def __enter__(self) -> 'CancelScope':
        t = self._task
        t._cancel_depth = self._depth = t._cancel_depth + 1
        return self

    def __exit__(self, exc_type, exc, __):
        # LOAD_FAST
        task = self._task
        level = task._cancel_level
        depth = self._depth

        self._task = None
        task._cancel_depth -= 1
        if level is not None:
            if level == depth:
                task._cancel_level = None
            else:
                assert level < depth, potential_bug_msg
        if exc_type is not _Cancelled:
            return
        level = exc.level
        if level == depth:
            self.cancelled_caught = True
            return True
        else:
            assert level < depth, potential_bug_msg

    @property
    def closed(self) -> bool:
        '''
        Whether this scope has been closed.
        The cause of the closure of the scope can be either an exception occurred or the scope exited gracefully,
        '''
        return self._task is None

    def cancel(self):
        '''Cancel the execution inside this scope as soon as possible. '''
        if self.cancel_called:
            return
        self.cancel_called = True
        if not self.closed:
            self._task.cancel(self._depth)


class open_cancel_scope:
    '''
    Same as :class:`trio.CancelScope` except this one returns an async context manager.

    .. code-block::

        async with open_cancel_scope() as scope:
            ...
    '''
    __slots__ = ('_scope', )

    async def __aenter__(self) -> T.Awaitable[CancelScope]:
        self._scope = CancelScope(await current_task())
        return self._scope.__enter__()

    async def __aexit__(self, *args):
        return self._scope.__exit__(*args)


def _current_task(task):
    return task._step(task)


@types.coroutine
def current_task(_f=_current_task) -> T.Awaitable[Task]:
    '''Returns the Task instance corresponding to the caller.

    .. code-block::

        task = await current_task()
    '''
    return (yield _f)[0][0]


class disable_cancellation:
    '''
    Return an async context manager that protects its code-block from cancellation.

    .. code-block::

        async with disable_cancellation():
            await something  # <- never gets cancelled
    '''

    __slots__ = ('_task', )

    async def __aenter__(self):
        self._task = task = await current_task()
        task._cancel_disabled += 1

    async def __aexit__(self, *__):
        self._task._cancel_disabled -= 1


@types.coroutine
def check_cancellation():
    '''
    If the current task has been requested to be cancelled, and the task is not protected from cancellation,
    cancel the task immediately. Otherwise, do nothing.

    .. code-block::

        await check_cancellation()
    '''
    task = (yield _current_task)[0][0]
    if task._cancel_requested and not task._cancel_disabled:
        yield _sleep_forever


def _sleep_forever(task):
    pass


@types.coroutine
def sleep_forever(_f=_sleep_forever) -> T.Awaitable:
    '''
    .. code-block::

        await sleep_forever()
    '''
    yield _f


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
dummy_task.name = r"asyncgui.dummy_task"

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


class Event:
    '''
    Similar to :class:`asyncio.Event`.
    The differences are:

    * :meth:`set` accepts any number of arguments but doesn't use them at all so it can be used as a callback function
      in any library.
    * :attr:`is_set` is a property not a function.

    .. code-block::

        e = Event()
        any_library.register_callback(e.set)
    '''

    __slots__ = ('_flag', '_waiting_tasks', )

    def __init__(self):
        self._flag = False
        self._waiting_tasks = []

    @property
    def is_set(self) -> bool:
        return self._flag

    def set(self, *args, **kwargs):
        '''
        Set the event.
        Unlike asyncio's, all tasks waiting for this event to be set will be resumed *immediately*.
        '''
        if self._flag:
            return
        self._flag = True
        tasks = self._waiting_tasks
        self._waiting_tasks = []
        for t in tasks:
            if t is not None:
                t._step()

    def clear(self):
        '''Unset the event.'''
        self._flag = False

    @types.coroutine
    def wait(self) -> T.Awaitable:
        '''
        Wait for the event to be set.
        Return *immediately* if it's already set.
        '''
        if self._flag:
            return
        try:
            tasks = self._waiting_tasks
            idx = len(tasks)
            yield self._waiting_tasks.append
        finally:
            tasks[idx] = None


class ISignal:
    '''
    Same as :class:`Event` except:

    * This one doesn't have ``clear()`` and ``is_set``.
    * Only one task can :meth:`wait` at a time.

    It's quite common that only one task waits for an event to be set.
    Using :class:`Event` may be over-kill in that situation because it is designed to allow multiple tasks to
    ``wait()`` simultaneously.

    .. code-block::

        sig = ISignal()
        any_library.register_callback(sig.set)

        async def async_func():
            await sig.wait()

    .. seealso:: wrapping-a-callback-based-api_
    '''

    __slots__ = ('_flag', '_task', )

    def __init__(self):
        self._flag = False
        self._task = None

    def set(self, *args, **kwargs):
        '''
        Set the event.
        The task waiting for this signal to be set will be resumed *immediately* if there is one.
        '''
        if self._flag:
            return
        self._flag = True
        if (t := self._task) is not None:
            t._step()

    _decrease_or_set = set

    @types.coroutine
    def wait(self) -> T.Awaitable:
        '''
        Wait for the signal to be set. Return *immediately* if it's already set.
        Raise :exc:`InvalidStateError` if there is already a task waiting for it.
        '''
        if self._flag:
            return
        if self._task is not None:
            raise InvalidStateError("There is already a task waiting for this signal to be set.")
        try:
            yield self._store_task
        finally:
            self._task = None

    def _store_task(self, task):
        self._task = task


class TaskCounter:
    '''
    (internal)
    数値が零になった事を通知する仕組みを持つカウンター。
    親taskが自分の子task達の終了を待つのに用いる。
    '''

    __slots__ = ('_signal', '_n_tasks', )

    def __init__(self, initial=0, /):
        self._n_tasks = initial
        self._signal = ISignal()

    def increase(self):
        self._n_tasks += 1

    def decrease(self):
        n = self._n_tasks - 1
        assert n >= 0, potential_bug_msg
        self._n_tasks = n
        if not n:
            self._signal.set()

    _decrease_or_set = decrease

    async def to_be_zero(self) -> T.Awaitable:
        if self._n_tasks:
            sig = self._signal
            sig._flag = False
            await sig.wait()

    def __bool__(self):
        return not not self._n_tasks  # 'not not' is not a typo


async def _wait_xxx(debug_msg, on_child_end, *aws: T.Iterable[Aw_or_Task]) -> T.Awaitable[T.Sequence[Task]]:
    children = tuple(v if isinstance(v, Task) else Task(v) for v in aws)
    if not children:
        return children
    counter = TaskCounter(len(children))
    parent = await current_task()

    try:
        with CancelScope(parent) as scope:
            on_child_end = partial(on_child_end, scope, counter)
            for c in children:
                c._suppresses_exc = True
                c._on_end = on_child_end
                start(c)
            await counter.to_be_zero()
    finally:
        if counter:
            for c in children:
                c.cancel()
            if counter:
                try:
                    parent._cancel_disabled += 1
                    await counter.to_be_zero()
                finally:
                    parent._cancel_disabled -= 1
        exceptions = tuple(e for c in children if (e := c._exc_caught) is not None)
        if exceptions:
            raise ExceptionGroup(debug_msg, exceptions)
        if (parent._cancel_level is not None) and (not parent._cancel_disabled):
            await sleep_forever()
            assert False, potential_bug_msg
    return children


def _on_child_end__ver_all(scope, counter_or_signal, child):
    counter_or_signal._decrease_or_set()
    if child._exc_caught is not None:
        scope.cancel()


def _on_child_end__ver_any(scope, counter_or_signal, child):
    counter_or_signal._decrease_or_set()
    if child._exc_caught is not None or child.finished:
        scope.cancel()


_wait_xxx_type = T.Callable[..., T.Awaitable[T.Sequence[Task]]]
wait_all: _wait_xxx_type = partial(_wait_xxx, "wait_all()", _on_child_end__ver_all)
'''
Run multiple tasks concurrently, and wait for **all** of them to **end**. When any of them raises an exception, the others
will be cancelled, and the exception will be propagated to the caller, like :class:`trio.Nursery`.

.. code-block::

    tasks = await wait_all(async_fn1(), async_fn2(), async_fn3())
    if tasks[0].finished:
        print("The return value of async_fn1() :", tasks[0].result)
'''
wait_any: _wait_xxx_type = partial(_wait_xxx, "wait_any()", _on_child_end__ver_any)
'''
Run multiple tasks concurrently, and wait for **any** of them to **finish**. As soon as that happens, the others will be
cancelled. When any of them raises an exception, the others will be cancelled, and the exception will be propagated to
the caller, like :class:`trio.Nursery`.

.. code-block::

    tasks = await wait_any(async_fn1(), async_fn2(), async_fn3())
    if tasks[0].finished:
        print("The return value of async_fn1() :", tasks[0].result)
'''


@asynccontextmanager
async def _wait_xxx_cm(debug_msg, on_child_end, wait_bg, aw: Aw_or_Task):
    signal = ISignal()
    fg_task = await current_task()
    bg_task = aw if isinstance(aw, Task) else Task(aw)
    exc = None

    try:
        with CancelScope(fg_task) as scope:
            bg_task._on_end = partial(on_child_end, scope, signal)
            bg_task._suppresses_exc = True
            yield start(bg_task)
            if wait_bg:
                await signal.wait()
    except Exception as e:
        exc = e
    finally:
        bg_task.cancel()
        if not signal._flag:
            try:
                fg_task._cancel_disabled += 1
                await signal.wait()
            finally:
                fg_task._cancel_disabled -= 1
        excs = tuple(
            e for e in (exc, bg_task._exc_caught, )
            if e is not None
        )
        if excs:
            raise ExceptionGroup(debug_msg, excs)
        if (fg_task._cancel_level is not None) and (not fg_task._cancel_disabled):
            await sleep_forever()
            assert False, potential_bug_msg


_wait_xxx_cm_type = T.Callable[[Aw_or_Task], T.AsyncContextManager[Task]]
wait_all_cm: _wait_xxx_cm_type = partial(_wait_xxx_cm, "wait_all_cm()", _on_child_end__ver_all, True)
'''See :doc:`structured-concurrency`.'''
wait_any_cm: _wait_xxx_cm_type = partial(_wait_xxx_cm, "wait_any_cm()", _on_child_end__ver_any, False)
'''See :doc:`structured-concurrency`.'''
run_as_primary: _wait_xxx_cm_type = partial(_wait_xxx_cm, "run_as_primary()", _on_child_end__ver_any, True)
'''See :doc:`structured-concurrency`.'''
run_as_secondary: _wait_xxx_cm_type = partial(_wait_xxx_cm, "run_as_secondary()", _on_child_end__ver_all, False)
'''See :doc:`structured-concurrency`.'''


class Nursery:
    '''
    Similar to :class:`trio.Nursery`.
    You should not directly instantiate this, use :func:`open_nursery`.
    '''

    __slots__ = ('_closed', '_children', '_scope', '_counters', '_callbacks', )

    def __init__(self, children, scope, counter, daemon_counter):
        self._closed = False
        self._children = children
        self._scope = scope
        self._counters = (daemon_counter, counter, )
        self._callbacks = (
            partial(_on_child_end__ver_all, scope, daemon_counter),
            partial(_on_child_end__ver_all, scope, counter),
        )

    def start(self, aw: Aw_or_Task, /, *, daemon=False) -> Task:
        '''
        *Immediately* start a Task/Awaitable under the supervision of the nursery.

        If the argument is a :class:`Task`, itself will be returned. If it's a :class:`typing.Awaitable`,
        it will be wrapped in a Task, and that Task will be returned.

        The ``daemon`` parameter acts like the one in the :mod:`threading` module.
        When only daemon tasks are left, they get cancelled, and the nursery closes.
        '''
        if self._closed:
            raise InvalidStateError("Nursery has been already closed")
        child = aw if isinstance(aw, Task) else Task(aw)
        child._suppresses_exc = True
        child._on_end = self._callbacks[not daemon]
        self._counters[not daemon].increase()
        self._children.append(child)
        return start(child)

    def close(self):
        '''Cancel all the child tasks in the nursery as soon as possible. '''
        self._closed = True
        self._scope.cancel()

    @property
    def closed(self) -> bool:
        return self._closed


@asynccontextmanager
async def open_nursery() -> T.AsyncIterator[Nursery]:
    '''
    Equivalent of :func:`trio.open_nursery`.

    .. code-block::

        async with open_nursery() as nursery:
            nursery.start(other_async_func1())
            nursery.start(other_async_func2())
    '''
    children = []
    exc = None
    parent = await current_task()
    counter = TaskCounter()
    daemon_counter = TaskCounter()

    try:
        with CancelScope(parent) as scope:
            nursery = Nursery(children, scope, counter, daemon_counter)
            yield nursery
            await counter.to_be_zero()
    except Exception as e:
        exc = e
    finally:
        nursery._closed = True
        for c in children:
            c.cancel()
        try:
            parent._cancel_disabled += 1
            await daemon_counter.to_be_zero()
            await counter.to_be_zero()
        finally:
            parent._cancel_disabled -= 1
        excs = tuple(
            e for e in itertools.chain((exc, ), (c._exc_caught for c in children))
            if e is not None
        )
        if excs:
            raise ExceptionGroup("Nursery", excs)
        if (parent._cancel_level is not None) and (not parent._cancel_disabled):
            await sleep_forever()
            assert False, potential_bug_msg


class IBox:
    '''
    :class:`ISignal` + the capability to transfer values.

    .. code-block::

        box = IBox()
        ...
        box.put(1, 2, key='value')

        async def async_func():
            args, kwargs = await box.get()
            assert args == (1, 2, )
            assert kwargs == {'key': 'value', }

    .. note::

        This is not a generic item storage, but is designed for a specific purpose.
        See wrapping-a-callback-based-api_ for details.
    '''

    __slots__ = ('_item', '_getter', )

    def __init__(self):
        self._item = None
        self._getter = None

    def put(self, *args, **kwargs):
        '''Put an item into the box. This has an effect only on the first call; subsequent calls will be ignored. '''
        if self._item is not None:
            return
        self._item = (args, kwargs, )
        if (getter := self._getter) is not None:
            getter._step(*args, **kwargs)

    @types.coroutine
    def get(self) -> T.Awaitable[T.Tuple[tuple, dict]]:
        '''
        Get an item inside the box. If the box is empty, wait until one is available.
        Raise :exc:`InvalidStateError` if there is already a task waiting for it.
        '''
        if self._getter is not None:
            raise InvalidStateError("There is already a task trying to get an item from this box.")
        if self._item is None:
            try:
                return (yield self._store_getter)
            finally:
                self._getter = None
        else:
            return self._item

    def _store_getter(self, task):
        self._getter = task


# -----------------------------------------------------------------------------
# Aliases
# -----------------------------------------------------------------------------
run_as_daemon = run_as_secondary  #: An alias for :func:`run_as_secondary`.
TaskGroup = open_nursery  #: An alias for :func:`open_nursery`.
and_ = wait_all  #: An alias for :func:`wait_all`. This exists solely for backward compatibility.
or_ = wait_any  #: An alias for :func:`wait_any`. This exists solely for backward compatibility.
