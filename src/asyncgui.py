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
    'IBox', 'ISignal',

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
    BaseExceptionGroup = BaseExceptionGroup
    ExceptionGroup = ExceptionGroup

potential_bug_msg = '''
This may be a bug of this library. Please make a minimal code that reproduces the bug, and open an issue at the GitHub
repository, and post that code. (https://github.com/gottadiveintopython/asyncgui).
'''


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class _Cancelled(BaseException):
    @cached_property
    def level(self) -> int:
        return self.args[0]


Cancelled = (_Cancelled, GeneratorExit, )


class TaskState(enum.Enum):
    CREATED = enum.auto()
    '''CORO_CREATED'''

    STARTED = enum.auto()
    '''CORO_RUNNING or CORO_SUSPENDED'''

    CANCELLED = enum.auto()
    '''CORO_CLOSED by 'Task.cancel()' or an unhandled exception'''

    FINISHED = enum.auto()
    '''CORO_CLOSED (finished)'''


class Task:
    __slots__ = (
        'name', '_uid', '_root_coro', '_state', '_result', '_on_end',
        '_exc_caught', '_suppresses_exc',
        '_cancel_disabled', '_cancel_depth', '_cancel_level',
    )

    _uid_iter = itertools.count()

    def __init__(self, awaitable: T.Awaitable, /):
        if not isawaitable(awaitable):
            raise ValueError(str(awaitable) + " is not awaitable.")
        self._uid = next(self._uid_iter)
        self.name = ""
        self._cancel_disabled = 0
        self._root_coro = self._wrapper(awaitable)
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
        return self._uid

    @property
    def root_coro(self) -> T.Coroutine:
        return self._root_coro

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def finished(self) -> bool:
        return self._state is TaskState.FINISHED

    @property
    def cancelled(self) -> bool:
        return self._state is TaskState.CANCELLED

    @property
    def result(self) -> T.Any:
        '''Result of the task. If the task hasn't finished yet,
        InvalidStateError will be raised.
        '''
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
        '''Cancel the task as soon as possible'''
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

    # give 'cancel()' an alias so that we can pass a Task instance to `contextlib.closing`
    close = cancel

    @property
    def _cancel_requested(self) -> bool:
        return self._cancel_level is not None

    @property
    def _is_cancellable(self) -> bool:
        '''Whether the task can immediately be cancelled.'''
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


Aw_or_Task = T.Union[T.Awaitable, Task]


def start(aw: Aw_or_Task, /) -> Task:
    '''Starts an asyncgui-flavored awaitable or a Task.

    If the argument is a Task, itself will be returned. If it's an awaitable,
    it will be wrapped in a Task, and the Task will be returned.
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
    You should not directly instantiate this. Use :func:`open_cancel_scope`.
    '''
    __slots__ = ('_task', '_depth', 'cancelled_caught', 'cancel_called', )

    def __init__(self, task: Task, /):
        self._task = task
        self.cancelled_caught = False
        self.cancel_called = False

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
        return self._task is None

    def cancel(self):
        if self.cancel_called:
            return
        self.cancel_called = True
        if not self.closed:
            self._task.cancel(self._depth)


class open_cancel_scope:
    '''
    Same as :class:`trio.CancelScope` except this one is an async context manager.

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


@types.coroutine
def current_task(_f=lambda task: task._step(task)) -> T.Awaitable[Task]:
    '''Returns the Task instance corresponding to the caller.'''
    return (yield _f)[0][0]


class disable_cancellation:
    '''
    Async context manager that protects its code-block from cancellation.

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


async def check_cancellation():
    '''
    (experimental) If the ``.cancel()`` method of the current task has been
    called and the task is not protected from cancellation, cancels the task
    immediately. Otherwise, does nothing.
    '''
    task = await current_task()
    if task._cancel_requested and not task._cancel_disabled:
        await sleep_forever()


@types.coroutine
def sleep_forever(_f=lambda task: None) -> T.Awaitable:
    yield _f


dummy_task = Task(sleep_forever())
dummy_task.cancel()
dummy_task.name = r"asyncgui.dummy_task"

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


class Event:
    '''
    Equivalent of :class:`asyncio.Event`.

    Difference
    ----------

    :meth:`set` accepts any number of arguments but doesn't use them at all so it can be used as a callback function
    of any library.

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
        if self._flag:
            return
        self._flag = True
        tasks = self._waiting_tasks
        self._waiting_tasks = []
        for t in tasks:
            if t is not None:
                t._step()

    def clear(self):
        self._flag = False

    @types.coroutine
    def wait(self) -> T.Awaitable:
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

    The reason this is introduced
    -----------------------------

    It's quite common that only one task waits for an event to be fired,
    and :class:`Event` may be over-kill in that situation because it is designed to accept multiple tasks.
    '''

    __slots__ = ('_flag', '_task', )

    def __init__(self):
        self._flag = False
        self._task = None

    def set(self, *args, **kwargs):
        if self._flag:
            return
        self._flag = True
        if (t := self._task) is not None:
            t._step()

    _decrease_or_set = set

    @types.coroutine
    def wait(self) -> T.Awaitable:
        if self._flag:
            return
        if self._task is not None:
            raise InvalidStateError("There is already a task waiting for this signal to set.")
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


async def _wait_xxx(debug_msg, on_child_end, *aws: T.Iterable[Aw_or_Task]):
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
wait_any: _wait_xxx_type = partial(_wait_xxx, "wait_any()", _on_child_end__ver_any)


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
wait_any_cm: _wait_xxx_cm_type = partial(_wait_xxx_cm, "wait_any_cm()", _on_child_end__ver_any, False)
run_as_primary: _wait_xxx_cm_type = partial(_wait_xxx_cm, "run_as_primary()", _on_child_end__ver_any, True)
run_as_secondary: _wait_xxx_cm_type = partial(_wait_xxx_cm, "run_as_secondary()", _on_child_end__ver_all, False)


class Nursery:
    '''
    You should not directly instantiate this. Use :func:`open_nursery`.
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
        if self._closed:
            raise InvalidStateError("Nursery has been already closed")
        child = aw if isinstance(aw, Task) else Task(aw)
        child._suppresses_exc = True
        child._on_end = self._callbacks[not daemon]
        self._counters[not daemon].increase()
        self._children.append(child)
        return start(child)

    def close(self):
        '''
        Cancel all the child tasks inside the nursery.
        '''
        self._closed = True
        self._scope.cancel()

    @property
    def closed(self) -> bool:
        return self._closed


@asynccontextmanager
async def open_nursery() -> T.AsyncIterator[Nursery]:
    '''
    Equivalent of :func:`trio.open_nursery`.
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
    An item box with the following limitations.

    * You can :meth:`put` an item in it only once. Doing it more than once will be ignored.
    * Only one task can :meth:`get` an item from it at a time.

    .. note::

        This exists for the purpose of wrapping a callback-based api in an async/await-based api.
        Using it for any other purpose is not recommended.
    '''

    __slots__ = ('_item', '_getter', )

    def __init__(self):
        self._item = None
        self._getter = None

    def put(self, *args, **kwargs):
        if self._item is not None:
            return
        self._item = (args, kwargs, )
        if (getter := self._getter) is not None:
            getter._step(*args, **kwargs)

    @types.coroutine
    def get(self) -> T.Awaitable[T.Tuple[tuple, dict]]:
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

run_as_daemon = run_as_secondary
TaskGroup = open_nursery
and_ = wait_all
or_ = wait_any
